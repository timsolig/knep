"""Prognosmodellen.

`nowcast` är referensen: Lucas-Kanade och semi-Lagrangesk extrapolering, ingen träning.

`Chain` är modellen som slog KNEP-proxyn i experiments/, plus tränade sannolikheter för extremer:

  1. Rörelse: Lucas-Kanade på bilderna för 30, 15 och 0 min sedan. Med 15 minuter mellan bilderna
     är förflyttningen stor mot bruset och tillväxten; bild för bild gav fältet för låg fart och
     sämre FSS för kraftig nederbörd.
  2. Extrapolering i 5-minuterssteg.
  3. Varje prognosbild matchas mot analysens intensitetsfördelning, så att interpolationen
     inte smetar ut topparna. Målet är analysen flyttad med närmaste granne: samma värden, men
     det som har lämnat området följer inte med, så volymen och avtagandet blir rätt vid randen.
  4. Platskarta: tillväxt och avtagande per pixel ur senaste timmens fel vid 30 min ledtid,
     inlagd gradvis över första halvtimmen. Fångar lovart, lä och strålblockering.
  5. Extremer (om en tränad modell finns): sannolikhet för minst 5 och 10 mm/h per pixel.
     Fältet i steg 3 och 4 lämnas orört; omskalning av topparna förlorade i verifieringen.

Platskartan behöver minnas senaste timmens prognoser; det tillståndet sparas mellan körningarna.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from pysteps.extrapolation.semilagrangian import extrapolate
from pysteps.motion.lucaskanade import dense_lucaskanade
from pysteps.utils.transformation import dB_transform
from scipy.ndimage import gaussian_filter

from . import extremes

STEP = timedelta(minutes=5)


def _db(frames):
    out, _ = dB_transform(np.nan_to_num(frames, nan=0.0), threshold=0.1, zerovalue=-15.0)
    return out


def _quiet(fn, *a, **k):
    import contextlib
    import io

    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **k)


def nowcast(obs: np.ndarray, steps: int) -> np.ndarray:
    """Referensen. obs: (T, H, W) i mm/h med 5 min mellan bilderna, äldst först, NaN utanför täckning.

    Returnerar (steps, H, W) i mm/h, ett fält per 5 min. NaN där det saknas underlag.
    """
    filled = np.nan_to_num(obs, nan=0.0)
    velocity = _quiet(dense_lucaskanade, _db(obs))
    forecast = extrapolate(filled[-1], velocity, steps)
    forecast[:, np.isnan(obs[-1])] = np.nan
    return forecast


def cdf_match(f, target):
    """Ger f målfältets värdefördelning men behåller f:s rangordning (nollor ordnas efter grannskapet)."""
    ok = np.isfinite(f)
    tv = np.sort(target[np.isfinite(target)])
    n = int(ok.sum())
    if n == 0 or tv.size == 0:
        return f
    key = f[ok] + 1e-3 * gaussian_filter(np.nan_to_num(f), 2.0)[ok]
    order = np.argsort(key, kind="stable")
    q = (np.arange(n) + 0.5) / n
    vals = np.empty(n, np.float32)
    vals[order] = tv[np.minimum((q * tv.size).astype(int), tv.size - 1)]
    out = np.full(f.shape, np.nan, np.float32)
    out[ok] = vals
    return out


@dataclass
class State:
    """Senaste timmens analyser och 30-minutersprognoser, nycklade på giltighetstid."""

    obs: dict = field(default_factory=dict)
    fc30: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "State":
        if not path.exists():
            return cls()
        d = np.load(path)
        s = cls()
        for k in d.files:
            kind, t = k.split("_", 1)
            getattr(s, kind)[t] = d[k].astype(np.float32)
        return s

    def save(self, path: Path) -> None:
        arrays = {f"obs_{t}": a.astype(np.float16) for t, a in self.obs.items()}
        arrays |= {f"fc30_{t}": a.astype(np.float16) for t, a in self.fc30.items()}
        tmp = path.with_suffix(".tmp.npz")
        np.savez_compressed(tmp, **arrays)
        tmp.replace(path)

    def prune(self, now: datetime, keep=timedelta(minutes=70)) -> None:
        for d in (self.obs, self.fc30):
            for t in [t for t in d if datetime.fromisoformat(t) < now - keep]:
                del d[t]


def location_map(state: State, now: datetime, shape, sigma=5.0, shrink=0.5, clip=6.0, window=12):
    """dB-korrektion per pixel ur senaste timmens par av analys och 30-minutersprognos."""
    num, den = np.zeros(shape), np.zeros(shape)
    for k in range(window):
        t = (now - k * STEP).isoformat()
        if t in state.obs and t in state.fc30:
            o, f = state.obs[t], state.fc30[t]
            ok = np.isfinite(f) & np.isfinite(o) & (f >= 0.5) & (o >= 0.5)
            num += np.where(ok, 10 * np.log10(np.where(ok, o, 1.0) / np.where(ok, f, 1.0)), 0.0)
            den += ok
    if not den.any():
        return np.zeros(shape, np.float32)
    g = gaussian_filter(num, sigma) / (gaussian_filter(den, sigma) + shrink)
    return np.clip(g, -clip, clip).astype(np.float32)


@dataclass
class Result:
    rain: np.ndarray  # (steps, H, W) mm/h
    prob: np.ndarray | None  # (len(extremes.THR), steps, H, W) eller None
    motion: np.ndarray  # (2, H, W) pixlar per 5 min


def motion_field(obs: np.ndarray, gap: int = 1, n: int = 7) -> np.ndarray:
    """Lucas-Kanade på n bilder med gap 5-minuterssteg emellan, i pixlar per 5 min.

    Med gap 1 och n 7 är det 30 min historik bild för bild. Glesare bilder ger större förflyttning
    mellan bilderna i förhållande till bruset och tillväxten.
    """
    idx = [max(0, len(obs) - 1 - gap * m) for m in range(n - 1, -1, -1)]
    return _quiet(dense_lucaskanade, _db(obs[idx])) / gap


class Chain:
    def __init__(self, ext_model: Path | None = None, prob_steps: int | None = None, motion_gap: int = 3,
                 motion_frames: int = 3, target: str = "advected"):
        self.models = extremes.load(ext_model) if ext_model and Path(ext_model).exists() else None  # dict med models och recal
        self.prob_steps = prob_steps  # räkna sannolikheterna bara för de första stegen (spar tid)
        self.motion_gap, self.motion_frames = motion_gap, motion_frames
        self.target = target  # "analysis" eller "advected": fördelningen följer med fältet ut ur området

    def run(self, obs: np.ndarray, now: datetime, steps: int, state: State | None = None) -> Result:
        """obs: (T, H, W) mm/h, 5 min mellan bilderna, äldst först, senaste = analysen vid now."""
        state = state if state is not None else State()
        motion = motion_field(obs, self.motion_gap, self.motion_frames)
        analysis = obs[-1]
        raw = extrapolate(np.nan_to_num(analysis), motion, steps)
        raw[:, ~np.isfinite(analysis)] = np.nan  # utanför täckningen deltar inte i matchningen
        if self.target == "advected":
            # analysens värden flyttade med närmaste granne: samma värden, men bara de som är kvar i området
            tgt = extrapolate(np.nan_to_num(analysis), motion, steps, interp_order=0)
            tgt[:, ~np.isfinite(analysis)] = np.nan
        else:
            tgt = [analysis] * steps
        corr = location_map(state, now, analysis.shape)
        rain = np.empty(raw.shape, np.float32)
        matched30 = None
        for k in range(steps):
            m = cdf_match(raw[k], tgt[k])
            if k == 5:
                matched30 = m
            rain[k] = m * 10 ** (corr * min(1.0, (k + 1) / 6) / 10)
        rain[:, ~np.isfinite(analysis)] = np.nan
        # tillståndet: analysen nu och den matchade 30-minutersprognosen (före platskartan, som i experimenten)
        state.obs[now.isoformat()] = analysis.astype(np.float32)
        if matched30 is not None:
            state.fc30[(now + 6 * STEP).isoformat()] = matched30
        state.prune(now)
        prob = None
        if self.models is not None:
            n = min(steps, self.prob_steps or steps)
            adv = lambda f, s: extrapolate(np.nan_to_num(f), motion, s)
            past15 = obs[-4] if len(obs) >= 4 else None
            past30 = obs[-7] if len(obs) >= 7 else None
            t15, t30, speed, dom = extremes.tendencies(analysis, past15, past30, motion, steps, adv)
            prob = np.zeros((len(extremes.THR), steps) + analysis.shape, np.float32)
            for k in range(1, n + 1):
                rain[k - 1], prob[:, k - 1] = extremes.apply(self.models, rain[k - 1], k, t15, t30, corr, speed, dom)
        return Result(rain, prob, motion)
