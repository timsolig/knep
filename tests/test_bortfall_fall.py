"""Bortfallsfallen (experiments/bortfall/fall.py) på syntetiska data, utan nätverk och utan /data."""

import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest
from rasterio.transform import from_origin

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments" / "bortfall"))
fall = pytest.importorskip("fall")

T0 = datetime(2024, 8, 9, 12, 0, tzinfo=UTC)


def _dist():
    """Tre radarer på en linje, 200 km mellan dem, på ett rutnät med 10 km."""
    tr = from_origin(0, 100_000, 10_000, 10_000)
    X, Y = fall.centres(tr, (20, 80))
    xy = {"sea": (100_000.0, 0.0), "seb": (300_000.0, 0.0), "noc": (500_000.0, 0.0)}
    return fall.distances_km(X, Y, xy), X


def test_hole_only_where_no_other_radar_reaches():
    dist, X = _dist()
    cov = np.ones(X.shape, bool)
    hole = fall.hole_mask(dist, ["sea"], cov, range_km=240)
    # inom 240 km från sea och längre än 240 km från seb (x < 60 km på linjen genom radarerna)
    assert hole.any()
    assert (X[10][hole[10]] < 60_000).all() and hole[10, 0]
    assert (dist["seb"][hole] > 240).all() and (dist["sea"][hole] <= 240).all()
    # båda svenska släckta: hålet växer men når inte inom räckvidd från noc
    both = fall.hole_mask(dist, ["sea", "seb"], cov, range_km=240)
    assert both.sum() > hole.sum() and (dist["noc"][both] > 240).all()
    # bara där radarn brukar ha data
    cov[:, :3] = False
    assert not fall.hole_mask(dist, ["sea"], cov, range_km=240)[:, :3].any()


def test_nearest_working_radar_ignores_switched_off():
    dist, _ = _dist()
    near = fall.nearest_working_km(dist, ["sea"])
    assert np.allclose(near, np.minimum(dist["seb"], dist["noc"]))


def test_unique_holes_drops_small_and_duplicates():
    a = np.zeros((50, 50), bool)
    a[10:40, 10:40] = True
    b = a.copy()
    b[10, 41] = True  # nästan samma hål med fler radarer
    small = np.zeros_like(a)
    small[0, 0] = True
    kept = fall.unique_holes({("x", "y"): b, ("x",): a, ("z",): small}, min_px=10)
    assert list(kept) == [("x",)]


def test_eligible_starts_need_whole_window():
    minutes = 30
    times = [T0 - timedelta(minutes=fall.UPPVARMNING) + k * timedelta(minutes=5) for k in range(200)]
    present = set(times)
    assert fall.eligible_starts(present, [T0], minutes) == [T0]
    gap = T0 + timedelta(minutes=minutes + fall.EFTER)  # sista bilden som behövs
    assert fall.eligible_starts(present - {gap}, [T0], minutes) == []
    assert fall.eligible_starts(present - {T0 - timedelta(minutes=fall.UPPVARMNING)}, [T0], minutes) == []


def test_wet_enough_thresholds():
    hole = np.ones((20, 20), bool)
    rain = np.zeros((20, 20), np.float32)
    rain.flat[:99] = 1.0
    assert not fall.wet_enough(rain, hole)  # 99 pixlar < 100
    rain.flat[:120] = 1.0
    assert fall.wet_enough(rain, hole)  # 120 pixlar och 30 %
    rain[:] = np.nan
    assert not fall.wet_enough(rain, hole)


def test_choose_is_deterministic_and_varied():
    combos = {(f"se{i}",): np.ones((2, 2), bool) for i in range(6)}
    starts = [T0 + timedelta(minutes=15 * k) for k in range(20)]
    wet = {(c, t): True for c in combos for t in starts}
    present = {T0 + timedelta(minutes=5 * k) for k in range(-20, 400)}
    a = fall.choose(date(2024, 8, 9), "traning", combos, wet, present, per_day=5)
    b = fall.choose(date(2024, 8, 9), "traning", combos, wet, present, per_day=5)
    assert a == b and len(a) == 5
    assert len({c for c, _, _ in a}) == 5  # olika kombinationer
    assert sorted(m for _, _, m in a) == sorted(fall.LANGDER)  # alla längder en gång
    for combo, t0, m in a:
        assert wet[(combo, t0)]
    c = fall.choose(date(2024, 8, 9), "validering", combos, wet, present, per_day=5)
    assert c != a  # eget frö per del


def test_choose_skips_dry_combos():
    combos = {("sea",): np.ones((2, 2), bool), ("seb",): np.ones((2, 2), bool)}
    wet = {(("sea",), T0): False, (("seb",), T0): True}
    present = {T0 + timedelta(minutes=5 * k) for k in range(-20, 400)}
    out = fall.choose(date(2024, 8, 9), "traning", combos, wet, present, per_day=4)
    assert [c for c, _, _ in out] == [("seb",)]


def test_meps_hours_cover_window():
    hours = fall.meps_hours(datetime(2024, 8, 9, 11, 25, tzinfo=UTC), datetime(2024, 8, 9, 13, 0, tzinfo=UTC))
    assert [h.hour for h in hours] == [12, 13]
    hours = fall.meps_hours(datetime(2024, 8, 9, 11, 0, tzinfo=UTC), datetime(2024, 8, 9, 12, 5, tzinfo=UTC))
    assert [h.hour for h in hours] == [11, 12, 13]


def test_lut_matches_radar_coding():
    from knep import radar

    raw = np.array([0, 1, 100, 200, 254, 255], np.uint8)
    rain = fall.to_rain(raw)
    dbz = raw.astype(np.float32) * radar.GAIN + radar.OFFSET
    ref = (10 ** (dbz / 10) / radar.ZR_A) ** (1 / radar.ZR_B)
    assert rain[0] == 0 and np.isnan(rain[-1])
    assert np.allclose(rain[1:-1], ref[1:-1], rtol=1e-5)


def test_gauges_in_crop_and_hole():
    tr = from_origin(0, 100_000, 2_000, 2_000)
    from pyproj import Transformer

    back = Transformer.from_crs("EPSG:3006", "EPSG:4326", always_xy=True)
    # tre mätare: i hålet, i utsnittet utanför hålet, utanför utsnittet
    pts = [(21_000, 79_000), (41_000, 79_000), (401_000, 79_000)]
    lon, lat = zip(*(back.transform(x, y) for x, y in pts))
    t = int(T0.timestamp())
    g = {"station": np.array([1, 2, 3]), "lat": np.array(lat, np.float32), "lon": np.array(lon, np.float32),
         "time": np.array([t, t, t]), "mm": np.array([1.0, 2.0, 3.0], np.float32)}
    box = (5, 15, 5, 25)  # rader 5..15, kolumner 5..25 i rutnätet
    hole = np.zeros((10, 20), bool)
    hole[:, :8] = True  # kolumn 5..12, x 10..26 km
    out = fall.gauges_in(g, tr, box, hole, T0 - timedelta(hours=1), T0)
    assert out["station"].tolist() == [1, 2]
    assert out["i_hal"].tolist() == [True, False]
    assert out["rad"].tolist() == [5, 5] and out["kol"].tolist() == [5, 15]
    # utanför tidsfönstret
    assert len(fall.gauges_in(g, tr, box, hole, T0, T0 + timedelta(hours=1))["station"]) == 0


def test_crop_box_margin_and_edges():
    m = np.zeros((100, 100), bool)
    m[40:50, 2:5] = True
    assert fall.crop_box(m, margin=10) == (30, 60, 0, 15)


def test_test_part_is_refused():
    with pytest.raises(ValueError):
        fall.days_for("test")
