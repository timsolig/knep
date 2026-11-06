"""Inlärd blandning per pixel i hålet (HistGradientBoosting).

    uv run python experiments/bortfall/inlard.py extrahera --processer 2      särdrag ur träningsfallen
    uv run python experiments/bortfall/inlard.py trana                        två modeller
    uv run python experiments/bortfall/bortfallsdomare.py kor inlard:Inlard --processer 2

Systemet `Inlard`
-----------------
För varje bild i bortfallet räknas den flyttade analysen (meps_hal.Flytt, fill_gaps utan
90-minutersgräns) och MEPS rättad mot radarn (meps_hal.Rattning, som i meps_hal.Meps). Per pixel i
hålet ger två modeller

- sannolikheten för regn (R >= 0,1 mm/h), klassificerare, och
- log(1 + R), regression med kvadratfel,

ur särdragen i `SARDRAG`. Hur många pixlar som regnar sätts av summan av sannolikheterna. De
pixlarna väljs efter regressionens värde, och deras värden fördelningsmatchas mot radarn utanför
hålet: de våta pixlarnas fördelning i en ring (RING_KM) utanför hålet i samma bild, med regressionens
egen fördelning som reserv när ringen är torr. Sist mjukas kanten upp: i de yttersta KANT_PX
pixlarna i hålet blandas fältet med ett gaussiskt utjämnat fält av analysen och radarn utanför.

Höjden saknas: ingen öppen höjdmodell fanns lokalt i natt (rapport 5).
Modellerna sparas i /data/bortfall/modeller/, aldrig i repot.
"""

from __future__ import annotations

import argparse
import json
import os

# domaren kör två processer; varje process får en tråd (Pi:n delas med driften)
os.environ.setdefault("OMP_NUM_THREADS", "1")
import pickle
import sys
import time
from datetime import timedelta
from pathlib import Path

import numpy as np
from scipy.ndimage import distance_transform_edt, gaussian_filter

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "src"))

import bortfallsdomare as domare  # noqa: E402
from meps_hal import Flytt, Rattning  # noqa: E402

MODELLER = Path("/data/bortfall/modeller")
UTDRAG = Path("/data/bortfall/inlard")
PX_KM = 2.0
RING_KM = 60.0
KANT_PX = 3
VAT = 0.1   # mm/h

SARDRAG = ["flytt", "flytt_s5", "flytt_s15", "meps", "meps_s5", "alder", "kant_km", "radar_km",
           "tim_sin", "tim_cos", "dag_sin", "dag_cos", "ring_medel", "ring_vat", "hal_flytt_medel",
           "sista_radar", "medel_uppv"]


def _l(x):
    return np.log1p(np.maximum(x, 0))


def _s(x, sigma):
    """Gaussiskt utjämnat log-fält med NaN som saknade (normaliserad faltning)."""
    ok = np.isfinite(x)
    v = gaussian_filter(np.where(ok, _l(x), 0).astype(np.float32), sigma)
    w = gaussian_filter(ok.astype(np.float32), sigma)
    return np.where(w > 0.05, v / np.maximum(w, 1e-6), np.nan)


class Statiskt:
    """Det som inte ändras under fallet."""

    def __init__(self, ind: domare.Indata):
        hal = ind.hal
        self.kant_km = distance_transform_edt(hal) * PX_KM
        utanfor = distance_transform_edt(~hal) * PX_KM
        self.ring = (~hal) & (utanfor <= RING_KM)
        self.kant = hal & (self.kant_km <= KANT_PX * PX_KM)
        f = ind.forfluten
        self.sista = np.nan_to_num(f[-1])
        with np.errstate(all="ignore"):
            self.medel = np.nan_to_num(np.nanmean(f, axis=0))


def sardrag(st: Statiskt, ind: domare.Indata, flytt: np.ndarray, meps: np.ndarray | None, alder: float):
    """Särdragsmatris för hålets pixlar (n, len(SARDRAG))."""
    hal = ind.hal
    n = int(hal.sum())
    t = ind.tid
    tim = 2 * np.pi * (t.hour + t.minute / 60) / 24
    dag = 2 * np.pi * t.timetuple().tm_yday / 365.25
    fl = np.where(hal, flytt, np.nan)
    b = ind.bild
    ring = b[st.ring]
    ring = ring[np.isfinite(ring)]
    rm = float(_l(ring).mean()) if ring.size else np.nan
    rv = float((ring >= VAT).mean()) if ring.size else np.nan
    hm = np.nanmean(_l(fl[hal])) if np.isfinite(fl[hal]).any() else np.nan
    # utjämningen tar med radarn utanför hålet, så att kanten ser grannskapet
    c = np.where(hal, fl, b)
    if meps is not None:
        m, ms = _l(meps)[hal], _s(meps, 5)[hal]
    else:
        m = ms = np.full(n, np.nan)
    kol = [_l(fl[hal]), _s(c, 5)[hal], _s(c, 15)[hal], m, ms, np.full(n, alder), st.kant_km[hal],
           ind.avstand[hal], np.full(n, np.sin(tim)), np.full(n, np.cos(tim)), np.full(n, np.sin(dag)),
           np.full(n, np.cos(dag)), np.full(n, rm), np.full(n, rv), np.full(n, hm), _l(st.sista[hal]),
           _l(st.medel[hal])]
    return np.stack(kol, axis=1).astype(np.float32)


class Basen:
    """Flyttad analys och rättad MEPS, bild för bild (som meps_hal.Blandning)."""

    def start(self, ind: domare.Indata) -> None:
        self.flytt = Flytt()
        self.flytt.start(ind)
        self.med_meps = bool(ind.meta.get("meps_tid"))
        if self.med_meps:
            self.r = Rattning(ind.hal)
            for b in ind.forfluten:
                self.r.lagg_till(b)
        self.forsta = True
        self.st = Statiskt(ind)

    def bas(self, k: int, ind: domare.Indata):
        a = self.flytt.steg(k, ind)
        m = None
        if self.med_meps:
            if self.forsta:
                self.r.assimilera(ind.meps, ind.meta, ind.tid - timedelta(minutes=5), under_bortfall=False)
                self.forsta = False
            self.r.lagg_till(ind.bild)
            self.r.assimilera(ind.meps, ind.meta, ind.tid, under_bortfall=True)
            m = self.r.falt(ind.meps, ind.tid) if ind.meps else None
        return a, m


# --- systemet ---------------------------------------------------------------------------------

def las_modell(path: Path = MODELLER / "inlard.pkl") -> dict:
    with open(path, "rb") as f:
        return pickle.load(f)


def matcha(p: np.ndarray, mu: np.ndarray, ring: np.ndarray) -> np.ndarray:
    """Antal våta = sum p; de med högst mu får radarns fördelning i ringen (reserv: expm1(mu))."""
    n = p.size
    nv = int(round(float(p.sum())))
    out = np.zeros(n, np.float32)
    if nv <= 0:
        return out
    order = np.argsort(-mu, kind="stable")[:nv]
    egen = np.sort(np.expm1(mu[order]))[::-1]
    rv = ring[np.isfinite(ring) & (ring >= VAT)]
    if rv.size >= 20:
        q = np.quantile(rv, 1 - (np.arange(nv) + 0.5) / nv)
    else:
        q = egen
    out[order] = np.maximum(q, VAT)
    return out


class Inlard(Basen):
    namn = "inlard"
    modell: dict | None = None

    def start(self, ind: domare.Indata) -> None:
        super().start(ind)
        if Inlard.modell is None:
            Inlard.modell = las_modell()

    def steg(self, k: int, ind: domare.Indata) -> np.ndarray:
        a, m = self.bas(k, ind)
        hal = ind.hal
        X = sardrag(self.st, ind, a, m, 5.0 * (k + 1))
        mod = Inlard.modell
        p = mod["klass"].predict_proba(X)[:, 1]
        mu = mod["regr"].predict(X)
        ut = ind.bild.copy()
        ut[hal] = matcha(p, mu, ind.bild[self.st.ring])
        # mjuk kant: de yttersta pixlarna i hålet mot ett utjämnat fält av analys och radar utanför
        c = np.nan_to_num(ut)
        g = gaussian_filter(c, 2.0)
        w = np.clip(1 - self.st.kant_km / (KANT_PX * PX_KM + PX_KM), 0, 1)
        ut = np.where(self.st.kant, (1 - w) * c + w * g, ut)
        return ut.astype(np.float32)


# --- träningen --------------------------------------------------------------------------------

def urval(index: list[dict]) -> list[dict]:
    """Det längsta fallet per träningsdag (sedan namnet), med eller utan MEPS."""
    dagar: dict[str, list[dict]] = {}
    for c in index:
        dagar.setdefault(c["dag"], []).append(c)
    return [sorted(v, key=lambda c: (-c["langd_min"], c["namn"]))[0] for _, v in sorted(dagar.items())]


def extrahera_fall(path: Path, per_bild: int = 1500, var: int = 2) -> Path:
    t0 = time.monotonic()
    fall = domare.Fall(path)
    ind = fall.indata()
    bas = Basen()
    bas.start(ind)
    import hashlib

    rng = np.random.default_rng(int(hashlib.sha256(fall.meta["namn"].encode()).hexdigest()[:8], 16))
    Xs, ys = [], []
    for k in range(fall.n):
        t = fall.tider[fall.k0 + k]
        ind.bild, ind.tid = fall.maskad(k), t
        ind.meps, ind.matare = fall.meps_till(t), {}
        a, m = bas.bas(k, ind)
        if k % var:
            continue
        o = fall.radar[fall.k0 + k][fall.hal]
        X = sardrag(bas.st, ind, a, m, 5.0 * (k + 1))
        ok = np.flatnonzero(np.isfinite(o))
        if ok.size > per_bild:
            ok = rng.choice(ok, per_bild, replace=False)
        Xs.append(X[ok])
        ys.append(o[ok])
    UTDRAG.mkdir(parents=True, exist_ok=True)
    ut = UTDRAG / f"{fall.meta['namn']}.npz"
    np.savez_compressed(ut, X=np.concatenate(Xs), y=np.concatenate(ys), dag=fall.dag)
    print("extraherat", fall.meta["namn"], round(time.monotonic() - t0), "s", flush=True)
    return ut


def extrahera(a) -> None:
    index = json.loads((domare.FALL / "traning" / "index.json").read_text())["fall"]
    valda = urval(index)
    if a.fall:
        valda = valda[: a.fall]
    paths = [domare.FALL / "traning" / c["fil"] for c in valda
             if not (UTDRAG / f"{c['namn']}.npz").exists()]
    print("fall att extrahera:", len(paths), flush=True)
    if a.processer > 1:
        from multiprocessing import Pool

        with Pool(a.processer) as pool:
            list(pool.imap_unordered(extrahera_fall, paths))
    else:
        for p in paths:
            extrahera_fall(p)


def trana(a) -> None:
    from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor

    filer = sorted(UTDRAG.glob("*.npz"))
    X = np.concatenate([np.load(f)["X"] for f in filer])
    y = np.concatenate([np.load(f)["y"] for f in filer])
    print("fall", len(filer), "pixlar", len(y), "andel våta", round(float((y >= VAT).mean()), 3), flush=True)
    kw = dict(max_iter=300, learning_rate=0.08, max_leaf_nodes=31, min_samples_leaf=200,
              early_stopping=True, validation_fraction=0.1, random_state=0)
    from threadpoolctl import threadpool_limits

    t0 = time.monotonic()
    with threadpool_limits(2):
        klass = HistGradientBoostingClassifier(**kw).fit(X, y >= VAT)
        regr = HistGradientBoostingRegressor(**kw).fit(X, np.log1p(y))
    print("tränat på", round(time.monotonic() - t0), "s; iterationer", klass.n_iter_, regr.n_iter_, flush=True)
    MODELLER.mkdir(parents=True, exist_ok=True)
    with open(MODELLER / "inlard.pkl", "wb") as f:
        pickle.dump({"klass": klass, "regr": regr, "sardrag": SARDRAG,
                     "fall": [f.stem for f in filer]}, f)
    (MODELLER / "inlard.json").write_text(json.dumps({"fall": [f.stem for f in filer], "pixlar": int(len(y)),
                                                       "iter": [int(klass.n_iter_), int(regr.n_iter_)]}) + "\n")


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extrahera")
    e.add_argument("--processer", type=int, default=1)
    e.add_argument("--fall", type=int, default=0)
    sub.add_parser("trana")
    a = p.parse_args()
    {"extrahera": extrahera, "trana": trana}[a.cmd](a)


if __name__ == "__main__":
    main()
