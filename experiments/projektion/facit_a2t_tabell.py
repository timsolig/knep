"""Tabellerna i markdown ur results/facit_a2t.json (uppgift 0005).

    uv run python experiments/projektion/facit_a2t_tabell.py [results/facit_a2t.json]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _f(x, nd=3):
    return f"{x:.{nd}f}".replace(".", ",").replace("-", "−")


def _ci(d, i, j=None, nd=3):
    v, lo, hi = d["v"][i], d["lo"][i], d["hi"][i]
    if j is not None:
        v, lo, hi = _idx(v, j), _idx(lo, j), _idx(hi, j)
    mark = " *" if (lo > 0 or hi < 0) else ""
    return f"{_f(v, nd)} ({_f(lo, nd)} till {_f(hi, nd)}){mark}"


def _idx(x, j):
    for k in j:
        x = x[k]
    return x


def _v(d, i, j=()):
    return _f(_idx(d["v"][i], j))


# (namn, mått, index i måttets sista axlar)
KART = [("CSI 1", "csi", (0,)), ("CSI 5", "csi", (1,)), ("FSS 1/10", "fss", (0, 0)), ("FSS 1/30", "fss", (0, 1)),
        ("FSS 5/10", "fss", (1, 0)), ("FSS 5/30", "fss", (1, 1)), ("kvot", "kvot", ()), ("MAE", "mae", ())]
MAT = [("CSI 1", "csi", (0,)), ("CSI 5", "csi", (1,)), ("kvot", "kvot", ()), ("MAE", "mae", ())]


def tabell(t: dict, matt) -> str:
    k, p, d = t["kedja"], t["persistens"], t["kedja_minus_persistens"]
    rows = ["| mått | +h | kedjan | persistensen | kedjan − persistensen (95 %) |", "|---|---|---|---|---|"]
    for namn, m, j in matt:
        for i in range(5):
            dk = "abs_ln_kvot" if m == "kvot" else m
            rows.append(f"| {namn} | {i + 1} | {_v(k[m], i, j)} | {_v(p[m], i, j)} | {_ci(d[dk], i, j)} |")
    return "\n".join(rows)


def kompakt(t: dict, matt) -> str:
    """En rad per mått: skillnaden per ledtid."""
    d = t["kedja_minus_persistens"]
    rows = ["| mått | " + " | ".join(f"+{i} h" for i in range(1, 6)) + " |", "|---|" + "---|" * 5]
    for namn, m, j in matt:
        dk = "abs_ln_kvot" if m == "kvot" else m
        rows.append(f"| {namn} | " + " | ".join(_ci(d[dk], i, j) for i in range(5)) + " |")
    return "\n".join(rows)


def varden(t: dict, matt) -> str:
    k, p = t["kedja"], t["persistens"]
    rows = ["| mått | " + " | ".join(f"+{i} h" for i in range(1, 6)) + " |", "|---|" + "---|" * 5]
    for namn, m, j in matt:
        rows.append(f"| {namn} | " + " | ".join(f"{_v(k[m], i, j)} / {_v(p[m], i, j)}" for i in range(5)) + " |")
    return "\n".join(rows)


def analyser(t: dict) -> str:
    rows = ["| analys | CSI 1 | CSI 5 | kvot | MAE (mm) |", "|---|---|---|---|---|"]
    for an, namn in (("analys_a0", "A0"), ("analys_a1", "A1"), ("analys_a2", "A2T (har sett mätaren)"),
                     ("analys_a2cv", "A2T utan mätaren (korsvalidering)")):
        x = t[an]
        rows.append(f"| {namn} | {_ci(x['csi'], 0, (0,))} | {_ci(x['csi'], 0, (1,))} | {_ci(x['kvot'], 0)} | {_ci(x['mae'], 0)} |")
    return "\n".join(rows).replace(" *", "")


def main():
    p = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "results" / "facit_a2t.json"
    r = json.loads(p.read_text())
    print(f"dagar {len(r['dagar'])}, utgåvor {sum(r['utgavor'].values())}\n")
    for g, t in r["tabeller"].items():
        matt = MAT if g.startswith("matare") else KART
        n = t["kedja"]["n"]
        print(f"### {g} (n per ledtid {n})\n")
        print("Kedjan / persistensen:\n")
        print(varden(t, matt) + "\n")
        print("Kedjan − persistensen (95 %), * = intervallet helt på ena sidan:\n")
        print(kompakt(t, matt) + "\n")
        if g.startswith("matare"):
            print("Analyserna mot mätarna på samma mätartimmar (ledtiden +1 h:s urval):\n")
            print(analyser(t) + "\n")


if __name__ == "__main__":
    main()
