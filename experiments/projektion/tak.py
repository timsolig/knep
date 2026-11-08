"""Tak för kedjans delar: fuskvarianter av kedjan som får se facit, för domaren (uppgift 0016).

SKRIVEN UTAN ATT HA KÖRTS. Ingen rad här är provkörd, inte ens importerad. Räkna med småfel vid
första körningen (se rapporten 0016, avsnittet "Det jag är osäker på").

Varje variant är kedjan körd som i drift (domare.KedjaOm, med platskartans tillstånd uppvärmt) där en
del får facit i efterhand: radarns kvartsmedel för kvartarna som slutar 15 min till 5 h efter
utgåvetiden, det som domaren mäter mot. Resultatet är ett tak: hur bra kedjan hade blivit om just
den delen vore perfekt. Det är inget system som kan köras i drift och bedöms aldrig som "bättre".

    cd experiments/projektion
    python domare.py kör --läge snabb --system tak:TakMangd --dagar 2020-02-10 --procs 1   # prov
    python domare.py kör --läge snabb --system tak:TakRorelse tak:TakMangd tak:TakTillvaxt \\
        tak:TakUtjamningFast tak:TakUtjamningBast
    python domare.py tabell --läge snabb --system tak:TakMangd ...      # mot kedja_om

Systemnamnet blir klassen: tak:TakRorelse sparas som /data/projektion/domare/snabb/tak_TakRorelse/.

  TakRorelse          rörelsefältet skattat ur facit (radarbilderna från utgåvan till 5 h) i stället för historiken
  TakMangd            fältet skalat per ledtid så att volymen över domänen stämmer med facit
  TakTillvaxt         fältet gånger kvoten facit/kedja i block om ca 32 km (utjämnad, kvoten högst 4 och minst 1/4)
  TakUtjamningFast    gaussisk utjämning med fast schema, sigma 0, 2, 4, 8, 12 km vid +1 till +5 h
  TakUtjamningBast    gaussisk utjämning med bästa sigma per utgåva och ledtid, vald mot facit (FSS 1 mm/h, 10 km)

Inget körs vid import utöver definitioner. Filen heter inte test_*.py och samlas inte av pytest.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import domare as D  # noqa: E402

model = D.model  # kedjans modul, importerad av domaren
NQ, Q, STEP = D.NQ, D.Q, D.STEP


# ---------- gemensamma hjälpmedel ----------

def facit(t, ctx) -> np.ndarray:
    """(20, H, W) radarns kvartsmedel för kvartarna som slutar t + 15 min ... t + 5 h, samma som domaren mäter
    mot (ctx.quarter). NaN där kvarten saknas."""
    out = np.full((NQ,) + ctx.frame(t).shape, np.nan, np.float32)
    for k in range(1, NQ + 1):
        o = ctx.quarter(t + k * Q)
        if o is not None:
            out[k - 1] = o
    return out


def smooth(f: np.ndarray, sigma_px: float) -> np.ndarray:
    """Gaussisk utjämning som ignorerar NaN (normaliserad faltning); NaN stannar NaN."""
    if sigma_px <= 0:
        return f
    ok = np.isfinite(f)
    g = gaussian_filter(np.where(ok, f, 0.0).astype(np.float32), sigma_px)
    w = gaussian_filter(ok.astype(np.float32), sigma_px)
    return np.where(ok, g / np.maximum(w, 1e-6), np.nan).astype(np.float32)


class _Tak(D.KedjaOm):
    """Kedjan körd som i drift; cheat(fc, o, res) ändrar prognosen (20, H, W) med facit o (20, H, W)."""

    def forecast(self, t, ctx):
        fc = super().forecast(t, ctx)
        if fc is None:
            return None
        return self.cheat(fc, facit(t, ctx), ctx.res, ctx, t)

    def cheat(self, fc, o, res, ctx, t):
        raise NotImplementedError


# ---------- 1. rörelsen ----------

def hindsight_motion(ctx, t) -> np.ndarray | None:
    """Rörelsefältet (2, H, W) i pixlar per 5 min ur radarbilderna från t framåt (var 15:e minut, som kedjans
    historik men åt andra hållet), tills en bild saknas eller 5 h är nådda. Samma Lucas-Kanade och samma
    tätning som Ctx.motion. None om färre än 4 bilder i följd finns."""
    c = ctx.chain
    frames = []
    for k in range(0, NQ * 3 + 1, c.motion_gap):
        f = ctx.frame(t + k * STEP)
        if f is None:
            break
        frames.append(f)
    if len(frames) < 4:
        return None
    xy, uv = model._quiet(model.dense_lucaskanade, model._db(np.stack(frames)), dense=False)
    return model.dense_motion(np.asarray(xy, np.float64), np.asarray(uv, np.float64), frames[0].shape,
                              c.motion_step) / c.motion_gap


class TakRorelse(_Tak):
    """Rörelsen ur facit. Platskartans uppvärmning (observe) använder fortfarande historikens rörelse."""

    def forecast(self, t, ctx):
        obs = ctx.history(t)
        if obs is None:
            return None
        motion = hindsight_motion(ctx, t)
        if motion is None:
            motion = ctx.motion(t)
        return D.quarters(self.chain.run(obs, t, NQ * 3, self.state, motion=motion).rain)


# ---------- 2. mängden ----------

class TakMangd(_Tak):
    """Varje ledtids fält gånger summa(facit) / summa(prognos) över rutorna där båda finns."""

    def cheat(self, fc, o, res, ctx, t):
        out = fc.copy()
        for k in range(NQ):
            m = np.isfinite(fc[k]) & np.isfinite(o[k])
            sf = float(fc[k][m].sum())
            if m.any() and sf > 0:
                out[k] = fc[k] * (float(o[k][m].sum()) / sf)
        return out


# ---------- 3. tillväxt och avtagande i stor skala ----------

def block_ratio(f, o, res, block_km=32.0, cap=4.0, eps=0.02) -> np.ndarray:
    """Kvoten facit/prognos av medelvärdena i glidande block om block_km (box), med eps mm/h i båda leden,
    klippt till [1/cap, cap] och utjämnad med sigma = blocket / 4. 1 där blocket saknar rutor med båda."""
    size = int(round(block_km / res)) | 1
    m = np.isfinite(f) & np.isfinite(o)
    n = D._box(m.astype(np.float32), size)
    mf = D._box(np.where(m, f, 0.0).astype(np.float32), size) / np.maximum(n, 1)
    mo = D._box(np.where(m, o, 0.0).astype(np.float32), size) / np.maximum(n, 1)
    r = np.clip((mo + eps) / (mf + eps), 1 / cap, cap)
    r = gaussian_filter(r.astype(np.float32), size / 4)
    return np.where(n > 0, r, 1.0).astype(np.float32)


class TakTillvaxt(_Tak):
    """Perfekt tillväxt och avtagande i skalan 32 km: regn som kedjan inte har någonstans (prognos 0) kan inte
    växa fram, bara det som finns förstärks eller dämpas."""

    def cheat(self, fc, o, res, ctx, t):
        out = fc.copy()
        for k in range(NQ):
            if np.isfinite(o[k]).any():
                out[k] = fc[k] * block_ratio(fc[k], o[k], res)
        return out


# ---------- 4. utjämningen ----------

SIGMA_FAST_KM = ([0.0, 1.0, 2.0, 3.0, 4.0, 5.0], [0.0, 0.0, 2.0, 4.0, 8.0, 12.0])  # (timmar, sigma i km)
SIGMA_LIST_KM = [0.0, 2.0, 4.0, 8.0, 12.0, 16.0, 24.0]
CRIT_THR, CRIT_KM = 1.0, 10.0  # kriteriet för TakUtjamningBast: FSS för 1 mm/h i fönster om 10 km


class TakUtjamningFast(_Tak):
    """En enkel S-PROG: kedjans fält utjämnat med ett sigma som växer med ledtiden (linjärt mellan punkterna)."""

    def cheat(self, fc, o, res, ctx, t):
        sig = np.interp(np.arange(1, NQ + 1) / 4, *SIGMA_FAST_KM)  # km vid kvartens slut
        return np.stack([smooth(fc[k], sig[k] / res) for k in range(NQ)])


class TakUtjamningBast(_Tak):
    """Som TakUtjamningFast men sigma väljs per utgåva och ledtid ur SIGMA_LIST_KM så att FSS (CRIT_THR mm/h,
    CRIT_KM km) mot facit blir högst. Valet per utgåva utnyttjar bruset i facit, så det här är ett övre tak för
    utjämningen, inte något som går att lära in. Valda sigman skrivs ut per utgåva."""

    def cheat(self, fc, o, res, ctx, t):
        size = int(round(CRIT_KM / res)) | 1
        out, chosen = fc.copy(), []
        for k in range(NQ):
            m = np.isfinite(fc[k]) & np.isfinite(o[k])
            if not m.any():
                chosen.append(np.nan)
                continue
            ow = np.where(m, o[k], 0.0).astype(np.float32)
            best, best_s = -np.inf, 0.0
            for s in SIGMA_LIST_KM:
                g = smooth(fc[k], s / res)
                num, den = D.fss_sums(np.where(m, np.nan_to_num(g), 0.0).astype(np.float32), ow, m, CRIT_THR, size)
                score = 1 - num / max(den, 1e-9)
                if score > best:
                    best, best_s, out[k] = score, s, g
            chosen.append(best_s)
        print(f"{ctx.day} {t:%H%M} sigma km per kvart: {chosen}", flush=True)
        return out
