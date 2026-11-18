"""Snabb utjämning med toppskydd (uppgift 0020), på utjamning.py från 0019.

Samma idé som 0019 (kedjans fält per kvart blandat mellan gaussfilter efter ett osäkerhetsmått utan
facit, måtten a och b, ingen utjämning de första `fri` kvartarna), men:

  snabbhet  filtren går med cv2.GaussianBlur och körs på ett grövre rutnät (omkring 2 pixlar per sigma
            efter nedsampling med INTER_AREA och uppsampling med INTER_LINEAR), nivåerna väljs med
            hattvikter (en vikt per nivå, summan 1) i stället för en where per nivå, och måtten räknas
            på 4 km. Normaliseringen mot NaN är densamma som i tak.smooth.
  toppskydd (`skydd`) i stället för golvet max(utjämnat, alfa · original), som sänkte blockmax_q90
            med ungefär log(1/alfa):
    a  skala upp det utjämnade fältet block för block (BLK_KM) så att blockets max blir kedjans
       (faktorn högst MAXFAKTOR)
    b  rutor som är största värdet i fönstret BLK_KM (och över noll) behåller kedjans värde
    c  bara massan under blockets kvantil Q utjämnas; överskottet ovanför läggs tillbaka oförändrat

Med sigma = 0 överallt blir resultatet exakt kedjans (test_utjamning_snabb.py). Ingen vädermodell.

    uv run python experiments/projektion/profil_utjamning.py S_ab_a 2 2020-08-29 12
"""

from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import domare as D  # noqa: E402
import utjamning as U  # noqa: E402

advect, model = D.advect, D.model
NQ = D.NQ
LEVELS = U.LEVELS
BLK_KM = 16.0
MAXFAKTOR = 4.0
Q = 0.9
GRID_KM = 4.0          # måtten b och a räknas på ett rutnät om minst så här många km
cv2.setNumThreads(1)


# ---------- grova rutnät ----------

def _down(x: np.ndarray, d: int) -> np.ndarray:
    if d == 1:
        return x
    h, w = x.shape
    return cv2.resize(x, (-(-w // d), -(-h // d)), interpolation=cv2.INTER_AREA)


def _up(x: np.ndarray, d: int, shape) -> np.ndarray:
    if d == 1:
        return x
    return cv2.resize(x, (shape[1], shape[0]), interpolation=cv2.INTER_LINEAR)


def gauss(x: np.ndarray, sigma_px: float) -> np.ndarray:
    """Gaussfilter (utan NaN i x) med sigma i pixlar, på ett grövre rutnät när sigma är stort."""
    if sigma_px <= 0:
        return x
    d = max(1, int(sigma_px // 2))
    xc = _down(x, d)
    g = cv2.GaussianBlur(xc, (0, 0), sigma_px / d, borderType=cv2.BORDER_REFLECT)
    return _up(g, d, x.shape)


_DEN: dict = {}   # nämnaren (filtrerad mask) per sigma; masken är densamma för alla kvartar i en utgåva


def smooth_nan(f: np.ndarray, ok: np.ndarray, sigma_px: float) -> np.ndarray:
    """Normaliserat filter som ignorerar NaN (som tak.smooth), snabbt. ok: ändlig mask."""
    d = max(1, int(sigma_px // 2))
    num = cv2.GaussianBlur(_down(f, d), (0, 0), sigma_px / d, borderType=cv2.BORDER_REFLECT)
    hit = _DEN.get(sigma_px)
    if hit is None or not np.array_equal(hit[0], ok):
        den = cv2.GaussianBlur(_down(ok.astype(np.float32), d), (0, 0), sigma_px / d, borderType=cv2.BORDER_REFLECT)
        _DEN[sigma_px] = hit = (ok.copy(), np.maximum(_up(den, d, f.shape), 1e-6))
    return _up(num, d, f.shape) / hit[1]


def blend_fast(fc: np.ndarray, sigma_km: np.ndarray, res: float, base: np.ndarray | None = None) -> np.ndarray:
    """fc utjämnad med sigma (km) per ruta, linjärt mellan LEVELS (hattvikter); NaN som i tak.smooth.

    base: fältet som utjämnas (skydd c); utdata är utjämnad(base) i stället för utjämnad(fc)."""
    s = np.clip(np.nan_to_num(sigma_km), 0, LEVELS[-1]).astype(np.float32)
    src = fc if base is None else base
    ok = np.isfinite(fc)
    z = np.where(ok, src, 0.0).astype(np.float32)
    out = np.zeros(fc.shape, np.float32)
    L = LEVELS
    for i, lv in enumerate(L):
        w = np.ones_like(s)
        if i > 0:
            w = np.minimum(w, (s - L[i - 1]) / (lv - L[i - 1]))
        if i < len(L) - 1:
            w = np.minimum(w, (L[i + 1] - s) / (L[i + 1] - lv))
        np.clip(w, 0, 1, out=w)
        if not w.any():
            continue
        lvl = z if lv == 0 else smooth_nan(z, ok, lv / res)
        out += w * lvl
    return np.where(ok, out, np.nan).astype(np.float32)


# ---------- block och fönster ----------

def _pad(x: np.ndarray, b: int, fill=0.0) -> np.ndarray:
    h, w = x.shape
    ph, pw = -h % b, -w % b
    return np.pad(x, ((0, ph), (0, pw)), mode="constant", constant_values=fill) if ph or pw else x


def block_stat(x: np.ndarray, b: int, fn) -> np.ndarray:
    xp = _pad(x, b)
    h, w = xp.shape
    return fn(xp.reshape(h // b, b, w // b, b), axis=(1, 3))


def block_expand(v: np.ndarray, b: int, shape) -> np.ndarray:
    return np.repeat(np.repeat(v, b, 0), b, 1)[: shape[0], : shape[1]]


def skydd_a(fc: np.ndarray, g: np.ndarray, b: int) -> np.ndarray:
    z0, z1 = np.nan_to_num(fc), np.nan_to_num(g)
    m0, m1 = block_stat(z0, b, np.max), block_stat(z1, b, np.max)
    f = np.clip(m0 / np.maximum(m1, 1e-6), 1.0, MAXFAKTOR)
    f = np.where(m0 > 0, f, 1.0).astype(np.float32)
    return g * block_expand(f, b, g.shape)


def skydd_b(fc: np.ndarray, g: np.ndarray, b: int) -> np.ndarray:
    z0 = np.nan_to_num(fc).astype(np.float32)
    mx = cv2.dilate(z0, np.ones((b, b), np.uint8), borderType=cv2.BORDER_CONSTANT, borderValue=0)
    top = (z0 >= mx) & (z0 > 0)
    return np.where(top, fc, g)


def cap_c(fc: np.ndarray, b: int) -> np.ndarray:
    z0 = np.nan_to_num(fc)
    xp = _pad(z0, b)
    h, w = xp.shape
    blocks = xp.reshape(h // b, b, w // b, b).transpose(0, 2, 1, 3).reshape(h // b, w // b, b * b)
    q = np.quantile(blocks, Q, axis=2).astype(np.float32)
    return block_expand(q, b, fc.shape)


# ---------- systemet ----------

class Snabb(U.Utjamning):
    skydd = "b"          # "a", "b", "c" eller "" (inget; alfa gäller då)
    alfa = 0.0

    def _d(self, res):
        return max(1, int(round(GRID_KM / res)))

    def sigma_a(self, t, ctx, motion):
        obs = ctx.history(t)
        if obs is None:
            return None
        xy, uv = model._quiet(model.dense_lucaskanade, model._db(obs[-3:]), dense=False)
        v2 = model.dense_motion(np.asarray(xy, np.float64), np.asarray(uv, np.float64), obs[-1].shape,
                                self.chain.motion_step)
        dv = (np.hypot(motion[0] - v2[0], motion[1] - v2[1]) * ctx.res).astype(np.float32)
        dv = gauss(dv, U.SMOOTH_KM / ctx.res)
        return [self.ka * dv * s for s in 3.0 * (np.arange(NQ) + 0.5)]

    def sigma_b(self, t, ctx, motion):
        t0 = t - timedelta(minutes=30)
        old, now, m0 = ctx.frame(t0), ctx.frame(t), ctx.motion(t0)
        if old is None or m0 is None:
            return None
        d = self._d(ctx.res)
        res = ctx.res * d
        size = int(round(U.BLOCK_KM / res)) | 1
        za = _down(np.nan_to_num(now).astype(np.float32), d)
        zb = _down(np.nan_to_num(old).astype(np.float32), d)
        mo, mo0 = (np.stack([_down(np.ascontiguousarray(c), d) for c in m]) / d for m in (motion, m0))
        full = now.shape
        out = []
        times = [3.0 * k + 2 for k in range(NQ)]
        times0 = [6 + 3.0 * k + 2 for k in range(NQ)]
        for (ax, ay, ao), (bx, by, bo) in zip(advect.displacements(mo, times), advect.displacements(mo0, times0)):
            a = advect.warp(za, ax, ay, ao, 1, 0.0)
            b = advect.warp(zb, bx, by, bo, 1, 0.0)
            num = D._box(np.abs(a - b), size)
            den = D._box((a + b) / 2, size) + U.EPS * size * size
            u = cv2.GaussianBlur((num / den).astype(np.float32), (0, 0), size / 4, borderType=cv2.BORDER_REFLECT)
            out.append(_up(self.kb * u, d, full))
        return out

    def forecast(self, t, ctx):
        fc = D.KedjaOm.forecast(self, t, ctx)
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
        b = max(2, int(round(BLK_KM / ctx.res)))
        for k in range(self.fri, NQ):
            if sig[k] is None:
                continue
            out[k] = self.one(fc[k], sig[k], ctx.res, b)
        return out

    def one(self, f, sig, res, b):
        if float(np.nan_to_num(sig).max()) <= 0.05:
            return f
        if self.skydd == "c":
            cap = cap_c(f, b)
            low = np.minimum(np.nan_to_num(f), cap)
            g = blend_fast(f, sig, res, base=low) + (np.nan_to_num(f) - low)
            return np.where(np.isfinite(f), g, np.nan).astype(np.float32)
        g = blend_fast(f, sig, res)
        if self.skydd == "a":
            g = skydd_a(f, g, b)
        elif self.skydd == "b":
            g = skydd_b(f, g, b)
        elif self.alfa > 0:
            g = np.maximum(g, self.alfa * f)
        return np.where(np.isfinite(f), g, np.nan).astype(np.float32)


def _make(name, **kw):
    c = type(name, (Snabb,), kw)
    globals()[name] = c
    return c


_make("S_ab_gol", maatt="ab", skydd="", alfa=0.95, fri=2)     # 0019:s fryst variant, snabb
_make("S_ab_a", maatt="ab", skydd="a", fri=2)
_make("S_ab_b", maatt="ab", skydd="b", fri=2)
_make("S_ab_c", maatt="ab", skydd="c", fri=2)
_make("S_noll", maatt="ab", ka=0.0, kb=0.0, skydd="a")
