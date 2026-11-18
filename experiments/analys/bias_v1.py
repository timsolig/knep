"""bias-v1: träna volymkorrektionen och korsvalidera den mot regnmätarna, utan valideringens och testdelens dygn.

Alla dygn i experiments/sverige/dagar.json (båda delarna, utan att skilja på dem) plus ett dygn före och
efter sätts till NaN (G och R) i en tunn omslutning av Store.pairs, innan något skattas eller räknas.
Skriptet skriver aldrig ut vilka dygn det är, bara antalet bortmaskade timmar.

    uv run python experiments/analys/bias_v1.py --start 2024-06-01 --end 2024-08-31 --grid TIF --out /dev/shm/bias_v1/prov
    uv run python experiments/analys/bias_v1.py --start 2023-01-01 --end 2025-12-31 --grid TIF --out /dev/shm/bias_v1/full --years

Lagret i /work/cache/bias läses bara (inget flush, inga add_*). Allt som skrivs hamnar i --out.
"""

from __future__ import annotations

import argparse
import json
import resource
import sys
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sverige"))
from knep.analys import bias  # noqa: E402

DAGAR = Path(__file__).resolve().parents[1] / "sverige" / "dagar.json"
STORE = Path("/work/cache/bias")
G_MAX = 100.0  # mm på en timme; svenskt rekord är långt under, större värden är felvärden i arkivet


def maskade_dygn() -> set[date]:
    """Alla dygn i dagar.json (alla delar) och grannarna. Innehållet skrivs aldrig ut."""
    ut = set()
    for d in json.loads(DAGAR.read_text()):
        k = date.fromisoformat(d["day"])
        ut |= {k - timedelta(days=1), k, k + timedelta(days=1)}
    return ut


class MaskadStore(bias.Store):
    """Store.pairs med G och R satta till NaN för de maskade dygnen (och för dygn i `extra`). Minnesbunden:
    hela paret läses en gång för alla stationer och väljs sedan per kolumn."""

    def __init__(self, root, masked: set[date], ids_all: np.ndarray):
        self.root = Path(root)  # ingen mkdir: Store.__init__ anropas inte
        self.masked = masked
        self.extra: set[date] = set()
        self.ids_all = np.asarray(ids_all)
        self._cache = None
        self.n_maskade_timmar = 0
        self.n_felvärden = 0

    def _full(self, start, end):
        key = (start, end)
        if self._cache is None or self._cache[0] != key:
            G, R, T = super().pairs(start, end, self.ids_all)
            dag = np.array([t.date() for t in T], dtype=object) if T else np.array([], dtype=object)
            m = np.array([d in self.masked for d in dag], bool)
            self.n_maskade_timmar = int(m.sum())
            G[m] = np.nan
            R[m] = np.nan
            # mätararkivet har felvärden (exakt 720 mm på en timme hos några stationer): över G_MAX är paret ogiltigt
            fel = np.nan_to_num(G, nan=0.0) > G_MAX
            self.n_felvärden = int(fel.sum())
            G[fel] = np.nan
            R[fel] = np.nan
            self._cache = (key, G, R, T, dag)
        return self._cache

    def pairs(self, start, end, ids):
        _, G, R, T, dag = self._full(start, end)
        pos = {int(s): k for k, s in enumerate(self.ids_all)}
        take = np.array([pos[int(s)] for s in ids])
        G, R = G[:, take], R[:, take]
        if self.extra:
            e = np.array([d in self.extra for d in dag], bool)
            G, R = G.copy(), R.copy()
            G[e] = np.nan
            R[e] = np.nan
        return G, R, T

    def flush(self):  # skriver aldrig till lagret
        raise RuntimeError("lagret får bara läsas")


def sammanfatta(G, R, Rc, use):
    s = bias._summary(G, R, Rc, use)
    if s:
        tg = np.nansum(G, axis=0)
        s["stationer"] = int((use & (tg >= 50)).sum())
    return s


def kvot_tabell(rader, namn):
    ut = [f"| {namn} | n | volym f | volym e | median f | median e | ±20 % f | ±20 % e |", "|---|---|---|---|---|---|---|---|"]
    for k, s in rader:
        if not s:
            ut.append(f"| {k} | 0 | | | | | | |")
            continue
        ut.append(f"| {k} | {s['stationer']} | {s['volym_före']:.3f} | {s['volym_efter']:.3f} | {s['median_före']:.3f} | "
                  f"{s['median_efter']:.3f} | {s['inom_20_proc_före']:.2f} | {s['inom_20_proc_efter']:.2f} |")
    return "\n".join(ut)


def kvantil_tabell(rader):
    qs = [f"{p * 100:g}" for p in bias.TAIL_Q]
    ut = ["| | " + " | ".join(f"q{q} mm (f / e)" for q in qs) + " |", "|---|" + "---|" * len(qs)]
    for k, s in rader:
        if not s or f"kvantil_{qs[0]}_före" not in s:
            ut.append(f"| {k} | " + " | ".join("" for _ in qs) + " |")
            continue
        ut.append(f"| {k} | " + " | ".join(
            f"{s[f'kvantil_{q}_mätare_mm']:.1f} ({s[f'kvantil_{q}_före']:.2f} / {s[f'kvantil_{q}_efter']:.2f})" for q in qs) + " |")
    return "\n".join(ut)


def delar(G, R, Rc, T, inside, h_st):
    """Alla uppdelningar: helhet, månader, årstider och strålhöjd."""
    mån = np.array([(t - timedelta(minutes=1)).month for t in T])
    ut = {"alla": sammanfatta(G, R, Rc, inside)}
    for m in range(1, 13):
        sel = mån == m
        ut[f"mån {m:02d}"] = sammanfatta(G[sel], R[sel], Rc[sel], inside) if sel.any() else {}
    for namn, ms in (("vinter (dec-feb)", (12, 1, 2)), ("vår (mar-maj)", (3, 4, 5)), ("sommar (jun-aug)", (6, 7, 8)), ("höst (sep-nov)", (9, 10, 11))):
        sel = np.isin(mån, ms)
        ut[namn] = sammanfatta(G[sel], R[sel], Rc[sel], inside) if sel.any() else {}
    for namn, lo, hi in (("stråle < 1 km", 0, 1), ("stråle 1 till 2 km", 1, 2), ("stråle > 2 km", 2, 99)):
        use = inside & (h_st >= lo) & (h_st < hi)
        ut[namn] = sammanfatta(G, R, Rc, use) if use.any() else {}
    return ut


def skriv(namn, tabeller, f):
    f.write(f"\n### {namn}\n\n")
    helhet = ["alla"]
    f.write(kvot_tabell([(k, tabeller[k]) for k in helhet + [k for k in tabeller if k.startswith(("vinter", "vår", "sommar", "höst", "stråle"))]], "urval") + "\n\n")
    f.write(kvantil_tabell([(k, tabeller[k]) for k in tabeller if not k.startswith("mån")]) + "\n\n")
    f.write("Per månad (stationer med minst 50 mm i månaden):\n\n")
    f.write(kvot_tabell([(k, tabeller[k]) for k in tabeller if k.startswith("mån")], "månad") + "\n")


def faktorns_spridning(corr, grid, f):
    from pyproj import Transformer

    h = corr.beam
    ok = np.isfinite(h)
    X, Y = grid.centres()
    f.write("\n### Faktorns spridning på kartan (K = nivåfaktorn, där strålen når)\n\n")
    f.write("| mitt i | p1 | p5 | p25 | p50 | p75 | p95 | p99 | max | andel > 1,5 | andel < 0,7 |\n|---|---|---|---|---|---|---|---|---|---|---|\n")
    til = Transformer.from_crs("EPSG:3006", "EPSG:4326", always_xy=True)
    for m, namn in ((1, "jan"), (4, "apr"), (7, "jul"), (10, "okt")):
        K = corr.factor(datetime(2024, m, 15, 12, tzinfo=UTC))[ok]
        p = np.percentile(K, [1, 5, 25, 50, 75, 95, 99])
        f.write(f"| {namn} | " + " | ".join(f"{v:.2f}" for v in p) + f" | {K.max():.2f} | {np.mean(K > 1.5):.3f} | {np.mean(K < 0.7):.3f} |\n")
    f.write("\nMedelfaktor och andel > 1,5 per strålhöjd, och var faktorn är störst (jan och jul):\n\n")
    f.write("| höjd | jan medel | jul medel | jan andel>1,5 | jul andel>1,5 | celler |\n|---|---|---|---|---|---|\n")
    Kj = corr.factor(datetime(2024, 1, 15, 12, tzinfo=UTC))
    Kl = corr.factor(datetime(2024, 7, 15, 12, tzinfo=UTC))
    for namn, lo, hi in (("< 1 km", 0, 1), ("1 till 2 km", 1, 2), ("2 till 3 km", 2, 3), ("> 3 km", 3, 99)):
        s = ok & (h >= lo) & (h < hi)
        if s.any():
            f.write(f"| {namn} | {Kj[s].mean():.2f} | {Kl[s].mean():.2f} | {np.mean(Kj[s] > 1.5):.3f} | {np.mean(Kl[s] > 1.5):.3f} | {int(s.sum())} |\n")
    for namn, K in (("jan", Kj), ("jul", Kl)):
        v = np.where(ok, K, -1)
        top = np.argsort(v.ravel())[-1]
        i, j = np.unravel_index(top, v.shape)
        lon, lat = til.transform(X[i, j], Y[i, j])
        stor = ok & (K > 1.5)
        if stor.any():
            lo_, la_ = til.transform(X[stor].mean(), Y[stor].mean())
            f.write(f"\n{namn}: störst {K[i, j]:.2f} vid {lat:.2f} N, {lon:.2f} E (stråle {h[i, j]:.1f} km); "
                    f"tyngdpunkt för celler över 1,5: {la_:.2f} N, {lo_:.2f} E\n")
        else:
            f.write(f"\n{namn}: störst {K[i, j]:.2f} vid {lat:.2f} N, {lon:.2f} E (stråle {h[i, j]:.1f} km); inga celler över 1,5\n")
    f.write(f"\nRestkartans spridning (log): p1 {np.percentile(corr.resid[ok], 1):+.2f}, p50 {np.percentile(corr.resid[ok], 50):+.2f}, "
            f"p99 {np.percentile(corr.resid[ok], 99):+.2f}; svansexponent γ = {corr.gamma:+.3f}\n")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--start", type=date.fromisoformat, required=True)
    p.add_argument("--end", type=date.fromisoformat, required=True)
    p.add_argument("--grid", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--years", action="store_true", help="även korsvalidering per år (träna övriga år, pröva ett)")
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    stations = bias.Stations.load(STORE / "stations.json")
    grid = bias._grid_from_tif(a.grid)
    beam = bias.beam_height(grid)
    store = MaskadStore(STORE, maskade_dygn(), stations.ids)
    G, R, T = store.pairs(a.start, a.end, stations.ids)
    print(f"par: {G.shape} timmar x stationer, {G.nbytes / 1e6:.0f} MB per matris; bortmaskade timmar: {store.n_maskade_timmar}; felvärden: {store.n_felvärden}; "
          f"timmar med data kvar: {int(np.isfinite(G).any(axis=1).sum())}", flush=True)
    row, col, inside = stations.pixels(grid)
    h_st = np.where(inside, beam[np.clip(row, 0, grid.shape[0] - 1), np.clip(col, 0, grid.shape[1] - 1)], np.nan)

    # 1. skattning på allt som är kvar
    corr, rep = bias.fit(store, stations, grid, a.start, a.end, beam=beam)
    corr.save(a.out / "bias_v1.npz")
    K = bias.station_factors(corr, T, row, col, inside)
    Rc = corr.tail(R * K)
    träning = delar(G, R, Rc, T, inside, h_st)
    print(f"fit klar {time.time() - t0:.0f} s, toppminne {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024:.0f} MB", flush=True)

    # 2. stationsvis korsvalidering (som bias.cross_validate, men behåller fälten för uppdelningarna)
    rng = np.random.default_rng(0)
    fold = rng.integers(0, 5, len(stations.ids))
    Rcv = np.full_like(R, np.nan)
    for fo in range(5):
        tr = fold != fo
        sub = bias.Stations(stations.ids[tr], stations.lat[tr], stations.lon[tr])
        c, _ = bias.fit(store, sub, grid, a.start, a.end, beam=beam)
        te = ~tr & inside
        Rcv[:, te] = c.tail(R[:, te] * bias.station_factors(c, T, row, col, inside)[:, te])
        print(f"del {fo} klar {time.time() - t0:.0f} s", flush=True)
    korsval = delar(G, R, Rcv, T, inside, h_st)
    # kontroll mot bias.cross_validate: samma tal för helheten
    kontroll = bias.cross_validate(store, stations, grid, a.start, a.end, beam=beam)
    print("kontroll cross_validate volym_efter", kontroll.get("volym_efter"), "mot", korsval["alla"].get("volym_efter"), flush=True)

    # 3. per år
    peråret = {}
    if a.years:
        års = sorted({t.year for t in T})  # dygnets index 0 är timmen som slutar 00 samma dygn, så dygnets år gäller
        for y in års:
            store.extra = {date(y, 1, 1) + timedelta(days=i) for i in range(366)
                           if (date(y, 1, 1) + timedelta(days=i)).year == y}
            c, _ = bias.fit(store, stations, grid, a.start, a.end, beam=beam)
            store.extra = set()
            sel = np.array([t.year == y for t in T])
            Ky = bias.station_factors(c, T, row, col, inside)
            Ry = c.tail(R * Ky)
            peråret[y] = delar(G[sel], R[sel], Ry[sel], [t for t, s in zip(T, sel) if s], inside, h_st)
            print(f"år {y} klar {time.time() - t0:.0f} s", flush=True)

    with open(a.out / "tabeller.md", "w") as f:
        f.write(f"Bortmaskade timmar: {store.n_maskade_timmar}; felvärden över {G_MAX:g} mm borttagna: {store.n_felvärden}; stationer med data: {rep['stationer']}; timmar i paret: {len(T)}\n")
        f.write(f"\nTräning (hela perioden, kartan skattad på samma data), gamma = {corr.gamma:+.3f}\n")
        skriv("I urvalet (träning)", träning, f)
        skriv("Stationsvis korsvalidering (5 delar, frö 0)", korsval, f)
        for y, t in peråret.items():
            skriv(f"Korsvalidering per år: tränat utan {y}, prövat på {y} (samma stationer)", t, f)
        faktorns_spridning(corr, grid, f)
    (a.out / "resultat.json").write_text(json.dumps({"träning": träning, "korsval": korsval, "år": {str(k): v for k, v in peråret.items()},
                                                    "rapport_fit": rep, "kontroll_cv": kontroll}, ensure_ascii=False, indent=1, default=float))
    print(f"klart {time.time() - t0:.0f} s, toppminne {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024:.0f} MB")


if __name__ == "__main__":
    main()
