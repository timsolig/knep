"""Tester för utjamning_snabb.py på syntetiska fält."""

import sys
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import domare as D  # noqa: E402
import utjamning_snabb as S  # noqa: E402
from tak import smooth  # noqa: E402


def field(seed=0, shape=(96, 80)):
    rng = np.random.default_rng(seed)
    x = rng.gamma(0.4, 3.0, shape).astype(np.float32)
    x[rng.random(shape) < 0.6] = 0.0
    x[0, 0] = np.nan
    return x


def test_sigma_noll_ger_samma_faelt(monkeypatch):
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

    for name in ("S_noll", "S_ab_a", "S_ab_b", "S_ab_c"):
        s = getattr(S, name)()
        assert np.array_equal(s.forecast(datetime(2020, 1, 1, 12), Ctx()), fc, equal_nan=True)


def test_konstant_sigma_nara_ett_filter():
    x = field(1)
    out = S.blend_fast(x, np.full_like(x, 8.0), 2.0)
    ref = smooth(x, 4.0)
    ok = np.isfinite(ref)
    assert np.isnan(out[~ok]).all()
    assert np.abs(out[ok] - ref[ok]).max() < 0.08 * ref[ok].max()
    out16 = S.blend_fast(x, np.full_like(x, 16.0), 2.0)
    assert np.abs(out16[ok] - smooth(x, 8.0)[ok]).max() < 0.08 * ref[ok].max()


def test_halv_nivaa_ar_blandning():
    x = field(2)
    a = S.blend_fast(x, np.full_like(x, 4.0), 2.0)
    b = S.blend_fast(x, np.full_like(x, 8.0), 2.0)
    m = S.blend_fast(x, np.full_like(x, 6.0), 2.0)
    ok = np.isfinite(x)
    assert np.allclose(m[ok], (a[ok] + b[ok]) / 2, atol=1e-4)


def peak():
    x = np.zeros((64, 64), np.float32)
    x[30, 30] = 20.0
    return x


def test_skydd_a_ger_blockets_max():
    x = peak()
    g = S.blend_fast(x, np.full_like(x, 16.0), 2.0)
    assert g.max() < 5
    out = S.skydd_a(x, g, 8)
    assert out.max() >= 20.0 / 1.0 - 1e-3 or out.max() >= g.max() * S.MAXFAKTOR - 1e-3


def test_skydd_b_behaller_toppen():
    x = peak()
    g = S.blend_fast(x, np.full_like(x, 16.0), 2.0)
    out = S.skydd_b(x, g, 8)
    assert out[30, 30] == 20.0


def test_skydd_c_behaller_overskottet_och_massan():
    x = peak() + 0.5
    s = S.Snabb()
    s.skydd = "c"
    out = s.one(x, np.full_like(x, 16.0), 2.0, 8)
    assert out.max() >= 19.0
    assert abs(out.sum() - x.sum()) < 0.02 * x.sum()
