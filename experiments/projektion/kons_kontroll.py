"""Kontroll: konservering:Referens ska ge samma summor som kedja_om (Variant.observe är rätt).

    uv run python experiments/projektion/kons_kontroll.py snabb 2023-07-12
"""

import sys

import numpy as np

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import domare as D  # noqa: E402

mode, day = sys.argv[1], sys.argv[2]
a = np.load(D.OUT / mode / "kedja_om" / f"{day}.npz")
b = np.load(D.OUT / mode / "konservering_Referens" / f"{day}.npz")
worst = 0.0
for k in a.files:
    if k in ("seconds", "forecast_seconds"):
        continue
    d = float(np.nanmax(np.abs(a[k] - b[k]) / np.maximum(np.abs(a[k]), 1e-9))) if a[k].size else 0.0
    worst = max(worst, d)
    if d > 1e-6:
        print(k, d)
print("största relativa skillnad", worst)
