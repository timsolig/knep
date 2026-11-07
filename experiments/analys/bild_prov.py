"""Provkörning av ekerdetektorn: starkaste strålen per radar på en dag (var timme)."""
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402

from bild import ECHO, NB, RADAR, UTC, datetime, geometry, radar  # noqa: E402

warnings.filterwarnings("ignore")
day = datetime.fromisoformat(sys.argv[1]).replace(tzinfo=UTC)
ps = [RADAR / f"{t:%Y/%m/%d}" / f"{t:%Y%m%d%H%M}.tif" for t in [day + k * radar.STEP for k in range(0, 288, 12)]]
ps = [p for p in ps if p.exists()]
grid = radar.read_rain(ps[0])[1]
geo = geometry(grid)
best = {}
for p in ps:
    rain, _ = radar.read_rain(p)
    cov = np.isfinite(rain)
    ef = (cov & (np.nan_to_num(rain) >= ECHO)).ravel()
    cf = cov.ravel()
    for code, (idx, key, near, lat, lon) in geo.items():
        e = np.bincount(key, ef[idx], NB * 4).reshape(NB, 4)
        n = np.bincount(key, cf[idx], NB * 4).reshape(NB, 4)
        tot = np.where(n.sum(1) >= 20, e.sum(1) / np.maximum(n.sum(1), 1), np.nan)
        fb = np.where(n >= 3, e / np.maximum(n, 1), np.nan)
        side = np.stack([np.roll(tot, s) for s in (*range(3, 11), *range(-10, -2))])
        med = np.nanmedian(side, 0)
        sc = tot - med
        a = int(np.nanargmax(sc))
        if sc[a] > best.get(code, (0,))[0]:
            best[code] = (round(float(sc[a]), 2), a, round(float(tot[a]), 2), round(float(med[a]), 2),
                          np.round(fb[a], 2).tolist(), n[a].tolist(), p.name)
for k, v in best.items():
    print(k, v)
