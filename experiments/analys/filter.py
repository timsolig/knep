"""Ett första filter mot radarns artefakter i A0 (uppgift 4 natten 2026-11-06).

    uv run python experiments/analys/filter.py karta                 klotterkartan och de fasta ekrarna ur träningsdagarna
    uv run python experiments/analys/filter.py kor F1 F2 [--del traning] [--bit 0/2]   genom domaren
    uv run python experiments/analys/domare.py tabell ...            (tabellerna läses som vanligt; se cmd_tabell här)

Filtret tar inte bort rutor som ofta är våta. Det har tre delar:

1. **Klotterrutor** (kartan räknas en gång, bara på träningsdagarna, ur artefakter.py:s summor per dag):
   en ruta är misstänkt om den har eko under torra timmar (alla p7-mätare inom 25 km torra) klart
   oftare än omgivningen och på flera dagar (samma plats i olika väderlägen), eller om den har eko
   oftare än omgivningen och samtidigt hög textur eller är isolerad. Ekofrekvensen ensam och
   stillheten ingår inte, eftersom båda är höga i fjällen (uppgift 1).
2. **Kontrollen bild för bild** på klotterrutorna: ekot tas bort bara om omgivningen (42 km, utan
   klotterrutorna själva) nästan saknar eko. Orografisk nederbörd hänger ihop med det övriga regnet
   och står därför kvar; klotter som syns när det är torrt runt omkring tas bort.
3. **Ekrar**: en smal och lång stråle (samma test som bild.py) tas bort om den ligger inom ±3° från
   solens azimut när solen står mellan −1,5 och +1,5° vid radarn (solstrålar), eller i en av de
   fasta ekrarna som återkommer på minst fem av de 28 träningsdagarna.
   Valfritt (`prickar`): isolerade kantiga prickar var som helst (under 3 % eko inom 42 km och
   |dBZ − grannarnas medel| ≥ 8 dB).

Filtret läser bara den aktuella bilden, kartan och listan, så det går att köra i varje cykel.
Testdelen läses aldrig (domare.days och artefakter.days kontrollerar det).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

import numpy as np
from scipy.ndimage import binary_dilation, median_filter, uniform_filter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "src"))
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location("analys_domare", HERE / "domare.py")
domare = importlib.util.module_from_spec(_spec)
sys.modules["analys_domare"] = domare
_spec.loader.exec_module(domare)

from artefakter import ECHO, OUT as ART, dbz_of  # noqa: E402

warnings.filterwarnings("ignore", category=RuntimeWarning)
FOUT = Path("/data/analys/filter")
KARTA = FOUT / "karta.npz"
EKRAR = FOUT / "ekrar.json"
KARTA_DRIFT = FOUT / "klotter_f4.npz"

# kartans trösklar, satta i förväg ur uppgift 1:s tabeller (inte valda på data här)
TORR_OVER = 0.10      # f_torr minus medianen inom 30 km
TORR_DAGAR = 2        # dagar med eko i mer än 30 % av de torra timmarna
EKO_OVER = 0.10       # f_eko minus medianen inom 30 km
TEX = 6.0             # dB, medlet av |dBZ − grannarnas medel| när det är eko
ISO = 0.05            # andelen eko som är isolerat
WIN = 21              # 42 km, omgivningen
SOL_HOJD = 1.5
SOL_DAZ = 3
EKER_DAGAR = 5        # en fast eker återkommer på minst så många av de 28 träningsdagarna (3 gav 174 strålar, mest regnband)


# ---------------------------------------------------------------- kartan

def build_map() -> None:
    from karta import days_with, derived, load
    tot, per_day = load("traning")
    D = derived(tot)
    nd = days_with(per_day, 0.3, dry=True)
    ft = np.nan_to_num(D["f_torr"])
    torr = (D["overskott_torr"] >= TORR_OVER) & (nd >= TORR_DAGAR) & np.isfinite(D["f_torr"])
    tex = np.nan_to_num(D["tex"])
    iso = np.nan_to_num(D["f_iso"])
    eko = (np.nan_to_num(D["overskott"]) >= EKO_OVER) & ((tex >= TEX) | (iso >= ISO))
    M = binary_dilation(torr | eko, iterations=1)
    FOUT.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(KARTA, klotter=M, torr=torr, eko=eko, f_torr=ft.astype(np.float16))
    print("klotterrutor", int(M.sum()), "torr", int(torr.sum()), "eko+textur/isolering", int(eko.sum()), f"dagar {len(per_day)}")
    hz = np.load(domare.HOJD)["h"]
    print("  över 400 m:", int((M & (hz > 400)).sum()), "av", int((hz > 400).sum()))

    # fasta ekrar: samma radar och azimut (±1°) på minst EKER_DAGAR träningsdagar, utan de nära solen
    from bild import DAG, sun  # noqa: F401
    tr = set(domare.days("traning"))
    by = defaultdict(set)
    for d in sorted(tr):
        f = DAG / f"{d}.json"
        if not f.exists():
            continue
        for e in json.loads(f.read_text())["ekrar"]:
            if -2 <= e["sol_hojd"] <= 10 and min(abs(e["az"] - e["sol_az"]) % 360, 360 - abs(e["az"] - e["sol_az"]) % 360) <= 3:
                continue
            by[(e["radar"], e["az"])].add(d)
    fixed = defaultdict(list)
    for (r, a), ds in by.items():
        n = len(set().union(*(by.get((r, (a + k) % 360), set()) for k in (-1, 0, 1))))
        if n >= EKER_DAGAR:
            fixed[r].append(a)
    fixed = {r: sorted(v) for r, v in fixed.items()}
    EKRAR.write_text(json.dumps(fixed, indent=1))
    print("fasta ekrar", {r: len(v) for r, v in fixed.items()})


# ---------------------------------------------------------------- filtret

class Filter:
    def __init__(self, grid, kontext: float = 0.03, karta: bool = True, ekrar: bool = True, prickar: bool = False,
                 klotter: np.ndarray | None = None, fasta: dict | None = None, geo: dict | None = None,
                 utvidgad: bool = True):
        """klotter, fasta och geo ges i testerna; annars läses kartan och listan ur FOUT och
        strålarnas geometri räknas ur rutnätet. utvidgad=False tar kartan utan utvidgningen med
        en ruta, alltså bara rutorna som själva uppfyller kriterierna."""
        self.kontext, self.use_karta, self.use_ekrar, self.prickar = kontext, karta, ekrar, prickar
        if klotter is None:
            z = np.load(KARTA)
            klotter = z["klotter"] if utvidgad else (z["torr"] | z["eko"])
        self.M = klotter
        assert self.M.shape == grid.shape
        if geo is None and ekrar:
            from bild import geometry
            geo = geometry(grid)
        self.geo = geo or {}
        if fasta is None and ekrar:
            fasta = json.loads(EKRAR.read_text())
        self.fixed = {r: np.array(v) for r, v in (fasta or {}).items()}
        self.removed = 0

    def _spokes(self, echo, cov, t) -> np.ndarray:
        """Bool-karta över rutor i strålar som ska bort (solstrålar och fasta ekrar)."""
        from bild import NB, sun
        out = np.zeros(echo.size, bool)
        ef, cf = echo.ravel(), cov.ravel()
        for code, (idx, key, near, lat, lon) in self.geo.items():
            saz, sel = sun(t, lat, lon)
            cand = np.zeros(NB, bool)
            if abs(sel) <= SOL_HOJD:
                a0 = int(round(saz))
                cand[[(a0 + k) % NB for k in range(-SOL_DAZ, SOL_DAZ + 1)]] = True
            if code in self.fixed:
                for a in self.fixed[code]:
                    cand[[(a + k) % NB for k in (-1, 0, 1)]] = True
            if not cand.any():
                continue
            e = np.bincount(key, ef[idx], NB * 4).reshape(NB, 4)
            n = np.bincount(key, cf[idx], NB * 4).reshape(NB, 4)
            fb = np.where(n >= 3, e / np.maximum(n, 1), np.nan)
            tot = np.where(n.sum(1) >= 20, e.sum(1) / np.maximum(n.sum(1), 1), np.nan)
            side = np.stack([np.roll(tot, s) for s in (*range(3, 11), *range(-10, -2))])
            med = np.nanmedian(side, 0)
            hit = cand & (tot >= 0.4) & ((fb >= 0.25).sum(1) >= 3) & (med <= 0.1)
            if hit.any():
                beams = np.flatnonzero(hit)
                out[idx[np.isin(key // 4, beams)]] = True
        return out.reshape(echo.shape)

    def apply(self, rain: np.ndarray, t) -> np.ndarray:
        cov = np.isfinite(rain)
        r0 = np.nan_to_num(rain, nan=0.0)
        echo = cov & (r0 >= ECHO)
        if not echo.any():
            return rain
        kill = np.zeros(rain.shape, bool)
        if self.use_karta:
            e_out = uniform_filter((echo & ~self.M).astype(np.float32), WIN)
            c_out = uniform_filter((cov & ~self.M).astype(np.float32), WIN)
            frac = e_out / np.maximum(c_out, 1e-3)
            kill |= self.M & echo & (frac < self.kontext)
        if self.prickar:
            dbz = dbz_of(rain)
            tex = np.abs(dbz - (uniform_filter(dbz, 3) * 9 - dbz) / 8)
            frac_all = uniform_filter(echo.astype(np.float32), WIN)
            kill |= echo & (tex >= 8) & (frac_all < 0.03)
        if self.use_ekrar:
            kill |= self._spokes(echo, cov, t) & echo
        if not kill.any():
            return rain
        self.removed += int(kill.sum())
        out = rain.copy()
        out[kill] = 0.0
        return out


VARIANTS = {
    "F0": dict(karta=False, ekrar=True),                 # bara ekrarna
    "F1": dict(kontext=0.03, karta=True, ekrar=True),
    "F2": dict(kontext=0.10, karta=True, ekrar=True),
    "F3": dict(kontext=0.03, karta=True, ekrar=True, prickar=True),
    # försök 2: som F1 men utan utvidgningen (nästa steg 2 i försök 1:s rapport)
    "F4": dict(kontext=0.03, karta=True, ekrar=True, utvidgad=False),
}


def make_system(name: str, kw: dict):
    class AF(domare.A0):
        namn = name
        matare = False

        def falt(self, dag, matare):
            fr = self.frames()
            rd = self.rd
            flt = Filter(rd.grid, **kw)
            k0 = domare.Radardag.PRE + 1
            # bilden gäller de fem minuterna före rd.times[k]; en timme i taget för minnets skull
            out = domare.sums_hourly(lambda i: flt.apply(fr[k0 + i], rd.times[k0 + i]), np.float32)
            self.removed = flt.removed
            return out
    AF.__name__ = name
    return AF


for _n, _kw in VARIANTS.items():
    domare.SYSTEMS[_n] = make_system(_n, _kw)


KEY_ROWS = [("timme/alla", "falskt vid torr mätare"), ("kvart/alla", "falskt vid torr mätare"),
            ("timme/over400", "falskt vid torr mätare"), ("timme/lovart", "falskt vid torr mätare"),
            ("timme/alla", "kvot summa"), ("timme/over400", "kvot summa"), ("timme/lovart", "kvot summa"),
            ("kvart/over400", "kvot summa"), ("kvart/lovart", "kvot summa"),
            ("timme/alla", "CSI 0.5"), ("kvart/alla", "CSI 0.5"), ("timme/over400", "CSI 0.5"), ("timme/lovart", "CSI 0.5"),
            ("timme/alla", "MAE")]


def cmd_urval(a) -> None:
    """Regeln, bestämd innan träningen kördes: bland varianterna som inte är sämre i något mått för
    falska ekon eller terrängen (domarens verdict, samre_i tom) väljs den med störst minskning av
    kartmåttet (rutor med eko i över hälften av de torra timmarna). Lika: den med minst ingrepp (F0 < F1 ...)."""
    base = domare.load_results("A0", a.del_)
    res = {}
    for n in a.system or list(VARIANTS):
        r = domare.load_results(n, a.del_)
        if not r:
            continue
        tab = domare.table(r, base, B=1000)
        v = domare.verdict(tab)
        rut = tab["rutor"]["rutor med eko i över hälften av de torra timmarna, per dag"]
        res[n] = {"dagar": len(set(r) & set(base)), "dom": v, "rutor": rut,
                  "rader": {f"{k} {m}": tab[k][m] for k, m in KEY_ROWS}}
        print(f"\n{n} ({res[n]['dagar']} dagar): sämre i {v['samre_i']}, bättre i {v['battre_i']}")
        print(f"  rutor {rut['varde']:.1f} mot {rut['bas']:.1f}, {rut['diff']:+.2f} ({rut['lo']:+.2f} till {rut['hi']:+.2f})")
        for k, m in KEY_ROWS:
            x = tab[k][m]
            print(f"  {k:14s} {m:24s} {x['varde']:.4f} mot {x['bas']:.4f}  {x['diff']:+.4f} ({x['lo']:+.4f} till {x['hi']:+.4f})")
    ok = [n for n in res if not res[n]["dom"]["samre_i"]]
    val = max(ok, key=lambda n: (res[n]["rutor"]["diff"], -list(VARIANTS).index(n))) if ok else None
    print("\nvalt:", val)
    FOUT.mkdir(parents=True, exist_ok=True)
    namn = f"urval_{a.del_}" + ("_" + "_".join(a.system) if a.system else "")
    (FOUT / f"{namn}.json").write_text(json.dumps({"valt": val, "varianter": res}, ensure_ascii=False, indent=1, default=float))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cmd", choices=["karta", "karta_drift", "kor", "tabell", "urval"])
    p.add_argument("system", nargs="*")
    p.add_argument("--del", dest="del_", default="validering", choices=["validering", "traning"])
    p.add_argument("--dag")
    p.add_argument("--mot")
    p.add_argument("--dagar", nargs="*", help="flera dagar i följd (i stället för --dag)")
    p.add_argument("--bit", default="0/1")
    p.add_argument("--ut", help=f"domarens katalog för dagfiler och tabeller (standard {domare.OUT})")
    a = p.parse_args()
    domare.set_out(a.ut)
    if a.cmd == "karta":
        build_map()
    elif a.cmd == "karta_drift":
        # F4:s karta (utan utvidgning) i formen som src/knep/analys/klotter.py läser
        z = np.load(KARTA)
        m = z["torr"] | z["eko"]
        np.savez_compressed(KARTA_DRIFT, klotter=m)
        print(KARTA_DRIFT, int(m.sum()), "rutor")
    elif a.cmd == "kor":
        for d in a.dagar or [a.dag]:
            a.dag = d
            domare.cmd_kor(a)
    elif a.cmd == "urval":
        cmd_urval(a)
    else:
        domare.cmd_tabell(a)


if __name__ == "__main__":
    main()
