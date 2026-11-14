"""Tabell för uppgift 0018 utan att skriva över resultat/<läge>.md: skriver till den angivna filen.

    uv run python experiments/projektion/tabell_0018.py snabb /data/projektion/x.md tak_TakTillvaxt64 ...
    uv run python experiments/projektion/tabell_0018.py traning x.md tillvaxt_TV_t60_b64 persistens --dagar 2020-02-10 ...

Med --dagar räknas bara de dygnen (när ett läge inte är körd för alla dygn).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import domare as D  # noqa: E402

args = sys.argv[1:]
days = None
if "--dagar" in args:
    i = args.index("--dagar")
    days, args = args[i + 1:], args[:i]
mode, out, systems = args[0], Path(args[1]), args[2:]
if days:
    D.mode_days = lambda _mode: days
md = D.table(mode, systems)
out.write_text(md + "\n")
print(md)
