"""Varianterna av somlos mot somlos_bas på träningsdagarna (läget snabb): några mått per ledtid,
bara punktvärden (valet görs med somlos.objective; intervallen tas fram på valideringen).

    uv run python experiments/projektion/somlos_tabell.py > experiments/projektion/resultat/somlos_snabb.md
"""

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import domare as D  # noqa: E402
import somlos as S  # noqa: E402

MÅTT = ["q99.9", "yta10", "yta20", "volym", "blockmax_q90", "fss5_30", "fss10_10", "csi5", "fss1_30", "form4_8"]
LI = [D.LEADS.index(k) for k in (4, 8, 12, 20)]


def main():
    days = D.FAST_DAYS
    base = D.scores(D.load("snabb", "somlos_bas", days), days)
    rows = []
    for line in (HERE / "resultat" / "somlos_sok.jsonl").read_text().splitlines():
        r = json.loads(line)
        if "var" in r and r.get("dygn") == len(days):
            rows.append(r)
    rows = sorted({r["var"]: r for r in rows}.values(), key=lambda r: r["mål"])
    print("# somlos: varianterna på träningsdagarna (läget snabb, 6 dygn, 4 km)\n")
    print("Målet (lägre är bättre) är medel av |log kvot| för konserveringen vid 2, 3 och 5 h plus straff "
          "för sämre träff, spärrar och form (somlos.objective). Under målet: värdet för basen och "
          "skillnaden variant minus bas vid 1, 2, 3 och 5 h.\n")
    print("| variant | mål | kons | straff |")
    print("|---|---|---|---|")
    for r in rows:
        print(f"| `{r['var']}` | {r['mål']:.4f} | {r['kons']:.4f} | {r['straff']:.4f} |")
    print()
    print("| mått | bas 1/2/3/5 h | " + " | ".join(f"`{r['var']}`" for r in rows[:5] if r["var"] != "bas") + " |")
    print("|---|---|" + "---|" * len([r for r in rows[:5] if r["var"] != "bas"]))
    sc = {r["var"]: D.scores(D.load("snabb", "somlos_" + r["var"], days), days) for r in rows[:5] if r["var"] != "bas"}
    for m in MÅTT:
        cells = [" ".join(f"{base[m][i]:+.2f}" for i in LI)]
        for v, s in sc.items():
            cells.append(" ".join(f"{s[m][i] - base[m][i]:+.3f}" for i in LI))
        print(f"| {m} | " + " | ".join(cells) + " |")


if __name__ == "__main__":
    main()
