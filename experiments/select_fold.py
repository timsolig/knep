"""Väljer variant på en grupp fall och testar den på en annan (korsvalidering över fall).

Urval: bland våra varianter som klarar formkraven på urvalsgruppen, den med högst
medel av ETS vid 1 och 5 mm/h över horisonterna 15 till 60 min. Formkraven gäller
vid 30, 45 och 60 min och jämförs med KNEP-proxyn i samma grupp:

  textur        avvikelse från radarns högst 0,05 större än proxyns (log10 effekt i 4 till 16 km)
  bias 5 mm/h   mellan 0,7 och 1,4
  hoppighet     högst 10 procent över proxyns
  fram/tillbaka högst 25 procent över proxyns (45 och 60 min)

    python experiments/select_fold.py fold_fmi.json fold_mch.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REF = "knep_L10"
HS = ("15", "30", "45", "60")


def get(r, *path):
    for p in path:
        r = (r or {}).get(p)
    return r


def passes(sc, s):
    why = []
    for h in ("30", "45", "60"):
        x, k = sc[s][h], sc[REF][h]
        tex, ktex = x.get("texture"), k.get("texture")
        if tex is not None and ktex is not None and abs(tex) > abs(ktex) + 0.05:
            why.append(f"textur {tex:+.2f} vid {h}")
        b5 = get(x, "cat_5.0", "BIAS")
        if b5 is not None and not 0.7 <= b5 <= 1.4:
            why.append(f"bias5 {b5:.2f} vid {h}")
        j, kj = x.get("jump"), k.get("jump")
        if j is not None and kj and j > 1.10 * kj:
            why.append(f"hopp {j:.2f} vid {h}")
        f, kf = x.get("flipflop"), k.get("flipflop")
        if f is not None and kf and f > 1.25 * kf:
            why.append(f"fram/tillbaka {f:.2f} vid {h}")
    return why


def score(sc, s):
    v = [(get(sc[s][h], "cat_1.0", "ETS") + get(sc[s][h], "cat_5.0", "ETS")) / 2 for h in HS]
    return sum(v) / len(v)


def main(sel_path, test_path):
    sel, test = json.loads(Path(sel_path).read_text()), json.loads(Path(test_path).read_text())
    ss, ts = sel["operational"]["scores"], test["operational"]["scores"]
    ours = [s for s in ss if not s.startswith("knep") and s != "steps_ens"]
    print(f"Urval på {', '.join(sel['cases'])}, test på {', '.join(test['cases'])}\n")
    print("| Variant | Poäng | Formkrav |\n|---|---|---|")
    ok = []
    for s in ours:
        why = passes(ss, s)
        print(f"| {s} | {score(ss, s):.3f} | {'klarar' if not why else '; '.join(why)} |")
        if not why:
            ok.append(s)
    best = max(ok, key=lambda s: score(ss, s))
    print(f"\nVald: {best}\n")
    print("| Horisont | ETS 1 proxy | ETS 1 vald | ETS 5 proxy | ETS 5 vald | MCC 1 proxy | MCC 1 vald |\n|---|---|---|---|---|---|---|")
    for h in HS:
        k, x = ts[REF][h], ts[best][h]
        print(f"| {h} | {get(k, 'cat_1.0', 'ETS'):.3f} | {get(x, 'cat_1.0', 'ETS'):.3f} | {get(k, 'cat_5.0', 'ETS'):.3f} | "
              f"{get(x, 'cat_5.0', 'ETS'):.3f} | {get(k, 'cat_1.0', 'MCC'):.3f} | {get(x, 'cat_1.0', 'MCC'):.3f} |")
    return best


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
