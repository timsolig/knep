"""En prognoscykel: hämta radar, prognostisera, rendera.

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

from . import model, radar, render

NO_NEW_DATA = 75
log = logging.getLogger("nowcast")


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


def _fetch_history(t0, n, cache, session) -> tuple[list[datetime], list[Path]]:
    """Hämta upp till n bilder bakåt från t0. Stannar vid första lucka så att tidssteget är jämnt."""
    times, paths = [], []
    for k in range(n):
        t = t0 - k * radar.STEP
        try:
            paths.append(radar.fetch(t, cache, session))
            times.append(t)
        except requests.HTTPError as e:
            log.warning("saknar radarbild %s: %s", t, e)
            break
    return times[::-1], paths[::-1]


def _prune(cache: Path, keep: set[Path]) -> None:
    for p in cache.glob("*.tif"):
        if p not in keep:
            p.unlink()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="nowcast", description=__doc__)
    p.add_argument("--out", type=Path, default=Path("out/data"), help="katalog för PNG-rutor och manifest")
    p.add_argument("--cache", type=Path, default=Path("cache"), help="katalog för hämtade radarbilder")
    p.add_argument("--hours", type=float, default=2.0, help="prognoslängd i timmar")
    p.add_argument("--history", type=int, default=4, help="antal radarbilder till rörelseskattningen")
    p.add_argument("--time", type=_parse_time, help="analystid i UTC (ISO 8601); standard är senaste bilden")
    p.add_argument("--wait", type=int, default=120, help="sekunder att vänta på en ny radarbild")
    p.add_argument("--keep-cache", action="store_true", help="rensa inte gamla radarbilder")
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args.cache.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = "nowcast/0.1 (hobbyprojekt)"

    if args.time:
        t0 = args.time
    else:
        t0 = _wait_for_new(session, _previous_analysis(args.out), args.wait)
        if t0 is None:
            log.info("ingen ny radarbild")
            return NO_NEW_DATA

    times, paths = _fetch_history(t0, args.history, args.cache, session)
    if len(times) < 2:
        log.error("för få radarbilder bakåt från %s", t0)
        return 1

    fields, grids = zip(*(radar.read_rain(path) for path in paths))
    obs = np.stack(fields)
    steps = round(args.hours * 60 / 5)

    started = time.monotonic()
    fc = model.nowcast(obs, steps)
    log.info("prognos %s, %d steg på %.1f s", t0, steps, time.monotonic() - started)

    frames = [(t, "obs", f) for t, f in zip(times, obs)]
    frames += [(t0 + (k + 1) * radar.STEP, "fc", f) for k, f in enumerate(fc)]
    render.Renderer(grids[-1]).write(args.out, t0, frames)
    log.info("skrev %d rutor till %s", len(frames), args.out)

    if not args.keep_cache:
        _prune(args.cache, set(paths))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
