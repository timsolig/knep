"""En ensemble av kedjan över rörelsefälten, med medelvärdet matchat tillbaka till kedjans fördelning (kön, spåret ensemble-rorelse).

Taket för lokal förskjutning är stort de första två timmarna (CSI 1 mm upp till +0,10, kön 0010), men
inget enskilt rörelsefält ur historiken tar hem det (rorelse-lokal) och utjämning fälldes av toppar och
form (0019 till 0021). Här körs kedjan med flera rimliga rörelsefält (driftens Lucas-Kanade, Farnebäck
och en lokalare interpolering), medelvärdet tas som läget där medlemmarna är överens, och värdena tas
tillbaka från driftens kedja med fördelningsmatchning (`model.cdf_match`), så att topparna och ytan
över trösklarna är kedjans. Det är medelvärdet för läget och kedjan för mängden.

    uv run python experiments/projektion/domare.py kör --läge snabb --procs 2 --system ensemble:Ensemble3

  Ensemble2   driftens fält och Farnebäck 32 km
  Ensemble3   driftens fält, Farnebäck 32 km och IDW med 8 grannar och potens 2
  Ensemble3U  som Ensemble3 utan matchningen (medelvärdet som det är), för att se vad matchningen gör
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import rorelse_lokal as R  # noqa: E402

D = R.D
model = D.model


class _Ensemble(D.KedjaOm):
    medlemmar = ("far32",)
    matcha = True
    win_km = 32.0   # Farnebäcks fönster (R._Farneback.falt läser det)

    def _falt(self, namn, t, ctx):
        if namn == "far32":
            return R._Farneback.falt(self, t, ctx)
        if namn == "idw":
            v = R.glesa(ctx, t)
            if v is None:
                return None
            c = self.chain
            return R.idw(*v, ctx.frame(t).shape, 8, 2.0, 20, c.motion_step) / c.motion_gap
        raise KeyError(namn)

    def forecast(self, t, ctx):
        obs = ctx.history(t)
        if obs is None:
            return None
        bas = D.quarters(self.chain.run(obs, t, D.NQ * 3, self.state, motion=ctx.motion(t)).rain)
        led = [bas]
        for namn in self.medlemmar:
            m = self._falt(namn, t, ctx)
            if m is None:
                continue
            st = copy.deepcopy(self.state)   # run skriver i tillståndet; medlemmarna får en kopia
            led.append(D.quarters(self.chain.run(obs, t, D.NQ * 3, st, motion=m).rain))
        if len(led) == 1:
            return bas
        with np.errstate(invalid="ignore"):
            medel = np.nanmean(np.stack(led), axis=0)
        medel[~np.isfinite(bas)] = np.nan
        if not self.matcha:
            return medel.astype(np.float32)
        return np.stack([model.cdf_match(medel[k], bas[k]) for k in range(D.NQ)]).astype(np.float32)


class Ensemble2(_Ensemble):
    medlemmar = ("far32",)


class Ensemble3(_Ensemble):
    medlemmar = ("far32", "idw")


class Ensemble3U(Ensemble3):
    matcha = False
