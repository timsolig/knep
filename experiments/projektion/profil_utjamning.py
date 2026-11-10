"""Tidtagning och profil för utjämningen på en utgåva (uppgift 0020). Skriver inget till disk.

    uv run python experiments/projektion/profil_utjamning.py V_ab_f2_al95 2 2020-08-29 12
"""

import cProfile
import pstats
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import domare as D  # noqa: E402


def prepare(cls, res, day, hour):
    s = cls()
    s.reset()
    ctx = D.Ctx(day, res)
    t = datetime.fromisoformat(day).replace(tzinfo=UTC) + timedelta(hours=hour)
    for k in range(int(D.WARMUP / D.STEP), 0, -1):
        s.observe(t - k * D.STEP, ctx)
    return s, ctx, t


def main():
    import importlib

    name, res, day, hour = sys.argv[1], int(sys.argv[2]), sys.argv[3], int(sys.argv[4])
    mod = importlib.import_module("utjamning_snabb" if name.startswith("S_") else "utjamning")
    cls = getattr(mod, name) if name != "kedja_om" else D.KedjaOm
    s, ctx, t = prepare(cls, res, day, hour)
    t0 = time.monotonic()
    s.forecast(t, ctx)
    print(f"{name} {res} km: {time.monotonic() - t0:.1f} s")
    if len(sys.argv) > 5:
        s, ctx, t = prepare(cls, res, day, hour)
        pr = cProfile.Profile()
        pr.enable()
        s.forecast(t, ctx)
        pr.disable()
        pstats.Stats(pr).sort_stats("cumulative").print_stats(18)


if __name__ == "__main__":
    main()
