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


def _run(cls, corr, kmax_env=None):
    s = cls(RD())
    s.corr = corr
    s.frames()
    return s._frames, RD().rain


def test_g0_ignores_tail():
    out, raw = _run(M.A0B_g0, _corr(np.log(2.0), gamma=-0.2))
    ok = np.isfinite(raw[0])
    assert np.allclose(out[0][ok], 2 * raw[0][ok], rtol=1e-5)


def test_g0_factor_one_is_a0():
    base = M.domare.A0(RD()).frames().copy()
    out, _ = _run(M.A0B_g0, _corr(0.0, gamma=-0.2))
    assert np.array_equal(base, out, equal_nan=True)


def test_ton_leaves_weak_echo_untouched():
    out, raw = _run(M.A0B_ton, _corr(np.log(2.0)))
    ok = np.isfinite(raw[0])
    weak = ok & (raw[0] <= 0.3)
    strong = ok & (raw[0] >= 1.0)
    assert weak.any() and strong.any()
    assert np.array_equal(out[0][weak], raw[0][weak])
    assert np.allclose(out[0][strong], 2 * raw[0][strong], rtol=1e-5)
    mid = ok & (raw[0] > 0.3) & (raw[0] < 1.0)
    assert np.all(out[0][mid] > raw[0][mid]) and np.all(out[0][mid] < 2 * raw[0][mid])


def test_ton_factor_one_is_a0():
    base = M.domare.A0(RD()).frames().copy()
    for cls in (M.A0B_ton, M.A0B_ton2):
        out, _ = _run(cls, _corr(0.0))
        assert np.array_equal(base, out, equal_nan=True)


def test_ton2_threshold():
    out, raw = _run(M.A0B_ton2, _corr(np.log(2.0)))
    ok = np.isfinite(raw[0])
    weak = ok & (raw[0] <= 0.5)
    strong = ok & (raw[0] >= 2.0)
    assert np.array_equal(out[0][weak], raw[0][weak])
    assert np.allclose(out[0][strong], 2 * raw[0][strong], rtol=1e-5)


def test_k2_clips_factor(monkeypatch):
    monkeypatch.setenv("KNEP_A0B_K2_TON", "")
    out, raw = _run(M.A0B_k2, _corr(np.log(5.0)))
    ok = np.isfinite(raw[0])
    assert np.allclose(out[0][ok], 2 * raw[0][ok], rtol=1e-5)
    out, _ = _run(M.A0B_k2, _corr(np.log(1.5)))
    assert np.allclose(out[0][ok], 1.5 * raw[0][ok], rtol=1e-5)


def test_k2_with_ton(monkeypatch):
    monkeypatch.setenv("KNEP_A0B_K2_TON", "0.3,1")
    out, raw = _run(M.A0B_k2, _corr(np.log(5.0)))
    ok = np.isfinite(raw[0])
    weak = ok & (raw[0] <= 0.3)
    assert np.array_equal(out[0][weak], raw[0][weak])
    strong = ok & (raw[0] >= 1.0)
    assert np.allclose(out[0][strong], 2 * raw[0][strong], rtol=1e-5)


def test_registered():
    for n in ("A0B_g0", "A0B_ton", "A0B_ton2", "A0B_k2"):
        assert M.domare.SYSTEMS[n].namn == n
    assert M.domare.SYSTEMS["A0B"] is M.A0B
