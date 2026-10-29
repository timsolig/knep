"""Extremkalibrering: särdrag, sannolikheter och omskalning av toppar.

Delas av driften (model.py) och träningen (experiments/extremes.py) så att modellen
används på exakt samma särdrag som den tränades på.

En gradient boosting-modell per tröskel ger sannolikheten att radarn överskrider
tröskeln i en pixel, omkalibrerad isotont per ledtid på prognoser utanför urvalet.
Det är sannolikheterna som används i drift. En monoton omskalning av kedjans värden mot
den förväntade ytan över varje tröskel finns kvar (calibrate_tail) för experimenten,
men den förlorade mot kedjan utan omskalning och är avstängd i drift.
"""

from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter, maximum_filter, uniform_filter

THR = [1.0, 5.0, 10.0, 20.0]
FEATURES = ["db", "max3", "max7", "max15", "mean7", "mean15", "mean31", "frac1", "frac5", "frac10",
            "lead", "tend15", "tend30", "corr", "speed", "q99", "q999", "wet"]
MONO = {"db", "max3", "max7", "max15", "mean7", "mean15", "mean31", "frac1", "frac5", "frac10"}


def db(x):
    return 10 * np.log10(np.maximum(x, 0.1))


def tendencies(now, past15, past30, motion, steps, advect):
    """Intensitetsändring längs banan de senaste 15 och 30 min, flyttad framåt med rörelsen.

    now, past15, past30: analyser i mm/h (past* kan vara None). advect(fält, steg) flyttar ett
    fält med rörelsen och returnerar (steg, H, W). Returnerar två (steps, H, W), farten och
    tre tal om händelsen (99- och 99,9-percentil i dB och andel med minst 1 mm/h).
    """
    n = gaussian_filter(np.nan_to_num(now), 2.0)
    out = []
    for back, past in ((3, past15), (6, past30)):
        if past is None:
            out.append(np.zeros((steps,) + now.shape, np.float32))
            continue
        p = gaussian_filter(np.nan_to_num(advect(np.nan_to_num(past), back)[-1]), 2.0)
        tend = np.where(np.maximum(n, p) >= 0.3, db(n) - db(p), 0.0).astype(np.float32)
        out.append(np.nan_to_num(advect(tend, steps)).astype(np.float32))
    speed = np.hypot(motion[0], motion[1]).astype(np.float32)
    o = now[np.isfinite(now)]
    q99, q999 = np.quantile(o, [0.99, 0.999]) if o.size else (0.0, 0.0)
    wet = float(np.mean(o >= 1.0)) if o.size else 0.0
    return out[0], out[1], speed, (float(db(q99)), float(db(q999)), wet)


def features(c, k, tend15, tend30, corr, speed, dom):
    """Särdrag (F, H, W) för kedjans fält c vid ledtid k (5-minuterssteg)."""
    cz = np.nan_to_num(c)
    f = np.empty((len(FEATURES),) + cz.shape, np.float32)
    f[0] = db(cz)
    f[1], f[2], f[3] = (db(maximum_filter(cz, w)) for w in (3, 7, 15))
    f[4], f[5], f[6] = (db(uniform_filter(cz, w)) for w in (7, 15, 31))
    f[7], f[8], f[9] = (uniform_filter((cz >= t).astype(np.float32), 15) for t in (1.0, 5.0, 10.0))
    f[10] = k * 5
    f[11], f[12] = tend15[k - 1], tend30[k - 1]
    f[13] = corr * min(1.0, k / 6) if corr is not None else 0.0
    f[14] = speed
    f[15], f[16], f[17] = dom
    return f


USE_THR = (5.0, 10.0)  # trösklar som räknas i drift: de som kalibreras och visas
STRIDE = 2  # sannolikheterna räknas på varannan pixel och interpoleras; de är släta fält


def predict_proba(models, f, mask, thresholds=USE_THR, stride=STRIDE):
    """Sannolikheter (len(THR), H, W) för thresholds, 0 för övriga trösklar.

    Räknas bara där mask är sann, på var stride:e pixel i båda led, och interpoleras
    bilinjärt tillbaka. Monotona över trösklarna: en högre tröskel räknas bara där den
    lägre har en sannolikhet värd att nämna.
    """
    from scipy.ndimage import zoom

    P = np.zeros((len(THR),) + mask.shape, np.float32)
    sub = mask[::stride, ::stride]
    if not sub.any():
        return P
    fs = f[:, ::stride, ::stride]
    prev = None
    for t in sorted(thresholds):
        n = THR.index(t)
        ps = np.zeros(sub.shape, np.float32)
        where = sub if prev is None else sub & (prev >= 0.002)
        if where.any():
            ps[where] = models[t].predict_proba(fs[:, where].T)[:, 1]
        if prev is not None:
            ps = np.minimum(ps, prev)
        prev = ps
        full = zoom(ps, stride, order=1)[: mask.shape[0], : mask.shape[1]] if stride > 1 else ps
        pad = np.zeros(mask.shape, np.float32)
        pad[: full.shape[0], : full.shape[1]] = full
        P[n] = np.where(mask, pad, 0.0)
    return P


# Bara trösklar där sannolikheterna har skicklighet på nya händelser kalibreras (5 och 10 mm/h).
# Vid 20 mm/h finns ingen pixelvis skicklighet i testerna, så över 10 mm/h behålls kedjans kvoter.
CAL_THR = [5.0, 10.0]


def calibrate_tail(c, expected, weight=1.0):
    """Skalar om c monotont så att antalet pixlar över 5 och 10 mm/h blir det förväntade.

    expected: förväntat antal per tröskel i THR (summan av sannolikheterna). Med weight < 1 blir
    målet ett geometriskt medel av kedjans eget antal och det förväntade. Rangordningen, alltså läge
    och struktur, behålls. Upp till 1 mm/h ändras inget och över 10 mm/h behålls kvoterna.
    """
    ok = np.isfinite(c) & (c >= 0.1)
    if ok.sum() < 10:
        return c
    s = np.sort(c[ok])[::-1]
    xs, ys = [np.log(0.1), 0.0], [np.log(0.1), 0.0]  # identitet till och med 1 mm/h
    for t in CAL_THR:
        e = expected[THR.index(t)]
        own = float((s >= t).sum())
        target = np.exp((1 - weight) * np.log(own + 0.5) + weight * np.log(e + 0.5)) - 0.5
        r = int(round(target))
        if r < 1:
            q = s[0] * 1.02  # förväntat färre än en pixel: ingen pixel ska nå tröskeln
        else:
            q = s[min(r, len(s)) - 1]
        x = np.log(max(q, 1.0001))
        if x <= xs[-1]:
            x = xs[-1] + 1e-4
        xs.append(x)
        ys.append(np.log(t))
    out = np.array(c, np.float32)
    v = np.log(np.maximum(c[ok], 0.1))
    mapped = np.interp(v, xs, ys)
    hi = v > xs[-1]
    mapped[hi] = ys[-1] + (v[hi] - xs[-1])
    out[ok] = np.exp(mapped)
    return out


LEAD_BUCKETS = ((1, 3), (4, 6), (7, 9), (10, 24))  # ledtider i 5-minuterssteg för omkalibreringen


def bucket(k):
    return next(n for n, (a, b) in enumerate(LEAD_BUCKETS) if a <= k <= b)


def recalibrate(P, k, recal):
    """Isoton omkalibrering per tröskel och ledtidsintervall, lärd på prognoser utanför urvalet."""
    if not recal:
        return P
    out = P.copy()
    for t in USE_THR:
        key = (t, bucket(k))
        if key in recal:
            x, y = recal[key]
            n = THR.index(t)
            out[n] = np.where(P[n] > 0, np.interp(P[n], x, y), 0.0)
    # monotont över trösklarna även efter omkalibreringen
    for a, b in zip(USE_THR, USE_THR[1:]):
        out[THR.index(b)] = np.minimum(out[THR.index(b)], out[THR.index(a)])
    return out


def apply(model, c, k, tend15, tend30, corr, speed, dom, rescale=False):
    """Fält och sannolikheter (len(THR), H, W) för en ledtid. model: dict från load().

    Fältet skalas om bara med rescale: i verifieringen på sex fall förlorade omskalningen
    ETS, SEDI och FSS vid 10 mm/h mot kedjan utan den, så i drift används sannolikheterna
    för extremerna och fältet lämnas som det är.
    """
    f = features(c, k, tend15, tend30, corr, speed, dom)
    mask = np.isfinite(c) & (f[3] >= db(1.0))  # minst 1 mm/h inom 30 km
    P = recalibrate(predict_proba(model["models"], f, mask), k, model.get("recal"))
    if not rescale:
        return c, P
    expected = P.reshape(len(THR), -1).sum(axis=1)
    return calibrate_tail(c, expected), P


def load(path: Path):
    with open(path, "rb") as fh:
        d = pickle.load(fh)
    if d.get("features") != FEATURES or d.get("thr") != THR:
        raise ValueError(f"{path}: modellen är tränad på andra särdrag")
    import sklearn

    if d.get("sklearn") and d["sklearn"] != sklearn.__version__:
        import logging

        logging.getLogger("nowcast").warning("%s är tränad med scikit-learn %s men %s är installerad; träna om",
                                             path, d["sklearn"], sklearn.__version__)
    return d
