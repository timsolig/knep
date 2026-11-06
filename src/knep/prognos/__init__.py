"""Tim-KNEP prognos: nederbörden 0 till 5 h framåt ur analysen.

Prognosen läser bara analysen (knep.analys.Analys) och sitt eget tillstånd i cache/state/.
Kedjan är model.Chain (rörelse, extrapolering, fördelningsmatchning, platskarta och
sannolikheter för kraftig nederbörd ur extremes.py); efter de första timmarna blandas MEPS
rättad mot radarn in (seamless.py och nwp.py). model.nowcast är referensen.

Rörelsefältet sparas i cache/state/motion.npy, och analysen använder det för att flytta förra
analysen in i radarbortfall i nästa cykel. Det är det enda som går från prognosen till analysen.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import requests

from . import model

log = logging.getLogger("knep")


@dataclass
class Prognos:
    rain: np.ndarray  # (steg, rader, kolumner), mm/h var 5:e minut efter analysen
    prob: np.ndarray | None  # sannolikheter för kraftig nederbörd (trösklar, steg, rader, kolumner)
    extra: dict = field(default_factory=dict)  # till manifestet, t.ex. seamless
    motion: np.ndarray | None = None  # (2, rader, kolumner) pixlar per 5 min, kedjans rörelsefält


def kor(analys, state_dir: Path, steps: int, *, model_path: Path | None = None, prob_hours: float = 2.0,
        reference: bool = False, seamless: bool = False, meps_cache: Path | None = None,
        session: requests.Session | None = None) -> Prognos:
    """Prognosen för `steps` steg om 5 min från analysen.

    seamless: blanda in MEPS (bara i realtid, eftersom MEPS bara finns för senaste körningen).
    """
    started = time.monotonic()
    obs, t0 = analys.rain, analys.t0
    extra = {}
    prob = None
    motion = None
    if reference:
        fc = model.nowcast(obs, steps)
    else:
        chain = model.Chain(model_path if model_path is not None and model_path.exists() else None,
                            prob_steps=round(prob_hours * 12))
        state = model.State.load(state_dir / "model.npz")
        res = chain.run(obs, t0, steps, state)
        state.save(state_dir / "model.npz")
        np.save(state_dir / "motion.npy", res.motion.astype(np.float32))
        motion = res.motion
        fc, prob = res.rain, res.prob
        if seamless:
            from . import seamless as sm
            try:
                fc, extra["seamless"] = sm.run_operational(meps_cache, state_dir / "seamless.npz", session,
                                                           analys.grid, t0, obs, fc)
            except (requests.RequestException, ValueError, KeyError, OSError) as e:  # utan MEPS: bara kedjan
                log.warning("MEPS: %s", e)
    log.info("prognos %s, %d steg på %.1f s", t0, steps, time.monotonic() - started)
    return Prognos(fc, prob, extra, motion)
