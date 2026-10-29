"""Händelsebyggaren på syntetiska data: rutor, poäng och index utan nätverk."""

import json
from datetime import UTC, datetime, timedelta

import numpy as np
from rasterio.crs import CRS
from rasterio.transform import from_origin

from knep import cases, model, radar

H, W = 120, 160
T0 = datetime(2023, 8, 8, 12, 0, tzinfo=UTC)


def _rain(t):
    k = int((t - T0) / timedelta(minutes=5))
    y, x = np.mgrid[0:H, 0:W]
    r = 30.0 * np.exp(-(((x - 30 - 2 * k) / 9.0) ** 2 + ((y - 60) / 7.0) ** 2))
    r[r < 0.05] = 0.0
    return r.astype(np.float32)


def test_build_writes_frames_scores_and_index(tmp_path):
    ev = cases.Event("prov", "Provhändelse", T0, T0 + timedelta(minutes=75), "regn", "Syntetisk cell.")
    grid = radar.Grid(CRS.from_epsg(3006), from_origin(400000, 6500000, 2000, 2000), (H, W))
    frames = lambda ts: [_rain(t) for t in ts]
    m = cases.build(ev, frames, grid, tmp_path / "prov", model.Chain())
    want = {"5": {"radar", "kedja30", "proxy30"}, "15": {"radar", "kedja30", "proxy30", "kedja60"}, "60": {"radar", "kedja", "proxy"}}
    for r, layers in want.items():
        fr = m["res"][r]
        assert layers <= set().union(*(f.keys() for f in fr)), r
        assert all((tmp_path / "prov" / f[k]).exists() for f in fr for k in f if k != "time")
    assert len(m["res"]["5"]) > 3 * len(m["res"]["15"]) - 3
    # en cell som bara flyttar sig är lätt för båda; poängen ska finnas och vara höga i alla upplösningar
    for r, h in (("5", "15"), ("15", "15"), ("60", "60")):
        s = m["scores"][r]["systems"]
        assert s["Ny kedja"]["ETS 1 mm/h"][h] > 0.7 and s["KNEP-proxy"]["ETS 1 mm/h"][h] > 0.5, r
        assert 0.7 < s["Ny kedja"]["Volym"][h] < 1.3
    assert m["legends"]["15"][0]["min"] < m["legends"]["5"][0]["min"]
    assert m["series"][0]["max"] > 20 and m["series"][0]["saknas"] == 0.0
    idx = cases.write_index(tmp_path)
    assert idx[0]["path"] == "prov" and json.loads((tmp_path / "index.json").read_text())[0]["name"] == "Provhändelse"


def test_known_events_are_defined():
    assert {"hans-2023", "anna-2026", "gavle-2021"} <= set(cases.EVENTS)
    for e in cases.EVENTS.values():
        assert e.start < e.end and e.links
