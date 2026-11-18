"""Uppgift 0028: platserna i pixlar och fallet 2026-11-07 (OPERA) som bild.

    uv run python experiments/riksgransen/ring_fall.py [namn.png]
"""

from __future__ import annotations

import glob
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ring_karta as rk  # noqa: E402
import ring_profil as rp  # noqa: E402
import zon  # noqa: E402
from knep.analys import radar  # noqa: E402


def grid():
    return zon.grid_of(radar.read_rain(Path(sorted(glob.glob("/data/radar/2020/02/10/*.tif"))[0]))[1])


def pix(g, lat, lon):
    from pyproj import Transformer
    x, y = Transformer.from_crs("EPSG:4326", "EPSG:3006", always_xy=True).transform(lon, lat)
    return (y - 0) and ((g.north - y) / g.res, (x - g.west) / g.res)


if __name__ == "__main__":
    g = grid()
    for k, (la, lo) in rp.PLATSER.items():
        r, c = pix(g, la, lo)
        print(k, round(r, 1), round(c, 1))
    f = np.load("/data/riksgransen/fall.npz")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 3, figsize=(15, 10))
    for j, i in enumerate((2, 5, 8)):
        for k, key in enumerate(("smhi", "opera")):
            a = f[key][i].astype(np.float32)
            ax[k, j].imshow(a[0:450, 0:471], vmin=0, vmax=5, cmap="viridis")
            ax[k, j].set_title(f"{key} {f['times'][i][11:16]}")
    fig.savefig(rk.TMP / (sys.argv[1] if len(sys.argv) > 1 else "fall.png"), dpi=60)
