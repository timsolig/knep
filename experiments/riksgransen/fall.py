"""Fallet 2026-11-07 16:00 till 18:15 UTC: SMHI:s nolla nordväst om Kiruna där OPERA har regn.

    uv run python experiments/riksgransen/fall.py hamta     SMHI och OPERA var 15:e minut, till /data/riksgransen/fall.npz
    uv run python experiments/riksgransen/fall.py siffror   glappet i rutan 68,3 till 68,7 N, 15,9 till 17,5 E
    uv run python experiments/riksgransen/fall.py karta H   kartor före och efter med zonen strålhöjd > H km

OPERA-originalen raderas direkt efter utskärningen.
"""

from __future__ import annotations

import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import zon  # noqa: E402
from knep.analys import composite, radar  # noqa: E402

FALL = zon.OUT / "fall.npz"
TIDER = [datetime(2026, 11, 7, 16, 0, tzinfo=UTC) + timedelta(minutes=15 * k) for k in range(10)]
BOX = (68.3, 68.7, 15.9, 17.5)


def hamta():
    import requests
    s = requests.Session()
    smhi, opera, grid = [], [], None
    for t in TIDER:
        r, g = radar.read_rain(radar.fetch(t, zon.OUT / "smhi", s))
        grid = grid or zon.grid_of(g)
        o = zon.fetch_opera_frame(s, t, grid, zon.OUT / "tmp")
        smhi.append(r)
        opera.append(o if o is not None else np.full(r.shape, np.nan, np.float32))
        time.sleep(0.6)
    np.savez_compressed(FALL, smhi=np.stack(smhi).astype(np.float16), opera=np.stack(opera).astype(np.float16),
                        times=np.array([t.isoformat() for t in TIDER]))
    print(FALL, FALL.stat().st_size)


def _grid():
    g = radar.read_rain(zon.OUT / "smhi" / f"{TIDER[0]:%Y%m%d%H%M}.tif")[1]
    return zon.grid_of(g)


def siffror():
    z = np.load(FALL)
    smhi, opera = z["smhi"].astype(np.float32), z["opera"].astype(np.float32)
    grid = _grid()
    lat, lon = zon.latlon(grid)
    beam, dist = zon.beam_se(grid), zon.dist_se(grid)
    box = (lat >= BOX[0]) & (lat <= BOX[1]) & (lon >= BOX[2]) & (lon <= BOX[3])
    print(f"rutan: {box.sum()} rutor, strålhöjd {np.nanmin(beam[box]):.1f} till {np.nanmax(beam[box]):.1f} km, "
          f"avstånd {dist[box].min():.0f} till {dist[box].max():.0f} km")
    print("tid    SMHI=0  SMHI=NaN  glapp(SMHI=0,OPERA>0,1)  SMHI medel  OPERA medel  OPERA medel i glappet")
    for k, t in enumerate(TIDER):
        s, o = smhi[k][box], opera[k][box]
        gap = (s == 0) & (o > 0.1)
        print(f"{t:%H:%M}  {int((s == 0).sum()):6d}  {int(np.isnan(s).sum()):8d}  {int(gap.sum()):8d}  "
              f"{np.nanmean(s):10.3f}  {np.nanmean(o):11.3f}  {o[gap].mean() if gap.any() else np.nan:8.2f}")
    # glappet i hela norr mot avståndet
    north = lat > 66
    print("\nhela norr (lat > 66), alla tider: glapp per avståndsklass (andel av rutor där OPERA > 0,1)")
    for a, b in ((0, 100), (100, 140), (140, 180), (180, 200), (200, 220), (220, 240)):
        sel = north & (dist >= a) & (dist < b)
        wet = (opera[:, sel] > 0.1)
        gap = wet & (smhi[:, sel] == 0)
        print(f"  {a:3d} till {b:3d} km: OPERA våt {int(wet.sum()):6d}, varav SMHI 0 {int(gap.sum()):6d} "
              f"({gap.sum() / max(wet.sum(), 1):.2f}), strålhöjd {np.nanmedian(beam[sel]):.1f} km")


def karta(h_km: float):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import BoundaryNorm, ListedColormap

    z = np.load(FALL)
    smhi, opera = z["smhi"].astype(np.float32), z["opera"].astype(np.float32)
    grid = _grid()
    far = composite.far_zone(grid, h_km)
    r0, r1, c0, c1 = 0, 260, 0, 300  # norr om ungefär 66 N
    lev = [0.1, 0.3, 0.5, 1, 2, 4, 8, 16, 100]
    cmap = ListedColormap(plt.get_cmap("viridis")(np.linspace(0.1, 1, len(lev) - 1)))
    cmap.set_under("white")
    cmap.set_bad("lightgrey")
    norm = BoundaryNorm(lev, cmap.N)
    zon.OUT.mkdir(parents=True, exist_ok=True)
    for k in (0, 4, 9):
        src = np.zeros(smhi[k].shape, np.uint8)
        fore, _ = composite.layer(smhi[k], src, opera[k], composite.SOURCE_OPERA)
        efter, _ = composite.layer_far(fore, src, opera[k], composite.SOURCE_OPERA, far)
        fig, ax = plt.subplots(1, 3, figsize=(15, 6.5))
        for a, f, title in zip(ax, (smhi[k], fore, efter), ("SMHI:s komposit", "A0 nu (OPERA där SMHI är NaN)",
                                                             f"A0 med OPERA i zonen (stråle > {h_km:g} km)")):
            im = a.imshow(f[r0:r1, c0:c1], cmap=cmap, norm=norm, interpolation="nearest")
            a.contour(far[r0:r1, c0:c1], [0.5], colors="red", linewidths=0.8)
            a.contour(np.isfinite(smhi[k])[r0:r1, c0:c1], [0.5], colors="black", linewidths=0.6)
            a.set_title(title, fontsize=10)
            a.set_xticks([]), a.set_yticks([])
        fig.colorbar(im, ax=ax, shrink=0.7, label="mm/h")
        fig.suptitle(f"{TIDER[k]:%Y-%m-%d %H:%M} UTC; rött: zonen, svart: SMHI:s täckning")
        p = zon.OUT / f"fall_{TIDER[k]:%H%M}_H{h_km:g}.png"
        fig.savefig(p, dpi=80)
        plt.close(fig)
        box_gap = far & (smhi[k] == 0) & (opera[k] > 0.1)
        print(p, "rutor ändrade:", int((efter != fore).sum()), "glapp i zonen:", int(box_gap.sum()))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "hamta":
        hamta()
    elif cmd == "siffror":
        siffror()
    else:
        karta(float(sys.argv[2]))
