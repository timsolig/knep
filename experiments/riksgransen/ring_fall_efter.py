"""Uppgift 0028: överlapp mellan den frysta masken och far_zone (H = 3), och fallet 2026-11-07 före och efter.

    uv run python experiments/riksgransen/ring_fall_efter.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ring_fall as rf  # noqa: E402
import ring_kand as rkd  # noqa: E402
import ring_karta as rk  # noqa: E402
import ring_profil as rp  # noqa: E402
import zon  # noqa: E402
from knep.analys import composite  # noqa: E402


def main():
    g = rf.grid()
    rad = json.loads(rkd.FRYST.read_text())["rad"]
    far = composite.far_zone(g, 3.0)
    for n, r in rad.items():
        la, lo = rp.PLATSER[n]
        m = zon.dist_to(g, la, lo) < r
        print(f"{n}: {int(m.sum())} rutor i masken, {int((m & far).sum())} i far_zone(H=3)")
    f = np.load("/data/riksgransen/fall.npz")
    op = f["opera"].astype(np.float32)
    P = rkd.platser(g)
    disc = np.zeros(g.shape, bool)
    for n, r in rad.items():
        disc |= P[n].d < r
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 2, figsize=(10, 10))
    i = 5
    for j, (r0, c0, n) in enumerate(((100, 80, "Røst"), (230, 70, "Sømna och Sørland"))):
        a = op[i][r0:r0 + 80, c0:c0 + 80]
        b = np.where(disc, np.nan, op[i])[r0:r0 + 80, c0:c0 + 80]
        ax[0, j].imshow(a, vmin=0, vmax=2); ax[0, j].set_title(f"{n} före {f['times'][i][11:16]}")
        ax[1, j].imshow(b, vmin=0, vmax=2); ax[1, j].set_title("efter (NaN = vitt)")
    fig.savefig(rk.TMP / "fall_fore_efter.png", dpi=50)


if __name__ == "__main__":
    main()
