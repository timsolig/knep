"""A0B: A0 med volymkorrektionen bias-v1, dömd av analysens domare (uppgift 0024).

    uv run python experiments/analys/a0b.py kor A0B --del validering --dag 2023-08-08 --ut /dev/shm/bias_v1/domare
    uv run python experiments/analys/a0b.py tabell A0B --mot A0 --del validering --ut /dev/shm/bias_v1/domare

Korrektionen (nivåfaktorn en gång per timme, sedan svansen) läggs på den råa SMHI-bilden före
composite.fill_gaps, utan medelfältsfaktor. Kartan väljs med miljövariabeln KNEP_BIAS_V1
(standard /dev/shm/bias_v1/full/bias_v1.npz). Domaren och dess mått är orörda; A0B läggs bara i
SYSTEMS. Allt skrivs till --ut, inget till /data.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "src"))

# samma modulobjekt som övriga experiment (filter.py) använder
if "analys_domare" in sys.modules:
    domare = sys.modules["analys_domare"]
else:
    _spec = importlib.util.spec_from_file_location("analys_domare", HERE / "domare.py")
    domare = importlib.util.module_from_spec(_spec)
    sys.modules["analys_domare"] = domare
    _spec.loader.exec_module(domare)

import numpy as np  # noqa: E402

from knep.analys import bias  # noqa: E402

KARTA = Path(os.environ.get("KNEP_BIAS_V1", "/dev/shm/bias_v1/full/bias_v1.npz"))
HOUR = 12  # bilder per timme; faktorn räknas om var 12:e bild


class A0B(domare.A0):
    """A0 med volymkorrektionen bias-v1 på den råa SMHI-bilden, före utfyllnaden."""

    namn = "A0B"
    corr: bias.Correction | None = None

    def frames(self):
        if hasattr(self, "_frames"):
            return self._frames
        corr = self.corr or bias.Correction.load(KARTA)
        assert corr is not None, f"kartan saknas: {KARTA}"
        rd = self.rd
        assert corr.beam.shape == rd.grid.shape, (corr.beam.shape, rd.grid.shape)
        rd.sparse_motion()  # rörelsen ur de råa bilderna, som i A0
        K = None
        for k in range(len(rd.times)):
            if k % HOUR == 0:
                K = corr.factor(rd.times[k])
            rd.rain[k] = corr.tail(rd.rain[k] * K)
        return super().frames()


domare.SYSTEMS["A0B"] = A0B


# Varianter (uppgift 0025): samma frysta karta, bara annan påläggning.
def tone(r, K, lo: float, hi: float):
    """r * K^w, w = 0 under lo mm/h, 1 över hi, linjärt i log r däremellan. Eko under lo förblir orört."""
    with np.errstate(invalid="ignore", divide="ignore"):
        w = np.clip((np.log(np.maximum(r, 1e-6)) - np.log(lo)) / (np.log(hi) - np.log(lo)), 0.0, 1.0)
        out = r * np.power(K, w)
    return np.where(w > 0, out, r).astype(np.float32)


class A0B_g0(A0B):
    """Nivåfaktorn utan svans (gamma 0)."""

    namn = "A0B_g0"
    ton: tuple[float, float] | None = None
    kmax: float | None = None

    def _lay(self, r, K):
        if self.kmax is not None:
            K = np.minimum(K, np.float32(self.kmax))
        if self.ton is not None:
            return tone(r, K, *self.ton)
        return (r * K).astype(np.float32)

    def frames(self):
        if hasattr(self, "_frames"):
            return self._frames
        corr = self.corr or bias.Correction.load(KARTA)
        assert corr is not None, f"kartan saknas: {KARTA}"
        rd = self.rd
        assert corr.beam.shape == rd.grid.shape, (corr.beam.shape, rd.grid.shape)
        rd.sparse_motion()
        K = None
        for k in range(len(rd.times)):
            if k % HOUR == 0:
                K = corr.factor(rd.times[k])
            rd.rain[k] = self._lay(rd.rain[k], K)  # aldrig svansen
        return domare.A0.frames(self)


class A0B_ton(A0B_g0):
    """K tonad: w = 0 under 0,3 mm/h, 1 över 1 mm/h."""

    namn = "A0B_ton"
    ton = (0.3, 1.0)


class A0B_ton2(A0B_g0):
    """K tonad: w = 0 under 0,5 mm/h, 1 över 2 mm/h."""

    namn = "A0B_ton2"
    ton = (0.5, 2.0)


class A0B_k2(A0B_g0):
    """K klippt vid 2, tonad som varianten i KNEP_A0B_K2_TON ("lo,hi", tom = ingen tonad)."""

    namn = "A0B_k2"
    kmax = 2.0

    @property
    def ton(self):  # type: ignore[override]
        v = os.environ.get("KNEP_A0B_K2_TON", "")
        return tuple(float(x) for x in v.split(",")) if v else None


for _c in (A0B_g0, A0B_ton, A0B_ton2, A0B_k2):
    domare.SYSTEMS[_c.namn] = _c


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cmd", choices=["kor", "tabell"])
    p.add_argument("system", nargs="+")
    p.add_argument("--del", dest="del_", default="validering", choices=["validering", "traning"])
    p.add_argument("--dag")
    p.add_argument("--mot")
    p.add_argument("--bit", default="0/1")
    p.add_argument("--ut", required=True, help="domarens katalog (en under /dev/shm, aldrig /data)")
    a = p.parse_args()
    assert not str(a.ut).startswith("/data"), "inget nytt till /data"
    domare.set_out(a.ut)
    (domare.cmd_kor if a.cmd == "kor" else domare.cmd_tabell)(a)


if __name__ == "__main__":
    main()
