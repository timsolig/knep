"""Tabellerna i markdown ur results/facit_a2t_varianter.json (uppgift 0006).

    uv run python experiments/projektion/facit_a2t_varianter_tabell.py
"""

from __future__ import annotations

import json
from pathlib import Path

R = json.loads((Path(__file__).resolve().parent / "results" / "facit_a2t_varianter.json").read_text())
VAR = ["kedja_utan_platskarta", "kedja_utan_matchning"]
FACIT = {"radar": "radarn (A0)", "a2t": "A2T", "matare": "mätarna (p7)"}


def f(x, n=3):
    return f"{x:.{n}f}".replace(".", ",").replace("-", "−")


def pick(d, i, idx):
    v = d[i]
    for k in idx:
        v = v[k]
    return v


MATT = [("CSI 1", "csi", (0,)), ("CSI 5", "csi", (1,)), ("FSS 1/10", "fss", (0, 0)), ("kvot", "kvot", ()),
        ("MAE", "mae", ())]


def cell(d, i, idx, n=3, stjarna=True):
    v, lo, hi = (pick(d[k], i, idx) for k in ("v", "lo", "hi"))
    star = " *" if stjarna and (lo > 0 or hi < 0) else ""
    return f"{f(v, n)} ({f(lo, n)} till {f(hi, n)}){star}"


def main():
    print(f"Dagar {len(R['dagar'])}, utgåvor {sum(R['utgavor'].values())}, B = {R['B']}\n")
    for fac, namn in FACIT.items():
        t = R["tabeller"][f"{fac}/alla"]
        print(f"### Facit {namn}, alla\n")
        print("| mått | system | +1 h | +2 h | +3 h | +4 h | +5 h |\n|---|---|---|---|---|---|---|")
        for lab, m, idx in MATT:
            if m not in t["kedja"]:
                continue
            for s in ["kedja", *VAR, "persistens"]:
                print(f"| {lab} | {s} | " + " | ".join(f(pick(t[s][m]['v'], i, idx)) for i in range(5)) + " |")
        print()
        for v in VAR:
            dd = t[f"{v}_minus_kedja"]
            print(f"| {v} − kedja | +1 h | +2 h | +3 h | +4 h | +5 h |\n|---|---|---|---|---|---|")
            for lab, m, idx in MATT:
                key = m
                if key not in dd:
                    continue
                print(f"| {lab} | " + " | ".join(cell(dd[key], i, idx) for i in range(5)) + " |")
            print()
    q = R["kvartar"]
    for src, lab in (("p14", "mot kvartsmätarna p14 (mm per kvart, mätarens ruta)"),
                     ("matarrutor", "mot radarns kvart i p14-mätarnas rutor"),
                     ("falt", "mot radarns kvart över hela fältet")):
        print(f"### Kvoten per kvart {lab}\n")
        print("| system | +15 min | +30 min | +45 min | +60 min |\n|---|---|---|---|---|")
        for s in (["radar"] if src == "p14" else []) + ["kedja", *VAR]:
            print(f"| {s} | " + " | ".join(cell(q[f"{src}/{s}"]["kvot"], j, (), stjarna=False) for j in range(4)) + " |")
        for v in VAR:
            print(f"| {v} − kedja | " + " | ".join(cell(q[f"{src}/{v}_minus_kedja"]["kvot"], j, ()) for j in range(4)) + " |")
        print(f"\nn per kvart: {q[f'{src}/kedja']['n']}\n")
    print("### Per dag, CSI 1 mm mot mätarna vid +1 h, och kvoten mot mätarna vid +1 h\n")
    sy = ["kedja", *VAR, "persistens"]
    print("| dag | " + " | ".join(f"CSI {s}" for s in sy) + " | " + " | ".join(f"kvot {s}" for s in sy) + " |")
    print("|---" * (1 + 2 * len(sy)) + "|")
    for d, e in R["per_dag"].items():
        m = e["matare"]
        print(f"| {d} | " + " | ".join(f(m[f'csi1_{s}'][0]) for s in sy) + " | "
              + " | ".join(f(m[f'kvot_{s}'][0], 2) for s in sy) + " |")


if __name__ == "__main__":
    main()
