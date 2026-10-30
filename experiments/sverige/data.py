"""Svenska testfall för prognosen 0 till 5 h: urval av dagar, radar ur SMHI:s arkiv och MEPS ur MET Norges.

    python experiments/sverige/data.py kandidater      prov var 6:e timme på var 3:e dag 2019 till 2025
    python experiments/sverige/data.py urval           väljer dagarna och skriver dagar.json (fryses i git)
    python experiments/sverige/data.py radar           hämtar radarn för dagarna till /data/radar
    python experiments/sverige/data.py meps            hämtar MEPS-körningarna för dagarna till /data/meps

Urvalet är regnigast först inom varje årstid, med Hans 2023 och Gävle 2021 alltid med, och
dagarna delas i en valideringsdel (för att välja vikter och inställningar) och en testdel som
rörs först i slutet. Indelningen bestäms av datumet, inte av resultaten.

MEPS: deterministiska körningar var 3:e timme på 2,5 km, ackumulerad nederbörd per timme.
Utsnittet täcker SMHI:s radarrutnät och sparas som timsummor i mm (float16).
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from knep import nwp, radar  # noqa: E402

HERE = Path(__file__).parent
DATA = Path("/data")
DAYS = HERE / "dagar.json"
CANDIDATES = DATA / "sverige" / "kandidater.json"
FIXED = {"2023-08-07": "Hans", "2023-08-08": "Hans", "2021-08-17": "Gävle"}
DEVELOPMENT = {"2023-08-08"}  # dagar som har setts under utvecklingen hamnar aldrig i testdelen
SEASONS = {12: "vinter", 1: "vinter", 2: "vinter", 3: "vår", 4: "vår", 5: "vår",
           6: "sommar", 7: "sommar", 8: "sommar", 9: "höst", 10: "höst", 11: "höst"}


class Throttled(requests.Session):
    """Högst RATE anrop per sekund, och väntar ut en spärr (429). SMHI tillåter 40 anrop på 10 s,
    och driften på Pi:n delar adressen, så verktygen håller sig långt under."""

    RATE = 2.0

    def __init__(self):
        super().__init__()
        self.headers["User-Agent"] = "knep/0.1 (hobbyprojekt, verifiering)"
        self._last = 0.0
        self._lock = threading.Lock()

    def request(self, *a, **k):
        for _ in range(5):
            with self._lock:  # taket gäller alla trådar tillsammans
                wait = self._last + 1 / self.RATE - time.monotonic()
                self._last = max(self._last + 1 / self.RATE, time.monotonic())
            if wait > 0:
                time.sleep(wait)
            r = super().request(*a, **k)
            if r.status_code != 429:
                return r
            time.sleep(35)
        return r


def session() -> requests.Session:
    return Throttled()


def candidates(a) -> None:
    """Våt yta och toppintensitet i radarn kl 00, 06, 12 och 18 på var 3:e dag."""
    s = session()
    out = json.loads(CANDIDATES.read_text()) if CANDIDATES.exists() else {}
    tmp = DATA / "sverige" / "prov"
    tmp.mkdir(parents=True, exist_ok=True)
    d = date(2019, 1, 1)
    while d <= date(2025, 12, 31):
        key = d.isoformat()
        if key not in out:
            wet, heavy, n = [], [], 0
            for h in range(0, 24, 6):
                t = datetime(d.year, d.month, d.day, h, tzinfo=UTC)
                try:
                    p = radar.fetch(t, tmp, s)
                    r, _ = radar.read_rain(p)
                    p.unlink()
                except (requests.RequestException, OSError) as e:
                    print(key, h, e, file=sys.stderr)
                    continue
                cov = np.isfinite(r)
                wet.append(float((r[cov] >= 0.5).mean()))
                heavy.append(float((r[cov] >= 5).mean()))  # andel med kraftigt regn; enstaka toppar är ofta klotter
                n += 1
            if n:
                out[key] = {"wet": round(float(np.mean(wet)), 4), "heavy": round(max(heavy), 5), "n": n}
                CANDIDATES.write_text(json.dumps(out, indent=0))
                print(key, out[key], flush=True)
        d += timedelta(days=3 if key not in FIXED else 1)
    for key in FIXED:  # de namngivna dagarna ligger inte nödvändigtvis på var 3:e dag
        if key not in out:
            out[key] = {"wet": None, "heavy": None, "n": 0}
    CANDIDATES.write_text(json.dumps(out, indent=0))


def select(a) -> None:
    """Sex dagar per årstid, de med störst våt yta (sommaren hälften efter ytan med kraftigt regn), plus de namngivna."""
    c = json.loads(CANDIDATES.read_text())
    chosen = dict(FIXED)
    for season in ("vinter", "vår", "sommar", "höst"):
        days = [(k, v) for k, v in c.items() if v["wet"] is not None and SEASONS[int(k[5:7])] == season and k not in FIXED]
        days.sort(key=lambda kv: -kv[1]["wet"])
        picked = [k for k, _ in days[:6]]
        if season == "sommar":  # skurar: ytan med kraftigt regn betyder mer än den våta ytan
            strong = sorted(days, key=lambda kv: -kv[1]["heavy"])
            picked = [k for k, _ in days[:3]] + [k for k, _ in strong if k not in [p for p, _ in days[:3]]][:3]
        for k in picked:
            chosen[k] = season
    out = []
    for i, k in enumerate(sorted(chosen)):
        # var tredje dag i datumordning till testdelen, de namngivna alltid i testdelen utom
        # 2023-08-08, som användes för att prova verktygen och därför ligger i valideringsdelen
        part = "test" if (i % 3 == 2 or k in FIXED) and k not in DEVELOPMENT else "validering"
        info = c.get(k, {})
        out.append({"day": k, "kind": chosen[k] if k not in FIXED else FIXED[k], "part": part,
                    "wet": info.get("wet"), "heavy": info.get("heavy")})
    # en dag intill en testdag hör till samma väder och går också till testdelen
    test = {date.fromisoformat(d["day"]) for d in out if d["part"] == "test"}
    for d in out:
        day = date.fromisoformat(d["day"])
        if d["part"] != "test" and d["day"] not in DEVELOPMENT and (day - timedelta(days=1) in test or day + timedelta(days=1) in test):
            d["part"] = "test"
    DAYS.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(f"{len(out)} dagar, {sum(d['part'] == 'test' for d in out)} i testdelen -> {DAYS}")


def load_days(part: str | None = None) -> list[dict]:
    days = json.loads(DAYS.read_text())
    return [d for d in days if part is None or d["part"] == part]


def radar_days(a) -> None:
    """Alla bilder var 5:e minut för dagarna, de sista 90 min före (för kedjans tillstånd) och
    5 h efter (för verifieringen). Fyra anrop i taget; svarstiden begränsar, inte taket."""
    s = session()

    def get(t):
        target = radar_path(t)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            radar.fetch(t, target.parent, s)
            return 0
        except requests.RequestException:
            return 1

    with ThreadPoolExecutor(4) as pool:
        for d in load_days():
            day = datetime.fromisoformat(d["day"]).replace(tzinfo=UTC)
            n = int((timedelta(hours=24 + 5) + timedelta(minutes=90)) / radar.STEP) + 1
            times = [day - timedelta(minutes=90) + k * radar.STEP for k in range(n)]
            print(d["day"], "saknas", sum(pool.map(get, times)), flush=True)


def radar_path(t: datetime) -> Path:
    return DATA / "radar" / t.strftime("%Y/%m/%d") / f"{t:%Y%m%d%H%M}.tif"


def meps_path(run: datetime) -> Path:
    return DATA / "meps" / f"meps_{run:%Y%m%dT%H}.npz"


CYCLE = 6         # arkivet har körningar var 6:e timme alla år (2023 även var 3:e); verifieringen tar bara dem
MEPS_LEADS = 14   # en körning är upp till 8,5 h gammal när den används och ska räcka 5 h framåt


def meps_runs_for(day: datetime) -> list[datetime]:
    """Körningarna som behövs för prognoser utfärdade under dygnet, med 2,5 h fördröjning och 5 h framåt."""
    first = nwp.available(day, CYCLE)
    return [first + timedelta(hours=CYCLE * k) for k in range(24 // CYCLE + 1)]


def meps_days(a) -> None:
    s = session()
    _, grid = radar.read_rain(next((DATA / "radar").rglob("*.tif")))
    rows, cols = nwp.box(grid)
    print("MEPS-utsnitt rader", rows, "kolumner", cols, flush=True)
    for d in load_days():
        day = datetime.fromisoformat(d["day"]).replace(tzinfo=UTC)
        for run in meps_runs_for(day):
            path = meps_path(run)
            if path.exists():
                continue
            try:
                r = nwp.fetch(s, run, rows, cols, archive=True, leads=MEPS_LEADS)
            except requests.RequestException as e:
                print(run, e, file=sys.stderr, flush=True)
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            r.save(path)
        print(d["day"], "klar", flush=True)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cmd", choices=["kandidater", "urval", "radar", "meps"])
    a = p.parse_args()
    {"kandidater": candidates, "urval": select, "radar": radar_days, "meps": meps_days}[a.cmd](a)


if __name__ == "__main__":
    main()
