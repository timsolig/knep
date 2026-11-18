"""Uppgift 0028: överskottet kring varje icke-svensk OPERA-radar mot bakgrunden 40 till 60 km ut,
andel bilder med eko (>= 0,1 mm/h) och med >= 1 mm/h, träningsdagarna.

    uv run python experiments/riksgransen/ring_profil2.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ring_fall as rf  # noqa: E402
import ring_karta as rk  # noqa: E402
import ring_profil as rp  # noqa: E402
import zon  # noqa: E402
from knep.analys import composite  # noqa: E402

V1 = int(np.ceil((10 * np.log10(composite.ZR_A * 1.0 ** composite.ZR_B) + 30) / 0.4))
KANTER = [0, 4, 8, 12, 16, 20, 25, 30, 40, 60]


def main():
    g = rf.grid()
    rk.TMP.mkdir(exist_ok=True)
    f0, f1, cv = None, None, None
    for d in rk.dagar("traning"):
        z = np.load(zon.OPERA_DIR / f"{d}.npz")["v"]
        cov = z != 255
        keep = cov.reshape(len(z), -1).mean(1) > 0.2
        z, cov = z[keep], cov[keep]
        a = ((z >= rk.V_WET) & cov).sum(0).astype(np.float64)
        b = ((z >= V1) & cov).sum(0).astype(np.float64)
        c = cov.sum(0).astype(np.float64)
        f0 = a if f0 is None else f0 + a
        f1 = b if f1 is None else f1 + b
        cv = c if cv is None else cv + c
    ok = cv > 0
    fe = np.where(ok, f0 / np.maximum(cv, 1), np.nan)
    fs = np.where(ok, f1 / np.maximum(cv, 1), np.nan)
    np.savez(rk.TMP / "frek2.npz", fe=fe, fs=fs, cv=cv)
    print("km:", KANTER)
    for namn, (la, lo) in rp.PLATSER.items():
        d = zon.dist_to(g, la, lo)
        row = []
        for nm, arr in (("eko>=0.1", fe), ("eko>=1", fs)):
            vals = []
            for a, b in zip(KANTER[:-1], KANTER[1:]):
                m = (d >= a) & (d < b) & ok
                vals.append(np.nanmean(arr[m]) if m.any() else np.nan)
            bg = np.nanmean(arr[(d >= 40) & (d < 60) & ok]) if ((d >= 40) & (d < 60) & ok).any() else np.nan
            row.append((nm, vals, bg))
        print(f"{namn:7s} " + " | ".join(f"{nm}: " + " ".join(f"{v:.2f}" for v in vals) + f" bg {bg:.2f}" for nm, vals, bg in row))


if __name__ == "__main__":
    main()
