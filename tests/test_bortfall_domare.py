"""Domaren (experiments/bortfall/domare.py): måtten, bootstrap och körningen på syntetiska fall."""

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments" / "bortfall"))
dm = pytest.importorskip("domare")

T0 = datetime(2024, 8, 9, 12, 0, tzinfo=UTC)


# --- åldrar och fönster -----------------------------------------------------------------------

def test_age_classes_are_half_open():
    assert dm.klass_for(0) is None
    assert dm.klass_for(5) == 0 and dm.klass_for(30) == 0
    assert dm.klass_for(35) == 1 and dm.klass_for(90) == 1
    assert dm.klass_for(95) == 2 and dm.klass_for(360) == 2
    assert dm.klass_for(365) is None


def test_window_sizes():
    assert dm.fonster(10) == 5 and dm.fonster(30) == 15


# --- FSS --------------------------------------------------------------------------------------

def _fss(f, o, m, thr, n):
    a, b = dm.fss_sums(f, o, m, thr, n)
    return 1 - a / b


def test_fss_perfect_and_disjoint():
    o = np.zeros((40, 40))
    o[10:20, 10:20] = 3.0
    m = np.ones(o.shape, bool)
    assert _fss(o, o, m, 1.0, 5) == pytest.approx(1.0)
    f = np.zeros_like(o)
    f[25:35, 25:35] = 3.0  # långt ifrån, inget överlapp i 5 x 5
    assert _fss(f, o, m, 1.0, 5) == pytest.approx(0.0)
    assert _fss(np.zeros_like(o), o, m, 1.0, 5) == pytest.approx(0.0)


def test_fss_grows_with_scale_for_displaced_field():
    o = np.zeros((60, 60))
    o[20:30, 20:30] = 2.0
    f = np.roll(o, 4, axis=1)
    m = np.ones(o.shape, bool)
    assert _fss(f, o, m, 1.0, 1) < _fss(f, o, m, 1.0, 5) < _fss(f, o, m, 1.0, 15)


def test_fss_window_one_is_pixelwise():
    """Med fönster 1 är FSS = 1 - (missar + falsklarm) / (2 träffar + missar + falsklarm)."""
    rng = np.random.default_rng(1)
    o = rng.gamma(0.5, 2.0, (30, 30))
    f = rng.gamma(0.5, 2.0, (30, 30))
    m = rng.random((30, 30)) > 0.3
    h, mi, fa = dm.csi_sums(f, o, m, 1.0)
    assert _fss(f, o, m, 1.0, 1) == pytest.approx(1 - (mi + fa) / (2 * h + mi + fa))


def test_fss_ignores_everything_outside_the_mask():
    """Andelarna räknas bara ur hålet: radarn utanför ska varken höja eller sänka FSS."""
    o = np.zeros((40, 40))
    o[:, :20] = 4.0
    m = np.zeros(o.shape, bool)
    m[:, 20:] = True              # hålet är torrt i facit
    f = o.copy()
    f[:, 20:] = 0.0               # och torrt i systemet
    base = dm.fss_sums(f, o, m, 1.0, 15)
    assert base == (0.0, 0.0)     # inget regn i hålet hos någon: inget underlag
    g = f.copy()
    g[:, :20] = 0.0               # utanför hålet ändrat: ingen skillnad
    assert dm.fss_sums(g, o, m, 1.0, 15) == base


# --- CSI, volym, söm --------------------------------------------------------------------------

def test_csi_counts():
    o = np.array([[2, 2, 0, 0]], float)
    f = np.array([[2, 0, 2, 0]], float)
    m = np.ones(o.shape, bool)
    assert dm.csi_sums(f, o, m, 1.0) == (1, 1, 1)
    m[0, 2] = False
    assert dm.csi_sums(f, o, m, 1.0) == (1, 1, 0)


def test_edge_band_on_both_sides():
    hole = np.zeros((20, 20), bool)
    hole[5:15, 5:15] = True
    band = dm.kantband(hole, 2)
    assert band[5, 10] and band[4, 10] and band[3, 10] and band[6, 10]
    assert not band[10, 10] and not band[0, 10] and not band[2, 10]


def test_seam_zero_for_radar_and_positive_for_jump():
    o = np.full((20, 20), 2.0)
    hole = np.zeros(o.shape, bool)
    hole[5:15, 5:15] = True
    band = dm.kantband(hole)
    a, skev, n = dm.som_sums(o, o, band)
    assert a == 0 and skev == 0 and n == band.sum()
    tom = np.where(hole, 0.0, o)
    a, skev, n = dm.som_sums(tom, o, band)
    assert a > 0 and skev > 0  # ett tomt hål i regn ger en brant kant som radarn inte har


def test_seam_skips_pixels_without_radar():
    o = np.full((20, 20), 1.0)
    o[:, :3] = np.nan
    hole = np.zeros(o.shape, bool)
    hole[2:18, 2:10] = True
    band = dm.kantband(hole)
    _, _, n = dm.som_sums(o, o, band)
    assert n < band.sum()


def test_frame_sums_use_radar_outside_and_zero_for_nan():
    o = np.full((30, 30), 2.0)
    hole = np.zeros(o.shape, bool)
    hole[10:20, 10:20] = True
    s = dm.tom_klass()
    f = np.full(o.shape, 50.0)   # utanför hålet ignoreras systemet
    f[hole] = np.nan             # NaN i hålet = 0 mm/h
    dm.bild_sums(s, f, o, hole, dm.kantband(hole))
    m = dm.matt(s)
    assert m["vol"] == 0 and m["csi_1"] == 0 and m["fss_1_10"] == pytest.approx(0)
    assert s["px"] == 100 and s["bilder"] == 1


def test_pooled_scores_add_sums():
    a, b = dm.tom_klass(), dm.tom_klass()
    a["csi_1"] = [1, 1, 0]
    b["csi_1"] = [3, 0, 1]
    a["vol"], b["vol"] = [1.0, 2.0], [3.0, 2.0]
    s = dm.summera([a, b])
    m = dm.matt(s)
    assert m["csi_1"] == pytest.approx(4 / 6)
    assert m["vol"] == pytest.approx(1.0)
    assert np.isnan(m["fss_1_10"])


# --- bootstrap --------------------------------------------------------------------------------

def _dag(csi_h, vol=1.0):
    s = dm.tom_klass()
    s["csi_1"] = [csi_h, 10 - csi_h, 0]
    s["vol"] = [vol * 10, 10.0]
    s["bilder"] = 1
    return [s, dm.tom_klass(), dm.tom_klass()]


def test_bootstrap_identical_systems_no_verdict():
    a = {f"d{i}": _dag(5 + i % 3) for i in range(10)}
    r = dm.bootstrap(a, a, 0, n=200)
    assert r["csi_1"]["diff"] == 0 and r["csi_1"]["dom"] == ""


def test_bootstrap_clear_improvement_and_volume_direction():
    rng = np.random.default_rng(3)
    a, b = {}, {}
    for i in range(12):
        h = int(rng.integers(2, 6))
        a[f"d{i}"] = _dag(h + 3, vol=1.0)
        b[f"d{i}"] = _dag(h, vol=0.5)
    r = dm.bootstrap(a, b, 0, n=300)
    assert r["csi_1"]["dom"] == "bättre" and r["csi_1"]["lo"] > 0
    assert r["vol"]["dom"] == "bättre" and r["vol"]["diff"] == pytest.approx(-0.5)
    r = dm.bootstrap(b, a, 0, n=300)
    assert r["csi_1"]["dom"] == "sämre" and r["vol"]["dom"] == "sämre"


def test_bootstrap_too_few_days_gives_no_verdict():
    a = {"d0": _dag(9), "d1": _dag(8)}
    b = {"d0": _dag(1), "d1": _dag(2)}
    assert dm.bootstrap(a, b, 0, n=100)["csi_1"]["dom"] == ""


def test_bootstrap_resamples_days_not_cases():
    """Två fall samma dag blir en dag i bootstrap."""
    res = {"fall": [{"dag": "d0", "klasser": _dag(3)}, {"dag": "d0", "klasser": _dag(5)},
                    {"dag": "d1", "klasser": _dag(4)}]}
    d = dm.per_dag(res)
    assert sorted(d) == ["d0", "d1"]
    assert d["d0"][0]["csi_1"] == [8, 12, 0]


# --- körningen --------------------------------------------------------------------------------

def _fall(minutes=120, rain=3.0, shape=(40, 50)):
    """Ett syntetiskt fall: stillastående regn i en ruta, hålet i mitten, mätare i hålet."""
    f = object.__new__(dm.Fall)
    k0 = 12
    nb = k0 + minutes // 5 + 1
    r = np.zeros((nb,) + shape, np.float32)
    r[:, 8:32, 10:40] = rain
    r[:, :, :2] = np.nan
    hole = np.zeros(shape, bool)
    hole[12:28, 18:32] = True
    f.radar, f.hal = r, hole
    f.avstand = np.full(shape, 250.0, np.float32)
    f.meps = np.zeros((0,) + shape, np.float32)
    f.meps_slut = []
    f.k0, f.n = k0, minutes // 5
    f.tider = [T0 - timedelta(minutes=60) + timedelta(minutes=5 * k) for k in range(nb)]
    f.meta = {"namn": "prov", "dag": "2024-08-09", "langd_min": minutes, "uppvarmning_bilder": k0}
    ends = [T0 + timedelta(minutes=15 * q) for q in range(1, minutes // 15 + 1)]
    f.matare = {"p14": {"tid": np.array([t.timestamp() for t in ends]), "mm": np.full(len(ends), rain / 4),
                        "rad": np.full(len(ends), 20), "kol": np.full(len(ends), 25),
                        "i_hal": np.ones(len(ends), bool), "station": np.arange(len(ends))}}
    return f


def test_facit_scores_perfectly():
    r = dm.kor_fall(dm.Facit(), _fall())
    for kl in range(2):
        m = dm.matt(r["klasser"][kl])
        assert m["fss_1_10"] == pytest.approx(1) and m["csi_0.5"] == 1 and m["vol"] == pytest.approx(1)
        assert m["som"] == pytest.approx(0)
        assert m["mae_p14"] == pytest.approx(0, abs=1e-5)  # regnet är 3 mm/h i 15 min = 0,75 mm
    assert r["klasser"][0]["bilder"] == 6 and r["klasser"][1]["bilder"] == 12 and r["klasser"][2]["bilder"] == 6


def test_hole_baseline_scores_zero():
    r = dm.kor_fall(dm.Hal(), _fall())
    m = dm.matt(r["klasser"][0])
    assert m["fss_1_10"] == pytest.approx(0) and m["csi_1"] == 0 and m["vol"] == 0 and m["som"] > 0
    assert m["mae_p14"] == pytest.approx(0.75, abs=1e-5)


def test_filled_keeps_stationary_rain_until_max_age():
    r = dm.kor_fall(dm.Fylld(), _fall())
    m0, m1, m2 = (dm.matt(r["klasser"][k]) for k in range(3))
    assert m0["csi_1"] > 0.95 and m1["csi_1"] > 0.95
    assert m2["vol"] == 0  # efter 90 min släpps pixlarna, som i drift


class Spion:
    """System som kontrollerar att det inte får se facit i hålet eller mätare som inte kommit."""

    namn = "spion"

    def start(self, ind):
        assert ind.forfluten.shape[0] == ind.k0
        self.sett = 0

    def steg(self, k, ind):
        assert np.isnan(ind.bild[ind.hal]).all()
        assert np.isfinite(ind.bild[5, 5])  # radarn utanför hålet finns
        for g in ind.matare.values():
            assert (g["tid"] <= (ind.tid - timedelta(minutes=60)).timestamp()).all()
        assert ind.tid == ind.tider[ind.k0 + k]
        self.sett += 1
        return ind.bild


def test_system_sees_no_truth_in_hole():
    f = _fall()
    s = Spion()
    dm.kor_fall(s, f)
    assert s.sett == f.n
