"""Underskottet i A1 på lovartsidan: var och varför (uppgift 6 natten 2026-11-07).

    uv run python experiments/analys/lovart.py diag --dag 2023-08-08

Diagnosen läser A0 (domarens Radardag och A0) och A1:s sparade fält (/data/analys/a2/a1falt,
valideringen) och skriver ut, för mätartimmarna på lovartsidan: summorna för A0, A1 och mätarna,
uppdelat efter rörelsens fart, stationerna som bidrar mest till underskottet, massan i lovartmasken
och i ett band nedströms, och hur stilla A0 står vid mätarna (korrelationen mellan bilderna med och
utan flytt längs rörelsen).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import a2 as A2mod  # noqa: E402  (laddar domaren som analys_domare)

D = A2mod.D
OUT = Path("/data/analys/lovart")


def cmd_diag(a):
    t = time.time()
    rd = D.Radardag(a.dag)
    dag = D.build_dag(a.dag, rd)
    a0 = D.A0(rd)
    kv0, tm0 = a0.falt(dag, None)
    z = np.load(D.OUT.parent / "a2" / "a1falt" / f"{a.dag}.npz")
    kv1, tm1 = z["kvart"].astype(np.float32), z["timme"].astype(np.float32)
    print("lästa", f"{time.time() - t:.0f} s", flush=True)
    m = dag.timme
    g = m.mm
    x0, x1 = tm0[m.t, m.r, m.c], tm1[m.t, m.r, m.c]
    ok = np.isfinite(x0) & np.isfinite(x1)
    lov = dag.lovart[m.t, m.r, m.c] & ok
    hm = rd.hourly_motion()
    spd = np.hypot(hm[m.t, 0, m.r, m.c], hm[m.t, 1, m.r, m.c])
    res = {"dag": a.dag}
    print(f"alla: A0 {x0[ok].sum():.0f} A1 {x1[ok].sum():.0f} mätare {g[ok].sum():.0f}")
    print(f"lovart ({lov.sum()} mätartimmar): A0 {x0[lov].sum():.1f} A1 {x1[lov].sum():.1f} mätare {g[lov].sum():.1f}")
    res["lovart"] = [float(x0[lov].sum()), float(x1[lov].sum()), float(g[lov].sum())]
    # efter fart (pixlar per 5 min, 1 px = 2 km)
    for lo, hi in ((0, 1), (1, 2), (2, 4), (4, 8), (8, 99)):
        s = lov & (spd >= lo) & (spd < hi)
        if s.any():
            print(f"  fart {lo}-{hi} px/5 min: n {s.sum():4d} A0 {x0[s].sum():7.1f} A1 {x1[s].sum():7.1f} "
                  f"mätare {g[s].sum():7.1f}  A1/A0 {x1[s].sum() / max(x0[s].sum(), 1e-6):.3f}")
    # efter A0:s intensitet vid mätaren
    for lo, hi in ((0, 1), (1, 3), (3, 6), (6, 99)):
        s = lov & (x0 >= lo) & (x0 < hi)
        if s.any():
            print(f"  A0 {lo}-{hi} mm: n {s.sum():4d} A0 {x0[s].sum():7.1f} A1 {x1[s].sum():7.1f} "
                  f"A1/A0 {x1[s].sum() / max(x0[s].sum(), 1e-6):.3f}")
    # stationerna som bidrar mest
    st = np.unique(m.station[lov])
    rows = []
    for s_ in st:
        s = lov & (m.station == s_)
        i = np.flatnonzero(s)[0]
        rows.append((float(x1[s].sum() - x0[s].sum()), int(s_), int(m.r[i]), int(m.c[i]), float(dag.elev[m.r[i], m.c[i]]),
                     float(x0[s].sum()), float(x1[s].sum()), float(g[s].sum()), float(spd[s].mean())))
    rows.sort()
    print("stationer med störst underskott (A1 − A0, station, rad, kol, höjd, A0, A1, mätare, fart):")
    for r_ in rows[:10]:
        print("  " + " ".join(f"{v:.1f}" if isinstance(v, float) else str(v) for v in r_))
    print("stationer med störst överskott:")
    for r_ in rows[-5:]:
        print("  " + " ".join(f"{v:.1f}" if isinstance(v, float) else str(v) for v in r_))
    res["stationer"] = rows
    # massan: i lovartmasken, uppströms och nedströms (Gaussutjämnad mask flyttad ±6 px längs rörelsen)
    L = dag.lovart
    fin = np.isfinite(tm0) & np.isfinite(tm1)
    sL0 = float(np.where(L & fin, tm0, 0).sum())
    sL1 = float(np.where(L & fin, tm1, 0).sum())
    print(f"massan i lovartmasken (alla rutor): A0 {sL0:.0f} A1 {sL1:.0f} A1/A0 {sL1 / sL0:.4f}")
    sA0 = float(np.where(fin, tm0, 0).sum())
    sA1 = float(np.where(fin, tm1, 0).sum())
    print(f"massan i hela rutnätet: A0 {sA0:.0f} A1 {sA1:.0f} A1/A0 {sA1 / sA0:.4f}")
    # utjämnat fält: om underskottet är en flytt syns det kvar efter utjämning, om det är en utsmetning inte
    for sig in (2.0, 5.0):
        d0 = np.stack([gaussian_filter(np.nan_to_num(tm0[h]), sig) for h in range(24)])
        d1 = np.stack([gaussian_filter(np.nan_to_num(tm1[h]), sig) for h in range(24)])
        y0, y1 = d0[m.t, m.r, m.c], d1[m.t, m.r, m.c]
        print(f"lovart efter Gauss {sig:g} px: A0 {y0[lov].sum():.1f} A1 {y1[lov].sum():.1f} A1/A0 {y1[lov].sum() / y0[lov].sum():.3f}")
    # hur stilla står A0 vid lovartmätarna: korrelation av bilderna t och t + 15 min i fönster om
    # 21 rutor kring mätaren, på plats (Euler) och med t flyttad längs rörelsen (Lagrange)
    from knep.prognos import advect
    fr = a0.frames()
    eu, la, n = [], [], 0
    for i in np.flatnonzero(lov):
        k = D.Radardag.PRE + 12 * int(m.t[i]) + 6
        r, c = int(m.r[i]), int(m.c[i])
        if r < 10 or c < 10 or r > fr.shape[1] - 11 or c > fr.shape[2] - 11:
            continue
        f0, f1 = np.nan_to_num(fr[k]), np.nan_to_num(fr[k + 3])
        if f0[r - 10:r + 11, c - 10:c + 11].max() < 0.5:
            continue
        mot = rd.motion_at(k)
        adv = advect.extrapolate(f0, mot, [3.0], outval=0.0)[0]
        w1 = f1[r - 10:r + 11, c - 10:c + 11].ravel()
        e = np.corrcoef(f0[r - 10:r + 11, c - 10:c + 11].ravel(), w1)[0, 1]
        l_ = np.corrcoef(adv[r - 10:r + 11, c - 10:c + 11].ravel(), w1)[0, 1]
        if np.isfinite(e) and np.isfinite(l_):
            eu.append(e)
            la.append(l_)
        n += 1
        if n >= 200:
            break
    eu, la = np.array(eu), np.array(la)
    print(f"stillheten vid lovartmätarna ({len(eu)} fall): korrelation på plats {eu.mean():.3f}, "
          f"längs rörelsen {la.mean():.3f}, andel där på plats är bättre {(eu > la).mean():.2f}")
    res["euler_lagr"] = [float(eu.mean()), float(la.mean()), float((eu > la).mean())]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"diag_{a.dag}.json").write_text(json.dumps(res))
    print("klart", f"{time.time() - t:.0f} s")


# ---------------------------------------------------------------- varianterna av A1 genom domaren

# namn -> (sätt, parameter). "min": hela den gemensamma delen min(f0, f1) står still; "lyft": andelen
# 1 − exp(−k · lyft) av den står still (knep.analys.a1.stay_fraction); None: A1 som i drift.
VARIANTS = {"A1": None, "A1M": ("min", 1.0), "A1L1": ("lyft", 1.0), "A1L03": ("lyft", 0.3)}


class Strom:
    """Kvart och timme ur intervallen ett i taget, exakt som domare.sums (via float16 som domare.A1)."""

    def __init__(self, shape):
        self.kv = np.full((96, *shape), np.nan, np.float16)
        self.ks, self.kn = np.zeros(shape, np.float32), np.zeros(shape, np.int16)
        self.hs = np.zeros((24, *shape), np.float32)
        self.hn = np.zeros((24, *shape), np.int16)

    def add(self, i: int, iv: np.ndarray):
        x = iv.astype(np.float16).astype(np.float32)
        fin = np.isfinite(x)
        x0 = np.where(fin, x, 0.0)
        self.ks += x0
        self.kn += fin
        self.hs[i // 12] += x0
        self.hn[i // 12] += fin
        if i % 3 == 2:
            q = i // 3
            mean = self.ks / np.maximum(self.kn, 1)
            self.kv[q] = np.where(self.kn * 3 >= 6, mean, np.nan) * (15 / 60.0)
            self.ks[:] = 0
            self.kn[:] = 0

    def result(self):
        mean = self.hs / np.maximum(self.hn, 1)
        return self.kv.astype(np.float32), np.where(self.hn * 3 >= 24, mean, np.nan).astype(np.float32)


def cmd_kor(a):
    from knep.analys import a1
    names = a.system or list(VARIANTS)
    todo = [a.dag] if a.dag else D.days(a.del_)
    i0, n = (int(x) for x in a.bit.split("/"))
    elev = np.load(D.HOJD)["h"].astype(np.float32)
    for day_s in todo[i0::n]:
        assert day_s in D.days("validering") + D.days("traning")
        base = OUT / "prov" if a.spara else D.OUT
        targets = {s: base / s / f"{day_s}.json" for s in names}
        targets = {s: p for s, p in targets.items() if not p.exists()}
        if not targets:
            continue
        t = time.time()
        rd = D.Radardag(day_s)
        dag = D.build_dag(day_s, rd)
        a0 = D.A0(rd)
        fr = a0.frames()
        if "A0" in targets:
            p = targets.pop("A0")
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(D.evaluate(a0, dag)))
        strom = {s: Strom(fr.shape[1:]) for s in targets}
        k0 = D.Radardag.PRE + 1
        cache = (None, None, {})
        for i in range(288):
            k = k0 + i
            j = min(max(0, (k - D.Radardag.PRE) // 3), 96)
            if cache[0] != j:
                mot = rd.motion_at(k).astype(np.float64)
                cache = (j, a1.paths(mot), {})
                for s in targets:
                    v = VARIANTS[s]
                    if v is not None and v[0] == "lyft":
                        cache[2][s] = a1.stay_fraction(mot, elev, v[1])
            for s in targets:
                v = VARIANTS[s]
                stay = None if v is None else (v[1] if v[0] == "min" else cache[2][s])
                strom[s].add(i, a1.interpolate(fr[k - 1], fr[k], cache[1], stay))
            if i == 11:
                print(day_s, "första timmen", f"{time.time() - t:.0f} s", flush=True)
        for s, p in targets.items():
            kv, tm = strom[s].result()
            if a.spara:
                np.savez_compressed(OUT / f"falt_{s}_{day_s}.npz", kvart=kv.astype(np.float16), timme=tm.astype(np.float16))
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(D.evaluate_fields(dag, kv, tm)))
        print(day_s, " ".join(targets), f"{time.time() - t:.0f} s", flush=True)
        del rd, dag, a0, fr, strom, cache
        import gc
        gc.collect()


def cmd_jamfor(a):
    """A1 ur strömmen mot domarens sparade A1 (a2/a1falt) för en valideringsdag: ska vara lika."""
    z = np.load(D.OUT.parent / "a2" / "a1falt" / f"{a.dag}.npz")
    y = np.load(OUT / f"falt_A1_{a.dag}.npz")
    for res in ("kvart", "timme"):
        u, v = z[res].astype(np.float32), y[res].astype(np.float32)
        both = np.isfinite(u) & np.isfinite(v)
        print(res, "NaN lika", bool((np.isfinite(u) == np.isfinite(v)).all()), "största skillnad", float(np.abs(u - v)[both].max()))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cmd", choices=["diag", "kor", "jamfor"])
    p.add_argument("system", nargs="*")
    p.add_argument("--dag")
    p.add_argument("--del", dest="del_", default="traning", choices=["validering", "traning"])
    p.add_argument("--bit", default="0/1")
    p.add_argument("--spara", action="store_true", help="provkörning: spara fälten och skriv summorna under OUT/prov")
    a = p.parse_args()
    {"diag": cmd_diag, "kor": cmd_kor, "jamfor": cmd_jamfor}[a.cmd](a)


if __name__ == "__main__":
    main()
