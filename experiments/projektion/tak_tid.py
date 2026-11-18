"""Tak för rörelse som ändras med ledtiden (uppgift 0022). Fuskvarianter som får se facit.

    uv run python experiments/projektion/kor_shm.py kör snabb tak_tid:TakRorelse1h tak_tid:TakRorelseTid --dagar <dag>

  TakRorelse1h    kedjan med ett fält skattat ur facit-bilderna t till t + 1 h (samma Lucas-Kanade som
                  tak.hindsight_motion men begränsad till 1 h). Kontroll: skiljer skattningens kvalitet och
                  fönstrets längd från att rörelsen ändras?
  TakRorelseTid   styckvis konstant rörelse per timme av ledtiden: fältet för timme h skattat ur facit-bilderna
                  t + (h-1) h till t + h h.

Hur TakRorelseTid är byggd: Chain.run tar bara ett fält, så kedjan körs som i drift (historikens rörelse, platskarta,
matchning) och varje kvarts prognos flyttas sedan med skillnaden mellan två förskjutningar bakåt längs vägen
(semi-lagrangesk): den längs kedjans fält och den längs de styckvisa facitfälten. Båda vägarna räknas med samma
integrator (`back_path`, 5-minutssteg, mittpunktsschema, bakåt från ankomsttiden och med fältet för den timme
varje steg ligger i), så med samma fält i alla timmar blir skillnaden exakt noll och prognosen kedjans.
Prognosen för kvarten hämtas i punkten x + (dx_facit - dx_kedja), där dx är förskjutningen bakåt (negativ i
rörelseriktningen). Kvartens tre 5-minutersbilder flyttas med skillnaden vid kvartens mittsteg.
Platskartan och matchningen sitter alltså kvar på kedjans plats och flyttas med, och rutor utan analys förblir NaN.
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import domare as D  # noqa: E402
import tak  # noqa: E402

model, NQ, STEP = D.model, D.NQ, D.STEP
HOUR = 12  # 5-minutersteg per timme


def motion_window(ctx, t, h0: int, h1: int):
    """Rörelsefältet (2, H, W) i pixlar per 5 min ur radarbilderna t + h0 h ... t + h1 h (var 15:e minut),
    eller None om färre än 4 bilder i följd finns."""
    c = ctx.chain
    frames = []
    for k in range(h0 * HOUR, h1 * HOUR + 1, c.motion_gap):
        f = ctx.frame(t + k * STEP)
        if f is None:
            break
        frames.append(f)
    if len(frames) < 4:
        return None
    xy, uv = model._quiet(model.dense_lucaskanade, model._db(np.stack(frames)), dense=False)
    return model.dense_motion(np.asarray(xy, np.float64), np.asarray(uv, np.float64), frames[0].shape,
                              c.motion_step) / c.motion_gap


def back_path(fields, k: int, grid):
    """Förskjutningen (dx, dy) bakåt i pixlar för ankomst efter k steg om 5 min. fields[i] är fältet (2, H, W)
    för steg i (0-räknat), alltså det som gäller under steg i + 1. Vägen går bakåt från steg k: steg k, k-1, ... 1."""
    gx, gy = grid
    h, w = gx.shape
    dx = np.zeros_like(gx)
    dy = np.zeros_like(gy)

    def at(v, px, py):
        mx, my = gx + px, gy + py
        return (cv2.remap(v[0], mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE),
                cv2.remap(v[1], mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE))

    for i in range(k - 1, -1, -1):
        v = np.asarray(fields[i], np.float32)
        ux, uy = at(v, dx, dy)  # hastigheten i nuvarande punkt, för mittpunkten
        mx_, my_ = at(v, dx - ux / 2, dy - uy / 2)
        dx, dy = dx - mx_, dy - my_
    return dx, dy


def shift_forecast(rain, chain_fields, true_fields, quarter_ends=None):
    """rain (3*NQ, H, W) från kedjan; flyttar varje kvarts tre bilder med skillnaden i förskjutning mellan
    de styckvisa facitfälten och kedjans fält (båda listor med ett (2, H, W) per 5-minutssteg)."""
    n, h, w = rain.shape
    gx, gy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    out = rain.copy()
    for q in range(n // 3):
        k = 3 * q + 2  # mittsteget (andra bilden) i kvarten, räknat i steg
        ax, ay = back_path(true_fields, k, (gx, gy))
        bx, by = back_path(chain_fields, k, (gx, gy))
        mx, my = gx + (ax - bx), gy + (ay - by)
        for j in range(3 * q, 3 * q + 3):
            f = rain[j]
            ok = np.isfinite(f)
            z = cv2.remap(np.where(ok, f, 0.0).astype(np.float32), mx, my, cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=0.0)
            out[j] = np.where(ok, z, np.nan)
    return out


class TakRorelse1h(tak._Tak):
    """Ett fält ur facit t till t + 1 h för hela prognosen."""

    def forecast(self, t, ctx):
        obs = ctx.history(t)
        if obs is None:
            return None
        motion = motion_window(ctx, t, 0, 1)
        if motion is None:
            motion = ctx.motion(t)
        return D.quarters(self.chain.run(obs, t, NQ * 3, self.state, motion=motion).rain)


class TakRorelseTid(tak._Tak):
    """Styckvis konstant rörelse per timme ur facit, via förskjutningen på kedjans prognos (se modulens docstring)."""

    def forecast(self, t, ctx):
        obs = ctx.history(t)
        if obs is None:
            return None
        base = ctx.motion(t)
        rain = self.chain.run(obs, t, NQ * 3, self.state, motion=base).rain
        per_hour = []
        for h in range(5):
            m = motion_window(ctx, t, h, h + 1)
            per_hour.append(base if m is None else m)
        true_fields = [per_hour[i // HOUR] for i in range(NQ * 3)]
        chain_fields = [base] * (NQ * 3)
        return D.quarters(shift_forecast(rain, chain_fields, true_fields))
