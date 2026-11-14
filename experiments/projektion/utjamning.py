"""Utjämning efter fältets osäkerhet (uppgift 0019): kedjans fält per kvart utjämnat med ett sigma som
varierar över ytan efter ett mått som bara använder det som finns vid utgåvan.

Två mått (väljs med `maatt`, båda kan användas, det större sigmat gäller):

  a  två rörelsefält: kedjans fält (tre bilder med 15 min mellan) mot ett fält ur de tre senaste bilderna
     med 5 min mellan (Lucas-Kanade som i kedjan). Förflyttningsskillnaden vid ledtiden är
     |v1 - v2| · steg · ruta (km); sigma = ka · skillnaden, utjämnad med gauss om SMOOTH_KM.
  b  start 30 min tidigare: bilden vid t - 30 min flyttad med rörelsen då och bilden vid t flyttad med
     rörelsen nu, till kvartarnas mitt; osäkerheten är den relativa skillnaden i block om BLOCK_KM,
     u = medel|a - b| / (medel(a + b) / 2 + 0,1), sigma = kb · u (km). Billig (en förflyttning per kvart,
     ingen kedjekörning).

Utjämningen görs som en linjär blandning mellan gaussfilter med fasta sigma (LEVELS km), så att kostnaden
är några filter per kvart. Toppen skyddas: utdata = max(utjämnat, alfa · original). Ingen utjämning
de första `fri` kvartarna. Med sigma = 0 överallt (ka = kb = 0) blir resultatet exakt kedjans (se
test_utjamning.py). Ingen vädermodell, inget facit.

    uv run python experiments/projektion/domare.py kör --läge snabb --procs 2 --system utjamning:U_a1

Klasserna U_<namn> är definierade längst ned. Inget körs vid import utöver definitioner.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import domare as D  # noqa: E402
from tak import smooth  # noqa: E402

advect, model = D.advect, D.model
NQ, STEP = D.NQ, D.STEP
LEVELS = np.array([0.0, 4.0, 8.0, 16.0, 24.0])   # km
SMOOTH_KM = 32.0
BLOCK_KM = 24.0
EPS = 0.1


def blend_levels(fc: np.ndarray, sigma_km: np.ndarray, res: float) -> np.ndarray:
    """fc (H, W) utjämnad med sigma (H, W) i km, linjärt mellan LEVELS; NaN som i tak.smooth."""
    s = np.clip(np.nan_to_num(sigma_km), 0, LEVELS[-1])
    if float(s.max()) <= 0.05:
        return fc
    idx = np.clip(np.searchsorted(LEVELS, s, side="right") - 1, 0, len(LEVELS) - 2)
    lo, hi = LEVELS[idx], LEVELS[idx + 1]
    w = np.clip((s - lo) / (hi - lo), 0, 1)
    out = np.zeros_like(fc, np.float32)
    for i in range(len(LEVELS) - 1):
        sel = idx == i
        if not sel.any():
            continue
        a = fc if i == 0 else smooth(fc, LEVELS[i] / res)
        b = smooth(fc, LEVELS[i + 1] / res)
        out = np.where(sel, (1 - w) * np.nan_to_num(a) + w * np.nan_to_num(b), out)
    return np.where(np.isfinite(fc), out, np.nan).astype(np.float32)


class Utjamning(D.KedjaOm):
    maatt = "a"
    ka = 1.0          # sigma (km) per km förflyttningsskillnad
    kb = 8.0          # sigma (km) per enhet relativ skillnad
    alfa = 0.8        # toppskydd: utdata >= alfa * original
    fri = 0           # antal första kvartar utan utjämning

    # ---- måtten ----
    def sigma_a(self, t, ctx, motion):
        obs = ctx.history(t)
        if obs is None:
            return None
        xy, uv = model._quiet(model.dense_lucaskanade, model._db(obs[-3:]), dense=False)
        v2 = model.dense_motion(np.asarray(xy, np.float64), np.asarray(uv, np.float64), obs[-1].shape,
                                self.chain.motion_step)
        dv = np.hypot(motion[0] - v2[0], motion[1] - v2[1]) * ctx.res            # km per steg
        dv = gaussian_filter(dv.astype(np.float32), SMOOTH_KM / ctx.res)
        steps = 3.0 * (np.arange(NQ) + 0.5)
        return [self.ka * dv * s for s in steps]

    def sigma_b(self, t, ctx, motion):
        from datetime import timedelta
        t0 = t - timedelta(minutes=30)
        old, now, m0 = ctx.frame(t0), ctx.frame(t), ctx.motion(t0)
        if old is None or m0 is None:
            return None
        size = int(round(BLOCK_KM / ctx.res)) | 1
        times = [3.0 * k + 2 for k in range(NQ)]
        times0 = [6 + 3.0 * k + 2 for k in range(NQ)]
        out = []
        za, zb = np.nan_to_num(now).astype(np.float32), np.nan_to_num(old).astype(np.float32)
        for (ax, ay, ao), (bx, by, bo) in zip(advect.displacements(motion, times), advect.displacements(m0, times0)):
            a = advect.warp(za, ax, ay, ao, 1, 0.0)
            b = advect.warp(zb, bx, by, bo, 1, 0.0)
            num = D._box(np.abs(a - b), size)
            den = D._box((a + b) / 2, size) + EPS * size * size
            u = (num / den).astype(np.float32)
            out.append(self.kb * gaussian_filter(u, size / 4))
        return out

    def forecast(self, t, ctx):
        fc = super().forecast(t, ctx)
        if fc is None:
            return None
        motion = ctx.motion(t)
        if motion is None:
            return fc
        sig = [None] * NQ
        for m in self.maatt:
            s = (self.sigma_a if m == "a" else self.sigma_b)(t, ctx, motion)
            if s is None:
                continue
            sig = [y if x is None else (x if y is None else np.maximum(x, y)) for x, y in zip(sig, s)]
        out = fc.copy()
        for k in range(self.fri, NQ):
            if sig[k] is None:
                continue
            g = blend_levels(fc[k], sig[k], ctx.res)
            out[k] = np.maximum(g, self.alfa * fc[k]) if self.alfa > 0 else g
        return out


def _make(name, **kw):
    c = type(name, (Utjamning,), kw)
    globals()[name] = c
    return c


# V: efter rättelsen av två fel (historikens längd i a, NaN utanför bilden i b); U_* i /data är ogiltiga
_make("V_a1", maatt="a", ka=1.0, alfa=0.8)
_make("V_a2", maatt="a", ka=2.0, alfa=0.8)
_make("V_b8", maatt="b", kb=8.0, alfa=0.8)
_make("V_b16", maatt="b", kb=16.0, alfa=0.8)
_make("V_ab", maatt="ab", ka=1.0, kb=8.0, alfa=0.8)
_make("V_a1_al6", maatt="a", ka=1.0, alfa=0.6)
_make("V_a1_f2", maatt="a", ka=1.0, alfa=0.8, fri=2)
_make("V_ab_f2_al95", maatt="ab", ka=1.0, kb=8.0, alfa=0.95, fri=2)
_make("U_noll", maatt="ab", ka=0.0, kb=0.0, alfa=0.8)
