"""Varianter av den sömlösa modellen (src/knep/seamless.py) för verify5h.py.

Varje system tar verifieringens sammanhang (kedjans kvartar, MEPS, radarn, tillståndet för
dagen) och ger 20 kvartsmedel. Rättningen av MEPS assimileras vid varje utfärdandetid ur
radarns senaste timme mot MEPS-timmen som slutar då.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from knep import radar, seamless

NQ = 20


def _radar_hour(ctx):
    fs = [ctx["obs"].frame(ctx["t"] - k * radar.STEP) for k in range(12)]
    fs = [f for f in fs if f is not None]
    return np.mean(fs, axis=0) if len(fs) >= 9 else None


def _state(ctx, key, p):
    run, on = ctx["meps_run"]
    k = run.hour_ending(ctx["t"])
    st = ctx["state"].get(key, seamless.State())
    rh = _radar_hour(ctx)
    if k is not None and rh is not None:
        st = seamless.assimilate(st, run.run.isoformat(), on[k], rh, p)
    ctx["state"][key] = st
    return st


def corrected(p: seamless.Params, key: str):
    def fn(ctx):
        st = _state(ctx, key, p)
        return np.stack([seamless.corrected(ctx["meps"][k], 15 * (k + 1), st, p) for k in range(NQ)])
    return fn


def blended(p: seamless.Params, key: str):
    def fn(ctx):
        st = _state(ctx, key, p)
        out = []
        for k in range(NQ):
            lead = 15 * (k + 1) - 7.5  # mitt i kvarten
            m = seamless.corrected(ctx["meps"][k], lead, st, p)
            out.append(seamless.blend(ctx["chain"][k], m, lead, p))
        return np.stack(out)
    return fn


P = seamless.Params()
SYSTEMS = {
    "meps_läge": corrected(replace(P, correct_amount=False), "läge"),
    "meps_mängd": corrected(replace(P, correct_shift=False), "mängd"),
    "meps_rättad": corrected(P, "rättad"),
    "sömlös_rå": blended(replace(P, correct_shift=False, correct_amount=False), "rå"),
    "sömlös": blended(P, "sömlös"),
}
