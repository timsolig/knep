"""Sammanställning av bild.py: solstrålar, återkommande ekrar och skurar av prickar (anaprop).

    uv run python experiments/analys/bild.py sammanstall
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime

import numpy as np

from artefakter import OUT, days
from bild import DAG

SOL_HOJD = (-2.0, 10.0)  # solen nära horisonten, där den syns i radarns lägsta elevationer
SOL_DAZ = 3.0  # grader


def circ(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)


def main() -> None:
    part = dict(days())
    E, P = [], []
    for d in sorted(part):
        f = DAG / f"{d}.json"
        if not f.exists():
            print("saknas", d)
            continue
        z = json.loads(f.read_text())
        for s in z["ekrar"]:
            s["del"] = part[d]
        for r in z["prickar"]:
            r["del"] = part[d]
        E += z["ekrar"]
        P += z["prickar"]
    out: dict = {"dagar": len({e["t"][:10] for e in P}), "ekrar_totalt": len(E)}

    # ekrar per radar och de som återkommer (samma radar, azimut ±1 grad, flera dagar)
    out["ekrar_per_radar"] = dict(Counter(e["radar"] for e in E).most_common())
    by = defaultdict(set)
    for e in E:
        for da in (-1, 0, 1):
            by[(e["radar"], (e["az"] + da) % 360)].add(e["t"][:10])
    rec, seen = [], set()
    for (r, a), ds in sorted(by.items(), key=lambda kv: -len(kv[1])):
        if len(ds) < 3 or any((r, (a + k) % 360) in seen for k in range(-2, 3)):
            continue
        seen.add((r, a))
        n_img = sum(1 for e in E if e["radar"] == r and circ(e["az"], a) <= 1)
        tr = len({d for d in ds if part[d] == "traning"})
        rec.append({"radar": r, "az": a, "dagar": len(ds), "dagar_traning": tr, "dagar_validering": len(ds) - tr,
                    "bilder": n_img})
    out["ekrar_aterkommande"] = rec[:40]

    # solen: andelen ekrar nära solens azimut när solen står lågt, mot slumpen
    low = [e for e in E if SOL_HOJD[0] <= e["sol_hojd"] <= SOL_HOJD[1]]
    near = [e for e in low if circ(e["az"], e["sol_az"]) <= SOL_DAZ]
    p0 = (2 * SOL_DAZ + 1) / 360
    # kontroll: samma ekrar mot solens azimut förskjuten 20 till 40 grader (ger en empirisk slumpnivå)
    ctrl = np.mean([np.mean([circ(e["az"], (e["sol_az"] + off) % 360) <= SOL_DAZ for e in low])
                    for off in (20, 25, 30, 35, 40, -20, -25, -30, -35, -40)]) if low else float("nan")
    out["sol"] = {"ekrar_lag_sol": len(low), "nara_solen": len(near), "andel": len(near) / max(len(low), 1),
                  "slump": p0, "kontroll_forskjuten": float(ctrl),
                  "handelser": sorted([{k: e[k] for k in ("t", "radar", "az", "andel", "sol_az", "sol_hojd", "del")}
                                       for e in near], key=lambda e: e["t"])}
    hi = [e for e in E if e["sol_hojd"] > SOL_HOJD[1]]
    out["sol"]["hog_sol"] = {"ekrar": len(hi), "nara_solen": sum(circ(e["az"], e["sol_az"]) <= SOL_DAZ for e in hi)}
    # per klass av solhöjd: andelen ekrar inom ±3 grader från solen
    klass = {}
    for lo, hi_ in ((-90, -5), (-5, 0), (0, 5), (5, 10), (10, 20), (20, 30), (30, 90)):
        sel = [e for e in E if lo <= e["sol_hojd"] < hi_]
        nn = sum(circ(e["az"], e["sol_az"]) <= SOL_DAZ for e in sel)
        klass[f"{lo}..{hi_}"] = {"ekrar": len(sel), "nara_solen": nn, "andel": round(nn / max(len(sel), 1), 3)}
    out["sol"]["per_solhojd"] = klass
    # solstrålar som följer solen: samma radar, minst tre bilder i följd (högst 10 min mellan) nära solens azimut
    # med solen över -2 grader
    cand = sorted([e for e in E if circ(e["az"], e["sol_az"]) <= SOL_DAZ and e["sol_hojd"] >= -2],
                  key=lambda e: (e["radar"], e["t"]))
    ev, cur = [], []
    for e in cand:
        t = datetime.fromisoformat(e["t"])
        if cur and (cur[-1]["radar"] != e["radar"] or (t - datetime.fromisoformat(cur[-1]["t"])).total_seconds() > 600):
            ev.append(cur)
            cur = []
        cur.append(e)
    if cur:
        ev.append(cur)
    sol_ev = []
    for g in ev:
        ts = sorted({e["t"] for e in g})
        if len(ts) < 3:
            continue
        sol_ev.append({"radar": g[0]["radar"], "fran": ts[0], "till": ts[-1], "bilder": len(ts),
                       "az": [min(e["az"] for e in g), max(e["az"] for e in g)],
                       "sol_az": [round(min(e["sol_az"] for e in g), 1), round(max(e["sol_az"] for e in g), 1)],
                       "sol_hojd": [round(min(e["sol_hojd"] for e in g), 1), round(max(e["sol_hojd"] for e in g), 1)],
                       "andel_max": max(e["andel"] for e in g), "del": g[0]["del"]})
    out["sol"]["foljer_solen"] = sol_ev
    # ekrarnas fördelning över dygnet (UTC) och solhöjd
    out["ekrar_timme_utc"] = dict(sorted(Counter(int(e["t"][11:13]) for e in E).items()))

    # prickar: timmar per radar där isolerade, kantiga ekon ligger långt över radarns vanliga nivå
    # v: 0 bilder, 1 eko, 2 prickar (alla), 3 torra rutor, 4 eko vid torra, 5 prickar vid torra,
    #    6 nya prickar (utanför kända klotterrutor), 7 nya kantiga, 8 nya prickar vid torra, 9 nya kantiga vid torra
    H = defaultdict(lambda: np.zeros(10))
    for r in P:
        key = (r["radar"], r["t"][:13])
        H[key] += [1, r["eko"], r["prickar"], r.get("torr_rutor", 0), r.get("torr_eko", 0), r.get("torr_prickar", 0),
                   r["prickar_nya"], r["kantigt_nytt"], r.get("torr_prickar_nya", 0), r.get("torr_kantigt_nytt", 0)]
    per_radar = defaultdict(list)
    for (rad, h), v in H.items():
        per_radar[rad].append((h, v[6] / v[0], v))
    bursts, levels = [], {}
    for rad, lst in per_radar.items():
        x = np.array([q[1] for q in lst])
        med = float(np.median(x))
        mad = float(np.median(np.abs(x - med)) * 1.4826) + 1.0
        levels[rad] = {"median_prickar_per_bild": med, "p95": float(np.percentile(x, 95))}
        for h, m, v in lst:
            if m >= max(20.0, med + 8 * mad):
                bursts.append({"radar": rad, "timme": h, "nya_prickar_per_bild": round(float(m), 1),
                               "alla_prickar_per_bild": round(float(v[2] / v[0]), 1),
                               "nya_kantiga_per_bild": round(float(v[7] / v[0]), 1),
                               "eko_per_bild": round(float(v[1] / v[0]), 1),
                               "andel_nya_prickar_av_eko": round(float(v[6] / max(v[1], 1)), 3),
                               "torr_andel_eko": round(float(v[4] / v[3]), 3) if v[3] else None,
                               "andel_nya_prickar_vid_torra": round(float(v[8] / max(v[6], 1)), 3),
                               "andel_nya_kantiga_vid_torra": round(float(v[9] / max(v[7], 1)), 3),
                               "del": part[h[:10]], "z": round(float((m - med) / mad), 1)})
    bursts.sort(key=lambda b: -b["nya_prickar_per_bild"])
    out["prickar_nivaer"] = levels
    out["skurar"] = bursts
    # skurarnas fördelning över lokal soltid (UTC + lon/15) och månad
    from knep.analys.composite import RADARS
    sol_t = Counter()
    for b in bursts:
        lt = (int(b["timme"][11:13]) + RADARS[b["radar"]][1] / 15) % 24
        sol_t[int(lt // 3) * 3] += 1
    out["skurar_soltid_3h"] = dict(sorted(sol_t.items()))
    out["skurar_manad"] = dict(sorted(Counter(int(b["timme"][5:7]) for b in bursts).items()))
    out["skurar_dagar"] = dict(Counter(b["timme"][:10] for b in bursts).most_common())
    # jämförelse: alla timmar
    allh = Counter()
    for (rad, h) in H:
        allh[int(((int(h[11:13]) + RADARS[rad][1] / 15) % 24) // 3) * 3] += 1
    out["alla_timmar_soltid_3h"] = dict(sorted(allh.items()))
    # anaprop: kantiga ekon utanför kända klotterrutor där mätarna är torra, timmar långt över radarns nivå,
    # och dygnscykeln i lokal soltid för sommar (maj till augusti) och resten av året
    dry_b = []
    cyc = defaultdict(lambda: np.zeros(3))
    for rad, lst in per_radar.items():
        x = np.array([q[2][9] / q[2][0] for q in lst])
        med = float(np.median(x))
        mad = float(np.median(np.abs(x - med)) * 1.4826) + 1.0
        for h, _, v in lst:
            m = v[9] / v[0]
            lt = int(((int(h[11:13]) + RADARS[rad][1] / 15) % 24) // 3) * 3
            som = "sommar" if 5 <= int(h[5:7]) <= 8 else "ovrigt"
            cyc[(som, lt)] += [1, m, v[4] / v[0]]
            if m >= max(30.0, med + 8 * mad):
                dry_b.append({"radar": rad, "timme": h, "torra_kantiga_per_bild": round(float(m), 1),
                              "torra_eko_per_bild": round(float(v[4] / v[0]), 1),
                              "torra_rutor_per_bild": round(float(v[3] / v[0]), 1),
                              "andel_kantiga_av_torra_eko": round(float(v[9] / max(v[4], 1)), 3),
                              "eko_per_bild": round(float(v[1] / v[0]), 1), "del": part[h[:10]],
                              "z": round(float((m - med) / mad), 1)})
    dry_b.sort(key=lambda b: -b["torra_kantiga_per_bild"])
    out["torra_skurar"] = dry_b
    out["torra_skurar_dagar"] = dict(Counter(b["timme"][:10] for b in dry_b).most_common())
    out["torra_skurar_soltid_3h"] = dict(sorted(Counter(
        int(((int(b["timme"][11:13]) + RADARS[b["radar"]][1] / 15) % 24) // 3) * 3 for b in dry_b).items()))
    out["dygnscykel_torra_kantiga"] = {f"{s} {lt:02d}": {"timmar": int(v[0]), "torra_kantiga_per_bild": round(float(v[1] / v[0]), 2),
                                                          "torra_eko_per_bild": round(float(v[2] / v[0]), 1)}
                                       for (s, lt), v in sorted(cyc.items())}
    tot = np.sum([v for v in H.values()], 0)
    out["prickar_totalt"] = {"bilder_radar": int(tot[0]), "andel_prickar_av_eko": float(tot[2] / tot[1]),
                             "andel_prickar_vid_torra": float(tot[5] / max(tot[2], 1)),
                             "andel_nya_prickar_av_prickar": float(tot[6] / max(tot[2], 1)),
                             "andel_nya_prickar_vid_torra": float(tot[8] / max(tot[6], 1)),
                             "andel_nya_kantiga_vid_torra": float(tot[9] / max(tot[7], 1)),
                             "andel_eko_vid_torra": float(tot[4] / max(tot[1], 1)),
                             "torra_rutor_per_bild": float(tot[3] / max(tot[0], 1))}
    (OUT / "bild_tabell.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(json.dumps({k: v for k, v in out.items() if k not in ("skurar", "sol", "prickar_nivaer")}, indent=1, ensure_ascii=False)[:4000])
    print("sol", {k: v for k, v in out["sol"].items() if k not in ("handelser", "foljer_solen", "per_solhojd")})
    for k, v in out["sol"]["per_solhojd"].items():
        print("  solhöjd", k, v)
    for e in out["sol"]["foljer_solen"]:
        print("  följer solen", e)
    for e in out["ekrar_aterkommande"][:25]:
        print("  återkommande", e)
    print("skurar", len(bursts))
    for b in bursts[:30]:
        print(" ", b)
    print("torra skurar", len(dry_b), out["torra_skurar_dagar"], out["torra_skurar_soltid_3h"])
    for b in dry_b[:30]:
        print(" ", b)
    for k, v in out["dygnscykel_torra_kantiga"].items():
        print("  dygn", k, v)


if __name__ == "__main__":
    main()
