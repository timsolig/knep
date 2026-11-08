"""Klotterkartan (F4) i ordning som modellfil för src/knep/analys/klotter.py (uppgift 0011).

    uv run python experiments/analys/klotter_modell.py [--kalla /data/analys/filter/v2/klotter_f4.npz]
                                                       [--ut /data/analys/filter/klotter-v1]

Kopierar driftkartan till <ut>/klotter_f4.npz (aldrig i repot), kontrollerar att klotter.load läser
den med radarns rutnät (887 × 471) och skriver <ut>/klotter_f4.json med sha256, storlek, antal
rutor, träningsdagarna som artefakter.py:s summor finns för och commiten. Släpper ingenting och
ändrar inte models/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from knep.analys import klotter  # noqa: E402

SHAPE = (887, 471)
ART_DAG = Path("/data/analys/artefakter/dag")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--kalla", default="/data/analys/filter/v2/klotter_f4.npz")
    p.add_argument("--ut", default="/data/analys/filter/klotter-v1")
    a = p.parse_args()
    ut = Path(a.ut)
    ut.mkdir(parents=True, exist_ok=True)
    dst = ut / "klotter_f4.npz"
    shutil.copyfile(a.kalla, dst)
    m = klotter.load(dst, SHAPE)
    assert m is not None and m.dtype == bool and m.shape == SHAPE, "klotter.load läser inte kartan"
    assert list(np.load(dst).files) == ["klotter"]
    traning = sorted(d["day"] for d in json.loads((ROOT / "experiments/projektion/traning.json").read_text()))
    dagar = [d for d in traning if (ART_DAG / f"{d}.npz").exists()]
    commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    meta = {"fil": str(dst), "sha256": hashlib.sha256(dst.read_bytes()).hexdigest(), "byte": dst.stat().st_size,
            "rutnat": list(SHAPE), "rutor": int(m.sum()), "nyckel": "klotter",
            "dagar": dagar, "antal_dagar": len(dagar), "saknade_traningsdagar": sorted(set(traning) - set(dagar)),
            "byggd_av": "experiments/analys/filter.py karta och karta_drift (F4: torr | eko, utan utvidgning)",
            "commit": commit}
    (ut / "klotter_f4.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps({k: v for k, v in meta.items() if k != "dagar"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
