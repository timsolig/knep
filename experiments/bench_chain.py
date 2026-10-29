"""Mäter tiden för en driftcykel av kedjan på ett rutnät i Sverigekompositens storlek.

Kör model.Chain på syntetiska fält: Lucas-Kanade på 3 av 7 bilder, extrapolering i 24 steg,
fördelningsmatchning, platskarta och, med --model, sannolikheterna för första timmen.

    python experiments/bench_chain.py [--model models/extremes.pkl]
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from knep import model  # noqa: E402

H, W, STEPS = 894, 475, 24

ap = argparse.ArgumentParser()
ap.add_argument("--model", type=Path, default=None)
ap.add_argument("--prob-steps", type=int, default=12)
a = ap.parse_args()

rng = np.random.default_rng(0)
field = gaussian_filter(rng.gamma(0.3, 4.0, (H + 40, W + 40)), 3).astype(np.float32) * 3
frames = np.stack([field[k * 3 : k * 3 + H, :W] for k in range(7)])
frames[frames < 0.1] = 0
chain = model.Chain(a.model, prob_steps=a.prob_steps)
state = model.State()
t0 = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)
for k in range(13):  # fyll tillståndet så att platskartan räknas
    state.obs[(t0 - k * model.STEP).isoformat()] = frames[-1]
    state.fc30[(t0 - k * model.STEP).isoformat()] = frames[-2]
start = time.perf_counter()
res = chain.run(frames, t0, STEPS, state)
dt = time.perf_counter() - start
print(f"en cykel: {dt:.1f} s för {H} x {W}, {STEPS} steg" + (f", sannolikheter {a.prob_steps} steg" if a.model else ""))
