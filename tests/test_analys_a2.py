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


def test_variants_off_by_default_give_identical_fields():
    dag = make_dag(seed=4)
    kv, tm = _fields(dag, scale=0.6)
    kv += 0.02  # svagt eko överallt
    rng = np.full((H, W), 60.0, np.float32)
    off = {r: dict(a2.PARAMS[r], K_SVAG=0.0, TORR2=0.0, R_TORR2=30.0) for r in a2.PARAMS}
    q0, h0 = a2.A2(kv, tm, rng).falt(dag, (dag.kvart, dag.timme), hours=[2, 3])
    q1, h1 = a2.A2(kv, tm, rng, params=off).falt(dag, (dag.kvart, dag.timme), hours=[2, 3])
    assert np.array_equal(q0, q1, equal_nan=True) and np.array_equal(h0, h1, equal_nan=True)
    assert a2.system_params("A2") is a2.PARAMS
    for namn in a2.FRYSTA:  # de frysta varianterna ändrar bara kvarten
        assert a2.system_params(namn)["timme"] == a2.PARAMS["timme"]


def _wet_dag(mm_q):
    """Tre mätare tätt ihop med samma kvartsvärde (och timvärde 4 · mm_q) hela dygnet."""
    n = 3
    r, c = np.array([70, 75, 80]), np.array([70, 75, 80])
    st = np.arange(n)
    kv = domare.Matare(np.repeat(st, 96), np.repeat(r, 96), np.repeat(c, 96), np.tile(np.arange(96), n),
                       np.full(n * 96, mm_q))
    tm = domare.Matare(np.repeat(st, 24), np.repeat(r, 24), np.repeat(c, 24), np.tile(np.arange(24), n),
                       np.full(n * 24, 4 * mm_q))
    return domare.Dag("2000-01-01", (H, W), kv, tm, np.zeros((H, W), np.float32), None)


def test_no_upscaling_of_weak_echo():
    dag = _wet_dag(2.0)  # mätarna har mycket mer än radarn: k > 1
    kv = np.full((96, H, W), 0.08, np.float32)  # svagt eko under tröskeln 0,125
    kv[:, 70:81, 70:81] = 0.5                   # starkare eko vid mätarna
    tm = kv.reshape(24, 4, H, W).sum(axis=1)
    rng = np.full((H, W), 60.0, np.float32)
    base = {r: dict(a2.PARAMS[r], SB=1e-6, ALFA=0.1) for r in a2.PARAMS}  # utan OI, bara kvoten
    q0, _ = a2.A2(kv, tm, rng, params=base).falt(dag, (dag.kvart, dag.timme), hours=[5])
    var = {"timme": base["timme"], "kvart": dict(base["kvart"], K_SVAG=0.1)}
    q1, _ = a2.A2(kv, tm, rng, params=var).falt(dag, (dag.kvart, dag.timme), hours=[5])
    t = 20
    assert q0[t, 60, 60] > 0.125            # standard: kvoten lyfter det svaga ekot över tröskeln
    assert np.isclose(q1[t, 60, 60], 0.08)  # varianten: k = min(k, 1) där A1 är svag
    assert q1[t, 75, 75] > 0.5 and np.isclose(q1[t, 75, 75], q0[t, 75, 75])  # starkt eko skalas som förut


def test_cap_over_weak_echo_stops_oi_lift():
    dag = _wet_dag(2.0)  # våta mätare: OI lyfter omgivningen
    kv = np.full((96, H, W), 0.08, np.float32)
    kv[:, 100:110, 100:110] = 0.0  # radarn torr här: OI får fortfarande lägga till regn
    tm = kv.reshape(24, 4, H, W).sum(axis=1)
    rng = np.full((H, W), 60.0, np.float32)
    base = {r: dict(a2.PARAMS[r], ALFA=1e9) for r in a2.PARAMS}  # utan kvoten, bara OI
    var = {"timme": base["timme"], "kvart": dict(base["kvart"], K_SVAG=0.125, SVAG_TAK=True)}
    q0, _ = a2.A2(kv, tm, rng, params=base).falt(dag, (dag.kvart, dag.timme), hours=[5])
    q1, _ = a2.A2(kv, tm, rng, params=var).falt(dag, (dag.kvart, dag.timme), hours=[5])
    t = 20
    assert q0[t, 90, 90] > 0.125 and q1[t, 90, 90] <= 0.08 + 1e-6  # svagt eko lyfts inte
    assert np.isclose(q1[t, 104, 104], q0[t, 104, 104]) and q1[t, 104, 104] > 0  # där A1 = 0 som förut


def test_dry_mask_over_weak_echo():
    for mm, removed in ((0.0, True), (1.0, False)):
        dag = _wet_dag(mm)
        kv = np.full((96, H, W), 0.08, np.float32)  # svagt eko, över TORR men under TORR2
        tm = kv.reshape(24, 4, H, W).sum(axis=1)
        rng = np.full((H, W), 60.0, np.float32)
        base = {r: dict(a2.PARAMS[r], SB=1e-6, ALFA=1e9) for r in a2.PARAMS}  # varken OI eller kvot
        var = {"timme": base["timme"], "kvart": dict(base["kvart"], TORR2=0.1, R_TORR2=30.0)}
        q0, _ = a2.A2(kv, tm, rng, params=base).falt(dag, (dag.kvart, dag.timme), hours=[5])
        q1, _ = a2.A2(kv, tm, rng, params=var).falt(dag, (dag.kvart, dag.timme), hours=[5])
        t = 20
        assert np.isclose(q0[t, 75, 75], 0.08)  # standardmasken rör inte ekot över TORR
        assert (q1[t, 75, 75] == 0.0) == removed
        assert np.isclose(q1[t, 140, 140], 0.08)  # långt från mätarna: ingen mask


def test_cross_validated_a2_runs_through_the_judge():
    dag = make_dag(seed=3, n_st=60)
    kv, tm = _fields(dag, scale=0.7)
    s = a2.A2(kv, tm, np.full((H, W), 80.0, np.float32))
    q, h = domare.run_system(s, dag)
    assert q.shape == kv.shape and h.shape == tm.shape
    res = domare.evaluate_fields(dag, q, h)
    assert res["timme/alla"]["n"] > 0
