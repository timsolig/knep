"""Väljer träningsdagarna för bortfallsexperimenten och skriver traning.json (fryses i git).

    uv run python experiments/bortfall/valj_traning.py

Ur /data/sverige/kandidater.json (radarn kl 00, 06, 12 och 18 var 3:e dag 2019 till 2025):

- bara 2020 till 2025, eftersom MEPS 2019 ligger på ett äldre, mindre rutnät
- alla fyra proven måste finnas (n = 4)
- aldrig en dag i experiments/sverige/dagar.json eller inom två dygn från en sådan;
  bara datumen läses, inte indelningen, och ingen data från de dagarna används
- sju dagar per årstid, regnigast först (våt yta, minst 0,5 mm/h); på sommaren väljs
  varannan dag efter ytan med kraftigt regn (minst 5 mm/h) i stället, för skurarna
- högst två dagar per år och årstid, och minst sex dygn mellan två träningsdagar,
  så att dagarna inte hör till samma väderläge
- våt yta minst 5 % i medel, annars finns för lite regn att släcka

Urvalet beror bara på kandidatlistan och reglerna ovan, inte på några resultat.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent
CANDIDATES = Path("/data/sverige/kandidater.json")
FROZEN = HERE.parent / "sverige" / "dagar.json"
OUT = HERE / "traning.json"
SEASONS = {12: "vinter", 1: "vinter", 2: "vinter", 3: "vår", 4: "vår", 5: "vår",
           6: "sommar", 7: "sommar", 8: "sommar", 9: "höst", 10: "höst", 11: "höst"}
PER_SEASON, PER_YEAR_SEASON, MIN_GAP, MIN_WET, BUFFER = 7, 2, 6, 0.05, 2


def blocked_days() -> list[date]:
    """Datumen i dagar.json, alla delar (bara datumet läses)."""
    return [date.fromisoformat(d["day"]) for d in json.loads(FROZEN.read_text())]


def select(cands: dict, blocked: list[date]) -> list[dict]:
    pool = []
    for k, v in cands.items():
        d = date.fromisoformat(k)
        if not (2020 <= d.year <= 2025) or v.get("n") != 4 or v.get("wet") is None or v["wet"] < MIN_WET:
            continue
        if any(abs((d - b).days) <= BUFFER for b in blocked):
            continue
        pool.append((d, v))
    chosen: list[tuple[date, dict, str, str]] = []

    def ok(d: date, season: str) -> bool:
        if any(abs((d - c).days) < MIN_GAP for c, *_ in chosen):
            return False
        return sum(1 for c, _, s, _ in chosen if s == season and c.year == d.year) < PER_YEAR_SEASON

    for season in ("vinter", "vår", "sommar", "höst"):
        days = [(d, v) for d, v in pool if SEASONS[d.month] == season]
        by_wet = sorted(days, key=lambda dv: -dv[1]["wet"])
        by_heavy = sorted(days, key=lambda dv: -dv[1]["heavy"])
        orders = [by_wet, by_heavy] if season == "sommar" else [by_wet]
        n = 0
        while n < PER_SEASON:
            order = orders[n % len(orders)]
            pick = next(((d, v) for d, v in order if ok(d, season)), None)
            if pick is None:
                break
            chosen.append((pick[0], pick[1], season, "kraftig" if order is not by_wet else "våt"))
            n += 1
    return [{"day": d.isoformat(), "season": s, "valt_efter": why, "wet": v["wet"], "heavy": v["heavy"]}
            for d, v, s, why in sorted(chosen, key=lambda c: c[0])]


def main() -> None:
    days = select(json.loads(CANDIDATES.read_text()), blocked_days())
    OUT.write_text(json.dumps(days, indent=1, ensure_ascii=False) + "\n")
    for d in days:
        print(d["day"], d["season"], d["valt_efter"], d["wet"], d["heavy"])
    print(f"{len(days)} dagar -> {OUT}")


if __name__ == "__main__":
    main()
