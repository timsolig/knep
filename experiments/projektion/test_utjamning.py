"""Tester för utjamning.py på syntetiska fält: sigma = 0 ger exakt kedjans fält, blandningen följer ett filter."""

import sys
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import domare as D  # noqa: E402
import utjamning as U  # noqa: E402
from tak import smooth  # noqa: E402


def field(seed=0, shape=(80, 70)):
    rng = np.random.default_rng(seed)
    x = rng.gamma(0.4, 3.0, shape).astype(np.float32)
    x[rng.random(shape) < 0.6] = 0.0
    x[0, 0] = np.nan
    return x


def test_sigma_noll_ger_samma_faelt():
    x = field()
    out = U.blend_levels(x, np.zeros_like(x), 2.0)
    assert np.array_equal(out, x, equal_nan=True)


def test_konstant_sigma_ar_ett_filter():
    x = field(1)
    out = U.blend_levels(x, np.full_like(x, 8.0), 2.0)
    assert np.allclose(out, smooth(x, 4.0), equal_nan=True, atol=1e-5)


def test_forecast_med_noll_ar_kedjan(monkeypatch):
    fc = np.stack([field(k) for k in range(D.NQ)])
    monkeypatch.setattr(D.KedjaOm, "forecast", lambda self, t, ctx: fc)

    class Ctx:
        res = 2

        def motion(self, t):
            return np.zeros((2,) + fc.shape[1:], np.float32)

        def history(self, t, n=12):
            return None

        def frame(self, t):
            return None

    for name in ("U_noll", "U_a1"):
        s = getattr(U, name)()
        assert np.array_equal(s.forecast(datetime(2020, 1, 1, 12), Ctx()), fc, equal_nan=True)


def test_toppskydd():
    x = np.zeros((60, 60), np.float32)
    x[30, 30] = 20.0
    out = U.blend_levels(x, np.full_like(x, 16.0), 2.0)
    assert out.max() < 5
    assert max(out.max(), 0.8 * x.max()) == 16.0
