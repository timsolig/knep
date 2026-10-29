"""Simulerat radarbortfall: hur mycket räddar den lagrangeska utfyllnaden i kompositen?

I varje fall slocknar en radar i en timme: en skiva med radien 100 km kring den mest
regniga platsen saknar data. Tre system jämförs mot den riktiga radarn:

  hel    ingen störning (övre gräns)
  hål    bortfallet lämnas som saknad data, som i en komposit utan reserv
  fylld  hålet fylls med composite.fill_gaps, alltså förra analysen flyttad med rörelsen
  utjämnad  som fylld men utjämnad mer ju äldre den är (med --smooth)

Prognoserna är kedjans kärna (Lucas-Kanade på 30 min, extrapolering, fördelningsmatchning),
från mitten av bortfallet till en halvtimme efter att radarn kommit tillbaka.

    python experiments/outage.py <gen> --out outage.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from pysteps.extrapolation.semilagrangian import extrapolate
from scipy.ndimage import gaussian_filter, uniform_filter

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from generate import LK, db, decode, quiet  # noqa: E402
from verify import cat_scores, cdf_match, contingency  # noqa: E402

from knep import composite  # noqa: E402

RADIUS, START, LENGTH = 50, 10, 12  # pixlar à 2 km, bild, antal bilder (5 min)
SMOOTH = False  # --smooth: även utfyllnad som jämnas ut med åldern
LEADS = (3, 6, 12)


def forecast(frames, steps=12):
    v = quiet(LK, db(frames))
    last = np.nan_to_num(frames[-1])
    fc = extrapolate(last, v, steps)
    fc = np.stack([cdf_match(f, frames[-1]) for f in fc])
    fc[:, ~np.isfinite(frames[-1])] = np.nan
    return fc


def run_case(path: Path):
    d = np.load(path)
    obs = decode(d["obs"])
    n, h, w = obs.shape
    wet = gaussian_filter(np.nansum(obs[START : START + 30] >= 1.0, axis=0).astype(float), 10)
    cy, cx = np.unravel_index(np.argmax(wet), wet.shape)
    yy, xx = np.mgrid[0:h, 0:w]
    disc = (yy - cy) ** 2 + (xx - cx) ** 2 <= RADIUS**2
    near = (yy - cy) ** 2 + (xx - cx) ** 2 <= (RADIUS + 40) ** 2
    out_frames = range(START, START + LENGTH)

    holed = obs.copy()
    for t in out_frames:
        holed[t][disc] = np.nan
    # utfylld analys bild för bild, som i driften: rörelsen från de senaste 30 min av redan fyllda bilder
    def fill(smooth):
        out = np.empty_like(obs)
        state, src = None, np.zeros((h, w), np.uint8)
        for t in range(n):
            motion = quiet(LK, db(out[max(0, t - 7) : t])) if t >= 3 else None
            rain, _, _, state = composite.fill_gaps(holed[t], src, state, motion, smooth=smooth)
            out[t] = rain
        return out

    filled = fill(False)
    seqs = [("hel", obs), ("hål", holed), ("fylld", filled)]
    if SMOOTH:
        seqs.append(("utjämnad", fill(True)))

    acc = {}
    def add(system, region, local, k, f, o):
        m = np.isfinite(o) & region
        f = np.where(np.isfinite(f), f, 0.0)[m]  # saknad prognos syns som inget regn
        o = o[m]
        a = acc.setdefault((system, local, k), {"c": {t: np.zeros(4) for t in (1.0, 5.0, 10.0)}, "fss": np.zeros(2), "mae": []})
        for t in a["c"]:
            a["c"][t] += contingency(f, o, t)
        a["mae"].append(float(np.mean(np.abs(f - o))))

    issues = range(START + LENGTH // 2, min(START + LENGTH + 6, n - max(LEADS)))
    for i in issues:
        for name, seq in seqs:
            fc = forecast(seq[i - 6 : i + 1])
            for k in LEADS:
                for region, local in ((near, True), (np.ones_like(near), False)):
                    add(name, region, local, k, fc[k - 1], obs[i + k])
                # FSS 5 mm/h på 10 km nära bortfallet
                f = np.where(np.isfinite(fc[k - 1]), fc[k - 1], 0.0)
                o = np.nan_to_num(obs[i + k])
                a, b = uniform_filter((f >= 5).astype(float) * near, 5), uniform_filter((o >= 5).astype(float) * near, 5)
                acc[(name, True, k)]["fss"] += [np.sum((a - b) ** 2), np.sum(a**2) + np.sum(b**2)]
    # analysens kvalitet i hålet under bortfallet
    ana = {}
    for name, seq in seqs[1:]:
        c = {t: np.zeros(4) for t in (1.0, 5.0)}
        for t in out_frames:
            f = np.where(np.isfinite(seq[t]), seq[t], 0.0)[disc & np.isfinite(obs[t])]
            o = obs[t][disc & np.isfinite(obs[t])]
            for thr in c:
                c[thr] += contingency(f, o, thr)
        ana[name] = {f"ETS{int(t)}": cat_scores(v)["ETS"] for t, v in c.items()}
    res = {}
    for (s, local, k), a in acc.items():
        r = res.setdefault(s, {}).setdefault("nära" if local else "hela", {})[str(k * 5)] = {
            f"ETS{int(t)}": cat_scores(c)["ETS"] for t, c in a["c"].items()}
        r["SEDI10"] = cat_scores(a["c"][10.0])["SEDI"]
        r["MAE"] = float(np.mean(a["mae"]))
        if local:
            num, den = a["fss"]
            r["FSS5_10km"] = 1 - num / den if den else None
    return {"centrum": [int(cy), int(cx)], "prognoser": res, "analys": ana}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("gen", type=Path)
    ap.add_argument("--out", type=Path, default=Path("outage.json"))
    ap.add_argument("--smooth", action="store_true")
    ap.add_argument("--cases", nargs="*")
    a = ap.parse_args()
    SMOOTH = a.smooth
    out = {}
    for p in sorted(x for x in a.gen.glob("*.npz") if not x.stem.endswith("_ext") and (not a.cases or x.stem in a.cases)):
        out[p.stem] = run_case(p)
        print(p.stem, json.dumps(out[p.stem]["analys"]), flush=True)
    a.out.write_text(json.dumps(out, indent=1, default=lambda x: None if x != x else x))
    print(f"skrev {a.out}")
