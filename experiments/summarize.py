"""Skriver resultattabeller i markdown från verify.py:s json."""

from __future__ import annotations

import json
import sys
from pathlib import Path

BASE = {
    "knep": "KNEP-proxy", "knep_inst": "KNEP-proxy, momentan indata",
    "lk": "5 min, LK 15 min", "lk30": "5 min, LK 30 min", "ema": "5 min, utjämnad rörelse",
    "filt": "5 min, filtrerad analys", "sprog": "5 min, S-PROG", "steps": "5 min, STEPS-PMM",
    "steps_ens": "5 min, STEPS-ensemble", "oro": "5 min, platskorrigerad",
    "cdf": "5 min, fördelningsmatchad", "oro_cdf": "5 min, matchad och platskorrigerad",
    "lag": "5 min, medel av tre körningar", "lagr": "5 min, medel av tre körningar med ramp",
    "ext": "5 min, tränad extremkalibrering", "exth": "5 min, tränad extremkalibrering, halv vikt",
}
OURS = ["lk", "lk30", "ema", "filt", "cdf", "oro", "oro_cdf", "ext", "exth", "lag", "lagr", "sprog", "steps", "steps_ens"]


def name(s):
    if "_L" in s:
        b, L = s.rsplit("_L", 1)
        return f"{BASE.get(b, b)} ({L} min)"
    return BASE.get(s, s)


COLS = [
    ("ETS 1", lambda r: r.get("cat_1.0", {}).get("ETS")),
    ("ETS 5", lambda r: r.get("cat_5.0", {}).get("ETS")),
    ("MCC 1", lambda r: r.get("cat_1.0", {}).get("MCC")),
    ("MCC 5", lambda r: r.get("cat_5.0", {}).get("MCC")),
    ("FSS 1/10km", lambda r: r.get("FSS_1.0_10km")),
    ("FSS 5/10km", lambda r: r.get("FSS_5.0_10km")),
    ("Bias 1", lambda r: r.get("cat_1.0", {}).get("BIAS")),
    ("Bias 5", lambda r: r.get("cat_5.0", {}).get("BIAS")),
    ("Textur", lambda r: r.get("texture")),
    ("SAL S", lambda r: r.get("SAL_S")),
    ("SAL A", lambda r: r.get("SAL_A")),
    ("SAL L", lambda r: r.get("SAL_L")),
    ("Hopp", lambda r: r.get("jump")),
    ("Fram och tillbaka", lambda r: r.get("flipflop")),
    ("CRPS/MAE", lambda r: r.get("CRPS")),
]
COLS_EXT = [
    ("ETS 10", lambda r: r.get("cat_10.0", {}).get("ETS")),
    ("ETS 20", lambda r: r.get("cat_20.0", {}).get("ETS")),
    ("SEDI 5", lambda r: r.get("cat_5.0", {}).get("SEDI")),
    ("SEDI 10", lambda r: r.get("cat_10.0", {}).get("SEDI")),
    ("SEDI 20", lambda r: r.get("cat_20.0", {}).get("SEDI")),
    ("POD 10", lambda r: r.get("cat_10.0", {}).get("POD")),
    ("FAR 10", lambda r: r.get("cat_10.0", {}).get("FAR")),
    ("Bias 10", lambda r: r.get("cat_10.0", {}).get("BIAS")),
    ("Bias 20", lambda r: r.get("cat_20.0", {}).get("BIAS")),
    ("FSS 10/10km", lambda r: r.get("FSS_10.0_10km")),
    ("FSS 10/30km", lambda r: r.get("FSS_10.0_30km")),
    ("Topp q99", lambda r: r.get("TAIL99")),
    ("Topp q99,9", lambda r: r.get("TAIL999")),
]


def fmt(x):
    return "" if x is None else f"{x:.2f}" if abs(x) >= 0.01 or x == 0 else f"{x:.3f}"


def table(scores, h, systems, cols=None):
    cols = cols or COLS
    head = "| System | " + " | ".join(c for c, _ in cols) + " |"
    sep = "|---" * (len(cols) + 1) + "|"
    rows = [head, sep]
    for s in systems:
        r = scores.get(s, {}).get(str(h))
        if r is None:
            continue
        rows.append(f"| {name(s)} | " + " | ".join(fmt(f(r)) for _, f in cols) + " |")
    return "\n".join(rows) + "\n\nExtremer:\n\n" + (_ext(scores, h, systems) if cols is COLS else "")


def _ext(scores, h, systems):
    head = "| System | " + " | ".join(c for c, _ in COLS_EXT) + " |"
    sep = "|---" * (len(COLS_EXT) + 1) + "|"
    rows = [head, sep]
    for s in systems:
        r = scores.get(s, {}).get(str(h))
        if r is None:
            continue
        rows.append(f"| {name(s)} | " + " | ".join(fmt(f(r)) for _, f in COLS_EXT) + " |")
    return "\n".join(rows)


def main(path):
    res = json.loads(Path(path).read_text())
    print(f"Fall: {', '.join(res['cases'])}\n")
    ours = OURS
    if "operational" in res:
        op = res["operational"]
        knep = [f"{b}_L{int(L)}" for L in op["latencies"] for b in ("knep", "knep_inst")]
        print("## Användarperspektiv (KNEP-proxyns fördröjning inom parentes)\n")
        for h in (15, 30, 45, 60):
            print(f"### {h} min framåt\n")
            print(table(op["scores"], h, knep + ours) + "\n")
        print("Skillnad mot KNEP-proxy (5, 50, 95 percentil; andel bootstrap > 0):\n")
        print("| System | Mot | Horisont | Tröskel | Mått | 5 % | median | 95 % | P(>0) |\n|---|---|---|---|---|---|---|---|---|")
        for k, (lo, med, hi, p) in sorted(op["bootstrap"].items()):
            s, ref, h, thr, sc = k.split("|")
            print(f"| {name(s)} | {name(ref)} | {h} | {thr} | {sc} | {lo:+.3f} | {med:+.3f} | {hi:+.3f} | {p:.2f} |")
        print()
    if "operational_inst" in res:
        lats = res.get("operational", {}).get("latencies", [5, 10, 15, 20])
        knep = [f"{b}_L{int(L)}" for L in lats for b in ("knep", "knep_inst")]
        print("## Användarperspektiv på 5-minutersupplösning (momentan radar som facit)\n")
        for h in (15, 30, 45, 60):
            print(f"### {h} min framåt\n")
            print(table(res["operational_inst"], h, knep + ours) + "\n")
    if "per_case" in res or "operational_per_case" in res:
        pc = res.get("operational_per_case", {})
        for h in ("30", "60"):
            print(f"## Per fall, ETS och MCC vid 1 och 5 mm/h, {h} min framåt\n")
            print("| Fall | System | ETS 1 | ETS 5 | MCC 1 | MCC 5 |\n|---|---|---|---|---|---|")
            for c, ss in pc.items():
                for s in ("knep_L5", "knep_L10", "knep_L15", "lk", "lk30", "oro", "oro_cdf", "sprog", "steps"):
                    r = ss.get(s, {}).get(h)
                    if r:
                        print(f"| {c} | {name(s)} | {fmt(r['ETS1'])} | {fmt(r['ETS5'])} | {fmt(r['MCC1'])} | {fmt(r['MCC5'])} |")
            print()
    if "algorithmic" in res:
        print("## Algoritm, samma kvartsanalyser, ingen fördröjning\n")
        for h in (15, 30, 45, 60):
            print(f"### {h} min ledtid\n")
            print(table(res["algorithmic"], h, ["knep", "knep_inst"] + ours) + "\n")
    if "variants_inst" in res:
        print("## Våra varianter, momentan 5-minutersverifiering\n")
        for h in (5, 15, 30, 60):
            print(f"### {h} min ledtid\n")
            print(table(res["variants_inst"], h, ours) + "\n")


if __name__ == "__main__":
    main(sys.argv[1])
