"""Uppgift 0028: radiell profil av andelen eko kring de norska radarplatserna och en karta.

    uv run python experiments/riksgransen/ring_profil.py   (kräver ring_karta.py frekvens)
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ring_karta as rk  # noqa: E402
import zon  # noqa: E402
from knep.analys import composite  # noqa: E402

PLATSER = {"Røst": (67.55, 12.06), "Andøya": (69.24, 15.88), **{k: (v[0], v[1]) for k, v in composite.RADARS.items() if not k.startswith("se")}}


def main():
    f = np.load(rk.TMP / "frek_traning.npz")
    cov = np.maximum(f["cov"], 1)
    fe, ft = f["eko"] / cov, f["torr"] / cov
    ok = f["cov"] > 0.5 * f["n"]
    rows = []
    # kodens radarlista: alla icke-svenska
    print("radarer i composite.RADARS:", {k: v[:2] for k, v in composite.RADARS.items() if not k.startswith("se")})
    grid = zon.grid_of(__import__("knep.analys.radar", fromlist=["x"]).read_rain(zon.OUT.parent / "radar" / "2020" / "02" / "10" / "202002100000.tif")[1]) if False else None
    import json
    from knep.analys import radar
    import glob
    p = sorted(glob.glob("/data/radar/2020/02/10/*.tif"))[0]
    grid = zon.grid_of(radar.read_rain(Path(p))[1])
    np.save(rk.TMP / "dummy.npy", np.zeros(1))
    out = {}
    edges = np.arange(0, 125, 5)
    for namn, (lat, lon) in PLATSER.items():
        d = zon.dist_to(grid, lat, lon)
        # sökning av toppen i fe_torr inom 20 km
        near = (d < 20) & ok
        if near.sum() == 0:
            print(namn, "utanför bilden")
            continue
        prof = []
        for a, b in zip(edges[:-1], edges[1:]):
            m = (d >= a) & (d < b) & ok
            prof.append((float(a), int(m.sum()), float(fe[m].mean()) if m.any() else None, float(ft[m].mean()) if m.any() else None))
        out[namn] = prof
        print(namn, lat, lon, "toppen torra grannar inom 20 km:", float(ft[near].max()), "eko:", float(fe[near].max()))
        print("  km  rutor  andel_eko  andel_eko_torra_grannar")
        for a, n, e, t in prof:
            if e is not None:
                print(f"  {a:3.0f} {n:5d}  {e:.4f}  {t:.5f}")
    # karta
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(10, 9))
    for a, arr, tit in ((ax[0], fe, "andel bilder med eko"), (ax[1], ft, "eko med torra grannar (42 km)")):
        a.imshow(np.where(ok, arr, np.nan), vmax=np.nanpercentile(arr[ok], 99.8), cmap="magma")
        a.set_title(tit)
    fig.savefig(rk.TMP / "frekvens_karta.png", dpi=70)
    np.savez(rk.TMP / "profil.npz", fe=fe, ft=ft, ok=ok)


if __name__ == "__main__":
    main()
