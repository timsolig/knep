"""Domaren för analysen (experiments/analys/domare.py) på syntetiska data, utan nätverk och arkiv."""

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("domare", ROOT / "experiments/analys/domare.py")
domare = importlib.util.module_from_spec(spec)
sys.modules["domare"] = domare
spec.loader.exec_module(domare)

H, W = 150, 150


def make_dag(seed=0, n_st=40, wet_frac=0.4, elev=None, lovart=None):
    """Stationer på slumpade rutor med kvarts- och timvärden som stämmer med varandra."""
    rng = np.random.default_rng(seed)
    r, c = rng.integers(0, H, n_st), rng.integers(0, W, n_st)
    q = np.where(rng.random((n_st, 96)) < wet_frac, rng.gamma(1.0, 1.0, (n_st, 96)), 0.0)
    h = q.reshape(n_st, 24, 4).sum(axis=2)
    st = np.arange(n_st)
    kv = domare.Matare(np.repeat(st, 96), np.repeat(r, 96), np.repeat(c, 96), np.tile(np.arange(96), n_st), q.ravel())
    tm = domare.Matare(np.repeat(st, 24), np.repeat(r, 24), np.repeat(c, 24), np.tile(np.arange(24), n_st), h.ravel())
    e = np.zeros((H, W), np.float32) if elev is None else elev
    return domare.Dag("2000-01-01", (H, W), kv, tm, e, lovart)


def perfect_fields(dag):
    q = np.zeros((96, H, W), np.float32)
    h = np.zeros((24, H, W), np.float32)
    q[dag.kvart.t, dag.kvart.r, dag.kvart.c] = dag.kvart.mm
    h[dag.timme.t, dag.timme.r, dag.timme.c] = dag.timme.mm
    return q, h


def test_days_never_include_test():
    import json
    dj = json.loads((ROOT / "experiments/sverige/dagar.json").read_text())
    test = {d["day"] for d in dj if d["part"] == "test"}
    assert not test & set(domare.days("validering"))
    assert not test & set(domare.days("traning"))
    with pytest.raises(ValueError):
        domare.days("test")


def test_fold_map_neighbours_differ():
    f = domare.fold_map((300, 300))
    b = f[::domare.BLOCK, ::domare.BLOCK]
    assert set(np.unique(f)) == set(range(domare.FOLDS))
    assert (b[1:, :] != b[:-1, :]).all() and (b[:, 1:] != b[:, :-1]).all()


def test_perfect_analysis_scores_perfectly():
    dag = make_dag()
    q, h = perfect_fields(dag)
    res = domare.evaluate_fields(dag, q, h)
    for key in ("kvart/alla", "timme/alla"):
        m = domare.metrics(res[key], key.split("/")[0])
        assert m["kvot summa"][0] == pytest.approx(1.0)
        assert m["MAE"][0] == pytest.approx(0.0, abs=1e-6)  # fälten är float32
        assert m["CSI 0.5"][0] == pytest.approx(1.0)
        assert m["falskt vid torr mätare"][0] == 0.0
    assert domare.metrics(res["kvart/alla"], "kvart")["hopp, kvot mot mätarna"][0] == pytest.approx(1.0)


def test_scaled_analysis_ratio_and_false_echo():
    dag = make_dag(seed=1)
    q, h = perfect_fields(dag)
    res = domare.evaluate_fields(dag, 0.5 * q, 0.5 * h)
    assert domare.metrics(res["timme/alla"], "timme")["kvot summa"][0] == pytest.approx(0.5)
    # eko överallt: alla torra mätare får falskt eko, och rutorna under torra timmar räknas
    res = domare.evaluate_fields(dag, q + 1.0, h + 4.0)
    m = domare.metrics(res["timme/alla"], "timme")
    assert m["falskt vid torr mätare"][0] == pytest.approx(1.0)
    assert res["rutor"]["eko_torr"] == res["rutor"]["rutor_torr"] > 0


def test_nan_is_skipped():
    dag = make_dag(seed=2)
    q, h = perfect_fields(dag)
    q[:] = np.nan
    res = domare.evaluate_fields(dag, q, h)
    assert res["kvart/alla"]["n"] == 0 and res["timme/alla"]["n"] > 0


def test_terrain_subsets():
    elev = np.zeros((H, W), np.float32)
    elev[:, : W // 2] = 600.0
    lov = np.zeros((24, H, W), bool)
    lov[:12] = True
    dag = make_dag(seed=3, elev=elev, lovart=lov)
    res = domare.evaluate_fields(dag, *perfect_fields(dag))
    hi = (dag.timme.c < W // 2).sum()
    assert res["timme/over400"]["n"] == hi
    assert res["timme/lovart"]["n"] == (dag.timme.t < 12).sum()
    assert res["kvart/lovart"]["n"] == (dag.kvart.t < 48).sum()


class Spy:
    """Ett system med mätare som skriver ned vilka stationer det fick och svarar med gruppens nummer."""

    namn = "spion"
    matare = True

    def __init__(self):
        self.seen = []

    def falt(self, dag, matare):
        kv, tm = matare
        self.seen.append(set(np.unique(tm.station)) | set(np.unique(kv.station)))
        k = len(self.seen) - 1
        return np.full((96, *dag.shape), k, np.float32), np.full((24, *dag.shape), k, np.float32)


def test_cross_validation_hides_the_judged_group():
    dag = make_dag(seed=4, n_st=120)
    spy = Spy()
    q, h = domare.run_system(spy, dag)
    assert len(spy.seen) == domare.FOLDS
    fold_of = dag.folds[dag.timme.r, dag.timme.c]
    from scipy.ndimage import distance_transform_edt
    for k, seen in enumerate(spy.seen):
        in_k = set(dag.timme.station[fold_of == k])
        assert not seen & in_k
        dist = distance_transform_edt(dag.folds != k) * domare.RES_KM
        near = set(dag.timme.station[dist[dag.timme.r, dag.timme.c] <= domare.BUFFER_KM])
        assert not seen & near
        assert seen  # resten får systemet se
    # rutorna i grupp k kommer ur körningen utan grupp k
    assert (h[0] == dag.folds).all() and (q[5] == dag.folds).all()


class Plain:
    namn = "utan"
    matare = False

    def __init__(self, q, h):
        self.q, self.h, self.calls = q, h, 0

    def falt(self, dag, matare):
        assert matare is None
        self.calls += 1
        return self.q, self.h


def test_system_without_gauges_runs_once():
    dag = make_dag(seed=5)
    s = Plain(*perfect_fields(dag))
    res = domare.evaluate(s, dag)
    assert s.calls == 1 and res["timme/alla"]["n"] == len(dag.timme)


def test_sums_from_intervals():
    iv = np.ones((288, 3, 3), np.float32)
    iv[0:2, 0, 0] = np.nan       # två av tre i första kvarten saknas: kvarten saknas
    iv[3, 1, 1] = np.nan         # en av tre saknas: medlet av de två
    q, h = domare.sums(iv)
    assert q.shape == (96, 3, 3) and h.shape == (24, 3, 3)
    assert np.isnan(q[0, 0, 0]) and q[1, 1, 1] == pytest.approx(0.25)
    assert h[0, 1, 1] == pytest.approx(1.0) and h[0, 0, 0] == pytest.approx(1.0)


def test_lovart_mask_follows_slope():
    elev = np.tile(np.linspace(0, 2000, W, dtype=np.float32), (H, 1))  # stiger österut
    lat = np.full((H, W), 65.0)
    lon = np.full((H, W), 15.0)
    m = np.zeros((24, 2, H, W), np.float32)
    m[:12, 0] = 2.0     # rörelse österut, uppför
    m[12:, 0] = -2.0    # västerut, nedför
    lov = domare.lovart_mask(elev, m, lat, lon)
    mid = (slice(None), slice(H // 2 - 5, H // 2 + 5), slice(W // 2 - 5, W // 2 + 5))
    assert lov[:12][mid].all() and not lov[12:][mid].any()


def _fake_day(rng, mae, false=0):
    acc = domare._empty()
    acc.update(n=100, sa=100.0, sg=100.0, ae=mae * 100, ndry=100, fdry=false, ndryo=100, fdryo=false,
               **{f"hit{t:g}": 50.0 for t in domare.CSI_THR}, **{f"mis{t:g}": 10.0 for t in domare.CSI_THR},
               **{f"fal{t:g}": 10.0 for t in domare.CSI_THR}, **{f"fpo{t:g}": 10.0 for t in domare.CSI_THR},
               **{f"fp2{t:g}": 50.0 for t in domare.CSI_THR}, **{f"fo2{t:g}": 50.0 for t in domare.CSI_THR},
               **{f"sa{t:g}": 50.0 for t in domare.AMT_THR}, **{f"sg{t:g}": 50.0 for t in domare.AMT_THR},
               ja=10.0, jg=10.0, nj=10)
    out = {f"{r}/{s}": dict(acc) for r in ("kvart", "timme") for s in domare.SUBSETS}
    out["rutor"] = {"eko_torr": 3, "rutor_torr": 100}
    return out


def test_table_and_verdict():
    rng = np.random.default_rng(0)
    base = {f"d{i}": _fake_day(rng, 0.5 + 0.1 * rng.random()) for i in range(10)}
    better = {d: _fake_day(rng, base[d]["timme/alla"]["ae"] / 100 - 0.1) for d in base}
    tab = domare.table(better, base, B=300)
    row = tab["timme/alla"]["MAE"]
    assert row["diff"] == pytest.approx(0.1) and row["lo"] > 0
    v = domare.verdict(tab)
    assert v["battre"] and "timme MAE" in v["battre_i"] and not v["samre_i"]
    # samma förbättring men fler falska ekon: inte bättre
    noisy = {d: _fake_day(rng, base[d]["timme/alla"]["ae"] / 100 - 0.1, false=20) for d in base}
    v = domare.verdict(domare.table(noisy, base, B=300))
    assert not v["battre"] and any("falskt" in s for s in v["samre_i"])
    # likadan som baslinjen: inte bättre
    assert not domare.verdict(domare.table(base, base, B=300))["battre"]
