"""knep.analys.a2 (A2T i src) mot experiments/analys/a2.py med system_params("A2T"), syntetiska data."""

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

from knep.analys import a2 as src

ROOT = Path(__file__).resolve().parents[1]
if "analys_a2" not in sys.modules:
    spec = importlib.util.spec_from_file_location("analys_a2", ROOT / "experiments/analys/a2.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["analys_a2"] = mod
    spec.loader.exec_module(mod)
exp = sys.modules["analys_a2"]
D = exp.D

H, W = 130, 170


def make_case(seed, n_st=50, wet_frac=0.4, nan_edge=True, svagt=True):
    """Mätare och A1 för en dag: A1 som mätarna gånger en slumpad faktor plus brus och svagt eko."""
    rng = np.random.default_rng(seed)
    r, c = rng.integers(0, H, n_st), rng.integers(0, W, n_st)
    q = np.where(rng.random((n_st, 96)) < wet_frac, rng.gamma(0.7, 0.8, (n_st, 96)), 0.0)
    h = q.reshape(n_st, 24, 4).sum(axis=2)
    st = np.arange(n_st)
    mq = D.Matare(np.repeat(st, 96), np.repeat(r, 96), np.repeat(c, 96), np.tile(np.arange(96), n_st), q.ravel())
    mh = D.Matare(np.repeat(st, 24), np.repeat(r, 24), np.repeat(c, 24), np.tile(np.arange(24), n_st), h.ravel())
    kv = rng.gamma(0.5, 0.2, (96, H, W)).astype(np.float32) * (rng.random((96, H, W)) < 0.3)
    if svagt:
        kv += np.float32(0.03) * (rng.random((96, H, W)) < 0.3)
    kv[mq.t, mq.r, mq.c] += (q.ravel() * rng.uniform(0.3, 1.2, q.size)).astype(np.float32)
    if nan_edge:
        kv[:, :12, :] = np.nan
        kv[:, :, -15:] = np.nan
    tm = kv.reshape(24, 4, H, W).sum(axis=1)
    rngkm = (40.0 + 2.0 * np.hypot(*np.mgrid[0:H, 0:W])).astype(np.float32)
    return mq, mh, kv, tm, rngkm


def run_exp(mq, mh, kv, tm, rngkm, hour):
    s = exp.A2(kv, tm, rngkm, exp.system_params("A2T"))
    q, h = s.falt(None, (mq, mh), hours=[hour])
    return h[hour], q[4 * hour:4 * hour + 4]


def run_src(mq, mh, kv, tm, rngkm, hour):
    win = (mh.t <= hour) & (mh.t > hour - src.TIMME["WIN"])
    fon = src.Matare(mh.r[win], mh.c[win], mh.mm[win], tm[mh.t[win], mh.r[win], mh.c[win]])
    th = mh.t == hour
    tim = src.Matare(mh.r[th], mh.c[th], mh.mm[th])
    kvm = [src.Matare(mq.r[mq.t == t], mq.c[mq.t == t], mq.mm[mq.t == t]) for t in range(4 * hour, 4 * hour + 4)]
    return src.A2T(rngkm).timme(tm[hour], kv[4 * hour:4 * hour + 4], fon, tim, kvm)


def test_parametrarna_ar_a2t():
    p = exp.system_params("A2T")
    for mine, res in ((src.TIMME, "timme"), (src.KVART, "kvart")):
        ref = {k: v for k, v in p[res].items() if k not in ("SVAG_TAK", "TORR2", "R_TORR2")}
        assert {k: v for k, v in mine.items() if k != "K_SVAG"} == {k: v for k, v in ref.items() if k != "K_SVAG"}
        assert mine["K_SVAG"] == ref.get("K_SVAG", 0.0)
        assert p[res].get("QC_T", 0.0) == 0 and p[res].get("TORR2", 0.0) == 0
    assert p["kvart"]["SVAG_TAK"] and src.STEG == exp.STEP and src.KMAX == exp.KMAX


@pytest.mark.parametrize("seed,hour,kw", [
    (0, 8, {}), (1, 14, {}), (2, 3, {}), (3, 20, {"nan_edge": False}),
    (4, 9, {"wet_frac": 0.0}),          # inga våta mätare
    (5, 10, {"n_st": 0}),               # inga mätare
    (6, 0, {"n_st": 3}),                # få mätare, fönstret bara en timme
    (7, 12, {"wet_frac": 0.9, "svagt": False}),
])
def test_samma_falt_som_experimentet(seed, hour, kw):
    case = make_case(seed, **kw)
    h_e, q_e = run_exp(*case, hour)
    h_s, q_s = run_src(*case, hour)
    assert h_s.dtype == np.float32 and q_s.shape == (4, H, W)
    assert np.array_equal(h_e, h_s, equal_nan=True)
    assert np.array_equal(q_e, q_s, equal_nan=True)


def test_utan_matare_kvot_ett_och_nan_bevaras():
    mq, mh, kv, tm, rngkm = make_case(11, n_st=0)
    h, q = run_src(mq, mh, kv, tm, rngkm, 5)
    ref = np.maximum(tm[5], 0)
    assert np.array_equal(np.isnan(h), np.isnan(tm[5]))
    assert np.allclose(h, ref, equal_nan=True)  # kvoten 1 utan mätare
    # kvarten: kvoten 1 och taket ändrar inget
    assert np.allclose(q, kv[20:24], equal_nan=True)


def test_torrmask_tak_och_inga_negativa():
    mq, mh, kv, tm, rngkm = make_case(12, wet_frac=0.0)
    hour = 7
    h, q = run_src(mq, mh, kv, tm, rngkm, hour)
    assert np.nanmin(h) >= 0 and np.nanmin(q) >= 0
    # alla mätare torra: där A1 är under TORR nära en mätare blir A2 0
    r0, c0 = mh.r[0], mh.c[0]
    a1 = kv[4 * hour:4 * hour + 4, r0, c0]
    for i in range(4):
        if np.isfinite(a1[i]) and a1[i] < src.KVART["TORR"]:
            assert q[i, r0, c0] == 0
    # taket: där 0 < A1 < K_SVAG är A2 högst A1
    a = kv[4 * hour:4 * hour + 4]
    svag = (a > 0) & (a < src.KVART["K_SVAG"])
    assert np.all(q[svag] <= a[svag])
    # torrmasken tar inte bort eko som radarn ser över TORR
    stark = np.isfinite(a) & (a >= 1.0)
    assert np.all(q[stark] > 0)


def test_nan_i_matarna_tas_bort():
    mq, mh, kv, tm, rngkm = make_case(13)
    hour = 9
    h0, q0 = run_src(mq, mh, kv, tm, rngkm, hour)
    mm = mq.mm.copy()
    extra = D.Matare(np.r_[mq.station, -1], np.r_[mq.r, 5], np.r_[mq.c, 5], np.r_[mq.t, 4 * hour], np.r_[mm, np.nan])
    h1, q1 = run_src(extra, mh, kv, tm, rngkm, hour)
    assert np.array_equal(q0, q1, equal_nan=True) and np.array_equal(h0, h1, equal_nan=True)
