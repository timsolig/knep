"""Varianter av den sömlösa modellen (src/knep/seamless.py) för verify5h.py.

Varje system tar verifieringens sammanhang (kedjans kvartar, MEPS, radarn, tillståndet för
dagen) och ger 20 kvartsmedel. Rättningen av MEPS assimileras vid varje utfärdandetid ur
radarns senaste timme mot MEPS-timmen som slutar då.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import numpy as np

from knep import radar, seamless

NQ = 20


def _radar_hour(ctx):
    fs = [ctx["obs"].frame(ctx["t"] - k * radar.STEP) for k in range(12)]
    fs = [f for f in fs if f is not None]
    return np.mean(fs, axis=0) if len(fs) >= 9 else None


def _state(ctx, key, p):
    """Rättningen för tillståndet key, assimilerad en gång per utfärdandetid (system som delar
    key delar också rättningen)."""
    done = ctx.setdefault("assimilated", {})
    if key in done:
        return done[key]
    run, on = ctx["meps_run"]
    k = run.hour_ending(ctx["t"])
    st = ctx["state"].get(key, seamless.State())
    rh = _radar_hour(ctx)
    if k is not None and rh is not None:
        st = seamless.assimilate(st, run.run.isoformat(), on[k], rh, p)
    ctx["state"][key] = done[key] = st
    return st


def _meps(ctx, source):
    """MEPS-kvartarna: "meps" konstant per timme, "meps_i" interpolerad i tiden, "lagg" medlet av
    den senaste och den förra körningen (båda interpolerade)."""
    if source == "lagg":
        return ctx["meps_i"] if ctx["meps_prev"] is None else 0.5 * (ctx["meps_i"] + ctx["meps_prev"])
    return ctx[source]


def corrected(p: seamless.Params, key: str, source: str = "meps_i"):
    def fn(ctx):
        st = _state(ctx, key, p)
        m = _meps(ctx, source)
        return np.stack([seamless.corrected(m[k], 15 * (k + 1) - 7.5, st, p) for k in range(NQ)])
    return fn


def blended(p: seamless.Params, key: str, source: str = "meps_i"):
    def fn(ctx):
        st = _state(ctx, key, p)
        mq = _meps(ctx, source)
        out = []
        for k in range(NQ):
            lead = 15 * (k + 1) - 7.5  # mitt i kvarten
            m = seamless.corrected(mq[k], lead, st, p)
            out.append(seamless.blend(ctx["chain"][k], m, lead, p))
        return np.stack(out)
    return fn


def variant(name: str):
    """Ett system ur namnet "s:t50_small:t50_large:shape[:sigma_km]" (fasta vikter) eller
    "a:t50_small:t50_large:shape:sigma_km:gamma" (anpassade vikter), med den fulla rättningen."""
    kind, *rest = name.split(":")
    parts = [float(x) for x in rest]
    keys = ["t50_small", "t50_large", "shape", "sigma_km"]
    p = replace(P, **dict(zip(keys, parts)))
    if kind == "a":
        return adaptive(p, parts[4] if len(parts) > 4 else 1.0, tag=name)
    return blended(p, "rättad")


P = seamless.Params()
SYSTEMS = {
    "meps_läge": corrected(replace(P, correct_amount=False), "läge"),
    "meps_mängd": corrected(replace(P, correct_shift=False), "mängd"),
    "meps_rättad": corrected(P, "rättad"),
    "meps_lagg_rättad": corrected(P, "rättad", "lagg"),
    "sömlös_rå": blended(replace(P, correct_shift=False, correct_amount=False), "rå"),
    "sömlös": blended(P, "rättad"),
    "sömlös_lagg": blended(P, "rättad", "lagg"),
}


def adaptive(p: seamless.Params, gamma: float = 1.0, source: str = "meps_i", tag: str = ""):
    """Som blended, men viktkurvan flyttas efter hur kedjan och den rättade MEPS-prognosen från
    förra utfärdandetiden (1 h sedan) träffade radarn nu (seamless.adapted)."""
    key = f"adaptiv_{gamma}_{tag}"

    def fn(ctx):
        st = _state(ctx, "rättad", p)
        mem = ctx["state"].get(key)
        o = ctx["obs"].quarter(ctx["t"])
        sc = sm = None
        if mem is not None and mem["t"] == ctx["t"] - timedelta(hours=1) and o is not None:
            sc, sm = seamless.skill(mem["chain"], o), seamless.skill(mem["meps"], o)
        q = seamless.adapted(p, sc, sm, gamma)
        mq = _meps(ctx, source)
        out, meps_c = [], []
        for k in range(NQ):
            lead = 15 * (k + 1) - 7.5
            m = seamless.corrected(mq[k], lead, st, p)
            meps_c.append(m)
            out.append(seamless.blend(ctx["chain"][k], m, lead, q))
        # kvart 4 slutar om 1 h: den prövas vid nästa utfärdandetid
        ctx["state"][key] = {"t": ctx["t"], "chain": ctx["chain"][3], "meps": meps_c[3]}
        return np.stack(out)
    return fn


SYSTEMS |= {"adaptiv": adaptive(P), "adaptiv_2": adaptive(P, 2.0)}
