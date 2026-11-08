"""Jämför en ombyggd klotterkarta bit för bit med den gamla (uppgift 0011).

    uv run python experiments/analys/karta_lika.py /data/analys/filter /data/analys/filter/v2

Skriver sha256 för filerna, och för varje array i karta.npz och klotter_f4.npz form, typ, antal
sanna rutor och antal olika element; ekrar.json jämförs som json.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def jamfor(a_dir: Path, b_dir: Path) -> bool:
    lika = True
    for namn in ("karta.npz", "klotter_f4.npz", "ekrar.json"):
        a, b = a_dir / namn, b_dir / namn
        ha, hb = sha(a), sha(b)
        print(f"{namn}: sha256 {'lika' if ha == hb else 'OLIKA'}  {ha[:16]} {hb[:16]}  {a.stat().st_size} {b.stat().st_size} byte")
        if namn.endswith(".json"):
            ok = json.loads(a.read_text()) == json.loads(b.read_text())
            print(f"  innehåll {'lika' if ok else 'OLIKA'}")
            lika &= ok
            continue
        za, zb = np.load(a), np.load(b)
        if sorted(za.files) != sorted(zb.files):
            print("  OLIKA nycklar", za.files, zb.files)
            lika = False
            continue
        for k in za.files:
            x, y = za[k], zb[k]
            same = x.shape == y.shape and x.dtype == y.dtype and np.array_equal(x, y, equal_nan=x.dtype.kind == "f")
            n_olika = int((x != y).sum()) if x.shape == y.shape and x.dtype.kind != "f" else (
                int((~((x == y) | (np.isnan(x) & np.isnan(y)))).sum()) if x.shape == y.shape else -1)
            extra = f", sanna {int(x.sum())} och {int(y.sum())}" if x.dtype == bool else ""
            print(f"  {k}: {x.shape} {x.dtype}, olika element {n_olika}{extra}, {'lika' if same else 'OLIKA'}")
            lika &= same
    print("allt lika" if lika else "SKILLNADER")
    return lika


if __name__ == "__main__":
    sys.exit(0 if jamfor(Path(sys.argv[1]), Path(sys.argv[2])) else 1)
