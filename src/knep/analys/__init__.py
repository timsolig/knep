"""Tim-KNEP analys: nederbörden som den är nu, ur radarn och regnmätarna.

Analysen är en egen produkt, skild från prognosen. Den byggs bild för bild ur SMHI:s komposit;
där den saknar data och pixeln brukar ha data läggs OPERA-kompositen på (om reserven är på),
sedan en egen komposit av de närmaste radarvolymerna och sist förra analysen flyttad med
rörelsen (composite.fill_gaps). Därefter volymkorrigeras den mot regnmätarna om en låst karta
finns (bias.py). Prognosen (knep.prognos) läser bara det som `bygg` returnerar.

Modulerna: radar.py (SMHI:s komposit), composite.py och sources.py (kompositen och reserverna),
bias.py (volymkorrektionen) och gauges.py (regnmätarna till sidan).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np
import requests

from . import bias, composite, radar

log = logging.getLogger("knep")


@dataclass
class Analys:
    """Analyserna bakåt från t0, äldst först, i mm/h på radarns rutnät."""

    t0: datetime
    times: list[datetime]
    rain: np.ndarray  # (bilder, rader, kolumner)
    grid: radar.Grid
    sources: np.ndarray | None  # källkoden per pixel för senaste bilden (composite.SOURCE_*)
    missing: list[str]  # svenska radarer som saknas i senaste bilden
    extra: dict = field(default_factory=dict)  # till manifestet, t.ex. volume_correction

    def share(self) -> dict[str, float]:
        """Andelen av de uppmätta pixlarna per källa i senaste bilden."""
        if self.sources is None:
            return {}
        valid = self.sources != composite.SOURCE_NONE
        out = {}
        for name, code in (("smhi", composite.SOURCE_SMHI), ("opera", composite.SOURCE_OPERA),
                           ("volymer", composite.SOURCE_VOLUME), ("flyttad", composite.SOURCE_ADVECTED)):
            out[name] = round(float((self.sources == code).sum() / max(valid.sum(), 1)), 4)
        return out


def target(grid: radar.Grid) -> composite.TargetGrid:
    return composite.TargetGrid(grid.transform.c, grid.transform.f, grid.transform.a, grid.shape)


def _analyses(times, cache, state_dir, session, fallback):
    """Analyser för times (äldst först): sparade om de redan byggts, annars SMHI plus reserv och utfyllnad.

    Returnerar också tiderna för de analyser som finns, eftersom en tid hoppas över när SMHI-bilden
    saknas och det inte finns något utfyllnadstillstånd.
    """
    out, kept, grid, sources, missing = [], [], None, None, []
    gap = composite.GapState.load(state_dir / "gaps.npz")
    motion_path = state_dir / "motion.npy"
    motion = np.load(motion_path) if motion_path.exists() else None
    for t in times:
        saved = state_dir / f"analys_{t:%Y%m%d%H%M}.npz"
        try:
            rain, g = radar.read_rain(radar.fetch(t, cache, session))
            grid = g
        except requests.RequestException as e:
            log.warning("saknar SMHI-bild %s: %s", t, e)
            rain = None
        if saved.exists():
            d = np.load(saved)
            out.append(d["rain"])
            kept.append(t)
            sources = d["source"]
            continue
        if rain is None and gap is None:
            continue
        if rain is None:
            rain = np.full(gap.analysis.shape, np.nan, np.float32)
        src = np.where(np.isfinite(rain), composite.SOURCE_SMHI, composite.SOURCE_NONE).astype(np.uint8)
        hole = ~np.isfinite(rain) & (gap.expected >= 0.5) if gap is not None else None
        if fallback and hole is not None and hole.any() and grid is not None:
            from . import sources as srcs
            tgt = target(grid)
            path = srcs.fetch_opera(session, t, cache)
            if path is not None:
                try:
                    rain, src = composite.layer(rain, src, srcs.read_opera(path, tgt), composite.SOURCE_OPERA)
                except (OSError, KeyError, ValueError) as e:
                    log.warning("kunde inte läsa OPERA %s: %s", t, e)
            hole = ~np.isfinite(rain) & (gap.expected >= 0.5)
            if hole.any():
                # egen komposit av de närmaste radarerna som når hålet, med förlängd räckvidd
                down = set(composite.missing_radars(rain, tgt, gap.expected))
                sites = srcs.radars_covering(hole, tgt, 320.0, exclude=down)[:4]
                vol, _, used = srcs.volume_composite(session, t, tgt, cache, sites, max_range_km=320.0)
                if vol is not None:
                    rain, src = composite.layer(rain, src, vol, composite.SOURCE_VOLUME)
                    log.info("fyllde bortfall med volymer från %s", ", ".join(used))
        if grid is not None:
            missing = composite.missing_radars(rain, target(grid), gap.expected if gap else np.ones(rain.shape, np.float32))
        rain, src, _, gap = composite.fill_gaps(rain, src, gap, motion)
        np.savez_compressed(saved, rain=rain.astype(np.float32), source=src)
        out.append(rain)
        kept.append(t)
        sources = src
    if gap is not None:
        gap.save(state_dir / "gaps.npz")
    return out, kept, grid, sources, missing


def bygg(t0: datetime, history: int, cache: Path, state_dir: Path, session: requests.Session, *,
         fallback: bool = False, bias_path: Path | None = None, collect: bool = False) -> Analys | None:
    """Analyserna för de `history` senaste bilderna fram till t0, eller None om för få finns.

    bias_path: låst karta för volymkorrektionen (None stänger av). collect: samla radarns värden
    vid mätarna och räkna veckofaktorn (bara i realtid, eftersom den hämtar senaste timmens mätare).
    """
    times = [t0 - k * radar.STEP for k in range(history)][::-1]
    fields, kept, grid, sources, missing = _analyses(times, cache, state_dir, session, fallback)
    if len(fields) < 2 or grid is None:
        log.error("för få radarbilder bakåt från %s", t0)
        return None
    rain = np.stack(fields)
    extra = {}
    if bias_path is not None:
        if collect:
            try:
                bias.Operational(cache / "bias", bias_path).step(session, t0, rain[-1], sources, target(grid))
            except Exception as e:  # noqa: BLE001  insamlingen får aldrig stoppa prognosen
                log.warning("volyminsamling: %s", e)
        corr = bias.Correction.load(bias_path)
        week = bias.load_week(cache / "bias")
        if corr is not None and week is not None:
            corr.mfb, corr.mfb_time = week
        if corr is not None and corr.beam.shape == rain.shape[1:]:
            k = corr.factor(t0)
            rain = corr.apply(rain, t0)
            cov = np.isfinite(rain[-1])
            extra["volume_correction"] = {"median": round(float(np.median(k[cov])), 3) if cov.any() else 1.0,
                                          "week": round(float(np.exp(corr.mfb)), 3), "tail_gamma": round(corr.gamma, 3)}
    return Analys(t0, kept, rain, grid, sources, missing, extra)


def source_of(state_dir: Path, t: datetime) -> np.ndarray | None:
    """Källkoderna per pixel för analysen t, ur det sparade tillståndet."""
    p = state_dir / f"analys_{t:%Y%m%d%H%M}.npz"
    try:
        return np.load(p)["source"] if p.exists() else None
    except (OSError, KeyError, ValueError):
        return None


def rensa(cache: Path, state_dir: Path, keep: int) -> None:
    """Ta bort radarbilder och sparade analyser utom de `keep` senaste."""
    for directory, pattern in ((cache, "*.tif"), (state_dir, "analys_*.npz")):
        for p in sorted(directory.glob(pattern))[:-keep]:
            p.unlink()
