"""Uppgift 0028: andelen eko (>= 0,1 mm/h) i ringar kring varje icke-svensk OPERA-radar i de bilder där
omgivningen (30 till 50 km) är torr (under 3 % eko), träningsdagarna. Skiljer ringen från vädret.

    uv run python experiments/riksgransen/ring_torr.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ring_fall as rf  # noqa: E402
import ring_karta as rk  # noqa: E402
import ring_profil as rp  # noqa: E402
import zon  # noqa: E402

KANTER = [0, 4, 8, 12, 16, 20, 25, 30]


def main():
    g = rf.grid()
    ds = {n: zon.dist_to(g, la, lo) for n, (la, lo) in rp.PLATSER.items() if n not in ("Røst", "Andøya")}
    ds = {n: d for n, d in ds.items() if (d < 5).any()}
    idx = {n: [(d >= a) & (d < b) for a, b in zip(KANTER[:-1], KANTER[1:])] for n, d in ds.items()}
    ann = {n: (d >= 30) & (d < 50) for n, d in ds.items()}
    acc = {n: np.zeros((len(KANTER) - 1, 2)) for n in ds}
    nfr = {n: 0 for n in ds}
    for day in rk.dagar("traning"):
        eko, cov = rk.eko_dag(day)
        for i in range(len(eko)):
            for n in ds:
                a = ann[n] & cov[i]
                if a.sum() < 100 or eko[i][a].mean() >= 0.03:
                    continue
                nfr[n] += 1
                for k, m in enumerate(idx[n]):
                    mm = m & cov[i]
                    acc[n][k] += (eko[i][mm].sum(), mm.sum())
    print("km:", KANTER, "(bilder med torr omgivning, andel eko per ring)")
    for n in ds:
        print(f"{n:7s} {nfr[n]:4d} bilder  " + " ".join(f"{a / max(b, 1):.3f}" for a, b in acc[n]))


if __name__ == "__main__":
    main()
