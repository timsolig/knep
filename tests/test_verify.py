"""Verifieringen: måtten, facit ur radarn, utgåvan, räkningen och verif.json på syntetiska data."""

import json
from datetime import UTC, datetime, timedelta

import numpy as np
from pyproj import Transformer
from rasterio.crs import CRS
from rasterio.transform import from_origin

from knep import verify
from knep.analys import composite
from knep.analys.radar import Grid

STEP = timedelta(minutes=5)
HOUR = timedelta(hours=1)
GRID = Grid(CRS.from_epsg(3006), from_origin(400000, 6600000, 2000, 2000), (40, 60))
T0 = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)


def rain_field(shift=0):
    f = np.zeros(GRID.shape, np.float32)
    f[4:20, 10 + shift:30 + shift] = 3.0
    return f


def smhi(t):
    return np.full(GRID.shape, composite.SOURCE_SMHI, np.uint8)


def test_scores_of_known_tables():
    perfect = np.array([30, 0, 0, 70])
    s = verify.dichotomous(perfect)
    assert s["ets"] == 1 and s["csi"] == 1 and s["far"] == 0 and s["mcc"] == 1 and s["fbi"] == 1 and s["pss"] == 1
    t = np.array([50, 20, 10, 920])  # träff, falsklarm, miss, rätt torrt
    s = verify.dichotomous(t)
    ar = 70 * 60 / 1000
    assert np.isclose(s["ets"], (50 - ar) / (80 - ar))
    assert np.isclose(s["pod"], 50 / 60) and np.isclose(s["far"], 20 / 70) and np.isclose(s["fbi"], 70 / 60)
    assert np.isclose(s["pss"], 50 / 60 - 20 / 940)
    assert np.isclose(s["mcc"], (50 * 920 - 20 * 10) / np.sqrt(70 * 60 * 940 * 930))
    assert -1 <= s["sedi"] <= 1 and s["sedi"] > 0.8
    # inget regn alls: måtten är odefinierade, inte noll
    assert np.isnan(verify.dichotomous(np.array([0, 0, 0, 100]))["ets"])
    c = verify.continuous(np.array([1.0, 2.0, 3.0]), np.array([1.0, 2.0, 5.0]))
    cs = verify.continuous_scores(c)
    assert np.isclose(cs["mae"], 2 / 3) and np.isclose(cs["me"], -2 / 3) and np.isclose(cs["ratio"], 6 / 8)
    assert np.isclose(cs["rmse"], np.sqrt(4 / 3)) and 0.9 < cs["r"] <= 1


def test_fss_perfect_and_disjoint():
    m = np.ones((30, 30), bool)
    a = np.zeros((30, 30), np.float32)
    a[5:10, 5:10] = 2
    b = np.zeros_like(a)
    b[20:25, 20:25] = 2
    assert np.allclose(verify.fss_scores(verify.fss_parts(a, a, m, 4))[:2], 1)  # 4 mm: inget regn, odefinierat
    d = verify.fss_scores(verify.fss_parts(b, a, m, 4))
    assert np.allclose(d[:2, 0], 0) and np.all(d[:2, 2] >= d[:2, 0])  # en större skala hjälper inte disjunkta fält här, men stjälper inte


def test_block_keeps_nan_and_observe_skips_advected(tmp_path):
    f = np.ones(GRID.shape, np.float32)
    f[0, 0] = np.nan
    b = verify.block(f)
    assert b.shape == (20, 30) and np.isnan(b[0, 0]) and b[0, 1] == 1
    src = np.full(GRID.shape, composite.SOURCE_SMHI, np.uint8)
    src[:, :10] = composite.SOURCE_ADVECTED
    frames = [(T0 - k * STEP, rain_field()) for k in range(11, -1, -1)]
    verify.observe(tmp_path, frames, lambda t: src)
    hour = verify.obs_hour(tmp_path, T0)
    assert hour is not None and np.isnan(hour[:, :5]).all() and np.isfinite(hour[:, 5:]).all()
    assert np.isclose(hour[5, 8], 3.0)


def test_hour_waits_for_a_missing_frame_then_accepts_eleven(tmp_path):
    frames = [(T0 - k * STEP, rain_field()) for k in range(11, 0, -1)]  # bilden 12:00 saknas
    verify.observe(tmp_path, frames + [(T0 - 12 * STEP, rain_field())], smhi)
    verify.observe(tmp_path, [(T0 - STEP, rain_field())], smhi)
    assert verify.obs_hour(tmp_path, T0) is None
    verify.observe(tmp_path, [(T0 + 2 * STEP, rain_field())], smhi)  # tio minuter senare: elva bilder räcker
    assert verify.obs_hour(tmp_path, T0) is not None


def _cycle_frames(t0, fc_field):
    obs = [(t0 - k * STEP, "obs", rain_field()) for k in range(11, -1, -1)]
    return obs + [(t0 + (k + 1) * STEP, "fc", fc_field) for k in range(verify.LEADS * 12)]


def _gauges(ends, value):
    x, y = 400000 + 2000 * 20 + 1000, 6600000 - 2000 * 10 - 1000  # mitt i regnet
    lon, lat = Transformer.from_crs("EPSG:3006", "EPSG:4326", always_xy=True).transform(x, y)
    return {"stations": {"1": [lat, lon, "Regnet"], "2": [lat, lon, "Fel"]},
            "60": {verify._iso(e): {"1": value, "2": 500.0} for e in ends}}


def test_issue_score_and_summary(tmp_path):
    vdir, out = tmp_path / "verif", tmp_path / "out"
    out.mkdir()
    # MET Norge: samma rutnät med 4 km, regnet förskjutet 20 km österut
    store = verify.source_dir(vdir)
    vg = verify.vgrid(GRID)
    met_hours = [(T0 + k * HOUR, verify.block(rain_field(10))) for k in (1, 2)]
    verify.store_hours(store, "met_20261103T1145", "2026-11-03T11:45:00Z", T0 - STEP, met_hours, vg)
    verify.store_hours(store, "met_20261103T0500", "2026-11-03T05:00:00Z", T0 - 7 * HOUR, met_hours, vg)  # för gammalt

    frames = _cycle_frames(T0, rain_field())
    assert verify.cycle(vdir, out, GRID, T0, frames, smhi) is None  # inget räknat än
    assert not verify.due(vdir, T0 + STEP)
    meta = json.loads(str(np.load(vdir / "pending" / "20261103T12.npz")["meta"]))
    assert set(meta["refs"]) == {"ours", "persistens", "met"} and meta["refs"]["met"] == "2026-11-03T11:45:00Z"

    # radarn de följande timmarna, som i drift: en cykel var femte minut
    ends = [T0 + k * HOUR for k in range(1, verify.LEADS + 1)]
    t = T0
    while t < ends[-1] + verify.GAUGE_DELAY - STEP:
        t += STEP
        verify.observe(vdir, [(t, rain_field())], smhi)
    (out / "gauges.json").write_text(json.dumps(_gauges(ends, 3.0)))
    # för tidigt: mätarna har inte kommit
    assert verify.score(vdir, GRID, ends[-1] + HOUR, None) == 0
    t += STEP
    v = verify.cycle(vdir, out, GRID, t, [(t, "obs", rain_field())], smhi)
    assert v and v["file"] == "verif.json" and v["windows"] == [7, 30]
    assert not list((vdir / "pending").glob("*.npz"))

    doc = json.loads((out / "verif.json").read_text())
    w = doc["windows"]["7"]
    assert w["issues"] == 1 and w["days"] == 1 and w["obs_hours"] == verify.LEADS
    i1 = verify.THRESHOLDS.index(1.0)
    radar = w["radar"]["models"]
    assert radar["ours"]["scores"]["ets"][0][i1][0] == 1 and radar["persistens"]["scores"]["ets"][4][i1][0] == 1
    assert radar["met"]["hours"] == [1, 1, 0, 0, 0]
    assert radar["met"]["scores"]["ets"][0][i1][0] < 0.6
    assert radar["met"]["scores"]["ets"][2][i1][0] is None  # MET Norge räknar inte så långt
    d = w["radar"]["diff"]["met"]["scores"]["ets"][0][i1]
    assert d[0] < 0 and d[1] is None  # ett dygn: inget intervall
    fss = radar["met"]["fss"][0][verify.FSS_THRESHOLDS.index(1.0)]
    assert fss[0][0] < fss[2][0]  # större skala, högre FSS för det förskjutna fältet
    g = w["gauges"]["models"]
    assert g["ours"]["n"][0] == 1 and g["ours"]["cont"]["mae"][0][0] == 0  # mätaren med 500 mm räknas inte
    assert "radar" in g and g["radar"]["cont"]["mae"][0][0] == 0
    assert w["stations"] == [["1", *_gauges(ends, 3.0)["stations"]["1"], verify.LEADS]]
    assert w["lags"]["met"]["median"] == 15
    assert doc["daily"]["days"] == ["2026-11-03"] and len(doc["daily"]["radar"]["ours"]["ct"][0]) == verify.LEADS
    assert (out / doc["area"]["file"]).exists()


def _a2t_field(scale=1.2):
    f = rain_field() * scale
    f[:2] = np.nan  # utanför täckningen
    return f


def _run(tmp_path, a2t_leads=()):
    """En utgåva T0 räknad som i drift; A2T:s timsummor för ledtiderna a2t_leads. Returnerar verif.json och posten."""
    vdir, out = tmp_path / "verif", tmp_path / "out"
    out.mkdir(parents=True)
    vg = verify.vgrid(GRID)
    verify.store_hours(verify.source_dir(vdir), "met_20261103T1145", "2026-11-03T11:45:00Z", T0 - STEP,
                       [(T0 + k * HOUR, verify.block(rain_field(10))) for k in (1, 2)], vg)
    verify.cycle(vdir, out, GRID, T0, _cycle_frames(T0, rain_field()), smhi)
    ends = [T0 + k * HOUR for k in range(1, verify.LEADS + 1)]
    t = T0
    while t < ends[-1] + verify.GAUGE_DELAY - STEP:
        t += STEP
        verify.observe(vdir, [(t, rain_field())], smhi)
    for k in a2t_leads:
        verify.store_a2t(vdir, ends[k - 1], _a2t_field(), 40 + k, ends[k - 1] + 2 * HOUR)
    (out / "gauges.json").write_text(json.dumps(_gauges(ends, 3.0)))
    t += STEP
    v = verify.cycle(vdir, out, GRID, t, [(t, "obs", rain_field())], smhi)
    return json.loads((out / "verif.json").read_text()), v


def test_a2t_store_overwrites_and_prunes(tmp_path):
    end = T0 + HOUR
    verify.store_a2t(tmp_path, end, _a2t_field(1.0), 10, end + HOUR)
    verify.store_a2t(tmp_path, end, _a2t_field(2.0), 25, end + 2 * HOUR)  # omräkning med fler mätare
    f, n = verify.a2t_hour(tmp_path, end)
    assert n == 25 and f.shape == verify.vgrid(GRID).shape and np.isclose(f[5, 8], 6.0) and np.isnan(f[0, 0])
    assert [p.name for p in verify.a2t_dir(tmp_path).iterdir()] == ["20261103T13.npz"]  # ingen tmp kvar
    verify.store_a2t(tmp_path, end + 13 * HOUR, _a2t_field(), 5, end + 13 * HOUR)
    assert verify.a2t_hour(tmp_path, end) is None and verify.a2t_hour(tmp_path, end + 13 * HOUR) is not None
    assert verify.a2t_hour(tmp_path, end + 2 * HOUR) is None


def test_score_with_a2t_leaves_radar_and_gauges_unchanged(tmp_path):
    without, v0 = _run(tmp_path / "utan")
    with_, v1 = _run(tmp_path / "med", a2t_leads=(1, 2, 4, 5))  # +3 h saknas
    assert "a2t" not in v0 and v1["a2t"] is True
    w0, w1 = without["windows"]["7"], with_["windows"]["7"]
    assert "a2t" not in w0 and "a2t_hours" not in w0 and "a2t" not in without["daily"]
    assert w0["radar"] == w1["radar"] and without["daily"]["radar"] == with_["daily"]["radar"]
    assert w0["obs_hours"] == w1["obs_hours"] == verify.LEADS and w0["gauge_hours"] == w1["gauge_hours"]
    # mätarna: samma tal, och A2T bara som en kandidat till
    g0, g1 = w0["gauges"], w1["gauges"]
    assert set(g1["models"]) == set(g0["models"]) | {"a2t"}
    assert all(g1["models"][k] == g0["models"][k] for k in g0["models"])
    assert all(g1["diff"][k] == g0["diff"][k] for k in g0["diff"])
    assert without["daily"]["gauges"] == {k: v for k, v in with_["daily"]["gauges"].items() if k != "a2t"}
    a = w1["a2t"]["models"]
    assert w1["a2t_hours"] == 4 and a["ours"]["hours"] == [1, 1, 0, 1, 1] and w1["a2t_gauges"] == 43.0
    i1 = verify.THRESHOLDS.index(1.0)
    assert a["ours"]["scores"]["csi"][0][i1][0] == 1  # samma regnområde, 1,2 gånger mer
    assert a["ours"]["cont"]["ratio"][0][0] < 1 and a["ours"]["n"][0] < w1["radar"]["models"]["ours"]["n"][0]
    assert "fss" in a["ours"] and "met" in w1["a2t"]["diff"] and with_["daily"]["a2t"]["ours"]["fss"]


def test_summary_reads_old_days_without_a2t(tmp_path):
    shape = verify.vgrid(GRID).shape
    o = np.random.default_rng(2).gamma(0.5, 2, 500)
    old = verify.Day(tmp_path / "days" / "2026-11-01.npz", shape)
    old.add("radar", "ours", 1, o, o)
    old.meta = {k: v for k, v in old.meta.items() if not k.startswith("a2t")}  # som en fil från före A2T
    old.save()
    new = verify.Day(tmp_path / "days" / "2026-11-02.npz", shape)
    new.add("radar", "ours", 1, o, o)
    new.add("a2t", "ours", 1, o * 0.9, o)
    new.meta["a2t_hours"], new.meta["a2t_n"] = 1, 30
    new.save()
    assert verify.Day(tmp_path / "days" / "2026-11-01.npz", shape).meta["a2t_hours"] == 0
    out = tmp_path / "out"
    v = verify.summary(tmp_path, out, GRID, datetime(2026, 11, 3, 12, tzinfo=UTC))
    doc = json.loads((out / "verif.json").read_text())
    w = doc["windows"]["7"]
    assert v["a2t"] is True and w["a2t_hours"] == 1 and w["a2t"]["models"]["ours"]["hours"][0] == 1
    assert doc["daily"]["a2t"]["ours"]["c"][0][0][0] == 0 and doc["daily"]["a2t"]["ours"]["c"][1][0][0] == 500
    # bara gamla dygn: inget a2t alls
    (tmp_path / "days" / "2026-11-02.npz").unlink()
    v = verify.summary(tmp_path, out, GRID, datetime(2026, 11, 3, 12, tzinfo=UTC))
    doc = json.loads((out / "verif.json").read_text())
    assert "a2t" not in v and "a2t" not in doc["windows"]["7"] and "a2t" not in doc["daily"]


def test_bootstrap_interval_with_several_days(tmp_path):
    shape = (20, 30)
    rng = np.random.default_rng(1)
    for k in range(10):
        day = verify.Day(tmp_path / "days" / f"2026-10-{20 + k:02d}.npz", shape)
        o = rng.gamma(0.5, 2, 2000)
        good, bad = o * rng.lognormal(0, 0.3, o.size), rng.permutation(o)
        for lead in range(1, verify.LEADS + 1):
            day.add("radar", "ours", lead, good, o)
            day.add("radar", "met", lead, bad, o)
            day.add("radar", "ours@met", lead, good, o)
        day.save()
    days = verify._load_days(tmp_path, shape)
    res = verify._window(days)
    i = verify.THRESHOLDS.index(1.0)
    est, lo, hi = res["radar"]["diff"]["met"]["scores"]["ets"][0][i]
    assert lo <= est <= hi and hi < 0  # MET Norges slumpade fält är tydligt sämre
    e, lo, hi = res["radar"]["models"]["ours"]["scores"]["ets"][0][i]
    assert lo <= e <= hi
