"""Per dag: hur mycket F4 tar bort vid mätarna jämfört med A0 (uppgift 0011, diagnos).

    uv run python experiments/analys/f4_dagar.py [--del traning] [--nyckel timme/over400]

Skriver för varje dag i delen Σanalys vid våta mätare (saw) och vid alla mätare (sa) för A0 och
F4 och skillnaden, ur dagfilerna i /data/analys/domare_v2/. Räknar inget nytt och ändrar inget.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("analys_domare", HERE / "domare.py")
domare = importlib.util.module_from_spec(_spec)
sys.modules["analys_domare"] = domare
_spec.loader.exec_module(domare)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--del", dest="del_", default="traning", choices=["validering", "traning"])
    p.add_argument("--nyckel", nargs="+", default=["timme/over400", "kvart/over400", "timme/alla"])
    a = p.parse_args()
    s, b = domare.load_results("F4", a.del_), domare.load_results("A0", a.del_)
    for k in a.nyckel:
        print(f"\n{k}: dag, sgw (mätare våt), saw A0, saw F4 − A0, sa F4 − A0 (mm)")
        tot = 0.0
        for d in sorted(set(s) & set(b)):
            x, y = s[d][k], b[d][k]
            dw, ds = x["saw"] - y["saw"], x["sa"] - y["sa"]
            tot += dw
            if dw or ds:
                print(f"  {d}  {y['sgw']:8.1f}  {y['saw']:8.1f}  {dw:+8.3f}  {ds:+8.3f}")
        print(f"  summa saw F4 − A0 {tot:+.3f} mm")


if __name__ == "__main__":
    main()
