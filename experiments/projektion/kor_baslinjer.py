"""Baslinjerna genom domaren, i den ordning de körs i natt (varje dygn sparas, så det går att avbryta och fortsätta).

    uv run python experiments/projektion/kor_baslinjer.py /data/projektion/logg/baslinjer.log
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import domare as D  # noqa: E402

PLAN = [
    ("validering_gles", "kedja", None),
    ("validering_gles", "persistens", None),
    ("validering", "kedja_om", ["2023-08-08", "2021-05-17"]),   # tidmätning av ett uppvärmt system
    ("validering_gles", "kedja_utan_platskarta", None),
    ("validering_gles", "pysteps", None),
    ("validering_gles", "kedja_utan_matchning", None),
    ("validering_gles", "sprog", None),
    ("validering", "kedja", None),
    ("validering", "persistens", None),
]

if __name__ == "__main__":
    if len(sys.argv) > 1:
        sys.stdout = sys.stderr = open(sys.argv[1], "a", buffering=1)
    for mode, name, days in PLAN:
        D.run(mode, name, 2, days)
