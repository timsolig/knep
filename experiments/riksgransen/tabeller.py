"""Tabellerna till rapporten ur /data/riksgransen/frekvens_<del>.json.

    uv run python experiments/riksgransen/tabeller.py [traning]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

OUT = Path("/data/riksgransen")


def f(x, n=2):
    return f"{x:.{n}f}".replace(".", ",")


def main():
    part = sys.argv[1] if len(sys.argv) > 1 else "traning"
    r = json.loads((OUT / f"frekvens_{part}.json").read_text())
    print(f"{len(r['dagar'])} dagar: {', '.join(r['dagar'])}\n")
    for name, bins, unit in (("beam", r["beam_bins"], "km"), ("dist", r["dist_bins"], "km")):
        print(f"| {'strålhöjd' if name == 'beam' else 'avstånd'} ({unit}) | rutbilder med OPERA ≥ 0,1 | varav SMHI 0 | andel | SMHI ≥ 0,1 | varav OPERA 0 | andel |")
        print("|---|---|---|---|---|---|---|")
        for b, lo in enumerate(bins):
            c = r[name].get(str(b))
            if not c or c["cov"] == 0:
                continue
            hi = bins[b + 1] if b + 1 < len(bins) else None
            lab = f"{lo:g} till {hi:g}" if hi is not None else f"över {lo:g}"
            print(f"| {lab.replace('.', ',')} | {c['ow']} | {c['gap']} | {f(c['gap'] / max(c['ow'], 1))} | {c['sw']} | {c['rev']} | {f(c['rev'] / max(c['sw'], 1))} |")
        print()
    print("| H (km) | rutor i zonen | OPERA ≥ 0,1 | varav SMHI 0 (a) | mätartimmar i zonen | stationer | ändrade timmar | varav mätaren våt (b) | mätare mm / OPERA mm i ändrade | torr–torr timmar, mätaren våt |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for h, k in r["kand"].items():
        m = r["matare"][h]
        fb = f(m["andrade_vat"] / m["andrade"]) if m["andrade"] else "–"
        ratio = f(m["g_andrade"] / m["o_andrade"]) if m["o_andrade"] else "–"
        tt = f(m["torr_torr_vat"] / m["torr_torr"]) if m["torr_torr"] else "–"
        print(f"| {h.replace('.', ',')} | {k['rutor']} | {k['ow']} | {k['gap']} ({f(k['gap'] / max(k['ow'], 1))}) | {m['timmar']} | {len(m['stationer'])} | {m['andrade']} | {m['andrade_vat']} ({fb}) | {ratio} | {m['torr_torr']} ({tt}) |")
    m = r["matare"]["0.0"]
    print(f"\nalla mätare (H = 0): {m['timmar']} timmar, ändrade {m['andrade']}, våta {m['andrade_vat']}"
          f" ({f(m['andrade_vat'] / max(m['andrade'], 1))}), mätare/OPERA {f(m['g_andrade'] / max(m['o_andrade'], 1e-9))};"
          f" torr–torr {m['torr_torr']}, våta {m['torr_torr_vat']} ({f(m['torr_torr_vat'] / max(m['torr_torr'], 1))})")
    for h in r["kand"]:
        m = r["matare"][h]
        if m["max_n"]:
            print(f"max-regeln H={h}: {m['max_n']} timmar, MAE SMHI {f(m['max_ae_smhi'] / m['max_n'], 3)}, MAE max {f(m['max_ae_max'] / m['max_n'], 3)}")
    print("\n| ring kring platsen (km) | rutor | OPERA har data | OPERA-eko ≥ 0,1, andel av bilderna med data | SMHI har data | glapp | glapp i zonen H = 2 / 3 / 4 |")
    print("|---|---|---|---|---|---|---|")
    for k, c in r["plats"].items():
        print(f"| {k} | {c['rutor']} | {c['opera_fin']} | {f(c['opera_eko'] / max(c['opera_fin'], 1), 3)} | {c['smhi_fin']} | {c['gap']} | {c['gap_H2']} / {c['gap_H3']} / {c['gap_H4']} |")
    print("\nurval:", json.dumps(r["urval"]))


if __name__ == "__main__":
    main()
