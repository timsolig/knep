"""Rendering: summor per kvart och timme, värdefilen och manifestet."""

import gzip
import json
from datetime import UTC, datetime, timedelta

import numpy as np
from rasterio.crs import CRS
from rasterio.transform import from_origin

from knep import radar, render

T0 = datetime(2024, 7, 1, 12, 5, tzinfo=UTC)


def test_values_roundtrip_within_four_percent():
    r = np.array([np.nan, 0.0, 0.05, 0.1, 1.0, 7.3, 55.0, 300.0], np.float32)
    back = render.decode_values(render.encode_values(r))
    assert np.isnan(back[0]) and back[1] == 0 and back[2] == 0
    assert np.allclose(back[3:], r[3:], rtol=0.04)


def test_write_aggregates_whole_periods(tmp_path):
    grid = radar.Grid(CRS.from_epsg(3006), from_origin(400000, 6500000, 2000, 2000), (40, 50))
    frames = []
    for k in range(-11, 25):
        t = T0 + k * timedelta(minutes=5)
        frames.append((t, "obs" if k <= 0 else "fc", np.full((40, 50), 6.0 if k <= 0 else 2.0, np.float32)))
    render.Renderer(grid).write(tmp_path, T0, frames)
    m = json.loads((tmp_path / "manifest.json").read_text())
    q = m["frames15"]
    assert all(datetime.fromisoformat(f["time"].replace("Z", "+00:00")).minute % 15 == 0 for f in q)
    assert {f["kind"] for f in q} == {"obs", "mix", "fc"}  # kvarten 12:00 till 12:15 blandar radar och prognos
    h = m["frames60"]
    # bara hela timmar: 12:00 saknar bilden 11:05, 13:00 börjar med analysen 12:05
    assert [(f["time"], f["kind"]) for f in h] == [("2024-07-01T13:00:00Z", "mix"), ("2024-07-01T14:00:00Z", "fc")]
    assert m["legends"]["60"][2]["min"] == 1 and m["units"]["15"] == "mm per 15 min"
    codes = np.frombuffer(gzip.decompress((tmp_path / m["values"]["file"]).read_bytes()), np.uint8).reshape(m["values"]["shape"])
    assert codes.shape == (36, 40, 50)
    assert np.allclose(render.decode_values(codes[0]), 6.0, rtol=0.04)
    assert all((tmp_path / f["file"]).exists() for f in q + h)
