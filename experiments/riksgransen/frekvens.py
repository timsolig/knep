"""Hur ofta SMHI är 0 där OPERA har regn, mot de svenska radarernas strålhöjd och avståndet, på
träningsdagarna med nederbörd i norr (OPERA var 15:e minut ur /data/riksgransen/opera15/).
Testdelen läses aldrig.

    uv run python experiments/riksgransen/frekvens.py [--del traning]   skriver /data/riksgransen/frekvens_<del>.json

Urvalsregeln för zonen, bestämd innan siffrorna sågs (uppgift 0010):

  Kandidaterna är H = 2, 3 och 4 km (zonen: svensk lägsta stråle över H). Den valda H är den
  minsta kandidat där, i zonen på träningsdagarna,
    (a) SMHI är 0 i minst hälften av de rutor och bilder där OPERA har minst 0,1 mm/h, och
    (b) vid mätarna i zonen, i de timmar där regeln ändrar något (SMHI 0 i timmen, OPERA minst
        0,1 mm/h i medel), har mätaren regn (över 0 mm) i minst hälften av timmarna. Med färre än
        20 sådana mätartimmar går (b) inte att bedöma och bara (a) gäller.
  Regeln "torr" (OPERA bara där SMHI är 0) väljs framför "max" (det största av SMHI och OPERA)
  om inte "max" ger lägre MAE mot mätarna i zonens timmar där SMHI har regn och OPERA mer.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import zon  # noqa: E402
from knep.analys import radar  # noqa: E402

_spec = importlib.util.spec_from_file_location("analys_domare", HERE.parent / "analys" / "domare.py")
domare = importlib.util.module_from_spec(_spec)
sys.modules["analys_domare"] = domare
_spec.loader.exec_module(domare)

BEAM_BINS = np.arange(0.0, 6.5, 0.5)
DIST_BINS = np.arange(0, 260, 20)
SITE_BINS = (0, 10, 20, 30, 40, 60, 80)
CANDIDATES = (2.0, 3.0, 4.0)
WET = 0.1


def _counts():
    return {k: 0 for k in ("cov", "ow", "gap", "sw", "rev")}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--del", dest="del_", default="traning", choices=["traning", "validering"])
    a = p.parse_args()
    days = [d for d in domare.days(a.del_) if (zon.OUT / "opera15" / f"{d}.npz").exists()]
    grid = None
    res = {"dagar": days, "beam": {}, "dist": {}, "kand": {}, "plats": {}, "matare": {}}
    for d in days:
        z = np.load(zon.OUT / "opera15" / f"{d}.npz")
        times = [datetime.fromisoformat(s) for s in z["times"]]
        day = datetime.fromisoformat(d).replace(tzinfo=UTC)
        sel = [i for i, t in enumerate(times) if day < t <= day + timedelta(days=1)]
        smhi, opera = [], []
        for i in sel:
            p_ = domare.frame_path(times[i])
            if not p_.exists() or str(times[i].isoformat()) in set(z["saknas"].tolist()):
                smhi.append(None)
                opera.append(None)
                continue
            r, g = radar.read_rain(p_)
            if grid is None:
                grid = zon.grid_of(g)
                beam, dist = zon.beam_se(grid), zon.dist_se(grid)
                bb = np.digitize(np.nan_to_num(beam, nan=99), BEAM_BINS) - 1
                db = np.digitize(dist, DIST_BINS) - 1
                site_d = {n: zon.dist_to(grid, *ll) for n, ll in zon.NO_SITES.items()}
                zones = {h: np.isfinite(beam) & (beam > h) for h in CANDIDATES}
                rg = g
            smhi.append(r)
            opera.append(zon.decode(z["v"][i]))
        for r, o in zip(smhi, opera):
            if r is None:
                continue
            cov = np.isfinite(r) & np.isfinite(o)
            ow = cov & (o >= WET)
            gap = ow & (r == 0)
            sw = cov & (r >= WET)
            rev = sw & (o == 0)
            for name, idx, nb in (("beam", bb, len(BEAM_BINS)), ("dist", db, len(DIST_BINS))):
                for k, m in (("cov", cov), ("ow", ow), ("gap", gap), ("sw", sw), ("rev", rev)):
                    c = np.bincount(idx[m].ravel(), minlength=nb + 1)[:nb]
                    acc = res[name]
                    for b in range(nb):
                        acc.setdefault(str(b), _counts())[k] += int(c[b])
            for h, zm in zones.items():
                acc = res["kand"].setdefault(str(h), {**_counts(), "rutor": int(zm.sum())})
                for k, m in (("cov", cov), ("ow", ow), ("gap", gap), ("sw", sw), ("rev", rev)):
                    acc[k] += int((m & zm).sum())
            # kring de norska radarplatserna: OPERA:s eko, och glappet om det ligger i SMHI:s täckning
            for n, sd in site_d.items():
                for lo, hi in zip(SITE_BINS[:-1], SITE_BINS[1:]):
                    ring = (sd >= lo) & (sd < hi)
                    acc = res["plats"].setdefault(f"{n} {lo}-{hi}", {"rutor": int(ring.sum()), "opera_fin": 0,
                                                                  "opera_eko": 0, "smhi_fin": 0, "gap": 0,
                                                                  **{f"gap_H{h:g}": 0 for h in CANDIDATES}})
                    acc["opera_fin"] += int((ring & np.isfinite(o)).sum())
                    acc["opera_eko"] += int((ring & (np.nan_to_num(o) >= WET)).sum())
                    acc["smhi_fin"] += int((ring & np.isfinite(r)).sum())
                    acc["gap"] += int((ring & gap).sum())
                    for h, zm in zones.items():
                        acc[f"gap_H{h:g}"] += int((ring & gap & zm).sum())
        # mätarna per timme: SMHI och OPERA som medel av bilderna :15, :30, :45 och :00
        m = domare.load_gauges(d, "timme", rg)
        S = np.full((24, *grid.shape), np.nan, np.float32)
        O = np.full((24, *grid.shape), np.nan, np.float32)
        for hh in range(24):
            fr = [(smhi[4 * hh + j], opera[4 * hh + j]) for j in range(4) if 4 * hh + j < len(smhi)]
            fr = [(r, o) for r, o in fr if r is not None]
            if len(fr) >= 3:
                S[hh] = np.mean([r for r, _ in fr], axis=0)
                O[hh] = np.mean([o for _, o in fr], axis=0)
        s, o, g = S[m.t, m.r, m.c], O[m.t, m.r, m.c], m.mm
        ok = np.isfinite(s) & np.isfinite(o)
        bm = beam[m.r, m.c]
        for h in (0.0,) + CANDIDATES:
            inz = ok & np.isfinite(bm) & (bm > h)
            acc = res["matare"].setdefault(str(h), {"timmar": 0, "stationer": [], "andrade": 0, "andrade_vat": 0,
                                                     "g_andrade": 0.0, "o_andrade": 0.0,
                                                     "torr_torr": 0, "torr_torr_vat": 0,
                                                     "max_n": 0, "max_ae_smhi": 0.0, "max_ae_max": 0.0})
            acc["timmar"] += int(inz.sum())
            acc["stationer"] = sorted(set(acc["stationer"]) | set(int(x) for x in m.station[inz]))
            ch = inz & (s == 0) & (o >= WET)
            acc["andrade"] += int(ch.sum())
            acc["andrade_vat"] += int((ch & (g > 0)).sum())
            acc["g_andrade"] += float(g[ch].sum())
            acc["o_andrade"] += float(o[ch].sum())
            dd = inz & (s == 0) & (o == 0)
            acc["torr_torr"] += int(dd.sum())
            acc["torr_torr_vat"] += int((dd & (g > 0)).sum())
            mx = inz & (s >= WET) & (o > s)
            acc["max_n"] += int(mx.sum())
            acc["max_ae_smhi"] += float(np.abs(s[mx] - g[mx]).sum())
            acc["max_ae_max"] += float(np.abs(o[mx] - g[mx]).sum())
        print(d, "klar", flush=True)
    res["beam_bins"] = BEAM_BINS.tolist()
    res["dist_bins"] = DIST_BINS.tolist()
    # urvalet enligt regeln i docstringen
    val, why = None, {}
    for h in CANDIDATES:
        k = res["kand"][str(h)]
        fa = k["gap"] / max(k["ow"], 1)
        mt = res["matare"][str(h)]
        fb = mt["andrade_vat"] / mt["andrade"] if mt["andrade"] >= 20 else None
        why[str(h)] = {"a": fa, "b": fb, "b_timmar": mt["andrade"]}
        if val is None and fa >= 0.5 and (fb is None or fb >= 0.5):
            val = h
    hv = res["matare"][str(val)] if val is not None else None
    mode = "max" if hv and hv["max_n"] >= 20 and hv["max_ae_max"] < hv["max_ae_smhi"] else "torr"
    res["urval"] = {"H": val, "regel": mode, "kriterier": why}
    out = zon.OUT / f"frekvens_{a.del_}.json"
    out.write_text(json.dumps(res, indent=1))
    print(json.dumps(res["urval"], indent=1))


if __name__ == "__main__":
    main()
