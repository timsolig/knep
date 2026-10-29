"""Tabeller ur tune_chain.py: alla fall ihop, och val med ett fall utanför i taget.

Första varianten är basen. Valet görs på de andra fallens poäng (medel av ETS 1, ETS 5 och FSS 5 mm/h på 30 km vid 30 och
60 min) och redovisas på det utelämnade fallet mot basvarianten.

    python experiments/summarize_tune.py tune_chain.json > results/kedjevarianter.md
"""

import json
import sys

KEYS = [("ETS1", "ETS 1"), ("ETS5", "ETS 5"), ("ETS10", "ETS 10"), ("FSS5_30km", "FSS 5/30 km"), ("FSS10_30km", "FSS 10/30 km"),
        ("volym", "Volym"), ("q999", "Q99,9"), ("tajming", "Tajming min"), ("avtagande_kor", "Avtag. kor"), ("hopp", "Hopp")]


def score(t):
    vals = [t[h][k] for h in ("30", "60") for k in ("ETS1", "ETS5", "FSS5_30km") if t[h].get(k) is not None]
    return sum(vals) / len(vals)


def fmt(v, key):
    if v is None:
        return ""
    return f"{v:.1f}" if key == "tajming" else f"{v:.3f}"


def main(path):
    d = json.load(open(path))
    variants = list(d["alla"])
    print(f"Fall: {', '.join(d['per_fall'])}\n")
    print("## Alla fall\n")
    for h in ("15", "30", "45", "60"):
        print(f"### {h} min\n")
        print("| Variant | " + " | ".join(k[1] for k in KEYS) + " |")
        print("|---" * (len(KEYS) + 1) + "|")
        for v in variants:
            t = d["alla"][v][h]
            print(f"| {v} | " + " | ".join(fmt(t.get(k), k) for k, _ in KEYS) + " |")
        print()
    print("## Ett fall utanför i taget\n")
    print("Vald variant på de andra fallen, poäng (medel av ETS 1, ETS 5 och FSS 5/30 km vid 30 och 60 min) på det utelämnade fallet.\n")
    print("| Utelämnat | Vald | Poäng bas | Poäng vald | ETS 1 60 bas | ETS 1 60 vald | Tajming 60 bas | Tajming 60 vald |")
    print("|---|---|---|---|---|---|---|---|")
    for case, tabs in d["utan"].items():
        best = max(variants, key=lambda v: score(tabs[v]))
        own = d["per_fall"][case]
        b, c = own[variants[0]], own[best]  # första varianten är basen
        print(f"| {case} | {best} | {score(b):.3f} | {score(c):.3f} | {b['60']['ETS1']:.3f} | {c['60']['ETS1']:.3f} | "
              f"{fmt(b['60'].get('tajming'), 'tajming')} | {fmt(c['60'].get('tajming'), 'tajming')} |")
    print("\n## Per fall, poäng\n")
    print("| Fall | " + " | ".join(variants) + " |")
    print("|---" * (len(variants) + 1) + "|")
    for case, tabs in d["per_fall"].items():
        print(f"| {case} | " + " | ".join(f"{score(tabs[v]):.3f}" for v in variants) + " |")


if __name__ == "__main__":
    main(sys.argv[1])
