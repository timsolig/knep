"""Vilka dagar som har nederbörd i norr: andelen rutor norr om 66 N med SMHI > 0,1 mm/h, ur en
bild i timmen i /data/radar. Beror inte på OPERA eller på något resultat. Testdelen läses aldrig.

    uv run python experiments/riksgransen/dagar.py   skriver /data/riksgransen/dagar_norr.json
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import zon  # noqa: E402
from knep.analys import radar  # noqa: E402

_spec = importlib.util.spec_from_file_location("analys_domare", HERE.parent / "analys" / "domare.py")
domare = importlib.util.module_from_spec(_spec)
sys.modules["analys_domare"] = domare
_spec.loader.exec_module(domare)


def main():
    out, lat = {}, None
    for part in ("traning", "validering"):
        for d in domare.days(part):
            day = datetime.fromisoformat(d).replace(tzinfo=UTC)
            fr = []
            for h in range(24):
                p = domare.frame_path(day + timedelta(hours=h, minutes=30))
                if p.exists():
                    r, g = radar.read_rain(p)
                    if lat is None:
                        lat, _ = zon.latlon(zon.grid_of(g))
                        north = lat > 66
                    fr.append(float((np.nan_to_num(r[north]) > 0.1).mean()))
            out[d] = {"del": part, "bilder": len(fr), "vat_norr": round(float(np.mean(fr)), 4) if fr else None}
            print(d, part, out[d], flush=True)
    (zon.OUT / "dagar_norr.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
