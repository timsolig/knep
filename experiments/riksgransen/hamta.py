"""OPERA-kompositen för hela dagar, utskuren till radarns rutnät (zon.encode) och sparad per dag.

    uv run python experiments/riksgransen/hamta.py --steg 5 2019-03-08 ...    till /data/riksgransen/opera/
    uv run python experiments/riksgransen/hamta.py --steg 15 2020-02-10 ...   till /data/riksgransen/opera15/

Tiderna är domarens Radardag (00:00 − 30 min till 24:00) i steget. Originalfilen raderas direkt
efter utskärningen; högst cirka 1 anrop per sekund; avbryter om /data har under 3 GB ledigt.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import zon  # noqa: E402
from knep.analys import radar  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument("dagar", nargs="+")
    p.add_argument("--steg", type=int, default=5)
    a = p.parse_args()
    import requests
    s = requests.Session()
    out_dir = zon.OPERA_DIR if a.steg == 5 else zon.OUT / f"opera{a.steg}"
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = zon.OUT / f"tmp{a.steg}"
    grid = None
    for d in a.dagar:
        out = out_dir / f"{d}.npz"
        if out.exists():
            continue
        if shutil.disk_usage("/data").free < 3e9:
            sys.exit("under 3 GB ledigt på /data, avbryter")
        day = datetime.fromisoformat(d).replace(tzinfo=UTC)
        times = [day + timedelta(minutes=-30 + a.steg * k) for k in range(24 * 60 // a.steg + 30 // a.steg + 1)]
        if grid is None:
            grid = zon.grid_of(radar.read_rain(_any_frame(day))[1])
        frames, missing, t_start = [], [], time.time()
        for t in times:
            t0 = time.time()
            o = zon.fetch_opera_frame(s, t, grid, tmp)
            if o is None:
                missing.append(t.isoformat())
                frames.append(np.full(grid.shape, 255, np.uint8))
            else:
                frames.append(zon.encode(o))
            time.sleep(max(0.0, 1.0 - (time.time() - t0)))
        np.savez_compressed(out, v=np.stack(frames), times=np.array([t.isoformat() for t in times]),
                            saknas=np.array(missing))
        print(d, len(times), "bilder,", len(missing), "saknas,", f"{out.stat().st_size / 1e6:.1f} MB,",
              f"{time.time() - t_start:.0f} s", flush=True)


def _any_frame(day):
    for h in range(24):
        p = radar_path(day + timedelta(hours=h))
        if p.exists():
            return p
    raise FileNotFoundError(day)


def radar_path(t):
    return Path("/data/radar") / f"{t:%Y/%m/%d}" / f"{t:%Y%m%d%H%M}.tif"


if __name__ == "__main__":
    main()
