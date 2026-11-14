"""Skillnaden mellan 0019:s utjämning (V_ab_f2_al95) och den snabba (S_ab_gol) på några utgåvor, i minnet,
och tiden per utgåva för kedja_om och de snabba varianterna. Skriver inget till disk.

    uv run python experiments/projektion/jamfor_snabb.py 2
"""

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import domare as D  # noqa: E402
import utjamning as U  # noqa: E402
import utjamning_snabb as S  # noqa: E402
from profil_utjamning import prepare  # noqa: E402

CASES = [("2020-08-29", 12), ("2021-05-11", 15), ("2024-07-28", 12)]


def main():
    res = int(sys.argv[1])
    for day, hour in CASES:
        s_old, ctx, t = prepare(U.V_ab_f2_al95, res, day, hour)
        s_new, _, _ = prepare(S.S_ab_gol, res, day, hour)
        s_ref, _, _ = prepare(D.KedjaOm, res, day, hour)
        tt = {}
        out = {}
        for name, s in (("kedja_om", s_ref), ("V_ab_f2_al95", s_old), ("S_ab_gol", s_new)):
            a = time.monotonic()
            out[name] = s.forecast(t, ctx)
            tt[name] = time.monotonic() - a
        ref, old, new = out["kedja_om"], out["V_ab_f2_al95"], out["S_ab_gol"]
        ok = np.isfinite(old) & np.isfinite(new)
        d = np.abs(old - new)
        d[~ok] = np.nan
        dev = np.abs(old - ref)
        dev[~ok] = np.nan
        print(f"{day} {hour:02d}: tid " + ", ".join(f"{k} {v:.1f} s" for k, v in tt.items()))
        print(f"   skillnad ny mot gammal: störst {np.nanmax(d):.2f} mm/h, medel {np.nanmean(d):.4f}; "
              f"gammal mot kedjan: medel {np.nanmean(dev):.4f}; max i fältet {np.nanmax(old):.1f}", flush=True)
        for k, name in ((None, "S_ab_a"), (None, "S_ab_b"), (None, "S_ab_c")):
            s, _, _ = prepare(getattr(S, name), res, day, hour)
            a = time.monotonic()
            f = s.forecast(t, ctx)
            print(f"   {name}: {time.monotonic() - a:.1f} s, medel|f-kedja| {np.nanmean(np.abs(f - ref)):.4f}, "
                  f"max {np.nanmax(f):.1f} (kedjan {np.nanmax(ref):.1f})", flush=True)


if __name__ == "__main__":
    main()
