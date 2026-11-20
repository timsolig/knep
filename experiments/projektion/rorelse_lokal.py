"""Ett rörelsefält som varierar över ytan (kön, spåret rorelse-lokal).

Taket för lokal förskjutning (kön 0010) är CSI 1 mm +0,045 till +0,101 vid 15 min till 2 h, lika stort
som tillväxttaket de första timmarna, medan en stel rörelse inte har något tak (0017). Kedjan gör sitt
täta fält ur Lucas-Kanades glesa vektorer med pysteps inverterade avståndsviktning över de 20 närmaste
med potensen 0,5 (`model.dense_motion`), vilket ger nästan samma rörelse överallt. Här prövas fält som
följer de lokala vektorerna mer (färre grannar, högre potens, tätare vektorer) och ett tätt fält ur
Farnebäck på historiken. Kedjan är annars som i drift (domare.KedjaOm); platskartans uppvärmning
använder driftens fält.

    uv run python experiments/projektion/domare.py kör --läge snabb --procs 2 --system rorelse_lokal:IDW_k8p1

  IDW_k8p1, IDW_k8p2, IDW_k20p2, IDW_k8p2_d10   samma glesa vektorer som kedjan, interpolerade med k
                                                 grannar, potensen p och declustring d px (kedjan: k20 p0,5 d20)
  Farneback32, Farneback64                       Farnebäck på historikens bilder (t − 30, t − 15, t), fönster
                                                 32 eller 64 km, med kedjans fält där det är torrt
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import domare as D  # noqa: E402

model = D.model


def idw(xy: np.ndarray, uv: np.ndarray, shape, k: int = 20, power: float = 0.5, decl: int = 20,
        step: int = 4) -> np.ndarray:
    """Som model.dense_motion men med k grannar, potensen och declustringen som val."""
    from pysteps.utils.cleansing import decluster
    from scipy.spatial import cKDTree

    h, w = shape
    if xy.shape[0] == 0:
        return np.zeros((2, h, w))
    xy, uv = decluster(xy, uv, decl, 1)
    if xy.shape[0] < 2:
        return np.zeros((2, h, w)) if xy.shape[0] == 0 else np.ones((2, h, w)) * uv[0][:, None, None]
    ys, xs = np.arange(0, h - 1 + step, step), np.arange(0, w - 1 + step, step)
    gx, gy = np.meshgrid(xs, ys)
    kk = min(k, xy.shape[0])
    dist, ind = cKDTree(xy).query(np.column_stack([gx.ravel(), gy.ravel()]), k=kk)
    if kk == 1:
        dist, ind = dist[:, None], ind[:, None]
    wts = 1 / np.power(dist + 0.5, power)
    wts /= wts.sum(axis=1, keepdims=True)
    coarse = np.einsum("pk,pkc->cp", wts, uv[ind]).reshape(2, len(ys), len(xs)).astype(np.float32)
    mx, my = np.meshgrid(np.arange(w, dtype=np.float32) / step, np.arange(h, dtype=np.float32) / step)
    return np.stack([cv2.remap(c, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
                     for c in coarse]).astype(np.float64)


def glesa(ctx, t):
    """Kedjans glesa vektorer vid t (samma som ctx.motion sparar), eller None."""
    if ctx.motion(t) is None:
        return None
    d = np.load(ctx.motion_dir / f"{t:%H%M}.npz")
    return d["xy"].astype(np.float64), d["uv"].astype(np.float64)


class _Rorelse(D.KedjaOm):
    def falt(self, t, ctx):
        raise NotImplementedError

    def forecast(self, t, ctx):
        obs = ctx.history(t)
        if obs is None:
            return None
        m = self.falt(t, ctx)
        if m is None:
            m = ctx.motion(t)
        return D.quarters(self.chain.run(obs, t, D.NQ * 3, self.state, motion=m).rain)


class _IDW(_Rorelse):
    k, power, decl = 20, 0.5, 20

    def falt(self, t, ctx):
        v = glesa(ctx, t)
        if v is None:
            return None
        c = self.chain
        return idw(*v, ctx.frame(t).shape, self.k, self.power, self.decl, c.motion_step) / c.motion_gap


class IDW_k8p1(_IDW):
    k, power = 8, 1.0


class IDW_k8p2(_IDW):
    k, power = 8, 2.0


class IDW_k20p2(_IDW):
    k, power = 20, 2.0


class IDW_k8p2_d10(_IDW):
    k, power, decl = 8, 2.0, 10


def db(x):
    return (10.0 * np.log10(np.nan_to_num(x, nan=0.0) + 0.1)).astype(np.float32)


def farneback(a: np.ndarray, b: np.ndarray, win_px: int) -> np.ndarray:
    """Flödet a -> b (2, H, W) i pixlar: regnet i a vid (y, x) ligger i b vid (y + v, x + u)."""
    f = cv2.calcOpticalFlowFarneback(db(a), db(b), None, 0.5, 3, max(3, win_px | 1), 3, 5, 1.1,
                                     cv2.OPTFLOW_FARNEBACK_GAUSSIAN)
    return np.stack([f[..., 0], f[..., 1]]).astype(np.float64)


class _Farneback(_Rorelse):
    win_km = 32.0

    def falt(self, t, ctx):
        q = D.Q
        a, b, c = ctx.frame(t - 2 * q), ctx.frame(t - q), ctx.frame(t)
        base = ctx.motion(t)
        if a is None or b is None or c is None or base is None:
            return None
        win = int(round(self.win_km / ctx.res))
        flow = (farneback(a, b, win) + farneback(b, c, win)) / 2 / 3.0   # pixlar per 15 min till per 5 min
        # där det är torrt säger Farnebäck inget: vikta mot kedjans fält efter andelen eko i fönstret
        eko = cv2.GaussianBlur((np.nan_to_num(c) > 0.1).astype(np.float32), (0, 0), win / 2)
        w = np.clip(eko / 0.2, 0.0, 1.0)[None]
        return w * flow + (1 - w) * base


class Farneback32(_Farneback):
    win_km = 32.0


class Farneback64(_Farneback):
    win_km = 64.0
