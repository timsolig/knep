"""Projektionen från SEVIRI:s geostationära bild till SMHI:s rutnät (satellit.py)."""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import satellit as S  # noqa: E402


def test_orientering_norr_upp_och_oster_at_vanster():
    row, col = S.index_for(6610700, 3622, 3610, 1856.0, 1856.0)
    lon, lat = S.rutnat_lonlat()
    nord, syd = np.unravel_index(np.argmax(lat), lat.shape), np.unravel_index(np.argmin(lat), lat.shape)
    ost, vast = np.unravel_index(np.argmax(lon), lon.shape), np.unravel_index(np.argmin(lon), lon.shape)
    assert row[nord] > row[syd]          # raderna går från söder mot norr
    assert col[ost] < col[vast]          # kolumnerna går från öster mot väster
    assert 1856 < row.min() and row.max() < 3712 and 1300 < col.min() and col.max() < 1856


def test_till_rutnat_utanfor_ar_saknas():
    v = np.full((10, 10), 2.0)
    row = np.full(S.FORM, 5)
    col = np.full(S.FORM, 5)
    col[0, 0] = 99
    out = S.till_rutnat(v, row, col)
    assert out[0, 0] == 3 and out[1, 1] == 2


def test_bortfall_nivakvot_och_mjuk_kant():
    import importlib.util

    p = Path(__file__).resolve().parents[1] / "bortfall" / "kallor.py"
    sys.path.insert(0, str(p.parent))
    spec = importlib.util.spec_from_file_location("bortfall_kallor", p)
    K = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(K)
    hal = np.zeros((60, 60), bool)
    hal[20:40, 20:40] = True
    smhi = np.full((60, 60), 2.0)
    smhi[hal] = np.nan
    opera = np.full((60, 60), 1.0)
    assert abs(K.nivakvot(smhi, opera, hal) - (2.0 * 1 + 1) / (1 * 1 + 1) * 1) < 0.6   # nära 2 (priorn drar mot 1)
    w = K.mjuk_kant(hal, 5)
    assert w[0, 0] == 0 and w[20, 20] < w[25, 25] <= 1 and w[30, 30] == 1
