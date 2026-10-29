"""Aspektmått per ledtid: tajming, volym, intensitet, spridning och avtagande.

Varje mått skiljer ut en egenskap hos prognosen, så att det syns var en ändring vinner och var
den förlorar. Momentana 5-minutersfält mot radarn vid giltighetstiden, gemensam yta för alla system.

  tajming     vilken radarbild runt giltighetstiden prognosen liknar mest (korrelation i dB efter
              lätt utjämning, parabel genom toppen). Positivt = prognosen ligger före, negativt = efter.
  volym       summan av nederbörd i prognosen mot radarn (kvot, geometriskt medel över körningarna)
  intensitet  99- och 99,9-percentilen och medelintensiteten där det regnar minst 0,5 mm/h (kvoter)
  spridning   våt yta över 0,5 och 5 mm/h (kvoter) och minsta skala där FSS för 1 mm/h är användbar
  avtagande   volymens förändring från analysen till giltighetstiden, prognos mot radar:
              korrelationen över körningarna (fångas tillväxt och avtagande alls?) och kvoten

Persistens (analysen står still) är med som referens för tajming och avtagande.

    python experiments/aspects.py GEN --out aspekter.json [--systems lk30 oro_cdf ext sprog]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from pysteps.extrapolation.semilagrangian import extrapolate
from scipy.ndimage import gaussian_filter, uniform_filter

sys.path.insert(0, str(Path(__file__).parent))
import verify  # noqa: E402

LEADS = range(1, 13)  # 5-minuterssteg
SCALES = [1, 3, 5, 9, 15, 25, 41]  # pixlar à 2 km för FSS-skalan
SHIFTS = range(-4, 5)  # radarbilder runt giltighetstiden för tajmingen


def _db(x):
    return 10 * np.log10(np.maximum(x, 0.1))


def timing(f, cs, t, mask):
    """Förskjutning i minuter (positivt = prognosen före) och om toppen är tydlig."""
    g = gaussian_filter(_db(np.where(mask, f, 0.0)), 1.5)[mask]
    g = g - g.mean()
    cor = []
    for s in SHIFTS:
        u = t + s
        if not 0 <= u < cs.n:
            cor.append(np.nan)
            continue
        o = cs.obs[u]
        m = np.isfinite(o)
        h = gaussian_filter(_db(np.where(mask & m, o, 0.0)), 1.5)[mask]
        h = h - h.mean()
        den = np.sqrt((g * g).sum() * (h * h).sum())
        cor.append((g * h).sum() / den if den else np.nan)
    cor = np.array(cor)
    if not np.isfinite(cor).any():
        return None
    j = int(np.nanargmax(cor))
    if j in (0, len(cor) - 1) or not np.isfinite(cor[j - 1]) or not np.isfinite(cor[j + 1]):
        return None  # toppen ligger på kanten: ingen säker skattning
    a, b, c = cor[j - 1], cor[j], cor[j + 1]
    d = 0.5 * (a - c) / (a - 2 * b + c) if (a - 2 * b + c) < 0 else 0.0
    sharp = b - np.nanmin(cor) > 0.02
    return (SHIFTS[j] + d) * 5.0, sharp


class Agg:
    def __init__(self):
        self.v = defaultdict(list)
        self.fss = defaultdict(lambda: np.zeros(2))
        self.fo = defaultdict(list)

    def table(self):
        out = {}
        for (s, k, name), vals in self.v.items():
            out.setdefault(s, {}).setdefault(k * 5, {})[name] = vals
        res = {}
        for s, ks in out.items():
            res[s] = {}
            for lead, d in ks.items():
                r = {}
                for name in ("volym", "q99", "q999", "medel", "yta05", "yta5"):
                    if name in d:
                        r[name] = float(np.exp(np.nanmean(d[name])))
                if "tajming" in d:
                    t = np.array(d["tajming"])
                    r["tajming"] = float(np.median(t))
                    r["tajming_abs"] = float(np.median(np.abs(t)))
                if "dv_f" in d:
                    a, b = np.array(d["dv_f"]), np.array(d["dv_o"])
                    ok = np.isfinite(a) & np.isfinite(b)
                    r["avtagande_kor"] = float(np.corrcoef(a[ok], b[ok])[0, 1]) if ok.sum() > 3 and a[ok].std() > 1e-6 else None
                    r["avtagande_f"] = float(np.exp(np.mean(a[ok])))
                    r["avtagande_o"] = float(np.exp(np.mean(b[ok])))
                # FSS-skala: minsta skala där FSS ≥ 0,5 + f0/2
                f0 = np.mean(self.fo[(s, lead // 5)]) if self.fo[(s, lead // 5)] else 0.0
                useful = 0.5 + f0 / 2
                fss = {}
                for sc in SCALES:
                    num, den = self.fss[(s, lead // 5, sc)]
                    fss[sc] = 1 - num / den if den else np.nan
                ok = [sc for sc in SCALES if fss[sc] >= useful]
                r["fss_skala_km"] = float(2 * ok[0]) if ok else None
                r["fss_1_10km"] = float(fss[5])
                res[s][lead] = r
        return res


def run_case(path, systems, agg):
    cs = verify.Case(path)
    motion = np.load(path)["motion"]
    for j, i in enumerate(cs.issues):
        o0 = cs.obs[i]
        # bara pixlar vars bana bakåt börjar inom täckningen: annars saknar alla prognoser inflödet
        # och tajmingen drar mot för sent
        cov = extrapolate(np.isfinite(o0).astype(np.float32), motion[j].astype(np.float32), max(LEADS), outval=0.0)
        for k in LEADS:
            t = i + k
            if t >= cs.n:
                continue
            fields = {s: cs.inst(s, i, t) for s in systems if s != "pers"}
            if any(f is None for f in fields.values()):
                continue
            if "pers" in systems:
                fields["pers"] = o0
            o = cs.obs[t]
            m = verify.common_mask(fields, o) & np.isfinite(o0) & (cov[k - 1] > 0.99)
            if (o[m] >= 1.0).sum() < 50:
                continue
            oo = o[m]
            vo, vo0 = oo.sum(), o0[m].sum()
            qo = np.quantile(oo, [0.99, 0.999])
            wo05, wo5 = (oo >= 0.5).sum(), (oo >= 5.0).sum()
            for s, f in fields.items():
                ff = f[m]
                vf = ff.sum()
                add = lambda name, x: agg.v[(s, k, name)].append(x)
                add("volym", np.log(max(vf, 1e-3) / max(vo, 1e-3)))
                qf = np.quantile(ff, [0.99, 0.999])
                add("q99", np.log(max(qf[0], 0.05) / max(qo[0], 0.05)))
                add("q999", np.log(max(qf[1], 0.05) / max(qo[1], 0.05)))
                if wo05 and (ff >= 0.5).sum():
                    add("medel", np.log(ff[ff >= 0.5].mean() / oo[oo >= 0.5].mean()))
                if wo05:
                    add("yta05", np.log(((ff >= 0.5).sum() + 1) / (wo05 + 1)))
                if wo5 >= 20:
                    add("yta5", np.log(((ff >= 5.0).sum() + 1) / (wo5 + 1)))
                if vo0 > 0:
                    add("dv_f", np.log(max(vf, 1e-3) / vo0))
                    add("dv_o", np.log(max(vo, 1e-3) / vo0))
                if k in (3, 6, 12):
                    tm = timing(f, cs, t, m)
                    if tm is not None and tm[1]:
                        add("tajming", tm[0])
                fz, oz = np.where(m, f, 0.0), np.where(m, o, 0.0)
                a, b = (fz >= 1.0).astype(np.float32), (oz >= 1.0).astype(np.float32)
                agg.fo[(s, k)].append(b[m].mean())
                for sc in SCALES:
                    if sc > 1:
                        aa, bb = uniform_filter(a, sc, mode="constant"), uniform_filter(b, sc, mode="constant")
                    else:
                        aa, bb = a, b
                    agg.fss[(s, k, sc)] += np.array([np.sum((aa - bb) ** 2), np.sum(aa**2) + np.sum(bb**2)])
    print(f"{cs.name}: klar", flush=True)


def markdown(res, systems, names):
    lines = []
    cols = [("tajming", "Tajming min"), ("tajming_abs", "Tajming abs"), ("volym", "Volym"), ("medel", "Medelint."),
            ("q99", "Q99"), ("q999", "Q99,9"), ("yta05", "Yta 0,5"), ("yta5", "Yta 5"), ("fss_skala_km", "FSS-skala km"),
            ("avtagande_kor", "Avtag. kor"), ("avtagande_f", "Avtag. prognos"), ("avtagande_o", "Avtag. radar")]
    for lead in (15, 30, 60):
        lines += [f"### {lead} min", "", "| System | " + " | ".join(c[1] for c in cols) + " |", "|---" * (len(cols) + 1) + "|"]
        for s in systems:
            r = res.get(s, {}).get(lead, {})
            cells = []
            for key, _ in cols:
                v = r.get(key)
                cells.append("" if v is None else f"{v:.2f}" if key != "fss_skala_km" else f"{v:.0f}")
            lines.append(f"| {names.get(s, s)} | " + " | ".join(cells) + " |")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("gen", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--systems", nargs="*", default=["pers", "lk30", "oro_cdf", "ext", "sprog"])
    p.add_argument("--cases", nargs="*")
    a = p.parse_args()
    verify.OURS[:] = [s for s in a.systems if s != "pers"]
    files = sorted(f for f in a.gen.glob("*.npz") if not f.stem.endswith("_ext"))
    if a.cases:
        files = [f for f in files if f.stem in a.cases]
    agg = Agg()
    for f in files:
        run_case(f, a.systems, agg)
    res = {"cases": [f.stem for f in files], "aspects": agg.table()}
    a.out.write_text(json.dumps(verify.clean(res), indent=1))
    names = {"pers": "Persistens", "lk30": "LK 30 min", "oro_cdf": "Kedjan utan extremkalibrering",
             "ext": "Kedjan", "exth": "Kedjan, halv kalibrering", "sprog": "S-PROG"}
    a.out.with_suffix(".md").write_text(markdown(res["aspects"], a.systems, names))
    print(f"skrev {a.out}")
