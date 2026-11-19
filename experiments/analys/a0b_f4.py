"""bias-v1 med klotterfiltret F4 (kön, spåret bias-v1-filter).

bias-v1 (uppgift 0023) ger den största vinsten i mängd som analysens domare har visat (kvot våt per
kvart +0,12), men fälldes i fyra försök (0024, 0025, 0027) bara av falska ekon vid torra mätare. Ett
troligt skäl är att nivåfaktorn också förstärker klotter (vindkraft, fasta ekon), som F4 är byggt för
att ta bort. Här läggs F4 på efter bias-v1, så att de falska ekona som korrektionen lyfter tas bort
innan domaren räknar.

    uv run python experiments/analys/a0b_f4.py kor A0BF4 A0Bk2F4 --del traning --ut /data/bias_v1/domare_tr
    uv run python experiments/analys/a0b_f4.py tabell A0BF4 --mot A0 --del traning --ut /data/bias_v1/domare_tr

Kartan för bias-v1 väljs med KNEP_BIAS_V1 (kön sätter /data/bias_v1/full/bias_v1.npz).

  A0BF4     A0B (bias-v1 som i 0024) och sedan F4 som i experiments/analys/filter.py
  A0Bk2F4   A0B_k2 (0025, den med minst falska ekon) och sedan F4
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ.setdefault("KNEP_BIAS_V1", "/data/bias_v1/full/bias_v1.npz")

import a0b  # noqa: E402  registrerar A0B och varianterna, och laddar domaren som analys_domare
import filter as F  # noqa: E402  F4:s filter

import numpy as np  # noqa: E402

domare = a0b.domare


def med_f4(bas, namn: str):
    """Systemet bas med F4 på varje bild, som filter.make_system gör med A0."""

    class S(bas):
        def falt(self, dag, matare):
            fr = self.frames()
            rd = self.rd
            flt = F.Filter(rd.grid, **F.VARIANTS["F4"])
            k0 = domare.Radardag.PRE + 1
            out = domare.sums_hourly(lambda i: flt.apply(fr[k0 + i], rd.times[k0 + i]), np.float32)
            self.removed = flt.removed
            return out

    S.namn = namn
    S.__name__ = namn
    return S


SYSTEM = {"A0BF4": med_f4(a0b.A0B, "A0BF4"), "A0Bk2F4": med_f4(a0b.A0B_k2, "A0Bk2F4")}
domare.SYSTEMS.update(SYSTEM)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cmd", choices=["kor", "tabell"])
    p.add_argument("system", nargs="+")
    p.add_argument("--del", dest="del_", default="traning", choices=["validering", "traning"])
    p.add_argument("--dag")
    p.add_argument("--mot")
    p.add_argument("--bit", default="0/1")
    p.add_argument("--ut", required=True)
    a = p.parse_args()
    domare.set_out(a.ut)
    (domare.cmd_kor if a.cmd == "kor" else domare.cmd_tabell)(a)


if __name__ == "__main__":
    main()
