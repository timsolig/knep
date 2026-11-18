"""Uppgift 0013: kontroll av de sparade summorna för kedjan utan fördelningsmatchning.

    python experiments/projektion/utan_matchning_kontroll.py tabell
    python experiments/projektion/utan_matchning_kontroll.py om --dag 2021-05-17 --ut /tmp/k0013

`tabell` skriver domarens tabell för `validering_gles` (kedja, kedja_utan_matchning, persistens) ur
de summor som sparades 2026-11-04, utan att skriva över resultat/validering_gles.md.
`om` räknar ett dygn om med dagens kod till en katalog utanför /data och jämför med de sparade summorna.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import domare as D  # noqa: E402

SYS = "kedja_utan_matchning"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["tabell", "om"])
    p.add_argument("--dag", default="2021-05-17")
    p.add_argument("--ut", default="/tmp/k0013")
    p.add_argument("--nboot", type=int, default=1000)
    a = p.parse_args()
    if a.cmd == "tabell":
        print(D.table("validering_gles", ["kedja", SYS, "persistens"], nboot=a.nboot))
        return
    r = D.run_day("validering_gles", a.dag, SYS, out=Path(a.ut) / SYS)
    s = dict(np.load(D.OUT / "validering_gles" / SYS / f"{a.dag}.npz"))
    for k in D.SUMKEYS:
        print(k, "lika" if np.array_equal(r[k], s[k]) else "OLIKA", float(np.max(np.abs(r[k] - s[k]))))
    print("utgåvor", int(r["issues"]), int(s["issues"]), "sekunder", float(r["seconds"]), "sparat", float(s["seconds"]))


if __name__ == "__main__":
    main()
