"""Andra källor i analyssteget, dömda av analysens domare (kön, spåret kallor-analys).

Satellitens molnmask (MSG, experiments/kallor/satellit.py) som torrmask: där satelliten säger klart i
de senaste bilderna som fanns i realtid kan radarn inte ha regn, så ekot där är klotter, anaprop eller
annat falskt. Och OPERA i zonen där den svenska strålen går över nederbörden (A0O, uppgift 0010),
men bara där satelliten säger moln, eftersom A0O fälldes av falska ekon.

    uv run python experiments/analys/kallor.py kor A0S A0S2 A1S --del traning
    uv run python experiments/analys/kallor.py tabell A0S --mot A0 --del traning
    uv run python experiments/analys/kallor.py kor A0OS --del validering

  A0S    A0 med ekot borttaget där den senaste molnmasken (minst 20 min gammal) säger klart
  A0S2   som A0S men de två senaste molnmaskerna måste säga klart (färre ändrade rutor)
  A1S    A1 på A0S:s bilder
  A0OS   A0O (OPERA där SMHI är torr och strålen går över 3 km) bara där satelliten säger moln

Norr om cirka 66 N finns ingen molnmask (koden 3); där ändras ingenting.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "kallor"))
sys.path.append(str(HERE.parent / "riksgransen"))  # sist: riksgransen har en egen fall.py

import a0o  # noqa: E402  laddar analysens domare som analys_domare och registrerar A0O
import satellit  # noqa: E402

domare = a0o.domare
composite, zon = a0o.composite, a0o.zon


class _Satmask:
    """Ekot tas bort där de n senaste molnmaskerna säger klart. Bilderna kopieras, så att A0:s bilder
    (som domaren delar mellan systemen samma dag) inte ändras."""

    n = 1

    def frames(self):
        if getattr(self, "_satfr", None) is not None:
            return self._satfr
        fr = super().frames().copy()
        mm = satellit.Molnmask(self.rd.day_s)
        self.borttaget = 0
        for k, t in enumerate(self.rd.times[: len(fr)]):
            klart = mm.klart(t, self.n) & (np.nan_to_num(fr[k]) > 0)
            self.borttaget += int(klart.sum())
            fr[k][klart] = 0.0
        self._satfr = fr
        return fr


class A0S(_Satmask, domare.A0):
    namn = "A0S"


class A0S2(_Satmask, domare.A0):
    namn = "A0S2"
    n = 2


class A1S(_Satmask, domare.A1):
    namn = "A1S"


class A0OS(a0o.A0O):
    """A0O, men OPERA tas bara där den senaste molnmasken säger moln (eller saknas)."""

    namn = "A0OS"

    def falt(self, dag, matare):
        fr = self.frames().copy()  # A0:s bilder delas med andra system samma dag
        z = zon.load_opera_day(self.rd.day_s)
        if z is None:
            raise FileNotFoundError(f"OPERA saknas för {self.rd.day_s}")
        _, v = z
        far = composite.far_zone(zon.grid_of(self.rd.grid), self.H)
        mm = satellit.Molnmask(self.rd.day_s)
        src = np.zeros(fr.shape[1:], np.uint8)
        for k in range(len(fr)):
            o = zon.decode(v[a0o.opera_index(k)])
            zon_k = far & mm.moln(self.rd.times[k])
            fr[k], _ = composite.layer_far(fr[k], src, o, composite.SOURCE_OPERA, zon_k, mode=self.regel)
        return domare.sums(fr[domare.Radardag.PRE + 1:])


for _c in (A0S, A0S2, A1S, A0OS):
    domare.SYSTEMS[_c.namn] = _c


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cmd", choices=["kor", "tabell"])
    p.add_argument("system", nargs="+")
    p.add_argument("--del", dest="del_", default="traning", choices=["validering", "traning"])
    p.add_argument("--dag")
    p.add_argument("--mot")
    p.add_argument("--bit", default="0/1")
    p.add_argument("--ut", default=None)
    a = p.parse_args()
    domare.set_out(a.ut)
    (domare.cmd_kor if a.cmd == "kor" else domare.cmd_tabell)(a)


if __name__ == "__main__":
    main()
