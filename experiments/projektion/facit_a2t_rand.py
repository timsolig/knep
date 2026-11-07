"""Kedjans mängd per kvart mot radarns kvart, nära randen av täckningen och inne i den (uppgift 0006).

    uv run python experiments/projektion/facit_a2t_rand.py

Ur de sparade kvartarna i /data/projektion/facit_a2t/kvartar/kedja/ (prognosen q<hh> och radarns egna
kvartar obs<hh>). Randen: rutor inom 50 km (25 rutor på 2 km) från en ruta utan radar i analysen vid
utgåvan (NaN i prognosen). Bara träningsdagarna i facit_a2t.dagar().
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
from scipy.ndimage import distance_transform_edt

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("facit_a2t", HERE / "facit_a2t.py")
F = importlib.util.module_from_spec(spec)
sys.modules["facit_a2t"] = F
spec.loader.exec_module(F)

RAND_RUTOR = 25


def main():
    tot = {"rand": np.zeros((4, 2)), "inne": np.zeros((4, 2))}
    for day in F.dagar():
        z = np.load(F.UT / "kvartar" / "kedja" / f"{day}.npz")
        for hh in F.ISSUES:
            if f"q{hh:02d}" not in z.files:
                continue
            q, o = z[f"q{hh:02d}"].astype(np.float32), z[f"obs{hh:02d}"].astype(np.float32)
            cov = np.isfinite(q[0])
            inne = distance_transform_edt(cov) > RAND_RUTOR
            for j in range(4):
                ok = np.isfinite(q[j]) & np.isfinite(o[j])
                for name, m in (("rand", ok & ~inne), ("inne", ok & inne)):
                    tot[name][j] += [q[j][m].sum(dtype=np.float64), o[j][m].sum(dtype=np.float64)]
    for name, v in tot.items():
        print(name, "kvot per kvart +15..+60:", np.round(v[:, 0] / v[:, 1], 3).tolist(),
              "andel av radarns regn:", np.round(v[:, 1] / (tot["rand"][:, 1] + tot["inne"][:, 1]), 3).tolist())


if __name__ == "__main__":
    main()
