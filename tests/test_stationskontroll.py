"""Kontrollen av mätarna per station och dygn (A2TS) i experiments/analys/a2.py, syntetiska data.

A2TS godkändes inte på valideringen (rapporten 2026-11-07/0007), så kontrollen finns bara i experimentet."""

import importlib.util
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if "analys_a2" not in sys.modules:
    spec = importlib.util.spec_from_file_location("analys_a2", ROOT / "experiments/analys/a2.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["analys_a2"] = mod
    spec.loader.exec_module(mod)
exp = sys.modules["analys_a2"]
Q = exp.system_params("A2TS")["kvart"]["QCS"]


def _dag(n=5, nper=96, mm=0.0, a1=0.0):
    """n × n stationer 30 km isär, alla perioder med samma värde."""
    yy, xx = np.mgrid[0:n, 0:n]
    xy = np.c_[xx.ravel(), yy.ravel()] * 30.0
    ns = n * n
    st = np.repeat(np.arange(ns), nper)
    return {"station": st, "t": np.tile(np.arange(nper), ns), "xy": np.repeat(xy, nper, axis=0),
            "mm": np.full(ns * nper, mm), "a": np.full(ns * nper, a1), "over400": np.zeros(ns * nper, bool)}


def test_av_som_standard():
    r = _dag()
    r["mm"][r["station"] == 12] = 1.0
    assert exp.stationsdygn({"kvart": r}, None) == set()
    assert "QCS" not in exp.system_params("A2T")["kvart"]
    assert "QCS" not in exp.system_params("A2T")["timme"]
    assert exp.system_params("A2TS")["timme"]["QCS"] == Q


def test_vat_mot_torrt_och_noll_mot_vatt():
    # station 12 visar regn i 20 kvartar där radarn och grannarna är torra
    r = _dag()
    r["mm"][(r["station"] == 12) & (r["t"] < 20)] = 0.5
    assert exp.stationsdygn({"kvart": r}, Q) == {12}
    # för få perioder: inte kastad
    r = _dag()
    r["mm"][(r["station"] == 12) & (r["t"] < 5)] = 0.5
    assert exp.stationsdygn({"kvart": r}, Q) == set()
    # en verklig skur: radarn och grannarna våta, inget kastas
    r = _dag(mm=0.8, a1=0.7)
    r["mm"][r["station"] == 12] = 3.0
    assert exp.stationsdygn({"kvart": r}, Q) == set()
    # station 7 visar noll i 20 kvartar där radarn och grannarna är tydligt våta
    r = _dag(mm=0.8, a1=0.7)
    r["mm"][(r["station"] == 7) & (r["t"] >= 50) & (r["t"] < 70)] = 0.0
    assert exp.stationsdygn({"kvart": r}, Q) == {7}


def test_skydd400():
    r = _dag()
    r["mm"][(r["station"] == 12) & (r["t"] < 20)] = 0.5
    r["over400"] = r["station"] == 12
    assert exp.stationsdygn({"kvart": r}, Q) == set()
    assert exp.stationsdygn({"kvart": r}, exp.qcs_params({"R": 100.0})) == {12}


def test_falt_tar_bort_stationen():
    """I fältversionen tas en station som är våt mot torr radar och torra grannar bort för dygnet."""
    D = exp.D
    H, W = 60, 60
    rr, cc = np.mgrid[5:55:12, 5:55:12]
    r, c = rr.ravel(), cc.ravel()
    ns = len(r)
    q = np.zeros((ns, 96))
    q[0, :20] = 0.5
    h = q.reshape(ns, 24, 4).sum(axis=2)
    st = np.arange(ns)
    mq = D.Matare(np.repeat(st, 96), np.repeat(r, 96), np.repeat(c, 96), np.tile(np.arange(96), ns), q.ravel())
    mh = D.Matare(np.repeat(st, 24), np.repeat(r, 24), np.repeat(c, 24), np.tile(np.arange(24), ns), h.ravel())
    kv = np.zeros((96, H, W), np.float32)
    tm = np.zeros((24, H, W), np.float32)
    rng = np.full((H, W), 50.0, np.float32)
    med = exp.A2(kv, tm, rng, exp.system_params("A2TS"))
    kq, _ = med.falt(None, (mq, mh), hours=range(2))
    assert med.kastade_dygn == {0}
    utan = exp.A2(kv, tm, rng, exp.system_params("A2T"))
    kq0, _ = utan.falt(None, (mq, mh), hours=range(2))
    assert kq0[0, r[0], c[0]] > 0.05 and kq[0, r[0], c[0]] == 0.0
