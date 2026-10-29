"""Kompositen: syntetiska ODIM-volymer, mosaik, utfyllnad vid bortfall."""

import numpy as np
import pytest
from pyproj import Transformer

from knep import composite

h5py = pytest.importorskip("h5py")

GRID = dict(west=126648.0, north=7771252.0, res=2000.0, shape=(894, 475))
TO_GRID = Transformer.from_crs("EPSG:4326", "EPSG:3006", always_xy=True)


def _pixel(grid, lon, lat):
    x, y = TO_GRID.transform(lon, lat)
    return int((grid.north - y) // grid.res), int((x - grid.west) // grid.res)


def write_pvol(path, site, cell_lonlat, cell_dbz=45.0, nrays=360, nbins=500, rscale=500.0, elangle=0.5):
    """En volym med en elevation där ett område runt cell_lonlat har cell_dbz, annars inget eko."""
    lat, lon, hgt, _ = composite.RADARS[site]
    aeqd = Transformer.from_crs("EPSG:4326", f"+proj=aeqd +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m", always_xy=True)
    cx, cy = aeqd.transform(*cell_lonlat)
    az = np.radians((np.arange(nrays) + 0.5) * 360 / nrays)
    rng = (np.arange(nbins) + 0.5) * rscale
    x = np.sin(az)[:, None] * rng[None, :] * np.cos(np.radians(elangle))
    y = np.cos(az)[:, None] * rng[None, :] * np.cos(np.radians(elangle))
    dbz = np.where(np.hypot(x - cx, y - cy) < 15000, cell_dbz, -32.0)
    gain, offset = 0.5, -32.0
    raw = np.round((dbz - offset) / gain).astype(np.uint8)
    raw[dbz <= -32] = 0  # undetect
    with h5py.File(path, "w") as h:
        h.create_group("what").attrs.update({"object": b"PVOL", "source": f"WMO:0,NOD:{site}".encode()})
        h.create_group("where").attrs.update({"lat": lat, "lon": lon, "height": float(hgt)})
        ds = h.create_group("dataset1")
        ds.create_group("where").attrs.update({"elangle": elangle, "nbins": nbins, "nrays": nrays,
                                               "rscale": rscale, "rstart": 0.0, "a1gate": 17})
        d = ds.create_group("data1")
        d.create_group("what").attrs.update({"quantity": b"DBZH", "gain": gain, "offset": offset,
                                             "nodata": 255.0, "undetect": 0.0})
        d.create_dataset("data", data=raw)


def test_volume_lands_on_the_right_pixel(tmp_path):
    grid = composite.TargetGrid(**GRID)
    cell = (13.6, 56.6)  # öster om Ängelholm
    write_pvol(tmp_path / "a.h5", "seang", cell)
    sweep = composite.read_pvol(tmp_path / "a.h5")
    assert sweep.site == "seang" and sweep.dbz.shape == (360, 500)
    dbz, q = composite.grid_sweep(sweep, grid)
    r, c = _pixel(grid, *cell)
    assert dbz[r, c] == pytest.approx(45.0, abs=0.6)
    assert np.isfinite(dbz).sum() > 1000 and (q > 0).sum() == np.isfinite(dbz).sum()
    lat, lon = composite.RADARS["seang"][:2]
    r0, c0 = _pixel(grid, lon, lat)
    assert q[r0, c0] > q[r, c]  # kvaliteten avtar med avståndet (strålhöjden)


def test_mosaic_prefers_the_lower_beam(tmp_path):
    grid = composite.TargetGrid(**GRID)
    cell = (13.0, 56.5)  # nära Ängelholm, långt från Karlskrona
    write_pvol(tmp_path / "a.h5", "seang", cell, cell_dbz=45.0)
    write_pvol(tmp_path / "b.h5", "sekaa", cell, cell_dbz=30.0)
    layers = [composite.grid_sweep(composite.read_pvol(tmp_path / f), grid) for f in ("a.h5", "b.h5")]
    dbz, q = composite.mosaic(layers)
    r, c = _pixel(grid, *cell)
    assert dbz[r, c] > 44.0


def test_gap_is_filled_by_advection_and_then_released():
    h, w = 120, 160
    y, x = np.mgrid[0:h, 0:w]
    def cell(k):
        return (20 * np.exp(-(((x - 40 - 2 * k) / 8) ** 2 + ((y - 60) / 8) ** 2))).astype(np.float32)
    motion = np.zeros((2, h, w), np.float32)
    motion[0] = 2.0  # 2 pixlar österut per 5 min
    src = np.zeros((h, w), np.uint8)
    rain, s, q, state = composite.fill_gaps(cell(0), src, None, motion)
    for k in range(1, 4):
        rain, s, q, state = composite.fill_gaps(cell(k), src, state, motion)
    hole = (x - 50) ** 2 + (y - 60) ** 2 < 30**2  # en radar faller bort
    for k in range(4, 10):
        obs = cell(k)
        obs[hole] = np.nan
        rain, s, q, state = composite.fill_gaps(obs, np.where(hole, 255, 0).astype(np.uint8), state, motion)
    truth = cell(9)
    assert np.all(s[hole] == composite.SOURCE_ADVECTED)
    assert abs(np.argmax(rain[60]) - np.argmax(truth[60])) <= 2
    assert 0 < q[hole].max() < 1
    # efter max_age släpps pixlarna som saknade
    for k in range(10, 32):
        obs = cell(k)
        obs[hole] = np.nan
        rain, s, q, state = composite.fill_gaps(obs, np.where(hole, 255, 0).astype(np.uint8), state, motion)
    assert np.isnan(rain[hole]).all()


def test_missing_radar_is_reported():
    grid = composite.TargetGrid(**GRID)
    rain = np.zeros(grid.shape, np.float32)
    lat, lon = composite.RADARS["sehuv"][:2]
    r0, c0 = _pixel(grid, lon, lat)
    yy, xx = np.mgrid[0 : grid.shape[0], 0 : grid.shape[1]]
    rain[(yy - r0) ** 2 + (xx - c0) ** 2 < 60**2] = np.nan
    assert composite.missing_radars(rain, grid, np.ones(grid.shape, np.float32)) == ["sehuv"]


def test_radars_covering_a_hole_nearest_first():
    from knep import sources
    grid = composite.TargetGrid(**GRID)
    r, c = _pixel(grid, 16.7, 61.6)  # vid Hudiksvall
    hole = np.zeros(grid.shape, bool)
    hole[r - 3 : r + 3, c - 3 : c + 3] = True
    near = sources.radars_covering(hole, grid, 320.0, exclude={"sehuv"})
    assert near[0] in ("selek", "seoer") and "sehuv" not in near and "sekrn" not in near


class _FakeResponse:
    def __init__(self, content=b"", status=200):
        self.content, self.status_code = content, status

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(str(self.status_code))


class _FakeS3:
    """Svarar som en S3-hink: listning med prefix och nedladdning av en nyckel."""

    def __init__(self, keys, body=b"h5"):
        self.keys, self.body, self.got = keys, body, []

    def get(self, url, params=None, timeout=None):
        if params and params.get("list-type") == "2":
            if "openradar-24h" not in url:
                return _FakeResponse(status=404)
            ks = [k for k in self.keys if k.startswith(params["prefix"])]
            xml = '<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">' + "".join(
                f"<Contents><Key>{k}</Key></Contents>" for k in ks) + "<IsTruncated>false</IsTruncated></ListBucketResult>"
            return _FakeResponse(xml.encode())
        self.got.append(url)
        return _FakeResponse(self.body)


def test_pvol_nearest_in_time_is_downloaded(tmp_path):
    from datetime import UTC, datetime
    from knep import sources
    keys = [f"2026/01/01/SE/sehuv/PVOL/sehuv@20260101T{hm}@0@PVOL.h5" for hm in ("1200", "1205", "1210")]
    s3 = _FakeS3(keys)
    path = sources.fetch_pvol(s3, "sehuv", datetime(2026, 1, 1, 12, 6, tzinfo=UTC), tmp_path)
    assert path is not None and s3.got[-1].endswith("sehuv@20260101T1205@0@PVOL.h5")
    assert sources.fetch_pvol(s3, "sekrn", datetime(2026, 1, 1, 12, 6, tzinfo=UTC), tmp_path) is None
