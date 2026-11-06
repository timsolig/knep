"""knep.analys.klotter: filtret mot fast klotter, avstängt utan karta."""

import numpy as np

from knep.analys import klotter


def _map(shape=(200, 200)):
    m = np.zeros(shape, bool)
    m[90:93, 90:93] = True
    return m


def test_without_map_nothing_changes():
    rain = np.ones((50, 50), np.float32)
    assert klotter.rensa(rain, None) is rain
    assert klotter.load(None, (50, 50)) is None


def test_isolated_clutter_is_removed_and_nan_kept():
    rain = np.zeros((200, 200), np.float32)
    rain[90:93, 90:93] = 4.0
    rain[:3, :3] = np.nan
    out = klotter.rensa(rain, _map())
    assert out[90:93, 90:93].max() == 0.0
    assert np.isnan(out[:3, :3]).all()
    assert rain[90, 90] == 4.0  # indata ändras inte


def test_rain_around_suspected_cells_is_kept():
    rain = np.zeros((200, 200), np.float32)
    rain[70:115, 70:115] = 1.5
    np.testing.assert_array_equal(klotter.rensa(rain, _map()), rain)


def test_load_checks_shape(tmp_path):
    p = tmp_path / "k.npz"
    np.savez_compressed(p, klotter=_map())
    assert klotter.load(p, (200, 200)).sum() == 9
    assert klotter.load(p, (100, 100)) is None
