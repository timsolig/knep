"""Terrängkvoten: en tränad karta över var kedjan systematiskt har för lite eller för mycket regn (kön, spåret terrangkvot).

Nederbörd som är bunden till terrängen (lovartsidor, fjällen) flyttas bort av kedjans rörelse, och
regn som avtar i lä flyttas dit. Det syns som en kvot facit/kedja som beror på platsen, ledtiden och
vindriktningen. Den kvoten lärs här på träningsdagarna och läggs på kedjans prognos, en gång per
kvart; den kan bara förstärka eller dämpa regn som kedjan redan har, aldrig skapa nytt.

Träningen och bedömningen skiljs åt: kartan lärs på träningsdagarna utom de sex i läget snabb
(FAST_DAYS) och bedöms i läget snabb, som alltså inte har setts. Valideringen körs bara för en frusen
variant.

    # 1. samla summorna (kedjan körs om som i drift, inget i domarens summor ändras):
    uv run python experiments/projektion/domare.py kör --läge traning --procs 2 --system terrang:TerrangSamla
    # 2. kartan ur summorna (och dagfilerna tas bort):
    uv run python experiments/projektion/terrang.py karta
    # 3. bedöm:
    uv run python experiments/projektion/domare.py kör --läge snabb --procs 2 --system terrang:KedjaTerrang

  KedjaTerrang          kvot per ruta och ledtimme (alla vindriktningar)
  KedjaTerrangRiktning  kvot per ruta, ledtimme och vindriktning (8 sektorer och svag vind), krympt mot
                        KedjaTerrang där riktningen har lite regn
  KedjaTerrangSvag      som KedjaTerrang med kvoten klippt till [0,75, 1,33] i stället för [0,5, 2]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import domare as D  # noqa: E402

ROOT = Path("/data/projektion/terrang")
SUM = ROOT / "summor"          # en fil per träningsdag, 4 km
KARTA = ROOT / "karta.npz"
NQ = D.NQ
NH = 5                         # ledtimmar: kvart 1 till 4 är timme 0 och så vidare
NS = 9                         # 8 vindsektorer och svag vind
SVAG = 0.5                     # pixlar per 5 min på 4 km (cirka 25 km/h) under vilket vinden räknas som svag
SIGMA_KM = 8.0                 # utjämningen av summorna
PRIOR = 0.05                   # mm/h: krymper kvoten mot 1 där det regnat lite


def ledtimme(k: int) -> int:
    """Kvarten k = 0..19 (slutar 15 min ... 5 h efter utgåvan) till ledtimmen 0..4."""
    return min(NH - 1, k // 4)


def sektor(motion: np.ndarray | None, res: int) -> int:
    """Domänens medelrörelse (2, H, W, pixlar per 5 min) till sektor 0..7 (åt vilket håll regnet går,
    0 = österut, moturs) eller 8 för svag vind eller okänd rörelse."""
    if motion is None:
        return NS - 1
    u, v = float(np.nanmean(motion[0])), float(np.nanmean(motion[1]))
    if not np.isfinite(u) or np.hypot(u, v) * res / 4.0 < SVAG:
        return NS - 1
    ang = np.degrees(np.arctan2(-v, u)) % 360.0  # rad nedåt är söderut
    return int(((ang + 22.5) % 360.0) // 45.0)


def grova(x: np.ndarray, f: int) -> np.ndarray:
    """Summan av f x f rutor (NaN räknas som 0), med kanten som inte går jämnt upp borttagen."""
    if f == 1:
        return np.nan_to_num(x).astype(np.float32)
    h, w = (x.shape[-2] // f) * f, (x.shape[-1] // f) * f
    y = np.nan_to_num(x[..., :h, :w])
    return y.reshape(*x.shape[:-2], h // f, f, w // f, f).sum(axis=(-3, -1)).astype(np.float32)


def kvot(so: np.ndarray, sf: np.ndarray, n: np.ndarray, res: int, lo: float, hi: float) -> np.ndarray:
    """(so + PRIOR·n) / (sf + PRIOR·n) efter utjämning av summorna, klippt till [lo, hi]; 1 där n = 0."""
    s = SIGMA_KM / res
    so, sf, n = (gaussian_filter(a.astype(np.float32), (0,) * (a.ndim - 2) + (s, s)) for a in (so, sf, n))
    with np.errstate(invalid="ignore", divide="ignore"):
        r = (so + PRIOR * n) / (sf + PRIOR * n)
    return np.where(n > 0, np.clip(r, lo, hi), 1.0).astype(np.float32)


class TerrangSamla(D.KedjaOm):
    """Kedjan som i drift; samlar summorna av facit och prognos per ledtimme och sektor (4 km) för dagar
    utanför läget snabb. Prognosen ändras inte."""

    def reset(self):
        super().reset()
        self.acc = None

    def forecast(self, t, ctx):
        fc = super().forecast(t, ctx)
        if fc is None or ctx.day in D.FAST_DAYS:
            return fc
        f = 4 // ctx.res
        s = sektor(ctx.motion(t), ctx.res)
        o = T_facit(t, ctx)
        if self.acc is None:
            shp = grova(fc[0], f).shape
            self.acc = {k: np.zeros((NH, NS) + shp, np.float32) for k in ("so", "sf", "n")}
        for k in range(NQ):
            m = np.isfinite(fc[k]) & np.isfinite(o[k])
            h = ledtimme(k)
            self.acc["so"][h, s] += grova(np.where(m, o[k], 0.0), f)
            self.acc["sf"][h, s] += grova(np.where(m, fc[k], 0.0), f)
            self.acc["n"][h, s] += grova(m.astype(np.float32), f)
        SUM.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(SUM / f"{ctx.day}.npz", **self.acc)  # skrivs om efter varje utgåva
        return fc


def T_facit(t, ctx):
    import tak  # noqa: PLC0415

    return tak.facit(t, ctx)


def bygg_karta() -> None:
    files = sorted(SUM.glob("*.npz"))
    assert files, f"inga summor i {SUM}"
    acc = None
    for p in files:
        z = np.load(p)
        acc = {k: z[k].astype(np.float64) for k in z} if acc is None else {k: acc[k] + z[k] for k in acc}
    np.savez_compressed(KARTA, so=acc["so"].astype(np.float32), sf=acc["sf"].astype(np.float32),
                        n=acc["n"].astype(np.float32), dagar=np.array([p.stem for p in files]))
    for p in files:
        p.unlink()
    alla = kvot(acc["so"].sum(1), acc["sf"].sum(1), acc["n"].sum(1), 4, 0.5, 2.0)
    print(f"karta ur {len(files)} dagar till {KARTA}; kvoten per ledtimme, 5 och 95 %:",
          [tuple(np.round(np.percentile(alla[h], [5, 95]), 2)) for h in range(NH)])


class KedjaTerrang(D.KedjaOm):
    lo, hi = 0.5, 2.0
    riktning = False

    def _karta(self, res):
        if getattr(self, "_r", None) is None or self._res != res:
            z = np.load(KARTA)
            so, sf, n = z["so"], z["sf"], z["n"]
            alla = kvot(so.sum(1), sf.sum(1), n.sum(1), 4, self.lo, self.hi)  # (NH, h, w)
            if self.riktning:
                per = kvot(so, sf, n, 4, self.lo, self.hi)                   # (NH, NS, h, w)
                ns = gaussian_filter(n, (0, 0, SIGMA_KM / 4, SIGMA_KM / 4))
                w = ns / (ns + 200.0)   # krympning mot alla riktningar där sektorn har få rutor med data
                r = w * per + (1 - w) * alla[:, None]
            else:
                r = alla[:, None].repeat(NS, axis=1)
            if res != 4:
                f = 4 // res
                r = r.repeat(f, axis=-2).repeat(f, axis=-1)
            self._r, self._res = r, res
        return self._r

    def forecast(self, t, ctx):
        fc = super().forecast(t, ctx)
        if fc is None:
            return None
        r = self._karta(ctx.res)
        s = sektor(ctx.motion(t), ctx.res)
        out = fc.copy()
        for k in range(NQ):
            rk = r[ledtimme(k), s]
            h, w = min(rk.shape[0], fc.shape[1]), min(rk.shape[1], fc.shape[2])
            out[k, :h, :w] = fc[k, :h, :w] * rk[:h, :w]
        return out


class KedjaTerrangRiktning(KedjaTerrang):
    riktning = True


class KedjaTerrangSvag(KedjaTerrang):
    lo, hi = 0.75, 1.33


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cmd", choices=["karta"])
    p.parse_args()
    bygg_karta()


if __name__ == "__main__":
    main()
