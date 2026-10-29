"""En prognoscykel: hämta radar, bygg kompositen, prognostisera, rendera.

Kompositen fyller radarbortfall med OPERA-kompositen (om --fallback) och annars med
förra analysen flyttad med rörelsen. Analysen volymkorrigeras mot regnmätarna om
models/bias.npz finns (se bias.py); radarns timsummor vid mätarna samlas varje cykel, och
en gång per dygn räknas veckofaktorn och en kandidat till ny karta. Modellen är kedjan i model.Chain, med sannolikheter
för kraftig nederbörd om models/extremes.pkl finns.

Till mosaiken på sidan hämtas också MET Norges nowcast och SMHI:s SNOW som kartor (compare.py).

Avslutar med kod 75 när det inte finns någon ny radarbild att räkna på.
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import requests

from . import bias, compare, composite, model, models, radar, render

NO_NEW_DATA = 75
log = logging.getLogger("knep")


def _parse_time(s: str) -> datetime:
    t = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return t.replace(tzinfo=UTC) if t.tzinfo is None else t.astimezone(UTC)


def _previous_analysis(out: Path) -> datetime | None:
    try:
        return _parse_time(json.loads((out / "manifest.json").read_text())["analysis"])
    except (FileNotFoundError, KeyError, ValueError):
        return None


def _wait_for_new(session: requests.Session, previous: datetime | None, wait: int) -> datetime | None:
    deadline = time.monotonic() + wait
    while True:
        t0 = radar.latest_time(session)
        if previous is None or t0 > previous:
            return t0
        if time.monotonic() > deadline:
            return None
        time.sleep(15)


def _target(grid: radar.Grid) -> composite.TargetGrid:
    return composite.TargetGrid(grid.transform.c, grid.transform.f, grid.transform.a, grid.shape)


def _analyses(times, cache, state_dir, session, fallback):
    """Analyser för times (äldst först): sparade om de redan byggts, annars SMHI plus reserv och utfyllnad."""
    out, grid, sources, missing = [], None, None, []
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
            target = _target(grid)
            path = srcs.fetch_opera(session, t, cache)
            if path is not None:
                try:
                    rain, src = composite.layer(rain, src, srcs.read_opera(path, target), composite.SOURCE_OPERA)
                except (OSError, KeyError, ValueError) as e:
                    log.warning("kunde inte läsa OPERA %s: %s", t, e)
            hole = ~np.isfinite(rain) & (gap.expected >= 0.5)
            if hole.any():
                # egen komposit av de närmaste radarerna som når hålet, med förlängd räckvidd
                down = set(composite.missing_radars(rain, target, gap.expected))
                sites = srcs.radars_covering(hole, target, 320.0, exclude=down)[:4]
                vol, _, used = srcs.volume_composite(session, t, target, cache, sites, max_range_km=320.0)
                if vol is not None:
                    rain, src = composite.layer(rain, src, vol, composite.SOURCE_VOLUME)
                    log.info("fyllde bortfall med volymer från %s", ", ".join(used))
        if grid is not None:
            missing = composite.missing_radars(rain, _target(grid), gap.expected if gap else np.ones(rain.shape, np.float32))
        rain, src, _, gap = composite.fill_gaps(rain, src, gap, motion)
        np.savez_compressed(saved, rain=rain.astype(np.float32), source=src)
        out.append(rain)
        sources = src
    if gap is not None:
        gap.save(state_dir / "gaps.npz")
    return out, grid, sources, missing


def _prune(directory: Path, pattern: str, keep: int) -> None:
    for p in sorted(directory.glob(pattern))[:-keep]:
        p.unlink()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="knep", description=__doc__)
    p.add_argument("--out", type=Path, default=Path("out/data"), help="katalog för PNG-rutor och manifest")
    p.add_argument("--cache", type=Path, default=Path("cache"), help="katalog för hämtade radarbilder och tillstånd")
    p.add_argument("--hours", type=float, default=2.0, help="prognoslängd i timmar")
    p.add_argument("--history", type=int, default=12, help="antal radarbilder bakåt (minst 7 för rörelsen, 12 ger en hel timme på kartan)")
    p.add_argument("--time", type=_parse_time, help="analystid i UTC (ISO 8601); standard är senaste bilden")
    p.add_argument("--wait", type=int, default=120, help="sekunder att vänta på en ny radarbild")
    p.add_argument("--model", type=Path, default=Path("models/extremes.pkl"), help="tränad extremkalibrering")
    p.add_argument("--prob-hours", type=float, default=2.0, help="timmar med sannolikheter för kraftig nederbörd")
    p.add_argument("--bias", type=Path, default=Path("models/bias.npz"), help="volymkorrektion mot regnmätarna")
    p.add_argument("--no-bias", action="store_true", help="ingen volymkorrektion och ingen insamling")
    p.add_argument("--fallback", action="store_true", help="fyll radarbortfall med OPERA-kompositen")
    p.add_argument("--reference", action="store_true", help="kör referensmodellen i stället för kedjan")
    p.add_argument("--keep-cache", action="store_true", help="rensa inte gamla radarbilder")
    p.add_argument("--no-compare", action="store_true", help="hämta inte MET Norges nowcast och SNOW till mosaiken")
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    state_dir = args.cache / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = "knep/0.1 (hobbyprojekt)"

    if args.time:
        t0 = args.time
    else:
        t0 = _wait_for_new(session, _previous_analysis(args.out), args.wait)
        if t0 is None:
            log.info("ingen ny radarbild")
            return NO_NEW_DATA

    times = [t0 - k * radar.STEP for k in range(args.history)][::-1]
    fields, grid, sources, missing = _analyses(times, args.cache, state_dir, session, args.fallback)
    if len(fields) < 2 or grid is None:
        log.error("för få radarbilder bakåt från %s", t0)
        return 1
    obs = np.stack(fields)
    steps = round(args.hours * 60 / 5)
    extra = {}
    if not args.no_bias:
        if not args.time:  # insamlingen hämtar senaste timmens mätare, så bara i realtid
            try:
                bias.Operational(args.cache / "bias", args.bias).step(session, t0, obs[-1], sources, _target(grid))
            except Exception as e:  # noqa: BLE001  insamlingen får aldrig stoppa prognosen
                log.warning("volyminsamling: %s", e)
        corr = bias.Correction.load(args.bias)
        week = bias.load_week(args.cache / "bias")
        if corr is not None and week is not None:
            corr.mfb, corr.mfb_time = week
        if corr is not None and corr.beam.shape == obs.shape[1:]:
            k = corr.factor(t0)
            obs = corr.apply(obs, t0)
            cov = np.isfinite(obs[-1])
            extra["volume_correction"] = {"median": round(float(np.median(k[cov])), 3) if cov.any() else 1.0,
                                          "week": round(float(np.exp(corr.mfb)), 3), "tail_gamma": round(corr.gamma, 3)}

    started = time.monotonic()
    prob = None
    if args.reference:
        fc = model.nowcast(obs, steps)
    else:
        chain = model.Chain(args.model if args.model.exists() else None, prob_steps=round(args.prob_hours * 12))
        state = model.State.load(state_dir / "model.npz")
        res = chain.run(obs, t0, steps, state)
        state.save(state_dir / "model.npz")
        np.save(state_dir / "motion.npy", res.motion.astype(np.float32))
        fc, prob = res.rain, res.prob
    log.info("prognos %s, %d steg på %.1f s", t0, steps, time.monotonic() - started)

    frames = [(t, "obs", f) for t, f in zip(times[-len(fields):], obs)]
    n_prob = round(args.prob_hours * 12) if prob is not None else 0
    frames += [(t0 + (k + 1) * radar.STEP, "fc", f, prob[2, k] if k < n_prob else None) for k, f in enumerate(fc)]
    share = {}
    if sources is not None:
        valid = sources != composite.SOURCE_NONE
        for name, code in (("smhi", composite.SOURCE_SMHI), ("opera", composite.SOURCE_OPERA),
                           ("volymer", composite.SOURCE_VOLUME), ("flyttad", composite.SOURCE_ADVECTED)):
            share[name] = round(float((sources == code).sum() / max(valid.sum(), 1)), 4)
    if not args.time and not args.no_compare:  # källorna har bara senaste loppet
        started = time.monotonic()
        extra["compare"] = compare.update(args.out, session, t0)
        log.info("jämförelsekällor på %.1f s", time.monotonic() - started)
    extra["models"] = models.versions()  # vilka släppta versioner som räknade den här prognosen
    render.Renderer(grid).write(args.out, t0, frames, {"missing_radars": missing, "sources": share} | extra)
    log.info("skrev %d rutor till %s", len(frames), args.out)

    if not args.keep_cache:
        _prune(args.cache, "*.tif", args.history + 2)
        _prune(state_dir, "analys_*.npz", args.history + 2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
