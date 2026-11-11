"""A0B (experiments/analys/a0b.py): med faktorn 1 överallt och utan svans blir det exakt A0."""

import importlib.util
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("analys_a0b", ROOT / "experiments/analys/a0b.py")
M = importlib.util.module_from_spec(spec)
sys.modules["analys_a0b"] = M
spec.loader.exec_module(M)

H, W = 40, 50


class Grid:
    shape = (H, W)


class RD:
    PRE = 6

    def __init__(self, seed=0):
        rng = np.random.default_rng(seed)
        t0 = datetime(2024, 6, 1, tzinfo=UTC)
        self.times = [t0 + timedelta(minutes=5 * k) for k in range(30)]
        r = rng.gamma(0.5, 2.0, (30, H, W)).astype(np.float32)
        r[rng.random((30, H, W)) < 0.3] = np.nan
        self.rain = r
        self.have = np.ones(30, bool)
        self.grid = Grid()

    def sparse_motion(self):
        return None

    def motion_at(self, k):
        return np.zeros((2, H, W), np.float32)


def _corr(coef0=0.0, gamma=0.0):
    coef = np.zeros((12, 3))
    coef[:, 0] = coef0
    return M.bias.Correction(coef, np.zeros((H, W), np.float32), np.full((H, W), 1.0, np.float32), gamma=gamma)


def test_factor_one_gives_exactly_a0():
    a0, a0b = RD(), RD()
    base = M.domare.A0(a0).frames().copy()
    sys_b = M.A0B(a0b)
    sys_b.corr = _corr()
    out = sys_b.frames()
    assert np.array_equal(base, out, equal_nan=True)


def test_factor_two_doubles_before_fill():
    rd = RD()
    s = M.A0B(rd)
    s.corr = _corr(np.log(2.0))
    raw = RD().rain.copy()
    s.frames()
    # utfyllnaden rör bara luckor; där originalet har eko ska värdet vara dubbelt
    ok = np.isfinite(raw[0])
    assert np.allclose(s._frames[0][ok], 2 * raw[0][ok], rtol=1e-5)


def test_registered():
    assert M.domare.SYSTEMS["A0B"] is M.A0B
