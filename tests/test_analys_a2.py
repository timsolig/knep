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
    for namn in ("A2S", "A2T"):  # de frysta varianterna mot falska ekon ändrar bara kvarten
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


def test_gauge_check_off_by_default_gives_identical_fields():
    dag = make_dag(seed=5)
    kv, tm = _fields(dag, scale=0.6)
    rng = np.full((H, W), 60.0, np.float32)
    base = a2.system_params("A2T")
    off = {r: dict(base[r], QC_T=0.0, QC_R=25.0) for r in base}
    q0, h0 = a2.A2(kv, tm, rng, params=base).falt(dag, (dag.kvart, dag.timme), hours=[2, 3])
    q1, h1 = a2.A2(kv, tm, rng, params=off).falt(dag, (dag.kvart, dag.timme), hours=[2, 3])
    assert np.array_equal(q0, q1, equal_nan=True) and np.array_equal(h0, h1, equal_nan=True)
    assert "QC_T" not in a2.PARAMS["kvart"] and "QC_T" not in a2.PARAMS["timme"]
    for namn in ("A2", "A2S", "A2T"):
        for r in ("kvart", "timme"):
            assert a2.system_params(namn)[r].get("QC_T", 0.0) == 0.0


def _ring(n=12, rad=15.0):
    """En mätare i mitten och n grannar på en ring med radien rad km."""
    ang = np.linspace(0, 2 * np.pi, n, endpoint=False)
    return np.r_[[[0.0, 0.0]], np.c_[rad * np.cos(ang), rad * np.sin(ang)]]


def test_gauge_check_flags_zero_in_rain_and_lone_peak():
    p = dict(a2.PARAMS["kvart"], QC_T=3.0, QC_R=40.0)
    xy = _ring()
    n = len(xy)
    rng = np.full(n, 50.0)
    low = np.zeros(n, bool)
    # 0 i regn: grannarna och radarn våta
    mm = np.full(n, 1.0)
    mm[0] = 0.0
    assert a2.kontroll(xy, mm, np.full(n, 1.0), rng, low, p).tolist() == [True] + [False] * (n - 1)
    # 0 där radarn är torr men grannarna våta: radarn stöder mätaren, den kastas inte
    bg = np.full(n, 1.0)
    bg[0] = 0.0
    assert not a2.kontroll(xy, mm, bg, rng, low, p).any()
    # en orimlig topp där grannarna och radarn är torra
    mm = np.zeros(n)
    mm[0] = 5.0
    assert a2.kontroll(xy, mm, np.zeros(n), rng, low, p)[0]
    # samma topp över 400 m: skyddad (radarn missar låg nederbörd i fjällen), utom utan skyddet
    hi = low.copy()
    hi[0] = True
    assert not a2.kontroll(xy, mm, np.zeros(n), rng, hi, p).any()
    assert a2.kontroll(xy, mm, np.zeros(n), rng, hi, dict(p, QC_SKYDD400=False))[0]
    # utan grannar inom QC_R kastas ingenting
    assert not a2.kontroll(xy * 10, mm, np.zeros(n), rng, low, p).any()
    # av som standard
    assert not a2.kontroll(xy, mm, np.zeros(n), rng, low, a2.PARAMS["kvart"]).any()


def test_gauge_check_in_field_removes_zero_in_rain():
    n = 13
    xy = _ring(12, 6.0) / domare.RES_KM  # i rutor
    r, c = np.round(75 + xy[:, 1]).astype(int), np.round(75 + xy[:, 0]).astype(int)
    st = np.arange(n)
    q = np.full((n, 96), 1.0)
    q[0] = 0.0  # mätaren i mitten visar 0 hela dygnet
    h = q.reshape(n, 24, 4).sum(axis=2)
    kvm = domare.Matare(np.repeat(st, 96), np.repeat(r, 96), np.repeat(c, 96), np.tile(np.arange(96), n), q.ravel())
    tmm = domare.Matare(np.repeat(st, 24), np.repeat(r, 24), np.repeat(c, 24), np.tile(np.arange(24), n), h.ravel())
    dag = domare.Dag("2000-01-01", (H, W), kvm, tmm, np.zeros((H, W), np.float32), None)
    kv = np.full((96, H, W), 1.0, np.float32)  # radarn våt överallt
    tm = kv.reshape(24, 4, H, W).sum(axis=1)
    rng = np.full((H, W), 50.0, np.float32)
    base = a2.system_params("A2T")
    qc = {res: dict(base[res], QC_T=3.0) for res in base}
    s0, s1 = a2.A2(kv, tm, rng, params=base), a2.A2(kv, tm, rng, params=qc)
    q0, h0 = s0.falt(dag, (dag.kvart, dag.timme), hours=[5])
    q1, h1 = s1.falt(dag, (dag.kvart, dag.timme), hours=[5])
    t = 20
    assert q0[t, r[0], c[0]] < 0.8 and h0[5, r[0], c[0]] < 3.2  # utan kontroll drar mätaren ner fältet
    assert q1[t, r[0], c[0]] > 0.9 and h1[5, r[0], c[0]] > 3.6  # med kontrollen är den borta
    assert ("kvart", 0, t) in s1.kastade and ("timme", 0, 5) in s1.kastade
    assert all(x[1] == 0 for x in s1.kastade)
