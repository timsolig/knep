"""Kort tabell över varianterna i uppgift 3: skillnaden mot baslinjen för de viktigaste måtten.

    uv run python experiments/projektion/kons_sammanfatt.py <läge> <ref> <system> ...

Skriver experiments/projektion/resultat/konservering_<läge>.md. Skillnaden är orienterad som i
domaren (negativt är bättre), `*` och `!` som där. Domen är domarens (domare.verdict).
"""

import sys

import numpy as np

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import domare as D  # noqa: E402

KEYS = ["q99", "q99.9", "yta5", "yta10", "yta20", "volym", "blockmax_q50", "blockmax_q90",
        "fss5_10", "fss5_30", "fss10_30", "csi5", "sedi10", "fss1_30", "csi1", "form4_8", "form8_16", "hopp"]
SHOWN = [1, 4, 8, 12, 20]


def main():
    mode, ref, systems = sys.argv[1], sys.argv[2], sys.argv[3:]
    days = D.mode_days(mode)
    rd = D.load(mode, ref, days)
    days = [d for d in days if rd[d]["issues"] > 0]
    idx = [D.LEADS.index(k) for k in SHOWN]
    out = [f"# Uppgift 3, läge {mode}, mot `{ref}`", "",
           f"{len(days)} dygn. Varje cell: systemets värde (log kvot mot radarn för kons och form, annars poäng) "
           "och skillnaden mot baslinjen, negativt är bättre; `*` intervallet (95 %, bootstrap över dygnen) helt på "
           "den bättre sidan, `!` helt på den sämre.", ""]
    head = "| mått | " + " | ".join(f"{k * 15} min" for k in SHOWN) + " |"
    sep = "|---|" + "---|" * len(SHOWN)
    verdicts = []
    for name in systems:
        sd = D.load(mode, name, days)
        if sd is None:
            out += [f"## {name}", "", "saknas", ""]
            continue
        cmp = D.compare(sd, rd, days, 500)
        v, why = D.verdict(cmp)
        verdicts.append((name, v, why))
        sec = float(sum(sd[d]["forecast_seconds"] for d in days)) / max(1, int(sum(sd[d]["issues"] for d in days)))
        out += [f"## {name}", "", f"Domen: **{v}** ({', '.join(why[:10])}{' ...' if len(why) > 10 else ''}). "
                f"Prognosen {sec:.1f} s per utgåva.", "", head, sep]
        for k in KEYS:
            r = cmp[k]
            cells = [f"{D.fmt(r['system'][i], r['kind'])} ({r['diff'][i]:+.3f}{D.mark(r, i)})" for i in idx]
            out.append(f"| {k} | " + " | ".join(cells) + " |")
        out.append("")
    out += ["## Domarna", ""] + [f"- `{n}`: {v} ({', '.join(w[:6])})" for n, v, w in verdicts] + [""]
    md = "\n".join(out)
    (D.RESULTS / f"konservering_{mode}.md").write_text(md + "\n")
    print(md)


if __name__ == "__main__":
    with np.errstate(all="ignore"):
        main()
