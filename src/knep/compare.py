"""Jämförelsekällor för mosaiken på sidan: MET Norges nowcast och SMHI:s SNOW som kartor.

Båda hämtas på Pi:n och ritas med samma färgskala som kedjan, så att de tre rutorna på sidan
går att jämföra direkt. Kartan på sidan är avgränsad till MEPS-området, som SNOW ligger på.

MET Norge: radarnowcasten på thredds.met.no, 24 steg om 5 min på 1 km i en lambertprojektion.
Hela filen är 73 MB och servern komprimerar inte utsnitt, så var 4:e punkt i båda riktningarna
hämtas via OPeNDAP (4 km, cirka 22 MB), och ett nytt lopp högst var 15:e minut.

SNOW: SMHI:s timvisa median ur ensemblen, hämtad som hela fält utan koordinater (cirka 35 KB per
timme). Rutnätet är MEPS: 949 gånger 1069 punkter med 2,5 km, söderifrån och upp.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import requests
from rasterio.crs import CRS
from rasterio.transform import Affine

from . import render
from .radar import Grid

log = logging.getLogger("knep")

MEPS_CRS = CRS.from_proj4("+proj=lcc +lat_0=63.3 +lon_0=15 +lat_1=63.3 +lat_2=63.3 +R=6371000 +units=m +no_defs")
MEPS_RES, MEPS_X0, MEPS_Y0, MEPS_SHAPE = 2500.0, -1060084.0, -1332518.0, (1069, 949)  # x0, y0: sydvästra punkten
MEPS = Grid(MEPS_CRS, Affine(MEPS_RES, 0, MEPS_X0 - MEPS_RES / 2, 0, -MEPS_RES,
                             MEPS_Y0 + (MEPS_SHAPE[0] - 0.5) * MEPS_RES), MEPS_SHAPE)

MET_CATALOG = "https://thredds.met.no/thredds/catalog/radarnowcasting/catalog.xml"
MET_DODS = "https://thredds.met.no/thredds/dodsC/radarnowcasting/"
MET_CRS = CRS.from_proj4("+proj=lcc +lat_0=63 +lon_0=15 +lat_1=63 +lat_2=63 +R=6371000 +units=m +no_defs")
MET_STRIDE = 4
MET_EVERY = timedelta(minutes=15)

SNOW = "https://opendata-download-metfcst.smhi.se/api/category/snow1g/version/1"

HOUR = timedelta(hours=1)


def _iso(t: datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def bounds() -> list:
    """MEPS-området i grader, [[syd, väst], [nord, öst]], för kartans gränser."""
    return render.Renderer(MEPS).bounds


# ---------- MET Norge ----------

def met_latest(session: requests.Session) -> tuple[str, datetime]:
    """Senaste loppet i katalogen: filnamn och analystid."""
    r = session.get(MET_CATALOG, timeout=30)
    r.raise_for_status()
    names = re.findall(r'name="(yrwms-nordic\.mos\.pcappi-0-rr\.[^"]*\.(\d{8}T\d{6})Z\.nc)"', r.text)
    if not names:
        raise ValueError("inga lopp i MET Norges katalog")
    name, stamp = max(names, key=lambda n: n[1])
    return name, datetime.strptime(stamp, "%Y%m%dT%H%M%S").replace(tzinfo=UTC)


def dods_arrays(body: bytes, dtypes: list[str]) -> list[np.ndarray]:
    """Arrayerna i ett OPeNDAP-svar (.dods) i ordning: längden två gånger, sedan värdena (XDR, big endian)."""
    i = body.index(b"\nData:\n") + len(b"\nData:\n")
    out = []
    for dt in dtypes:
        n = int(np.frombuffer(body, ">u4", 1, i)[0])
        i += 8
        out.append(np.frombuffer(body, dt, n, i).astype(dt[1:] if dt[0] == ">" else dt))
        i += n * np.dtype(dt).itemsize
    return out


def met_fetch(session: requests.Session, name: str, stride: int = MET_STRIDE):
    """Loppets tider och fält i mm/h, glesat med stride, och dess rutnät."""
    url = MET_DODS + name
    r = session.get(url + ".dds", timeout=30)
    r.raise_for_status()
    nx, ny = (int(re.search(rf"{k}\[{k} = (\d+)\]", r.text).group(1)) for k in ("Xc", "Yc"))
    r = session.get(url + ".dods?time,Xc[0:1:1],Yc[0:1:1]", timeout=30)
    r.raise_for_status()
    t, xc, yc = dods_arrays(r.content, [">i4", ">f4", ">f4"])
    q = f"lwe_precipitation_rate.lwe_precipitation_rate[0:1:{len(t) - 1}][0:{stride}:{ny - 1}][0:{stride}:{nx - 1}]"
    r = session.get(url + ".dods?" + q, timeout=180)
    r.raise_for_status()
    (v,) = dods_arrays(r.content, [">f4"])
    h, w = -(-ny // stride), -(-nx // stride)
    v = v.reshape(len(t), h, w)
    v[~(v < 1e30)] = np.nan
    v[v < 0] = 0.0
    dx, dy = float(xc[1] - xc[0]) * stride, float(yc[0] - yc[1]) * stride
    grid = Grid(MET_CRS, Affine(dx, 0, float(xc[0]) - dx / 2, 0, -dy, float(yc[0]) + dy / 2), (h, w))
    times = [datetime.fromtimestamp(int(s), UTC) for s in t]
    return times, v, grid


def _write_met(out: Path, ref: datetime, times, fields, grid) -> dict:
    d = out / "met"
    d.mkdir(parents=True, exist_ok=True)
    rend = render.Renderer(grid)
    names, entries = set(), {5: [], 15: [], 60: []}
    frames = [(t, "fc", f) for t, f in zip(times, fields)]
    for i, (t, _, f) in enumerate(frames):
        name = f"{i:02d}.png"
        rend.png(f, d / name)
        names.add(name)
        entries[5].append({"time": _iso(t), "file": f"met/{name}"})
    for minutes, prefix in ((15, "q"), (60, "h")):
        for i, (end, start, _, f) in enumerate(render.aggregate(frames, minutes)):
            name = f"{prefix}{i:02d}.png"
            rend.png(f, d / name)
            names.add(name)
            entries[minutes].append({"time": _iso(end), "start": _iso(start), "file": f"met/{name}"})
    for old in d.glob("*.png"):
        if old.name not in names:
            old.unlink()
    return {"reference": _iso(ref), "bounds": rend.bounds, "resolution_km": round(grid.transform.a / 1000, 1),
            "frames": entries[5], "frames15": entries[15], "frames60": entries[60]}


def met(out: Path, session: requests.Session, now: datetime) -> dict | None:
    """MET Norges senaste lopp, ritat; det förra återanvänds om det är yngre än MET_EVERY."""
    index = out / "met" / "met.json"
    prev = json.loads(index.read_text()) if index.exists() else None
    name, ref = met_latest(session)
    if prev and (_parse(prev["reference"]) >= ref or ref - _parse(prev["reference"]) < MET_EVERY):
        return prev
    times, fields, grid = met_fetch(session, name)
    entry = _write_met(out, ref, times, fields, grid)
    index.write_text(json.dumps(entry))
    log.info("MET Norge: lopp %s, %d steg", _iso(ref), len(times))
    return entry


# ---------- SNOW ----------

def snow_hours(now: datetime, hours: float = 2.0) -> list[datetime]:
    """Timmarna (sluttid) som överlappar prognosen från now och hours framåt."""
    first = now.replace(minute=0, second=0, microsecond=0) + HOUR
    last = now + timedelta(hours=hours)
    out, t = [], first
    while t - HOUR < last:
        out.append(t)
        t += HOUR
    return out


def snow_field(session: requests.Session, end: datetime) -> tuple[np.ndarray, str] | None:
    """Medianen för timmen som slutar end, i mm (= medelintensitet i mm/h), på MEPS rutnät med norr uppåt."""
    url = (f"{SNOW}/geotype/multipoint/time/{end:%Y%m%dT%H%M%SZ}/parameter/precipitation_amount_median/data.json")
    r = session.get(url, params={"with-geo": "false"}, timeout=60)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    d = r.json()
    v = np.array(d["timeSeries"][0]["data"]["precipitation_amount_median"], np.float32)
    v[v >= 9999] = np.nan
    return v.reshape(MEPS_SHAPE)[::-1].copy(), d.get("referenceTime", "")


def snow(out: Path, session: requests.Session, now: datetime, hours: float = 2.0) -> dict | None:
    d = out / "snow"
    d.mkdir(parents=True, exist_ok=True)
    rend = render.Renderer(MEPS)
    entries, names, ref = [], set(), ""
    for end in snow_hours(now, hours):
        got = snow_field(session, end)
        if got is None:
            continue
        field, ref = got
        name = f"h{end:%H}.png"
        rend.png(field, d / name)
        names.add(name)
        entries.append({"time": _iso(end), "start": _iso(end - HOUR), "file": f"snow/{name}"})
    for old in d.glob("*.png"):
        if old.name not in names:
            old.unlink()
    if not entries:
        return None
    return {"reference": ref, "bounds": rend.bounds, "frames60": entries}


def update(out: Path, session: requests.Session, now: datetime, hours: float = 2.0) -> dict:
    """Båda källorna för manifestet. En källa som fallerar saknas bara den här gången."""
    res = {"bounds": bounds()}
    for key, fn in (("met", met), ("snow", lambda o, s, t: snow(o, s, t, hours))):
        try:
            got = fn(out, session, now)
        except (requests.RequestException, ValueError, KeyError, IndexError) as e:
            log.warning("%s: %s", key, e)
            got = None
        if got:
            res[key] = got
    return res
