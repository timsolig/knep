"""Kedjan och persistensen mot tre facit på träningsdagarna: radarn (A0), A2T och mätarna (uppgift 0005).

    uv run python experiments/projektion/facit_a2t.py analys --dag 2020-07-24 [...]
    uv run python experiments/projektion/facit_a2t.py kedja --dag 2020-07-24 [...]
    uv run python experiments/projektion/facit_a2t.py summera [--B 2000]
    uv run python experiments/projektion/facit_a2t.py kedja --system kedja_utan_platskarta [--prov]
    uv run python experiments/projektion/facit_a2t.py summera --varianter kedja_utan_platskarta kedja_utan_matchning

En diagnos, inget val: ingen domare och inget system ändras.

Uppgift 0006 lade till --system (steget kedja kör ett annat system ur projektionens SYSTEMS och sparar
under UT/<system>/; kedja räknas som förut och jämförs bitvis med den sparade körningen), den första
timmens kvartar under UT/kvartar/<system>/ (för kedja också radarns egna kvartar) och --varianter i
steget summera: varianterna mot persistensen och mot kedjan (variant minus kedja, samma bootstrap) och
kvoten per kvart (+15 till +60 min) mot kvartsmätarna p14 och mot radarns kvartar, till
experiments/projektion/results/facit_a2t_varianter.json.

Dagarna: de träningsdagar (experiments/projektion/traning.json, genom analysens domare.days("traning"),
som kontrollerar att ingen testdag finns med) där analysens domare redan har A1
(/data/analys/domare/A1/<dag>.json), 15 av 28. Validering och test läses inte, inte heller deras mätare.

analys  A0 (SMHI:s komposit med utfyllnad, som analysens domare), A1 och A2T (knep.analys.a2, samma
        konstanter som i drift, med A1 och alla timmätare p7 och kvartsmätare p14 för dagen) per timme.
        A2T räknas dessutom en gång per grupp i korsvalideringen (domarens fem grupper om 100 km,
        mätarna utanför gruppen och mer än 25 km från den), så att A2T kan bedömas mot mätare den inte
        har sett. Sparas i UT/analys/<dag>.npz: A0 och A2T i block om 2 (4 km, verify.block), värdena
        i mätarnas rutor och masken eko90 (rutor med eko i över 90 % av dagens bilder).
kedja   Kedjan som läget traning i projektionens domare (KedjaOm: model.Chain(None), utan MEPS, utan
        extremmodell och volymkorrektion, platskartan uppvärmd 90 min, rörelsecachen under
        /data/projektion/cache/rorelse/2km/) för utgåvorna 03, 06, ..., 18 UTC, timsummorna +1 till +5 h
        (medlet av kvartarna 4(k−1) till 4k−1, kodade som driftens värdefil). Sparas i UT/kedja/<dag>.npz
        (float16, 2 km).
summera Måtten för kedjan och persistensen (A0:s timsumma som slutar vid utgåvan) mot radarn (A0), A2T
        och mätarna (p7 i mätarens ruta, 2 km) per ledtid, utan mask och utan rutorna i F4:s
        klotterkarta (/data/analys/filter/klotter_f4.npz, block om 2 där någon ruta är klotter) eller i
        eko90. Dessutom A0, A1, A2T och A2T i korsvalidering mot mätarna. Skillnaden kedjan minus
        persistensen med 95 %-intervall från bootstrap över dagarna. Till
        experiments/projektion/results/facit_a2t.json.

Utgåvorna 03 till 18 UTC är de var 3:e timme där alla fem målen (timmarna som slutar 04:00 till 23:00)
och persistensen ligger inom dagen, så att varje ledtid har samma utgåvor.

Kartmåtten (4 km, de rutor där A0, A2T, persistensen och kedjan alla finns, samma för båda facit): CSI
vid 1 och 5 mm, FSS vid 1 och 5 mm med fönster 10 och 30 km (3 och 7 block, andelarna bara ur rutorna i
masken som verify.fss_many), summakvoten och MAE.
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import gc
import importlib.util
import json
import shutil
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


AD = _load("analys_domare", ROOT / "experiments/analys/domare.py")   # analysens domare

UT = Path("/data/projektion/facit_a2t")
A1_DOMARE = Path("/data/analys/domare/A1")
A1_SPARAD = Path("/data/analys/a2/a1falt_traning")     # A1 för tre träningsdagar ur uppgift 0003
KLOTTER = Path("/data/analys/filter/klotter_f4.npz")
RESULT = HERE / "results" / "facit_a2t.json"

ISSUES = [3, 6, 9, 12, 15, 18]   # UTC
LEADS = 5
THR = (1.0, 5.0)
FSS_KM = (10.0, 30.0)
KM = 4.03                        # blockets sida (2 x 2,015 km)
MASKS = ("alla", "utan_f4", "utan_eko90")
MIN_FREE_GB = 3.0


def dagar() -> list[str]:
    tr = AD.days("traning")  # kontrollerar att ingen testdag finns med
    return [d for d in tr if (A1_DOMARE / f"{d}.json").exists()]


def _check(day: str) -> None:
    assert day in dagar(), f"{day} är inte en träningsdag med A1"


def _disk() -> None:
    free = shutil.disk_usage("/data").free / 2 ** 30
    if free < MIN_FREE_GB:
        raise SystemExit(f"bara {free:.1f} GB ledigt på /data, avbryter")


def block(x: np.ndarray) -> np.ndarray:
    """Medel av 2 x 2 rutor över de två sista axlarna (verify.block), NaN om någon saknas."""
    h, w = x.shape[-2] // 2, x.shape[-1] // 2
    y = x[..., :2 * h, :2 * w].astype(np.float32)
    return y.reshape(*x.shape[:-2], h, 2, w, 2).mean(axis=(-3, -1))


# ---------------------------------------------------------------- analysen

def cmd_analys(a) -> None:
    from knep.analys import a2 as S
    for day in a.dag:
        _check(day)
        _disk()
        p = UT / "analys" / f"{day}.npz"
        if p.exists():
            print(day, "analys finns", flush=True)
            continue
        t0 = time.time()
        rd = AD.Radardag(day)
        grid = rd.grid
        dag = AD.build_dag(day, rd)
        have = np.isfinite(rd.rain[AD.Radardag.PRE + 1:])
        eko90 = ((rd.rain[AD.Radardag.PRE + 1:] > 0) & have).sum(0) > 0.9 * np.maximum(have.sum(0), 1)
        eko90 &= have.sum(0) >= 0.5 * have.shape[0]
        del have
        sp = A1_SPARAD / f"{day}.npz"
        a0 = AD.A1(rd)   # frames() är A0 (utfyllnaden görs en gång), falt() är A1 ur samma bilder
        _, tm0 = AD.sums(a0.frames()[AD.Radardag.PRE + 1:])
        if sp.exists():
            z = np.load(sp)
            kv1, tm1 = z["kvart"].astype(np.float32), z["timme"].astype(np.float32)
        else:
            kv1, tm1 = a0.falt(None, None)
        t_a1 = time.time() - t0
        del rd, a0
        gc.collect()
        mq, mh = dag.kvart, dag.timme
        model = S.A2T.fran_grid(grid)

        def a2t(mq, mh, hours):
            out = np.full(tm1.shape, np.nan, np.float32)
            for hour in hours:
                win = (mh.t <= hour) & (mh.t > hour - S.TIMME["WIN"])
                fon = S.Matare(mh.r[win], mh.c[win], mh.mm[win], tm1[mh.t[win], mh.r[win], mh.c[win]])
                th = mh.t == hour
                tim = S.Matare(mh.r[th], mh.c[th], mh.mm[th])
                kvm = [S.Matare(mq.r[mq.t == q], mq.c[mq.t == q], mq.mm[mq.t == q]) for q in range(4 * hour, 4 * hour + 4)]
                out[hour], _ = model.timme(tm1[hour], kv1[4 * hour:4 * hour + 4], fon, tim, kvm)
            return out

        t1 = time.time()
        hours = range(24)
        tm2 = a2t(mq, mh, hours)
        t_a2 = time.time() - t1
        # korsvalideringen: A2T utan gruppens mätare, bara för timmarna som bedöms
        need = range(ISSUES[0], ISSUES[-1] + LEADS)
        g = mh
        fold = dag.folds[g.r, g.c]
        cv = np.full(len(g), np.nan, np.float32)
        for k in range(AD.FOLDS):
            q_k, h_k = dag.training(k)
            f = a2t(q_k, h_k, need)
            sel = fold == k
            cv[sel] = f[g.t[sel], g.r[sel], g.c[sel]]
            del f
        t_cv = time.time() - t1 - t_a2
        UT.joinpath("analys").mkdir(parents=True, exist_ok=True)
        # A0 i alla mätarrutor för alla timmar (persistensen vid mätaren)
        cells, cell = np.unique(np.stack([g.r, g.c], 1), axis=0, return_inverse=True)
        np.savez_compressed(
            p, a0=block(tm0), a2=block(tm2), eko90=eko90,
            cell_a0=tm0[:, cells[:, 0], cells[:, 1]], g_cell=cell.ravel(),
            g_station=g.station, g_r=g.r, g_c=g.c, g_t=g.t, g_mm=g.mm, g_fold=fold,
            g_a0=tm0[g.t, g.r, g.c], g_a1=tm1[g.t, g.r, g.c], g_a2=tm2[g.t, g.r, g.c], g_a2cv=cv,
            tid=np.array([t_a1, t_a2, t_cv]))
        print(day, f"A0+A1 {t_a1:.0f} s, A2T {t_a2:.0f} s, korsvalidering {t_cv:.0f} s, mätartimmar {len(g)}", flush=True)
        del kv1, tm1, tm0, tm2, dag
        gc.collect()


# ---------------------------------------------------------------- kedjan

def cmd_kedja(a) -> None:
    """Ett system ur projektionens SYSTEMS (standard kedja, KedjaOm()) till UT/<system>/<dag>.npz med
    timsummorna och UT/kvartar/<system>/<dag>.npz med den första timmens fyra kvartar (mm/h, kodade som
    värdefilen). För kedja sparas dessutom radarns egna kvartar (ctx.quarter, kompositen utan utfyllnad)
    i kvartsfilen. Finns timfilen redan räknas den om och jämförs (ska vara bitvis lika) men skrivs inte
    över. System utan platskarta (warm = False) värms inte upp: tillståndet läses bara av platskartan."""
    PD = _load("projektion_domare", HERE / "domare.py")
    from knep import render
    for day in a.dag:
        _check(day)
        _disk()
        p = UT / a.system / f"{day}.npz"
        pq = UT / "kvartar" / a.system / f"{day}.npz"
        utg = ISSUES
        if a.prov:   # en utgåva, inget skrivs bredvid de riktiga filerna
            utg = [12]
            pq = UT / "prov" / "kvartar" / a.system / f"{day}.npz"
            if not p.exists():
                p = UT / "prov" / a.system / f"{day}.npz"
        if pq.exists():
            print(day, a.system, "finns", flush=True)
            continue
        started = time.monotonic()
        system = PD.KedjaOm() if a.system == "kedja" else PD.make_system(a.system)
        system.reset()
        ctx = PD.Ctx(day, 2)
        d0 = datetime.fromisoformat(day).replace(tzinfo=UTC)
        issues = [d0 + timedelta(hours=h) for h in utg]
        warm = set()
        if getattr(system, "warm", True):
            for t in issues:
                warm |= {t - k * PD.STEP for k in range(1, int(PD.WARMUP / PD.STEP) + 1)}
        out, kv, t_fc = {}, {}, []
        for t in sorted(warm | set(issues)):
            ctx.forget(t - timedelta(hours=2))
            if t not in issues:
                system.observe(t, ctx)
                continue
            if ctx.frame(t) is None:
                continue
            s = time.monotonic()
            fc = system.forecast(t, ctx)
            t_fc.append(time.monotonic() - s)
            if fc is None:
                continue
            fc = np.stack([render.decode_values(render.encode_values(x)) for x in fc])
            hrs = np.stack([fc[4 * (k - 1):4 * k].mean(0) for k in range(1, LEADS + 1)])
            out[f"h{t:%H}"] = hrs.astype(np.float16)
            kv[f"q{t:%H}"] = fc[:4].astype(np.float16)
            if a.system == "kedja":
                shp = fc.shape[1:]
                obs = [ctx.quarter(t + (j + 1) * 3 * PD.STEP) for j in range(4)]
                kv[f"obs{t:%H}"] = np.stack([o if o is not None else np.full(shp, np.nan, np.float32)
                                             for o in obs]).astype(np.float16)
        if p.exists():
            z = np.load(p)
            want = {f"h{h:02d}" for h in utg} & (set(z.files) - {"tid"})
            same = want == set(out) and all(np.array_equal(z[k], out[k], equal_nan=True) for k in out)
            print(day, a.system, "timsummorna lika som de sparade:", same, flush=True)
            if not same:
                raise SystemExit(f"{day}: {a.system} skiljer sig från den sparade körningen")
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(p, tid=np.array(t_fc), **out)
        pq.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(pq, **kv)
        print(day, a.system, f"{len(out)} utgåvor på {time.monotonic() - started:.0f} s "
                   f"(prognosen {np.mean(t_fc) if t_fc else 0:.0f} s per utgåva)", flush=True)


# ---------------------------------------------------------------- måtten

def _boxsum(I: np.ndarray, win: int) -> np.ndarray:
    h = win // 2
    P = np.pad(I, [(0, 0)] * (I.ndim - 2) + [(h + 1, h), (h + 1, h)]).cumsum(-2, dtype=np.int32).cumsum(-1, dtype=np.int32)
    return P[..., win:, win:] - P[..., :-win, win:] - P[..., win:, :-win] + P[..., :-win, :-win]


def fss_parts(F: np.ndarray, O: np.ndarray, m: np.ndarray) -> np.ndarray:
    """(tröskel, fönster, [Σ(Pf − Po)², Σ(Pf² + Po²)]) med andelarna bara ur rutorna i m (som verify.fss_many)."""
    out = np.zeros((len(THR), len(FSS_KM), 2))
    M = m.astype(np.uint8)
    for i, thr in enumerate(THR):
        Io = ((O >= thr) & m).astype(np.uint8)
        If = ((F >= thr) & m).astype(np.uint8)
        for j, km in enumerate(FSS_KM):
            win = max(1, round(km / KM)) | 1
            inv = M.astype(np.float32) / np.maximum(_boxsum(M, win), 1)
            po, pf = _boxsum(Io, win) * inv, _boxsum(If, win) * inv
            out[i, j] = [((pf - po) ** 2).sum(dtype=np.float64), (pf * pf + po * po).sum(dtype=np.float64)]
    return out


def ct(f: np.ndarray, o: np.ndarray) -> np.ndarray:
    """(tröskel, [träff, falskt, miss])."""
    return np.array([[((f >= t) & (o >= t)).sum(), ((f >= t) & (o < t)).sum(), ((f < t) & (o >= t)).sum()] for t in THR],
                    np.float64)


def cont(f: np.ndarray, o: np.ndarray) -> np.ndarray:
    """[n, Σf, Σo, Σ|f − o|]."""
    f, o = f.astype(np.float64), o.astype(np.float64)
    return np.array([f.size, f.sum(), o.sum(), np.abs(f - o).sum()])


def day_sums(day: str, f4b: np.ndarray, varianter: tuple[str, ...] = ()) -> dict:
    """Summorna för en dag: nycklar 'facit/mask/system' -> {'ct': (L, 2, 3), 'cont': (L, 4), 'fss': (L, 2, 2, 2)}
    och 'matare/mask/analys' -> {'ct', 'cont'} för analyserna mot mätarna. Varianterna räknas på samma
    utgåvor och rutor som kedjan (rutorna där kedjan finns) och dessutom där varianten finns."""
    za, zk = np.load(UT / "analys" / f"{day}.npz"), np.load(UT / "kedja" / f"{day}.npz")
    zv = {v: np.load(UT / v / f"{day}.npz") for v in varianter}
    a0, a2 = za["a0"], za["a2"]
    eko90b = block(za["eko90"].astype(np.float32)) > 0
    masks2 = {"alla": None, "utan_f4": f4b, "utan_eko90": eko90b}
    g = {k[2:]: za[k] for k in za.files if k.startswith("g_")}
    res: dict = {}

    def acc(key, lead, **parts):
        d = res.setdefault(key, {"ct": np.zeros((LEADS, len(THR), 3)), "cont": np.zeros((LEADS, 4)),
                                 "fss": np.zeros((LEADS, len(THR), len(FSS_KM), 2))})
        for k, v in parts.items():
            d[k][lead] += v

    n_iss = 0
    for hh in ISSUES:
        key = f"h{hh:02d}"
        if key not in zk.files:
            continue
        if any(key not in z.files for z in zv.values()):
            raise SystemExit(f"{day} {key}: någon variant saknar utgåvan som kedjan har")
        fc = zk[key].astype(np.float32)      # (5, H, W) 2 km
        fv = {v: z[key].astype(np.float32) for v, z in zv.items()}
        P = a0[hh - 1]                       # A0:s timme som slutar vid utgåvan (4 km)
        n_iss += 1
        fcb = block(fc)
        fvb = {v: block(x) for v, x in fv.items()}
        for k in range(1, LEADS + 1):
            idx = hh + k - 1                  # timmen som slutar hh + k
            F = fcb[k - 1]
            base = np.isfinite(a0[idx]) & np.isfinite(a2[idx]) & np.isfinite(P) & np.isfinite(F)
            for v, x in fvb.items():
                bad = int((base & ~np.isfinite(x[k - 1])).sum())
                if bad:
                    raise SystemExit(f"{day} {key} +{k} h: {v} saknas i {bad} block där kedjan finns")
            for mname, mm in masks2.items():
                m = base if mm is None else base & ~mm
                if m.sum() < 50:
                    continue
                for fname, O in (("radar", a0[idx]), ("a2t", a2[idx])):
                    for sname, X in (("kedja", F), ("persistens", P), *((v, x[k - 1]) for v, x in fvb.items())):
                        acc(f"{fname}/{mname}/{sname}", k - 1, ct=ct(X[m], O[m]), cont=cont(X[m], O[m]),
                            fss=fss_parts(np.nan_to_num(X), np.nan_to_num(O), m))
            # mätarna i sina rutor (2 km); persistensen ur A0 i mätarens ruta för timmen hh
            sel = g["t"] == idx
            r, c, mm_g = g["r"][sel], g["c"][sel], g["mm"][sel]
            fk = fc[k - 1][r, c]
            pk = za["cell_a0"][hh - 1, g["cell"][sel]]
            ok = np.isfinite(fk) & np.isfinite(pk) & np.isfinite(g["a0"][sel]) & np.isfinite(g["a2"][sel])
            gv = {v: x[k - 1][r, c] for v, x in fv.items()}
            for v, x in gv.items():
                if (ok & ~np.isfinite(x)).any():
                    raise SystemExit(f"{day} {key} +{k} h: {v} saknas vid mätare där kedjan finns")
            for mname, mm in masks2.items():
                mk = ok if mm is None else ok & ~mm[np.minimum(r // 2, mm.shape[0] - 1), np.minimum(c // 2, mm.shape[1] - 1)]
                for sname, X in (("kedja", fk), ("persistens", pk), *gv.items()):
                    acc(f"matare/{mname}/{sname}", k - 1, ct=ct(X[mk], mm_g[mk]), cont=cont(X[mk], mm_g[mk]))
                for an in ("a0", "a1", "a2", "a2cv"):
                    v = g[an][sel]
                    acc(f"matare/{mname}/analys_{an}", k - 1, ct=ct(v[mk], mm_g[mk]), cont=cont(v[mk], mm_g[mk]))
    res["_utgavor"] = n_iss
    return res


def scores(d: dict) -> dict:
    out = {}
    a, b, c = d["ct"][..., 0], d["ct"][..., 1], d["ct"][..., 2]
    out["csi"] = a / np.maximum(a + b + c, 1)
    n, sf, so, ae = d["cont"].T
    out["kvot"] = sf / np.maximum(so, 1e-9)
    out["mae"] = ae / np.maximum(n, 1)
    if "fss" in d:
        out["fss"] = 1 - d["fss"][..., 0] / np.maximum(d["fss"][..., 1], 1e-12)
    return out


def _iv(v, samp) -> dict:
    return {"v": np.round(v, 4).tolist(), "lo": np.round(np.percentile(samp, 2.5, 0), 4).tolist(),
            "hi": np.round(np.percentile(samp, 97.5, 0), 4).tolist()}


def _grid(day: str):
    from knep.analys import radar
    d0 = datetime.fromisoformat(day).replace(tzinfo=UTC)
    for k in range(288):
        p = AD.frame_path(d0 + k * radar.STEP)
        if p.exists():
            return radar.read_rain(p)[1]
    raise SystemExit(f"{day}: ingen radarbild")


def quarter_sums(day: str, systems: list[str]) -> dict:
    """Den första timmens kvartar (+15 till +60 min) per utgåva: 'kalla/system' -> cont (4, 4).
    p14/s: systemet mot kvartsmätarna p14 i mätarens ruta (mm per kvart; radar = radarns egen kvart).
    falt/s: systemet mot radarns kvart (ctx.quarter) över hela fältet där båda finns.
    matarrutor/s: systemet mot radarns kvart i rutorna med en p14-mätare (samma mätarkvartar som p14)."""
    zq = {s: np.load(UT / "kvartar" / s / f"{day}.npz") for s in systems}
    mq = AD.load_gauges(day, "kvart", _grid(day))
    res: dict = {}

    def acc(key, j, x, o):
        res.setdefault(key, {"cont": np.zeros((4, 4))})["cont"][j] += cont(x, o)

    for hh in ISSUES:
        if any(f"q{hh:02d}" not in z.files for z in zq.values()):
            continue
        obs = zq["kedja"][f"obs{hh:02d}"].astype(np.float32)
        fq = {s: z[f"q{hh:02d}"].astype(np.float32) for s, z in zq.items()}
        for j in range(4):
            o = obs[j]
            mf = np.isfinite(o)
            for x in fq.values():
                mf &= np.isfinite(x[j])
            sel = mq.t == 4 * hh + j
            r, c, g = mq.r[sel], mq.c[sel], mq.mm[sel]
            ok = mf[r, c]
            r, c, g = r[ok], c[ok], g[ok]
            acc("p14/radar", j, o[r, c] / 4, g)
            for s, x in fq.items():
                acc(f"p14/{s}", j, x[j][r, c] / 4, g)
                acc(f"matarrutor/{s}", j, x[j][r, c], o[r, c])
                acc(f"falt/{s}", j, x[j][mf], o[mf])
    return res


def quarter_tables(days: list[str], systems: list[str], boots: np.ndarray) -> dict:
    per = [quarter_sums(d, systems) for d in days]
    out = {}
    for key in per[0]:
        st = np.stack([p[key]["cont"] for p in per])           # (dagar, 4, 4)

        def kv(c):
            return c[..., 1] / np.maximum(c[..., 2], 1e-9)

        def mae(c):
            return c[..., 3] / np.maximum(c[..., 0], 1)

        tot = st.sum(0)
        bs = np.stack([st[i].sum(0) for i in boots])
        out[key] = {"kvot": _iv(kv(tot), kv(bs)), "mae": _iv(mae(tot), mae(bs)), "n": tot[:, 0].astype(int).tolist(),
                    "kvot_per_dag": {d: np.round(kv(p[key]["cont"]), 3).tolist() for d, p in zip(days, per)}}
        src, s = key.split("/")
        if s not in ("kedja", "radar"):
            ref = np.stack([p[f"{src}/kedja"]["cont"] for p in per])
            bref = np.stack([ref[i].sum(0) for i in boots])
            out[f"{src}/{s}_minus_kedja"] = {"kvot": _iv(kv(tot) - kv(ref.sum(0)), kv(bs) - kv(bref))}
    return out


def _sum(per_day: list[dict], key: str) -> dict:
    keys = per_day[0][key].keys()
    return {k: sum(pd[key][k] for pd in per_day) for k in keys}


def cmd_summera(a) -> None:
    f4 = np.load(KLOTTER)["klotter"]
    f4b = block(f4.astype(np.float32)) > 0
    days = [d for d in dagar() if (UT / "analys" / f"{d}.npz").exists() and (UT / "kedja" / f"{d}.npz").exists()]
    if a.varianter:
        days = [d for d in days if all((UT / v / f"{d}.npz").exists() for v in a.varianter)]
    per = {}
    for d in days:
        per[d] = day_sums(d, f4b, tuple(a.varianter))
        print(d, "utgåvor", per[d]["_utgavor"], flush=True)
    rng = np.random.default_rng(0)
    nd = len(days)
    boots = rng.integers(0, nd, size=(a.B, nd))
    plist = [per[d] for d in days]
    res = {"dagar": days, "utgavor": {d: per[d]["_utgavor"] for d in days}, "trosklar_mm": THR, "fss_km": FSS_KM,
           "utgavotider_utc": ISSUES, "masker": MASKS, "f4_block": int(f4b.sum()), "B": a.B, "tabeller": {}}
    groups = sorted({k.rsplit("/", 1)[0] for k in plist[0] if not k.startswith("_")})
    for gname in groups:
        systems = sorted({k.rsplit("/", 1)[1] for k in plist[0] if k.startswith(gname + "/")})
        tab = {}
        est = {s: scores(_sum(plist, f"{gname}/{s}")) for s in systems}
        # bootstrap: summorna per dag i en matris per system och mått
        stacks = {s: {k: np.stack([pd[f"{gname}/{s}"][k] for pd in plist]) for k in plist[0][f"{gname}/{s}"]} for s in systems}
        bs = {s: [] for s in systems}
        for idx in boots:
            for s in systems:
                bs[s].append(scores({k: v[idx].sum(0) for k, v in stacks[s].items()}))
        for s in systems:
            tab[s] = {}
            for m, v in est[s].items():
                samp = np.stack([b[m] for b in bs[s]])
                tab[s][m] = {"v": np.round(v, 4).tolist(), "lo": np.round(np.percentile(samp, 2.5, 0), 4).tolist(),
                             "hi": np.round(np.percentile(samp, 97.5, 0), 4).tolist()}
            tab[s]["n"] = stacks[s]["cont"].sum(0)[:, 0].astype(int).tolist()
        pairs = [(s, "persistens") for s in ["kedja", *a.varianter]] + [(v, "kedja") for v in a.varianter]
        for s1, s2 in pairs:
            if s1 not in systems or s2 not in systems:
                continue
            diff = {}
            for m in est[s1]:
                if m == "kvot":   # skillnaden i |ln kvot|: negativ betyder att s1:s mängd ligger närmare facit
                    f = lambda x: np.abs(np.log(np.maximum(x, 1e-9)))  # noqa: E731
                else:
                    f = lambda x: x  # noqa: E731
                v = f(est[s1][m]) - f(est[s2][m])
                samp = np.stack([f(b1[m]) - f(b2[m]) for b1, b2 in zip(bs[s1], bs[s2])])
                diff["abs_ln_kvot" if m == "kvot" else m] = _iv(v, samp)
                if m == "kvot" and s2 == "kedja":   # och själva kvoten, variant minus kedjan
                    diff["kvot"] = _iv(est[s1][m] - est[s2][m], np.stack([b1[m] - b2[m] for b1, b2 in zip(bs[s1], bs[s2])]))
            tab[f"{s1}_minus_{s2}"] = diff
        res["tabeller"][gname] = tab
    if a.varianter:
        res["kvartar"] = quarter_tables(days, ["kedja", *a.varianter], boots)
    # per dag (utan mask): CSI 1 mm och FSS 1 mm/30 km för kedjan och persistensen per ledtid och facit
    res["per_dag"] = {}
    for d, pd in zip(days, plist):
        res["per_dag"][d] = {}
        for fname in ("radar", "a2t", "matare"):
            e = {}
            for s in ("kedja", "persistens", *a.varianter):
                sc = scores(pd[f"{fname}/alla/{s}"])
                e[f"csi1_{s}"] = np.round(sc["csi"][:, 0], 3).tolist()
                if "fss" in sc:
                    e[f"fss1_30_{s}"] = np.round(sc["fss"][:, 0, 1], 3).tolist()
                e[f"kvot_{s}"] = np.round(sc["kvot"], 3).tolist()
            res["per_dag"][d][fname] = e
    RESULT.parent.mkdir(exist_ok=True)
    namn = a.namn or ("varianter" if a.varianter else "")
    out = RESULT if not namn else RESULT.with_name(f"facit_a2t_{namn}.json")
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print("skrev", out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["analys", "kedja", "summera", "dagar"])
    ap.add_argument("--dag", nargs="+", default=None)
    ap.add_argument("--B", type=int, default=2000)
    ap.add_argument("--namn", default="")
    ap.add_argument("--system", default="kedja", help="steget kedja: systemet ur projektionens SYSTEMS")
    ap.add_argument("--prov", action="store_true", help="steget kedja: bara utgåvan 12 UTC, till UT/prov/")
    ap.add_argument("--varianter", nargs="*", default=[],
                    help="steget summera: system utöver kedja som jämförs med kedjan och persistensen")
    a = ap.parse_args()
    if a.cmd == "dagar":
        print(" ".join(dagar()))
        return
    if a.dag is None:
        a.dag = dagar()
    {"analys": cmd_analys, "kedja": cmd_kedja, "summera": cmd_summera}[a.cmd](a)


if __name__ == "__main__":
    main()
