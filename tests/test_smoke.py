"""Röktest med syntetiska kompositer i SMHI:s format: en regncell som rör sig österut."""

import json
from datetime import UTC, datetime

import numpy as np
import rasterio
from rasterio.transform import from_origin

from nowcast import cli, model, radar

# SMHI-kompositens ungefärliga rutnät i SWEREF99 TM, 2 km
WEST, NORTH, RES, W, H = 126648, 7771252, 2000, 475, 894
T0 = datetime(2026, 10, 28, 19, 25, tzinfo=UTC)
SPEED = 2  # pixlar österut per 5 min


def _rain(k: int) -> np.ndarray:
    """Regnfält i mm/h för bild k (0 = analysen, negativa = äldre)."""
    y, x = np.mgrid[0:H, 0:W]
    cx, cy = 150 + SPEED * k, 600
    r = 25.0 * np.exp(-(((x - cx) / 20.0) ** 2 + ((y - cy) / 12.0) ** 2))
    r[r < 0.05] = 0.0
    return r


def _encode(rain: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore"):
        dbz = 10 * np.log10(radar.ZR_A * rain**radar.ZR_B)
    raw = np.clip(np.round((dbz - radar.OFFSET) / radar.GAIN), 1, 254)
    raw[rain == 0] = radar.NO_ECHO
    y, x = np.mgrid[0:H, 0:W]
    raw[((x - W / 2) / (W * 0.55)) ** 2 + ((y - H / 2) / (H * 0.55)) ** 2 > 1] = radar.NO_DATA
    return raw.astype(np.uint8)


def _write_cache(cache, n=4):
    for k in range(n):
        t = T0 - k * radar.STEP
        with rasterio.open(
            cache / f"{t:%Y%m%d%H%M}.tif", "w", driver="GTiff", width=W, height=H, count=1,
            dtype="uint8", crs="EPSG:3006", transform=from_origin(WEST, NORTH, RES, RES),
        ) as dst:
            dst.write(_encode(_rain(-k)), 1)


def test_decoding_roundtrip(tmp_path):
    _write_cache(tmp_path, n=1)
    rain, grid = radar.read_rain(tmp_path / f"{T0:%Y%m%d%H%M}.tif")
    assert grid.crs.to_epsg() == 3006
    assert np.isnan(rain).any() and np.nanmax(rain) > 20
    truth = _rain(0)
    inside = np.isfinite(rain) & (truth > 1)
    assert np.allclose(rain[inside], truth[inside], rtol=0.1)


def test_motion_is_eastward():
    obs = np.stack([_rain(k) for k in (-3, -2, -1, 0)])
    fc = model.nowcast(obs, 12)
    cx = lambda f: (np.nan_to_num(f) * np.arange(W)).sum() / np.nan_to_num(f).sum()
    shift = cx(fc[-1]) - cx(obs[-1])
    assert abs(shift - 12 * SPEED) < 4, shift


def test_cli_end_to_end(tmp_path):
    cache, out = tmp_path / "cache", tmp_path / "out"
    cache.mkdir()
    _write_cache(cache)
    rc = cli.main(["--time", T0.isoformat(), "--cache", str(cache), "--out", str(out), "--hours", "1", "--keep-cache"])
    assert rc == 0
    manifest = json.loads((out / "manifest.json").read_text())
    kinds = [f["kind"] for f in manifest["frames"]]
    assert kinds == ["obs"] * 4 + ["fc"] * 12
    assert manifest["analysis"] == "2026-10-28T19:25:00Z"
    (s, w), (n, e) = manifest["bounds"]
    assert 53 < s < 54.5 and 69.5 < n < 70.5 and 4.5 < w < 6 and 29 < e < 31
    assert all((out / f["file"]).exists() for f in manifest["frames"])
