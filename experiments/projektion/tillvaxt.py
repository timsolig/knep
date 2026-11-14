"""Tillväxt och avtagande i stor skala ur historiken (uppgift 0018): kedjan gånger en kvot per block som
bara använder det som finns vid utgåvan.

Blockmedlet (box, block_km) av analysen nu och av analysen 30 och 60 min före utgåvan, flyttad längs
kedjans rörelsefält fram till utgåvetiden (samma luftmassa, Lagrange), ger en trend per block: log-kvot per
timme, en anpassning genom nuläget (s = sum(t_i dL_i) / sum(t_i^2) med t_i = 0,5 och 1 h). Kvoten vid
ledtiden L (kvartens mitt, timmar) är exp(s L d(L)) med d = exp(-L / tau), klippt till [1/2, 2] och
utjämnad som block_ratio (gauss, sigma = blocket / 4); kedjans fält multipliceras med den. Där kedjan har
noll blir det noll, så inget regn skapas. Ingen vädermodell och inget facit.

    uv run python experiments/projektion/domare.py kör --läge snabb --procs 2 --system tillvaxt:TV_t60_b32 ...

Systemnamnet är klassen: tillvaxt:TV_t60_b32 sparas som /data/projektion/domare/snabb/tillvaxt_TV_t60_b32/.
Klasserna: TV_t<tau i minuter>_b<block i km>. Inget körs vid import utöver definitioner.
"""

from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import domare as D  # noqa: E402

advect = D.advect
NQ, STEP = D.NQ, D.STEP
EPS = 0.02          # mm/h, som block_ratio
CAP = 2.0           # kvoten klipps till [1/CAP, CAP]
AGES = (30, 60)     # minuter bakåt


def block_mean(f: np.ndarray, size: int):
    """(medel, antal rutor) i glidande block, NaN räknas inte."""
    ok = np.isfinite(f)
    n = D._box(ok.astype(np.float32), size)
    m = D._box(np.where(ok, f, 0.0).astype(np.float32), size) / np.maximum(n, 1)
    return m, n


def trend_per_hour(ctx, t, motion, size: int) -> np.ndarray | None:
    """Log-kvot per timme i varje block ur analysen nu och 30 och 60 min före (flyttade till nu). None om
    ingen äldre bild finns."""
    now = ctx.frame(t)
    m0, n0 = block_mean(now, size)
    l0 = np.log(m0 + EPS)
    num = np.zeros_like(l0)
    den = 0.0
    for age in AGES:
        old = ctx.frame(t - timedelta(minutes=age))
        if old is None:
            continue
        steps = age // 5
        (mx, my, outside), = advect.displacements(motion, [steps])
        adv = advect.warp(np.nan_to_num(old).astype(np.float32), mx, my, outside, 1)
        valid = advect.warp(np.isfinite(old).astype(np.float32), mx, my, outside, 1, outval=0.0)
        adv = np.where(valid > 0.99, adv, np.nan)
        m1, n1 = block_mean(adv, size)
        h = age / 60.0
        num += h * np.where(n1 > size * size * 0.5, l0 - np.log(m1 + EPS), 0.0)  # h dL, dL = L_nu - L_gammal
        den += h * h
    if den == 0:
        return None
    return (num / den).astype(np.float32)   # s = sum(h dL) / sum(h^2)


class Tillvaxt(D.KedjaOm):
    tau_min = 60.0
    block_km = 32.0

    def forecast(self, t, ctx):
        fc = super().forecast(t, ctx)
        if fc is None:
            return None
        size = int(round(self.block_km / ctx.res)) | 1
        motion = ctx.motion(t)
        if motion is None:
            return fc
        s = trend_per_hour(ctx, t, motion, size)
        if s is None:
            return fc
        s = np.clip(s, -3.0, 3.0)
        out = fc.copy()
        for k in range(NQ):
            lead_h = (k + 0.5) * 0.25
            r = np.exp(s * lead_h * np.exp(-lead_h * 60.0 / self.tau_min))
            r = np.clip(r, 1 / CAP, CAP)
            r = gaussian_filter(r.astype(np.float32), size / 4)
            out[k] = fc[k] * r
        return out


def _make(tau, km):
    return type(f"TV_t{tau}_b{km}", (Tillvaxt,), {"tau_min": float(tau), "block_km": float(km)})


for _tau in (30, 60, 120):
    for _km in (32, 64):
        _c = _make(_tau, _km)
        globals()[_c.__name__] = _c
