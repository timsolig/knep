"""En cykel: analysen, prognosen och produkterna till sidan.

1. Analysen (knep.analys): SMHI:s komposit med reserver vid radarbortfall (OPERA om --fallback,
   radarvolymer, förra analysen flyttad med rörelsen) och volymkorrektion mot regnmätarna om
   models/bias.npz finns. I realtid samlas radarns värden vid mätarna, och en gång per dygn räknas
   veckofaktorn och en kandidat till ny karta.
2. Prognosen (knep.prognos): kedjan i model.Chain, med sannolikheter för kraftig nederbörd om
   models/extremes.pkl finns. Bara radarn: ingen vädermodell blandas in.
3. Produkterna: MET Norges nowcast och SMHI:s SNOW till mosaiken (compare.py), regnmätarna
   (gauges.py), tidigare utgåvor (runs.py), verifieringen 7 och 30 dygn bakåt (verify.py) och
   kartorna med manifestet (render.py).

Avslutar med kod 75 när det inte finns någon ny radarbild att räkna på.
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path

import requests

from . import analys, compare, models, prognos, render, runs, verify
from .analys import a1, a2_cykel, gauges, radar

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


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="knep", description=__doc__)
    p.add_argument("--out", type=Path, default=Path("out/data"), help="katalog för PNG-rutor och manifest")
    p.add_argument("--cache", type=Path, default=Path("cache"), help="katalog för hämtade radarbilder och tillstånd")
    p.add_argument("--hours", type=float, default=5.0, help="prognoslängd i timmar, kedjan hela vägen")
    p.add_argument("--history", type=int, default=12, help="antal radarbilder bakåt (minst 7 för rörelsen, 12 ger en hel timme på kartan)")
    p.add_argument("--time", type=_parse_time, help="analystid i UTC (ISO 8601); standard är senaste bilden")
    p.add_argument("--wait", type=int, default=120, help="sekunder att vänta på en ny radarbild")
    p.add_argument("--model", type=Path, default=Path("models/extremes.pkl"), help="tränad extremkalibrering")
    p.add_argument("--prob-hours", type=float, default=2.0, help="timmar med sannolikheter för kraftig nederbörd")
    p.add_argument("--bias", type=Path, default=Path("models/bias.npz"), help="volymkorrektion mot regnmätarna")
    p.add_argument("--no-bias", action="store_true", help="ingen volymkorrektion och ingen insamling")
    p.add_argument("--fallback", action="store_true", help="fyll radarbortfall med OPERA-kompositen")
    p.add_argument("--klotter", type=Path, default=None,
                   help="karta över fast klotter (analys/klotter.py); filtret är av utan den")
    p.add_argument("--opera-fjarr", type=float, default=None, metavar="KM",
                   help="med --fallback: OPERA där SMHI är torr inom zonen där de svenska radarernas lägsta "
                        "stråle ligger över KM km (glappet nordväst om Kiruna); av utan värde")
    p.add_argument("--reference", action="store_true", help="kör referensmodellen i stället för kedjan")
    p.add_argument("--keep-cache", action="store_true", help="rensa inte gamla radarbilder")
    p.add_argument("--no-compare", action="store_true", help="hämta inte MET Norges nowcast och SNOW till mosaiken")
    p.add_argument("--back", type=float, default=render.HISTORY_HOURS,
                   help="timmar radaranalys bakåt på sidan (hist/), 0 stänger av")
    p.add_argument("--runs", type=float, default=runs.HOURS,
                   help="timmar med tidigare utgåvor (timsummor varje timme, runs/), 0 stänger av")
    p.add_argument("--no-gauges", action="store_true", help="hämta inte regnmätarna till sidan (gauges.json)")
    p.add_argument("--a2", action="store_true",
                   help="A2T, A1 rättad mot regnmätarna ur gauges.json, kvart och timme bakåt till a2/ (levels.a2)")
    p.add_argument("--a2-matare", type=Path, default=None,
                   help="katalog med mätararkivet p7.npz och p14.npz i stället för gauges.json, för historiska körningar")
    p.add_argument("--no-verify",action="store_true", help="ingen verifiering mot radarn och mätarna (verif.json)")
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

    a = analys.bygg(t0, args.history, args.cache, state_dir, session, fallback=args.fallback,
                    bias_path=None if args.no_bias else args.bias, collect=not args.time,
                    klotter_path=args.klotter, opera_fjarr=args.opera_fjarr)
    if a is None:
        return 1
    steps = round(args.hours * 60 / 5)
    p = prognos.kor(a, state_dir, steps, model_path=args.model, prob_hours=args.prob_hours,
                    reference=args.reference)
    grid, fc, prob = a.grid, p.rain, p.prob
    extra = a.extra | p.extra

    frames = [(t, "obs", f) for t, f in zip(a.times, a.rain)]
    n_prob = round(args.prob_hours * 12) if prob is not None else 0
    frames += [(t0 + (k + 1) * radar.STEP, "fc", f, prob[2, k] if k < n_prob else None) for k, f in enumerate(fc)]
    if not args.time and not args.no_compare:  # källorna har bara senaste loppet
        started = time.monotonic()
        store = None if args.no_verify else verify.source_dir(args.cache / "verif")
        extra["compare"] = compare.update(args.out, session, t0, args.hours, store)
        log.info("jämförelsekällor på %.1f s", time.monotonic() - started)
    if not args.time and not args.no_gauges:  # SMHI ger alla stationer bara för senaste timmen
        try:
            g = gauges.update(args.out, session, datetime.now(UTC), max(args.back, 1.0))
        except Exception as e:  # noqa: BLE001  mätarna får aldrig stoppa prognosen
            log.warning("mätare: %s", e)
            g = None
        if g:
            extra["gauges"] = g
    extra["models"] = models.versions()  # vilka släppta versioner som räknade den här prognosen
    rend = render.Renderer(grid)
    if args.back > 0:
        started = time.monotonic()
        extra["history"] = rend.history(args.out, [(t, f) for t, kind, f, *_ in frames if kind == "obs"], t0, args.back)
        log.info("analys bakåt: %d bilder på %.1f s", len(extra["history"]["frames"]), time.monotonic() - started)
        started = time.monotonic()
        a1_frames = None
        try:  # A1 får aldrig stoppa prognosen
            a1_frames = a1.update(state_dir, a.times, a.rain, p.motion)
            extra["levels"] = {"a0": "history", "a2": None,
                               "a1": rend.history(args.out, a1_frames, t0, args.back, directory=render.A1_DIR)}
            log.info("A1: %d intervall på %.1f s", len(a1_frames), time.monotonic() - started)
        except Exception as e:  # noqa: BLE001
            log.warning("A1: %s", e)
        if args.a2 and a1_frames is not None:
            try:  # A2 får aldrig stoppa prognosen
                doc = a2_cykel.las_arkiv(args.a2_matare, t0) if args.a2_matare else a2_cykel.las_gauges_json(args.out)
                extra["levels"]["a2"] = a2_cykel.kor(state_dir, args.out, rend, a1_frames, t0, args.back, doc,
                                                     verif_dir=None if args.no_verify else args.cache / "verif")
            except Exception as e:  # noqa: BLE001
                log.warning("A2: %s", e)
    if args.runs > 0:
        try:  # utgåvan sparas första cykeln i timmen; ett fel här får inte stoppa prognosen
            if runs.due(args.out, t0):
                runs.archive(args.out, rend, t0, frames, extra.get("compare"))
                log.info("sparade utgåvan %s", t0)
            extra["runs"] = runs.listing(args.out, t0, args.runs)
        except Exception as e:  # noqa: BLE001
            log.warning("utgåvor: %s", e)
    if not args.time and not args.no_verify:  # jämförelsekällorna och mätarna finns bara i realtid
        started = time.monotonic()
        try:  # verifieringen får aldrig stoppa prognosen
            v = verify.cycle(args.cache / "verif", args.out, grid, t0, frames, lambda t: analys.source_of(state_dir, t))
            if v:
                extra["verification"] = v
            log.info("verifiering på %.1f s", time.monotonic() - started)
        except Exception as e:  # noqa: BLE001
            log.warning("verifiering: %s", e)
    rend.write(args.out, t0, frames, {"missing_radars": a.missing, "sources": a.share()} | extra)
    log.info("skrev %d rutor till %s", len(frames), args.out)

    if not args.keep_cache:
        analys.rensa(args.cache, state_dir, args.history + 2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
