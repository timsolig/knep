"""Uppgift 3: varianter av kedjans projektion och matchning, som system för domaren.

Varje variant är kedjan (model.Chain) med ett eller flera val ändrade, och med platskartans
tillstånd uppvärmt på samma sätt som baslinjen (domare.KedjaOm), men där 30-minutersprognosen i
tillståndet görs med variantens egen flytt och matchning, som i drift.

    uv run python experiments/projektion/domare.py kör --läge snabb --system konservering:Bikubisk
    uv run python experiments/projektion/konservering.py <logg> <läge> <system> ...

Varianterna (namnen är klasser här):

    Bikubisk      flytten bikubisk, klippt till [0, största grannvärdet]
    Narmast       flytten med närmaste granne (värdena bevaras, ingen utjämning)
    Skarp05/1/2   rangordningen i matchningen efter ett skärpt fält (sharpen 0,5, 1, 2)
    Analys        matchningen mot hela analysens fördelning (target="analysis")
    BikubiskSkarp1, BikubiskAnalys, ...  kombinationer
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import domare as D  # noqa: E402
from knep import model  # noqa: E402


class Variant(D.KedjaOm):
    kw: dict = {}

    def __init__(self):
        super().__init__(**self.kw)

    def observe(self, t, ctx):
        """Som KedjaOm.observe, men 30-minutersprognosen med variantens flytt, mål och matchning."""
        a = ctx.frame(t)
        if ctx.history(t) is None:
            return
        motion = ctx.motion(t)
        z = np.nan_to_num(a).astype(np.float32)
        raw, tgt = self.chain.project(z, motion, 6)
        raw, tgt = raw[-1], (a if self.chain.target != "advected" else tgt[-1])
        raw[~np.isfinite(a)] = np.nan
        tgt = np.where(np.isfinite(a), tgt, np.nan)
        st = self.state
        st.obs[t.isoformat()] = a.astype(np.float32)
        st.fc30[(t + 6 * model.STEP).isoformat()] = self.chain.matched(raw, tgt)
        st.prune(t)


def _v(name, **kw):
    return type(name, (Variant,), {"kw": kw, "name": name})


Bikubisk = _v("Bikubisk", interp="cubic")
Narmast = _v("Narmast", interp="nearest")
Skarp05 = _v("Skarp05", sharpen=0.5)
Skarp1 = _v("Skarp1", sharpen=1.0)
Skarp2 = _v("Skarp2", sharpen=2.0)
Analys = _v("Analys", target="analysis")
BikubiskSkarp1 = _v("BikubiskSkarp1", interp="cubic", sharpen=1.0)
BikubiskAnalys = _v("BikubiskAnalys", interp="cubic", target="analysis")
BikubiskSkarp1Analys = _v("BikubiskSkarp1Analys", interp="cubic", sharpen=1.0, target="analysis")
Referens = _v("Referens")  # samma som kedja_om, för att kontrollera att Variant.observe är rätt


if __name__ == "__main__":
    sys.stdout = sys.stderr = open(sys.argv[1], "a", buffering=1)
    mode = sys.argv[2]
    for name in sys.argv[3:]:
        print("=====", name, mode, time.strftime("%H:%M:%S"), flush=True)
        D.run(mode, name if ":" in name else f"konservering:{name}", 2, None)
        print("klar", name, time.strftime("%H:%M:%S"), flush=True)
