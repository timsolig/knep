"""Finns MEPS i /data/meps för dagarna? Skriver dagarna och körningarna som saknas.

    uv run python experiments/projektion/meps_koll.py
"""

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))
sys.path.insert(0, str(HERE.parent / "sverige"))
from data import CYCLE, load_days, meps_path  # noqa: E402
from knep.prognos import nwp  # noqa: E402


def runs(day: str) -> list[datetime]:
    d0 = datetime.fromisoformat(day).replace(tzinfo=UTC)
    return sorted({nwp.available(d0 + timedelta(hours=h), CYCLE) for h in range(24)})


def main():
    sets = {"validering": [d["day"] for d in load_days("validering")],
            "traning": [d["day"] for d in json.loads((HERE / "traning.json").read_text())]}
    for name, days in sets.items():
        ok = []
        for day in days:
            miss = [r for r in runs(day) if not meps_path(r).exists()]
            chain = (Path("/data/sverige/kedja") / day).exists()
            print(f"{name} {day}: {'MEPS finns' if not miss else 'saknar ' + ', '.join(f'{r:%dT%H}' for r in miss)}"
                  f"{', kedjan finns' if chain else ''}")
            if not miss:
                ok.append(day)
        print(f"{name}: {len(ok)} av {len(days)} dygn med all MEPS: {ok}\n")


if __name__ == "__main__":
    main()
