"""MEPS i hålet (experiments/bortfall/meps_hal.py) på syntetiska fall."""

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments" / "bortfall"))
dm = pytest.importorskip("bortfallsdomare")
mh = pytest.importorskip("meps_hal")

T0 = datetime(2024, 8, 9, 12, 0, tzinfo=UTC)


def _fall(minutes=120, rain=3.0, meps_faktor=2.0, shape=(70, 90), med_meps=True):
    """Stillastående regn i en stor ruta, hålet i mitten; MEPS har samma regn gånger meps_faktor."""
    f = object.__new__(dm.Fall)
    k0 = 12
    nb = k0 + minutes // 5 + 1
    r = np.zeros((nb,) + shape, np.float32)
    r[:, 10:60, 10:80] = rain
    hole = np.zeros(shape, bool)
    hole[25:45, 35:55] = True
    f.radar, f.hal = r, hole
    f.avstand = np.full(shape, 250.0, np.float32)
    f.k0, f.n = k0, minutes // 5
    f.tider = [T0 - timedelta(minutes=60) + timedelta(minutes=5 * k) for k in range(nb)]
    f.meta = {"namn": "prov", "dag": "2024-08-09", "langd_min": minutes, "uppvarmning_bilder": k0}
    if med_meps:
        f.meps_slut = [T0 + timedelta(hours=h) for h in range(0, minutes // 60 + 2)]
        f.meps = np.stack([r[0] * meps_faktor] * len(f.meps_slut))
        f.meta |= {"meps_tid": [e.isoformat() for e in f.meps_slut],
                   "meps_korning": ["20240809T06+%d" % i for i in range(len(f.meps_slut))]}
    else:
        f.meps, f.meps_slut = np.zeros((0,) + shape, np.float32), []
        f.meta |= {"meps_tid": [], "meps_korning": []}
    f.matare = {}
    return f


def test_meps_in_time_interpolates_between_hour_midpoints():
    a, b = np.zeros((2, 2), np.float32), np.full((2, 2), 4.0, np.float32)
    meps = {T0: a, T0 + timedelta(hours=1): b}
    assert mh.meps_vid({}, T0) is None
    assert mh.meps_vid(meps, T0 - timedelta(minutes=50))[0, 0] == 0      # före första mitten
    assert mh.meps_vid(meps, T0)[0, 0] == pytest.approx(2.0)             # mitt emellan
    assert mh.meps_vid(meps, T0 + timedelta(minutes=50))[0, 0] == 4.0    # efter sista mitten


def test_run_for_time():
    meta = {"meps_tid": [(T0 + timedelta(hours=1)).isoformat(), (T0 + timedelta(hours=2)).isoformat()],
            "meps_korning": ["20240809T06+6", "20240809T12+1"]}
    assert mh.korning_vid(meta, T0 + timedelta(minutes=10)) == "20240809T06"
    assert mh.korning_vid(meta, T0 + timedelta(minutes=70)) == "20240809T12"


def test_fill_in_hole_uses_values_outside():
    x = np.full((30, 30), 2.0, np.float32)
    hole = np.zeros(x.shape, bool)
    hole[10:20, 10:20] = True
    x[hole] = 100.0
    y = mh.fyll_i_hal(x, hole, 5.0)
    assert np.allclose(y[hole], 2.0, atol=1e-4) and np.array_equal(y[~hole], x[~hole])


def test_blend_limits_and_outside():
    shape = (40, 40)
    hole = np.zeros(shape, bool)
    hole[10:30, 10:30] = True
    radar = np.full(shape, 1.0, np.float32)
    radar[hole] = np.nan
    flytt = np.where(hole, 3.0, np.nan).astype(np.float32)
    meps = np.full(shape, 6.0, np.float32)
    v_meps, v_flytt = mh.Vikter(0.0, 0.0, match=False), mh.Vikter(np.inf, np.inf, match=False)
    a = mh.blanda(flytt, meps, radar, hole, 60, v_meps)
    assert np.allclose(a[hole], 6.0) and np.array_equal(a[~hole], radar[~hole])
    b = mh.blanda(flytt, meps, radar, hole, 60, v_flytt)
    assert np.allclose(b[12:28, 12:28], 3.0, atol=1e-5)
    # mitt emellan: värdena i hålet mellan de två, och med matchningen mellan fördelningarna
    c = mh.blanda(flytt, meps, radar, hole, 60, mh.Vikter(60.0, 60.0))
    assert np.allclose(c[hole], 4.5, atol=1e-4)
    # den flyttade analysens vikt avtar med åldern
    assert mh.vikt(10, 60, 2.5) > mh.vikt(120, 60, 2.5) and mh.vikt(60, 60, 2.5) == pytest.approx(0.5)


def test_meps_system_corrects_amount_against_radar_outside():
    """MEPS har dubbla mängden; rättningen mot radarn utanför hålet ger rätt volym i hålet."""
    r = dm.kor_fall(mh.Meps(), _fall(meps_faktor=2.0))
    for kl in range(2):
        m = dm.matt(r["klasser"][kl])
        assert m["vol"] == pytest.approx(1.0, abs=0.1)
        assert m["csi_1"] > 0.9


def test_blend_keeps_stationary_rain_after_90_min():
    s = mh.Blandning()
    s.vikter = mh.Vikter(60.0, 150.0)
    r = dm.kor_fall(s, _fall(minutes=180))
    m = dm.matt(r["klasser"][2])
    assert m["csi_1"] > 0.9 and m["vol"] == pytest.approx(1.0, abs=0.15)


def test_without_meps_falls_back_to_fylld():
    f = _fall(med_meps=False)
    a = dm.kor_fall(mh.Blandning(), f)
    b = dm.kor_fall(dm.Fylld(), f)
    assert a["klasser"] == b["klasser"]
    c = dm.kor_fall(mh.Meps(), f)
    assert c["klasser"] == b["klasser"]


def test_candidates_and_selection():
    k = mh.kandidater()
    assert "bara_meps" in k and "bara_flytt" in k and len(k) > 10
    idx = [{"dag": "d1", "langd_min": L, "namn": f"n{L}", "meps_tid": ["x"]} for L in (30, 360, 180, 60)]
    idx.append({"dag": "d2", "langd_min": 360, "namn": "utan", "meps_tid": []})
    assert [c["namn"] for c in mh.urval(idx)] == ["n360", "n180"]
