"""Hjälpfunktionerna i sammanslagning.py på syntetiska data."""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import sammanslagning as S  # noqa: E402


def test_interp_traffar_punkterna_och_gar_mot_medel():
    xy = np.array([[0.0, 0.0], [100.0, 0.0], [0.0, 100.0]])
    v = np.array([1.0, 3.0, 2.0])
    ut = S.interp(np.vstack([xy, [[1000.0, 1000.0]]]), xy, v, 40.0, nugget=1e-6)
    assert np.allclose(ut[:3], v, atol=1e-3) and abs(ut[3] - v.mean()) < 1e-3


def test_autokorr_l_langre_for_jamnare_falt():
    rng = np.random.default_rng(0)
    from scipy.ndimage import gaussian_filter

    brus = rng.gamma(0.5, 1.0, (200, 200))
    kort = S.autokorr_l(gaussian_filter(brus, 1))
    lang = S.autokorr_l(gaussian_filter(brus, 8))
    assert kort < lang and 10 <= kort <= 120


def test_sardrag_form():
    F0 = np.zeros((40, 30), np.float32)
    F0[10, 10] = 4.0
    X = S.sardrag(F0, np.full((40, 30), 50.0), None, 7)
    assert X.shape == (40, 30, 10) and X[10, 10, 0] == 2.0 and X[10, 10, 4] == 2.0
