"""Hämtar data för träningsdagarna (och mätarna för valideringsdagarna) till /data.

    uv run python experiments/bortfall/hamta.py radar matare   SMHI:s komposit, sedan regnmätarna
    uv run python experiments/bortfall/hamta.py meps           MEPS ur MET Norges arkiv
    uv run python experiments/bortfall/hamta.py kontroll       vad som finns och saknas, hämtar inget

Radarn: alla bilder var 5:e minut från 90 min före dygnet till 5 h efter, som för
experiments/sverige (till /data/radar/ÅÅÅÅ/MM/DD/). MEPS: körningarna var 6:e timme som
behövs under dygnet (till /data/meps/). Mätarna: SMHI:s timsummor (parameter 7) och
kvartssummor (parameter 14) ur corrected-archive, utsnitt för tränings- och valideringsdagarna
till /data/bortfall/matare/. Testdagarna hämtas aldrig.

Allt kan köras om och hoppar över det som redan finns. Hämtningen avbryts om /data har
mindre än 2 GB ledigt eller om processen har skrivit mer än --max-gb.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import requests

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "sverige"))
sys.path.insert(0, str(HERE.parents[1] / "src"))
import data as sv  # noqa: E402

from knep import bias, nwp, radar  # noqa: E402

DATA = Path("/data")
OUT = DATA / "bortfall"
GAUGES = OUT / "matare"
MIN_FREE = 2 * 1024**3
METOBS = "https://opendata-download-metobs.smhi.se/api/version/1.0/parameter"


class Budget:
    def __init__(self, max_gb: float):
        self.left = max_gb * 1024**3

    def ok(self) -> bool:
        free = shutil.disk_usage(DATA).free
        if free < MIN_FREE:
            print(f"AVBRYTER: bara {free / 1024**3:.2f} GB ledigt på /data", flush=True)
            return False
        if self.left <= 0:
            print("AVBRYTER: processens datatak är nått", flush=True)
            return False
        return True

    def spend(self, path: Path) -> None:
        self.left -= path.stat().st_size


def training_days() -> list[date]:
    days = [date.fromisoformat(d["day"]) for d in json.loads((HERE / "traning.json").read_text())]
    frozen = [date.fromisoformat(d["day"]) for d in json.loads(sv.DAYS.read_text())]
    bad = [d for d in days if any(abs((d - f).days) <= 2 for f in frozen)]
    assert not bad, f"träningsdagar för nära dagar.json: {bad}"
    return days


def validation_days() -> list[date]:
    return [date.fromisoformat(d["day"]) for d in sv.load_days("validering")]


def frame_times(d: date) -> list[datetime]:
    day = datetime(d.year, d.month, d.day, tzinfo=UTC)
    n = int((timedelta(hours=24 + 5) + timedelta(minutes=90)) / radar.STEP) + 1
    return [day - timedelta(minutes=90) + k * radar.STEP for k in range(n)]


def get_radar(budget: Budget, threads: int = 2) -> None:
    s = sv.session()

    def get(t):
        target = sv.radar_path(t)
        if target.exists():
            return 0
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            radar.fetch(t, target.parent, s)
            budget.spend(target)
            return 0
        except requests.RequestException:
            return 1

    with ThreadPoolExecutor(threads) as pool:
        for d in training_days():
            if not budget.ok():
                return
            print(d, "radar saknas", sum(pool.map(get, frame_times(d))), flush=True)


def get_meps(budget: Budget) -> None:
    s = sv.session()
    _, grid = radar.read_rain(next((DATA / "radar").rglob("*.tif")))
    rows, cols = nwp.box(grid)
    for d in training_days():
        day = datetime(d.year, d.month, d.day, tzinfo=UTC)
        for run in sv.meps_runs_for(day):
            path = sv.meps_path(run)
            if path.exists():
                continue
            if not budget.ok():
                return
            try:
                r = nwp.fetch(s, run, rows, cols, archive=True, leads=sv.MEPS_LEADS)
            except (requests.RequestException, OSError, KeyError, ValueError) as e:
                print(run, "MEPS fel", e, flush=True)
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            r.save(path)
            budget.spend(path)
        print(d, "MEPS klar", flush=True)


def get_gauges(budget: Budget) -> None:
    """Utsnitt ur corrected-archive för alla stationer: dygnet och 5 h efter, för tränings- och valideringsdagar."""
    s = sv.session()
    days = sorted(set(training_days()) | set(validation_days()))
    spans = [(datetime(d.year, d.month, d.day, tzinfo=UTC) - timedelta(minutes=90),
              datetime(d.year, d.month, d.day, tzinfo=UTC) + timedelta(hours=29)) for d in days]
    GAUGES.mkdir(parents=True, exist_ok=True)
    for param in (7, 14):
        path = GAUGES / f"p{param}.npz"
        if path.exists() or not budget.ok():
            continue
        st = s.get(f"{METOBS}/{param}.json", timeout=60).json()["station"]
        first, last = spans[0][0].timestamp() * 1000, spans[-1][1].timestamp() * 1000
        st = [x for x in st if x["from"] <= last and x["to"] >= first]
        ids, lats, lons, times, vals = [], [], [], [], []
        for i, x in enumerate(st):
            try:
                r = s.get(f"{METOBS}/{param}/station/{x['id']}/period/corrected-archive/data.csv", timeout=120)
                if r.status_code == 404:
                    continue
                r.raise_for_status()
            except requests.RequestException as e:
                print(param, x["id"], "fel", e, flush=True)
                continue
            for sid, t, v in bias.parse_archive_csv(r.text, x["id"]):
                if any(a <= t <= b for a, b in spans):
                    ids.append(sid), lats.append(x["latitude"]), lons.append(x["longitude"])
                    times.append(int(t.timestamp())), vals.append(v)
            if i % 25 == 0:
                print(param, f"{i + 1}/{len(st)} stationer, {len(vals)} värden", flush=True)
        np.savez_compressed(path, station=np.array(ids, np.int64), lat=np.array(lats, np.float32),
                            lon=np.array(lons, np.float32), time=np.array(times, np.int64),
                            mm=np.array(vals, np.float32))
        budget.spend(path)
        print(param, "klar", len(set(ids)), "stationer", len(vals), "värden ->", path, flush=True)


def check() -> None:
    for d in training_days():
        times = frame_times(d)
        have = sum(sv.radar_path(t).exists() for t in times)
        runs = sv.meps_runs_for(datetime(d.year, d.month, d.day, tzinfo=UTC))
        meps = sum(sv.meps_path(r).exists() for r in runs)
        print(d, f"radar {have}/{len(times)}", f"MEPS {meps}/{len(runs)}")
    for param in (7, 14):
        p = GAUGES / f"p{param}.npz"
        if p.exists():
            z = np.load(p)
            print(f"mätare p{param}: {len(set(z['station'].tolist()))} stationer, {len(z['mm'])} värden")
        else:
            print(f"mätare p{param}: saknas")
    print(f"ledigt på /data: {shutil.disk_usage(DATA).free / 1024**3:.2f} GB")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("what", nargs="+", choices=["radar", "meps", "matare", "kontroll"])
    p.add_argument("--max-gb", type=float, default=0.8, help="högsta mängd ny data för den här processen")
    p.add_argument("--logg", type=Path, help="skriv utdata till den här filen (läggs till)")
    a = p.parse_args()
    if a.logg:
        sys.stdout = sys.stderr = open(a.logg, "a", buffering=1)
    budget = Budget(a.max_gb)
    for w in a.what:
        {"radar": lambda: get_radar(budget), "meps": lambda: get_meps(budget),
         "matare": lambda: get_gauges(budget), "kontroll": check}[w]()


if __name__ == "__main__":
    main()
