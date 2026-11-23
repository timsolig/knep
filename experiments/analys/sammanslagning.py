"""Fyra sätt att foga in regnmätarna i analysen i stället för (eller utöver) A2T:s optimala interpolation (kön, spåret sammanslagning).

A2T (a2.py) rättar först i stor skala och gör sedan optimal interpolation (OI) i kvadratrotsskala med en
fast exponentiell korrelation (L = 40 km) och ett bakgrundsfel som bara beror på avståndet till radarn. OI
förutsätter normalfördelade fel med samma struktur överallt, vilket nederbörden inte har (nollorna, skevheten,
fel som växer med intensiteten, korrelation som beror på vädret, lägesfel). Här prövas fyra andra vägar,
var och en i flera varianter, med A2T:s storskaliga kvot, torrmask och tak där inget annat sägs:

  L1, L2      lärd: gradient boosting som förutsäger sqrt(mätaren) ur radarn i rutan och omgivningen,
              avståndet till radarn, höjden och årstiden (L1 bara modellen, L2 modellen som bakgrund och
              A2T:s OI på resten). Tränad på träningsdagarna i två delar efter dag, så att en dag bedöms
              med modellen som inte har sett den; valideringen med modellen tränad på alla träningsdagar.
  CM20, CM40, CM80, CMm40
              conditional merging: mätarnas fält och radarns värden vid mätarna interpoleras på samma sätt,
              och skillnaden läggs på radarn (sqrt-skala; L km), så att radarns form behålls; CMm40 som kvot.
  K1, K2, K3  korrelation som beror på vädret: L skattat ur radarfältets egen autokorrelation för perioden
              (K1), bakgrundsfelet som växer med intensiteten (K2), båda (K3).
  T50, T35, T50L40
              två steg: först om det regnar (indikatorn ur radarn rättad mot mätarnas våt eller torr), sedan
              hur mycket (A2T där det regnar, mätarnas interpolerade mängd där radarn är torr men det regnar,
              0 annars); tröskeln för sannolikheten 0,5 eller 0,35, korrelationslängden 20 eller 40 km.

    uv run python experiments/analys/sammanslagning.py a1falt              A1:s fält för träningsdagarna
    uv run python experiments/analys/sammanslagning.py trana_lard          modellerna för L1 och L2
    uv run python experiments/analys/sammanslagning.py kor CM40 --del traning
    uv run python experiments/analys/domare.py tabell CM40 --mot A2T --del traning

Allt bedöms med analysens domare (korsvalidering i block mot mätarna) mot A2T. Testdelen läses aldrig.
"""

from __future__ import annotations

import argparse
import gc
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np
from scipy.ndimage import maximum_filter, uniform_filter
from scipy.spatial.distance import cdist

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import a2  # noqa: E402

D = a2.D
UT = Path("/data/analys/sammanslagning")
A1TR = a2.OUT / "a1falt_traning"


# ---------------------------------------------------------------- gemensamt

def interp(xy_t, xy_g, v, L, nugget=0.1):
    """Enkel kriging (OI med konstant varians) av v i punkterna xy_g till xy_t: medel plus OI av avvikelserna."""
    if len(v) == 0:
        return np.zeros(len(xy_t))
    mu = float(np.mean(v))
    r = cdist(xy_g, xy_g)
    B = np.exp(-r / L)
    B[np.diag_indices_from(B)] += nugget
    w = np.linalg.solve(B, v - mu)
    return mu + np.exp(-cdist(xy_t, xy_g) / L) @ w


def autokorr_l(F0: np.ndarray, step: int = 4, lo: float = 10.0, hi: float = 120.0) -> float:
    """Längden (km) där radarfältets autokorrelation (sqrt-skala, glest rutnät) faller till 1/e."""
    f = np.sqrt(F0[::step, ::step])
    if f.std() < 1e-6:
        return 40.0
    f = f - f.mean()
    F = np.fft.rfft2(f, s=(2 * f.shape[0], 2 * f.shape[1]))
    ac = np.fft.irfft2(F * np.conj(F))[: f.shape[0], : f.shape[1]]
    ac /= ac[0, 0]
    prof = np.minimum(ac[0, :], ac[:, 0][: ac.shape[1]] if ac.shape[0] >= ac.shape[1] else ac[0, :])
    under = np.nonzero(prof < np.exp(-1))[0]
    lag = under[0] if len(under) else len(prof)
    return float(np.clip(lag * step * D.RES_KM, lo, hi))


class _Bas(a2.A2):
    """A2 med _period utbytt; dag sätts av kör (för modellernas delar och höjden)."""

    dag_s: str | None = None
    elev: np.ndarray | None = None

    def falt(self, dag, matare, hours=range(24)):
        self.elev = getattr(dag, "elev", None)
        return super().falt(dag, matare, hours)

    def _gauges(self, F1, m, sel):
        g = m.subset(sel)
        xy = np.c_[g.c, g.r].astype(float) * D.RES_KM
        a = F1[g.r, g.c].astype(float)
        ok = np.isfinite(a) & np.isfinite(g.mm)
        return g, xy[ok], g.mm[ok], a[ok], ok

    def _skydd(self, out, F1, F0, m, sel, p):
        """A2T:s tak över svagt eko och torrmask, som i a2.A2._period."""
        out = a2.svag_tak(out, F0, p)
        g = m.subset(sel)
        if len(g):
            from scipy.spatial import cKDTree  # noqa: PLC0415

            xy = np.c_[g.c, g.r].astype(float) * D.RES_KM
            d_any = cKDTree(xy).query(self.cxy, distance_upper_bound=p["R_TORR"] + 1)[0]
            wet = g.mm > 0
            d_wet = cKDTree(xy[wet]).query(self.cxy, distance_upper_bound=p["R_TORR"] + 1)[0] if wet.any() \
                else np.full(len(self.cxy), np.inf)
            dry_c = ((d_any <= p["R_TORR"]) & (d_wet > p["R_TORR"])).reshape(self.cshape)
            h, w = self.shape
            dry = np.repeat(np.repeat(dry_c, a2.STEP, 0), a2.STEP, 1)[:h, :w] & (F0 < p["TORR"])
            out[dry] = 0.0
        return np.where(np.isfinite(F1), out, np.nan).astype(np.float32)


# ---------------------------------------------------------------- 1. lärd

def sardrag(F0: np.ndarray, rng_km: np.ndarray, elev: np.ndarray | None, manad: int) -> np.ndarray:
    """(H, W, n) särdragen per ruta: sqrt(A1) i rutan och medel i 5, 11, 25 rutor, max i 9, andel våt i 11,
    avståndet till radarn, höjden och årstiden."""
    s = np.sqrt(np.maximum(F0, 0.0)).astype(np.float32)
    lag = [s, uniform_filter(s, 5), uniform_filter(s, 11), uniform_filter(s, 25), maximum_filter(s, 9),
           uniform_filter((F0 > 0.1).astype(np.float32), 11), rng_km.astype(np.float32),
           (elev if elev is not None else np.zeros_like(s)).astype(np.float32),
           np.full_like(s, np.cos(2 * np.pi * manad / 12)), np.full_like(s, np.sin(2 * np.pi * manad / 12))]
    return np.stack(lag, axis=-1)


def del_av(dag_s: str) -> int:
    tr = sorted(D.days("traning"))
    return tr.index(dag_s) % 2 if dag_s in tr else -1


class _Lard(_Bas):
    oi = False
    _modeller: dict = {}

    def _modell(self, res):
        d = del_av(self.dag_s)
        namn = f"lard_{res}_{'alla' if d < 0 else f'utan{d}'}.pkl"
        if namn not in self._modeller:
            self._modeller[namn] = pickle.loads((UT / namn).read_bytes())
        return self._modeller[namn]

    def _period(self, F1, m, sel, ratio_c, ratio_g, p):
        res = "timme" if p is self.params["timme"] else "kvart"
        F0 = np.nan_to_num(F1, nan=0.0)
        # förutsägelsen beror inte på mätarna, så den räknas en gång per period (inte per grupp i domarens
        # korsvalidering), och på var STEP:e ruta som OI:s tillskott, sedan bilinjärt upp
        nyckel = (res, F0.shape, float(F0.sum()), float((F0 > 0).sum()))
        cache = self.__dict__.setdefault("_pred", {})
        if nyckel not in cache:
            X = sardrag(F0, self.rng_full, self.elev, int(self.dag_s[5:7]))[::a2.STEP, ::a2.STEP]
            grov = self._modell(res).predict(X.reshape(-1, X.shape[-1])).reshape(X.shape[:2])
            cache.clear() if len(cache) > 200 else None
            cache[nyckel] = np.maximum(a2._up(grov.astype(np.float32), self.shape), 0.0)
            # rutor utan eko får bara regn om modellen är säker (inget duggregn ur tomma rutor)
            cache[nyckel][(F0 <= 0) & (cache[nyckel] < 0.3)] = 0.0
        pred = cache[nyckel]
        out = pred ** 2
        if self.oi:
            g, xy, mm, a, ok = self._gauges(F1, m, sel)
            if len(mm):
                d = np.sqrt(mm) - pred[g.r[ok], g.c[ok]]
                sbg = a2.sigma_b(self.rng_full[g.r[ok], g.c[ok]].astype(float), p)
                v = a2.oi_vikter(xy, sbg, d, p)
                inc = a2.oi_tillskott(self.cxy, a2.sigma_b(self.crng, p), xy, sbg, v, p).reshape(self.cshape)
                out = np.maximum(np.sqrt(out) + a2._up(inc, self.shape), 0.0) ** 2
        return self._skydd(out, F1, F0, m, sel, p)


class L1(_Lard):
    namn = "L1"


class L2(_Lard):
    namn = "L2"
    oi = True


def cmd_trana_lard(a):
    """Gradient boosting per upplösning, på träningsdagarnas mätare (A1 i rutan och omgivningen); en modell
    utan varje dags del (för träningsdagarna) och en på alla (för valideringen)."""
    from sklearn.ensemble import HistGradientBoostingRegressor

    UT.mkdir(parents=True, exist_ok=True)
    data = {"kvart": [], "timme": []}
    for f in sorted(A1TR.glob("*.npz")):
        day_s = f.stem
        rd = D.Radardag(day_s)
        dag = D.build_dag(day_s, rd)
        rng = a2.radar_range_km(rd.grid)
        del rd
        gc.collect()
        z = np.load(f)
        for res, m, F in (("kvart", dag.kvart, z["kvart"]), ("timme", dag.timme, z["timme"])):
            for t in np.unique(m.t):
                sel = m.t == t
                F0 = np.nan_to_num(F[t].astype(np.float32))
                X = sardrag(F0, rng, getattr(dag, "elev", None), int(day_s[5:7]))
                r, c, mm = m.r[sel], m.c[sel], m.mm[sel]
                ok = np.isfinite(mm) & (mm >= 0) & np.isfinite(F[t][r, c])
                data[res].append((del_av(day_s), X[r[ok], c[ok]], np.sqrt(mm[ok])))
        print(day_s, "särdrag", flush=True)
        del dag, z
        gc.collect()
    for res, rows in data.items():
        dl = np.concatenate([np.full(len(y), d) for d, _, y in rows])
        X = np.concatenate([x for _, x, _ in rows])
        y = np.concatenate([y for _, _, y in rows])
        for namn, mask in (("alla", np.ones(len(y), bool)), ("utan0", dl != 0), ("utan1", dl != 1)):
            mod = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, max_leaf_nodes=31,
                                                l2_regularization=1.0, random_state=0).fit(X[mask], y[mask])
            (UT / f"lard_{res}_{namn}.pkl").write_bytes(pickle.dumps(mod))
        print(res, len(y), "punkter", flush=True)


# ---------------------------------------------------------------- 2. conditional merging

class _CM(_Bas):
    L = 40.0
    kvot = False

    def _period(self, F1, m, sel, ratio_c, ratio_g, p):
        F0 = np.nan_to_num(F1, nan=0.0)
        rf = a2.svag_kvot(a2._up(ratio_c, self.shape, 4 * a2.STEP), F0, p)
        bg = np.maximum(rf * F0, 0.0)
        g, xy, mm, a, ok = self._gauges(F1, m, sel)
        if len(mm) < 3:
            return self._skydd(bg, F1, F0, m, sel, p)
        rg = a2.svag_kvot(ratio_g, F1[g.r, g.c].astype(float), p)
        ab = a * (rg[ok] if np.ndim(rg) and len(rg) == len(ok) else 1.0)
        if self.kvot:
            G = interp(self.cxy, xy, mm, self.L).reshape(self.cshape)
            R = interp(self.cxy, xy, ab, self.L).reshape(self.cshape)
            k = np.clip((a2._up(np.maximum(G, 0), self.shape) + 0.2) / (a2._up(np.maximum(R, 0), self.shape) + 0.2), 0.25, 4)
            out = bg * k
        else:
            G = interp(self.cxy, xy, np.sqrt(mm), self.L).reshape(self.cshape)
            R = interp(self.cxy, xy, np.sqrt(np.maximum(ab, 0)), self.L).reshape(self.cshape)
            out = np.maximum(np.sqrt(bg) + a2._up(G - R, self.shape), 0.0) ** 2
        return self._skydd(out, F1, F0, m, sel, p)


class CM20(_CM):
    namn, L = "CM20", 20.0


class CM40(_CM):
    namn, L = "CM40", 40.0


class CM80(_CM):
    namn, L = "CM80", 80.0


class CMm40(_CM):
    namn, L, kvot = "CMm40", 40.0, True


# ---------------------------------------------------------------- 3. korrelation som beror på vädret

class _K(_Bas):
    l_ur_faltet = False
    beta = 0.0   # bakgrundsfelet gånger (1 + beta · sqrt(A1))

    def _period(self, F1, m, sel, ratio_c, ratio_g, p):
        F0 = np.nan_to_num(F1, nan=0.0)
        q = dict(p)
        if self.l_ur_faltet:
            q["L"] = autokorr_l(F0)
        rf = a2.svag_kvot(a2._up(ratio_c, self.shape, 4 * a2.STEP), F0, q)
        out = np.maximum(rf * F0, 0.0)
        g, xy, mm, a, ok = self._gauges(F1, m, sel)
        if len(mm):
            rg = a2.svag_kvot(ratio_g, F1[g.r, g.c].astype(float), q)[ok] if len(ratio_g) == len(ok) else 1.0
            bg = np.sqrt(np.maximum(rg * a, 0.0))
            d = np.sqrt(mm) - bg
            sbg = a2.sigma_b(self.rng_full[g.r[ok], g.c[ok]].astype(float), q) * (1 + self.beta * bg)
            v = a2.oi_vikter(xy, sbg, d, q)
            sc = np.sqrt(out[::a2.STEP, ::a2.STEP]).ravel()[: len(self.crng)]
            sbt = a2.sigma_b(self.crng, q) * (1 + self.beta * sc)
            inc = a2.oi_tillskott(self.cxy, sbt.astype(np.float32), xy, sbg, v, q).reshape(self.cshape)
            out = np.maximum(np.sqrt(out) + a2._up(inc, self.shape), 0.0) ** 2
        return self._skydd(out, F1, F0, m, sel, q)


class K1(_K):
    namn, l_ur_faltet = "K1", True


class K2(_K):
    namn, beta = "K2", 0.5


class K3(_K):
    namn, l_ur_faltet, beta = "K3", True, 0.5


# ---------------------------------------------------------------- 4. två steg

class _T(_Bas):
    troskel = 0.5
    L = 20.0

    def _period(self, F1, m, sel, ratio_c, ratio_g, p):
        F0 = np.nan_to_num(F1, nan=0.0)
        a2t = a2.A2._period(self, F1, m, sel, ratio_c, ratio_g, p)
        g, xy, mm, a, ok = self._gauges(F1, m, sel)
        if len(mm) < 3:
            return a2t
        res_tr = 0.1 if p is self.params["kvart"] else 0.2   # mm per period för "våt"
        ir_g = (a > res_tr).astype(float)
        ig = (mm > res_tr).astype(float)
        inc = interp(self.cxy, xy, ig - ir_g, self.L, nugget=0.3).reshape(self.cshape)
        ir = (F0 > res_tr).astype(np.float32)
        P = np.clip(ir + a2._up(inc - np.mean(ig - ir_g), self.shape), 0, 1)
        vat = P >= self.troskel
        mangd = np.zeros_like(F0)
        if (mm > res_tr).sum() >= 2:
            w = mm > res_tr
            mangd = np.maximum(a2._up(interp(self.cxy, xy[w], np.sqrt(mm[w]), 40.0).reshape(self.cshape), self.shape), 0.0) ** 2
        out = np.where(vat, np.where(np.nan_to_num(a2t) > 0, a2t, mangd), 0.0)
        return np.where(np.isfinite(F1), out, np.nan).astype(np.float32)


class T50(_T):
    namn = "T50"


class T35(_T):
    namn, troskel = "T35", 0.35


class T50L40(_T):
    namn, L = "T50L40", 40.0


SYSTEM = {c.namn: c for c in (L1, L2, CM20, CM40, CM80, CMm40, K1, K2, K3, T50, T35, T50L40)}


# ---------------------------------------------------------------- körningen

def cmd_a1falt(a):
    for day_s in D.days("traning"):
        p = A1TR / f"{day_s}.npz"
        if p.exists():
            continue
        t = time.time()
        rd = D.Radardag(day_s)
        kv, tm = D.A1(rd).falt(None, None)
        p.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(p, kvart=kv.astype(np.float16), timme=tm.astype(np.float16))
        print(day_s, "A1", f"{time.time() - t:.0f} s", flush=True)
        del rd, kv, tm
        gc.collect()


def cmd_kor(a):
    cls = SYSTEM[a.system]
    params = a2.system_params("A2T")
    dagar = [a.dag] if a.dag else D.days(a.del_)
    for day_s in dagar:
        target = D.OUT / cls.namn / f"{day_s}.json"
        if target.exists():
            continue
        t = time.time()
        if a.del_ == "validering":
            if not a2.a1_path(day_s).exists():
                continue
            dag, grid, kv1, tm1 = a2._load_val(day_s)
        else:
            f = A1TR / f"{day_s}.npz"
            if not f.exists():
                continue
            rd = D.Radardag(day_s)
            dag = D.build_dag(day_s, rd)
            grid = rd.grid
            del rd
            gc.collect()
            z = np.load(f)
            kv1, tm1 = z["kvart"].astype(np.float32), z["timme"].astype(np.float32)
        s = cls(kv1, tm1, a2.radar_range_km(grid), params)
        s.dag_s = day_s
        res = D.evaluate(s, dag)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(res))
        print(day_s, cls.namn, f"{time.time() - t:.0f} s", flush=True)
        del dag, s, kv1, tm1
        gc.collect()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cmd", choices=["a1falt", "trana_lard", "kor"])
    p.add_argument("system", nargs="?")
    p.add_argument("--del", dest="del_", default="traning", choices=["traning", "validering"])
    p.add_argument("--dag")
    a = p.parse_args()
    {"a1falt": cmd_a1falt, "trana_lard": cmd_trana_lard, "kor": cmd_kor}[a.cmd](a)


if __name__ == "__main__":
    main()
