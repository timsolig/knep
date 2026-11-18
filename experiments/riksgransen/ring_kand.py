"""Uppgift 0028: kandidaterna mot ringarna i OPERA-delen av A0, valda på träningsdagarna.

    uv run python experiments/riksgransen/ring_kand.py trana        profil, r per plats, klotterkartan för tröskelkandidaterna, måtten på träningen
    uv run python experiments/riksgransen/ring_kand.py validera     den frysta kandidaten (ur /dev/shm/opera_ring/fryst.json) på valideringsdagarna

Allt på OPERA 15-minutersbilderna (/data/riksgransen/opera15/), bara dagar i träningen respektive
valideringen (domare.days). Testdelen läses aldrig.

Regler, bestämda innan siffrorna sågs (uppgift 0028):

* Torra bilder för en plats: omgivningen 30 till 50 km har under 3 % eko (>= 0,1 mm/h).
* Ringplats: andelen eko i ringen 4 till 8 km, i torra bilder, är minst 0,05 (minst cirka 5 gånger omgivningen).
  Radien r är den yttre kanten på den första 4-kmsringen från 8 km och utåt där andelen är högst
  max(0,02, 2 · andelen vid 25 till 30 km). Andøya ingår om profilen visar ringen; annars redovisas den.
* (a) Fast mask: OPERA = NaN inom r km kring ringplatserna.
* (b) Klotterkarta: en ruta är isolerad i en bild om den har eko och ringen 14 till 30 km kring den (rutor
  utanför den inre fönstret 15x15 men innanför 31x31) har under 3 % eko. Kartan är andelen bilder där
  rutan är isolerad. Rutor över tröskeln TAU är misstänkta (TAU i 0,02, 0,05, 0,10). Som F4 tas ekot på en
  misstänkt ruta bort (NaN) bara om omgivningen inom 42 km, utan de misstänkta rutorna, har under 3 % eko.
  Vald är den största TAU där ekot kring ringplatserna i torra bilder går ner till högst
  max(0,02, 2 · andelen vid 25 till 30 km) i alla ringar upp till r.
* Mått: andelen eko i ringarna kring platserna (torra bilder) före och efter (borttaget räknas som inget
  eko), och andelen av den våta OPERA-volymen (summan av mm/h över 0,1) inom 100 km som tas bort, för
  timmar där mer än 20 % av rutorna inom 150 km är våta (medel över timmens bilder).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy.ndimage import uniform_filter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ring_fall as rf  # noqa: E402
import ring_karta as rk  # noqa: E402
import ring_profil as rp  # noqa: E402
import zon  # noqa: E402

KANTER = np.array([0, 4, 8, 12, 16, 20, 25, 30])
TORR = 0.03
TAUS = (0.02, 0.05, 0.10)
IN_, UT_ = 15, 31
WIN = 21
FRYST = rk.TMP / "fryst.json"


def last(day):
    z = np.load(zon.OPERA_DIR / f"{day}.npz")
    v, times = z["v"], [str(t) for t in z["times"]]
    cov = v != 255
    keep = np.flatnonzero(cov.reshape(len(v), -1).mean(1) > 0.2)
    return v[keep], [times[i] for i in keep]


def box(x, n):
    return uniform_filter(x.astype(np.float32), n, mode="constant") * n * n


def isolerad(eko, cov):
    """Rutor med eko där ringen 14 till 30 km kring dem har under 3 % eko."""
    e = box(eko, UT_) - box(eko, IN_)
    c = box(cov, UT_) - box(cov, IN_)
    return eko & (e < TORR * np.maximum(c, 1))


def kill_b(eko, cov, hot):
    """Samma regel som knep.analys.klotter.rensa men NaN i stället för 0 (returnerar bool av borttagna)."""
    if not (eko & hot).any():
        return np.zeros_like(eko)
    e = box(eko & ~hot, WIN)
    c = box(cov & ~hot, WIN)
    return hot & eko & (e < TORR * np.maximum(c, 1))


class Plats:
    def __init__(self, g, namn, lat, lon):
        self.namn = namn
        d = zon.dist_to(g, lat, lon)
        self.d = d
        self.ann = (d >= 30) & (d < 50)
        self.rings = [(d >= a) & (d < b) for a, b in zip(KANTER[:-1], KANTER[1:])]
        self.r100 = d < 100
        self.r150 = d < 150


def platser(g):
    out = {}
    for n, (la, lo) in rp.PLATSER.items():
        if n in ("Røst", "Andøya"):
            continue
        d = zon.dist_to(g, la, lo)
        if (d < 5).any():
            out[n] = Plats(g, n, la, lo)
    return out


def torr(p, eko, cov):
    a = p.ann & cov
    return a.sum() >= 100 and eko[a].mean() < TORR


def profil_dag(P, v, acc):
    cov = v != 255
    eko = (v >= rk.V_WET) & cov
    for i in range(len(v)):
        for n, p in P.items():
            if torr(p, eko[i], cov[i]):
                acc[n]["n"] += 1
                for k, m in enumerate(p.rings):
                    mm = m & cov[i]
                    acc[n]["e"][k] += eko[i][mm].sum()
                    acc[n]["c"][k] += mm.sum()


def kartdag(v, num, den):
    cov = v != 255
    eko = (v >= rk.V_WET) & cov
    for i in range(len(v)):
        num += isolerad(eko[i], cov[i])
    den += cov.sum(0)


def valj_radie(prof):
    """Ur andelen per ring: (ringplats, r)."""
    s = prof["e"] / np.maximum(prof["c"], 1)
    if s[1] < 0.05:
        return False, 0
    gr = max(0.02, 2 * s[6])
    r = 8
    for k in range(2, 7):
        if s[k] <= gr:
            break
        r = KANTER[k + 1]
    return True, int(r)


def mat_dag(P, v, times, kands, acc):
    """Måtten för en dag och alla kandidater. kands: namn -> funktion (eko, cov, rain)->borttagen (bool).
    acc[kand][plats] = dict med ring-summor och timvolymer."""
    cov = v != 255
    eko = (v >= rk.V_WET) & cov
    rain = zon.decode(v)
    rain0 = np.where(eko, rain, 0.0)
    timmar = {}
    for i, t in enumerate(times):
        timmar.setdefault(t[:13], []).append(i)
    wetfr = {n: np.array([eko[i][p.r150].mean() for i in range(len(v))]) for n, p in P.items()}
    for kn, fn in kands.items():
        rem = [fn(eko[i], cov[i], i) for i in range(len(v))]
        for n, p in P.items():
            A = acc[kn][n]
            for i in range(len(v)):
                if torr(p, eko[i], cov[i]):
                    A["n"] += 1
                    for k, m in enumerate(p.rings):
                        A["e0"][k] += (eko[i] & m).sum()
                        A["e1"][k] += ((eko[i] & ~rem[i]) & m).sum()
                        A["c"][k] += (cov[i] & m).sum()
            for h, ii in timmar.items():
                if np.mean(wetfr[n][ii]) > 0.2:
                    A["h"] += 1
                    for i in ii:
                        A["vol"] += rain0[i][p.r100].sum()
                        A["vol_ut"] += rain0[i][p.r100 & rem[i]].sum()


def ny_acc(P, kands):
    return {kn: {n: {"n": 0, "h": 0, "vol": 0.0, "vol_ut": 0.0, "e0": np.zeros(len(KANTER) - 1), "e1": np.zeros(len(KANTER) - 1),
                     "c": np.zeros(len(KANTER) - 1)} for n in P} for kn in kands}


def skriv(acc, ringplatser, tit):
    print(f"\n=== {tit} ===")
    print("andel eko per ring (0-4,4-8,8-12,12-16,16-20,20-25,25-30 km) i torra bilder, före -> efter; borttagen våt volym inom 100 km i regnstimmar")
    res = {}
    for kn, per in acc.items():
        print(f"-- {kn}")
        vt, vu = 0.0, 0.0
        for n in ringplatser:
            A = per[n]
            e0 = A["e0"] / np.maximum(A["c"], 1)
            e1 = A["e1"] / np.maximum(A["c"], 1)
            print(f"  {n:6s} {A['n']:4d} torra bilder  före " + " ".join(f"{x:.3f}" for x in e0) + "  efter " + " ".join(f"{x:.3f}" for x in e1)
                  + f"  | {A['h']} regnstimmar, borttagen volym {100 * A['vol_ut'] / max(A['vol'], 1e-9):.3f} %")
            vt += A["vol"]
            vu += A["vol_ut"]
        print(f"  alla ringplatser: borttagen våt volym {100 * vu / max(vt, 1e-9):.3f} %")
        res[kn] = {n: {"ring_fore": (per[n]["e0"] / np.maximum(per[n]["c"], 1)).round(4).tolist(),
                       "ring_efter": (per[n]["e1"] / np.maximum(per[n]["c"], 1)).round(4).tolist(),
                       "bilder": per[n]["n"], "timmar": per[n]["h"],
                       "vol_pct": round(100 * per[n]["vol_ut"] / max(per[n]["vol"], 1e-9), 4)} for n in ringplatser}
        res[kn]["alla_vol_pct"] = round(100 * vu / max(vt, 1e-9), 4)
    return res


def kandidater(P, rad, hotmaps):
    k = {}
    disc = np.zeros(next(iter(P.values())).d.shape, bool)
    for n, r in rad.items():
        disc |= P[n].d < r
    k["a_mask"] = lambda e, c, i: disc & c
    for tau, hot in hotmaps.items():
        k[f"b_tau{tau}"] = (lambda hot: lambda e, c, i: kill_b(e, c, hot))(hot)
    return k, disc


def trana():
    rk.TMP.mkdir(exist_ok=True)
    g = rf.grid()
    P = platser(g)
    days = rk.dagar("traning")
    acc = {n: {"n": 0, "e": np.zeros(len(KANTER) - 1), "c": np.zeros(len(KANTER) - 1)} for n in P}
    num = np.zeros(g.shape, np.float64)
    den = np.zeros(g.shape, np.float64)
    for d in days:
        v, _ = last(d)
        profil_dag(P, v, acc)
        kartdag(v, num, den)
        print("pass 1", d, flush=True)
    rad, info = {}, {}
    for n in P:
        ring, r = valj_radie(acc[n])
        s = acc[n]["e"] / np.maximum(acc[n]["c"], 1)
        info[n] = {"bilder": acc[n]["n"], "andel_per_ring": s.round(4).tolist(), "ringplats": bool(ring), "r_km": r}
        print(f"{n:6s} {acc[n]['n']:4d} bilder  " + " ".join(f"{x:.3f}" for x in s) + f"  ring={ring} r={r}")
        if ring:
            rad[n] = r
    share = num / np.maximum(den, 1)
    np.save(rk.TMP / "andel_isolerad.npy", share.astype(np.float32))
    hotmaps = {tau: (share > tau) & (den > 0) for tau in TAUS}
    for tau, h in hotmaps.items():
        print(f"TAU {tau}: {int(h.sum())} misstänkta rutor")
        np.save(rk.TMP / f"hot_{tau}.npy", h)
    kands, disc = kandidater(P, rad, hotmaps)
    print("mask: ", int(disc.sum()), "rutor")
    rp_ = [n for n in P if n in rad]
    ac = ny_acc(P, kands)
    for d in days:
        v, t = last(d)
        mat_dag(P, v, t, kands, ac)
        print("pass 2", d, flush=True)
    res = skriv(ac, rp_, "träning")
    (rk.TMP / "trana.json").write_text(json.dumps({"info": info, "rad": rad, "res": res}, ensure_ascii=False, indent=1, default=float))


def validera():
    g = rf.grid()
    P = platser(g)
    fr = json.loads(FRYST.read_text())
    rad = fr["rad"]
    hot = {fr["tau"]: np.load(rk.TMP / f"hot_{fr['tau']}.npy")} if fr["kand"].startswith("b") else {}
    kands, _ = kandidater(P, rad, hot)
    kands = {k: v for k, v in kands.items() if k == fr["kand"] or k == "a_mask"}
    ac = ny_acc(P, kands)
    for d in rk.dagar("validering"):
        v, t = last(d)
        mat_dag(P, v, t, kands, ac)
        print("validering", d, flush=True)
    res = skriv(ac, [n for n in P if n in rad], "validering")
    (rk.TMP / "validera.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float))


if __name__ == "__main__":
    {"trana": trana, "validera": validera}[sys.argv[1]]()
