"""Provkörning för domaren: tiden för rörelsefältet och ett A1-intervall, och mätarnas tidsstämplar."""

import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from knep.analys import a1, radar  # noqa: E402
from knep.prognos.model import motion_field  # noqa: E402

t0 = datetime(2023, 8, 8, 12, tzinfo=UTC)
fr = [radar.read_rain(Path(f"/data/radar/{t:%Y/%m/%d}/{t:%Y%m%d%H%M}.tif"))[0]
      for t in [t0 - timedelta(minutes=5 * k) for k in range(6, -1, -1)]]
obs = np.stack(fr)
s = time.time()
m = motion_field(obs, 3, 3, 4)
print("motion", round(time.time() - s, 2), m.shape, float(np.abs(m).mean()))
s = time.time()
f = a1.interval_mean(obs[-2], obs[-1], m)
print("interval", round(time.time() - s, 2))
for p in ("p7", "p14"):
    z = np.load(f"/data/bortfall/matare/{p}.npz")
    print(p, np.unique(z["time"] % 900), float(np.nanmax(z["mm"])), int(np.isnan(z["mm"]).sum()))
