"""Uppgift 4: en stillastående och en rörlig del av fältet, som system för domaren.

Kedjan (model.Chain) med valet stay = (smax, lyft, fel, tau): andelen
s = smax (1 - exp(-(lyft · max(u·∇h, 0) + fel · max(platskartan, 0)))) av analysen står still och
avtar med tidsskalan tau (min), resten flyttas som förut. u·∇h är lyftet i m per 5 min ur kedjans
rörelse och höjdmodellen (hojd.py, /data/projektion/hojd_2km.npz); platskartan är senaste timmens
fel i dB som kedjan redan räknar. Matchningens mål delas på samma sätt.

    uv run python experiments/projektion/terrang.py <logg> <läge> <system> ...
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import domare as D  # noqa: E402
from konservering import Variant  # noqa: E402
from knep import model  # noqa: E402

HOJD = Path("/data/projektion/hojd_2km.npz")
_cache: dict = {}


def terrain(res: int) -> np.ndarray:
    if res not in _cache:
        _cache[res] = D.coarsen(np.load(HOJD)["h"].astype(np.float32), res // 2)
    return _cache[res]


class Stay(Variant):
    stay: tuple = (0.0, 0.0, 0.0, 60.0)

    stay_target = "split"

    def __init__(self):
        super().__init__()
        self.chain.stay = self.stay
        self.chain.stay_target = self.stay_target

    def _res(self, ctx):
        super()._res(ctx)
        t = terrain(ctx.res)
        self.chain.terrain = t if t.shape == ctx.frame_shape else None

    def forecast(self, t, ctx):
        a = ctx.frame(t)
        if a is not None:
            ctx.frame_shape = a.shape
        return super().forecast(t, ctx)

    def observe(self, t, ctx):
        a = ctx.frame(t)
        if a is None or ctx.history(t) is None:
            return
        ctx.frame_shape = a.shape
        self._res(ctx)
        motion = ctx.motion(t)
        c = self.chain
        corr = model.location_map(self.state, t, a.shape) if c.location else np.zeros(a.shape, np.float32)
        z = c.prepared(a).astype(np.float32)
        raw, tgt = c.project(z, motion, 6, c.stay_fraction(motion, corr))
        raw, tgt = raw[-1], tgt[-1]
        raw[~np.isfinite(a)] = np.nan
        tgt = np.where(np.isfinite(a), tgt, np.nan)
        st = self.state
        st.obs[t.isoformat()] = a.astype(np.float32)
        st.fc30[(t + 6 * model.STEP).isoformat()] = c.matched(raw, tgt)
        st.prune(t)


def _v(name, stay, **kw):
    return type(name, (Stay,), {"kw": kw, "name": name, "stay": stay, "inflow_km": 0.0})


# (smax, lyft per m/5 min, fel per dB, tau min)
Noll = _v("Noll", (0.0, 0.0, 0.0, 60.0))            # kontroll: ska vara exakt kedja_om
# lyftet är upplösningsoberoende (m per 5 min); 10 m/s uppför 50 m per 2 km ger cirka 75 m per 5 min
Lyft = _v("Lyft", (0.5, 0.01, 0.0, 120.0))          # bara lyftet
Fel = _v("Fel", (0.5, 0.0, 0.5, 120.0))             # bara platskartans fel
LyftFel = _v("LyftFel", (0.5, 0.01, 0.5, 120.0))
LyftFelLang = _v("LyftFelLang", (0.5, 0.01, 0.5, 600.0))
LyftFelStark = _v("LyftFelStark", (0.8, 0.03, 1.0, 120.0))
LyftFelSvag = _v("LyftFelSvag", (0.3, 0.005, 0.3, 120.0))
# matchningens mål ur det odelade fältet: delningen ändrar bara var värdena hamnar
LyftHel = type("LyftHel", (Lyft,), {"name": "LyftHel", "stay_target": "whole"})


if __name__ == "__main__":
    sys.stdout = sys.stderr = open(sys.argv[1], "a", buffering=1)
    mode = sys.argv[2]
    for name in sys.argv[3:]:
        print("=====", name, mode, time.strftime("%H:%M:%S"), flush=True)
        D.run(mode, f"terrang:{name}", 2, None)
        print("klar", name, time.strftime("%H:%M:%S"), flush=True)
