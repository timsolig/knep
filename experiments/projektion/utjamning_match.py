"""Utjämningen med kedjans fördelning tillbaka (uppgift 0021), på utjamning_snabb.Snabb.

Det utjämnade fältet g för en kvart mappas om efter rang till kedjans fält f för samma kvart (bara
ändliga rutor): g:s högsta rang får f:s högsta värde och så vidare. Läget och formen kommer från g
(utjämnat där osäkert), värdemängden från f. Billigt: bara de n = antal f > 0 högsta g-rutorna
sorteras (argpartition), resten blir 0 (f har lika många nollor).

  match_hel    hela fördelningen: sorterade värden lika med kedjans
  match_svans  bara g >= tröskel: de g-rutorna får f:s högsta värden, under tröskeln står g kvar
  match_block  som hel, per block om B pixlar (bara block med regn i f), och om `mjuk` medelvärde av två
               rutnät förskjutna ett halvt block (mjuk övergång)

Ingen vädermodell.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import utjamning_snabb as S  # noqa: E402


def _topp(f: np.ndarray, g: np.ndarray, n: int):
    """Index (platta) för g:s n högsta rutor, sorterade fallande, och f:s n högsta värden fallande."""
    n = min(n, g.size)
    if n <= 0:
        return None, None
    idx = np.argpartition(g, g.size - n)[g.size - n:] if n < g.size else np.arange(g.size)
    idx = idx[np.argsort(-g[idx], kind="stable")]
    vals = np.sort(f)[::-1][:n] if n >= f.size else np.partition(f, f.size - n)[f.size - n:]
    return idx, np.sort(vals)[::-1]


def match_hel(f: np.ndarray, g: np.ndarray) -> np.ndarray:
    ok = np.isfinite(f) & np.isfinite(g)
    fo, go = f[ok], g[ok]
    out = np.zeros_like(go)
    idx, vals = _topp(fo, go, int((fo > 0).sum()))
    if idx is not None:
        out[idx] = vals
    r = np.full(f.shape, np.nan, np.float32)
    r[ok] = out
    return r


def match_svans(f: np.ndarray, g: np.ndarray, tr: float | None = None, kvantil: float = 0.95) -> np.ndarray:
    """tr: tröskel i mm/h; utan den väljs den som g:s kvantil bland regnrutorna (g > 0,05)."""
    ok = np.isfinite(f) & np.isfinite(g)
    fo, go = f[ok], g[ok]
    if tr is None:
        w = go[go > 0.05]
        tr = float(np.quantile(w, kvantil)) if w.size else np.inf
    n = min(int((go >= tr).sum()), int((fo > 0).sum()))
    out = go.copy()
    if n > 0:
        idx, vals = _topp(fo, go, n)
        out[idx] = vals
    r = np.full(f.shape, np.nan, np.float32)
    r[ok] = out
    return r


def _block_pass(f, g, b, o):
    """match_hel per block (b pixlar) på rutnätet förskjutet o pixlar; ger (fält, antal) eller None utanför."""
    h, w = f.shape
    res = np.zeros(f.shape, np.float32)
    cnt = np.zeros(f.shape, np.float32)
    for y in range(o, h, b):
        for x in range(o, w, b):
            fb, gb = f[y:y + b, x:x + b], g[y:y + b, x:x + b]
            if not (fb > 0).any():
                continue
            m = match_hel(fb, gb)
            v = np.isfinite(m)
            res[y:y + b, x:x + b][v] = m[v]
            cnt[y:y + b, x:x + b][v] = 1
    return res, cnt


def match_block(f: np.ndarray, g: np.ndarray, b: int, mjuk: bool = True) -> np.ndarray:
    ok = np.isfinite(f) & np.isfinite(g)
    f0, g0 = np.where(ok, f, 0).astype(np.float32), np.where(ok, g, 0).astype(np.float32)
    r, c = _block_pass(f0, g0, b, 0)
    if mjuk:
        r2, c2 = _block_pass(f0, g0, b, b // 2)
        r, c = r + r2, c + c2
    out = np.where(c > 0, r / np.maximum(c, 1), g0)
    return np.where(ok, out, np.nan).astype(np.float32)


class Match(S.Snabb):
    """Utjämning (Snabb) och sedan matchning mot kedjans fält per kvart."""
    skydd = ""
    alfa = 0.0
    typ = "hel"          # hel, svans, block
    tr = None
    kv = 0.95
    blk_km = 64.0
    mjuk = True

    def one(self, f, sig, res, b):
        g = S.Snabb.one(self, f, sig, res, b)
        if g is f or np.array_equal(g, f, equal_nan=True):
            return f
        if self.typ == "hel":
            m = match_hel(f, g)
        elif self.typ == "svans":
            m = match_svans(f, g, self.tr, self.kv)
        else:
            m = match_block(f, g, max(4, int(round(self.blk_km / res))), self.mjuk)
        if self.alfa > 0:
            m = np.maximum(m, self.alfa * f)
        return m.astype(np.float32)


def _make(name, **kw):
    c = type(name, (Match,), kw)
    globals()[name] = c
    return c


_make("M_hel", typ="hel", maatt="ab", fri=2)
_make("M_hel_gol", typ="hel", maatt="ab", fri=2, alfa=0.95)
_make("M_svans2", typ="svans", tr=2.0, maatt="ab", fri=2)
_make("M_svans1", typ="svans", tr=1.0, maatt="ab", fri=2)
_make("M_svansq", typ="svans", tr=None, kv=0.95, maatt="ab", fri=2)
_make("M_blk64", typ="block", blk_km=64.0, maatt="ab", fri=2)
_make("M_blk128", typ="block", blk_km=128.0, maatt="ab", fri=2)
