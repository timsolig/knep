"""Verifierar genererade prognoser med flera mått och i tre jämförelser.

1. Användarperspektiv: senaste tillgängliga prognos vid en given klocktid, med
   fördröjning och uppdateringstakt, verifierad på 15-minuters medelintensitet
   (KNEP-proxyns egen storhet). Horisont = minuter från klocktiden.
2. Algoritm: samma kvartsanalyser för alla, ingen fördröjning.
3. Varianter: våra momentana 5-minutersprognoser mot momentan radar.

Mått: ETS, MCC, CSI, POD, FAR, frekvensbias, FSS på 2/10/30 km, MAE,
SAL, spektral textur (kvar av 4 till 16 km-skalor), hoppighet och CRPS.
"""

from __future__ import annotations

import argparse
import os
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter, uniform_filter

sys.path.insert(0, str(Path(__file__).parent))
from generate import NK, NS, decode, encode  # noqa: E402

THRS = [0.5, 1.0, 2.0, 5.0, 10.0, 20.0]
FSS_THRS = [1.0, 5.0, 10.0]
FSS_SCALES = [1, 5, 15]  # pixlar à 2 km
STORED = ["lk", "lk30", "ema", "filt", "sprog", "steps"]
OURS = STORED + ["oro"]
SAL_OURS = ["lk", "oro", "sprog", "steps"]
LAT_OURS = 3
LAG_W = (4.0, 2.0, 1.0)  # vikter för de tre senaste körningarna i "lag"
CDF_TARGET = os.environ.get("NOWCAST_CDF_TARGET", "analysis")


class Case:
    def __init__(self, path: Path):
        d = np.load(path)
        self.name = path.stem
        self.times = [datetime.fromisoformat(t) for t in d["times"]]
        self.obs = decode(d["obs"])
        n = len(self.times)
        self.acc = np.full_like(self.obs, np.nan)
        for i in range(2, n):
            self.acc[i] = self.obs[i - 2 : i + 1].mean(axis=0)
        self.issues = list(d["issues"])
        self.kissues = list(d["kissues"])
        self.f = {k: d[k] for k in STORED if k in OURS or k == "lk30"}  # bara det som jämförs
        ext = path.with_name(path.stem + "_ext.npz")
        if ext.exists():
            e = np.load(ext)
            for k in e.files:
                if k in OURS:
                    self.f[k] = e[k]
        self.knep = {"knep": d["knep"], "knep_inst": d["knep_inst"]}
        self.members = {tuple(k): v for k, v in zip(d["member_keys"], d["member_vals"])}
        self.quarter = [i for i, t in enumerate(self.times) if t.minute % 15 == 0]
        self.n = n
        self._cache = {}
        self.motion = d["motion"] if CDF_TARGET == "advected" else None
        self.corr = self._stationary_correction(self.f["lk30"])
        if {"cdf", "oro_cdf"} & set(OURS):
            self.f["cdf"] = self._matched(self.f["lk30"])
            self.corr_cdf = self._stationary_correction(self.f["cdf"])

    def _matched(self, base):
        """Sannolikhetsmatchar varje prognosbild mot analysens fördelning (lk30 + CDF-matchning).

        Extrapoleringens bilinjära interpolation smetar ut toppar; matchningen återställer
        analysens intensitetsfördelning men behåller prognosens rangordning, alltså läget.
        Med CDF_TARGET = "advected" (miljövariabeln NOWCAST_CDF_TARGET) är målet analysen flyttad
        med närmaste granne, så att nederbörd som lämnar området också lämnar fördelningen.
        """
        out = np.empty_like(base)
        for j, i in enumerate(self.issues):
            if CDF_TARGET == "advected":
                from pysteps.extrapolation.semilagrangian import extrapolate

                tgt = extrapolate(np.nan_to_num(self.obs[i]), self.motion[j].astype(np.float32), base.shape[1], interp_order=0)
                tgt[:, ~np.isfinite(self.obs[i])] = np.nan
            for k in range(base.shape[1]):
                target = tgt[k] if CDF_TARGET == "advected" else self.obs[i]
                out[j, k] = encode(cdf_match(decode(base[j, k]), target))
        return out

    def _stationary_correction(self, base, window=12, sigma=5.0, shrink=0.5, clip=6.0):
        """Lär en platsbunden tillväxt/avtagande-karta online ur senaste timmens 30-minutersfel.

        För varje körning i: medel av 10·log10(obs/prognos) där både obs och prognosen
        med 30 min ledtid är ≥ 0,5 mm/h, utjämnat 10 km och krympt mot noll där underlaget är tunt.
        En enkel, träningsfri ersättare för en terrängkarta: fångar lovart/lä och strålblockering.
        """
        out = {}
        lk30 = base
        shape = self.obs.shape[1:]
        for i in self.issues:
            num, den = np.zeros(shape), np.zeros(shape)
            for t in range(i - window + 1, i + 1):
                src = t - 6
                if src not in self.issues:
                    continue
                fc = decode(lk30[self.issues.index(src), 5])
                o = self.obs[t]
                ok = np.isfinite(fc) & np.isfinite(o) & (fc >= 0.5) & (o >= 0.5)
                num += np.where(ok, 10 * np.log10(np.where(ok, o, 1.0) / np.where(ok, fc, 1.0)), 0.0)
                den += ok
            g = gaussian_filter(num, sigma) / (gaussian_filter(den, sigma) + shrink)
            out[i] = np.clip(g, -clip, clip).astype(np.float32)
        return out

    def inst(self, s: str, i: int, t: int) -> np.ndarray | None:
        if t <= i:
            return self.obs[t]
        if i not in self.issues or t - i > NS:
            return None
        if s == "oro":
            base = decode(self.f["lk30"][self.issues.index(i), t - i - 1])
            return base * 10 ** (self.corr[i] * min(1.0, (t - i) / 6) / 10)
        if s == "oro_cdf":
            base = decode(self.f["cdf"][self.issues.index(i), t - i - 1])
            return base * 10 ** (self.corr_cdf[i] * min(1.0, (t - i) / 6) / 10)
        if s in ("lag", "lag_cdf", "lagr"):
            key = (s, i, t)
            if key not in self._cache:
                if len(self._cache) > 400:
                    self._cache.clear()
                f = self._lagged("oro", i, t, ramp=s == "lagr")
                self._cache[key] = cdf_match(f, self.obs[i]) if s == "lag_cdf" else f
            return self._cache[key]
        return decode(self.f[s][self.issues.index(i), t - i - 1])

    def _lagged(self, base, i, t, ramp=False):
        """Viktat medel av de tre senaste körningarnas prognoser för samma tid.

        Fasta vikter 4:2:1, eller med ramp: vikten på äldre körningar r^k där r växer
        från 0 till 0,5 över första timmen, så att korta ledtider bygger på senaste körningen.
        """
        r = min(0.5, 0.5 * (t - i) / 12) if ramp else 0.5
        num, den = None, 0.0
        for k in range(len(LAG_W)):
            w = r ** k
            j = i - k
            if j not in self.issues or t - j > NS:
                continue
            f = self.inst(base, j, t)
            num = w * f if num is None else num + w * f
            den += w
        return num / den

    def acc_ours(self, s: str, i: int, v: int) -> np.ndarray | None:
        parts = [self.inst(s, i, t) for t in (v - 2, v - 1, v)]
        return None if any(p is None for p in parts) else np.mean(parts, axis=0)

    def acc_knep(self, s: str, i: int, v: int) -> np.ndarray | None:
        if i not in self.kissues or (v - i) % 3 or not 0 < (v - i) // 3 <= NK:
            return None
        return decode(self.knep[s][self.kissues.index(i), (v - i) // 3 - 1])

    def ens(self, i: int, v: int) -> np.ndarray | None:
        q = self.members.get((i, v))
        return None if q is None else decode(q)


def cdf_match(f, target):
    """Ger f målfältets värdefördelning men behåller f:s rangordning.

    Lika värden (främst nollor) ordnas efter ett utjämnat fält, så att pixlar nära
    regn blir våta först om målet har större regnyta än prognosen.
    """
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


# ---- mått ------------------------------------------------------------------

def contingency(f, o, thr):
    a, b = f >= thr, o >= thr
    h = np.sum(a & b); fa = np.sum(a & ~b); m = np.sum(~a & b); cn = np.sum(~a & ~b)
    return np.array([h, m, fa, cn], float)


def cat_scores(c):
    h, m, fa, cn = c
    n = h + m + fa + cn
    hr = (h + m) * (h + fa) / n if n else 0
    ets = (h - hr) / (h + m + fa - hr) if (h + m + fa - hr) else np.nan
    den = np.sqrt((h + fa) * (h + m) * (cn + fa) * (cn + m))
    mcc = (h * cn - fa * m) / den if den else np.nan
    # SEDI (Ferro och Stephenson 2011): beror inte på hur sällsynt händelsen är, därför lämpad för extremer
    H = h / (h + m) if (h + m) else np.nan
    F = fa / (fa + cn) if (fa + cn) else np.nan
    if 0 < H < 1 and 0 < F < 1:
        sedi = (np.log(F) - np.log(H) - np.log(1 - F) + np.log(1 - H)) / (np.log(F) + np.log(H) + np.log(1 - F) + np.log(1 - H))
    else:
        sedi = np.nan
    return {
        "ETS": ets, "MCC": mcc, "SEDI": sedi,
        "CSI": h / (h + m + fa) if (h + m + fa) else np.nan,
        "POD": h / (h + m) if (h + m) else np.nan,
        "FAR": fa / (h + fa) if (h + fa) else np.nan,
        "BIAS": (h + fa) / (h + m) if (h + m) else np.nan,
    }


def fss_parts(f, o, thr, scale):
    a, b = (f >= thr).astype(float), (o >= thr).astype(float)
    if scale > 1:
        a = uniform_filter(a, size=scale, mode="constant")
        b = uniform_filter(b, size=scale, mode="constant")
    return np.array([np.sum((a - b) ** 2), np.sum(a**2) + np.sum(b**2)])


def texture(f, o, px_km=2.0):
    """log10 av forecast/obs-effekt i våglängder 4 till 16 km (0 = som observerat, negativt = utsmetat)."""
    def psd(x):
        x = x - x.mean()
        p = np.abs(np.fft.fft2(x)) ** 2
        ky = np.fft.fftfreq(x.shape[0]); kx = np.fft.fftfreq(x.shape[1])
        k = np.sqrt(ky[:, None] ** 2 + kx[None, :] ** 2) / px_km  # cykler per km
        band = (k >= 1 / 16) & (k <= 1 / 4)
        return p[band].mean()
    po = psd(o)
    return np.log10(psd(f) / po) if po > 0 else np.nan


def sal(f, o):
    """SAL på 4 km (2 x 2-medel) för att hålla nere tiden; objekten är ändå större än så."""
    try:
        from pysteps.verification.salscores import sal as _sal
        h, w = (f.shape[0] // 2) * 2, (f.shape[1] // 2) * 2
        c = lambda x: x[:h, :w].reshape(h // 2, 2, w // 2, 2).mean(axis=(1, 3))
        return _sal(c(f), c(o))
    except Exception:
        return (np.nan, np.nan, np.nan)


def crps_ens(ens, o):
    e = ens.reshape(ens.shape[0], -1)
    y = o.ravel()
    t1 = np.mean(np.abs(e - y[None]), axis=0)
    t2 = np.mean(np.abs(e[:, None] - e[None]), axis=(0, 1))
    return np.mean(t1 - 0.5 * t2)


# ---- jämförelser -----------------------------------------------------------

class Acc:
    """Samlar per (system, horisont): kontingens per tröskel, FSS-delar, MAE, plus per prov för bootstrap."""

    def __init__(self):
        self.c = defaultdict(lambda: np.zeros(4))
        self.fss = defaultdict(lambda: np.zeros(2))
        self.mae = defaultdict(list)
        self.tex = defaultdict(list)
        self.sal = defaultdict(list)
        self.crps = defaultdict(list)
        self.tail = defaultdict(list)  # (system, h) → [(log10 q99-kvot, log10 q99,9-kvot)]
        self.samples = defaultdict(list)  # (system, h, thr) → [(cluster, counts)]
        self.jump = defaultdict(list)
        self.flip = defaultdict(list)

    def merge(self, other):
        """Lägger till ett annat Acc (ett fall i taget håller nere minnet)."""
        for name in ("c", "fss"):
            mine = getattr(self, name)
            for k, v in getattr(other, name).items():
                mine[k] = mine[k] + v
        for name in ("mae", "tex", "sal", "crps", "tail", "samples", "jump", "flip"):
            mine = getattr(self, name)
            for k, v in getattr(other, name).items():
                mine[k].extend(v)
        return self

    def add(self, s, h, f, o, cluster, extra=True, with_sal=False):
        for thr in THRS:
            c = contingency(f, o, thr)
            self.c[(s, h, thr)] += c
            self.samples[(s, h, thr)].append((cluster, c))
        for thr in FSS_THRS:
            for sc in FSS_SCALES:
                self.fss[(s, h, thr, sc)] += fss_parts(f, o, thr, sc)
        self.mae[(s, h)].append(np.mean(np.abs(f - o)))
        # toppkvot: de högsta intensiteterna i prognosen mot radarns, oavsett läge
        qo = np.quantile(o, [0.99, 0.999])
        if qo[1] >= 1.0:
            qf = np.quantile(f, [0.99, 0.999])
            self.tail[(s, h)].append(np.log10(np.maximum(qf, 0.05) / np.maximum(qo, 0.05)))
        if extra and (o >= 1).sum() > 50:
            self.tex[(s, h)].append(texture(f, o))
            if with_sal:
                self.sal[(s, h)].append(sal(f, o))

    def table(self):
        out = {}
        for (s, h, thr), c in self.c.items():
            out.setdefault(s, {}).setdefault(h, {})[f"cat_{thr}"] = cat_scores(c)
        for (s, h, thr, sc), (num, den) in self.fss.items():
            out[s][h][f"FSS_{thr}_{2 * sc}km"] = 1 - num / den if den else np.nan
        for (s, h), v in self.mae.items():
            out[s][h]["MAE"] = float(np.mean(v))
        for (s, h), v in self.tex.items():
            out[s][h]["texture"] = float(np.nanmean(v))
        for (s, h), v in self.sal.items():
            a = np.array(v, float)
            out[s][h]["SAL_S"] = float(np.nanmedian(np.abs(a[:, 0])))
            out[s][h]["SAL_A"] = float(np.nanmedian(np.abs(a[:, 1])))
            out[s][h]["SAL_L"] = float(np.nanmedian(a[:, 2]))
        for (s, h), v in self.crps.items():
            out.setdefault(s, {}).setdefault(h, {})["CRPS"] = float(np.mean(v))
        for (s, h), v in self.tail.items():
            a = np.array(v)
            out[s][h]["TAIL99"] = float(10 ** np.median(a[:, 0]))
            out[s][h]["TAIL999"] = float(10 ** np.median(a[:, 1]))
        for (s, h), v in self.jump.items():
            out[s][h]["jump"] = float(np.mean(v))
        for (s, h), v in self.flip.items():
            out[s][h]["flipflop"] = float(np.mean(v))
        return out


def common_mask(fields, o):
    m = np.isfinite(o)
    for f in fields.values():
        m &= np.isfinite(f)
    return m


def operational(cases, lats, horizons=range(15, 70, 5), sal_lats=(10, 15), with_sal=True):
    """Alla system i samma prov: våra med 3 min fördröjning, KNEP-proxyn med varje fördröjning i lats."""
    acc = Acc()
    jump, flip = acc.jump, acc.flip
    knames = [f"{s}_L{int(L)}" for L in lats for s in ("knep", "knep_inst")]
    sal_systems = set(SAL_OURS) | {f"{s}_L{int(L)}" for L in sal_lats for s in ("knep", "knep_inst")}
    for cs in cases:
        def latest(issues, tau, lat):
            lim = tau - int(np.ceil(lat / 5))
            c = [i for i in issues if i <= lim]
            return c[-1] if c else None

        def fc_all(tau, v):
            out = {}
            i = latest(cs.issues, tau, LAT_OURS)
            if i is None:
                return None
            for s in OURS:
                f = cs.acc_ours(s, i, v)
                if f is None:
                    return None
                out[s] = f
            for L in lats:
                k = latest(cs.kissues, tau, L)
                if k is None:
                    return None
                for s in cs.knep:
                    f = cs.acc_knep(s, k, v)
                    if f is None:
                        return None
                    out[f"{s}_L{int(L)}"] = f
            return out, cs.ens(i, v)

        for tau in range(cs.n):
            for v in cs.quarter:
                h = (v - tau) * 5
                if h not in horizons:
                    continue
                hb = 15 * (h // 15)  # horisontintervall 15 till 25, 30 till 40, 45 till 55, 60 till 65 min
                got = fc_all(tau, v)
                if got is None:
                    continue
                fields, ens = got
                o = cs.acc[v]
                # de deterministiska systemen jämförs på sin gemensamma yta; ensemblen
                # får egen mask så att dess saknade värden inte styr ytan för de andra
                m = common_mask(fields, o)
                oo = np.where(m, o, 0.0)
                for s, f in fields.items():
                    acc.add(s, hb, np.where(m, f, 0.0), oo, (cs.name, v), extra=h in (30, 45, 60),
                            with_sal=with_sal and h in (30, 60) and s in sal_systems)
                if ens is not None:
                    me = m & np.all(np.isfinite(ens), axis=0)
                    acc.crps[("steps_ens", hb)].append(crps_ens(ens[:, me], o[me]))
                    for s, f in fields.items():
                        acc.crps[(s, hb)].append(np.mean(np.abs(f[me] - o[me])))
                # hoppighet: samma giltighetstid, prognoser tillgängliga med 15 minuters mellanrum
                later = fc_all(tau + 3, v) if (v - tau - 3) * 5 >= 15 else None
                latest2 = fc_all(tau + 6, v) if (v - tau - 6) * 5 >= 15 else None
                if later is not None:
                    f2 = later[0]
                    for s in fields:
                        mm = m & np.isfinite(f2[s])
                        a, b = (fields[s] >= 1.0) & mm, (f2[s] >= 1.0) & mm
                        u = np.sum(a | b)
                        if u:
                            jump[(s, hb)].append(np.sum(a ^ b) / u)
                        if latest2 is not None:
                            f3 = latest2[0][s]
                            m3 = mm & np.isfinite(f3)
                            a3, b3, c = a & m3, b & m3, (f3 >= 1.0) & m3
                            u3 = np.sum(a3 | b3 | c)
                            if u3:
                                flip[(s, hb)].append(np.sum((a3 == c) & (a3 != b3)) / u3)
    return acc.table(), acc, knames


def operational_inst(cases, lats, horizons=range(15, 70, 5)):
    """Användarperspektiv på 5-minutersupplösning: momentan radar som facit.

    KNEP-proxyns 15-minutersvärde gäller för hela sin kvart, som när en karta
    med 15-minuterssteg visas i en 5-minutersanimation.
    """
    acc = Acc()
    for cs in cases:
        def latest(issues, tau, lat):
            lim = tau - int(np.ceil(lat / 5))
            c = [i for i in issues if i <= lim]
            return c[-1] if c else None

        for tau in range(cs.n):
            i = latest(cs.issues, tau, LAT_OURS)
            if i is None:
                continue
            for t in range(tau + 1, cs.n):
                h = (t - tau) * 5
                if h not in horizons:
                    continue
                hb = 15 * (h // 15)
                q = t if t in cs.quarter else min([x for x in cs.quarter if x > t], default=None)
                if q is None:
                    continue
                fields = {s: cs.inst(s, i, t) for s in OURS}
                for L in lats:
                    k = latest(cs.kissues, tau, L)
                    for s in cs.knep:
                        fields[f"{s}_L{int(L)}"] = None if k is None else cs.acc_knep(s, k, q)
                if any(f is None for f in fields.values()):
                    continue
                o = cs.obs[t]
                m = common_mask(fields, o)
                for s, f in fields.items():
                    acc.add(s, hb, np.where(m, f, 0.0), np.where(m, o, 0.0), (cs.name, t), extra=h in (30, 45, 60))
    return acc.table(), acc


def algorithmic(cases, leads=(15, 30, 45, 60)):
    acc = Acc()
    for cs in cases:
        for i in cs.kissues:
            if i not in cs.issues:
                continue
            for lead in leads:
                v = i + lead // 5
                if v >= cs.n:
                    continue
                fields = {s: cs.acc_ours(s, i, v) for s in OURS}
                fields.update({s: cs.acc_knep(s, i, v) for s in cs.knep})
                if any(f is None for f in fields.values()):
                    continue
                o = cs.acc[v]
                m = common_mask(fields, o)
                for s, f in fields.items():
                    acc.add(s, lead, np.where(m, f, 0.0), np.where(m, o, 0.0), (cs.name, v), extra=lead in (30, 60), with_sal=True)
    return acc.table(), acc


def variants_inst(cases, leads=(5, 15, 30, 45, 60)):
    acc = Acc()
    for cs in cases:
        for i in cs.issues:
            for lead in leads:
                t = i + lead // 5
                if t >= cs.n:
                    continue
                fields = {s: cs.inst(s, i, t) for s in OURS}
                if any(f is None for f in fields.values()):
                    continue
                o = cs.obs[t]
                m = common_mask(fields, o)
                for s, f in fields.items():
                    acc.add(s, lead, np.where(m, f, 0.0), np.where(m, o, 0.0), (cs.name, t), extra=lead in (30, 60))
    return acc.table(), acc


def bootstrap_diff(acc, a, b, h, thr, score="ETS", n=1000, seed=0):
    """Klusterbootstrap över (fall, giltighetstid): fördelning av score(a) − score(b)."""
    sa, sb = acc.samples[(a, h, thr)], acc.samples[(b, h, thr)]
    clusters = sorted({c for c, _ in sa})
    ca = defaultdict(lambda: np.zeros(4)); cb = defaultdict(lambda: np.zeros(4))
    for c, x in sa:
        ca[c] += x
    for c, x in sb:
        cb[c] += x
    rng = np.random.default_rng(seed)
    diffs = []
    for _ in range(n):
        pick = rng.choice(len(clusters), len(clusters))
        A = sum((ca[clusters[p]] for p in pick), np.zeros(4))
        B = sum((cb[clusters[p]] for p in pick), np.zeros(4))
        diffs.append(cat_scores(A)[score] - cat_scores(B)[score])
    d = np.array(diffs)
    return float(np.nanpercentile(d, 5)), float(np.nanmedian(d)), float(np.nanpercentile(d, 95)), float(np.mean(d > 0))


def clean(x):
    if isinstance(x, dict):
        return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, (float, np.floating)):
        return None if not np.isfinite(x) else round(float(x), 4)
    return x


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("gen", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--cases", nargs="*", default=None)
    p.add_argument("--latencies", nargs="*", type=float, default=[5, 10, 15, 20])
    p.add_argument("--sal-latencies", nargs="*", type=float, default=[10, 15], help="fördröjningar där SAL beräknas (SAL är långsam)")
    p.add_argument("--skip", nargs="*", default=[], help="hoppa över: algorithmic, variants")
    p.add_argument("--boot-systems", nargs="*", default=["lk", "lk30", "oro", "sprog", "steps"])
    p.add_argument("--no-sal", action="store_true")
    p.add_argument("--no-per-case", action="store_true")
    p.add_argument("--ours", nargs="*", default=None, help="våra system att jämföra (standard: alla lagrade och oro); även cdf, oro_cdf")
    p.add_argument("--sal-systems", nargs="*", default=None, help="våra system där SAL beräknas")
    a = p.parse_args()
    if a.ours:
        OURS[:] = a.ours
    if a.sal_systems is not None:
        SAL_OURS[:] = a.sal_systems
    files = sorted(p for p in a.gen.glob("*.npz") if not p.stem.endswith("_ext"))
    if a.cases:
        files = [f for f in files if f.stem in a.cases]
    res = {"cases": [f.stem for f in files]}
    # ett fall i taget i minnet; ackumulatorerna slås ihop
    acc_op, acc_inst, per_case = Acc(), Acc(), {}
    acc_alg, acc_var = Acc(), Acc()
    for f in files:
        cs = Case(f)
        if "operational" not in a.skip:
            t1, acc1, _ = operational([cs], a.latencies, sal_lats=a.sal_latencies, with_sal=not a.no_sal)
            acc_op.merge(acc1)
            if not a.no_per_case:
                per_case[cs.name] = {s: {h: {"ETS1": r.get("cat_1.0", {}).get("ETS"), "ETS5": r.get("cat_5.0", {}).get("ETS"),
                                             "MCC1": r.get("cat_1.0", {}).get("MCC"), "MCC5": r.get("cat_5.0", {}).get("MCC"),
                                             "SEDI10": r.get("cat_10.0", {}).get("SEDI")}
                                         for h, r in hs.items()} for s, hs in t1.items()}
        if "inst" not in a.skip:
            acc_inst.merge(operational_inst([cs], a.latencies)[1])
        if "algorithmic" not in a.skip:
            acc_alg.merge(algorithmic([cs])[1])
        if "variants" not in a.skip:
            acc_var.merge(variants_inst([cs])[1])
        print(f"{cs.name}: klar", flush=True)
        del cs
    if "operational" not in a.skip:
        boot = {}
        for L in a.latencies:
            ref = f"knep_L{int(L)}"
            for s in a.boot_systems:
                for h in (15, 30, 45, 60):
                    for thr in (1.0, 5.0):
                        for score in ("ETS", "MCC"):
                            if (s, h, thr) in acc_op.samples and (ref, h, thr) in acc_op.samples:
                                boot[f"{s}|{ref}|{h}|{thr}|{score}"] = bootstrap_diff(acc_op, s, ref, h, thr, score)
        res["operational"] = {"scores": acc_op.table(), "bootstrap": boot, "latencies": a.latencies}
        res["operational_per_case"] = per_case
    if "inst" not in a.skip:
        res["operational_inst"] = acc_inst.table()
    if "algorithmic" not in a.skip:
        res["algorithmic"] = acc_alg.table()
    if "variants" not in a.skip:
        res["variants_inst"] = acc_var.table()
    a.out.write_text(json.dumps(clean(res), indent=1))
    print(f"skrev {a.out}")
