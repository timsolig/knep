"""Diagnos för kontrollen per station och dygn (uppgift 0007), bara träningsdagarna: hur många grannar
mätarna har inom R km och hur de syntetiska dygnsfelen ser ut mot radarn.

    uv run python experiments/analys/qcs_diag.py [--dagar 3]
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a2  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dagar", type=int, default=3)
    a = ap.parse_args()
    pds = a2._train_pdays(a)
    for pd in pds:
        a2.syntetiska_dygn(pd, 0.03)
        Q = pd.res["kvart"]
        for R in (50, 75, 100):
            ns = []
            for t in np.unique(Q["t"]):
                i = np.flatnonzero(Q["t"] == t)
                tr = cKDTree(Q["xy"][i])
                ns += [len(x) - 1 for x in tr.query_ball_point(Q["xy"][i], R)]
            ns = np.array(ns)
            print(pd.day, R, "km: grannar median", np.median(ns), "andel med minst 2", round((ns >= 2).mean(), 3))
        for s, ty in pd.syn_dygn.items():
            i = Q["station"] == s
            av = Q["a"][i]
            print("  ", s, a2.SYN_DYGN[ty], "perioder", int(i.sum()), "radar torr", int((av <= 0.01).sum()),
                  "radar minst 0,5", int((av >= 0.5).sum()), "sant", round(float(np.nansum(Q["mm"][i])), 1),
                  "in", round(float(np.nansum(Q["mm_in"][i])), 1))


if __name__ == "__main__":
    main()
