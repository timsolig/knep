"""A2 (experiments/analys/a2.py) på syntetiska data, utan nätverk och arkiv."""

import importlib.util
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("analys_a2", ROOT / "experiments/analys/a2.py")
a2 = importlib.util.module_from_spec(spec)
sys.modules["analys_a2"] = a2
spec.loader.exec_module(a2)
domare = a2.D

H, W = 150, 150


def make_dag(seed=0, n_st=40, wet_frac=0.4):
    """Stationer på slumpade rutor med kvarts- och timvärden som stämmer med varandra."""
    rng = np.random.default_rng(seed)
    r, c = rng.integers(0, H, n_st), rng.integers(0, W, n_st)
    q = np.where(rng.random((n_st, 96)) < wet_frac, rng.gamma(1.0, 1.0, (n_st, 96)), 0.0)
    h = q.reshape(n_st, 24, 4).sum(axis=2)
    st = np.arange(n_st)
    kv = domare.Matare(np.repeat(st, 96), np.repeat(r, 96), np.repeat(c, 96), np.tile(np.arange(96), n_st), q.ravel())
    tm = domare.Matare(np.repeat(st, 24), np.repeat(r, 24), np.repeat(c, 24), np.tile(np.arange(24), n_st), h.ravel())
    return domare.Dag("2000-01-01", (H, W), kv, tm, np.zeros((H, W), np.float32), None)


def _fields(dag, scale=1.0):
    """A1 som stämmer med mätarna gånger scale i mätarnas rutor, 0 annars."""
    kv = np.zeros((96, H, W), np.float32)
    tm = np.zeros((24, H, W), np.float32)
    kv[dag.kvart.t, dag.kvart.r, dag.kvart.c] = dag.kvart.mm * scale
    tm[dag.timme.t, dag.timme.r, dag.timme.c] = dag.timme.mm * scale
    return kv, tm


def test_ratio_is_one_without_gauges_and_shrinks():
    p = dict(a2.PARAMS["timme"])
    xy = np.zeros((3, 2))
    assert np.allclose(a2.stor_kvot(xy, np.zeros((0, 2)), np.zeros(0), np.zeros(0), p), 1.0)
    # en mätare med dubbla radarns mängd: kvoten mellan 1 och 2, närmare 2 ju mer regn
    k1 = a2.stor_kvot(xy, np.zeros((1, 2)), np.array([2.0]), np.array([1.0]), p)
    k2 = a2.stor_kvot(xy, np.zeros((1, 2)), np.array([20.0]), np.array([10.0]), p)
    assert np.all((k1 > 1) & (k1 < 2)) and np.all(k2 > k1)


def test_oi_moves_towards_gauges():
    dag = make_dag(seed=1)
    kv, tm = _fields(dag, scale=0.5)
    s = a2.A2(kv, tm, np.full((H, W), 50.0, np.float32))
    q, h = s.falt(dag, (dag.kvart, dag.timme), hours=[3])
    m = dag.timme.subset(dag.timme.t == 3)
    wet = m.mm > 1
    err_a1 = np.abs(tm[3, m.r, m.c] - m.mm)[wet].mean()
    err_a2 = np.abs(h[3, m.r, m.c] - m.mm)[wet].mean()
    assert err_a2 < err_a1
    assert np.isnan(h[4]).all()  # bara den begärda timmen räknas


def test_dry_mask_only_where_both_radar_and_gauges_are_dry():
    dag = make_dag(seed=2, wet_frac=0.0)  # alla mätare torra
    kv, tm = _fields(dag)
    tm[:, :, :] = 0.0
    tm[0, 10:20, 10:20] = 3.0  # radarn säger regn: får inte tas bort av torrmasken
    s = a2.A2(kv, tm, np.full((H, W), 50.0, np.float32), params={
        r: dict(a2.PARAMS[r], SB=1e-6) for r in a2.PARAMS})  # utan OI-tillskott
    _, h = s.falt(dag, (dag.kvart, dag.timme), hours=[0])
    assert np.all(h[0, 10:20, 10:20] > 0)
    assert np.nanmax(np.where(tm[0] == 0, h[0], 0)) == 0


def test_cross_validated_a2_runs_through_the_judge():
    dag = make_dag(seed=3, n_st=60)
    kv, tm = _fields(dag, scale=0.7)
    s = a2.A2(kv, tm, np.full((H, W), 80.0, np.float32))
    q, h = domare.run_system(s, dag)
    assert q.shape == kv.shape and h.shape == tm.shape
    res = domare.evaluate_fields(dag, q, h)
    assert res["timme/alla"]["n"] > 0
