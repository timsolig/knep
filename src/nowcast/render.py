"""Omprojicering till Web Mercator, PNG-rutor och manifest för webbsidan."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from PIL import Image
from rasterio.transform import array_bounds
from rasterio.warp import Resampling, calculate_default_transform, reproject, transform_bounds

from .radar import Grid

WEB = "EPSG:3857"

# Nedre gräns i mm/h för varje färg. Under första gränsen ritas inget.
LEVELS = [0.1, 0.5, 1, 2, 4, 8, 16, 32]
COLORS = np.array(
    [
        (166, 214, 255, 170),
        (102, 170, 245, 200),
        (40, 110, 220, 215),
        (36, 160, 90, 225),
        (240, 205, 40, 235),
        (245, 135, 30, 240),
        (215, 40, 40, 245),
        (160, 30, 160, 250),
    ],
    dtype=np.uint8,
)


def _iso(t: datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class Renderer:
    def __init__(self, grid: Grid):
        h, w = grid.shape
        west, south, east, north = array_bounds(h, w, grid.transform)
        self.grid = grid
        self.transform, dw, dh = calculate_default_transform(
            grid.crs, WEB, w, h, left=west, bottom=south, right=east, top=north
        )
        self.shape = (dh, dw)
        w_, s_, e_, n_ = transform_bounds(WEB, "EPSG:4326", *array_bounds(dh, dw, self.transform))
        self.bounds = [[round(s_, 5), round(w_, 5)], [round(n_, 5), round(e_, 5)]]

    def warp(self, field: np.ndarray) -> np.ndarray:
        out = np.full(self.shape, np.nan, np.float32)
        reproject(
            field.astype(np.float32),
            out,
            src_transform=self.grid.transform,
            src_crs=self.grid.crs,
            src_nodata=np.nan,
            dst_transform=self.transform,
            dst_crs=WEB,
            dst_nodata=np.nan,
            resampling=Resampling.nearest,
        )
        return out

    def png(self, field: np.ndarray, path: Path) -> None:
        idx = np.digitize(np.nan_to_num(self.warp(field), nan=0.0), LEVELS)
        rgba = np.zeros(idx.shape + (4,), np.uint8)
        rain = idx > 0
        rgba[rain] = COLORS[idx[rain] - 1]
        Image.fromarray(rgba, "RGBA").save(path, optimize=True)

    def write(self, out: Path, analysis: datetime, frames: list[tuple[datetime, str, np.ndarray]]) -> None:
        """Skriv en PNG per ruta och sist manifest.json, så att sidan aldrig ser en halv uppdatering."""
        out.mkdir(parents=True, exist_ok=True)
        entries, names = [], set()
        for i, (t, kind, field) in enumerate(frames):
            name = f"{i:02d}.png"
            self.png(field, out / name)
            names.add(name)
            entries.append({"time": _iso(t), "kind": kind, "file": name})
        for old in out.glob("*.png"):
            if old.name not in names:
                old.unlink()
        manifest = {
            "analysis": _iso(analysis),
            "generated": _iso(datetime.now(UTC)),
            "step_minutes": 5,
            "bounds": self.bounds,
            "legend": [
                {"min": lvl, "color": "rgba({},{},{},{:.2f})".format(*c[:3], c[3] / 255)}
                for lvl, c in zip(LEVELS, COLORS)
            ],
            "frames": entries,
        }
        tmp = out / "manifest.json.tmp"
        tmp.write_text(json.dumps(manifest, indent=1))
        tmp.replace(out / "manifest.json")
