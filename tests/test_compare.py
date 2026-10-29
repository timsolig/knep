"""Jämförelsekällorna: OPeNDAP-avkodning, MEPS rutnät, timmarna för SNOW och ritningen (inget nätverk)."""

import json
from datetime import UTC, datetime, timedelta

import numpy as np
from pyproj import Transformer
from rasterio.transform import Affine

from knep import compare
from knep.radar import Grid

T0 = datetime(2026, 10, 29, 19, 10, tzinfo=UTC)


def _dods(*arrays):
    body = b"Dataset {\n} x;\n\nData:\n"
    for a in arrays:
        body += np.array([a.size, a.size], ">u4").tobytes() + a.astype(a.dtype.newbyteorder(">")).tobytes()
    return body


def test_dods_arrays_in_order():
    t = np.array([1, 2, 3], np.int32)
    v = np.array([0.5, 9.96921e36], np.float32)
    a, b = compare.dods_arrays(_dods(t, v), [">i4", ">f4"])
    assert a.tolist() == [1, 2, 3] and b[0] == 0.5 and b[1] > 1e30


def test_meps_grid_matches_snow_corners():
    # första och sista punkten i SNOW:s koordinatlista (sydväst och nordost)
    to = Transformer.from_crs(compare.MEPS_CRS, "EPSG:4326", always_xy=True)
    tr = compare.MEPS.transform
    h, w = compare.MEPS_SHAPE
    sw = to.transform(tr.c + tr.a / 2, tr.f + (h - 0.5) * tr.e)
    ne = to.transform(tr.c + (w - 0.5) * tr.a, tr.f + tr.e / 2)
    assert np.allclose(sw, (0.278280, 50.319616), atol=1e-3)
    assert ne[1] > 70 and ne[0] > 30


def test_snow_hours_cover_the_forecast():
    assert compare.snow_hours(T0) == [T0.replace(minute=0) + timedelta(hours=k) for k in (1, 2, 3)]
    assert len(compare.snow_hours(T0.replace(minute=0))) == 2


class _Session:
    """Svarar på MET Norges katalog, DDS och data med ett litet syntetiskt lopp."""

    def __init__(self, ref):
        self.ref, self.calls = ref, 0

    def get(self, url, params=None, timeout=None):
        class R:
            status_code = 200
            def raise_for_status(self): pass
        r = R()
        stamp = f"{self.ref:%Y%m%dT%H%M%S}Z"
        if url.endswith("catalog.xml"):
            r.text = f'<dataset name="yrwms-nordic.mos.pcappi-0-rr.x.nordiclcc-1000.{stamp}.nc"/>'
        elif url.endswith(".dds"):
            r.text = "Float32 Xc[Xc = 40];\nFloat32 Yc[Yc = 30];"
        elif "time,Xc" in url:
            t = np.array([self.ref.timestamp() + 300 * k for k in range(24)], np.int32)
            r.content = _dods(t, np.array([0.0, 1000.0], np.float32), np.array([100000.0, 99000.0], np.float32))
        else:
            self.calls += 1
            r.content = _dods(np.full(24 * 8 * 10, 3.0, np.float32))
        return r


def test_met_reuses_a_recent_run(tmp_path):
    s = _Session(T0)
    e = compare.met(tmp_path, s, T0)
    assert e["reference"] == "2026-10-29T19:10:00Z" and len(e["frames"]) == 24 and e["resolution_km"] == 4
    assert all((tmp_path / f["file"]).exists() for f in e["frames"] + e["frames15"] + e["frames60"])
    s.ref = T0 + timedelta(minutes=10)  # nytt lopp, men yngre än MET_EVERY: inget nytt hämtas
    assert compare.met(tmp_path, s, T0)["reference"] == e["reference"] and s.calls == 1
    s.ref = T0 + timedelta(minutes=15)
    assert compare.met(tmp_path, s, T0)["reference"] == "2026-10-29T19:25:00Z" and s.calls == 2
    assert json.loads((tmp_path / "met" / "met.json").read_text())["reference"] == "2026-10-29T19:25:00Z"


def test_snow_renders_hours_and_skips_missing(tmp_path, monkeypatch):
    field = np.zeros(compare.MEPS_SHAPE, np.float32)
    field[-100:, :] = 2.0  # norr uppåt: regn längst i norr
    monkeypatch.setattr(compare, "snow_field", lambda s, end: None if end.hour == 22 else (field, "2026-10-29T19:00:00Z"))
    e = compare.snow(tmp_path, None, T0)
    assert [f["time"] for f in e["frames60"]] == ["2026-10-29T20:00:00Z", "2026-10-29T21:00:00Z"]
    assert all((tmp_path / f["file"]).exists() for f in e["frames60"])


def test_update_survives_a_failing_source(tmp_path, monkeypatch):
    import requests

    def boom(*a):
        raise requests.ConnectionError("nere")
    monkeypatch.setattr(compare, "met", boom)
    monkeypatch.setattr(compare, "snow", lambda *a: {"frames60": []})
    res = compare.update(tmp_path, None, T0)
    assert "met" not in res and "snow" in res and len(res["bounds"]) == 2


def test_renderer_accepts_lambert_grids():
    g = Grid(compare.MET_CRS, Affine(4000, 0, -796000, 0, -4000, 1125000), (534, 424))
    (s, w), (n, e) = compare.render.Renderer(g).bounds
    assert 50 < s < 56 and 70 < n < 76 and w < 0 and e > 30
