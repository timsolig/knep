"""Uppgift 0028: fallet 2026-11-07 (OPERA) nära Røst och Andøya, utsnitt och radiell profil per bild.

    uv run python experiments/riksgransen/ring_zoom.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ring_fall as rf  # noqa: E402
import ring_karta as rk  # noqa: E402
import zon  # noqa: E402

PL = {"Røst": (136.8, 123.1), "Andøya": (44.6, 202.6)}


def main():
    f = np.load("/data/riksgransen/fall.npz")
    op = f["opera"].astype(np.float32)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 4, figsize=(16, 8))
    for k, (n, (r, c)) in enumerate(PL.items()):
        r0, c0 = max(int(r) - 40, 0), max(int(c) - 40, 0)
        for j, i in enumerate((0, 3, 6, 9)):
            ax[k, j].imshow(op[i][r0:r0 + 80, c0:c0 + 80], vmin=0, vmax=2, cmap="viridis", extent=(c0, c0 + 80, r0 + 80, r0))
            ax[k, j].plot([c], [r], "r+")
            ax[k, j].set_title(f"{n} {f['times'][i][11:16]}")
    fig.savefig(rk.TMP / "fall_zoom.png", dpi=60)
    # radiell profil per bild: medel mm/h och andel >= 0,1, i 3-km-ringar
    for n, (r, c) in PL.items():
        rr, cc = np.mgrid[0:op.shape[1], 0:op.shape[2]]
        d = np.hypot(rr - r, cc - c) * 2.0
        print(n, "(km 0-3,3-6,...)")
        for i in range(0, len(op), 3):
            vals = []
            for a in range(0, 60, 6):
                m = (d >= a) & (d < a + 6) & np.isfinite(op[i])
                vals.append((np.nanmean(op[i][m] >= 0.1), np.nanmean(op[i][m])))
            print(f["times"][i][11:16], " ".join(f"{e:.2f}/{v:.2f}" for e, v in vals))


if __name__ == "__main__":
    main()
