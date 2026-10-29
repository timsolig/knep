"""Extremkalibreringen: omskalningen ger rätt antal pixlar över trösklarna utan att ändra läget."""

import numpy as np

from nowcast import extremes


def _field():
    rng = np.random.default_rng(3)
    c = rng.gamma(0.6, 2.0, (120, 150)).astype(np.float32)
    c[c < 0.1] = 0.0
    c[:5] = np.nan
    return c


def test_calibrate_tail_hits_the_expected_counts_and_keeps_ranks():
    c = _field()
    expected = np.zeros(len(extremes.THR))
    expected[extremes.THR.index(5.0)] = 900
    expected[extremes.THR.index(10.0)] = 80
    out = extremes.calibrate_tail(c, expected)
    assert abs(np.nansum(out >= 5.0) - 900) <= 2
    assert abs(np.nansum(out >= 10.0) - 80) <= 2
    ok = np.isfinite(c) & (c >= 0.1)
    order_in, order_out = np.argsort(c[ok], kind="stable"), np.argsort(out[ok], kind="stable")
    assert np.array_equal(c[ok][order_in] > 0, out[ok][order_in] > 0)
    assert np.corrcoef(order_in.argsort(), order_out.argsort())[0, 1] > 0.999
    # under 1 mm/h ändras inget, och NaN förblir NaN
    low = ok & (c < 0.99)
    assert np.allclose(out[low], c[low]) and np.isnan(out[:5]).all()


def test_half_weight_lands_between():
    c = _field()
    own10 = int(np.nansum(c >= 10.0))
    expected = np.zeros(len(extremes.THR))
    expected[extremes.THR.index(5.0)] = np.nansum(c >= 5.0)
    expected[extremes.THR.index(10.0)] = own10 * 4
    full = np.nansum(extremes.calibrate_tail(c, expected) >= 10.0)
    half = np.nansum(extremes.calibrate_tail(c, expected, weight=0.5) >= 10.0)
    assert own10 < half < full


def test_features_have_the_trained_layout():
    c = _field()
    n = 4
    t15 = np.zeros((n,) + c.shape, np.float32)
    f = extremes.features(c, 2, t15, t15, np.zeros(c.shape, np.float32), np.ones(c.shape, np.float32), (5.0, 10.0, 0.1))
    assert f.shape == (len(extremes.FEATURES),) + c.shape
    assert np.all(f[extremes.FEATURES.index("lead")] == 10)
    assert np.all(f[extremes.FEATURES.index("max15")] >= f[extremes.FEATURES.index("db")])
