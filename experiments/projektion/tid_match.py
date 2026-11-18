"""Tid per utgåva för kedja_om, S_ab_gol och matchningsvarianterna (uppgift 0021), i minnet.

    uv run python experiments/projektion/tid_match.py 2 [2020-08-29 12]
"""

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import domare as D  # noqa: E402
import utjamning_match as M  # noqa: E402
import utjamning_snabb as S  # noqa: E402
from profil_utjamning import prepare  # noqa: E402


def main():
    res = int(sys.argv[1])
    day, hour = (sys.argv[2], int(sys.argv[3])) if len(sys.argv) > 3 else ("2020-08-29", 12)
    s_ref, ctx, t = prepare(D.KedjaOm, res, day, hour)
    a = time.monotonic()
    ref = s_ref.forecast(t, ctx)
    print(f"kedja_om {time.monotonic() - a:.1f} s", flush=True)
    for cls in (S.S_ab_gol, M.M_hel, M.M_hel_gol, M.M_svans2, M.M_svans1, M.M_svansq, M.M_blk64, M.M_blk128):
        s, _, _ = prepare(cls, res, day, hour)
        a = time.monotonic()
        f = s.forecast(t, ctx)
        dt = time.monotonic() - a
        ok = np.isfinite(ref) & np.isfinite(f)
        print(f"{cls.__name__}: {dt:.1f} s, medel|f-kedja| {np.mean(np.abs(f - ref)[ok]):.4f}, "
              f"max {np.nanmax(f):.1f} (kedjan {np.nanmax(ref):.1f}), vol {np.nansum(f) / np.nansum(ref):.3f}", flush=True)


if __name__ == "__main__":
    main()
