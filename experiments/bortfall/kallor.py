"""Andra källor när en radar saknas, dömda av bortfallsdomaren mot `fylld` (kön, spåret kallor-bortfall).

Driften fyller ett hål med den senaste analysen flyttad längs rörelsen (`fylld`, composite.fill_gaps).
Här prövas det som också finns i realtid: OPERA (grannländernas radarer når in i hålet), satellitens
molnmask (där det är klart kan det inte regna) och regnmätarna (som kommer en timme sent).

    uv run python experiments/bortfall/bortfallsdomare.py kor kallor:FylldS --del traning --processer 2
    uv run python experiments/bortfall/bortfallsdomare.py tabell kallor:FylldS --mot fylld --del traning

  FylldS      fylld, men 0 i hålet där den senaste molnmasken (minst 20 min gammal) säger klart
  UtjamnadS   utjamnad (fill_gaps med utjämning) och satellitens torrmask
  FylldO      OPERA i hålet där den finns (kvarten som började senast 5 min före bilden), annars fylld
  FylldOS     FylldO och satellitens torrmask
  FylldM      fylld gånger en kvot ur timmätarna i och kring hålet (perioder som slutat minst 60 min före)
  FylldOSM    FylldOS och mätarnas kvot
  FylldO30    utfyllnaden de första 30 min av bortfallet, sedan OPERA (FylldO60 efter 60 min)

OPERA läses ur /data/riksgransen/opera15/<dag>.npz (experiments/riksgransen/hamta.py --steg 15), satelliten
ur /data/kallor/msgclm/<dag>.npz (experiments/kallor/satellit.py). Saknas en dag ändras ingenting.
"""

from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "kallor"))
sys.path.append(str(HERE.parent / "riksgransen"))  # sist: riksgransen har en egen fall.py

import bortfallsdomare as B  # noqa: E402
import satellit  # noqa: E402

OPERA_FORDROJNING = timedelta(minutes=5)
KVOT_GRANS = (0.5, 2.0)
KVOT_PRIOR = 2.0   # mm: krymper kvoten mot 1 när mätarna har lite regn


def _utsnitt(ind):
    r0, r1, c0, c1 = ind.meta["utsnitt"]
    return slice(r0, r1), slice(c0, c1)


class _Kallor(B.Fylld):
    satellit = False
    opera = False
    matare = False
    opera_efter_min = 0   # OPERA först när bortfallet är äldre än så (utfyllnaden är bättre i början)

    def start(self, ind):
        dag = ind.meta["dag"]
        self.rs, self.cs = _utsnitt(ind)
        self.mm = satellit.Molnmask(dag) if self.satellit else None
        self.op = None
        if self.opera:
            import zon  # noqa: PLC0415

            z = zon.load_opera_day(dag)
            if z is not None:
                tider, v = z
                self.op = (np.asarray(tider), v, zon)
        self.historik = []   # (tid, analys) för mätarnas kvot
        super().start(ind)

    def _opera(self, t):
        tider, v, zon = self.op
        ts = np.array([x.timestamp() if hasattr(x, "timestamp") else float(x) for x in tider])
        i = int(np.searchsorted(ts, (t - OPERA_FORDROJNING).timestamp(), side="right")) - 1
        if i < 0 or (t - OPERA_FORDROJNING).timestamp() - ts[i] > 1800:
            return None
        return zon.decode(v[i])[self.rs, self.cs]

    def _kvot(self, ind, t) -> float:
        g = ind.matare.get("p7")
        if not g or not len(g.get("tid", [])):
            return 1.0
        sg = sf = 0.0
        for i in range(len(g["tid"])):
            slut = float(g["tid"][i])
            mm = float(g["mm"][i])
            if not (0 <= mm <= 60) or not g["i_hal"][i]:
                continue
            bilder = [a for (tt, a) in self.historik if slut - 3600 < tt.timestamp() <= slut]
            if len(bilder) < 10:
                continue
            r, c = int(g["rad"][i]), int(g["kol"][i])
            sg += mm
            sf += float(np.nansum([b[r, c] for b in bilder])) * 5 / 60
        return float(np.clip((sg + KVOT_PRIOR) / (sf + KVOT_PRIOR), *KVOT_GRANS))

    def steg(self, k, ind):
        out = super().steg(k, ind).copy()
        hal = ind.hal & ~np.isfinite(ind.bild)
        t = ind.tid
        if self.op is not None and 5 * (k + 1) > self.opera_efter_min:
            o = self._opera(t)
            if o is not None:
                ta = hal & np.isfinite(o)
                out[ta] = o[ta]
        if self.matare:
            out[hal] = out[hal] * self._kvot(ind, t)
        if self.mm is not None:
            klart = self.mm.klart(t, 1)[self.rs, self.cs]
            out[hal & klart] = 0.0
        self.historik = (self.historik + [(t, out.copy())])[-36:]
        return out


class FylldS(_Kallor):
    namn = "kallor_FylldS"
    satellit = True


class UtjamnadS(FylldS):
    namn = "kallor_UtjamnadS"
    smooth = True


class FylldO(_Kallor):
    namn = "kallor_FylldO"
    opera = True


class FylldOS(_Kallor):
    namn = "kallor_FylldOS"
    opera = satellit = True


class FylldM(_Kallor):
    namn = "kallor_FylldM"
    matare = True


class FylldOSM(_Kallor):
    namn = "kallor_FylldOSM"
    opera = satellit = matare = True


class FylldO30(FylldO):
    """Utfyllnaden de första 30 minuterna, sedan OPERA (kön 0222: OPERA förlorar bara vid 0 till 30 min)."""

    namn = "kallor_FylldO30"
    opera_efter_min = 30


class FylldO60(FylldO):
    namn = "kallor_FylldO60"
    opera_efter_min = 60
