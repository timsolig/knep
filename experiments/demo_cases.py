"""Bygger händelseflikar av de öppna testfallen, så att sidan har innehåll innan Pi:n byggt de svenska.

Kedjan körs med sannolikheterna som tränats utan det aktuella fallet, så det som
visas är prognoser utanför urvalet.

    python experiments/demo_cases.py <pysteps-data> <gen> --out web/cases
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC
from pathlib import Path

import numpy as np
from rasterio.crs import CRS
from rasterio.transform import from_origin

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from cases import load  # noqa: E402

from knep import cases, model, radar  # noqa: E402

DEMO = {
    "knmi_20100826": ("test-knmi-2010", "Testfall: ihållande regn i Nederländerna", "regn"),
    "rmi_20210704": ("test-rmi-2021", "Testfall: skyfall i Belgien", "regn"),
    "mch_20150515": ("test-mch-2015", "Testfall: åska över Alperna", "regn"),
    "fmi_20160928": ("test-fmi-2016", "Testfall: åska i Finland", "regn"),
    "mch_20170131": ("test-mch-2017", "Testfall: vinternederbörd i Schweiz", "regn"),
}


def grid_of(meta, shape):
    proj = meta["projection"]
    k = 1.0
    if "+a=6378.137" in proj:  # KNMI anger ellipsoid och koordinater i km
        proj = proj.replace("+a=6378.137", "+a=6378137").replace("+b=6356.752", "+b=6356752")
        k = 1000.0
    px = meta["xpixelsize"]  # redan i meter efter cases.load
    r0, c0 = meta.get("crop", (0, 0))
    x1, y2 = meta["x1"] * k, meta["y2"] * k
    return radar.Grid(CRS.from_proj4(proj), from_origin(x1 + c0 * px, y2 - r0 * px, px, px), shape)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data", type=Path)
    ap.add_argument("gen", type=Path)
    ap.add_argument("--out", type=Path, default=Path("web/cases"))
    ap.add_argument("--cases", nargs="*", default=list(DEMO))
    a = ap.parse_args()
    for name in a.cases:
        slug, title, kind = DEMO[name]
        obs, times, meta = load(a.data, name)
        if meta.get("yorigin", "upper") == "lower":
            obs = obs[:, ::-1]
        times = [t.replace(tzinfo=UTC) for t in times]
        idx = {t: k for k, t in enumerate(times)}
        o = obs[np.isfinite(obs)]
        text = (f"Öppet radarfall från pysteps-data, {times[0]:%Y-%m-%d}. Högst {o.max():.0f} mm/h i 2 km-rutorna. "
                "Visar hur kedjan och KNEP-proxyn klarar händelsen; sannolikheterna för kraftig nederbörd är tränade utan det här fallet.")
        ev = cases.Event(slug, title, times[13], times[-1], kind, text, ("https://github.com/pySTEPS/pysteps-data",), "pysteps")
        mpath = a.gen / "ext" / "models" / f"model_utan_{name}.pkl"
        chain = model.Chain(mpath if mpath.exists() else None)
        frames = lambda ts: [obs[idx[t]] if t in idx else None for t in ts]
        cases.build(ev, frames, grid_of(meta, obs.shape[1:]), a.out / slug, chain)
        print(f"{slug}: klart", flush=True)
    cases.write_index(a.out)


if __name__ == "__main__":
    main()
