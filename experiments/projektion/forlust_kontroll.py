"""Kontroll: forlust.py:s steg "platskarta" är samma fält som kedjan (domare.KedjaOm) ger.

    uv run python experiments/projektion/forlust_kontroll.py 2023-07-12 15
"""

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import domare as D  # noqa: E402
import forlust as F  # noqa: E402
from knep.prognos import advect, model  # noqa: E402

day, hour = sys.argv[1], int(sys.argv[2])
t = datetime.fromisoformat(day).replace(tzinfo=UTC) + timedelta(hours=hour)
ctx = D.Ctx(day, 2)
ref = D.KedjaOm()
ref.reset()
for k in range(18, 0, -1):
    ref.observe(t - k * D.STEP, ctx)
fc = ref.forecast(t, ctx)

sysm = D.KedjaOm()
state = F.warm_state(t, ctx, sysm)
corr = model.location_map(state, t, fc.shape[1:])
analysis = ctx.history(t)[-1]
a = np.nan_to_num(analysis).astype(np.float32)
for q in (1, 4, 20):
    ks = [3 * (q - 1) + j for j in range(3)]
    out = []
    for k, (mx, my, outside) in enumerate(advect.displacements(ctx.motion(t), 60)):
        if k in ks:
            b, n = advect.warp(a, mx, my, outside, 1), advect.warp(a, mx, my, outside, 0)
            b[~np.isfinite(analysis)], n[~np.isfinite(analysis)] = np.nan, np.nan
            out.append(model.cdf_match(b, n) * 10 ** (corr * min(1.0, (k + 1) / 6) / 10))
    mine = np.mean(out, 0)
    d = np.nanmax(np.abs(mine - fc[q - 1]))
    print(f"kvart {q}: största skillnad {d:.2e} mm/h, max {np.nanmax(fc[q - 1]):.1f}")
