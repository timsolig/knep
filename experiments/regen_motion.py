"""Skriver om lk30 och rörelsefälten i en katalog med genererade fall, med ett annat rörelsefält.

Allt annat (radarn, KNEP-proxyn, S-PROG och de andra varianterna) kopieras som det är, så att
kedjan med det nya rörelsefältet kan verifieras och extremmodellen tränas om på exakt samma prov.

    python experiments/regen_motion.py <gen> <ny gen> --gap 3 --frames 3
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from pysteps.extrapolation.semilagrangian import extrapolate

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from generate import NS, decode, encode, mask_outside  # noqa: E402

from knep import model  # noqa: E402

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("gen", type=Path)
    p.add_argument("out", type=Path)
    p.add_argument("--gap", type=int, default=3)
    p.add_argument("--frames", type=int, default=3)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    for path in sorted(f for f in a.gen.glob("*.npz") if not f.stem.endswith("_ext")):
        d = dict(np.load(path))
        obs = decode(d["obs"])
        filled = np.nan_to_num(obs, nan=0.0)
        lk30 = np.zeros_like(d["lk30"])
        motion = np.zeros_like(d["motion"])
        for j, i in enumerate(d["issues"]):
            v = model.motion_field(obs[: i + 1], a.gap, a.frames)
            motion[j] = v.astype(np.float16)
            lk30[j] = encode(mask_outside(extrapolate(filled[i], v, NS), obs[i]))
        d["lk30"], d["motion"] = lk30, motion
        np.savez_compressed(a.out / path.name, **d)
        print(f"{path.stem}: klar", flush=True)
