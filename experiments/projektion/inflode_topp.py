"""Uppgift 7 natten 2026-11-07: tabellerna för Inflode25 med en platskarta som inte förstärker toppen.

Som `domare.py tabell`, men skriver till en egen fil och kan begränsas till de dygn som är körda
(valideringen kördes bara på en del av dygnen, se rapporten), så att lägets fil inte skrivs över.

    uv run python experiments/projektion/inflode_topp.py <läge> <baslinje> <ut.md> <system> ... [--dagar d1 d2 ...]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import domare as D  # noqa: E402


def main(argv: list[str]) -> None:
    days = None
    if "--dagar" in argv:
        i = argv.index("--dagar")
        argv, days = argv[:i], argv[i + 1:]
    mode, ref, out, *systems = argv
    if days:
        allowed = set(D.mode_days(mode))
        assert set(days) <= allowed, "dygn utanför läget"
        D.mode_days = lambda m: [d for d in days]
    md = D.table(mode, systems, ref)
    if days:
        md = md.replace(f"# Domaren, läge {mode}", f"# Domaren, läge {mode}, dygnen {', '.join(days)}", 1)
    Path(out).write_text(md + "\n")
    print(md)


if __name__ == "__main__":
    main(sys.argv[1:])
