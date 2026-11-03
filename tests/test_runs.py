"""Tidigare utgåvor: en per timme, bara timmarna efter utgåvan, och borttagning efter fönstret."""

import json
from datetime import UTC, datetime, timedelta

import numpy as np
from rasterio.crs import CRS
from rasterio.transform import from_origin

from knep import radar, render, runs

STEP = timedelta(minutes=5)


def setup(tmp_path):
    grid = radar.Grid(CRS.from_epsg(3006), from_origin(400000, 6500000, 2000, 2000), (20, 30))
    (tmp_path / "snow").mkdir()
    (tmp_path / "snow" / "h13.png").write_bytes(b"png")
    (tmp_path / "snow" / "h12.png").write_bytes(b"png")
    compare = {"bounds": [[0, 0], [1, 1]], "snow": {"bounds": [[1, 2], [3, 4]], "reference": "2026-11-03T11:45:00Z", "frames60": [
        {"time": "2026-11-03T12:00:00Z", "start": "2026-11-03T11:00:00Z", "file": "snow/h12.png"},
        {"time": "2026-11-03T13:00:00Z", "start": "2026-11-03T12:00:00Z", "file": "snow/h13.png"}]}}
    return render.Renderer(grid), compare


def frames_at(t0, hours=2):
    f = np.full((20, 30), 2.0, np.float32)
    return [(t0 - k * STEP, "obs", f) for k in range(11, -1, -1)] + [(t0 + (k + 1) * STEP, "fc", f) for k in range(hours * 12)]


def test_archive_keeps_hours_after_issue_and_copies_sources(tmp_path):
    rend, compare = setup(tmp_path)
    t0 = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)
    assert runs.due(tmp_path, t0)
    run = runs.archive(tmp_path, rend, t0, frames_at(t0), compare)
    assert [f["time"] for f in run["models"]["ours"]["frames60"]] == ["2026-11-03T13:00:00Z", "2026-11-03T14:00:00Z"]
    assert [f["file"] for f in run["models"]["snow"]["frames60"]] == ["runs/20261103T1200/snow_h13.png"]
    assert "bounds" not in run["models"]
    for f in run["models"]["ours"]["frames60"] + run["models"]["snow"]["frames60"]:
        assert (tmp_path / f["file"]).exists()
    # samma timme sparas bara en gång, och inte långt efter heltimmen
    assert not runs.due(tmp_path, t0 + STEP)
    assert not runs.due(tmp_path, t0 + timedelta(minutes=80))
    assert runs.due(tmp_path, t0 + timedelta(minutes=65))


def test_listing_newest_first_and_drops_old(tmp_path):
    rend, compare = setup(tmp_path)
    t0 = datetime(2026, 11, 3, 0, 0, tzinfo=UTC)
    for h in range(0, 15, 1):
        t = t0 + timedelta(hours=h)
        runs.archive(tmp_path, rend, t, frames_at(t, 1), compare)
    now = t0 + timedelta(hours=14)
    lst = runs.listing(tmp_path, now, hours=12)
    assert lst[0]["issued"] == "2026-11-03T14:00:00Z" and lst[-1]["issued"] == "2026-11-03T02:00:00Z" and len(lst) == 13
    assert len(list((tmp_path / "runs").iterdir())) == 13
    assert json.loads((tmp_path / "runs" / "20261103T1400" / "run.json").read_text())["issued"] == lst[0]["issued"]
