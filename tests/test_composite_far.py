"""OPERA i zonen där de svenska radarernas stråle går högt (glappet nordväst om Kiruna, uppgift 0010)."""

import numpy as np
from pyproj import Transformer

from knep.analys import composite

GRID = dict(west=126648.4, north=7771252.88, res=2014.96, shape=(887, 471))
TO_GRID = Transformer.from_crs("EPSG:4326", "EPSG:3006", always_xy=True)


def _pixel(grid, lon, lat):
    x, y = TO_GRID.transform(lon, lat)
    return int((grid.north - y) // grid.res), int((x - grid.west) // grid.res)


def test_far_zone_covers_narvik_but_not_kiruna_or_the_south():
    grid = composite.TargetGrid(**GRID)
    far = composite.far_zone(grid, 3.0)
    assert far[_pixel(grid, 16.8, 68.5)]           # kring Narvik, cirka 170 km från Kiruna
    assert not far[_pixel(grid, 20.6, 67.8)]       # vid Kirunaradarn
    assert not far[_pixel(grid, 18.0, 59.3)]       # Stockholm
    # bortom räckvidden (Røst, cirka 360 km från Kiruna) är zonen falsk; där tar layer reserven
    assert not far[_pixel(grid, 12.1, 67.55)]
    assert far.sum() < composite.far_zone(grid, 2.0).sum()


def test_layer_far_takes_opera_only_in_the_zone_where_smhi_is_dry():
    h, w = 4, 6
    rain = np.array([[0, 0, 1, np.nan, 0, 0]] * h, np.float32)
    extra = np.full((h, w), 2.0, np.float32)
    extra[:, 4] = 0.05  # under min_extra
    far = np.zeros((h, w), bool)
    far[:2] = True
    src = np.where(np.isfinite(rain), composite.SOURCE_SMHI, composite.SOURCE_NONE).astype(np.uint8)
    out, s = composite.layer_far(rain, src, extra, composite.SOURCE_OPERA, far)
    # i zonen: torr SMHI med våt OPERA tas, SMHI med regn står kvar, NaN och svag OPERA rörs inte
    assert np.all(out[:2, [0, 1, 5]] == 2.0) and np.all(s[:2, [0, 1, 5]] == composite.SOURCE_OPERA)
    assert np.all(out[:2, 2] == 1.0) and np.all(s[:2, 2] == composite.SOURCE_SMHI)
    assert np.isnan(out[:2, 3]).all() and np.all(out[:2, 4] == 0)
    # utanför zonen är allt som förut
    np.testing.assert_array_equal(out[2:], rain[2:])
    np.testing.assert_array_equal(s[2:], src[2:])
    # mode="max" tar också där OPERA är större än SMHI:s regn
    out_m, _ = composite.layer_far(rain, src, extra, composite.SOURCE_OPERA, far, mode="max")
    assert np.all(out_m[:2, 2] == 2.0) and np.all(out_m[2:, 2] == 1.0)


def test_empty_zone_changes_nothing():
    rng = np.random.default_rng(1)
    rain = rng.gamma(0.3, 1.0, (30, 40)).astype(np.float32)
    rain[rain < 0.5] = 0
    extra = rng.gamma(0.5, 2.0, (30, 40)).astype(np.float32)
    src = np.zeros(rain.shape, np.uint8)
    out, s = composite.layer_far(rain, src, extra, composite.SOURCE_OPERA, np.zeros(rain.shape, bool))
    np.testing.assert_array_equal(out, rain)
    np.testing.assert_array_equal(s, src)


def _fake_sources(monkeypatch, grid):
    """SMHI torr överallt inom 240 km från en svensk radar, OPERA 1 mm/h överallt."""
    import rasterio
    from pyproj import CRS

    import knep.analys as analys
    from knep.analys import radar, sources

    rg = radar.Grid(CRS.from_epsg(3006), rasterio.Affine(grid.res, 0, grid.west, 0, -grid.res, grid.north), grid.shape)
    from knep.analys import bias
    beam = bias.beam_height(grid, {k: v for k, v in composite.RADARS.items() if k.startswith("se")})
    smhi = np.where(np.isfinite(beam), 0.0, np.nan).astype(np.float32)
    fetched = []
    monkeypatch.setattr(radar, "fetch", lambda t, cache, session: tmp_path_marker)
    monkeypatch.setattr(radar, "read_rain", lambda p: (smhi.copy(), rg))
    monkeypatch.setattr(sources, "fetch_opera", lambda s, t, c: fetched.append(t) or tmp_path_marker)
    monkeypatch.setattr(sources, "read_opera", lambda p, g: np.ones(grid.shape, np.float32))
    monkeypatch.setattr(sources, "volume_composite", lambda *a, **k: (None, None, []))
    return analys, smhi, fetched


tmp_path_marker = "ingen-fil"


def test_analyses_default_unchanged_and_option_takes_opera_in_zone(monkeypatch, tmp_path):
    from datetime import UTC, datetime
    grid = composite.TargetGrid(**GRID)
    analys, smhi, fetched = _fake_sources(monkeypatch, grid)
    t = [datetime(2026, 11, 7, 17, 0, tzinfo=UTC)]
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    out, *_ = analys._analyses(t, tmp_path, tmp_path / "a", None, True)
    np.testing.assert_array_equal(out[0], smhi)  # standard: inget hål, ingen OPERA, inget ändrat
    assert fetched == []
    out, _, _, src, _ = analys._analyses(t, tmp_path, tmp_path / "b", None, True, opera_fjarr=3.0)
    far = composite.far_zone(grid, 3.0)
    assert len(fetched) == 1
    assert np.all(out[0][far] == 1.0) and np.all(src[far] == composite.SOURCE_OPERA)
    inside = np.isfinite(smhi) & ~far
    assert np.all(out[0][inside] == 0.0) and np.all(src[inside] == composite.SOURCE_SMHI)
    # utanför SMHI:s täckning tar layer OPERA som förut
    assert np.all(out[0][~np.isfinite(smhi)] == 1.0)
