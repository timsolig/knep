"""Regnmätarna till sidan: SMHI:s kvartssummor (parameter 14) och timsummor (parameter 7).

SMHI ger alla stationer i ett anrop bara för senaste timmen, så varje cykel lägger till den
timmen i gauges.json bredvid manifestet och behåller de senaste HOURS timmarna. Sidan ritar
stationerna med samma färgskala som kartorna och tar dem till punktserien.

Ett värde vid tiden t är summan för perioden som slutar t. Bara kvalitet G (kontrollerad) och
Y (misstänkt eller aggregerad) tas med, som i bias.py.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import requests

log = logging.getLogger("knep")

METOBS = "https://opendata-download-metobs.smhi.se/api/version/1.0/parameter"
PARAMS = {"15": 14, "60": 7}
HOURS = 12
FILE = "gauges.json"


def _iso(t: datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse(doc: dict) -> tuple[dict, dict]:
    """Stationer {id: [lat, lon, namn]} och värden {tid: {id: mm}} ur ett svar för station-set/all."""
    stations, values = {}, {}
    for s in doc.get("station", []):
        sid = str(s["key"])
        got = False
        for v in s.get("value") or []:
            if v.get("value") in (None, "") or v.get("quality") not in ("G", "Y"):
                continue
            t = _iso(datetime.fromtimestamp(int(v["date"]) / 1000, UTC))
            values.setdefault(t, {})[sid] = round(float(v["value"]), 2)
            got = True
        if got:
            stations[sid] = [round(s["latitude"], 4), round(s["longitude"], 4), s.get("name", "")]
    return stations, values


def merge(old: dict | None, fresh: dict[str, tuple[dict, dict]], now: datetime, hours: float = HOURS) -> dict:
    """Lägg nya värden ovanpå de sparade och släng det som är äldre än hours."""
    out = {"stations": dict((old or {}).get("stations", {}))}
    oldest = _iso(now - timedelta(hours=hours))
    for res in PARAMS:
        series = dict((old or {}).get(res, {}))
        if res in fresh:
            stations, values = fresh[res]
            out["stations"].update(stations)
            for t, vals in values.items():
                series[t] = {**series.get(t, {}), **vals}
        out[res] = {t: series[t] for t in sorted(series) if t > oldest}
    used = {sid for res in PARAMS for vals in out[res].values() for sid in vals}
    out["stations"] = {sid: v for sid, v in sorted(out["stations"].items()) if sid in used}
    out["updated"] = _iso(now)
    out["hours"] = hours
    return out


def update(out: Path, session: requests.Session, now: datetime, hours: float = HOURS) -> dict | None:
    """Hämta senaste timmen och skriv gauges.json; en parameter som fallerar hoppas över den här gången."""
    path = out / FILE
    try:
        old = json.loads(path.read_text())
    except (FileNotFoundError, ValueError):
        old = None
    fresh = {}
    for res, param in PARAMS.items():
        try:
            r = session.get(f"{METOBS}/{param}/station-set/all/period/latest-hour/data.json", timeout=30)
            r.raise_for_status()
            fresh[res] = parse(r.json())
        except (requests.RequestException, ValueError, KeyError) as e:
            log.warning("mätare %s min: %s", res, e)
    if not fresh and old is None:
        return None
    doc = merge(old, fresh, now, hours)
    out.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, separators=(",", ":"), ensure_ascii=False))
    tmp.replace(path)
    return {"file": FILE, "hours": hours, "stations": len(doc["stations"]),
            "15": len(doc["15"]), "60": len(doc["60"])}
