"""Uppgift 4: Copernicus GLO-90 skalad till radarns rutnät (2 km, EPSG:3006).

Läser de öppna COG-filerna direkt från nätet (/vsicurl/, med översiktsnivå), lägger dem på ett
latlon-rutnät med 0,01 grader och projicerar om till radarns rutnät med medelvärde. Bara
resultatet sparas: /data/projektion/hojd_2km.npz (höjden i m, havet 0).

    uv run python experiments/projektion/hojd.py [en radarfil]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import reproject, transform_bounds

OUT = Path("/data/projektion/hojd_2km.npz")
URL = ("/vsicurl/https://copernicus-dem-90m.s3.amazonaws.com/"
       "Copernicus_DSM_COG_30_{ns}{lat:02d}_00_{ew}{lon:03d}_00_DEM/"
       "Copernicus_DSM_COG_30_{ns}{lat:02d}_00_{ew}{lon:03d}_00_DEM.tif")
D = 0.01  # grader i mellanrutnätet (ungefär 1 km)


def tile(lat: int, lon: int):
    ns, ew = ("N" if lat >= 0 else "S"), ("E" if lon >= 0 else "W")
    url = URL.format(ns=ns, lat=abs(lat), ew=ew, lon=abs(lon))
    n = int(round(1 / D))
    try:
        with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif"):
            with rasterio.open(url) as src:
                z = src.read(1, out_shape=(n, n), resampling=Resampling.average).astype(np.float32)
    except Exception:  # noqa: BLE001  ingen ruta (hav) eller fel: 0
        return None
    return np.where(z > -100, z, 0.0)


def main(radar_file: str) -> None:
    with rasterio.open(radar_file) as r:
        crs, tr, shape = r.crs, r.transform, r.shape
        b = r.bounds
    w, s, e, n = transform_bounds(crs, "EPSG:4326", *b, densify_pts=50)
    lat0, lat1 = int(np.floor(s)), int(np.ceil(n))
    lon0, lon1 = int(np.floor(w)), int(np.ceil(e))
    m = int(round(1 / D))
    big = np.zeros(((lat1 - lat0) * m, (lon1 - lon0) * m), np.float32)
    got = 0
    for lat in range(lat0, lat1):
        for lon in range(lon0, lon1):
            z = tile(lat, lon)
            if z is not None:
                r0 = (lat1 - 1 - lat) * m
                c0 = (lon - lon0) * m
                big[r0:r0 + m, c0:c0 + m] = z
                got += 1
        print("lat", lat, "rutor", got, flush=True)
    dst = np.zeros(shape, np.float32)
    reproject(big, dst, src_transform=from_origin(lon0, lat1, D, D), src_crs="EPSG:4326",
              dst_transform=tr, dst_crs=crs, resampling=Resampling.average)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(OUT, h=dst.astype(np.float32), transform=np.array(tr)[:6], crs=str(crs))
    print("klar", OUT, dst.shape, float(dst.max()), got, "rutor", flush=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/data/radar/2023/07/12/202307120000.tif")
