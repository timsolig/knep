"""Mått på nederbördsfältens form, för formsviten (form5h.py).

Alla mått jämför en prognos f med radarn o på samma pixlar (masken m) och ger ett värde där 0
är rätt: logaritmen av en kvot eller en skillnad. Det gör att de kan medlas över körningarna och
dagarna och att tecknet säger åt vilket håll prognosen avviker.

  spektrum    effektspektrum för dBR i rutor på 256 km helt inom täckningen, per våglängdsband.
              Utjämning syns som för lite effekt på små skalor (negativt)
  SAL         struktur, amplitud och läge enligt Wernli m.fl. (2008). S > 0: för stora eller platta
              objekt (utsmetat); S < 0: för små eller spetsiga. A: volymen. L: läget, 0 till 2
  objekt      antalet regnområden över 1 och 5 mm/h och deras typiska storlek (ytviktat medel)
  kanter      medelbranthet i dBR (Sobel), där det regnar i prognosen eller radarn
  fördelning  kvantilerna 95, 99 och 99,9 över ytan och den våta ytan över 0,5 och 5 mm/h
  tid         förändringen mellan kvartarna, prognosen mot radarn: en prognos som står still
              eller hoppar vid hela timmar avviker här
"""

from __future__ import annotations

import cv2
import numpy as np
from scipy import ndimage

TILE = 128                                  # pixlar à 2 km
RES_KM = 2.0
BANDS_KM = [(4, 8), (8, 16), (16, 32), (32, 64), (64, 128), (128, 256)]
OBJ_THR = [1.0, 5.0]
MIN_OBJ = 4                                 # pixlar, 16 km²
EPS = 1e-6


def dbr(x):
    return 10 * np.log10(np.maximum(np.nan_to_num(x), 0.1))


def logratio(a, b, floor=EPS):
    return float(np.log(max(a, floor) / max(b, floor)))


# ---------- spektrum ----------

def tiles(m: np.ndarray, o: np.ndarray, min_wet: float = 0.02) -> list[tuple[int, int]]:
    """Rutorna (övre vänstra hörnet) helt inom masken och med minst min_wet våt yta i radarn."""
    h, w = m.shape
    out = []
    for i in range(0, h - TILE + 1, TILE // 2):
        for j in range(0, w - TILE + 1, TILE // 2):
            if m[i:i + TILE, j:j + TILE].all() and (o[i:i + TILE, j:j + TILE] >= 0.1).mean() >= min_wet:
                out.append((i, j))
    return out


_WIN = np.outer(np.hanning(TILE), np.hanning(TILE)).astype(np.float32)
_K = np.hypot(*np.meshgrid(np.fft.fftfreq(TILE), np.fft.rfftfreq(TILE), indexing="ij"))  # cykler per pixel
_WL = np.where(_K > 0, RES_KM / np.maximum(_K, EPS), np.inf)                           # våglängd i km
_BAND = [(_WL >= lo) & (_WL < hi) for lo, hi in BANDS_KM]


def spectrum(x: np.ndarray, ts: list[tuple[int, int]]) -> np.ndarray | None:
    """Effekten per band (medel över rutorna) för dBR, eller None utan rutor."""
    if not ts:
        return None
    d = dbr(x)
    acc = np.zeros(len(BANDS_KM))
    for i, j in ts:
        t = d[i:i + TILE, j:j + TILE]
        p = np.abs(np.fft.rfft2((t - t.mean()) * _WIN)) ** 2
        acc += [p[b].mean() for b in _BAND]
    return acc / len(ts)


# ---------- SAL ----------

def _objects(x: np.ndarray, m: np.ndarray):
    wet = x[m & (x >= 0.1)]
    if wet.size < 20:
        return None
    thr = np.quantile(wet, 0.95) / 15
    lab, n = ndimage.label((x >= thr) & m, structure=np.ones((3, 3)))
    if n == 0:
        return None
    idx = np.arange(1, n + 1)
    s = ndimage.sum(x, lab, idx)
    mx = ndimage.maximum(x, lab, idx)
    com = np.array(ndimage.center_of_mass(x, lab, idx)).reshape(-1, 2)
    return s, mx, com


def sal(f: np.ndarray, o: np.ndarray, m: np.ndarray) -> tuple[float, float, float] | None:
    f, o = np.where(m, np.nan_to_num(f), 0.0), np.where(m, np.nan_to_num(o), 0.0)
    df, do = f[m].mean(), o[m].mean()
    if do < 0.01 or df < 0.01:
        return None
    a = (df - do) / (0.5 * (df + do))
    of, oo = _objects(f, m), _objects(o, m)
    if of is None or oo is None:
        return None
    ys, xs = np.nonzero(m)
    dmax = np.hypot(ys.max() - ys.min(), xs.max() - xs.min())
    cf, co = np.array(ndimage.center_of_mass(f)), np.array(ndimage.center_of_mass(o))

    def spread(obj, c):
        s, _, com = obj
        return (s * np.hypot(*(com - c).T)).sum() / s.sum()

    def volume(obj):
        s, mx, _ = obj
        return (s * (s / np.maximum(mx, EPS))).sum() / s.sum()

    l1 = np.hypot(*(cf - co)) / dmax
    l2 = 2 * abs(spread(of, cf) - spread(oo, co)) / dmax
    vf, vo = volume(of), volume(oo)
    s = (vf - vo) / (0.5 * (vf + vo))
    return float(s), float(a), float(l1 + l2)


# ---------- objekt, kanter, fördelning ----------

def objects(x: np.ndarray, m: np.ndarray, thr: float) -> tuple[int, float]:
    """Antalet regnområden (minst MIN_OBJ pixlar) och den ytviktade medelstorleken i km²."""
    n, lab, stats, _ = cv2.connectedComponentsWithStats(((np.nan_to_num(x) >= thr) & m).astype(np.uint8), connectivity=8)
    a = stats[1:, cv2.CC_STAT_AREA].astype(np.float64)
    a = a[a >= MIN_OBJ]
    if a.size == 0:
        return 0, 0.0
    return int(a.size), float((a ** 2).sum() / a.sum() * RES_KM ** 2)


def sharpness(x: np.ndarray, region: np.ndarray) -> float:
    d = dbr(x).astype(np.float32)
    g = np.hypot(cv2.Sobel(d, cv2.CV_32F, 1, 0, ksize=3), cv2.Sobel(d, cv2.CV_32F, 0, 1, ksize=3)) / 8
    return float(g[region].mean()) if region.any() else np.nan


QS = [0.95, 0.99, 0.999]
WET = [0.5, 5.0]


def distribution(x: np.ndarray, m: np.ndarray) -> list[float]:
    v = np.nan_to_num(x[m])
    return [float(q) for q in np.quantile(v, QS)] + [float((v >= t).mean()) for t in WET]


# ---------- allt för ett fält ----------

def shape_metrics(f: np.ndarray, o: np.ndarray, m: np.ndarray, ts, ps_o, region) -> dict:
    """Alla formmått för prognosen f mot radarn o (ps_o: radarns spektrum, region: där kanterna mäts)."""
    f = np.nan_to_num(f)
    out = {}
    ps_f = spectrum(f, ts)
    if ps_f is not None and ps_o is not None:
        for (lo, hi), a, b in zip(BANDS_KM, ps_f, ps_o):
            out[f"spek_{lo}_{hi}"] = logratio(a, b)
    r = sal(f, o, m)
    if r is not None:
        out["S"], out["A"], out["L"] = r
    for thr in OBJ_THR:
        nf, af = objects(f, m, thr)
        no, ao = objects(o, m, thr)
        if no >= 3:
            out[f"obj_antal_{thr:g}"] = logratio(nf, no, 0.5)
            out[f"obj_storlek_{thr:g}"] = logratio(af, ao, RES_KM ** 2)
    so, sf = sharpness(o, region), sharpness(f, region)
    if np.isfinite(so) and np.isfinite(sf):
        out["kanter"] = logratio(sf, so)
    names = [f"q{q * 100:g}" for q in QS] + [f"yta_{t:g}" for t in WET]
    for n, a, b in zip(names, distribution(f, m), distribution(o, m)):
        if b > (1e-3 if n.startswith("yta") else 0.1):
            out[n] = logratio(a, b)
    return out


def temporal(fs: list[np.ndarray], os_: list[np.ndarray], m: np.ndarray) -> list[float]:
    """log(prognosens förändring / radarns förändring) mellan på varandra följande kvartar."""
    out = []
    for k in range(1, len(fs)):
        if os_[k] is None or os_[k - 1] is None:
            out.append(np.nan)
            continue
        df = np.abs(np.nan_to_num(fs[k]) - np.nan_to_num(fs[k - 1]))[m].mean()
        do = np.abs(np.nan_to_num(os_[k]) - np.nan_to_num(os_[k - 1]))[m].mean()
        out.append(logratio(df, do) if do > 1e-3 else np.nan)
    return out


# ---------- samstämmighet mellan körningarna ----------

def fss(a: np.ndarray, b: np.ndarray, m: np.ndarray, thr: float = 1.0, km: float = 30.0) -> float | None:
    size = int(round(km / RES_KM)) | 1
    box = lambda x: cv2.boxFilter(x, cv2.CV_32F, (size, size), normalize=False, borderType=cv2.BORDER_CONSTANT)
    mf = m.astype(np.float32)
    den = np.maximum(box(mf), EPS)
    pa = (box(((np.nan_to_num(a) >= thr) & m).astype(np.float32)) / den)[m]
    pb = (box(((np.nan_to_num(b) >= thr) & m).astype(np.float32)) / den)[m]
    ref = float((pa ** 2 + pb ** 2).sum())
    if ref < 1.0:
        return None
    return 1 - float(((pa - pb) ** 2).sum()) / ref


def jump(new: np.ndarray, old: np.ndarray, m: np.ndarray) -> float | None:
    """Skillnaden mellan två prognoser för samma tid, relativt deras medelintensitet."""
    a, b = np.nan_to_num(new)[m], np.nan_to_num(old)[m]
    s = 0.5 * (a.mean() + b.mean())
    return float(np.abs(a - b).mean() / s) if s > 0.01 else None
