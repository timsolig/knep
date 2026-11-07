"""Filtret mot radarns artefakter (experiments/analys/filter.py) på syntetiska data, utan arkiv."""

import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("analys_filter", ROOT / "experiments/analys/filter.py")
F = importlib.util.module_from_spec(spec)
sys.modules["analys_filter"] = F
spec.loader.exec_module(F)

H, W = 240, 240
T = datetime(2023, 1, 4, 12, tzinfo=UTC)  # solen står högt nog i söder; inget soltest slår till


class Grid:
    shape = (H, W)


def _map():
    M = np.zeros((H, W), bool)
    M[100:103, 100:103] = True
    return M


def test_clutter_with_dry_surroundings_is_removed():
    rain = np.zeros((H, W), np.float32)
    rain[100:103, 100:103] = 5.0          # eko bara i klotterrutorna
    rain[0:5, 0:5] = np.nan               # utanför täckningen står kvar som NaN
    f = F.Filter(Grid(), kontext=0.03, ekrar=False, klotter=_map())
    out = f.apply(rain, T)
    assert out[100:103, 100:103].max() == 0.0
    assert np.isnan(out[0:5, 0:5]).all()
    assert f.removed == 9


def test_rain_on_clutter_cells_is_kept_when_it_rains_around():
    """Orografisk nederbörd på en misstänkt ruta: det regnar i omgivningen, så ekot står kvar."""
    rain = np.zeros((H, W), np.float32)
    rain[80:125, 80:125] = 2.0
    f = F.Filter(Grid(), kontext=0.03, ekrar=False, klotter=_map())
    out = f.apply(rain, T)
    np.testing.assert_array_equal(out, rain)


def test_echo_outside_map_is_never_touched_without_options():
    rng = np.random.default_rng(0)
    rain = np.where(rng.random((H, W)) < 0.002, 3.0, 0.0).astype(np.float32)  # isolerade prickar
    f = F.Filter(Grid(), kontext=0.5, ekrar=False, klotter=np.zeros((H, W), bool))
    np.testing.assert_array_equal(f.apply(rain, T), rain)
    f = F.Filter(Grid(), ekrar=False, prickar=True, klotter=np.zeros((H, W), bool))
    assert f.apply(rain, T).max() == 0.0  # med prickar tas de isolerade kantiga bort


def _geo(r0=120, c0=120):
    yy, xx = np.mgrid[0:H, 0:W]
    dy, dx = yy - r0, xx - c0
    d = np.hypot(dy, dx)
    az = (np.degrees(np.arctan2(dx, -dy)) + 360) % 360
    m = (d >= F.domare.np.float64(20)) & (d < 100)
    idx = np.flatnonzero(m)
    key = (az.ravel()[idx]).astype(int) % 360 * 4 + ((d.ravel()[idx] - 20) // 20).astype(int)
    return {"xx": (idx, key, np.flatnonzero(d.ravel() < 75), 60.0, 15.0)}, az, d


def test_fixed_spoke_is_removed_only_where_the_narrow_test_fires():
    geo, az, d = _geo()
    beam = (np.abs(az - 60.5) < 1.0) & (d >= 20) & (d < 100)
    rain = np.where(beam, 1.0, 0.0).astype(np.float32)
    f = F.Filter(Grid(), karta=False, ekrar=True, klotter=np.zeros((H, W), bool), fasta={"xx": [60]}, geo=geo)
    assert f.apply(rain, T).max() == 0.0
    # samma stråle men inte i listan: står kvar
    f = F.Filter(Grid(), karta=False, ekrar=True, klotter=np.zeros((H, W), bool), fasta={"xx": [200]}, geo=geo)
    np.testing.assert_array_equal(f.apply(rain, T), rain)
    # regn överallt (också åt sidorna): ingen smal stråle, inget tas bort
    wide = np.where((d >= 20) & (d < 100), 1.0, 0.0).astype(np.float32)
    f = F.Filter(Grid(), karta=False, ekrar=True, klotter=np.zeros((H, W), bool), fasta={"xx": [60]}, geo=geo)
    np.testing.assert_array_equal(f.apply(wide, T), wide)
