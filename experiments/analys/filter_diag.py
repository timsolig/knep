"""Diagnostik för filtret (uppgift 4): mätarna som ligger i klotterkartans rutor på några träningsdagar.

    uv run python experiments/analys/filter_diag.py 2020-02-10 2020-07-24 2020-10-07
"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import filter as F  # noqa: E402

D = F.domare


def main(days):
    from knep.analys import radar
    M = np.load(F.KARTA)
    K, torr, eko = M["klotter"], M["torr"], M["eko"]
    z = np.load("/data/analys/artefakter/kartor.npz")
    hz = np.load(D.HOJD)["h"]
    for day in days:
        assert day in D.days("traning")
        _, grid = radar.read_rain(next(iter(sorted((D.RADAR / day.replace("-", "/")).glob("*.tif")))))
        m = D.load_gauges(day, "timme", grid)
        inM = K[m.r, m.c]
        print(day, "mätare i kartan:", len(np.unique(m.station[inM])), "av", len(np.unique(m.station)))
        for s in np.unique(m.station[inM]):
            sel = m.station == s
            r, c = m.r[sel][0], m.c[sel][0]
            print(f"  station {s} höjd {int(hz[r, c])} torr-krit {bool(torr[r, c])} eko-krit {bool(eko[r, c])} "
                  f"mm {m.mm[sel].sum():.1f} f_torr {float(z['f_torr'][r, c]):.3f} tex {float(z['tex'][r, c]):.1f} "
                  f"f_iso {float(z['f_iso'][r, c]):.3f} lyft {float(z['lyft'][r, c]):.2f} typ {int(z['typ'][r, c])} "
                  f"överskott {float(z['overskott'][r, c]):.3f}")


if __name__ == "__main__":
    main(sys.argv[1:])
