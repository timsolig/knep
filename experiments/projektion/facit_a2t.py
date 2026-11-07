"""Kedjan och persistensen mot tre facit på träningsdagarna: radarn (A0), A2T och mätarna (uppgift 0005).

    uv run python experiments/projektion/facit_a2t.py analys --dag 2020-07-24 [...]
    uv run python experiments/projektion/facit_a2t.py kedja --dag 2020-07-24 [...]
    uv run python experiments/projektion/facit_a2t.py summera [--B 2000]

En diagnos, inget val: ingen domare och inget system ändras.

Dagarna: de träningsdagar (experiments/projektion/traning.json, genom analysens domare.days("traning"),
som kontrollerar att ingen testdag finns med) där analysens domare redan har A1
(/data/analys/domare/A1/<dag>.json), 15 av 28. Validering och test läses inte, inte heller deras mätare.

analys  A0 (SMHI:s komposit med utfyllnad, som analysens domare), A1 och A2T (knep.analys.a2, samma
        konstanter som i drift, med A1 och alla timmätare p7 och kvartsmätare p14 för dagen) per timme.
        A2T räknas dessutom en gång per grupp i korsvalideringen (domarens fem grupper om 100 km,
        mätarna utanför gruppen och mer än 25 km från den), så att A2T kan bedömas mot mätare den inte
        har sett. Sparas i UT/analys/<dag>.npz: A0 och A2T i block om 2 (4 km, verify.block), värdena
        i mätarnas rutor och masken eko90 (rutor med eko i över 90 % av dagens bilder).
kedja   Kedjan som läget traning i projektionens domare (KedjaOm: model.Chain(None), utan MEPS, utan
        extremmodell och volymkorrektion, platskartan uppvärmd 90 min, rörelsecachen under
        /data/projektion/cache/rorelse/2km/) för utgåvorna 03, 06, ..., 18 UTC, timsummorna +1 till +5 h
        (medlet av kvartarna 4(k−1) till 4k−1, kodade som driftens värdefil). Sparas i UT/kedja/<dag>.npz
        (float16, 2 km).
summera Måtten för kedjan och persistensen (A0:s timsumma som slutar vid utgåvan) mot radarn (A0), A2T
        och mätarna (p7 i mätarens ruta, 2 km) per ledtid, utan mask och utan rutorna i F4:s
        klotterkarta (/data/analys/filter/klotter_f4.npz, block om 2 där någon ruta är klotter) eller i
        eko90. Dessutom A0, A1, A2T och A2T i korsvalidering mot mätarna. Skillnaden kedjan minus
        persistensen med 95 %-intervall från bootstrap över dagarna. Till
        experiments/projektion/results/facit_a2t.json.

Utgåvorna 03 till 18 UTC är de var 3:e timme där alla fem målen (timmarna som slutar 04:00 till 23:00)
och persistensen ligger inom dagen, så att varje ledtid har samma utgåvor.

Kartmåtten (4 km, de rutor där A0, A2T, persistensen och kedjan alla finns, samma för båda facit): CSI
vid 1 och 5 mm, FSS vid 1 och 5 mm med fönster 10 och 30 km (3 och 7 block, andelarna bara ur rutorna i
masken som verify.fss_many), summakvoten och MAE.
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import gc
import importlib.util
import json
import shutil
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


AD = _load("analys_domare", ROOT / "experiments/analys/domare.py")   # analysens domare

UT = Path("/data/projektion/facit_a2t")
A1_DOMARE = Path("/data/analys/domare/A1")
A1_SPARAD = Path("/data/analys/a2/a1falt_traning")     # A1 för tre träningsdagar ur uppgift 0003
KLOTTER = Path("/data/analys/filter/klotter_f4.npz")
RESULT = HERE / "results" / "facit_a2t.json"

ISSUES = [3, 6, 9, 12, 15, 18]   # UTC
LEADS = 5
THR = (1.0, 5.0)
FSS_KM = (10.0, 30.0)
KM = 4.03                        # blockets sida (2 x 2,015 km)
MASKS = ("alla", "utan_f4", "utan_eko90")
MIN_FREE_GB = 3.0


def dagar() -> list[str]:
    tr = AD.days("traning")  # kontrollerar att ingen testdag finns med
    return [d for d in tr if (A1_DOMARE / f"{d}.json").exists()]


def _check(day: str) -> None:
    assert day in dagar(), f"{day} är inte en träningsdag med A1"


def _disk() -> None:
    free = shutil.disk_usage("/data").free / 2 ** 30
    if free < MIN_FREE_GB:
        raise SystemExit(f"bara {free:.1f} GB ledigt på /data, avbryter")


def block(x: np.ndarray) -> np.ndarray:
    """Medel av 2 x 2 rutor över de två sista axlarna (verify.block), NaN om någon saknas."""
    h, w = x.shape[-2] // 2, x.shape[-1] // 2
    y = x[..., :2 * h, :2 * w].astype(np.float32)
    return y.reshape(*x.shape[:-2], h, 2, w, 2).mean(axis=(-3, -1))


# ---------------------------------------------------------------- analysen

def cmd_analys(a) -> None:
    from knep.analys import a2 as S
    for day in a.dag:
        _check(day)
        _disk()
        p = UT / "analys" / f"{day}.npz"
        if p.exists():
            print(day, "analys finns", flush=True)
            continue
        t0 = time.time()
        rd = AD.Radardag(day)
        grid = rd.grid
        dag = AD.build_dag(day, rd)
        have = np.isfinite(rd.rain[AD.Radardag.PRE + 1:])
        eko90 = ((rd.rain[AD.Radardag.PRE + 1:] > 0) & have).sum(0) > 0.9 * np.maximum(have.sum(0), 1)
        eko90 &= have.sum(0) >= 0.5 * have.shape[0]
        del have
        sp = A1_SPARAD / f"{day}.npz"
        a0 = AD.A1(rd)   # frames() är A0 (utfyllnaden görs en gång), falt() är A1 ur samma bilder
        _, tm0 = AD.sums(a0.frames()[AD.Radardag.PRE + 1:])
        if sp.exists():
            z = np.load(sp)
            kv1, tm1 = z["kvart"].astype(np.float32), z["timme"].astype(np.float32)
        else:
            kv1, tm1 = a0.falt(None, None)
        t_a1 = time.time() - t0
        del rd, a0
        gc.collect()
        mq, mh = dag.kvart, dag.timme
        model = S.A2T.fran_grid(grid)

        def a2t(mq, mh, hours):
            out = np.full(tm1.shape, np.nan, np.float32)
            for hour in hours:
                win = (mh.t <= hour) & (mh.t > hour - S.TIMME["WIN"])
                fon = S.Matare(mh.r[win], mh.c[win], mh.mm[win], tm1[mh.t[win], mh.r[win], mh.c[win]])
                th = mh.t == hour
                tim = S.Matare(mh.r[th], mh.c[th], mh.mm[th])
                kvm = [S.Matare(mq.r[mq.t == q], mq.c[mq.t == q], mq.mm[mq.t == q]) for q in range(4 * hour, 4 * hour + 4)]
                out[hour], _ = model.timme(tm1[hour], kv1[4 * hour:4 * hour + 4], fon, tim, kvm)
            return out

        t1 = time.time()
        hours = range(24)
        tm2 = a2t(mq, mh, hours)
        t_a2 = time.time() - t1
        # korsvalideringen: A2T utan gruppens mätare, bara för timmarna som bedöms
        need = range(ISSUES[0], ISSUES[-1] + LEADS)
        g = mh
        fold = dag.folds[g.r, g.c]
        cv = np.full(len(g), np.nan, np.float32)
        for k in range(AD.FOLDS):
            q_k, h_k = dag.training(k)
            f = a2t(q_k, h_k, need)
            sel = fold == k
            cv[sel] = f[g.t[sel], g.r[sel], g.c[sel]]
            del f
        t_cv = time.time() - t1 - t_a2
        UT.joinpath("analys").mkdir(parents=True, exist_ok=True)
        # A0 i alla mätarrutor för alla timmar (persistensen vid mätaren)
        cells, cell = np.unique(np.stack([g.r, g.c], 1), axis=0, return_inverse=True)
        np.savez_compressed(
            p, a0=block(tm0), a2=block(tm2), eko90=eko90,
            cell_a0=tm0[:, cells[:, 0], cells[:, 1]], g_cell=cell.ravel(),
            g_station=g.station, g_r=g.r, g_c=g.c, g_t=g.t, g_mm=g.mm, g_fold=fold,
            g_a0=tm0[g.t, g.r, g.c], g_a1=tm1[g.t, g.r, g.c], g_a2=tm2[g.t, g.r, g.c], g_a2cv=cv,
            tid=np.array([t_a1, t_a2, t_cv]))
        print(day, f"A0+A1 {t_a1:.0f} s, A2T {t_a2:.0f} s, korsvalidering {t_cv:.0f} s, mätartimmar {len(g)}", flush=True)
        del kv1, tm1, tm0, tm2, dag
        gc.collect()


# ---------------------------------------------------------------- kedjan

def cmd_kedja(a) -> None:
    PD = _load("projektion_domare", HERE / "domare.py")
    from knep import render
    for day in a.dag:
        _check(day)
        _disk()
        p = UT / "kedja" / f"{day}.npz"
        if p.exists():
            print(day, "kedja finns", flush=True)
            continue
        started = time.monotonic()
        system = PD.KedjaOm()
        system.reset()
        ctx = PD.Ctx(day, 2)
        d0 = datetime.fromisoformat(day).replace(tzinfo=UTC)
        issues = [d0 + timedelta(hours=h) for h in ISSUES]
        warm = set()
        for t in issues:
            warm |= {t - k * PD.STEP for k in range(1, int(PD.WARMUP / PD.STEP) + 1)}
        out, t_fc = {}, []
        for t in sorted(warm | set(issues)):
            ctx.forget(t - timedelta(hours=2))
            if t not in issues:
                system.observe(t, ctx)
                continue
            if ctx.frame(t) is None:
                continue
            s = time.monotonic()
            fc = system.forecast(t, ctx)
            t_fc.append(time.monotonic() - s)
            if fc is None:
                continue
            fc = np.stack([render.decode_values(render.encode_values(x)) for x in fc])
            hrs = np.stack([fc[4 * (k - 1):4 * k].mean(0) for k in range(1, LEADS + 1)])
            out[f"h{t:%H}"] = hrs.astype(np.float16)
        UT.joinpath("kedja").mkdir(parents=True, exist_ok=True)
        np.savez_compressed(p, tid=np.array(t_fc), **out)
        print(day, f"kedja {len(out)} utgåvor på {time.monotonic() - started:.0f} s "
                   f"(prognosen {np.mean(t_fc) if t_fc else 0:.0f} s per utgåva)", flush=True)


# ---------------------------------------------------------------- måtten

def _boxsum(I: np.ndarray, win: int) -> np.ndarray:
    h = win // 2
    P = np.pad(I, [(0, 0)] * (I.ndim - 2) + [(h + 1, h), (h + 1, h)]).cumsum(-2, dtype=np.int32).cumsum(-1, dtype=np.int32)
    return P[..., win:, win:] - P[..., :-win, win:] - P[..., win:, :-win] + P[..., :-win, :-win]


def fss_parts(F: np.ndarray, O: np.ndarray, m: np.ndarray) -> np.ndarray:
    """(tröskel, fönster, [Σ(Pf − Po)², Σ(Pf² + Po²)]) med andelarna bara ur rutorna i m (som verify.fss_many)."""
    out = np.zeros((len(THR), len(FSS_KM), 2))
    M = m.astype(np.uint8)
    for i, thr in enumerate(THR):
        Io = ((O >= thr) & m).astype(np.uint8)
        If = ((F >= thr) & m).astype(np.uint8)
        for j, km in enumerate(FSS_KM):
            win = max(1, round(km / KM)) | 1
            inv = M.astype(np.float32) / np.maximum(_boxsum(M, win), 1)
            po, pf = _boxsum(Io, win) * inv, _boxsum(If, win) * inv
            out[i, j] = [((pf - po) ** 2).sum(dtype=np.float64), (pf * pf + po * po).sum(dtype=np.float64)]
    return out


def ct(f: np.ndarray, o: np.ndarray) -> np.ndarray:
    """(tröskel, [träff, falskt, miss])."""
    return np.array([[((f >= t) & (o >= t)).sum(), ((f >= t) & (o < t)).sum(), ((f < t) & (o >= t)).sum()] for t in THR],
                    np.float64)


def cont(f: np.ndarray, o: np.ndarray) -> np.ndarray:
    """[n, Σf, Σo, Σ|f − o|]."""
    f, o = f.astype(np.float64), o.astype(np.float64)
    return np.array([f.size, f.sum(), o.sum(), np.abs(f - o).sum()])


def day_sums(day: str, f4b: np.ndarray) -> dict:
    """Summorna för en dag: nycklar 'facit/mask/system' -> {'ct': (L, 2, 3), 'cont': (L, 4), 'fss': (L, 2, 2, 2)}
    och 'matare/mask/analys' -> {'ct', 'cont'} för analyserna mot mätarna."""
    za, zk = np.load(UT / "analys" / f"{day}.npz"), np.load(UT / "kedja" / f"{day}.npz")
    a0, a2 = za["a0"], za["a2"]
    eko90b = block(za["eko90"].astype(np.float32)) > 0
    masks2 = {"alla": None, "utan_f4": f4b, "utan_eko90": eko90b}
    g = {k[2:]: za[k] for k in za.files if k.startswith("g_")}
    res: dict = {}

    def acc(key, lead, **parts):
        d = res.setdefault(key, {"ct": np.zeros((LEADS, len(THR), 3)), "cont": np.zeros((LEADS, 4)),
                                 "fss": np.zeros((LEADS, len(THR), len(FSS_KM), 2))})
        for k, v in parts.items():
            d[k][lead] += v

    n_iss = 0
    for hh in ISSUES:
        key = f"h{hh:02d}"
        if key not in zk.files:
            continue
        fc = zk[key].astype(np.float32)      # (5, H, W) 2 km
        P = a0[hh - 1]                       # A0:s timme som slutar vid utgåvan (4 km)
        n_iss += 1
        fcb = block(fc)
        for k in range(1, LEADS + 1):
            idx = hh + k - 1                  # timmen som slutar hh + k
            F = fcb[k - 1]
            base = np.isfinite(a0[idx]) & np.isfinite(a2[idx]) & np.isfinite(P) & np.isfinite(F)
            for mname, mm in masks2.items():
                m = base if mm is None else base & ~mm
                if m.sum() < 50:
                    continue
                for fname, O in (("radar", a0[idx]), ("a2t", a2[idx])):
                    for sname, X in (("kedja", F), ("persistens", P)):
                        acc(f"{fname}/{mname}/{sname}", k - 1, ct=ct(X[m], O[m]), cont=cont(X[m], O[m]),
                            fss=fss_parts(np.nan_to_num(X), np.nan_to_num(O), m))
            # mätarna i sina rutor (2 km); persistensen ur A0 i mätarens ruta för timmen hh
            sel = g["t"] == idx
            r, c, mm_g = g["r"][sel], g["c"][sel], g["mm"][sel]
            fk = fc[k - 1][r, c]
            pk = za["cell_a0"][hh - 1, g["cell"][sel]]
            ok = np.isfinite(fk) & np.isfinite(pk) & np.isfinite(g["a0"][sel]) & np.isfinite(g["a2"][sel])
            for mname, mm in masks2.items():
                mk = ok if mm is None else ok & ~mm[np.minimum(r // 2, mm.shape[0] - 1), np.minimum(c // 2, mm.shape[1] - 1)]
                for sname, X in (("kedja", fk), ("persistens", pk)):
                    acc(f"matare/{mname}/{sname}", k - 1, ct=ct(X[mk], mm_g[mk]), cont=cont(X[mk], mm_g[mk]))
                for an in ("a0", "a1", "a2", "a2cv"):
                    v = g[an][sel]
                    acc(f"matare/{mname}/analys_{an}", k - 1, ct=ct(v[mk], mm_g[mk]), cont=cont(v[mk], mm_g[mk]))
    res["_utgavor"] = n_iss
    return res


def scores(d: dict) -> dict:
    out = {}
    a, b, c = d["ct"][..., 0], d["ct"][..., 1], d["ct"][..., 2]
    out["csi"] = a / np.maximum(a + b + c, 1)
    n, sf, so, ae = d["cont"].T
    out["kvot"] = sf / np.maximum(so, 1e-9)
    out["mae"] = ae / np.maximum(n, 1)
    if "fss" in d:
        out["fss"] = 1 - d["fss"][..., 0] / np.maximum(d["fss"][..., 1], 1e-12)
    return out


def _sum(per_day: list[dict], key: str) -> dict:
    keys = per_day[0][key].keys()
    return {k: sum(pd[key][k] for pd in per_day) for k in keys}


def cmd_summera(a) -> None:
    f4 = np.load(KLOTTER)["klotter"]
    f4b = block(f4.astype(np.float32)) > 0
    days = [d for d in dagar() if (UT / "analys" / f"{d}.npz").exists() and (UT / "kedja" / f"{d}.npz").exists()]
    per = {}
    for d in days:
        per[d] = day_sums(d, f4b)
        print(d, "utgåvor", per[d]["_utgavor"], flush=True)
    rng = np.random.default_rng(0)
    nd = len(days)
    boots = rng.integers(0, nd, size=(a.B, nd))
    plist = [per[d] for d in days]
    res = {"dagar": days, "utgavor": {d: per[d]["_utgavor"] for d in days}, "trosklar_mm": THR, "fss_km": FSS_KM,
           "utgavotider_utc": ISSUES, "masker": MASKS, "f4_block": int(f4b.sum()), "B": a.B, "tabeller": {}}
    groups = sorted({k.rsplit("/", 1)[0] for k in plist[0] if not k.startswith("_")})
    for gname in groups:
        systems = sorted({k.rsplit("/", 1)[1] for k in plist[0] if k.startswith(gname + "/")})
        tab = {}
        est = {s: scores(_sum(plist, f"{gname}/{s}")) for s in systems}
        # bootstrap: summorna per dag i en matris per system och mått
        stacks = {s: {k: np.stack([pd[f"{gname}/{s}"][k] for pd in plist]) for k in plist[0][f"{gname}/{s}"]} for s in systems}
        bs = {s: [] for s in systems}
        for idx in boots:
            for s in systems:
                bs[s].append(scores({k: v[idx].sum(0) for k, v in stacks[s].items()}))
        for s in systems:
            tab[s] = {}
            for m, v in est[s].items():
                samp = np.stack([b[m] for b in bs[s]])
                tab[s][m] = {"v": np.round(v, 4).tolist(), "lo": np.round(np.percentile(samp, 2.5, 0), 4).tolist(),
                             "hi": np.round(np.percentile(samp, 97.5, 0), 4).tolist()}
            tab[s]["n"] = stacks[s]["cont"].sum(0)[:, 0].astype(int).tolist()
        if "kedja" in systems and "persistens" in systems:
            diff = {}
            for m in est["kedja"]:
                if m == "kvot":   # skillnaden i |ln kvot|: negativ betyder att kedjans mängd ligger närmare facit
                    f = lambda x: np.abs(np.log(np.maximum(x, 1e-9)))  # noqa: E731
                else:
                    f = lambda x: x  # noqa: E731
                v = f(est["kedja"][m]) - f(est["persistens"][m])
                samp = np.stack([f(bk[m]) - f(bp[m]) for bk, bp in zip(bs["kedja"], bs["persistens"])])
                diff["abs_ln_kvot" if m == "kvot" else m] = {
                    "v": np.round(v, 4).tolist(), "lo": np.round(np.percentile(samp, 2.5, 0), 4).tolist(),
                    "hi": np.round(np.percentile(samp, 97.5, 0), 4).tolist()}
            tab["kedja_minus_persistens"] = diff
        res["tabeller"][gname] = tab
    RESULT.parent.mkdir(exist_ok=True)
    out = RESULT if not a.namn else RESULT.with_name(f"facit_a2t_{a.namn}.json")
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print("skrev", out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["analys", "kedja", "summera", "dagar"])
    ap.add_argument("--dag", nargs="+", default=None)
    ap.add_argument("--B", type=int, default=2000)
    ap.add_argument("--namn", default="")
    a = ap.parse_args()
    if a.cmd == "dagar":
        print(" ".join(dagar()))
        return
    if a.dag is None:
        a.dag = dagar()
    {"analys": cmd_analys, "kedja": cmd_kedja, "summera": cmd_summera}[a.cmd](a)


if __name__ == "__main__":
    main()
