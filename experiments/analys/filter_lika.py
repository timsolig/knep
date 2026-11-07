"""Kontroll: src/knep/analys/klotter.rensa med F4:s karta ger samma bilder som kartdelen av F4 i
filter.py (utan ekrarna), på en valideringsdag.

    uv run python experiments/analys/filter_lika.py [dag]
"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import filter as F  # noqa: E402

from knep.analys import klotter  # noqa: E402

domare = F.domare
dag = sys.argv[1] if len(sys.argv) > 1 else "2019-03-08"
assert dag in domare.days("validering") + domare.days("traning")
rd = domare.Radardag(dag)
fr = domare.SYSTEMS["A0"](rd).frames()
m = klotter.load(F.KARTA_DRIFT, fr.shape[1:])
assert m is not None
flt = F.Filter(rd.grid, kontext=0.03, karta=True, ekrar=False, utvidgad=False)
olika = borttagna = 0
for k in range(0, fr.shape[0], 3):
    a = flt.apply(fr[k], rd.times[k])
    b = klotter.rensa(fr[k], m)
    olika += int((np.nan_to_num(a, nan=-1) != np.nan_to_num(b, nan=-1)).sum())
    borttagna += int((np.nan_to_num(fr[k], nan=-1) != np.nan_to_num(b, nan=-1)).sum())
print(dag, "bilder", len(range(0, fr.shape[0], 3)), "olika rutor", olika, "borttagna rutor", borttagna)
