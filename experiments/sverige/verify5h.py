"""Verifiering 0 till 5 h på de svenska dagarna: CSI, FSS och volym per ledtid mot radarn.

    python experiments/sverige/verify5h.py --part validering [--system kedja meps ...]

Varje hel timme på dagarna är en utfärdandetid T. Prognoserna jämförs som kvartsmedel för
kvartarna som slutar T + 15 min till T + 5 h, och som timsummor för timme 1 till 5. Radarns
kvartsmedel är medlet av bilderna vid slutet av kvarten och 5 och 10 min före (samma
konvention som render.aggregate). Ytan är där radarn har data och kedjans prognos finns, för
alla system, så att de jämförs på samma pixlar.

System (se SYSTEMS): kedjan förlängd till 5 h, MEPS som den fanns (2,5 h fördröjning),
persistens, och blandningarna i sommodell.py.

Resultat: /data/sverige/resultat/<del>.json och en tabell på stdout.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).parent))
from data import DATA, load_days, meps_path, radar_path  # noqa: E402
from knep import nwp, radar, render  # noqa: E402

Q = timedelta(minutes=15)
NQ = 20                                   # kvartar till 5 h
THR = [0.5, 1.0, 5.0]                     # mm/h
FSS_THR = [1.0, 5.0]
SCALES_KM = [10, 30, 90]
RES_KM = 2.0
OUT = DATA / "sverige" / "resultat"


class Obs:
    """Radarns bilder och kvartsmedel, med en enkel cache."""

    def __init__(self):
        self.frames, self.quarters, self.grid = {}, {}, None

    def frame(self, t: datetime):
        if t not in self.frames:
            p = radar_path(t)
            f = None
            if p.exists():
                try:
                    f, self.grid = radar.read_rain(p)
                except Exception:  # noqa: BLE001
                    f = None
            self.frames[t] = f
        return self.frames[t]

    def quarter(self, end: datetime):
        if end not in self.quarters:
            fs = [self.frame(end - k * radar.STEP) for k in range(3)]
            self.quarters[end] = None if any(f is None for f in fs) else np.mean(fs, axis=0).astype(np.float32)
        return self.quarters[end]

    def forget(self, before: datetime) -> None:
        for d in (self.frames, self.quarters):
            for t in [t for t in d if t < before]:
                del d[t]


class Meps:
    def __init__(self):
        self.cache = {}

    def on(self, run: datetime, grid):
        if run not in self.cache:
            p = meps_path(run)
            if not p.exists():
                self.cache[run] = None
            else:
                r = nwp.Run.load(p)
                self.cache[run] = (r, r.on(grid))
            if len(self.cache) > 6:
                self.cache.pop(next(iter(self.cache)))
        return self.cache[run]


CHAIN_DIR = DATA / "sverige" / "kedja"


def chain_forecast(day: str, t: datetime, root: Path = CHAIN_DIR):
    p = root / day / f"{t:%H%M}.npz"
    if not p.exists():
        return None
    d = np.load(p)
    return render.decode_values(d["codes"]), d["motion"].astype(np.float32)


def meps_quarters(meps: Meps, t: datetime, grid, interpolate: bool = False, lag: int = 0):
    """MEPS som kvartsmedel från körningen som fanns vid t (lag: så många körningar tidigare).

    Utan interpolate gäller timsumman hela timmen; med interpolate tas intensiteten mitt i
    kvarten, interpolerad mellan timmarnas mitt (seamless.meps_at)."""
    from knep import seamless

    got = meps.on(nwp.available(t) - lag * timedelta(hours=3), grid)
    if got is None:
        return None
    run, on = got
    out = np.full((NQ,) + tuple(grid.shape), np.nan, np.float32)
    for k in range(NQ):
        end = t + (k + 1) * Q
        if interpolate:
            out[k] = seamless.meps_at(on, run.run, end - timedelta(minutes=5))
        else:
            h = run.hour_ending(end)
            if h is not None:
                out[k] = on[h]
    return out


# ---------- mått ----------

class Scores:
    def __init__(self, systems: list[str]):
        self.systems = systems
        n = len(systems)
        self.ct = np.zeros((n, NQ, len(THR), 3))                         # träffar, missar, falsklarm
        self.fss = np.zeros((n, NQ, len(FSS_THR), len(SCALES_KM), 2))    # summa (pf - po)², summa pf² + po²
        self.vol = np.zeros((n, NQ, 2))
        self.hct = np.zeros((n, 5, len(THR), 3))                          # timsummor
        self.hfss = np.zeros((n, 5, len(FSS_THR), len(SCALES_KM), 2))
        self.n = np.zeros((n, NQ))

    @staticmethod
    def _box(x, size):
        return cv2.boxFilter(x, cv2.CV_32F, (size, size), normalize=False, borderType=cv2.BORDER_CONSTANT)

    def fractions(self, x, m):
        """Andelarna över tröskeln per skala, (FSS_THR, SCALES_KM, pixlar i m); räknas en gång per fält."""
        mf = m.astype(np.float32)
        out = []
        for thr in FSS_THR:
            b = ((x >= thr) & m).astype(np.float32)
            row = []
            for km in SCALES_KM:
                size = int(round(km / RES_KM)) | 1
                den = self._box(mf, size)
                row.append((self._box(b, size) / np.maximum(den, 1e-6))[m])
            out.append(row)
        return out

    def _add(self, ct, fss, i, k, f, o, m, fo):
        for j, thr in enumerate(THR):
            F, O = (f >= thr) & m, (o >= thr) & m
            ct[i, k, j] += [(F & O).sum(), (~F & O).sum(), (F & ~O).sum()]
        ff = self.fractions(f, m)
        for j in range(len(FSS_THR)):
            for s in range(len(SCALES_KM)):
                pf, po = ff[j][s], fo[j][s]
                fss[i, k, j, s] += [((pf - po) ** 2).sum(), (pf ** 2 + po ** 2).sum()]

    def add(self, i: int, k: int, f, o, m, fo) -> None:
        self._add(self.ct, self.fss, i, k, f, o, m, fo)
        self.vol[i, k] += [f[m].sum(), o[m].sum()]
        self.n[i, k] += 1

    def add_hour(self, i: int, h: int, f, o, m, fo) -> None:
        self._add(self.hct, self.hfss, i, h, f, o, m, fo)

    def table(self) -> dict:
        def csi(ct):
            return ct[..., 0] / np.maximum(ct.sum(-1), 1)

        def fss(x):
            return 1 - x[..., 0] / np.maximum(x[..., 1], 1e-9)
        res = {}
        for i, name in enumerate(self.systems):
            res[name] = {
                "n": self.n[i].tolist(),
                "csi": {str(t): csi(self.ct[i, :, j]).round(4).tolist() for j, t in enumerate(THR)},
                "fss": {f"{t}_{km}": fss(self.fss[i, :, j, s]).round(4).tolist()
                        for j, t in enumerate(FSS_THR) for s, km in enumerate(SCALES_KM)},
                "volym": (self.vol[i, :, 0] / np.maximum(self.vol[i, :, 1], 1e-9)).round(3).tolist(),
                "tim_csi": {str(t): csi(self.hct[i, :, j]).round(4).tolist() for j, t in enumerate(THR)},
                "tim_fss": {f"{t}_{km}": fss(self.hfss[i, :, j, s]).round(4).tolist()
                            for j, t in enumerate(FSS_THR) for s, km in enumerate(SCALES_KM)},
            }
        return res


# ---------- system ----------

def systems_for(names):
    import sommodell
    base = {
        "kedja": lambda c: c["chain"],
        "meps": lambda c: c["meps"],
        "persistens": lambda c: np.repeat(c["analysis"][None], NQ, axis=0),
        "meps_int": lambda c: c["meps_i"],
        "meps_lagg": lambda c: c["meps_i"] if c["meps_prev"] is None else 0.5 * (c["meps_i"] + c["meps_prev"]),
    }
    return {n: base.get(n) or sommodell.SYSTEMS.get(n) or sommodell.variant(n) for n in names}


def run(part: str, names: list[str], limit: int | None = None, chain_dir: Path = CHAIN_DIR, every: int = 1) -> dict:
    systems = systems_for(names)
    sc = Scores(names)
    obs, meps = Obs(), Meps()
    started, issues = time.monotonic(), 0
    for d in load_days(part):
        day = datetime.fromisoformat(d["day"]).replace(tzinfo=UTC)
        state = {}  # för system som minns mellan utfärdandetiderna (assimilering)
        for h in range(0, 24, every):
            t = day + timedelta(hours=h)
            obs.forget(t - timedelta(hours=2))
            fc = chain_forecast(d["day"], t, chain_dir)
            if fc is None:
                continue
            analysis = obs.frame(t)
            if analysis is None or obs.grid is None:
                continue
            chain, motion = fc
            mq = meps_quarters(meps, t, obs.grid)
            if mq is None:
                continue
            ctx = {"t": t, "chain": chain, "motion": motion, "meps": mq, "analysis": analysis, "grid": obs.grid,
                   "meps_i": meps_quarters(meps, t, obs.grid, interpolate=True),
                   "meps_prev": meps_quarters(meps, t, obs.grid, interpolate=True, lag=1),
                   "obs": obs, "state": state, "meps_run": meps.on(nwp.available(t), obs.grid)}
            fcs = {n: fn(ctx) for n, fn in systems.items()}
            mask_base = np.isfinite(chain[0])
            hour_f = {n: np.zeros(analysis.shape, np.float32) for n in names}
            hour_o = np.zeros(analysis.shape, np.float32)
            hour_m = mask_base.copy()
            for k in range(NQ):
                o = obs.quarter(t + (k + 1) * Q)
                if o is None:
                    hour_m[:] = False
                    continue
                m = mask_base & np.isfinite(o)  # samma pixlar för alla system
                for n in names:
                    m &= np.isfinite(fcs[n][k])
                on = np.nan_to_num(o)
                fo = sc.fractions(on, m)
                for i, n in enumerate(names):
                    f = np.nan_to_num(fcs[n][k])
                    sc.add(i, k, f, on, m, fo)
                    hour_f[n] += f / 4
                hour_o += np.nan_to_num(o) / 4
                hour_m &= np.isfinite(o)
                if k % 4 == 3:
                    fo = sc.fractions(hour_o, hour_m)
                    for i, n in enumerate(names):
                        sc.add_hour(i, k // 4, hour_f[n], hour_o, hour_m, fo)
                        hour_f[n][:] = 0
                    hour_o[:] = 0
                    hour_m = mask_base.copy()
            issues += 1
            if limit and issues >= limit:
                break
        print(f"{d['day']}: {issues} utfärdandetider, {time.monotonic() - started:.0f} s", flush=True)
        if limit and issues >= limit:
            break
    return sc.table()


def show(res: dict) -> None:
    leads = [1, 2, 4, 8, 12, 16, 20]  # kvartar
    for metric, key in (("CSI 1 mm/h", ("csi", "1.0")), ("CSI 5 mm/h", ("csi", "5.0")), ("FSS 1 mm/h 30 km", ("fss", "1.0_30")),
                        ("FSS 5 mm/h 30 km", ("fss", "5.0_30")), ("Volym", ("volym", None))):
        print(f"\n{metric:18s}" + "".join(f"{k * 15:>7d}" for k in leads))
        for n, r in res.items():
            v = r[key[0]] if key[1] is None else r[key[0]][key[1]]
            print(f"{n:18s}" + "".join(f"{v[k - 1]:7.3f}" for k in leads))
    print("\nTimsummor, FSS 1 mm/h 30 km, timme 1 till 5")
    for n, r in res.items():
        print(f"{n:18s}" + "".join(f"{x:7.3f}" for x in r["tim_fss"]["1.0_30"]))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--part", default="validering")
    p.add_argument("--system", nargs="+", default=["kedja", "meps", "persistens"])
    p.add_argument("--limit", type=int, default=None, help="högst så många utfärdandetider (för att prova)")
    p.add_argument("--every", type=int, default=1, help="var n:e timme som utfärdandetid")
    p.add_argument("--tag", default=None, help="namn på resultatfilen")
    p.add_argument("--kedja", type=Path, default=CHAIN_DIR, help="katalogen med kedjans prognoser")
    a = p.parse_args()
    res = run(a.part, a.system, a.limit, a.kedja, a.every)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{a.tag or a.part}.json").write_text(json.dumps(res))
    show(res)


if __name__ == "__main__":
    main()
