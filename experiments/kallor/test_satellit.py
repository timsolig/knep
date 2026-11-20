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
