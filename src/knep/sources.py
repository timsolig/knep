"""Reservkällor till kompositen: EUMETNET:s öppna radardata (CC BY 4.0).

Enskilda radarvolymer (ODIM PVOL) och OPERA-kompositen ligger i en öppen S3-hink.
Senaste dygnet finns i `openradar-24h`, äldre data i `openradar-archive` (från 2012).
Se https://eumetnet.github.io/openradardata-documentation/

Allt här är best effort: en källa som inte svarar ger None och kompositen går vidare
med nästa lager.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import requests

from . import composite

log = logging.getLogger("knep.sources")
S3 = "https://s3.waw3-1.cloudferro.com"
BUCKETS = ("openradar-24h", "openradar-archive")
_NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"


def list_keys(session: requests.Session, bucket: str, prefix: str) -> list[str]:
    keys, token = [], None
    while True:
        params = {"list-type": "2", "prefix": prefix}
        if token:
            params["continuation-token"] = token
        r = session.get(f"{S3}/{bucket}", params=params, timeout=30)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        keys += [k.text for k in root.iter(f"{_NS}Key")]
        if root.findtext(f"{_NS}IsTruncated") == "true":
            token = root.findtext(f"{_NS}NextContinuationToken")
        else:
            return keys


def key_time(key: str) -> datetime | None:
    m = re.search(r"(\d{8})T?(\d{4})", key.rsplit("/", 1)[-1])
    return datetime.strptime("".join(m.groups()), "%Y%m%d%H%M").replace(tzinfo=UTC) if m else None


def _download(session, bucket, key, cache: Path) -> Path:
    path = cache / key.replace("/", "_")
    if not path.exists():
        r = session.get(f"{S3}/{bucket}/{key}", timeout=60)
        r.raise_for_status()
        tmp = path.with_suffix(".part")
        tmp.write_bytes(r.content)
        tmp.replace(path)
    return path


def fetch_pvol(session, site: str, t: datetime, cache: Path, tol=timedelta(minutes=3)) -> Path | None:
    """Volymen från en radar närmast tiden t, inom tol."""
    prefix = f"{t:%Y/%m/%d}/{site[:2].upper()}/{site}/PVOL/"
    for bucket in BUCKETS:
        try:
            keys = list_keys(session, bucket, prefix)
        except requests.RequestException as e:
            log.debug("%s %s: %s", bucket, prefix, e)
            continue
        timed = [(abs(kt - t), k) for k in keys if (kt := key_time(k)) is not None and abs(kt - t) <= tol]
        if timed:
            try:
                return _download(session, bucket, min(timed)[1], cache)
            except requests.RequestException as e:
                log.warning("kunde inte hämta %s: %s", site, e)
    return None


def fetch_opera(session, t: datetime, cache: Path) -> Path | None:
    key = f"{t:%Y/%m/%d}/OPERA/COMP/OPERA@{t:%Y%m%dT%H%M}@0@DBZH.h5"
    for bucket in BUCKETS:
        try:
            return _download(session, bucket, key, cache)
        except requests.RequestException:
            continue
    return None


def read_opera(path: Path, grid: composite.TargetGrid) -> np.ndarray:
    """OPERA:s DBZH-komposit omprojicerad till rutnätet, i mm/h. NaN där OPERA saknar data."""
    import h5py
    import rasterio
    from rasterio.crs import CRS
    from rasterio.transform import Affine
    from rasterio.warp import Resampling, reproject
    from pyproj import Transformer

    with h5py.File(path, "r") as h:
        where = h["where"].attrs
        proj = where["projdef"].decode() if isinstance(where["projdef"], bytes) else str(where["projdef"])
        xs, ys = float(where["xscale"]), float(where["yscale"])
        what = h["dataset1/data1/what"].attrs
        raw = h["dataset1/data1/data"][...].astype(np.float32)
        dbz = raw * float(what["gain"]) + float(what["offset"])
        dbz[raw == float(what["nodata"])] = np.nan
        dbz[raw == float(what["undetect"])] = -32.0
        x0, y0 = Transformer.from_crs("EPSG:4326", proj, always_xy=True).transform(float(where["UL_lon"]), float(where["UL_lat"]))
    dst = np.full(grid.shape, np.nan, np.float32)
    reproject(dbz, dst, src_transform=Affine(xs, 0, x0, 0, -ys, y0), src_crs=CRS.from_proj4(proj),
              dst_transform=Affine(grid.res, 0, grid.west, 0, -grid.res, grid.north), dst_crs=CRS.from_epsg(3006),
              resampling=Resampling.nearest, src_nodata=np.nan, dst_nodata=np.nan)
    return composite.dbz_to_rain(dst)


def radars_covering(mask, grid: composite.TargetGrid, max_range_km: float, exclude=()):
    """Radarer vars räckvidd når någon pixel i mask, närmast först."""
    from pyproj import Transformer

    rows, cols = np.nonzero(mask)
    if rows.size == 0:
        return []
    x = grid.west + (cols + 0.5) * grid.res
    y = grid.north - (rows + 0.5) * grid.res
    to_grid = Transformer.from_crs("EPSG:4326", "EPSG:3006", always_xy=True)
    out = []
    for code, (lat, lon, _, _) in composite.RADARS.items():
        if code in exclude:
            continue
        x0, y0 = to_grid.transform(lon, lat)
        d = np.hypot(x - x0, y - y0).min() / 1000
        if d <= max_range_km:
            out.append((d, code))
    return [c for _, c in sorted(out)]


def volume_composite(session, t: datetime, grid: composite.TargetGrid, cache: Path, sites=None, max_range_km=None):
    """Egen komposit av enskilda volymer. Returnerar (mm/h, kvalitet, lista med radarer som bidrog).

    max_range_km kan sättas längre än radarns ordinarie räckvidd för att täcka ett bortfall
    från grannradarer, med högre strålar och därför lägre kvalitet.
    """
    layers, used = [], []
    for site in sites or composite.RADARS:
        path = fetch_pvol(session, site, t, cache)
        if path is None:
            continue
        try:
            sweep = composite.read_pvol(path)
            layers.append(composite.grid_sweep(sweep, grid, max_range_km or composite.RADARS[site][3]))
            used.append(site)
        except (OSError, KeyError, ValueError) as e:
            log.warning("kunde inte läsa %s: %s", path.name, e)
    if not layers:
        return None, None, []
    dbz, q = composite.mosaic(layers)
    return composite.dbz_to_rain(dbz), q, used
