"""Tabell för uppgift 0018 utan att skriva över resultat/<läge>.md: skriver till /data/projektion/<fil>.

    uv run python experiments/projektion/tabell_0018.py snabb /data/projektion/tak_tillvaxt_tabell.md tak_TakTillvaxt64 ...
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import domare as D  # noqa: E402

mode, out, systems = sys.argv[1], Path(sys.argv[2]), sys.argv[3:]
md = D.table(mode, systems)
out.write_text(md + "\n")
print(md)
