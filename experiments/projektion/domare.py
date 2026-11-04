"""Domaren för projektionen: konserveringen av extremerna, träffen för det kraftiga och spärrarna.

    python experiments/projektion/domare.py kör --läge validering --system kedja persistens
    python experiments/projektion/domare.py tabell --läge validering --system kedja persistens pysteps

Ett system är en klass (se System) som får radarn fram till utgåvetiden och ger 20 kvartsmedel i
mm/h för kvartarna som slutar 15 min till 5 h efter utgåvetiden. System som har ett tillstånd
(platskartan) får dessutom radarn var 5:e minut under uppvärmningen före varje utgåvetid
(observe), så att tillståndet byggs upp som i drift.

Lägen (LÄGEN):
  validering       valideringsdagarna, 2 km, samma utgåvetider som /data/sverige/kedja (varje hel timme)
  validering_gles  som validering men var 3:e timme, för dyra system (S-PROG); jämförs med kedjan på samma tider
  traning          de 28 träningsdagarna, 2 km, var 3:e timme
  snabb            6 av träningsdagarna, 4 km (medel av 2 x 2 pixlar), var 3:e timme, för sökningen

Testdelen i dagar.json finns inte i något läge och läses aldrig.

Måtten räknas på rutorna där radaranalysen vid utgåvetiden och radarns kvartsmedel har data
(samma rutor för alla system), vid ledtiderna LEADS, och sparas som summor per dygn i
/data/projektion/domare/<läge>/<system>/<dag>.npz. Tabellen bildar kvoter och poäng ur summorna
och skillnaden mot baslinjen med 95 %-intervall från bootstrap över dygnen (se tabell()).

Rörelsefälten (Lucas-Kanade som i kedjan, glesa vektorer) sparas per 5-minuterstid under
/data/projektion/cache/rorelse/<res>km/<dag>/<HHMM>.npz och återanvänds av alla system.
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import json
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import cv2
import numpy as np

cv2.setNumThreads(1)
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))
sys.path.insert(0, str(HERE.parent / "sverige"))
from data import load_days, radar_path  # noqa: E402
from knep import advect, model, radar, render  # noqa: E402

ROOT = Path("/data/projektion")
CACHE = ROOT / "cache"
OUT = ROOT / "domare"
CHAIN_DIR = Path("/data/sverige/kedja")
RESULTS = HERE / "resultat"

Q = timedelta(minutes=15)
NQ = 20
STEP = radar.STEP
WARMUP = timedelta(minutes=90)           # platskartan behöver 30-minutersprognoserna från senaste timmen
HISTORY = 12                             # bilder bakåt som i drift (cli --history)
MIN_HISTORY = 7                          # som experiments/sverige/kedja.py: färre i följd ger ingen prognos
LEADS = [1, 2, 4, 6, 8, 12, 16, 20]      # kvartar: 15, 30, 60, 90, 120, 180, 240 och 300 min
SHOW = [1, 2, 4, 8, 12, 20]              # i tabellen: 15 och 30 min, 1, 2, 3 och 5 h

WET = 0.1                                # mm/h, våta rutor för percentilerna
PCTS = [99.0, 99.9]
AREA_THR = [5.0, 10.0, 20.0]
CT_THR = [1.0, 5.0, 10.0]                # kontingenstabeller (CSI, SEDI)
FSS_CASES = [(1.0, 30), (5.0, 10), (5.0, 30), (10.0, 10), (10.0, 30)]  # (mm/h, km)
BLOCK_KM = 30
BMAX_WET = 0.5                           # block med max minst så här räknas i blockmaxets fördelning
BMAX_Q = [50.0, 90.0]
BANDS_KM = [(4, 8), (8, 16)]
TILE_KM = 256
EDGES = np.concatenate([[0.0], np.geomspace(WET, 500.0, 400)])  # histogrammens kanter i mm/h


# ---------- lägen ----------

def training_days() -> list[str]:
    return [d["day"] for d in json.loads((HERE / "traning.json").read_text())]


FAST_DAYS = ["2020-02-10", "2021-05-11", "2023-07-12", "2024-07-28", "2024-09-26", "2024-12-19"]


def _val_days() -> list[str]:
    return [d["day"] for d in load_days("validering")]


def _chain_hours(day: str) -> list[int]:
    return sorted(int(p.stem[:2]) for p in (CHAIN_DIR / day).glob("*.npz"))


LÄGEN = {
    "validering": dict(days=_val_days, res=2, hours=_chain_hours, ref="kedja"),
    "validering_gles": dict(days=_val_days, res=2, hours=lambda d: [h for h in _chain_hours(d) if h % 3 == 0], ref="kedja"),
    "traning": dict(days=training_days, res=2, hours=lambda d: list(range(0, 24, 3)), ref="kedja_om"),
    "snabb": dict(days=lambda: FAST_DAYS, res=4, hours=lambda d: list(range(0, 24, 3)), ref="kedja_om"),
}


def mode_days(mode: str) -> list[str]:
    days = LÄGEN[mode]["days"]()
    test = {d["day"] for d in load_days() if d["part"] == "test"}
    assert not test & set(days), "testdelen får aldrig användas"
    return days


# ---------- radarn och rörelsen ----------

def coarsen(x: np.ndarray, f: int) -> np.ndarray:
    """Medel av f x f pixlar (NaN om någon saknas), med kanten som inte går jämnt upp borttagen."""
    if f == 1:
        return x
    h, w = (x.shape[0] // f) * f, (x.shape[1] // f) * f
    return x[:h, :w].reshape(h // f, f, w // f, f).mean(axis=(1, 3)).astype(np.float32)


class Ctx:
    """Radarn och rörelsen för ett dygn i ett läge, med cache. Systemen läser bara bakåt från t."""

    def __init__(self, day: str, res: int, motion_root: Path = CACHE / "rorelse"):
        self.day, self.res, self.f = day, res, res // 2
        self.frames: dict = {}
        self.motions: dict = {}
        self.motion_dir = motion_root / f"{res}km" / day
        self.chain = model.Chain(None)   # rörelsens inställningar som i drift

    def frame(self, t: datetime):
        if t not in self.frames:
            p, f = radar_path(t), None
            if p.exists():
                try:
                    f = coarsen(radar.read_rain(p)[0], self.f)
                except Exception:  # noqa: BLE001  en trasig fil räknas som saknad
                    f = None
            self.frames[t] = f
        return self.frames[t]

    def forget(self, before: datetime) -> None:
        for t in [t for t in self.frames if t < before]:
            del self.frames[t]
        for t in [t for t in self.motions if t < before]:
            del self.motions[t]

    def history(self, t: datetime, n: int = HISTORY):
        """De senaste bilderna i följd fram till t (högst n), äldst först, eller None om färre än MIN_HISTORY."""
        out = []
        for k in range(n):
            f = self.frame(t - k * STEP)
            if f is None:
                break
            out.append(f)
        return np.stack(out[::-1]) if len(out) >= MIN_HISTORY else None

    def quarter(self, end: datetime):
        fs = [self.frame(end - k * STEP) for k in range(3)]
        return None if any(f is None for f in fs) else np.mean(fs, axis=0).astype(np.float32)

    def motion(self, t: datetime) -> np.ndarray | None:
        """Kedjans rörelsefält vid t i pixlar per 5 min, (2, H, W); glesa vektorerna sparas på disk."""
        if t in self.motions:
            return self.motions[t]
        p = self.motion_dir / f"{t:%H%M}.npz"
        c = self.chain
        if p.exists():
            d = np.load(p)
            xy, uv = d["xy"], d["uv"]
        else:
            obs = self.history(t)
            if obs is None:
                return None
            idx = [max(0, len(obs) - 1 - c.motion_gap * m) for m in range(c.motion_frames - 1, -1, -1)]
            xy, uv = model._quiet(model.dense_lucaskanade, model._db(obs[idx]), dense=False)
            xy, uv = np.asarray(xy, np.float32), np.asarray(uv, np.float32)
            self.motion_dir.mkdir(parents=True, exist_ok=True)
            tmp = p.with_suffix(".tmp.npz")
            np.savez_compressed(tmp, xy=xy, uv=uv)
            tmp.replace(p)
        shape = self.frame(t).shape
        m = model.dense_motion(xy.astype(np.float64), uv.astype(np.float64), shape, c.motion_step) / c.motion_gap
        self.motions[t] = m
        return m


# ---------- systemen ----------

class System:
    """Grundklassen. forecast ger (20, H, W) kvartsmedel i mm/h, NaN eller None där det saknas.

    warm = True: observe anropas var 5:e minut under WARMUP före varje utgåvetid (inte vid själva
    utgåvetiden), i tidsordning. reset anropas i början av varje dygn."""

    name = "system"
    warm = False

    def reset(self) -> None:
        pass

    def observe(self, t: datetime, ctx: Ctx) -> None:
        pass

    def forecast(self, t: datetime, ctx: Ctx) -> np.ndarray | None:
        raise NotImplementedError


def quarters(rain: np.ndarray) -> np.ndarray:
    """60 bilder var 5:e minut till 20 kvartsmedel (som kedja.py och render.aggregate)."""
    return rain.reshape(NQ, 3, *rain.shape[1:]).mean(axis=1)


class Kedja(System):
    """Driftens kedja som den sparats i /data/sverige/kedja (bara valideringsdagarna, 2 km)."""

    name = "kedja"

    def forecast(self, t, ctx):
        p = CHAIN_DIR / ctx.day / f"{t:%H%M}.npz"
        if ctx.res != 2 or not p.exists():
            return None
        return render.decode_values(np.load(p)["codes"])


class KedjaOm(System):
    """Kedjan körd om här (model.Chain), med platskartans tillstånd uppvärmt som i drift."""

    name = "kedja_om"
    warm = True

    def __init__(self, **kw):
        self.chain = model.Chain(None, **kw)
        self.warm = self.chain.location

    def reset(self):
        self.state = model.State()

    def observe(self, t, ctx):
        """Det som Chain.run(obs, t, 6, state) gör med tillståndet, men bara steg 6 flyttas och matchas
        (samma värden, test_domare.test_warm_equals_chain_run)."""
        a = ctx.frame(t)
        if ctx.history(t) is None:
            return
        motion = ctx.motion(t)
        *_, (mx, my, outside) = advect.displacements(motion, 6)
        z = np.nan_to_num(a).astype(np.float32)
        raw, tgt = advect.warp(z, mx, my, outside, 1), advect.warp(z, mx, my, outside, 0)
        raw[~np.isfinite(a)] = np.nan
        tgt[~np.isfinite(a)] = np.nan
        st = self.state
        st.obs[t.isoformat()] = a.astype(np.float32)
        st.fc30[(t + 6 * model.STEP).isoformat()] = model.cdf_match(raw, tgt) if self.chain.match else raw
        st.prune(t)

    def forecast(self, t, ctx):
        obs = ctx.history(t)
        if obs is None:
            return None
        return quarters(self.chain.run(obs, t, NQ * 3, self.state, motion=ctx.motion(t)).rain)


class Persistens(System):
    name = "persistens"

    def forecast(self, t, ctx):
        a = ctx.frame(t)
        return None if a is None else np.repeat(a[None], NQ, axis=0)


class Pysteps(System):
    """Referensen model.nowcast: Lucas-Kanade (tätt fält) på senaste timmens bilder och
    semi-Lagrangesk extrapolering. Extrapoleringen görs med advect.extrapolate, som är samma
    schema som pysteps (tests/test_advect.py) men mångdubbelt snabbare."""

    name = "pysteps"

    def forecast(self, t, ctx):
        obs = ctx.history(t)
        if obs is None:
            return None
        v = model._quiet(model.dense_lucaskanade, model._db(obs))
        fc = advect.extrapolate(np.nan_to_num(obs[-1]), v, NQ * 3)
        fc[:, ~np.isfinite(obs[-1])] = np.nan
        return quarters(fc)


class Sprog(System):
    """S-PROG ur pysteps (6 kaskadnivåer, AR(2)) med kedjans rörelse, i 15-minuterssteg på
    bilderna för 30, 15 och 0 min sedan. Värdet vid kvartens slut får stå för kvartsmedlet."""

    name = "sprog"

    def forecast(self, t, ctx):
        from pysteps import nowcasts
        from pysteps.utils.transformation import dB_transform

        obs = ctx.history(t)
        v = ctx.motion(t)
        if obs is None or v is None:
            return None
        sp = model._quiet(nowcasts.get_method("sprog"), model._db(obs[[-7, -4, -1]]), 3 * v, NQ,
                          precip_thr=-10.0, n_cascade_levels=6, ar_order=2)
        out, _ = dB_transform(sp, threshold=-10.0, inverse=True)
        out[out < 0.1] = 0.0
        out = out.astype(np.float32)
        out[:, ~np.isfinite(obs[-1])] = np.nan
        return out


SYSTEMS = {
    "kedja": Kedja,
    "kedja_om": KedjaOm,
    "kedja_utan_matchning": lambda: KedjaOm(match=False),
    "kedja_utan_platskarta": lambda: KedjaOm(location=False),
    "persistens": Persistens,
    "pysteps": Pysteps,
    "sprog": Sprog,
}


def make_system(name: str) -> System:
    """Ett system ur SYSTEMS, eller 'modul:Klass' för system i andra filer under experiments/projektion."""
    if name in SYSTEMS:
        s = SYSTEMS[name]()
    else:
        import importlib
        mod, cls = name.split(":")
        s = getattr(importlib.import_module(mod), cls)()
    s.name = name.replace(":", "_")
    return s


# ---------- måtten för ett fält ----------

def wet_hist(x: np.ndarray) -> np.ndarray:
    return np.histogram(x[x >= WET], EDGES)[0]


def hist_quantile(h: np.ndarray, p: float) -> float:
    """Percentilen p (0..100) ur ett histogram över EDGES, linjärt inom facket."""
    n = h.sum()
    if n == 0:
        return np.nan
    c = np.cumsum(h)
    target = p / 100 * n
    i = int(np.searchsorted(c, target))
    i = min(i, len(h) - 1)
    lo = c[i - 1] if i > 0 else 0
    frac = (target - lo) / max(h[i], 1)
    return float(EDGES[i] + frac * (EDGES[i + 1] - EDGES[i]))


def block_max(x: np.ndarray, m: np.ndarray, size: int) -> np.ndarray:
    """Maxvärdet i block om size x size pixlar, för de block som ligger helt inom masken."""
    h, w = (x.shape[0] // size) * size, (x.shape[1] // size) * size
    xb = np.where(m, x, 0.0)[:h, :w].reshape(h // size, size, w // size, size)
    mb = m[:h, :w].reshape(h // size, size, w // size, size).all(axis=(1, 3))
    return xb.max(axis=(1, 3))[mb]


def contingency(f, o, m, thr) -> np.ndarray:
    F, O = (f >= thr) & m, (o >= thr) & m
    hits = (F & O).sum()
    fa = F.sum() - hits
    miss = O.sum() - hits
    return np.array([hits, miss, fa, m.sum() - hits - miss - fa], np.float64)


def _box(x, size):
    return cv2.boxFilter(x, cv2.CV_32F, (size, size), normalize=False, borderType=cv2.BORDER_CONSTANT)


def fss_sums(f, o, m, thr, size) -> np.ndarray:
    """(summa (pf - po)², summa pf² + po²) över maskens rutor, andelarna räknade inom masken."""
    mf = m.astype(np.float32)
    den = np.maximum(_box(mf, size), 1e-6)
    pf = (_box(((f >= thr) & m).astype(np.float32), size) / den)[m]
    po = (_box(((o >= thr) & m).astype(np.float32), size) / den)[m]
    return np.array([((pf - po) ** 2).sum(), (pf ** 2 + po ** 2).sum()], np.float64)


def spectrum_tiles(m: np.ndarray, o: np.ndarray, tile: int, min_wet: float = 0.02) -> list:
    h, w = m.shape
    out = []
    for i in range(0, h - tile + 1, tile // 2):
        for j in range(0, w - tile + 1, tile // 2):
            if m[i:i + tile, j:j + tile].all() and (o[i:i + tile, j:j + tile] >= 0.1).mean() >= min_wet:
                out.append((i, j))
    return out


class Spectrum:
    """Effekten för dBR per våglängdsband, som experiments/sverige/form.py men för valfri upplösning."""

    def __init__(self, res: float):
        self.tile = int(TILE_KM / res)
        self.win = np.outer(np.hanning(self.tile), np.hanning(self.tile)).astype(np.float32)
        k = np.hypot(*np.meshgrid(np.fft.fftfreq(self.tile), np.fft.rfftfreq(self.tile), indexing="ij"))
        wl = np.where(k > 0, res / np.maximum(k, 1e-9), np.inf)
        self.bands = [(wl >= lo) & (wl < hi) for lo, hi in BANDS_KM]

    def __call__(self, x, ts) -> np.ndarray:
        d = 10 * np.log10(np.maximum(x, 0.1))
        acc = np.zeros(len(BANDS_KM))
        for i, j in ts:
            t = d[i:i + self.tile, j:j + self.tile]
            p = np.abs(np.fft.rfft2((t - t.mean()) * self.win)) ** 2
            acc += [p[b].mean() if b.any() else np.nan for b in self.bands]
        return acc


def jump(new, old, m) -> tuple[float, float]:
    """(summa |ny - gammal|, summa (ny + gammal) / 2) över masken; kvoten är form.jump."""
    a, b = new[m], old[m]
    return float(np.abs(a - b).sum()), float(0.5 * (a.sum() + b.sum()))


class Acc:
    """Summorna för ett dygn, (len(LEADS), ...) per mått, för systemet (f) och radarn (o)."""

    def __init__(self, res: float):
        L = len(LEADS)
        self.res = res
        self.spec = Spectrum(res)
        self.d = {
            "n": np.zeros(L),
            "hist_f": np.zeros((L, len(EDGES) - 1)), "hist_o": np.zeros((L, len(EDGES) - 1)),
            "bmax_f": np.zeros((L, len(EDGES) - 1)), "bmax_o": np.zeros((L, len(EDGES) - 1)),
            "area_f": np.zeros((L, len(AREA_THR))), "area_o": np.zeros((L, len(AREA_THR))),
            "vol": np.zeros((L, 2)),
            "ct": np.zeros((L, len(CT_THR), 4)),
            "fss": np.zeros((L, len(FSS_CASES), 2)),
            "spec": np.zeros((L, len(BANDS_KM), 3)),  # summa f, summa o, antal rutor
            "jump": np.zeros((L, 2)),
        }

    def add(self, i: int, f: np.ndarray, o: np.ndarray, m: np.ndarray, old: np.ndarray | None = None) -> None:
        d = self.d
        f, o = np.where(m, np.nan_to_num(f), 0.0).astype(np.float32), np.where(m, o, 0.0).astype(np.float32)
        d["n"][i] += 1
        d["hist_f"][i] += wet_hist(f[m])
        d["hist_o"][i] += wet_hist(o[m])
        size = max(1, round(BLOCK_KM / self.res))
        bf, bo = block_max(f, m, size), block_max(o, m, size)
        d["bmax_f"][i] += np.histogram(bf[bf >= BMAX_WET], EDGES)[0]
        d["bmax_o"][i] += np.histogram(bo[bo >= BMAX_WET], EDGES)[0]
        d["area_f"][i] += [(f[m] >= t).sum() for t in AREA_THR]
        d["area_o"][i] += [(o[m] >= t).sum() for t in AREA_THR]
        d["vol"][i] += [f[m].sum(), o[m].sum()]
        for j, t in enumerate(CT_THR):
            d["ct"][i, j] += contingency(f, o, m, t)
        for j, (t, km) in enumerate(FSS_CASES):
            d["fss"][i, j] += fss_sums(f, o, m, t, int(round(km / self.res)) | 1)
        ts = spectrum_tiles(m, o, self.spec.tile)
        if ts:
            d["spec"][i, :, 0] += self.spec(f, ts)
            d["spec"][i, :, 1] += self.spec(o, ts)
            d["spec"][i, :, 2] += len(ts)
        if old is not None:
            d["jump"][i] += jump(f, np.where(m, np.nan_to_num(old), 0.0), m)


# ---------- körningen ----------

def run_day(mode: str, day: str, sysname: str, out: Path | None = None) -> dict:
    cfg = LÄGEN[mode]
    res = cfg["res"]
    path = (out or OUT / mode / sysname.replace(":", "_")) / f"{day}.npz"
    if path.exists():
        return dict(np.load(path))
    system = make_system(sysname)
    system.reset()
    ctx = Ctx(day, res)
    acc = Acc(res)
    d0 = datetime.fromisoformat(day).replace(tzinfo=UTC)
    issues = [d0 + timedelta(hours=h) for h in cfg["hours"](day)]
    warm = set()
    if system.warm:
        for t in issues:
            warm |= {t - k * STEP for k in range(1, int(WARMUP / STEP) + 1)}
    started, n, t_fc, prev = time.monotonic(), 0, 0.0, None
    for t in sorted(warm | set(issues)):
        ctx.forget(t - timedelta(hours=2))
        if t not in issues:
            system.observe(t, ctx)
            continue
        analysis = ctx.frame(t)
        if analysis is None:
            continue
        s = time.monotonic()
        fc = system.forecast(t, ctx)
        t_fc += time.monotonic() - s
        if fc is None:
            continue
        if not isinstance(system, Kedja):  # samma kodning som driftens sparade prognoser (värdefilen)
            fc = np.stack([render.decode_values(render.encode_values(x)) for x in fc])
        cov = np.isfinite(analysis)
        for i, k in enumerate(LEADS):
            o = ctx.quarter(t + k * Q)
            if o is None:
                continue
            m = cov & np.isfinite(o)
            old = None
            if prev is not None and t - prev[0] <= timedelta(hours=3):
                j = k + int((t - prev[0]) / Q)
                old = prev[1][j - 1] if j <= NQ else None
            acc.add(i, fc[k - 1], o, m, old)
        prev = (t, fc)
        n += 1
    result = acc.d | {"issues": np.array(n), "seconds": np.array(time.monotonic() - started), "forecast_seconds": np.array(t_fc)}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp.npz")
    np.savez_compressed(tmp, **result)
    tmp.replace(path)
    print(f"{sysname} {mode} {day}: {n} utgåvor på {time.monotonic() - started:.0f} s", flush=True)
    return result


def _job(args):
    return run_day(*args)


def run(mode: str, sysname: str, procs: int = 2, days: list[str] | None = None) -> None:
    from multiprocessing import get_context

    days = days or mode_days(mode)
    started = time.monotonic()
    jobs = [(mode, d, sysname) for d in days]
    if procs <= 1:
        for j in jobs:
            _job(j)
    else:
        with get_context("fork").Pool(procs, maxtasksperchild=1) as pool:
            list(pool.imap_unordered(_job, jobs))
    print(f"{sysname} {mode}: {len(days)} dygn på {time.monotonic() - started:.0f} s med {procs} processer", flush=True)


# ---------- tabellen ----------

def _lr(a, b):
    return np.log(np.maximum(a, 1e-9) / np.maximum(b, 1e-9))


def _sedi(ct):
    h, mi, fa, cn = ct[..., 0], ct[..., 1], ct[..., 2], ct[..., 3]
    H = np.clip(h / np.maximum(h + mi, 1), 1e-6, 1 - 1e-6)
    F = np.clip(fa / np.maximum(fa + cn, 1), 1e-6, 1 - 1e-6)
    lf, lh, l1f, l1h = np.log(F), np.log(H), np.log(1 - F), np.log(1 - H)
    return (lf - lh - l1f + l1h) / (lf + lh + l1f + l1h)


def _hq(h, p):
    return np.array([hist_quantile(x, p) for x in h])


# mått: namn -> (funktion av summorna (summerade över dygnen), slag)
# slag: "kons" |log kvot| ska minska, "träff" ska öka, "spärr+" (ska inte minska), "spärr|" (|log kvot| ska inte öka),
# "spärr-" (ska inte öka), "info" bara redovisat
def _metrics():
    m = {}
    for p in PCTS:
        m[f"q{p:g}"] = (lambda s, p=p: _lr(_hq(s["hist_f"], p), _hq(s["hist_o"], p)), "kons")
    for j, t in enumerate(AREA_THR):
        m[f"yta{t:g}"] = (lambda s, j=j: _lr(s["area_f"][:, j], s["area_o"][:, j]), "kons")
    m["volym"] = (lambda s: _lr(s["vol"][:, 0], s["vol"][:, 1]), "kons")
    for p in BMAX_Q:
        m[f"blockmax_q{p:g}"] = (lambda s, p=p: _lr(_hq(s["bmax_f"], p), _hq(s["bmax_o"], p)), "kons")
    m["blockmax_antal"] = (lambda s: _lr(s["bmax_f"].sum(-1), s["bmax_o"].sum(-1)), "info")
    for j, (t, km) in enumerate(FSS_CASES):
        kind = "spärr+" if t == 1.0 else "träff"
        m[f"fss{t:g}_{km}"] = (lambda s, j=j: 1 - s["fss"][:, j, 0] / np.maximum(s["fss"][:, j, 1], 1e-9), kind)
    csi = lambda s, j: s["ct"][:, j, 0] / np.maximum(s["ct"][:, j, :3].sum(-1), 1)
    m["csi1"] = (lambda s: csi(s, 0), "spärr+")
    m["csi5"] = (lambda s: csi(s, 1), "träff")
    m["sedi5"] = (lambda s: _sedi(s["ct"][:, 1]), "träff")
    m["sedi10"] = (lambda s: _sedi(s["ct"][:, 2]), "träff")
    for j, (lo, hi) in enumerate(BANDS_KM):
        m[f"form{lo}_{hi}"] = (lambda s, j=j: _lr(s["spec"][:, j, 0], s["spec"][:, j, 1]), "spärr|")
    m["hopp"] = (lambda s: s["jump"][:, 0] / np.maximum(s["jump"][:, 1], 1e-9), "spärr-")
    return m


METRICS = _metrics()
SUMKEYS = ["hist_f", "hist_o", "bmax_f", "bmax_o", "area_f", "area_o", "vol", "ct", "fss", "spec", "jump", "n"]


def load(mode: str, sysname: str, days: list[str]) -> dict | None:
    d = OUT / mode / sysname.replace(":", "_")
    if not all((d / f"{x}.npz").exists() for x in days):
        return None
    return {x: dict(np.load(d / f"{x}.npz")) for x in days}


def scores(per_day: dict, days: list[str], w: np.ndarray | None = None) -> dict:
    """Måtten ur summorna för dygnen (med vikter w, antal gånger varje dygn dras)."""
    w = np.ones(len(days)) if w is None else w
    s = {k: sum(wi * per_day[x][k] for wi, x in zip(w, days) if wi) for k in SUMKEYS}
    with np.errstate(all="ignore"):
        return {name: fn(s) for name, (fn, _) in METRICS.items()}


def compare(sys_days: dict, ref_days: dict, days: list[str], nboot: int = 1000, seed: int = 0) -> dict:
    """Värdena och skillnaden mot baslinjen med 95 %-intervall, bootstrap över dygnen.

    Skillnaden är orienterad så att negativt alltid är bättre: |log kvot| för kons och spärr|,
    baslinjen minus systemet för träff och spärr+, systemet minus baslinjen för spärr-."""
    rng = np.random.default_rng(seed)

    def diff(a, b, kind):
        if kind in ("kons", "spärr|"):
            return np.abs(a) - np.abs(b)
        if kind in ("träff", "spärr+"):
            return b - a
        return a - b

    base_s, base_r = scores(sys_days, days), scores(ref_days, days)
    boots = {k: [] for k in METRICS}
    for _ in range(nboot):
        w = np.bincount(rng.integers(0, len(days), len(days)), minlength=len(days)).astype(float)
        a, b = scores(sys_days, days, w), scores(ref_days, days, w)
        for k, (_, kind) in METRICS.items():
            boots[k].append(diff(a[k], b[k], kind))
    out = {}
    for k, (_, kind) in METRICS.items():
        bs = np.array(boots[k])
        with np.errstate(all="ignore"):
            lo, hi = np.nanpercentile(bs, 2.5, axis=0), np.nanpercentile(bs, 97.5, axis=0)
        out[k] = {"kind": kind, "system": base_s[k], "ref": base_r[k], "diff": diff(base_s[k], base_r[k], kind), "lo": lo, "hi": hi}
    return out


def verdict(cmp: dict, leads=SHOW) -> tuple[str, list[str]]:
    """Bättre bara om någon konservering är bättre (intervallet helt under 0), ingen konservering
    eller träff är sämre (helt över 0) och ingen spärr är sämre (helt över 0), på ledtiderna leads."""
    idx = [LEADS.index(k) for k in leads]
    better, worse = [], []
    for k, r in cmp.items():
        if r["kind"] == "info":
            continue
        for i in idx:
            lo, hi = r["lo"][i], r["hi"][i]
            if np.isfinite(hi) and hi < 0 and r["kind"] == "kons":
                better.append(f"{k}@{LEADS[i] * 15}")
            if np.isfinite(lo) and lo > 0:
                worse.append(f"{k}@{LEADS[i] * 15}")
    ok = bool(better) and not worse
    return ("bättre" if ok else "inte bättre"), worse if worse else better


def fmt(x, kind):
    if not np.isfinite(x):
        return "  .  "
    return f"{x:+.2f}" if kind in ("kons", "spärr|") else f"{x:.3f}"


def table(mode: str, systems: list[str], ref: str | None = None, nboot: int = 1000) -> str:
    ref = ref or LÄGEN[mode]["ref"]
    days = mode_days(mode)
    ref_days = load(mode, ref, days)
    if ref_days is None:
        raise SystemExit(f"baslinjen {ref} saknas för {mode}")
    days = [d for d in days if ref_days[d]["issues"] > 0]
    lines = [f"# Domaren, läge {mode}", "",
             f"{len(days)} dygn, baslinje `{ref}`. Kons och form är log kvot mot radarn (0 är rätt), träff och spärrar som poäng; "
             "hopp är medelskillnaden mellan utgåvor för samma tid relativt intensiteten. Under varje system: skillnaden "
             "mot baslinjen med 95 %-intervall (bootstrap över dygnen), orienterad så att negativt är bättre; "
             "`*` intervallet helt på den bättre sidan, `!` helt på den sämre.", ""]
    head = "| mått | slag | " + " | ".join(f"{k * 15} min" for k in SHOW) + " |"
    sep = "|---|---|" + "---|" * len(SHOW)
    idx = [LEADS.index(k) for k in SHOW]
    summary = {}
    for name in systems:
        sd = load(mode, name, days)
        if sd is None:
            lines += [f"## {name}", "", "saknas (inte körd i det här läget)", ""]
            continue
        n = int(sum(sd[d]["issues"] for d in days))
        sec = float(sum(sd[d]["seconds"] for d in days))
        lines += [f"## {name}", "", f"{n} utgåvor, {sec / 60:.0f} processorminuter.", "", head, sep]
        if name == ref:
            sc = scores(sd, days)
            for k, (_, kind) in METRICS.items():
                lines.append(f"| {k} | {kind} | " + " | ".join(fmt(sc[k][i], kind) for i in idx) + " |")
        else:
            cmp = compare(sd, ref_days, days, nboot)
            for k, r in cmp.items():
                cells = []
                for i in idx:
                    mark = "*" if r["hi"][i] < 0 else ("!" if r["lo"][i] > 0 else "")
                    cells.append(f"{fmt(r['system'][i], r['kind'])} ({r['diff'][i]:+.3f} [{r['lo'][i]:+.3f}, {r['hi'][i]:+.3f}]){mark}")
                lines.append(f"| {k} | {r['kind']} | " + " | ".join(cells) + " |")
            v, why = verdict(cmp)
            summary[name] = v
            lines += ["", f"Domen: **{v}**" + (f" ({', '.join(why[:12])}{' ...' if len(why) > 12 else ''})" if why else "")]
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cmd", choices=["kör", "tabell"])
    p.add_argument("--läge", dest="mode", default="snabb", choices=list(LÄGEN))
    p.add_argument("--system", nargs="+", default=["kedja"])
    p.add_argument("--procs", type=int, default=2)
    p.add_argument("--dagar", nargs="*", default=None, help="bara de här dygnen (för att prova)")
    p.add_argument("--ref", default=None)
    p.add_argument("--nboot", type=int, default=1000)
    a = p.parse_args()
    if a.cmd == "kör":
        for s in a.system:
            run(a.mode, s, a.procs, a.dagar)
    else:
        md = table(a.mode, a.system, a.ref, a.nboot)
        RESULTS.mkdir(parents=True, exist_ok=True)
        (RESULTS / f"{a.mode}.md").write_text(md + "\n")
        print(md)


if __name__ == "__main__":
    main()
