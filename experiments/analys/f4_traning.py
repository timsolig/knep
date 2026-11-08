"""F4 mot A0 på träningsdagarna med den nya domaren, alla dagar och de 13 från 2026-11-06 (uppgift 0011).

    uv run python experiments/analys/f4_traning.py [--sys F4] [--mot A0]

Läser dagfilerna i /data/analys/domare_v2/ (domare.load_results, bara träningsdelen), räknar
domarens tabell och domarna med den nya och den gamla regeln för alla träningsdagar som har
dagfiler och för de 13 dagar som bedömningen 2026-11-06 gjordes på, skriver huvudraderna och
sparar /data/analys/domare_v2/f4_traning_jamforelse.json. Domaren ändras inte.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("analys_domare", HERE / "domare.py")
domare = importlib.util.module_from_spec(_spec)
sys.modules["analys_domare"] = domare
_spec.loader.exec_module(domare)

DAGAR13 = ["2020-02-10", "2020-07-24", "2020-10-07", "2021-01-23", "2021-05-11", "2022-12-20", "2023-01-04",
           "2023-07-12", "2023-11-22", "2024-07-28", "2024-09-26", "2025-06-23", "2025-10-24"]

RADER = [(k, m) for k in ("kvart/alla", "timme/alla", "kvart/over400", "timme/over400", "kvart/lovart", "timme/lovart")
         for m in ("kvot våt", "kvot summa", "falskt vid torr mätare", "falskt där allt inom 25 km är torrt",
                   "FSS 0.5", "FSS 1", "FSS 5", "CSI 0.5", "MAE")]


def bedom(s: dict, b: dict) -> dict:
    tab = domare.table(s, b)
    return {"dagar": sorted(set(s) & set(b)), "tabell": tab,
            "dom": domare.verdict(tab), "dom_gammal_regel": domare.verdict(tab, regel="gammal"),
            "dom_utan_underlagskrav": domare.verdict(tab, min_days=0)}


def visa(namn: str, r: dict) -> None:
    print(f"\n== {namn}: {len(r['dagar'])} dagar")
    for k, m in RADER:
        x = r["tabell"][k].get(m)
        if x is None:
            continue
        print(f"  {k:14s} {m:36s} {x['varde']:.5f} mot {x['bas']:.5f}  {x['diff']:+.6f} "
              f"({x['lo']:+.6f} till {x['hi']:+.6f})  dagar {x['dagar']}")
    x = r["tabell"]["rutor"]["rutor med eko i över hälften av de torra timmarna, per dag"]
    print(f"  kartmåttet {x['varde']:.2f} mot {x['bas']:.2f}  {x['diff']:+.2f} ({x['lo']:+.2f} till {x['hi']:+.2f})")
    for d in ("dom", "dom_gammal_regel", "dom_utan_underlagskrav"):
        if d in r:
            print(f"  {d}: {json.dumps(r[d], ensure_ascii=False)}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--sys", default="F4")
    p.add_argument("--mot", default="A0")
    p.add_argument("--validering", action="store_true",
                   help="skriv bara huvudraderna ur den sparade tabellen för valideringen (räknar inget om)")
    a = p.parse_args()
    if a.validering:
        r = json.loads((domare.OUT / f"tabell_{a.sys}_mot_{a.mot}_validering.json").read_text())
        visa("validering (sparad tabell)", r)
        return
    s, b = domare.load_results(a.sys, "traning"), domare.load_results(a.mot, "traning")
    ut = {"alla": bedom(s, b),
          "dagar13": bedom({d: s[d] for d in DAGAR13 if d in s}, {d: b[d] for d in DAGAR13 if d in b})}
    for namn, r in ut.items():
        visa(namn, r)
    (domare.OUT / f"{a.sys.lower()}_traning_jamforelse.json").write_text(
        json.dumps(ut, ensure_ascii=False, indent=1, default=float))


if __name__ == "__main__":
    main()
