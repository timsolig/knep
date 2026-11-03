"""Extrapoleringen med OpenCV ska ge samma resultat som pysteps (inget nätverk)."""

import numpy as np
from pysteps.extrapolation.semilagrangian import extrapolate

from knep import advect


def _case():
    rng = np.random.default_rng(1)
    h, w = 60, 80
    y, x = np.mgrid[:h, :w]
    field = (np.exp(-((x - 30) ** 2 + (y - 25) ** 2) / 60) * 20 + rng.random((h, w))).astype(np.float32)
    velocity = np.stack([1.2 + 0.3 * np.sin(y / 9), -0.4 + 0.2 * np.cos(x / 11)]).astype(np.float32)  # roterar lite
    return field, velocity


def test_matches_pysteps_bilinear_and_nearest():
    field, v = _case()
    for order in (1, 0):
        ref = extrapolate(field, v, 12, interp_order=order)
        new = advect.extrapolate(field, v, 12, orders=order)
        assert (np.isfinite(ref) == np.isfinite(new)).mean() > 0.999
        both = np.isfinite(ref) & np.isfinite(new)
        assert np.abs(ref - new)[both].max() < (1e-3 if order else 21)
        assert (np.abs(ref - new)[both] > 1e-3).mean() < 1e-3


def test_several_fields_share_the_motion_and_uneven_steps():
    field, v = _case()
    a, b = advect.extrapolate([field, 2 * field], v, [1, 2, 4, 7])
    assert a.shape == (4, 60, 80) and np.allclose(2 * a, b, equal_nan=True)
    ref = extrapolate(field, v, [1, 2, 4, 7])
    both = np.isfinite(ref) & np.isfinite(a)
    assert np.abs(ref - a)[both].max() < 1e-3
