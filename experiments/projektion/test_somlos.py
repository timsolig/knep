"""Somlos: blandningens varianter med standardvärdena är exakt seamless.blend."""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import somlos as S  # noqa: E402
from knep import seamless  # noqa: E402


def _fields(seed=0, shape=(120, 140)):
    rng = np.random.default_rng(seed)
    c = np.maximum(rng.gamma(0.3, 3.0, shape) - 0.5, 0).astype(np.float32)
    m = np.maximum(rng.gamma(0.5, 2.0, shape) - 0.5, 0).astype(np.float32)
    c[:10] = np.nan          # utanför radarn
    m[:, :5] = np.nan        # utanför MEPS
    return c, m


def test_default_equals_seamless_blend():
    c, m = _fields()
    for lead in (7.5, 67.5, 172.5, 292.5):
        p = S.Var().params(2.0)
        a = S.blend_v(c, m, lead, p, S.Var())
        b = seamless.blend(c, m, lead, seamless.Params())
        assert np.array_equal(np.isnan(a), np.isnan(b))
        np.testing.assert_allclose(np.nan_to_num(a), np.nan_to_num(b), rtol=0, atol=1e-6)


def test_three_scales_equal_two_when_same_weight():
    c, m = _fields(1)
    v = S.Var(t50_fine=60.0, fine_km=8.0)  # samma vikt för de minsta skalorna som för de små
    p = v.params(2.0)
    a, b = S.blend_v(c, m, 120.0, p, v), S.blend_v(c, m, 120.0, p, S.Var())
    np.testing.assert_allclose(np.nan_to_num(a), np.nan_to_num(b), atol=1e-4)


def test_top_weight_keeps_chain_tail():
    c, m = _fields(2)
    lead = 292.5
    p = S.Var().params(2.0)
    base = S.blend_v(c, m, lead, p, S.Var())
    top = S.blend_v(c, m, lead, p, S.Var(top_w=1.0, top_thr=5.0))
    ok = np.isfinite(c) & np.isfinite(m)
    # de högsta värdena blir kedjans, de låga är som förut
    assert np.isclose(np.nanmax(top[ok]), np.nanmax(c[ok]), rtol=1e-5)
    assert np.isclose(np.quantile(top[ok], 0.3), np.quantile(base[ok], 0.3), atol=1e-5)


def test_tag_roundtrip():
    assert S.Var().tag() == "bas"
    assert S.Var(top_w=0.5).tag() == "top_w=0.5"
