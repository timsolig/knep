"""Varianterna av A0O mot A0 på träningsdagarna (a0o.py trana), med domarens regel.

    uv run python experiments/riksgransen/urval_tr.py

Regeln, bestämd innan siffrorna sågs: bland varianterna som domaren godkänner mot A0 på träningen
(alla mätare) väljs den med störst förbättring av kvot våt per timme vid zonens mätare. Godkänns
ingen, väljs ingen. Det här är underlag till en senare uppgift; valideringen rörs inte här.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import zon  # noqa: E402

_spec = importlib.util.spec_from_file_location("analys_domare", HERE.parent / "analys" / "domare.py")
domare = importlib.util.module_from_spec(_spec)
sys.modules["analys_domare"] = domare
_spec.loader.exec_module(domare)

from a0o import TR_OUT, VARIANTER  # noqa: E402

ROWS = [("timme/alla", "kvot våt"), ("timme/alla", "FSS 0.5"), ("timme/alla", "CSI 1"),
        ("timme/alla", "falskt vid torr mätare"), ("kvart/alla", "falskt vid torr mätare"),
        ("timme/over400", "kvot våt"), ("timme/over400", "falskt vid torr mätare")]


def load(sub, name):
    out = {}
    for p in sorted((TR_OUT / sub / name).glob("*.json")):
        out[p.stem] = json.loads(p.read_text())
    return out


def f(x):
    return f"{x:+.4f}".replace(".", ",")


def main():
    res = {}
    for name, (H, thr) in VARIANTER.items():
        a, b = load("alla", name), load("alla", "A0")
        za, zb = load(f"zon_H{H:g}", name), load(f"zon_H{H:g}", "A0")
        if not a:
            continue
        tab, ztab = domare.table(a, b, B=1000), domare.table(za, zb, B=1000)
        v = domare.verdict(tab)
        zr = ztab["timme/alla"]["kvot våt"]
        res[name] = {"H": H, "min_opera": thr, "dagar": len(a), "dom": v,
                     "zon_kvot_vat": [zr["varde"], zr["bas"], zr["diff"], zr["lo"], zr["hi"]],
                     "zon_falskt": [ztab["timme/alla"]["falskt vid torr mätare"][k] for k in ("varde", "bas", "diff", "lo", "hi")],
                     "rader": {f"{k} {m}": [tab[k][m][x] for x in ("varde", "bas", "diff", "lo", "hi")] for k, m in ROWS}}
        rut = tab["rutor"]["rutor med eko i över hälften av de torra timmarna, per dag"]
        res[name]["rutor"] = [rut[x] for x in ("varde", "bas", "diff", "lo", "hi")]
    ok = [n for n in res if res[n]["dom"]["battre"]]
    val = max(ok, key=lambda n: res[n]["zon_kvot_vat"][2]) if ok else None
    (zon.OUT / "urval_tr.json").write_text(json.dumps({"valt": val, "varianter": res}, ensure_ascii=False, indent=1, default=float))
    print("| variant | H | min OPERA | dagar | godkänd | sämre i | kvot våt timme, zonen (A0) skillnad (95 %) | falskt timme, zonen (A0) skillnad (95 %) | falskt timme, alla (A0) skillnad (95 %) | rutor per dag (A0) |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for n, r in res.items():
        z, zf, fa, ru = r["zon_kvot_vat"], r["zon_falskt"], r["rader"]["timme/alla falskt vid torr mätare"], r["rutor"]
        sam = ", ".join(r["dom"]["samre_i"][:3]) + (" ..." if len(r["dom"]["samre_i"]) > 3 else "")
        print(f"| {n} | {r['H']:g} | {r['min_opera']:g} | {r['dagar']} | {'ja' if r['dom']['battre'] else 'nej'} | {sam or 'inget'} | "
              f"{z[0]:.3f} ({z[1]:.3f}) {f(z[2])} ({f(z[3])} till {f(z[4])}) | {zf[0]:.4f} ({zf[1]:.4f}) {f(zf[2])} ({f(zf[3])} till {f(zf[4])}) | "
              f"{fa[0]:.4f} ({fa[1]:.4f}) {f(fa[2])} ({f(fa[3])} till {f(fa[4])}) | {ru[0]:.1f} ({ru[1]:.1f}) |".replace(".", ","))
    print("\nbättre i:", {n: r["dom"]["battre_i"] for n, r in res.items()})
    print("valt:", val)


if __name__ == "__main__":
    main()
