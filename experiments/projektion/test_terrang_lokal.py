"""Tester för terrang.py (terrängkvoten) och tak_lokal.py (taket för lokal förskjutning) på syntetiska fält."""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import tak_lokal as L  # noqa: E402
import terrang as T  # noqa: E402


def test_ledtimme():
    assert [T.ledtimme(k) for k in (0, 3, 4, 19)] == [0, 0, 1, 4]


def test_sektor():
    m = np.zeros((2, 10, 10), np.float32)
    assert T.sektor(m, 4) == T.NS - 1                     # stilla: svag vind
    m[0] = 2.0
    assert T.sektor(m, 4) == 0                            # österut
    m[0], m[1] = 0.0, -2.0
    assert T.sektor(m, 4) == 2                            # norrut (rad uppåt)
    assert T.sektor(None, 4) == T.NS - 1


def test_grova_summerar_och_ignorerar_nan():
    x = np.ones((5, 5), np.float32)
    x[0, 0] = np.nan
    g = T.grova(x, 2)
    assert g.shape == (2, 2) and g[0, 0] == 3 and g[1, 1] == 4


def test_kvot_krymper_mot_ett_och_klipps():
    so = np.zeros((20, 20), np.float32)
    sf = np.zeros((20, 20), np.float32)
    n = np.full((20, 20), 10.0, np.float32)
    assert np.allclose(T.kvot(so, sf, n, 4, 0.5, 2.0), 1.0)       # inget regn: kvoten 1
    so[:] = 100.0
    sf[:] = 10.0
    assert np.allclose(T.kvot(so, sf, n, 4, 0.5, 2.0), 2.0)       # klippt
    assert np.allclose(T.kvot(so, sf, np.zeros_like(n), 4, 0.5, 2.0), 1.0)  # inga rutor: 1


def test_flytta_mot_flyttar_en_cell_utan_att_skapa_regn():
    f = np.zeros((64, 64), np.float32)
    o = np.zeros((64, 64), np.float32)
    f[20:28, 20:28] = 5.0
    o[20:28, 24:32] = 5.0                                 # samma cell 4 rutor österut
    f[0, 0] = np.nan
    g = L.flytta_mot(f, o, 9)
    assert np.isnan(g[0, 0])                              # täckningen ändras inte
    assert np.nanmax(g) <= 5.0 + 1e-4                     # inget nytt regn över det som fanns
    assert g[24, 29] > 2.5 and g[24, 21] < 2.5            # cellen har flyttat österut


def test_nybildning_tar_bara_regn_langt_fran_kedjans():
    class Ctx:
        pass

    fc = np.zeros((L.NQ, 40, 40), np.float32)
    o = np.zeros((L.NQ, 40, 40), np.float32)
    fc[:, 5:8, 5:8] = 2.0
    o[:, 6:9, 6:9] = 3.0          # nära kedjans cell: lämnas
    o[:, 30:33, 30:33] = 4.0      # långt bort: ny cell, tas från facit
    from types import SimpleNamespace

    out = L.TakNybildning.cheat(SimpleNamespace(ny_km=16.0), fc, o, 4, Ctx(), None)
    assert out[0, 31, 31] == 4.0 and out[0, 8, 8] == 0.0 and out[0, 6, 6] == 2.0


def test_idw_som_kedjan_med_kedjans_val():
    import rorelse_lokal as R

    rng = np.random.default_rng(0)
    xy = rng.uniform(0, 60, (40, 2))
    uv = rng.normal(0, 1, (40, 2))
    a = R.idw(xy, uv, (64, 64), 20, 0.5, 20, 4)
    b = R.model.dense_motion(xy, uv, (64, 64), 4)
    assert np.allclose(a, b)


def test_farneback_ger_ratt_riktning():
    import rorelse_lokal as R

    a = np.zeros((64, 64), np.float32)
    b = np.zeros((64, 64), np.float32)
    a[20:30, 20:30] = 5.0
    b[20:30, 23:33] = 5.0            # 3 rutor österut
    f = R.farneback(a, b, 9)
    assert 1.5 < f[0, 25, 26] < 4.5 and abs(f[1, 25, 26]) < 1.0


def test_ensemble_matchning_behaller_kedjans_varden():
    import ensemble as E

    rng = np.random.default_rng(1)
    bas = rng.gamma(0.5, 2.0, (40, 40)).astype(np.float32)
    medel = (bas + np.roll(bas, 3, axis=1)) / 2
    m = E.model.cdf_match(medel, bas)
    assert np.allclose(np.sort(m.ravel()), np.sort(bas.ravel()))   # samma värden som kedjan
    assert np.corrcoef(m.ravel(), medel.ravel())[0, 1] > 0.8       # men i medelvärdets ordning
