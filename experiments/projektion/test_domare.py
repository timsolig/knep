"""Tester för domarens mått på syntetiska fält (inget nätverk, ingen data på disk)."""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))
import domare as D  # noqa: E402


def field(seed=0, shape=(120, 90)):
    rng = np.random.default_rng(seed)
    x = rng.gamma(0.4, 3.0, shape).astype(np.float32)
    x[rng.random(shape) < 0.6] = 0.0
    return x


def test_hist_quantile_matches_percentile():
    x = field(1, (300, 300))
    w = x[x >= D.WET]
    h = D.wet_hist(x)
    for p in (50, 99, 99.9):
        assert D.hist_quantile(h, p) == pytest.approx(np.percentile(w, p), rel=0.03)
    assert np.isnan(D.hist_quantile(np.zeros_like(h), 99))


def test_contingency_and_sedi():
    o = np.array([[10, 10, 0, 0]], np.float32)
    f = np.array([[10, 0, 10, 0]], np.float32)
    m = np.ones_like(o, bool)
    ct = D.contingency(f, o, m, 5.0)
    assert ct.tolist() == [1, 1, 1, 1]
    # perfekt prognos: SEDI nära 1; slumpmässig (H = F): SEDI 0
    assert D._sedi(np.array([[50.0, 0, 0, 50]]))[0] > 0.99
    assert abs(D._sedi(np.array([[25.0, 25, 25, 25]]))[0]) < 1e-9


def test_fss_perfect_and_disjoint():
    o = np.zeros((40, 40), np.float32)
    o[10:15, 10:15] = 8
    m = np.ones_like(o, bool)
    num, den = D.fss_sums(o, o, m, 5.0, 5)
    assert num == 0 and den > 0
    f = np.zeros_like(o)
    f[30:35, 30:35] = 8
    num, den = D.fss_sums(f, o, m, 5.0, 3)
    assert 1 - num / den == pytest.approx(0.0)


def test_block_max_only_full_blocks():
    x = np.arange(36, dtype=np.float32).reshape(6, 6)
    m = np.ones_like(x, bool)
    m[0, 0] = False
    b = D.block_max(x, m, 3)
    assert sorted(b.tolist()) == [17.0, 32.0, 35.0]


def test_coarsen_nan():
    x = np.ones((5, 4), np.float32)
    x[0, 0] = np.nan
    c = D.coarsen(x, 2)
    assert c.shape == (2, 2) and np.isnan(c[0, 0]) and c[1, 1] == 1


def test_spectrum_smoothing_is_negative():
    from scipy.ndimage import gaussian_filter

    o = field(2, (300, 300)) * 3
    m = np.ones_like(o, bool)
    sp = D.Spectrum(2.0)
    ts = D.spectrum_tiles(m, o, sp.tile)
    assert ts
    po, pf = sp(o, ts), sp(gaussian_filter(o, 2.0), ts)
    assert np.all(D._lr(pf, po) < -0.5)
    assert np.all(D._lr(sp(o, ts), po) == 0)


def acc_for(f_fn, days=3, res=2.0):
    out = {}
    for d in range(days):
        a = D.Acc(res)
        for i in range(len(D.LEADS)):
            o = field(10 * d + i, (300, 300)) * 4
            m = np.ones_like(o, bool)
            m[:5] = False
            a.add(i, f_fn(o), o, m, old=o)
        out[f"d{d}"] = a.d | {"issues": np.array(1), "seconds": np.array(1.0)}
    return out


def test_perfect_forecast_scores():
    per = acc_for(lambda o: o)
    s = D.scores(per, list(per))
    for k in ("q99", "q99.9", "yta5", "yta10", "volym", "blockmax_q50", "blockmax_q90", "form4_8", "form8_16"):
        assert np.allclose(s[k], 0, atol=1e-6), k
    for k in ("fss1_30", "fss5_10", "fss10_30", "csi1", "csi5"):
        assert np.allclose(s[k], 1), k
    assert np.allclose(s["hopp"], 0)


def test_inflated_peaks_show_in_conservation_and_compare():
    good = acc_for(lambda o: o)
    big = acc_for(lambda o: o * 1.5)
    days = list(good)
    c = D.compare(big, good, days, nboot=50)
    assert np.all(c["q99"]["system"] > 0.3)
    assert np.all(c["q99"]["diff"] > 0)           # sämre konservering
    assert np.all(c["volym"]["lo"] > 0)
    assert np.all(c["csi1"]["diff"] > 0)          # falsklarm vid 1 mm/h
    v, worse = D.verdict(c)
    assert v == "inte bättre" and worse
    same = D.compare(good, good, days, nboot=20)
    assert np.allclose(np.nan_to_num(same["fss5_30"]["diff"]), 0)


def test_mark_min_log_difference():
    one = np.array([0.0])
    tiny = {"kind": "kons", "lo": one - 0.008, "hi": one - 0.002}
    assert D.mark(tiny, 0) == ""                      # under MIN_LOG räknas inte, åt något håll
    assert D.mark({"kind": "spärr|", "lo": one + 0.002, "hi": one + 0.008}, 0) == ""
    assert D.mark({"kind": "kons", "lo": one - 0.05, "hi": one - 0.02}, 0) == "*"
    assert D.mark({"kind": "spärr|", "lo": one + 0.02, "hi": one + 0.05}, 0) == "!"
    # poängen (FSS, CSI) har ingen tolerans: en säker försämring räknas
    assert D.mark({"kind": "träff", "lo": one + 0.001, "hi": one + 0.002}, 0) == "!"


def test_quarters_shape():
    x = np.arange(60 * 4, dtype=np.float32).reshape(60, 2, 2)
    q = D.quarters(x)
    assert q.shape == (20, 2, 2) and q[0, 0, 0] == x[:3, 0, 0].mean()


class FakeCtx:
    def __init__(self, frames, t0):
        self.frames, self.t0 = frames, t0

    def frame(self, t):
        return self.frames[-1]

    def history(self, t):
        return self.frames

    def motion(self, t):
        return np.stack([np.full(self.frames.shape[1:], 1.3), np.full(self.frames.shape[1:], -0.7)])


def test_warm_equals_chain_run():
    from datetime import UTC, datetime

    rng = np.random.default_rng(3)
    frames = np.stack([field(k, (60, 80)) for k in range(7)])
    frames[:, :3, :5] = np.nan
    t = datetime(2024, 7, 1, 12, tzinfo=UTC)
    ctx = FakeCtx(frames, t)
    for match in (True, False):
        s = D.KedjaOm(match=match)
        s.reset()
        s.observe(t, ctx)
        ref = D.model.State()
        D.model.Chain(None, match=match).run(frames, t, 6, ref, motion=ctx.motion(t))
        assert list(s.state.fc30) == list(ref.fc30)
        k = next(iter(ref.fc30))
        np.testing.assert_array_equal(np.nan_to_num(s.state.fc30[k], nan=-1), np.nan_to_num(ref.fc30[k], nan=-1))
    assert rng is not None


def test_modes_never_contain_test_days():
    test = {d["day"] for d in D.load_days() if d["part"] == "test"}
    for mode in D.LÄGEN:
        assert not test & set(D.LÄGEN[mode]["days"]())
