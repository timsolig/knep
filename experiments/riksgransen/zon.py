"""Gemensamt för uppgift 0010 (glappet nordväst om Riksgränsen): rutnätet, de svenska radarernas
strålhöjd och avstånd, de norska radarplatserna och OPERA-utsnitten.

OPERA-utsnitten sparas under /data/riksgransen/opera/<dag>.npz: för varje 5-minutersbild ett
uint8-fält över hela radarns rutnät (887 × 471) med samma kodning som SMHI:s
komposit, dBZ = 0,4 · v − 30, 0 = inget eko (under 0 dBZ i OPERA eller -32), 255 = OPERA saknar
data. Tider utan OPERA-fil har alla värden 255 och står i `saknas`.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from knep.analys import bias, composite  # noqa: E402

OUT = Path("/data/riksgransen")
OPERA_DIR = OUT / "opera"
NO_SITES = {"Røst": (67.53, 12.10), "Andøya": (69.24, 16.00)}  # composite.RADARS norst, noand


def grid_of(g) -> composite.TargetGrid:
    """TargetGrid ur radar.Grid (som knep.analys.target)."""
    return composite.TargetGrid(g.transform.c, g.transform.f, g.transform.a, g.shape)


def swedish():
    return {k: v for k, v in composite.RADARS.items() if k.startswith("se")}


def beam_se(grid: composite.TargetGrid) -> np.ndarray:
    """Lägsta strålhöjden (km över havet, 0,5°) bland de svenska radarerna; NaN bortom 240 km."""
    return bias.beam_height(grid, swedish())


def dist_se(grid: composite.TargetGrid) -> np.ndarray:
    """Avståndet i km till närmaste svenska radar."""
    from pyproj import Transformer
    X, Y = grid.centres()
    tr = Transformer.from_crs("EPSG:4326", "EPSG:3006", always_xy=True)
    best = np.full(grid.shape, np.inf)
    for lat, lon, _, _ in swedish().values():
        x0, y0 = tr.transform(lon, lat)
        best = np.minimum(best, np.hypot(X - x0, Y - y0))
    return (best / 1000).astype(np.float32)


def dist_to(grid: composite.TargetGrid, lat: float, lon: float) -> np.ndarray:
    from pyproj import Transformer
    X, Y = grid.centres()
    x0, y0 = Transformer.from_crs("EPSG:4326", "EPSG:3006", always_xy=True).transform(lon, lat)
    return (np.hypot(X - x0, Y - y0) / 1000).astype(np.float32)


def latlon(grid: composite.TargetGrid):
    from pyproj import Transformer
    X, Y = grid.centres()
    lon, lat = Transformer.from_crs("EPSG:3006", "EPSG:4326", always_xy=True).transform(X, Y)
    return np.asarray(lat, np.float32), np.asarray(lon, np.float32)


def encode(rain: np.ndarray) -> np.ndarray:
    """mm/h till SMHI:s kodning uint8 (0 inget eko, 255 saknas)."""
    out = np.full(rain.shape, 255, np.uint8)
    fin = np.isfinite(rain)
    with np.errstate(divide="ignore", invalid="ignore"):
        dbz = 10 * np.log10(composite.ZR_A * np.maximum(rain, 1e-9) ** composite.ZR_B)
    v = np.clip(np.rint((dbz + 30) / 0.4), 1, 254)
    out[fin] = np.where(rain[fin] > 0, v[fin], 0).astype(np.uint8)
    return out


def decode(v: np.ndarray) -> np.ndarray:
    """uint8 till mm/h som radar.read_rain (NaN där 255)."""
    dbz = v.astype(np.float32) * 0.4 - 30
    rain = composite.dbz_to_rain(dbz)
    rain[v == 0] = 0.0
    rain[v == 255] = np.nan
    return rain


def read_opera_any(path: Path, grid: composite.TargetGrid) -> np.ndarray:
    """Som sources.read_opera, men läser också det äldre formatet (DBZH_QIND.h5, före 2024, var
    15:e minut, float64 med gain och nodata under dataset1/what)."""
    import h5py
    from pyproj import Transformer
    from rasterio.crs import CRS
    from rasterio.transform import Affine
    from rasterio.warp import Resampling, reproject

    with h5py.File(path, "r") as h:
        where = h["where"].attrs
        proj = where["projdef"].decode() if isinstance(where["projdef"], bytes) else str(where["projdef"])
        xs, ys = float(where["xscale"]), float(where["yscale"])
        what = h["dataset1/data1/what"].attrs if "what" in h["dataset1/data1"] else h["dataset1/what"].attrs
        raw = h["dataset1/data1/data"][...].astype(np.float32)
        dbz = raw * float(what["gain"]) + float(what["offset"])
        dbz[raw == np.float32(what["nodata"])] = np.nan
        dbz[raw == np.float32(what["undetect"])] = -32.0
        x0, y0 = Transformer.from_crs("EPSG:4326", proj, always_xy=True).transform(float(where["UL_lon"]), float(where["UL_lat"]))
    dst = np.full(grid.shape, np.nan, np.float32)
    reproject(dbz, dst, src_transform=Affine(xs, 0, x0, 0, -ys, y0), src_crs=CRS.from_proj4(proj),
              dst_transform=Affine(grid.res, 0, grid.west, 0, -grid.res, grid.north), dst_crs=CRS.from_epsg(3006),
              resampling=Resampling.nearest, src_nodata=np.nan, dst_nodata=np.nan)
    return composite.dbz_to_rain(dst)


def fetch_opera_frame(session, t: datetime, grid: composite.TargetGrid, tmp: Path):
    """OPERA för tiden t på hela rutnätet i mm/h, eller None. Originalfilen raderas direkt.
    Provar det nya namnet (DBZH.h5) och sedan det äldre (DBZH_QIND.h5)."""
    import requests
    from knep.analys import sources
    tmp.mkdir(parents=True, exist_ok=True)
    p = None
    for suffix in ("DBZH", "DBZH_QIND"):
        key = f"{t:%Y/%m/%d}/OPERA/COMP/OPERA@{t:%Y%m%dT%H%M}@0@{suffix}.h5"
        try:
            p = sources._download(session, "openradar-archive", key, tmp)
            break
        except requests.RequestException:
            continue
    if p is None:
        return None
    try:
        return read_opera_any(p, grid)
    except (OSError, KeyError, ValueError):
        return None
    finally:
        p.unlink(missing_ok=True)


def load_opera_day(day_s: str):
    """(tider, utsnitt uint8 (n, H, W)) för dagen, eller None."""
    p = OPERA_DIR / f"{day_s}.npz"
    if not p.exists():
        return None
    z = np.load(p)
    return [datetime.fromisoformat(s) for s in z["times"]], z["v"]
