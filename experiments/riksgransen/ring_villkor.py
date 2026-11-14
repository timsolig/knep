"""Uppgift 0029: ringen vid OPERA-radarerna, mask villkorad per bild.

    uv run python experiments/riksgransen/ring_villkor.py trana      kandidaterna på träningsdagarna, väljer och fryser
    uv run python experiments/riksgransen/ring_villkor.py fall       den frysta varianten på fallet 2026-11-07 (kartor till /dev/shm/opera_ring/)
    uv run python experiments/riksgransen/ring_villkor.py validera   den frysta varianten och den fasta masken på valideringsdagarna, en gång

Data och mått som i ring_kand.py (OPERA 15-minutersbilder, bara dagar i träningen respektive valideringen via
rk.dagar / domare.days; testdelen läses aldrig; inget skrivs till /data).

Kandidater, fastlagda innan siffrorna sågs:

* För varje plats och bild tas eko (NaN) bort inom radien r bara om andelen eko (>= 0,1 mm/h) bland de
  täckta rutorna i ringen utanför, från r + g till R km, är under p. g = 4 km, R = 40 km.
  Är mindre än 30 rutor täckta i ringen utanför tas inget bort.
* Radier: 8, 12, 16 och 24 km lika för alla sex platser, och "per": 0028:s radier (Røst 12, Sømna 12,
  Hurum-fjell 16, Kortpi 8, Vimpeli 8, Utajärvi 16) men 24 för Røst.
* Villkor: andel, p i 0,02, 0,05, 0,10 (v_p), eller intensitet, medel av mm/h (0 för ruta utan eko) i ringen
  utanför under 0,1 mm/h (i_0.1). Totalt 5 radier x 4 villkor = 20 kandidater, och den fasta masken 0028 (a_mask)
  som jämförelse.
* Val (förhandsregel): bland kandidaterna där andelen eko i ringarna 0-4 och 4-8 km i torra bilder efter masken är
  högst 2 gånger andelen vid 25 till 30 km vid alla sex platser, den med minst borttagen våt volym (inom 100 km,
  timmar med över 20 % våta rutor inom 150 km, alla platser). Finns ingen sådan (2 gånger 0,004 är hårt), gäller
  i stället golvet max(0,02, 2 gånger andelen vid 25 till 30 km) som i 0028. Kravet för att ersätta den fasta
  masken är under 1 % borttagen våt volym totalt.
* Torra bilder, ringar och volymmått som i ring_kand.py.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ring_fall as rf  # noqa: E402
import ring_kand as rkd  # noqa: E402
import ring_karta as rk  # noqa: E402
import ring_profil as rp  # noqa: E402
import zon  # noqa: E402

GAP, RMAX = 4.0, 40.0
PS = (0.02, 0.05, 0.10)
INT_P = 0.1
MIN_COV = 30
R0028 = {"norst": 12, "nosmn": 12, "nohfj": 16, "fikor": 8, "fivim": 8, "fiuta": 16}  # Røst, Sømna, Hurum-fjell, Kortpi, Vimpeli, Utajärvi
RADIER = {
    "r8": {n: 8 for n in R0028},
    "r12": {n: 12 for n in R0028},
    "r16": {n: 16 for n in R0028},
    "r24": {n: 24 for n in R0028},
    "per": {**R0028, "norst": 24},
}
FRYST = rk.TMP / "fryst_villkor.json"


class Geo:
    """Index för skiva och ytterring per plats och radie."""

    def __init__(self, P, radier):
        self.disc, self.out = {}, {}
        for sk, rad in radier.items():
            for n, r in rad.items():
                d = P[n].d
                self.disc[(sk, n)] = np.flatnonzero((d < r).ravel())
                self.out[(sk, n)] = np.flatnonzero(((d >= r + GAP) & (d < RMAX)).ravel())
        self.radier = radier


def villkor(geo, sk, vk, eko, cov, rain0):
    """Borttagen (bool) för kandidat (radieschema sk, villkor vk)."""
    rem = np.zeros(eko.shape, bool)
    flat = rem.ravel()
    ef, cf, rf_ = eko.ravel(), cov.ravel(), rain0.ravel()
    for n in geo.radier[sk]:
        o = geo.out[(sk, n)]
        c = cf[o]
        nc = c.sum()
        if nc < MIN_COV:
            continue
        if vk[0] == "v":
            ok = (ef[o] & c).sum() / nc < vk[1]
        else:
            ok = rf_[o][c].sum() / nc < vk[1]
        if ok:
            flat[geo.disc[(sk, n)]] = True
    return rem & cov


def kandidater(P, g):
    radier = RADIER
    geo = Geo(P, radier)
    k = {}
    for sk in radier:
        for p in PS:
            k[f"{sk}_v{p}"] = (lambda sk, p: lambda e, c, r: villkor(geo, sk, ("v", p), e, c, r))(sk, p)
        k[f"{sk}_i{INT_P}"] = (lambda sk: lambda e, c, r: villkor(geo, sk, ("i", INT_P), e, c, r))(sk)
    disc = np.zeros(g.shape, bool)
    for n, r in R0028.items():
        disc |= P[n].d < r
    k["a_mask"] = lambda e, c, r: disc & c
    return k


def mat_dag(P, v, times, kands, acc):
    """Som ring_kand.mat_dag, men kandidaten får också regnet (mm/h, 0 utan eko)."""
    cov = v != 255
    eko = (v >= rk.V_WET) & cov
    rain0 = np.where(eko, zon.decode(v), 0.0)
    rain0 = np.nan_to_num(rain0)
    timmar = {}
    for i, t in enumerate(times):
        timmar.setdefault(t[:13], []).append(i)
    wetfr = {n: np.array([eko[i][p.r150].mean() for i in range(len(v))]) for n, p in P.items()}
    tor = {n: [rkd.torr(p, eko[i], cov[i]) for i in range(len(v))] for n, p in P.items()}
    ef, cf, rf_ = eko.reshape(len(v), -1), cov.reshape(len(v), -1), rain0.reshape(len(v), -1)
    idx = {n: ([np.flatnonzero(m.ravel()) for m in p.rings], np.flatnonzero(p.r100.ravel())) for n, p in P.items()}
    for kn, fn in kands.items():
        rem = np.stack([fn(eko[i], cov[i], rain0[i]).ravel() for i in range(len(v))])
        for n in P:
            A = acc[kn][n]
            rings, i100 = idx[n]
            for i in range(len(v)):
                if tor[n][i]:
                    A["n"] += 1
                    for k, ix in enumerate(rings):
                        e = ef[i][ix]
                        A["e0"][k] += e.sum()
                        A["e1"][k] += (e & ~rem[i][ix]).sum()
                        A["c"][k] += cf[i][ix].sum()
            for h, ii in timmar.items():
                if np.mean(wetfr[n][ii]) > 0.2:
                    A["h"] += 1
                    for i in ii:
                        r100 = rf_[i][i100]
                        A["vol"] += r100.sum()
                        A["vol_ut"] += r100[rem[i][i100]].sum()


def andel25(acc_any, n):
    A = acc_any[n]
    return A["e0"][6] / max(A["c"][6], 1)


def valj(res_tr, ac):
    """Förhandsregeln. res_tr: kandidat -> plats -> ring_efter. Returnerar (namn, regelversion)."""
    for regel in ("strikt", "golv"):
        ok = []
        for kn, per in ac.items():
            if kn == "a_mask":
                continue
            bra = True
            per = {n: A for n, A in per.items() if n in R0028}
            for n, A in per.items():
                e1 = A["e1"] / np.maximum(A["c"], 1)
                ref = A["e0"][6] / max(A["c"][6], 1)
                gr = 2 * ref if regel == "strikt" else max(0.02, 2 * ref)
                if e1[0] > gr or e1[1] > gr:
                    bra = False
            if bra:
                vt = sum(A["vol"] for A in per.values())
                vu = sum(A["vol_ut"] for A in per.values())
                ok.append((vu / max(vt, 1e-9), kn))
        if ok:
            ok.sort()
            return ok[0][1], regel, ok
    return None, None, []


def trana():
    rk.TMP.mkdir(exist_ok=True)
    g = rf.grid()
    P = rkd.platser(g)
    kands = kandidater(P, g)
    ac = rkd.ny_acc(P, kands)
    for d in rk.dagar("traning"):
        v, t = rkd.last(d)
        mat_dag(P, v, t, kands, ac)
        print("träning", d, flush=True)
    res = rkd.skriv(ac, list(R0028), "träning, villkorad mask")
    namn, regel, ok = valj(res, ac)
    print("\nkandidater som klarar regeln:", regel, [(round(100 * a, 3), b) for a, b in ok])
    print("VALD:", namn, regel)
    (rk.TMP / "trana_villkor.json").write_text(json.dumps({"res": res, "vald": namn, "regel": regel, "ok": ok}, ensure_ascii=False, indent=1, default=float))
    if namn:
        FRYST.write_text(json.dumps({"kand": namn}))


def validera():
    g = rf.grid()
    P = rkd.platser(g)
    kands = kandidater(P, g)
    namn = json.loads(FRYST.read_text())["kand"]
    kands = {k: v for k, v in kands.items() if k in (namn, "a_mask")}
    ac = rkd.ny_acc(P, kands)
    for d in rk.dagar("validering"):
        v, t = rkd.last(d)
        mat_dag(P, v, t, kands, ac)
        print("validering", d, flush=True)
    res = rkd.skriv(ac, list(R0028), "validering")
    (rk.TMP / "validera_villkor.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float))


def fall():
    g = rf.grid()
    P = rkd.platser(g)
    namn = sys.argv[2] if len(sys.argv) > 2 else json.loads(FRYST.read_text())["kand"]  # annan kandidat bara som upplysning
    fn = kandidater(P, g)[namn]
    f = np.load("/data/riksgransen/fall.npz")
    op = f["opera"].astype(np.float32)
    times = [str(t) for t in f["times"]]
    cov = np.isfinite(op)
    eko = cov & (op >= 0.1)
    r_, a_ = P["norst"], P["noand"]
    after = op.copy()
    print("tid   Røst före (ringar 0-4..25-30 km) | efter | andel borttagen skiva | Andøya före")
    for i in range(len(op)):
        rem = fn(eko[i], cov[i], np.nan_to_num(np.where(eko[i], op[i], 0)))
        after[i] = np.where(rem, np.nan, op[i])
        e1 = eko[i] & ~rem

        def ring(pl, e):
            return " ".join(f"{(e & m & cov[i]).sum() / max((m & cov[i]).sum(), 1):.2f}" for m in pl.rings)
        print(times[i][11:16], ring(r_, eko[i]), "|", ring(r_, e1), "|", f"{rem[r_.d < 24].mean():.2f}", "|", ring(a_, eko[i]))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 3, figsize=(15, 10))
    for j, i in enumerate((2, 5, 8)):
        for k, a in enumerate((op[i], after[i])):
            ax[k, j].imshow(a[100:180, 80:160], vmin=0, vmax=2)
            ax[k, j].set_title(f"Røst {'före' if k == 0 else 'efter'} {times[i][11:16]}")
    fig.savefig(rk.TMP / "fall_villkor_rost.png", dpi=50)
    fig, ax = plt.subplots(2, 3, figsize=(15, 10))
    r0, c0 = 15, 160
    for j, i in enumerate((2, 5, 8)):
        for k, a in enumerate((op[i], after[i])):
            ax[k, j].imshow(a[r0:r0 + 70, c0:c0 + 70], vmin=0, vmax=2)
            ax[k, j].set_title(f"Andøya {'före' if k == 0 else 'efter'} {times[i][11:16]}")
    fig.savefig(rk.TMP / "fall_villkor_andoya.png", dpi=50)


if __name__ == "__main__":
    {"trana": trana, "validera": validera, "fall": fall}[sys.argv[1]]()
