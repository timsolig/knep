"""Sammanställer extremresultaten: verifiering av kartorna och av sannolikheterna.

    python experiments/summarize_ext.py res_ext.json prob.json outage.json > results/extremer.md
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SYS = [("knep_L10", "KNEP-proxy"), ("oro_cdf", "Kedjan"), ("exth", "Kedjan, halv kalibrering"),
       ("ext", "Kedjan, extremkalibrerad"), ("sprog", "S-PROG")]


def g(r, *p):
    for k in p:
        r = (r or {}).get(k)
    return r


def f(x, d=2):
    return "" if x is None else f"{x:.{d}f}".replace(".", ",").replace("-", "−")


def maps(res, key, title):
    sc = res[key]
    print(f"## {title}\n")
    cols = [("ETS 5", ("cat_5.0", "ETS")), ("ETS 10", ("cat_10.0", "ETS")), ("ETS 20", ("cat_20.0", "ETS")),
            ("SEDI 5", ("cat_5.0", "SEDI")), ("SEDI 10", ("cat_10.0", "SEDI")), ("SEDI 20", ("cat_20.0", "SEDI")),
            ("Bias 10", ("cat_10.0", "BIAS")), ("Bias 20", ("cat_20.0", "BIAS")), ("FSS 10/30 km", ("FSS_10.0_30km",)),
            ("Topp q99,9", ("TAIL999",)), ("ETS 1", ("cat_1.0", "ETS")), ("Textur", ("texture",))]
    for h in ("15", "30", "45", "60"):
        print(f"### {h} min\n")
        print("| System | " + " | ".join(c for c, _ in cols) + " |")
        print("|---" * (len(cols) + 1) + "|")
        for s, name in SYS:
            r = sc.get(s, {}).get(h)
            if r:
                print(f"| {name} | " + " | ".join(f(g(r, *p)) for _, p in cols) + " |")
        print()


def probs(prob):
    print("## Sannolikheter mot momentan radar\n")
    print("Brier skill score mot händelsens egen klimatologi (1 är perfekt, 0 som klimatologin), ROC-yta och kvoten mellan summerad sannolikhet och antal observerade.\n")
    for t in ("5.0", "10.0"):
        print(f"### Minst {t[:-2]} mm/h\n")
        print("| System | " + " | ".join(f"BSS {L}" for L in ("15", "30", "45", "60")) + " | " + " | ".join(f"AUC {L}" for L in ("15", "30", "60")) + " | Kvot 30 |")
        print("|---" * 9 + "|")
        for s in ("tränad", "grannskap 30 km", "grannskap 14 km", "kedjan ja/nej"):
            r = prob.get(s, {})
            bss = [f(g(r, L, t, "BSS")) for L in ("15", "30", "45", "60")]
            auc = [f(g(r, L, t, "AUC")) for L in ("15", "30", "60")]
            print(f"| {s} | " + " | ".join(bss) + " | " + " | ".join(auc) + f" | {f(g(r, '30', t, 'kvot'))} |")
        print()
    print("### Tillförlitlighet för minst 10 mm/h vid 30 min (tränad)\n")
    print("| Prognos | Observerat | Antal |\n|---|---|---|")
    for p, o, n in g(prob, "tränad", "30", "10.0", "tillforlitlighet") or []:
        print(f"| {f(p)} | {f(o)} | {n} |")
    print()


def outage(out):
    print("## Simulerat radarbortfall, 100 km radie i 60 min\n")
    print("Prognoser från mitten av bortfallet till 30 min efter, nära bortfallet. Analysens ETS i hålet under bortfallet.\n")
    print("| Fall | Analys ETS 1, hål | Analys ETS 1, fylld | ETS 1 30 min: hel · hål · fylld | ETS 5 30 min: hel · hål · fylld | FSS 5 30 min: hel · hål · fylld |")
    print("|---|---|---|---|---|---|")
    for c, r in out.items():
        p = r["prognoser"]
        def tri(m):
            return " · ".join(f(g(p, s, "nära", "30", m)) for s in ("hel", "hål", "fylld"))
        print(f"| {c} | {f(g(r, 'analys', 'hål', 'ETS1'))} | {f(g(r, 'analys', 'fylld', 'ETS1'))} | {tri('ETS1')} | {tri('ETS5')} | {tri('FSS5_10km')} |")
    print()


if __name__ == "__main__":
    res = json.loads(Path(sys.argv[1]).read_text())
    prob = json.loads(Path(sys.argv[2]).read_text())
    out = json.loads(Path(sys.argv[3]).read_text()) if len(sys.argv) > 3 and Path(sys.argv[3]).exists() else None
    print(f"Fall: {', '.join(res['cases'])}\n")
    maps(res["operational"], "scores", "Kartor, användarperspektiv, 15-minuters medelintensitet")
    maps({"x": res["operational_inst"]}, "x", "Kartor, användarperspektiv, momentan radar var 5:e minut")
    probs(prob)
    if out:
        outage(out)
