"""Varianter av kedjan mot aspekterna, byggda direkt ur de sparade analyserna och rörelsefälten.

Varje variant är kedjan (extrapolering, fördelningsmatchning, platskarta) med en ändring:

  fart=s        rörelsefältet gånger s (tajming: ligger prognosen efter eller före?)
  iter=n        n iterationer för banorna bakåt i den semi-Lagrangeska extrapoleringen
  mål=flyttad   fördelningsmatchningen mot analysen flyttad med närmaste granne i stället för
                hela analysen, så att nederbörd som lämnar området också lämnar fördelningen
  rörelse=lk60  Lucas-Kanade på 60 min i stället för 30 min
  ema=a         rörelsefältet utjämnat mellan körningarna, vikt a på det nya
  trend=φ       hela fältet skalas med senaste halvtimmens volymförändring upphöjd till φ per halvtimme
  rörelse=gles  Lucas-Kanade på bilder med 15 minuters mellanrum (30 min historik); gles10 med
                10 minuter (30 min), gles60 med 30 minuter (60 min), gles4 med 15 minuter (45 min)

Måtten är de i aspects.py plus ETS och FSS, alla på ytan där banan bakåt börjar inom täckningen.
Resultat per fall, så att ett val kan göras med ett fall utanför i taget.

    python experiments/tune_chain.py GEN --out tune_chain.json --variants bas fart=1.1 fart=1.2 ...
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from pysteps.extrapolation.semilagrangian import extrapolate
from pysteps.motion.lucaskanade import dense_lucaskanade
from scipy.ndimage import uniform_filter

sys.path.insert(0, str(Path(__file__).parent))
import aspects  # noqa: E402
import verify  # noqa: E402
from generate import decode  # noqa: E402

NS = 12
EVAL = (3, 6, 9, 12)
# glesa rörelsefält: (mellanrum i 5-minuterssteg, antal bilder)
GLES = {"gles": (3, 3), "gles10": (2, 4), "gles60": (6, 3), "gles4": (3, 4)}


def parse(v: str) -> dict:
    cfg = {"fart": 1.0, "iter": 1, "mål": "analys", "rörelse": "lk30", "plats": True, "ema": 1.0, "trend": 0.0}
    if v == "bas":
        return cfg
    for part in v.split(","):
        k, val = part.split("=")
        cfg[k] = float(val) if k in ("fart", "ema", "trend") else int(val) if k == "iter" else (val == "ja") if k == "plats" else val
    return cfg


def _db(x):
    return 10 * np.log10(np.maximum(np.nan_to_num(x), 0.1))


def forecasts(obs, issues, motion, cfg):
    """(issues, NS, H, W) för en variant, utan platskarta."""
    out = np.empty((len(issues), NS) + obs.shape[1:], np.float32)
    v_prev = None
    for j, i in enumerate(issues):
        a = obs[i]
        if cfg["rörelse"] == "lk60":
            with contextlib.redirect_stdout(io.StringIO()):
                v = dense_lucaskanade(_db(obs[max(0, i - 12) : i + 1]), verbose=False)
        elif cfg["rörelse"] in GLES:
            # bilder med glesare mellanrum: större förflyttning mot bruset, delas sedan med mellanrummet
            gap, n = GLES[cfg["rörelse"]]
            frames = [max(0, i - gap * m) for m in range(n - 1, -1, -1)]
            with contextlib.redirect_stdout(io.StringIO()):
                v = dense_lucaskanade(_db(obs[frames]), verbose=False) / gap
        else:
            v = motion[j].astype(np.float32)
        if cfg["ema"] < 1.0 and v_prev is not None:  # rörelsen utjämnad mellan körningarna
            v = cfg["ema"] * v + (1 - cfg["ema"]) * v_prev
        v_prev = v
        v = v * cfg["fart"]
        raw = extrapolate(np.nan_to_num(a), v, NS, n_iter=cfg["iter"])
        raw[:, ~np.isfinite(a)] = np.nan
        if cfg["mål"] == "flyttad":
            tgt = extrapolate(np.nan_to_num(a), v, NS, n_iter=cfg["iter"], interp_order=0)
            tgt[:, ~np.isfinite(a)] = np.nan
        for k in range(NS):
            target = tgt[k] if cfg["mål"] == "flyttad" else a
            out[j, k] = verify.cdf_match(raw[k], target)
    return out


def location(obs, issues, fc, window=12, sigma=5.0, shrink=0.5, clip=6.0):
    """Platskartan som i model.location_map, ur variantens egna 30-minutersprognoser."""
    from scipy.ndimage import gaussian_filter

    out = {}
    shape = obs.shape[1:]
    for i in issues:
        num, den = np.zeros(shape), np.zeros(shape)
        for t in range(i - window + 1, i + 1):
            src = t - 6
            if src not in issues:
                continue
            f = fc[issues.index(src), 5]
            o = obs[t]
            ok = np.isfinite(f) & np.isfinite(o) & (f >= 0.5) & (o >= 0.5)
            num += np.where(ok, 10 * np.log10(np.where(ok, o, 1.0) / np.where(ok, f, 1.0)), 0.0)
            den += ok
        g = gaussian_filter(num, sigma) / (gaussian_filter(den, sigma) + shrink)
        out[i] = np.clip(g, -clip, clip).astype(np.float32)
    return out


class Scores:
    def __init__(self):
        self.c = defaultdict(lambda: np.zeros(4))
        self.fss = defaultdict(lambda: np.zeros(2))
        self.v = defaultdict(list)

    def add(self, k, f, o, o0, m, cs, t):
        ff, oo = np.where(m, f, 0.0), np.where(m, o, 0.0)
        for thr in (1.0, 5.0, 10.0):
            self.c[(k, thr)] += verify.contingency(ff[m], oo[m], thr)
            for sc in (5, 15):
                self.fss[(k, thr, sc)] += verify.fss_parts(ff, oo, thr, sc)
        vf, vo, v0 = ff[m].sum(), oo[m].sum(), np.where(m, o0, 0.0)[m].sum()
        self.v[(k, "volym")].append(np.log(max(vf, 1e-3) / max(vo, 1e-3)))
        qf, qo = np.quantile(ff[m], 0.999), np.quantile(oo[m], 0.999)
        self.v[(k, "q999")].append(np.log(max(qf, 0.05) / max(qo, 0.05)))
        if v0 > 0:
            self.v[(k, "dv_f")].append(np.log(max(vf, 1e-3) / v0))
            self.v[(k, "dv_o")].append(np.log(max(vo, 1e-3) / v0))
        tm = aspects.timing(f, cs, t, m)
        if tm is not None and tm[1]:
            self.v[(k, "tajming")].append(tm[0])

    def table(self):
        out = {}
        for k in EVAL:
            r = {}
            for thr in (1.0, 5.0, 10.0):
                s = verify.cat_scores(self.c[(k, thr)])
                r[f"ETS{thr:g}"] = s["ETS"]
                for sc in (5, 15):
                    num, den = self.fss[(k, thr, sc)]
                    r[f"FSS{thr:g}_{2 * sc}km"] = 1 - num / den if den else np.nan
            for name in ("volym", "q999"):
                r[name] = float(np.exp(np.mean(self.v[(k, name)]))) if self.v[(k, name)] else np.nan
            if self.v[(k, "tajming")]:
                r["tajming"] = float(np.median(self.v[(k, "tajming")]))
            if self.v[(k, "hopp")]:
                r["hopp"] = float(np.mean(self.v[(k, "hopp")]))
            a, b = np.array(self.v[(k, "dv_f")]), np.array(self.v[(k, "dv_o")])
            if len(a) > 3 and a.std() > 1e-6:
                r["avtagande_kor"] = float(np.corrcoef(a, b)[0, 1])
            out[k * 5] = r
        return out


def run_case(path, variants):
    cs = verify.Case(path)  # med OURS tomt laddas bara lk30 och obs
    z = np.load(path)
    motion = z["motion"]
    issues = cs.issues
    res = {}
    covs = {}
    for j, i in enumerate(issues):
        covs[i] = extrapolate(np.isfinite(cs.obs[i]).astype(np.float32), motion[j].astype(np.float32), NS, outval=0.0) > 0.99
    for name in variants:
        cfg = parse(name)
        fc = forecasts(cs.obs, issues, motion, cfg)
        corr = location(cs.obs, issues, fc) if cfg["plats"] else None
        sc = Scores()
        for j, i in enumerate(issues):
            # volymtrend: senaste halvtimmens förändring av hela områdets volym, dämpad med trend
            g = 1.0
            if cfg["trend"] and i >= 6:
                both = np.isfinite(cs.obs[i]) & np.isfinite(cs.obs[i - 6])
                v0, v1 = cs.obs[i][both].sum(), cs.obs[i - 6][both].sum()
                if v0 > 0 and v1 > 0:
                    g = float(np.clip(v0 / v1, 0.5, 2.0))
            for k in EVAL:
                t = i + k
                if t >= cs.n:
                    continue
                f = fc[j, k - 1]
                if corr is not None:
                    f = f * 10 ** (corr[i] * min(1.0, k / 6) / 10)
                if g != 1.0:
                    f = f * g ** (cfg["trend"] * k / 6)
                o = cs.obs[t]
                m = np.isfinite(f) & np.isfinite(o) & np.isfinite(cs.obs[i]) & covs[i][k - 1]
                if (o[m] >= 1.0).sum() < 50:
                    continue
                sc.add(k, f, o, cs.obs[i], m, cs, t)
        # hopp: samma giltighetstid från körningar med 15 minuters mellanrum, andel som byter status vid 1 mm/h
        for j, i in enumerate(issues):
            if i + 3 not in issues:
                continue
            jb = issues.index(i + 3)
            for k in (6, 9, 12):
                t = i + k
                if t >= cs.n:
                    continue
                fa, fb = fc[j, k - 1], fc[jb, k - 4]
                if corr is not None:
                    fa = fa * 10 ** (corr[i] * min(1.0, k / 6) / 10)
                    fb = fb * 10 ** (corr[i + 3] * min(1.0, (k - 3) / 6) / 10)
                m = np.isfinite(fa) & np.isfinite(fb) & covs[i][k - 1]
                a_, b_ = (fa >= 1.0) & m, (fb >= 1.0) & m
                u = np.sum(a_ | b_)
                if u:
                    sc.v[(k, "hopp")].append(np.sum(a_ ^ b_) / u)
        res[name] = sc
        print(f"{cs.name} {name}: klar", flush=True)
    return res


def pooled(per_case):
    """Slår ihop Scores över fall (summor för kontingens och FSS, listor för resten)."""
    tot = Scores()
    for sc in per_case:
        for k, v in sc.c.items():
            tot.c[k] += v
        for k, v in sc.fss.items():
            tot.fss[k] += v
        for k, v in sc.v.items():
            tot.v[k] += v
    return tot


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("gen", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--variants", nargs="*", default=["bas", "fart=1.1", "fart=1.2", "fart=1.3", "iter=3", "mål=flyttad"])
    p.add_argument("--cases", nargs="*")
    a = p.parse_args()
    verify.OURS[:] = []
    files = sorted(f for f in a.gen.glob("*.npz") if not f.stem.endswith("_ext"))
    if a.cases:
        files = [f for f in files if f.stem in a.cases]
    per_case = {}
    for f in files:
        per_case[f.stem] = run_case(f, a.variants)
    out = {"per_fall": {c: {v: sc.table() for v, sc in r.items()} for c, r in per_case.items()},
           "alla": {v: pooled([r[v] for r in per_case.values()]).table() for v in a.variants}}
    # ett fall utanför i taget: summan över de andra fallen
    out["utan"] = {c: {v: pooled([r[v] for cc, r in per_case.items() if cc != c]).table() for v in a.variants} for c in per_case}
    a.out.write_text(json.dumps(verify.clean(out), indent=1))
    print(f"skrev {a.out}")
