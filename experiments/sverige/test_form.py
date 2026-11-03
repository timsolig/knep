"""Formmåtten i form.py på syntetiska fält: tecken och storlek åt rätt håll."""

import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import form  # noqa: E402

H, W = 300, 300


def _field(seed=0):
    rng = np.random.default_rng(seed)
    noise = cv2.GaussianBlur(rng.standard_normal((H, W)).astype(np.float32), (0, 0), 4)
    noise /= noise.std()
    return np.where(noise > 0.6, np.exp(1.5 * (noise - 0.6)) - 0.5, 0).clip(0).astype(np.float32) * 4


def _all(f, o):
    m = np.ones((H, W), bool)
    ts = form.tiles(m, o)
    region = (o >= 0.1) | (f >= 0.1)
    return form.shape_metrics(f, o, m, ts, form.spectrum(o, ts), region)


def test_identical_field_gives_zero():
    o = _field()
    r = _all(o.copy(), o)
    assert r and all(abs(v) < 1e-9 for v in r.values()), r


def test_smoothing_shows_as_lost_small_scales_and_positive_structure():
    o = _field()
    f = cv2.GaussianBlur(o, (0, 0), 3)
    f *= o.sum() / f.sum()
    r = _all(f, o)
    assert r["spek_4_8"] < -1.0 and r["spek_8_16"] < r["spek_64_128"] + 1e-9
    assert r["S"] > 0.2 and abs(r["A"]) < 0.01
    assert r["kanter"] < -0.2
    assert r["q99.9"] < 0


def test_shift_moves_location_not_structure():
    o = np.zeros((H, W), np.float32)
    o[40:140, 40:140] = _field(1)[40:140, 40:140]   # ett regnområde, flyttat 60 km utan omslag
    f = np.zeros_like(o)
    f[70:170, 40:140] = o[40:140, 40:140]
    r = _all(f, o)
    assert r["L"] > 0.03 and abs(r["S"]) < 0.15 and abs(r["spek_4_8"]) < 0.2


def test_temporal_and_consistency():
    o = [_field(k) for k in range(4)]
    still = [o[0]] * 4
    m = np.ones((H, W), bool)
    assert all(v < -5 for v in form.temporal(still, o, m))
    assert form.jump(o[0], o[0], m) == 0 and form.jump(o[0], o[1], m) > 0.5
    assert form.fss(o[0], o[0], m) == 1.0
