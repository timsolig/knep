"""Ringen kring de norska och finska OPERA-radarerna tas bort ur OPERA-lagret (uppgift 0028)."""

import numpy as np
from pyproj import Transformer

from knep.analys import composite

GRID = dict(west=126648.4, north=7771252.88, res=2014.96, shape=(887, 471))
TO_GRID = Transformer.from_crs("EPSG:4326", "EPSG:3006", always_xy=True)


def _pixel(grid, lon, lat):
    x, y = TO_GRID.transform(lon, lat)
    return int((grid.north - y) // grid.res), int((x - grid.west) // grid.res)


def test_mask_sets_nan_inside_radius_only():
    grid = composite.TargetGrid(**GRID)
    op = np.ones(grid.shape, np.float32)
    out = composite.mask_opera_ring(op, grid)
    r, c = _pixel(grid, 12.1, 67.53)  # Røst
    assert np.isnan(out[r, c])
    assert np.isnan(out[r + 3, c])        # cirka 6 km
    assert out[r + 8, c] == 1             # cirka 16 km, utanför 12 km
    assert out[0, 0] == 1 and np.isfinite(out).sum() < op.size
    assert (op == 1).all()                # indata orörd


def test_mask_is_nan_so_layer_can_fill_from_elsewhere():
    grid = composite.TargetGrid(**GRID)
    r, c = _pixel(grid, 12.1, 67.53)
    op = np.full(grid.shape, 2.0, np.float32)
    masked = composite.mask_opera_ring(op, grid)
    rain = np.full(grid.shape, np.nan, np.float32)
    src = np.zeros(grid.shape, np.uint8)
    rain, src = composite.layer(rain, src, masked, composite.SOURCE_OPERA)
    assert np.isnan(rain[r, c]) and rain[0, 0] == 2.0


def test_custom_radii_and_unknown_codes_are_ignored():
    grid = composite.TargetGrid(**GRID)
    op = np.ones(grid.shape, np.float32)
    out = composite.mask_opera_ring(op, grid, radii={"noand": 10.0, "finns_inte": 50.0})
    r, c = _pixel(grid, 16.0, 69.24)
    assert np.isnan(out[r, c]) and np.isfinite(out).sum() > op.size - 200
