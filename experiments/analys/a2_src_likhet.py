"""A2T i src (knep.analys.a2) mot experimentet (experiments/analys/a2.py, system_params("A2T")) på
träningsdagar, och körtiden för en timme på hela rutnätet.

    uv run python experiments/analys/a2_src_likhet.py likhet --dag 2019-06-02 [--domare]
    uv run python experiments/analys/a2_src_likhet.py tid --dag 2019-06-02 [--timme 14]

likhet: A1:s fält för dagen (räknas som i domaren och sparas i /data/analys/a2/a1falt_traning/), sedan A2T
med alla mätare för alla 24 timmar med båda versionerna; största skillnaden per upplösning. Med --domare
dessutom domaren (korsvalideringen i grupper) med båda och en jämförelse av siffrorna. Bara träningsdagar
(kontrolleras); testdelen läses aldrig. Resultatet i /data/analys/a2/src_likhet/<dag>.json.
"""

from __future__ import annotations

import argparse
import gc
import importlib.util
import json
import resource
import sys
import time
import tracemalloc
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("analys_a2", HERE / "a2.py")
E = importlib.util.module_from_spec(spec)
sys.modules["analys_a2"] = E
spec.loader.exec_module(E)
D = E.D

from knep.analys import a2 as S  # noqa: E402

OUT = Path("/data/analys/a2")


def _a1(day_s):
    """(dag, grid, kvart, timme) för en träningsdag; A1 sparas som float16 och läses som float32 (som
    experimentets valideringsfält)."""
    assert day_s in D.days("traning"), "bara träningsdagar"
    p = OUT / "a1falt_traning" / f"{day_s}.npz"
    rd = D.Radardag(day_s)
    dag = D.build_dag(day_s, rd)
    grid = rd.grid
    if not p.exists():
        t = time.time()
        kv, tm = D.A1(rd).falt(None, None)
        p.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(p, kvart=kv.astype(np.float16), timme=tm.astype(np.float16))
        print(day_s, "A1", f"{time.time() - t:.0f} s", flush=True)
        del kv, tm
    del rd
    gc.collect()
    z = np.load(p)
    return dag, grid, z["kvart"].astype(np.float32), z["timme"].astype(np.float32)


class SrcA2T:
    """src-versionen med experimentets gränssnitt (falt(dag, (kvart, timme))) för domaren."""

    namn = "A2T_src"
    matare = True

    def __init__(self, kv1, tm1, model: S.A2T):
        self.kv1, self.tm1, self.m = kv1, tm1, model

    def falt(self, dag, matare, hours=range(24)):
        mq, mh = matare
        kv = np.full(self.kv1.shape, np.nan, np.float32)
        tm = np.full(self.tm1.shape, np.nan, np.float32)
        for hour in hours:
            win = (mh.t <= hour) & (mh.t > hour - S.TIMME["WIN"])
            fon = S.Matare(mh.r[win], mh.c[win], mh.mm[win], self.tm1[mh.t[win], mh.r[win], mh.c[win]])
            th = mh.t == hour
            tim = S.Matare(mh.r[th], mh.c[th], mh.mm[th])
            kvm = [S.Matare(mq.r[mq.t == t], mq.c[mq.t == t], mq.mm[mq.t == t]) for t in range(4 * hour, 4 * hour + 4)]
            tm[hour], kv[4 * hour:4 * hour + 4] = self.m.timme(self.tm1[hour], self.kv1[4 * hour:4 * hour + 4],
                                                                fon, tim, kvm)
        return kv, tm


def _diff(a, b):
    same_nan = bool(np.array_equal(np.isnan(a), np.isnan(b)))
    d = np.abs(np.nan_to_num(a) - np.nan_to_num(b))
    return {"lika": bool(np.array_equal(a, b, equal_nan=True)), "samma_nan": same_nan,
            "storsta_skillnad_mm": float(d.max()), "rutor_olika": int((d > 0).sum()),
            "summa_mm": float(np.nansum(b))}


def _jfr_json(a, b, path=""):
    """Alla tal i domarens resultat som skiljer sig (sökväg, a, b)."""
    out = []
    if isinstance(a, dict):
        for k in a:
            out += _jfr_json(a[k], b.get(k), f"{path}/{k}")
    elif isinstance(a, list):
        for i, (x, y) in enumerate(zip(a, b)):
            out += _jfr_json(x, y, f"{path}[{i}]")
    elif a != b and not (isinstance(a, float) and isinstance(b, float) and np.isnan(a) and np.isnan(b)):
        out.append((path, a, b))
    return out


def cmd_likhet(a):
    for day_s in a.dag:
        dag, grid, kv1, tm1 = _a1(day_s)
        rng_e = E.radar_range_km(grid)
        model = S.A2T.fran_grid(grid)
        res = {"dag": day_s, "timmatare": len(dag.timme), "kvartsvarden": len(dag.kvart),
               "radaravstand_lika": bool(np.array_equal(rng_e, model.rng)), "res_km": model.res}
        t = time.time()
        q_e, h_e = E.A2(kv1, tm1, rng_e, E.system_params("A2T")).falt(dag, (dag.kvart, dag.timme))
        t1 = time.time()
        q_s, h_s = SrcA2T(kv1, tm1, model).falt(dag, (dag.kvart, dag.timme))
        t2 = time.time()
        res["alla_matare"] = {"kvart": _diff(q_e, q_s), "timme": _diff(h_e, h_s),
                              "tid_experiment_s": t1 - t, "tid_src_s": t2 - t1}
        print(day_s, json.dumps(res, ensure_ascii=False), flush=True)
        del q_e, h_e, q_s, h_s
        gc.collect()
        if a.domare:
            t = time.time()
            r_e = D.evaluate(E.A2(kv1, tm1, rng_e, E.system_params("A2T")), dag)
            t1 = time.time()
            r_s = D.evaluate(SrcA2T(kv1, tm1, model), dag)
            olika = _jfr_json(r_e, r_s)
            res["domaren"] = {"tal_olika": len(olika), "forsta_olika": olika[:10],
                              "tid_experiment_s": t1 - t, "tid_src_s": time.time() - t1,
                              "experiment": r_e}
            print(day_s, "domaren", len(olika), "tal olika", flush=True)
        p = OUT / "src_likhet" / f"{day_s}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(res, ensure_ascii=False, indent=1))
        del dag, kv1, tm1
        gc.collect()


def _rss_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def cmd_tid(a):
    day_s = a.dag[0]
    dag, grid, kv1, tm1 = _a1(day_s)
    hour = a.timme
    mq, mh = dag.kvart, dag.timme
    t = time.time()
    model = S.A2T.fran_grid(grid)
    t_init = time.time() - t
    win = (mh.t <= hour) & (mh.t > hour - S.TIMME["WIN"])
    fon = S.Matare(mh.r[win], mh.c[win], mh.mm[win], tm1[mh.t[win], mh.r[win], mh.c[win]])
    th = mh.t == hour
    tim = S.Matare(mh.r[th], mh.c[th], mh.mm[th])
    kvm = [S.Matare(mq.r[mq.t == t], mq.c[mq.t == t], mq.mm[mq.t == t]) for t in range(4 * hour, 4 * hour + 4)]
    a1h, a1q = tm1[hour].copy(), kv1[4 * hour:4 * hour + 4].copy()
    del dag, kv1, tm1
    gc.collect()
    rss0 = _rss_mb()
    tider = []
    tracemalloc.start()
    for _ in range(a.n):
        t = time.time()
        model.timme(a1h, a1q, fon, tim, kvm)
        tider.append(time.time() - t)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    res = {"dag": day_s, "timme": hour, "rutnat": list(model.shape), "timmatare": len(tim),
           "fonster": len(fon), "kvartsvarden": sum(len(m) for m in kvm),
           "init_s (radaravstånd och rutnät)": t_init, "tider_s": tider, "median_s": float(np.median(tider)),
           "topp_numpy_mb (tracemalloc)": peak / 2 ** 20, "maxrss_fore_mb": rss0, "maxrss_efter_mb": _rss_mb()}
    print(json.dumps(res, ensure_ascii=False, indent=1), flush=True)
    p = OUT / "src_likhet" / f"tid_{day_s}_{hour}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(res, ensure_ascii=False, indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["likhet", "tid"])
    ap.add_argument("--dag", nargs="+", required=True)
    ap.add_argument("--domare", action="store_true")
    ap.add_argument("--timme", type=int, default=14)
    ap.add_argument("--n", type=int, default=5)
    a = ap.parse_args()
    {"likhet": cmd_likhet, "tid": cmd_tid}[a.cmd](a)


if __name__ == "__main__":
    main()
