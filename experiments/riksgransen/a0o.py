"""A0O: domarens A0 med OPERA där SMHI är torr inom zonen med svensk stråle över H km
(composite.layer_far), bedömd med analysens domare (experiments/analys/domare.py).

    uv run python experiments/riksgransen/a0o.py kor --H 3 [--regel torr] 2019-03-08 ...
    uv run python experiments/analys/domare.py tabell A0O --mot A0                         alla mätare
    uv run python experiments/analys/domare.py tabell A0O --mot A0 --ut /data/riksgransen/domare_zon   bara zonens mätare

OPERA finns i arkivet bara var 15:e minut före 2024, så varje 5-minutersbild får OPERA från
närmaste kvart (högst 5 minuter bort; /data/riksgransen/opera15/). I drift finns OPERA var 5:e
minut. Regeln läggs på A0:s bilder efter utfyllnaden (composite.fill_gaps); i drift kommer den
före. Det skiljer bara där SMHI saknar data i zonen och utfyllnaden flyttar in värden, och där
tar drift ändå OPERA (composite.layer). Inget annat i A0 ändras.

`kor` räknar A0 och A0O för dagen ur samma bilder och skriver
  /data/analys/domare_v2/A0O/<dag>.json         (domarens dagfil, alla mätare)
  /data/riksgransen/domare_zon/{A0,A0O}/<dag>.json  (samma summor bara för mätarna i zonen; en
                                                    diagnostik, inte en ändring av domens regel)
och kontrollerar att A0 blir exakt domarens befintliga dagfil.
"""

from __future__ import annotations

import argparse
import gc
import importlib.util
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import zon  # noqa: E402
from knep.analys import composite  # noqa: E402

_spec = importlib.util.spec_from_file_location("analys_domare", HERE.parent / "analys" / "domare.py")
domare = importlib.util.module_from_spec(_spec)
sys.modules["analys_domare"] = domare
_spec.loader.exec_module(domare)

ZON_OUT = zon.OUT / "domare_zon"


def opera_index(k: int) -> int:
    """OPERA-bilden (var 15:e minut från 00:00 − 30 min) närmast Radardag-bilden k (var 5:e minut)."""
    return int(np.floor(k / 3 + 0.5))


class A0O(domare.A0):
    namn = "A0O"
    matare = False
    H = 3.0
    regel = "torr"

    def falt(self, dag, matare):
        fr = self.frames()  # A0
        z = zon.load_opera_day(self.rd.day_s)
        if z is None:
            raise FileNotFoundError(f"OPERA saknas för {self.rd.day_s}")
        _, v = z
        far = composite.far_zone(zon.grid_of(self.rd.grid), self.H)
        src = np.zeros(fr.shape[1:], np.uint8)
        self.changed = 0
        for k in range(len(fr)):
            o = zon.decode(v[opera_index(k)])
            new, _ = composite.layer_far(fr[k], src, o, composite.SOURCE_OPERA, far, mode=self.regel)
            self.changed += int((np.isfinite(fr[k]) & (new != fr[k])).sum())
            fr[k] = new
        return domare.sums(fr[domare.Radardag.PRE + 1:])


domare.SYSTEMS["A0O"] = A0O


def zone_dag(dag, far):
    """Samma dag med bara mätarna i zonen."""
    k = dag.kvart.subset(far[dag.kvart.r, dag.kvart.c])
    t = dag.timme.subset(far[dag.timme.r, dag.timme.c])
    return domare.Dag(dag.day, dag.shape, k, t, dag.elev, dag.lovart, dag.folds)


def kor(a):
    A0O.H, A0O.regel = a.H, a.regel
    for d in a.dagar:
        assert d in domare.days("validering") + domare.days("traning")
        out = domare.OUT / "A0O" / f"{d}.json"
        if out.exists() and not a.om:
            continue
        t = time.time()
        rd = domare.Radardag(d)
        dag = domare.build_dag(d, rd)
        far = composite.far_zone(zon.grid_of(rd.grid), a.H)
        dz = zone_dag(dag, far)
        s = A0O(rd)
        fr = s.frames()
        q0, h0 = domare.sums(fr[domare.Radardag.PRE + 1:])
        r0 = domare.evaluate_fields(dag, q0, h0)
        z0 = domare.evaluate_fields(dz, q0, h0)
        del q0, h0
        old = domare.OUT / "A0" / f"{d}.json"
        if old.exists():
            same = json.loads(json.dumps(r0)) == json.loads(old.read_text())
            print(d, "A0 som domarens dagfil:", same, flush=True)
        q, h = s.falt(dag, None)
        r1 = domare.evaluate_fields(dag, q, h)
        z1 = domare.evaluate_fields(dz, q, h)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(r1))
        for n, r in (("A0", z0), ("A0O", z1)):
            p = ZON_OUT / n / f"{d}.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(r))
        info = {"dag": d, "H": a.H, "regel": a.regel, "andrade_rutbilder": s.changed,
                "zonens_matare_timme": int(len(dz.timme)), "zonens_stationer": sorted(set(int(x) for x in dz.timme.station)),
                "matare_timme": int(len(dag.timme)), "sekunder": round(time.time() - t)}
        (ZON_OUT / f"info_{d}.json").write_text(json.dumps(info))
        print(json.dumps(info), flush=True)
        del rd, dag, dz, s, fr, q, h
        gc.collect()


VARIANTER = {"H2": (2.0, 0.1), "H3": (3.0, 0.1), "H4": (4.0, 0.1), "H2t03": (2.0, 0.3), "H3t03": (3.0, 0.3)}
TR_OUT = zon.OUT / "domare_tr"


def trana(a):
    """Varianterna (H, minsta OPERA i mm/h) på träningsdagarna, ur samma A0-bilder. Skriver
    domarens dagfiler för A0 och varje variant under TR_OUT/alla/ och för zonens mätare (zonen
    för variantens H) under TR_OUT/zon_H<H>/. Valideringen rörs inte."""
    for d in a.dagar:
        assert d in domare.days("traning")
        if (TR_OUT / "alla" / list(VARIANTER)[-1] / f"{d}.json").exists():
            continue
        t = time.time()
        rd = domare.Radardag(d)
        dag = domare.build_dag(d, rd)
        g = zon.grid_of(rd.grid)
        fr = domare.A0(rd).frames()
        k0 = domare.Radardag.PRE + 1
        _, v = zon.load_opera_day(d)
        zones = {h: composite.far_zone(g, h) for h in {h for h, _ in VARIANTER.values()}}
        dz = {h: zone_dag(dag, z) for h, z in zones.items()}
        res = {}
        q, h_ = domare.sums(fr[k0:])
        res["A0"] = (q, h_)

        def write(name, q, hh):
            for sub, dd in [("alla", dag)] + [(f"zon_H{h:g}", dz[h]) for h in zones]:
                p = TR_OUT / sub / name / f"{d}.json"
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(json.dumps(domare.evaluate_fields(dd, q, hh)))
        write("A0", q, h_)
        del q, h_, res
        src = np.zeros(g.shape, np.uint8)
        for name, (H, thr) in VARIANTER.items():
            def interval(i, H=H, thr=thr):
                k = k0 + i
                o = zon.decode(v[opera_index(k)])
                return composite.layer_far(fr[k], src, o, composite.SOURCE_OPERA, zones[H], min_extra=thr)[0]
            q, hh = domare.sums_hourly(interval)
            write(name, q, hh)
            del q, hh
        print(d, f"{time.time() - t:.0f} s", flush=True)
        del rd, dag, fr, v
        gc.collect()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["kor", "trana"])
    p.add_argument("dagar", nargs="+")
    p.add_argument("--H", type=float, default=2.0)
    p.add_argument("--regel", default="torr", choices=["torr", "max"])
    p.add_argument("--om", action="store_true", help="räkna om dagar som redan finns")
    p.add_argument("--ut", help="domarens katalog för dagfilerna (standard domare.OUT); zonens filer under <ut>/zon")
    a = p.parse_args()
    if a.ut:
        global ZON_OUT
        domare.set_out(a.ut)
        ZON_OUT = Path(a.ut) / "zon"
    trana(a) if a.cmd == "trana" else kor(a)


if __name__ == "__main__":
    main()
