"""Den sömlösa modellen på syntetiska fält (inget nätverk)."""

import numpy as np

from knep import seamless

H, W = 200, 160


def _blob(cx, cy, amp=8.0, r=12.0):
    y, x = np.mgrid[:H, :W]
    return (amp * np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2 * r * r))).astype(np.float32)


def test_weight_goes_from_chain_to_meps():
    assert seamless.weight(0, 60, 2.5) == 1.0
    assert abs(seamless.weight(60, 60, 2.5) - 0.5) < 1e-9
    assert seamless.weight(300, 60, 2.5) < 0.02


def test_shift_estimate_moves_meps_onto_radar():
    radar = _blob(80, 100) + _blob(40, 50, 5)
    meps = _blob(92, 92) + _blob(52, 42, 5)   # 12 px österut och 8 px norrut (uppåt i bilden)
    p = seamless.Params()
    dx, dy = seamless.estimate_shift(meps, radar, p)
    moved = seamless.shift(meps, dx, dy)
    err = lambda a: float(np.abs(a - radar).sum())
    assert err(moved) < 0.5 * err(meps)
    assert 6 < np.median(dx[90:110, 70:90]) < 16 and -12 < np.median(dy[90:110, 70:90]) < -3


def test_amount_mapping_scales_meps_to_radar():
    radar = _blob(80, 100, 10)
    meps = 2 * radar
    qm = seamless.estimate_amount(meps, radar)
    out = seamless.apply_amount(meps, qm)
    assert abs(out.sum() / radar.sum() - 1) < 0.05


def test_blend_endpoints_and_outside_radar():
    chain = _blob(80, 100)
    chain[:, :20] = np.nan                   # utanför radarns täckning
    meps = _blob(60, 60)
    p = seamless.Params(match=False)
    early = seamless.blend(chain, meps, 0, p)
    assert np.allclose(early[:, 20:], chain[:, 20:], atol=1e-4)
    late = seamless.blend(chain, meps, 600, p)
    assert np.abs(late - meps).max() < 0.15
    assert np.isfinite(early[:, :20]).all() and np.allclose(early[:, :20], meps[:, :20], atol=0.2)


def test_matched_blend_keeps_the_peak():
    chain, meps = _blob(80, 100, 10), _blob(70, 90, 10)
    plain = seamless.blend(chain, meps, 90, seamless.Params(match=False))
    matched = seamless.blend(chain, meps, 90, seamless.Params())
    assert plain.max() < 9.5 and matched.max() > 9.5


def test_assimilation_resets_with_a_new_run():
    radar, meps = _blob(80, 100), _blob(90, 100)
    p = seamless.Params()
    st = seamless.assimilate(seamless.State(), "a", meps, radar, p)
    st2 = seamless.assimilate(st, "a", meps, radar, p)
    assert np.allclose(st2.dx, st.dx, atol=1e-3)  # samma skattning: medlet ändras inte
    st3 = seamless.assimilate(st2, "b", meps * 0, radar, p)
    assert st3.run == "b"


def test_meps_at_interpolates_between_hour_centres():
    from datetime import UTC, datetime, timedelta

    run = datetime(2026, 7, 1, 12, tzinfo=UTC)
    on = np.stack([np.full((4, 4), v, np.float32) for v in (0.0, 2.0, 4.0)])
    at = lambda m: float(seamless.meps_at(on, run, run + timedelta(minutes=m))[0, 0])
    assert at(30) == 0.0 and at(90) == 2.0 and abs(at(60) - 1.0) < 1e-6   # mitt i timmarna och mellan dem
    assert at(170) == 4.0 and np.isnan(seamless.meps_at(on, run, run + timedelta(hours=4))[0, 0])
    assert float(seamless.meps_at(on, run, run + timedelta(minutes=60), interpolate=False)[0, 0]) == 0.0


def test_run_operational_blends_and_keeps_state(tmp_path, monkeypatch):
    from datetime import UTC, datetime

    from rasterio.crs import CRS
    from rasterio.transform import from_origin

    from knep import nwp
    from knep.radar import Grid

    grid = Grid(CRS.from_epsg(3006), from_origin(400000, 6800000, 2000, 2000), (H, W))
    run_t = datetime(2026, 7, 1, 9, tzinfo=UTC)
    now = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)
    meps_field = _blob(60, 60)

    class FakeRun(nwp.Run):
        def on(self, target):
            return np.stack([meps_field] * len(self.hourly))
    monkeypatch.setattr(nwp, "latest_run", lambda s: run_t)
    monkeypatch.setattr(nwp, "box", lambda g: ((0, 10), (0, 10)))
    monkeypatch.setattr(nwp, "fetch", lambda s, r, rows, cols: FakeRun(r, np.zeros((11, 10, 10), np.float32), rows, cols))
    obs = np.stack([_blob(80, 100)] * 12)
    fc = np.stack([_blob(80, 100)] * 60)
    out, info = seamless.run_operational(tmp_path / "meps", tmp_path / "st.npz", None, grid, now, obs, fc)
    assert out.shape == fc.shape and info["hours"] == 5 and info["meps_run"] == "2026-07-01T09:00:00Z"
    assert np.allclose(out[0], fc[0], atol=0.5)                       # först nästan bara kedjan
    assert np.abs(out[-1] - fc[-1]).sum() > np.abs(out[0] - fc[0]).sum()  # sedan mer av MEPS
    st = seamless.load_state(tmp_path / "st.npz")
    assert st.run == run_t.isoformat() and st.dx is not None and st.qm is not None
