"""SMHI:s radarkomposit för Sverige: 5 min, 8-bitars GeoTIFF i EPSG:3006.

Kodning enligt https://opendata.smhi.se/apidocs/radar/data.html
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import rasterio
import requests
from rasterio.crs import CRS

BASE = "https://opendata-download-radar.smhi.se/api/version/latest/area/sweden/product/comp"
STEP = timedelta(minutes=5)

GAIN, OFFSET = 0.4, -30.0  # dBZ = värde * GAIN + OFFSET
NO_ECHO, NO_DATA = 0, 255  # inget eko inom täckning / utanför täckning
ZR_A, ZR_B = 200.0, 1.5  # SMHI:s Z-R-samband: Z = 200 R^1.5


@dataclass(frozen=True)
class Grid:
    crs: CRS
    transform: rasterio.Affine
    shape: tuple[int, int]


def url_for(t: datetime) -> str:
    return f"{BASE}/{t:%Y/%m/%d}/radar_{t:%y%m%d%H%M}.tif"


def latest_time(session: requests.Session) -> datetime:
    r = session.get(BASE, params={"format": "tif"}, timeout=20)
    r.raise_for_status()
    valid = r.json()["lastFiles"][0]["valid"]
    return datetime.strptime(valid, "%Y-%m-%d %H:%M").replace(tzinfo=UTC)


def fetch(t: datetime, cache: Path, session: requests.Session) -> Path:
    """Hämta en komposit till cachen om den inte redan finns där."""
    path = cache / f"{t:%Y%m%d%H%M}.tif"
    if not path.exists():
        r = session.get(url_for(t), timeout=30)
        r.raise_for_status()
        tmp = path.with_suffix(".part")
        tmp.write_bytes(r.content)
        tmp.replace(path)
    return path


def read_rain(path: Path) -> tuple[np.ndarray, Grid]:
    """Läs en komposit som regnintensitet i mm/h. NaN utanför radartäckningen."""
    with rasterio.open(path) as src:
        raw = src.read(1)
        grid = Grid(src.crs or CRS.from_epsg(3006), src.transform, raw.shape)
    dbz = raw.astype(np.float32) * GAIN + OFFSET
    rain = (10.0 ** (dbz / 10.0) / ZR_A) ** (1.0 / ZR_B)
    rain[raw == NO_ECHO] = 0.0
    rain[raw == NO_DATA] = np.nan
    return rain, grid
