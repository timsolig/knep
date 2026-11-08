"""Sammanställningen för uppgift 0009 (domaren med kvot våt): kvot summa och kvot våt per system,
upplösning och delmängd, och domarna med den nya och den gamla regeln ur tabellfilerna.

    uv run python experiments/analys/vat_kvot.py A0 A1 A2T F4 F1 --jmf A1:A0 A2T:A0 A2T:A1 F4:A0 F1:A0

Läser bara dagfilerna och tabellerna i domarens katalog (standard /data/analys/domare_v2/) på
valideringen. Testdelen läses aldrig (domare.days kontrollerar det).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if "analys_domare" not in sys.modules:
    _spec = importlib.util.spec_from_file_location("analys_domare", HERE / "domare.py")
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules["analys_domare"] = _mod
    _spec.loader.exec_module(_mod)
D = sys.modules["analys_domare"]


def fmt(x: float, d: int = 3) -> str:
    return f"{x:.{d}f}".replace(".", ",")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("system", nargs="+")
    p.add_argument("--jmf", nargs="*", default=[], help="system:bas, tabellen måste finnas")
    p.add_argument("--del", dest="del_", default="validering", choices=["validering", "traning"])
    p.add_argument("--ut")
    a = p.parse_args()
    D.set_out(a.ut)
    print("| system | dagar | upplösning | delmängd | kvot summa | kvot våt |")
    print("|---|---|---|---|---|---|")
    for s in a.system:
        r = D.load_results(s, a.del_)
        if not r:
            continue
        tot = D._sum(list(r.values()))
        for res in ("kvart", "timme"):
            for sub in D.SUBSETS:
                m = D.metrics(tot[f"{res}/{sub}"], res)
                print(f"| {s} | {len(r)} | {res} | {sub} | {fmt(m['kvot summa'][0])} | {fmt(m['kvot våt'][0])} |")
    for j in a.jmf:
        s, b = j.split(":")
        path = D.OUT / f"tabell_{s}_mot_{b}_{a.del_}.json"
        if not path.exists():
            print(f"\n{s} mot {b}: tabellen saknas")
            continue
        t = json.loads(path.read_text())
        print(f"\n### {s} mot {b} ({len(t['dagar'])} dagar)\n")
        for k, lab in (("dom", "ny regel (kvot våt)"), ("dom_gammal_regel", "gammal regel (kvot summa)")):
            v = t[k]
            print(f"- {lab}: {'bättre' if v['battre'] else 'inte bättre'}; bättre i {', '.join(v['battre_i']) or 'inget'}; "
                  f"sämre i {', '.join(v['samre_i']) or 'inget'}")
        print("\n| delmängd | mått | system | bas | skillnad i godhet (95 %) |\n|---|---|---|---|---|")
        for res in ("kvart", "timme"):
            for sub in D.SUBSETS:
                for name in ("kvot summa", "kvot våt"):
                    row = t["tabell"][f"{res}/{sub}"][name]
                    print(f"| {res} {sub} | {name} | {fmt(row['varde'])} | {fmt(row['bas'])} | "
                          f"{row['diff']:+.3f} ({row['lo']:+.3f} till {row['hi']:+.3f}) |".replace(".", ","))


if __name__ == "__main__":
    main()
