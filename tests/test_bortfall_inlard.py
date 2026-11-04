"""Inlärd blandning (experiments/bortfall/inlard.py) på syntetiska fall."""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments" / "bortfall"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
dm = pytest.importorskip("domare")
il = pytest.importorskip("inlard")
pytest.importorskip("sklearn")

from test_bortfall_meps_hal import _fall  # noqa: E402


def test_match_wet_count_and_ring_distribution():
    p = np.array([0.9, 0.8, 0.2, 0.1, 0.0, 0.0])          # summa 2 -> två våta
    mu = np.array([0.1, 2.0, 1.0, 0.0, 0.0, 0.0])
    ring = np.concatenate([np.full(50, 1.0), np.full(50, 5.0), np.zeros(30)])
    out = il.matcha(p, mu, ring)
    assert (out > 0).sum() == 2
    assert out[1] > out[2] and out[2] > 0                  # högst mu får störst värde
    assert out.max() <= 5.0 and out[out > 0].min() >= 1.0
    # torr ring: modellens egen fördelning
    out2 = il.matcha(p, mu, np.zeros(10))
    assert out2[1] == pytest.approx(np.expm1(2.0), rel=1e-5)


def test_features_shape_and_no_truth():
    f = _fall(minutes=60)
    ind = f.indata()
    b = il.Basen()
    b.start(ind)
    t = f.tider[f.k0]
    ind.bild, ind.tid, ind.meps = f.maskad(0), t, f.meps_till(t)
    a, m = b.bas(0, ind)
    X = il.sardrag(b.st, ind, a, m, 5.0)
    assert X.shape == (int(f.hal.sum()), len(il.SARDRAG))
    # sardragen beror inte på facit i hålet
    f.radar[f.k0, f.hal] = 99.0
    ind.bild = f.maskad(0)
    assert np.allclose(np.nan_to_num(il.sardrag(b.st, ind, a, m, 5.0)), np.nan_to_num(X))


def test_system_runs_with_tiny_model(tmp_path):
    from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor

    rng = np.random.default_rng(0)
    X = rng.normal(size=(400, len(il.SARDRAG))).astype(np.float32)
    X[:, 0] = rng.uniform(0, 2, 400)
    y = np.expm1(X[:, 0])
    il.Inlard.modell = {"klass": HistGradientBoostingClassifier(max_iter=10).fit(X, y > 0.5),
                        "regr": HistGradientBoostingRegressor(max_iter=10).fit(X, X[:, 0])}
    try:
        r = dm.kor_fall(il.Inlard(), _fall(minutes=120))
    finally:
        il.Inlard.modell = None
    m = dm.matt(r["klasser"][0])
    assert m["fss_1_30"] > 0.5           # stillastående regn i hela hålet hittas
