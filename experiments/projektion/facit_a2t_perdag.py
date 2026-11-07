"""Tabellen per dag ur results/facit_a2t.json: CSI 1 mm vid +1 och +5 h, kedjan och persistensen per facit,
och radarns kvot mot A2T vid +1 h (persistensens summa delad med facit är en grov bild av hur torr radarn är).

    uv run python experiments/projektion/facit_a2t_perdag.py
"""

import json
from pathlib import Path

r = json.loads((Path(__file__).resolve().parent / "results" / "facit_a2t.json").read_text())
print("| dag | radar +1 h | A2T +1 h | mätarna +1 h | radar +5 h | A2T +5 h | mätarna +5 h | A0/mätare (pers. +1 h) |")
print("|---|---|---|---|---|---|---|---|")
for d, e in r["per_dag"].items():
    cells = []
    for i in (0, 4):
        for f in ("radar", "a2t", "matare"):
            cells.append(f"{e[f]['csi1_kedja'][i]:.3f} / {e[f]['csi1_persistens'][i]:.3f}".replace(".", ","))
    cells.append(f"{e['matare']['kvot_persistens'][0]:.2f}".replace(".", ","))
    print(f"| {d} | " + " | ".join(cells) + " |")
