"""Omprojicering till Web Mercator, PNG-rutor och manifest för webbsidan.

Kartan finns i tre upplösningar: momentan intensitet var 5:e minut, och summor per kvart och
per timme (för jämförelse med KNEP:s kvartar och SNOW:s timmar). Samma färg betyder samma
medelintensitet i alla tre, så legenden för summorna är intensitetsgränserna gånger periodens längd.
Värdena finns också i en komprimerad fil på radarns rutnät, så att sidan kan rita en tidsserie för
en punkt utan att avkoda färger.

Radaranalysen de senaste tolv timmarna ritas en gång per bild till hist/ (Renderer.history), så att
sidan kan bläddra bakåt utan att varje cykel ritar om allt.
"""

from __future__ import annotations

import gzip
import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
from PIL import Image
from rasterio.transform import array_bounds
from rasterio.warp import Resampling, calculate_default_transform, reproject, transform_bounds

from .analys.radar import Grid

WEB = "EPSG:3857"
MODEL_NAME = "Tim-KNEP"  # namnet på sidan

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


# sannolikhet för kraftig nederbörd: nedre gräns och färg
PROB_LEVELS = [0.1, 0.3, 0.5, 0.7]
PROB_COLORS = np.array([(255, 200, 120, 120), (250, 140, 60, 170), (220, 60, 60, 210), (150, 20, 110, 235)], dtype=np.uint8)


def legend(minutes: int = 5):
    """Färggränser: mm/h för 5 min, mm per period för summorna."""
    f = 1.0 if minutes <= 5 else minutes / 60.0
    return [{"min": round(lvl * f, 3), "color": "rgba({},{},{},{:.2f})".format(*c[:3], c[3] / 255)} for lvl, c in zip(LEVELS, COLORS)]


# radaranalysen bakåt på sidan, i underkatalogen hist/
HISTORY_HOURS, HISTORY_DIR = 12, "hist"
A1_DIR = "a1"  # A1, analysen interpolerad längs rörelsen (analys/a1.py), ritad som hist/
A2_DIR = "a2"  # A2T, A1 rättad mot regnmätarna (analys/a2_cykel.py), bara kvart och timme

UNITS = {5: "mm/h", 15: "mm per 15 min", 60: "mm per timme"}
STEP = timedelta(minutes=5)

# värdefilen: 0 = torrt (under 0,1 mm/h), 255 = saknas, annars 0,1 mm/h gånger 10^((kod - 1) * 0,014)
CODE_BASE, CODE_DB = 0.1, 0.14


def encode_values(r: np.ndarray) -> np.ndarray:
    q = np.zeros(r.shape, np.uint8)
    wet = np.isfinite(r) & (r >= CODE_BASE)
    q[wet] = np.clip(np.round(10 * np.log10(r[wet] / CODE_BASE) / CODE_DB) + 1, 1, 254).astype(np.uint8)
    q[~np.isfinite(r)] = 255
    return q


def decode_values(q: np.ndarray) -> np.ndarray:
    r = np.where(q == 0, 0.0, CODE_BASE * 10 ** ((q.astype(np.float32) - 1) * CODE_DB / 10)).astype(np.float32)
    r[q == 255] = np.nan
    return r


def aggregate(frames, minutes: int):
    """Medelintensitet per period ur 5-minutersrutor: (slut, start, sort, fält), bara hela perioder.

    frames: (tid, sort, fält) där fältet gäller de fem minuterna före tiden. En period med både
    radar och prognos får sorten "mix".
    """
    by_t = {fr[0]: (fr[1], fr[2]) for fr in frames}
    n = minutes // 5
    out = []
    for end in sorted(by_t):
        if (end.minute % minutes if minutes < 60 else end.minute) != 0:
            continue
        ts = [end - k * STEP for k in range(n)]
        if not all(t in by_t for t in ts):
            continue
        kinds = {by_t[t][0] for t in ts}
        field = np.mean([by_t[t][1] for t in ts], axis=0).astype(np.float32)
        out.append((end, end - timedelta(minutes=minutes), kinds.pop() if len(kinds) == 1 else "mix", field))
    return out


def prob_legend():
    return [{"min": lvl, "color": "rgba({},{},{},{:.2f})".format(*c[:3], c[3] / 255)} for lvl, c in zip(PROB_LEVELS, PROB_COLORS)]


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
        self._map = None

    def _lookup(self) -> tuple[np.ndarray, np.ndarray]:
        """Närmaste granne mellan två fasta rutnät: vilken källpixel varje målpixel tar räknas en
        gång, genom att omprojicera pixlarnas nummer, och sedan är varje bild ett uppslag."""
        if self._map is None:
            h, w = self.grid.shape
            src = np.arange(h * w, dtype=np.float64).reshape(h, w)
            dst = np.full(self.shape, np.nan, np.float64)
            reproject(src, dst, src_transform=self.grid.transform, src_crs=self.grid.crs, src_nodata=np.nan,
                      dst_transform=self.transform, dst_crs=WEB, dst_nodata=np.nan,
                      resampling=Resampling.nearest)
            valid = np.isfinite(dst)
            self._map = valid, dst[valid].astype(np.int64)
        return self._map

    def warp(self, field: np.ndarray) -> np.ndarray:
        valid, src = self._lookup()
        out = np.full(self.shape, np.nan, np.float32)
        out[valid] = np.asarray(field, np.float32).ravel()[src]
        return out

    def _png(self, value: np.ndarray, levels, colors, path: Path) -> None:
        """PNG med palett: klass 0 genomskinlig, klass i färgen colors[i - 1] med dess alfa."""
        idx = np.digitize(np.nan_to_num(self.warp(value), nan=0.0), levels).astype(np.uint8)
        pal = np.vstack([np.zeros((1, 4), np.uint8), colors])
        img = Image.fromarray(idx, "P")
        img.putpalette(pal[:, :3].ravel().tolist())
        img.save(path, transparency=bytes(pal[:, 3].tolist()), compress_level=6)

    def png(self, field: np.ndarray, path: Path) -> None:
        self._png(field, LEVELS, COLORS, path)

    def png_prob(self, p: np.ndarray, path: Path) -> None:
        self._png(p, PROB_LEVELS, PROB_COLORS, path)

    def history(self, out: Path, frames: list[tuple], now: datetime, hours: float = HISTORY_HOURS,
                directory: str = HISTORY_DIR) -> dict:
        """Radaranalysen bakåt: varje 5-minutersbild, kvart och timme ritas en gång till hist/ med
        tiden i namnet och ligger kvar i hours timmar. Namnen ändras aldrig, så sidan kan cacha dem.

        frames: (tid, fält) för analyserna i den här cykeln. Kvartar och timmar ritas när alla
        deras bilder finns i frames, så den senaste timmen räcker för att fylla på.
        """
        d = out / directory
        d.mkdir(parents=True, exist_ok=True)
        todo = [(t, "obs", f) for t, f in frames]
        for t, _, f in todo:
            path = d / f"{t:%Y%m%dT%H%M}.png"
            if not path.exists():
                self.png(f, path)
        for minutes, prefix in ((15, "q"), (60, "h")):
            for end, _, _, f in aggregate(todo, minutes):
                path = d / f"{prefix}{end:%Y%m%dT%H%M}.png"
                if not path.exists():
                    self.png(f, path)
        return _listing(d, directory, now, hours)

    def periods(self, out: Path, items: list[tuple], now: datetime, hours: float = HISTORY_HOURS,
                directory: str = A2_DIR) -> dict:
        """Kvarts- och timsummor bakåt som inte byggs ur 5-minutersbilder (A2, analys/a2_cykel.py).

        items: (periodens slut, minuter 15 eller 60, fält i mm/h, märke). Filen heter som i history med
        märket efter: q20261107T1015_n512.png. Ett nytt märke för samma period ersätter det gamla, så
        sidan aldrig ser en gammal bild ur cachen. Listan har samma form som history."""
        d = out / directory
        d.mkdir(parents=True, exist_ok=True)
        for end, minutes, f, tag in items:
            prefix = {15: "q", 60: "h"}[minutes]
            path = d / f"{prefix}{end:%Y%m%dT%H%M}_{tag}.png"
            if not path.exists():
                self.png(f, path)
            for old in d.glob(f"{prefix}{end:%Y%m%dT%H%M}_*.png"):
                if old != path:
                    old.unlink()
        return _listing(d, directory, now, hours)

    def write(self, out: Path, analysis: datetime, frames: list[tuple], extra: dict | None = None) -> None:
        """Skriv PNG per ruta och upplösning, värdefilen och sist manifest.json, så att sidan aldrig
        ser en halv uppdatering.

        frames: (tid, "obs" eller "fc", fält i mm/h[, sannolikhet för minst 10 mm/h]).
        """
        out.mkdir(parents=True, exist_ok=True)
        entries, names = [], set()
        for i, fr in enumerate(frames):
            t, kind, field = fr[:3]
            name = f"{i:02d}.png"
            self.png(field, out / name)
            names.add(name)
            entry = {"time": _iso(t), "kind": kind, "file": name}
            if len(fr) > 3 and fr[3] is not None:
                pname = f"p10_{i:02d}.png"
                self.png_prob(fr[3], out / pname)
                names.add(pname)
                entry["p10"] = pname
            entries.append(entry)
        agg = {}
        for minutes, prefix in ((15, "q"), (60, "h")):
            lst = []
            for i, (end, start, kind, field) in enumerate(aggregate([fr[:3] for fr in frames], minutes)):
                name = f"{prefix}{i:02d}.png"
                self.png(field, out / name)
                names.add(name)
                lst.append({"time": _iso(end), "start": _iso(start), "kind": kind, "file": name})
            agg[minutes] = lst
        codes = np.stack([encode_values(fr[2]) for fr in frames])
        vname = "values.bin.gz"
        with gzip.open(out / (vname + ".tmp"), "wb", compresslevel=6) as fh:
            fh.write(codes.tobytes())
        (out / (vname + ".tmp")).replace(out / vname)
        for old in out.glob("*.png"):
            if old.name not in names:
                old.unlink()
        tr = self.grid.transform
        manifest = {
            "model": MODEL_NAME,
            "analysis": _iso(analysis),
            "generated": _iso(datetime.now(UTC)),
            "step_minutes": 5,
            "bounds": self.bounds,
            "legend": legend(5),
            "legends": {str(m): legend(m) for m in UNITS},
            "units": {str(m): u for m, u in UNITS.items()},
            "prob_legend": prob_legend(),
            "frames": entries,
            "frames15": agg[15],
            "frames60": agg[60],
            "values": {"file": vname, "shape": list(codes.shape), "crs": "EPSG:3006",
                       "west": tr.c, "north": tr.f, "res": tr.a, "base": CODE_BASE, "step_db": CODE_DB,
                       "times": [_iso(fr[0]) for fr in frames]},
        } | (extra or {})
        tmp = out / "manifest.json.tmp"
        tmp.write_text(json.dumps(manifest, indent=1))
        tmp.replace(out / "manifest.json")


def _listing(d: Path, directory: str, now: datetime, hours: float) -> dict:
    """Bilderna bakåt i d som listor per upplösning; de som är äldre än hours (eller efter now) tas bort.
    Ett märke efter tiden (Renderer.periods) är tillåtet."""
    oldest = now - timedelta(hours=hours)
    lists = {5: [], 15: [], 60: []}
    for p in sorted(d.glob("*.png")):
        m = re.fullmatch(r"([qh]?)(\d{8}T\d{4})(?:_\w+)?", p.stem)
        if not m:
            continue
        t = datetime.strptime(m.group(2), "%Y%m%dT%H%M").replace(tzinfo=UTC)
        minutes = {"": 5, "q": 15, "h": 60}[m.group(1)]
        if t - timedelta(minutes=minutes) < oldest or t > now:
            p.unlink()
            continue
        entry = {"time": _iso(t), "kind": "obs", "file": f"{directory}/{p.name}"}
        if minutes > 5:
            entry["start"] = _iso(t - timedelta(minutes=minutes))
        lists[minutes].append(entry)
    return {"hours": hours, "frames": lists[5], "frames15": lists[15], "frames60": lists[60]}
