"""Sammanfattningens tabell (uppgift 6): alla system i validering_gles mot kedjan, med 95 %-intervall.

Läser bara domarens sparade summor per dygn (/data/projektion/domare/validering_gles/), räknar
ingenting om. Ett system som bara finns på några dygn jämförs med kedjan på samma dygn.

    uv run python experiments/projektion/sammanfatt.py [--nboot 1000]   # skriver resultat/sammanfattning.md
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import domare as D  # noqa: E402

SYSTEMS = [
    ("persistens", "persistens"),
    ("pysteps", "pysteps"),
    ("kedja_utan_matchning", "utan matchning"),
    ("kedja_utan_platskarta", "utan platskarta"),
    ("konservering_NarmastRamp3", "NarmastRamp3"),
    ("konservering_Inflode25", "Inflode25"),
    ("konservering_Inflode75", "Inflode75"),
    ("terrang_Lyft", "Lyft (6 dygn)"),
]
ROWS = [
    ("yta5", "kons"), ("yta10", "kons"), ("yta20", "kons"), ("volym", "kons"), ("q99.9", "kons"), ("blockmax_q90", "kons"),
    ("fss5_30", "träff"), ("fss10_10", "träff"), ("csi5", "träff"), ("sedi10", "träff"),
    ("fss1_30", "spärr"), ("csi1", "spärr"), ("form4_8", "spärr"), ("hopp", "spärr"),
]
COLS = [1, 4, 8, 20]  # 15 min, 1 h, 2 h, 5 h


def days_of(name: str) -> list[str]:
    d = D.OUT / "validering_gles" / name
    return sorted(p.stem for p in d.glob("*.npz"))


def cell(r: dict, i: int, kind: str) -> str:
    if not np.isfinite(r["diff"][i]):
        return "."
    f = "{:+.3f}"
    return f"{f.format(r['diff'][i])} ({f.format(r['lo'][i])}, {f.format(r['hi'][i])}){D.mark(r, i)}"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--nboot", type=int, default=1000)
    p.add_argument("--ut", default=str(Path(__file__).parent / "resultat" / "sammanfattning.md"))
    a = p.parse_args()
    ref_all = days_of("kedja")
    out = ["# Alla system mot kedjan, validering_gles", "",
           "Skillnad mot `kedja`, negativt är bättre (|log kvot| för konservering och form, poängen omvänd för FSS, CSI och SEDI, "
           "hoppet som det är), med 95 %-intervall ur bootstrap över dygnen. `*` helt på den bättre sidan, `!` helt på den sämre "
           f"(för log kvot minst {D.MIN_LOG} från 0). Kolumnerna: 15 min, 1 h, 2 h, 5 h. Domen räknar också 30 min och 3 h.", ""]
    verdicts = []
    for name, label in SYSTEMS:
        days = [x for x in days_of(name) if x in ref_all]
        if not days:
            continue
        s, r = D.load("validering_gles", name, days), D.load("validering_gles", "kedja", days)
        cmp = D.compare(s, r, days, nboot=a.nboot)
        v, why = D.verdict(cmp)
        verdicts.append((label, len(days), v, why))
        out += [f"## {label}", "", f"{len(days)} dygn. Domen: **{v}** ({', '.join(why[:8])}{' …' if len(why) > 8 else ''}).", "",
                "| mått | slag | 15 min | 1 h | 2 h | 5 h |", "|---|---|---|---|---|---|"]
        for m, kind in ROWS:
            idx = [D.LEADS.index(k) for k in COLS]
            out.append(f"| {m} | {kind} | " + " | ".join(cell(cmp[m], i, kind) for i in idx) + " |")
        out.append("")
        print(f"{label}: {v}", file=sys.stderr, flush=True)
    out += ["## Domarna", "", "| system | dygn | dom | celler som avgör |", "|---|---|---|---|"]
    out += [f"| {l} | {n} | {v} | {', '.join(w[:10])} |" for l, n, v, w in verdicts]
    Path(a.ut).write_text("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
