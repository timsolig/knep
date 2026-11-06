"""Röktest med syntetiska kompositer i SMHI:s format: en regncell som rör sig österut."""

import json
from datetime import UTC, datetime

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from knep import cli
from knep.analys import radar
from knep.prognos import model

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
    _write_cache(cache, n=7)
    rc = cli.main(["--time", T0.isoformat(), "--cache", str(cache), "--out", str(out), "--hours", "1", "--keep-cache",
                   "--history", "7", "--no-bias"])
    assert rc == 0
    manifest = json.loads((out / "manifest.json").read_text())
    kinds = [f["kind"] for f in manifest["frames"]]
    assert kinds == ["obs"] * 7 + ["fc"] * 12
    assert manifest["missing_radars"] == [] and manifest["sources"]["smhi"] == 1.0
    assert manifest["analysis"] == "2026-10-28T19:25:00Z"
    (s, w), (n, e) = manifest["bounds"]
    assert 53 < s < 54.5 and 69.5 < n < 70.5 and 4.5 < w < 6 and 29 < e < 31
    assert all((out / f["file"]).exists() for f in manifest["frames"])


def test_chain_moves_and_keeps_peaks():
    obs = np.stack([_rain(k) for k in range(-6, 1)])
    res = model.Chain().run(obs, T0, 12)
    cx = lambda f: (np.nan_to_num(f) * np.arange(W)).sum() / np.nan_to_num(f).sum()
    assert abs(cx(res.rain[-1]) - cx(obs[-1]) - 12 * SPEED) < 4
    # matchningen mot analysens fördelning: toppen smetas inte ut av interpolationen
    assert np.nanmax(res.rain[-1]) > 0.97 * np.nanmax(obs[-1])
    assert res.prob is None


def test_chain_options_for_ablations():
    obs = np.stack([_rain(k) for k in range(-6, 1)])
    base = model.Chain().run(obs, T0, 12)
    # ett förberäknat rörelsefält ger samma prognos
    same = model.Chain().run(obs, T0, 12, motion=base.motion)
    np.testing.assert_array_equal(np.nan_to_num(same.rain), np.nan_to_num(base.rain))
    # utan matchning är det den bilinjära flytten, som smetar ut toppen
    raw = model.Chain(match=False).run(obs, T0, 12, motion=base.motion)
    assert np.nanmax(raw.rain[-1]) < np.nanmax(base.rain[-1])
    # utan platskarta används inte tillståndet
    state = model.State()
    for k in range(12):
        t = T0 - k * model.STEP
        state.obs[t.isoformat()] = obs[-1] * 4
        state.fc30[t.isoformat()] = obs[-1]
    off = model.Chain(location=False).run(obs, T0, 12, state, motion=base.motion)
    np.testing.assert_array_equal(np.nan_to_num(off.rain), np.nan_to_num(base.rain))


def test_chain_projection_options():
    obs = np.stack([_rain(k) for k in range(-6, 1)])
    base = model.Chain().run(obs, T0, 12)
    # standardvärdena är driftens kedja
    same = model.Chain(interp="linear", sharpen=0.0).run(obs, T0, 12, motion=base.motion)
    np.testing.assert_array_equal(np.nan_to_num(same.rain), np.nan_to_num(base.rain))
    lin = model.Chain(match=False).run(obs, T0, 12, motion=base.motion).rain
    a = np.nan_to_num(obs[-1])
    for interp in ("cubic", "nearest"):
        r = model.Chain(interp=interp, match=False).run(obs, T0, 12, motion=base.motion).rain
        # mindre utsmetat än bilinjärt, men inga toppar över analysens och inga negativa värden
        assert np.nanmax(r[-1]) > np.nanmax(lin[-1]) and np.nanmax(r) <= a.max() + 1e-4 and np.nanmin(r) >= 0
    # blandningen med det bilinjära ligger mitt emellan
    cub = model.Chain(interp="cubic", match=False).run(obs, T0, 12, motion=base.motion).rain
    half = model.Chain(interp="cubic", blend=0.5, match=False).run(obs, T0, 12, motion=base.motion).rain
    np.testing.assert_allclose(np.nan_to_num(half), np.nan_to_num(0.5 * cub + 0.5 * lin), atol=1e-4)
    # rampen: bilinjärt till 20 min, sedan gradvis till den bikubiska vid 40 min
    ramp = model.Chain(interp="cubic", ramp=(20, 40), match=False).run(obs, T0, 12, motion=base.motion).rain
    np.testing.assert_allclose(np.nan_to_num(ramp[:4]), np.nan_to_num(lin[:4]), atol=1e-5)
    np.testing.assert_allclose(np.nan_to_num(ramp[5]), np.nan_to_num(0.5 * cub[5] + 0.5 * lin[5]), atol=1e-4)
    np.testing.assert_allclose(np.nan_to_num(ramp[8:]), np.nan_to_num(cub[8:]), atol=1e-5)
    # skärpt rangordning: samma värden som kedjan (ur målet), annan placering
    sh = model.Chain(sharpen=2.0).run(obs, T0, 12, motion=base.motion).rain
    np.testing.assert_allclose(np.sort(sh[-1][np.isfinite(sh[-1])]), np.sort(base.rain[-1][np.isfinite(base.rain[-1])]), rtol=1e-5)
    with pytest.raises(ValueError):
        model.Chain(interp="spline")


def test_fill_outside_and_inflow():
    a = np.full((20, 30), np.nan, np.float32)
    a[:, 10:] = 4.0
    # standard: nollor utanför täckningen, som nan_to_num i drift
    np.testing.assert_array_equal(model.fill_outside(a), np.nan_to_num(a))
    f = model.fill_outside(a, decay=5.0)
    np.testing.assert_array_equal(f[:, 10:], a[:, 10:])
    # randvärdet avtar med avståndet från täckningen
    assert np.allclose(f[10, 9], 4.0 * np.exp(-1 / 5), rtol=1e-3) and f[10, 0] < f[10, 5] < f[10, 9]
    # kedjan med inflödet: regn flyttas in över randen där kedjan annars har nollor
    obs = np.stack([np.where(np.arange(30) >= 10, 4.0, np.nan)[None, :].repeat(20, 0)] * 7).astype(np.float32)
    motion = np.zeros((2, 20, 30))
    motion[0] = 1.0  # en pixel per steg åt höger
    base = model.Chain(match=False, location=False).run(obs, T0, 6, motion=motion).rain
    inn = model.Chain(match=False, location=False, inflow=50.0).run(obs, T0, 6, motion=motion).rain
    assert np.nanmin(base[-1][:, 10:13]) == 0.0 and np.nanmin(inn[-1][:, 10:13]) > 3.0


def test_chain_stay_keeps_terrain_rain():
    """Med stay står en andel still där vinden blåser uppför; utan terräng och fel flyttas allt."""
    obs = np.zeros((7, 20, 40), np.float32)
    obs[:, 8:12, 18:22] = 8.0
    motion = np.zeros((2, 20, 40))
    motion[0] = 1.0
    terrain = np.tile(np.arange(40, dtype=np.float32) * 50.0, (20, 1))  # stiger åt höger, med vinden
    base = model.Chain(match=False, location=False).run(obs, T0, 6, motion=motion).rain
    flat = model.Chain(match=False, location=False, stay=(0.8, 1.0, 0.0, 1e9),
                       terrain=np.zeros_like(terrain)).run(obs, T0, 6, motion=motion).rain
    np.testing.assert_allclose(flat, base, atol=1e-5)
    hill = model.Chain(match=False, location=False, stay=(0.8, 1.0, 0.0, 1e9), terrain=terrain)
    s = hill.stay_fraction(motion, np.zeros((20, 40), np.float32))
    assert 0.79 < s[10, 20] <= 0.8
    out = hill.run(obs, T0, 6, motion=motion).rain
    assert out[-1][10, 20] > 6.0 and base[-1][10, 20] == 0.0
    np.testing.assert_allclose(np.nansum(out[-1]), np.nansum(base[-1]), rtol=1e-3)  # volymen kvar
    hill.stay_target = "whole"  # målet ur det odelade fältet, som i kedjan
    a = obs[-1]
    np.testing.assert_array_equal(hill.project(a, motion, 6, s)[1], hill.project(a, motion, 6)[1])


def test_location_map_learns_a_stationary_bias():
    """En plats där radarn alltid ser 3 dB mer än prognosen ska få en positiv korrektion."""
    state = model.State()
    shape = (60, 80)
    base = np.full(shape, 2.0, np.float32)
    obs = base.copy()
    obs[20:40, 30:50] *= 10 ** 0.3
    for k in range(12):
        t = T0 - k * model.STEP
        state.obs[t.isoformat()] = obs
        state.fc30[t.isoformat()] = base
    corr = model.location_map(state, T0, shape)
    assert corr[30, 40] > 2.0 and abs(corr[5, 5]) < 0.5


def test_state_roundtrip(tmp_path):
    s = model.State()
    s.obs[T0.isoformat()] = np.ones((4, 5), np.float32)
    s.fc30[T0.isoformat()] = np.full((4, 5), 2.0, np.float32)
    s.save(tmp_path / "m.npz")
    r = model.State.load(tmp_path / "m.npz")
    assert np.allclose(r.fc30[T0.isoformat()], 2.0) and list(r.obs) == [T0.isoformat()]


def test_cli_applies_volume_correction(tmp_path):
    from knep import render
    from knep.analys import bias, composite

    cache, out = tmp_path / "cache", tmp_path / "out"
    cache.mkdir()
    _write_cache(cache, n=7)
    grid = composite.TargetGrid(WEST + RES / 2 - RES / 2, NORTH, RES, (H, W))
    coef = np.zeros((12, 3))
    coef[:, 0] = np.log(1.5)
    path = tmp_path / "bias.npz"
    bias.Correction(coef, np.zeros((H, W), np.float32), bias.beam_height(grid)).save(path)
    rc = cli.main(["--time", T0.isoformat(), "--cache", str(cache), "--out", str(out), "--hours", "1", "--keep-cache",
                   "--history", "7", "--bias", str(path)])
    assert rc == 0
    m = json.loads((out / "manifest.json").read_text())
    assert abs(m["volume_correction"]["median"] - 1.5) < 0.01
    import gzip

    codes = np.frombuffer(gzip.decompress((out / m["values"]["file"]).read_bytes()), np.uint8).reshape(m["values"]["shape"])
    analysis = render.decode_values(codes[6])
    truth = _rain(0)
    inside = np.isfinite(analysis) & (truth > 2)
    assert np.allclose(analysis[inside], 1.5 * truth[inside], rtol=0.12)


def test_analysis_times_follow_missing_frames(tmp_path):
    """Saknas en bild mitt i och finns inget utfyllnadstillstånd, får de äldre analyserna ändå rätt tid.

    Det händer när äldre analyser redan är sparade men gaps.npz saknas, och då hoppas tiden över.
    """
    import requests

    from knep import analys

    class Offline(requests.Session):
        def get(self, *a, **k):
            raise requests.ConnectionError("offline")

    cache, state = tmp_path / "cache", tmp_path / "state"
    cache.mkdir()
    state.mkdir()
    _write_cache(cache, n=7)
    analys.bygg(T0, 7, cache, state, Offline())  # sparar analyserna och gaps.npz
    gone = T0 - 3 * radar.STEP
    (cache / f"{gone:%Y%m%d%H%M}.tif").unlink()
    for p in [state / "gaps.npz", *state.glob(f"analys_{gone:%Y%m%d%H%M}.npz"),
              *(state / f"analys_{t:%Y%m%d%H%M}.npz" for t in (T0 - k * radar.STEP for k in range(3)))]:
        p.unlink()
    a = analys.bygg(T0, 7, cache, state, Offline())
    assert len(a.times) == len(a.rain) == 6
    assert gone not in a.times and a.times[0] == T0 - 6 * radar.STEP and a.times[-1] == T0
