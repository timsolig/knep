"""Domaren för analysen: avgör om en analys är bättre än en annan, mot SMHI:s regnmätare.

    uv run python experiments/analys/domare.py kor A0 [--del validering] [--dag 2023-08-08]
    uv run python experiments/analys/domare.py tabell A1 --mot A0 [--del validering]
    uv run python experiments/analys/domare.py kontroll A0 [--dag 2023-08-08]   (gamla måtten oförändrade)

Ett system är en klass med `namn`, `matare` (om det använder regnmätarna) och
`falt(dag, matare) -> (kvart, timme)`: nederbörden i mm per kvart (96, H, W) och per timme
(24, H, W) på radarns rutnät, NaN där analysen saknar data. Kvarten k slutar 00:15 + k·15 min och
timmen h slutar 01:00 + h timmar (UTC), som mätarnas tidsstämplar.

Korsvalideringen: rutnätet delas i block om 100 km som går till FOLDS grupper efter plats
(grupp = (blockrad + 2·blockkolumn) mod 5, så att två block som gränsar till varandra aldrig hör
till samma grupp). Ett system som använder mätare körs en gång per grupp och får bara mätarna
utanför gruppen och mer än BUFFER_KM från den. Fältet som bedöms sätts ihop av rutorna i varje
grupp ur den körning som inte såg gruppen. System utan mätare körs en gång; det sammansatta fältet
är då samma fält, så de bedöms på samma grupper.

Per dag sparas summor (antal, summor, träffar, falska larm) per upplösning och delmängd i
/data/analys/domare_v2/<system>/<dag>.json, så att måtten för en mängd dagar och bootstrap över
dagarna räknas ur summorna. Måtten:

  mängd    kvoten summa(analys)/summa(mätare) över alla perioder ("kvot summa"), samma kvot för
           perioder där mätaren har regn, över 0 mm ("kvot våt"), och för perioder där mätaren
           har över 1, 5 och 10 mm, och MAE (mm per period)
  träff    CSI och FSS vid 0,5, 1 och 5 mm per period. FSS mot punkter: P är andelen rutor över
           tröskeln i ett fönster om FSS_WIN × FSS_WIN rutor (22 km) kring mätaren, O är 0 eller 1
           för mätaren, FSS = 1 − Σ(P − O)² / (ΣP² + ΣO²)
  falska   andelen perioder med analyserat regn (över 0,5 mm per timme, för kvarten 0,125 mm)
           vid mätare som visar 0 mm, och samma där alla mätare inom 25 km visar 0 mm; och per
           dag antalet rutor med eko (över 0,5 mm) i mer än hälften av de torra timmarna (minst
           6 torra timmar, torr = minst en mätare inom 25 km och alla torra)
  terräng  samma mått för mätare över 400 m och för mätartimmar på lovartsidan (rörelsen uppför
           den utjämnade terrängen, minst LOVART_W m per 5 min, i fjällen eller på sydsvenska
           höjdområdet)
  hopp     för timmar där mätaren har alla fyra kvartarna: Σ|kvart(k) − kvart(k−1)| för analysen
           genom samma summa för mätaren (1 betyder att analysen hoppar lika mycket som mätarna)

Regeln (verdict) använder "kvot våt" i stället för "kvot summa" i gruppen mängd (användarens
beslut 2026-11-07, punkt 3): summakvoten räknar också eko vid torra mätare som mängd och belönar
därför för höga toppar och falska ekon så länge radarn i stort är för torr. "kvot summa" står
kvar i tabellerna, och verdict(tab, regel="gammal") ger domen med den gamla regeln, så att
tidigare rapporter går att jämföra. Dagfilerna med de nya summorna (saw, sgw) ligger i
/data/analys/domare_v2/ (OUT, --ut); de gamla i /data/analys/domare/ saknar dem och ger bara
den gamla regeln. Rörelsefälten läses och sparas fortfarande i /data/analys/domare/rorelse/.

Mätarna kontrolleras grovt: värden under 0 eller över 100 mm per timme (60 mm per kvart) tas bort
(p7 och p14 har enstaka värden på hundratusentals mm).

Testdelen i experiments/sverige/dagar.json läses aldrig (days() kontrollerar det).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
from scipy.ndimage import distance_transform_edt, gaussian_filter, uniform_filter
from scipy.signal import fftconvolve
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

OUT = Path("/data/analys/domare_v2")   # dagfiler och tabeller med kvot våt (byts med --ut)
OUT_V1 = Path("/data/analys/domare")   # de gamla dagfilerna och tabellerna, utan kvot våt
RORELSE = OUT_V1 / "rorelse"           # rörelsefälten är desamma för båda
RADAR = Path("/data/radar")
HOJD = Path("/data/projektion/hojd_2km.npz")
GAUGES = {"timme": Path("/data/bortfall/matare/p7.npz"), "kvart": Path("/data/bortfall/matare/p14.npz")}
RES_KM = 2.0
BLOCK = 50          # rutor, 100 km
FOLDS = 5
BUFFER_KM = 25.0
NEAR_KM = 25.0
FSS_WIN = 11
MAX_MM = {"timme": 100.0, "kvart": 60.0}
ECHO = {"timme": 0.5, "kvart": 0.125}   # 0,5 mm/h
CSI_THR = (0.5, 1.0, 5.0)
AMT_THR = (1.0, 5.0, 10.0)
HIGH_M = 400.0
LOVART_W = 3.0      # m per 5 min
DRY_HOURS_MIN = 6
NPER = {"kvart": 96, "timme": 24}
SUBSETS = ("alla", "over400", "lovart")


# ---------------------------------------------------------------- dagarna

def days(part: str = "validering") -> list[str]:
    """Dagarna i delen ('validering' ur dagar.json eller 'traning' ur traning.json). Aldrig test."""
    dj = json.loads((ROOT / "experiments/sverige/dagar.json").read_text())
    test = {d["day"] for d in dj if d["part"] == "test"}
    if part == "validering":
        out = [d["day"] for d in dj if d["part"] == "validering"]
    elif part == "traning":
        out = [d["day"] for d in json.loads((ROOT / "experiments/projektion/traning.json").read_text())]
    else:
        raise ValueError(f"okänd del {part!r}; testdelen får inte läsas")
    assert not test & set(out)
    return sorted(out)


# ---------------------------------------------------------------- mätarna

@dataclass
class Matare:
    """Mätarvärden för en dag och upplösning: en rad per station och period."""

    station: np.ndarray
    r: np.ndarray       # rad på rutnätet
    c: np.ndarray       # kolumn
    t: np.ndarray       # period 0..95 (kvart) eller 0..23 (timme)
    mm: np.ndarray

    def __len__(self):
        return len(self.mm)

    def subset(self, keep: np.ndarray) -> "Matare":
        return Matare(self.station[keep], self.r[keep], self.c[keep], self.t[keep], self.mm[keep])


def fold_map(shape: tuple[int, int]) -> np.ndarray:
    """Gruppen för varje ruta: block om BLOCK rutor, (blockrad + 2·blockkolumn) mod FOLDS."""
    rr, cc = np.mgrid[0:shape[0], 0:shape[1]]
    return ((rr // BLOCK + 2 * (cc // BLOCK)) % FOLDS).astype(np.int8)


@dataclass
class Dag:
    """Allt domaren och systemen behöver om en dag utom själva analysen."""

    day: str
    shape: tuple[int, int]
    kvart: Matare
    timme: Matare
    elev: np.ndarray                    # m per ruta
    lovart: np.ndarray | None = None    # (24, H, W) bool: rutan ligger på lovartsidan under timmen
    folds: np.ndarray = field(default=None)

    def __post_init__(self):
        if self.folds is None:
            self.folds = fold_map(self.shape)

    def gauges(self, res: str) -> Matare:
        return self.kvart if res == "kvart" else self.timme

    def training(self, k: int) -> tuple[Matare, Matare]:
        """Mätarna ett system får se när grupp k bedöms: utanför gruppen och mer än BUFFER_KM från den."""
        dist = distance_transform_edt(self.folds != k) * RES_KM
        out = []
        for m in (self.kvart, self.timme):
            out.append(m.subset(dist[m.r, m.c] > BUFFER_KM))
        return out[0], out[1]


def _to_rc(lat, lon, grid):
    from pyproj import Transformer
    tr = Transformer.from_crs("EPSG:4326", grid.crs, always_xy=True)
    x, y = tr.transform(np.asarray(lon, float), np.asarray(lat, float))
    c, r = (~grid.transform) * (x, y)
    return np.floor(np.asarray(r)).astype(int), np.floor(np.asarray(c)).astype(int)


def load_gauges(day_s: str, res: str, grid) -> Matare:
    """Mätarna för dagens perioder ur p7 (timme) eller p14 (kvart); andra dagar filtreras bort direkt."""
    z = np.load(GAUGES[res])
    day = datetime.fromisoformat(day_s).replace(tzinfo=UTC)
    t0, t1 = int(day.timestamp()), int((day + timedelta(days=1)).timestamp())
    tt = z["time"]
    keep = (tt > t0) & (tt <= t1)
    st, lat, lon, tt, mm = z["station"][keep], z["lat"][keep], z["lon"][keep], tt[keep], z["mm"][keep]
    ok = np.isfinite(mm) & (mm >= 0) & (mm <= MAX_MM[res])
    st, lat, lon, tt, mm = st[ok], lat[ok], lon[ok], tt[ok], mm[ok]
    r, c = _to_rc(lat, lon, grid)
    h, w = grid.shape
    inside = (r >= 0) & (r < h) & (c >= 0) & (c < w)
    period = 900 if res == "kvart" else 3600
    t = (tt - t0) // period - 1
    m = Matare(st[inside], r[inside], c[inside], t[inside].astype(int), mm[inside].astype(np.float64))
    # en rad per station och period
    _, first = np.unique(np.stack([m.station, m.t]), axis=1, return_index=True)
    return m.subset(np.sort(first))


def lovart_mask(elev: np.ndarray, motion_h: np.ndarray, lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    """(24, H, W) bool: rörelsen går uppför den utjämnade terrängen med minst LOVART_W m per 5 min,
    i fjällen (utjämnad höjd över 300 m) eller på sydsvenska höjdområdet.

    motion_h: (24, 2, H, W) rörelsen i pixlar per 5 min under timmen (x, y som i kedjan)."""
    hs = gaussian_filter(elev.astype(np.float32), 5.0)
    big = gaussian_filter(elev.astype(np.float32), 10.0)
    gy, gx = np.gradient(hs)
    region = (big > 300.0) | ((lat > 56.5) & (lat < 58.5) & (lon > 13.3) & (lon < 16.2) & (big > 120.0))
    w = motion_h[:, 0] * gx[None] + motion_h[:, 1] * gy[None]
    return (w > LOVART_W) & region[None]


# ---------------------------------------------------------------- bedömningen av en dag

def _empty():
    return {"n": 0, "sa": 0.0, "sg": 0.0, "ae": 0.0, "saw": 0.0, "sgw": 0.0,
            **{f"sa{t:g}": 0.0 for t in AMT_THR}, **{f"sg{t:g}": 0.0 for t in AMT_THR},
            **{f"{k}{t:g}": 0.0 for t in CSI_THR for k in ("hit", "mis", "fal", "fpo", "fp2", "fo2")},
            "ndry": 0, "fdry": 0, "ndryo": 0, "fdryo": 0, "ja": 0.0, "jg": 0.0, "nj": 0}


def _dry_area(m: Matare, nper: int) -> np.ndarray:
    """Per rad i m: alla mätare inom NEAR_KM (med den själv) visar 0 mm i perioden."""
    out = np.zeros(len(m), bool)
    for t in range(nper):
        s = np.flatnonzero(m.t == t)
        if len(s) == 0:
            continue
        tree = cKDTree(np.c_[m.r[s], m.c[s]] * RES_KM)
        wet = m.mm[s] > 0
        for i, nb in zip(s, tree.query_ball_point(np.c_[m.r[s], m.c[s]] * RES_KM, NEAR_KM)):
            out[i] = not wet[nb].any()
    return out


def _accumulate(acc: dict, a: np.ndarray, g: np.ndarray, p: dict, dry_area: np.ndarray, res: str):
    acc["n"] += len(a)
    acc["sa"] += float(a.sum())
    acc["sg"] += float(g.sum())
    acc["ae"] += float(np.abs(a - g).sum())
    wet = g > 0
    acc["saw"] += float(a[wet].sum())
    acc["sgw"] += float(g[wet].sum())
    for t in AMT_THR:
        s = g > t
        acc[f"sa{t:g}"] += float(a[s].sum())
        acc[f"sg{t:g}"] += float(g[s].sum())
    for t in CSI_THR:
        fa, ob = a >= t, g >= t
        acc[f"hit{t:g}"] += float((fa & ob).sum())
        acc[f"mis{t:g}"] += float((~fa & ob).sum())
        acc[f"fal{t:g}"] += float((fa & ~ob).sum())
        P, O = p[t], ob.astype(float)
        acc[f"fpo{t:g}"] += float(((P - O) ** 2).sum())
        acc[f"fp2{t:g}"] += float((P ** 2).sum())
        acc[f"fo2{t:g}"] += float((O ** 2).sum())
    dry = g == 0
    echo = a > ECHO[res]
    acc["ndry"] += int(dry.sum())
    acc["fdry"] += int((dry & echo).sum())
    acc["ndryo"] += int(dry_area.sum())
    acc["fdryo"] += int((dry_area & echo).sum())


def evaluate_fields(dag: Dag, kvart: np.ndarray, timme: np.ndarray) -> dict:
    """Summorna för en dag ur de sammansatta fälten (kvart (96, H, W), timme (24, H, W), mm)."""
    out = {}
    fields = {"kvart": kvart, "timme": timme}
    for res, F in fields.items():
        m = dag.gauges(res)
        a = F[m.t, m.r, m.c].astype(np.float64)
        ok = np.isfinite(a)
        m, a = m.subset(ok), a[ok]
        g = m.mm
        # FSS: andelen rutor över tröskeln i fönstret kring varje mätare (NaN räknas som torrt)
        p = {t: np.zeros(len(m)) for t in CSI_THR}
        for t_per in np.unique(m.t):
            s = m.t == t_per
            Fi = np.nan_to_num(F[t_per], nan=0.0)
            for thr in CSI_THR:
                frac = uniform_filter((Fi >= thr).astype(np.float32), FSS_WIN, mode="constant")
                p[thr][s] = frac[m.r[s], m.c[s]]
        dry_area = _dry_area(m, NPER[res])
        high = dag.elev[m.r, m.c] > HIGH_M
        hour_of = m.t if res == "timme" else m.t // 4
        lov = dag.lovart[hour_of, m.r, m.c] if dag.lovart is not None else np.zeros(len(m), bool)
        for name, sel in (("alla", np.ones(len(m), bool)), ("over400", high), ("lovart", lov)):
            acc = _empty()
            _accumulate(acc, a[sel], g[sel], {t: p[t][sel] for t in CSI_THR}, dry_area[sel], res)
            out[f"{res}/{name}"] = acc
    # hoppen mellan kvartarna i timmar där mätaren har alla fyra
    m = dag.kvart
    a = kvart[m.t, m.r, m.c]
    hours = m.t // 4
    key = m.station.astype(np.int64) * 100 + hours
    order = np.lexsort((m.t, key))
    k_s, t_s = key[order], m.t[order]
    uniq, start, cnt = np.unique(k_s, return_index=True, return_counts=True)
    for u, s0, n in zip(uniq, start, cnt):
        if n != 4:
            continue
        idx = order[s0:s0 + 4]
        if not np.all(np.diff(t_s[s0:s0 + 4]) == 1):
            continue
        ai, gi = a[idx], m.mm[idx]
        if not np.isfinite(ai).all() or (gi.max() <= 0 and ai.max() <= 0):
            continue
        ja, jg = float(np.abs(np.diff(ai)).sum()), float(np.abs(np.diff(gi)).sum())
        r, c = m.r[idx[0]], m.c[idx[0]]
        h = int(u % 100)
        subs = ["alla"] + (["over400"] if dag.elev[r, c] > HIGH_M else []) + \
            (["lovart"] if dag.lovart is not None and dag.lovart[h, r, c] else [])
        for name in subs:
            out[f"kvart/{name}"]["ja"] += ja
            out[f"kvart/{name}"]["jg"] += jg
            out[f"kvart/{name}"]["nj"] += 1
    # rutor med eko i mer än hälften av de torra timmarna
    mh = dag.timme
    h, w = dag.shape
    rad = NEAR_KM / RES_KM
    k = int(np.ceil(rad))
    yy, xx = np.mgrid[-k:k + 1, -k:k + 1]
    disk = ((yy ** 2 + xx ** 2) <= rad ** 2).astype(np.float32)
    ndry = np.zeros((h, w), np.int32)
    necho = np.zeros((h, w), np.int32)
    for t in range(24):
        s = mh.t == t
        if not s.any():
            continue
        allg, wet = np.zeros((h, w), np.float32), np.zeros((h, w), np.float32)
        np.add.at(allg, (mh.r[s], mh.c[s]), 1)
        np.add.at(wet, (mh.r[s], mh.c[s]), (mh.mm[s] > 0).astype(np.float32))
        n = np.rint(fftconvolve(allg, disk, mode="same"))
        nw = np.rint(fftconvolve(wet, disk, mode="same"))
        dry = (n >= 1) & (nw == 0) & np.isfinite(timme[t])
        ndry += dry
        necho += dry & (np.nan_to_num(timme[t]) > ECHO["timme"])
    elig = ndry >= DRY_HOURS_MIN
    out["rutor"] = {"eko_torr": int((elig & (necho > 0.5 * ndry)).sum()), "rutor_torr": int(elig.sum())}
    return out


def run_system(system, dag: Dag) -> tuple[np.ndarray, np.ndarray]:
    """Det sammansatta fältet: för system med mätare rutorna i grupp k ur körningen utan grupp k."""
    if not getattr(system, "matare", False):
        return system.falt(dag, None)
    kv = tm = None
    for k in range(FOLDS):
        q, h = system.falt(dag, dag.training(k))
        if kv is None:
            kv, tm = np.full(q.shape, np.nan, np.float32), np.full(h.shape, np.nan, np.float32)
        sel = dag.folds == k
        kv[:, sel], tm[:, sel] = q[:, sel], h[:, sel]
    return kv, tm


def evaluate(system, dag: Dag) -> dict:
    q, h = run_system(system, dag)
    return evaluate_fields(dag, q, h)


# ---------------------------------------------------------------- måtten ur summorna

LOWER, HIGHER, NEAR1 = "lägre", "högre", "nära 1"


def metrics(acc: dict, res: str) -> dict[str, tuple[float, str]]:
    """Måtten ur summerade komponenter: namn -> (värde, vad som är bättre)."""
    def q(a, b):
        return a / b if b > 0 else np.nan
    m = {"kvot summa": (q(acc["sa"], acc["sg"]), NEAR1),
         # dagfiler från före kvot våt saknar saw och sgw: måttet blir NaN och bedöms inte
         "kvot våt": (q(acc.get("saw", 0.0), acc.get("sgw", 0.0)), NEAR1)}
    for t in AMT_THR:
        m[f"kvot >{t:g} mm"] = (q(acc[f"sa{t:g}"], acc[f"sg{t:g}"]), NEAR1)
    m["MAE"] = (q(acc["ae"], acc["n"]), LOWER)
    for t in CSI_THR:
        m[f"CSI {t:g}"] = (q(acc[f"hit{t:g}"], acc[f"hit{t:g}"] + acc[f"mis{t:g}"] + acc[f"fal{t:g}"]), HIGHER)
    for t in CSI_THR:
        m[f"FSS {t:g}"] = (1 - q(acc[f"fpo{t:g}"], acc[f"fp2{t:g}"] + acc[f"fo2{t:g}"]), HIGHER)
    m["falskt vid torr mätare"] = (q(acc["fdry"], acc["ndry"]), LOWER)
    m["falskt där allt inom 25 km är torrt"] = (q(acc["fdryo"], acc["ndryo"]), LOWER)
    if res == "kvart":
        m["hopp, kvot mot mätarna"] = (q(acc["ja"], acc["jg"]), NEAR1)
    return m


GROUPS = {  # vilka mått som hör till vilken del av regeln
    "mängd": ["kvot våt"] + [f"kvot >{t:g} mm" for t in AMT_THR] + ["MAE"],
    "träff": [f"CSI {t:g}" for t in CSI_THR] + [f"FSS {t:g}" for t in CSI_THR],
    "falska": ["falskt vid torr mätare", "falskt där allt inom 25 km är torrt"],
}
# den gamla regeln (före 2026-11-07): summakvoten i stället för kvoten för våta perioder
GROUPS_GAMMAL = dict(GROUPS, mängd=["kvot summa"] + GROUPS["mängd"][1:])


MIN_DAYS = 5  # ett mått bedöms bara om dess nämnare har underlag från minst så många dagar


def _support(name: str) -> list[str]:
    """Komponenterna i måttets nämnare (dagar där de är 0 bidrar inte till måttet)."""
    for t in AMT_THR:
        if name == f"kvot >{t:g} mm":
            return [f"sg{t:g}"]
    for t in CSI_THR:
        if name == f"CSI {t:g}":
            return [f"hit{t:g}", f"mis{t:g}", f"fal{t:g}"]
        if name == f"FSS {t:g}":
            return [f"fp2{t:g}", f"fo2{t:g}"]
    return {"kvot summa": ["sg"], "kvot våt": ["sgw"], "MAE": ["n"], "falskt vid torr mätare": ["ndry"],
            "falskt där allt inom 25 km är torrt": ["ndryo"], "hopp, kvot mot mätarna": ["jg"]}[name]


def _sum(per_day: list[dict]) -> dict:
    out = {}
    for d in per_day:
        for k, acc in d.items():
            o = out.setdefault(k, {kk: 0 for kk in acc})
            for kk, v in acc.items():
                o[kk] = o.get(kk, 0) + v
    return out


def _goodness(v: float, kind: str) -> float:
    """Större är bättre."""
    if kind == HIGHER:
        return v
    if kind == LOWER:
        return -v
    return -abs(np.log(v)) if v > 0 else -np.inf


def table(per_day: dict[str, dict], base: dict[str, dict] | None = None, B: int = 2000, seed: int = 0) -> dict:
    """Måtten för alla dagar, och om base ges skillnaden mot den med 95 %-intervall (bootstrap över dagarna).

    per_day, base: dag -> summorna för dagen. Skillnaden räknas på samma dagar.
    Varje rad: (nyckel, mått) -> {"varde", "bas", "diff", "lo", "hi", "battre": diff i godhet med intervall}.
    """
    names = sorted(per_day if base is None else set(per_day) & set(base))
    tot = _sum([per_day[d] for d in names])
    tot_b = _sum([base[d] for d in names]) if base is not None else None
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(names), size=(B, len(names))) if base is not None else None
    out = {}
    for key in tot:
        if key == "rutor":
            continue
        res = key.split("/")[0]
        mv = metrics(tot[key], res)
        rows = {}
        if base is not None:
            boots, boots_b = [], []
            for b in range(B):
                sel = [names[i] for i in idx[b]]
                boots.append(metrics(_sum([{key: per_day[d][key]} for d in sel])[key], res))
                boots_b.append(metrics(_sum([{key: base[d][key]} for d in sel])[key], res))
            mb = metrics(tot_b[key], res)
        for name, (v, kind) in mv.items():
            row = {"varde": v, "battre": kind,
                   "dagar": int(sum(sum(per_day[d][key].get(c, 0) for c in _support(name)) > 0 for d in names))}
            if base is not None:
                g = np.array([_goodness(x[name][0], kind) - _goodness(y[name][0], kind) for x, y in zip(boots, boots_b)])
                g = g[np.isfinite(g)]
                row.update(bas=mb[name][0], diff=_goodness(v, kind) - _goodness(mb[name][0], kind),
                           lo=float(np.percentile(g, 2.5)) if len(g) else np.nan,
                           hi=float(np.percentile(g, 97.5)) if len(g) else np.nan)
            rows[name] = row
        out[key] = rows
    # rutorna med eko under torra timmar: medel per dag
    cells = np.array([per_day[d]["rutor"]["eko_torr"] for d in names], float)
    row = {"varde": float(cells.mean()), "battre": LOWER}
    if base is not None:
        cb = np.array([base[d]["rutor"]["eko_torr"] for d in names], float)
        diffs = np.array([-(cells[i].mean() - cb[i].mean()) for i in idx])
        row.update(bas=float(cb.mean()), diff=float(-(cells.mean() - cb.mean())),
                   lo=float(np.percentile(diffs, 2.5)), hi=float(np.percentile(diffs, 97.5)))
    out["rutor"] = {"rutor med eko i över hälften av de torra timmarna, per dag": row}
    return out


def verdict(tab: dict, min_days: int = MIN_DAYS, regel: str = "ny") -> dict:
    """Regeln: bättre om något mått för mängd eller träff (kvart eller timme, alla mätare) är bättre
    med intervallet helt över 0, och inget mått för falska ekon eller terrängen är sämre med
    intervallet helt under 0. Intervallen är skillnaden i godhet (större är bättre).

    regel="ny" (standard) tar kvot våt i gruppen mängd, regel="gammal" summakvoten som före
    2026-11-07 (GROUPS_GAMMAL).

    Ett mått bedöms bara om nämnaren har underlag från minst min_days dagar; annars bygger
    intervallet ur bootstrap på en eller ett par händelser och säger inget (min_days=0 bedömer allt)."""
    groups = {"ny": GROUPS, "gammal": GROUPS_GAMMAL}[regel]
    better, worse = [], []

    def ok(row):
        return row.get("dagar", min_days) >= min_days and np.isfinite(row["lo"]) and np.isfinite(row["hi"])

    for res in ("kvart", "timme"):
        for g in ("mängd", "träff"):
            for name in groups[g]:
                row = tab[f"{res}/alla"][name]
                if ok(row) and row["lo"] > 0:
                    better.append(f"{res} {name}")
        for name in groups["falska"]:
            row = tab[f"{res}/alla"][name]
            if ok(row) and row["hi"] < 0:
                worse.append(f"{res} {name}")
        for sub in ("over400", "lovart"):
            for g in ("mängd", "träff", "falska"):
                for name in groups[g]:
                    row = tab[f"{res}/{sub}"][name]
                    if ok(row) and row["hi"] < 0:
                        worse.append(f"{res} {sub} {name}")
    r = tab["rutor"]["rutor med eko i över hälften av de torra timmarna, per dag"]
    if r["hi"] < 0:
        worse.append("rutor med eko under torra timmar")
    return {"battre": not worse and bool(better), "battre_i": better, "samre_i": worse}


def markdown(tab: dict, namn: str, bas: str | None) -> str:
    lines = []
    for key, rows in tab.items():
        lines.append(f"\n**{key}**\n")
        if bas:
            lines.append(f"| mått | {namn} | {bas} | skillnad i godhet (95 %) | bättre är | dagar |")
            lines.append("|---|---|---|---|---|---|")
        else:
            lines.append(f"| mått | {namn} | bättre är |")
            lines.append("|---|---|---|")
        for name, r in rows.items():
            v = f"{r['varde']:.3f}"
            if bas:
                lines.append(f"| {name} | {v} | {r['bas']:.3f} | {r['diff']:+.3f} ({r['lo']:+.3f} till {r['hi']:+.3f}) | {r['battre']} | {r.get('dagar', '')} |")
            else:
                lines.append(f"| {name} | {v} | {r['battre']} |")
    return "\n".join(lines).replace(".", ",").replace("+,", "+").replace("(,", "(")


# ---------------------------------------------------------------- radarn och baslinjerna

def frame_path(t: datetime) -> Path:
    return RADAR / f"{t:%Y/%m/%d}" / f"{t:%Y%m%d%H%M}.tif"


class Radardag:
    """Radarns bilder för en dag (från 00:00 − 30 min till 24:00) och rörelsefältet var 15:e minut
    (kedjans inställningar, motion_field med gap 3 och 3 bilder, steg 4). Rörelsen sparas glest
    (var 4:e ruta, float16) i OUT/rorelse/<dag>.npz och interpoleras upp när den läses."""

    PRE = 6  # bilder före 00:00

    def __init__(self, day_s: str):
        from knep.analys import radar
        self.day_s = day_s
        self.day = datetime.fromisoformat(day_s).replace(tzinfo=UTC)
        self.times = [self.day + (k - self.PRE) * radar.STEP for k in range(288 + self.PRE + 1)]
        grid, frames = None, []
        for t in self.times:
            p = frame_path(t)
            if p.exists():
                r, g = radar.read_rain(p)
                grid = grid or g
                frames.append(r)
            else:
                frames.append(None)
        self.grid = grid
        shp = grid.shape
        self.rain = np.stack([f if f is not None else np.full(shp, np.nan, np.float32) for f in frames]).astype(np.float32)
        self.have = np.array([f is not None for f in frames])
        self._motion = None

    def sparse_motion(self) -> np.ndarray:
        """(97, 2, H/4, W/4): rörelsen vid 00:00, 00:15, ..., 24:00 i pixlar per 5 min, var 4:e ruta."""
        if self._motion is not None:
            return self._motion
        p = RORELSE / f"{self.day_s}.npz"
        h, w = self.grid.shape
        if p.exists():
            sm = np.load(p)["m"].astype(np.float32)
        else:
            from knep.prognos.model import motion_field
            sm, last = [], np.zeros((2, h, w))
            for j in range(97):
                k = self.PRE + 3 * j  # index för tiden 00:00 + 15 j min
                idx = [k - 6, k - 3, k]
                if all(self.have[i] for i in idx):
                    obs = np.nan_to_num(self.rain[idx], nan=0.0)
                    last = motion_field(obs, 1, 3, 4)  # bilderna ligger redan 15 min isär: gap 3 i 5-minuterssteg
                    last = last / 3.0
                sm.append(last[:, ::4, ::4].astype(np.float16))
            sm = np.stack(sm)
            p.parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(p, m=sm)
            sm = sm.astype(np.float32)
        self._motion = sm
        self._cache = (None, None)
        return sm

    def _up(self, sm: np.ndarray) -> np.ndarray:
        import cv2
        h, w = self.grid.shape
        mx, my = np.meshgrid(np.arange(w, dtype=np.float32) / 4.0, np.arange(h, dtype=np.float32) / 4.0)
        return np.stack([cv2.remap(np.ascontiguousarray(sm[c]), mx, my, cv2.INTER_LINEAR,
                                   borderMode=cv2.BORDER_REPLICATE) for c in range(2)])

    def motion_at(self, k: int) -> np.ndarray:
        """Rörelsen som kedjan hade när bilden k kom: senaste kvartens fält (för k före 00:00 det vid 00:00)."""
        sm = self.sparse_motion()
        j = min(max(0, (k - self.PRE) // 3), 96)
        if self._cache[0] != j:
            self._cache = (j, self._up(sm[j]))
        return self._cache[1]

    def hourly_motion(self) -> np.ndarray:
        """(24, 2, H, W): medlet av rörelsen under timmen."""
        m = self.sparse_motion()
        return np.stack([self._up(m[4 * h:4 * h + 5].mean(axis=0)) for h in range(24)])


def sums(intervals: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Kvart och timme i mm ur 288 intervall (mm/h) med slut 00:05 .. 24:00. En period räknas om
    minst två tredjedelar av intervallen har data; medlet av de som finns används."""
    def agg(n):
        out = np.empty((len(intervals) // n, *intervals.shape[1:]), np.float32)
        for i in range(len(out)):
            x = intervals[i * n:(i + 1) * n].astype(np.float32)
            fin = np.isfinite(x)
            ok = fin.sum(axis=0)
            mean = np.where(fin, x, 0.0).sum(axis=0) / np.maximum(ok, 1)
            out[i] = np.where(ok * 3 >= 2 * n, mean, np.nan) * (n * 5 / 60.0)
        return out
    return agg(3), agg(12)


class A0:
    """Radaranalysen som i drift utan reserver och volymkorrektion: SMHI:s komposit med lagrangesk
    utfyllnad vid bortfall (composite.fill_gaps), varje bild gäller de fem minuterna före den."""

    namn = "A0"
    matare = False

    def __init__(self, rd: Radardag):
        self.rd = rd

    def frames(self) -> np.ndarray:
        """Analyserna för alla bilder i Radardag (med utfyllnad)."""
        from knep.analys import composite
        if hasattr(self, "_frames"):
            return self._frames
        rd, gap = self.rd, None
        rd.sparse_motion()  # rörelsen ur de råa bilderna, innan de fylls i
        out = rd.rain  # fylls i på plats för att spara minne; rd.rain är sedan A0
        for k in range(len(rd.times)):
            rain = rd.rain[k]
            src = np.where(np.isfinite(rain), composite.SOURCE_SMHI, composite.SOURCE_NONE).astype(np.uint8)
            motion = rd.motion_at(k) if gap is not None and not rd.have[k] else None
            rain, _, _, gap = composite.fill_gaps(rain, src, gap, motion)
            out[k] = rain
        self._frames = out
        return out

    def falt(self, dag, matare):
        return sums(self.frames()[Radardag.PRE + 1:])


class A1(A0):
    """A1 i drift: varje intervall interpolerat längs kedjans rörelsefält (knep.analys.a1)."""

    namn = "A1"

    def falt(self, dag, matare):
        from knep.analys import a1
        fr = self.frames()
        k0 = Radardag.PRE + 1
        iv = np.empty((288, *fr.shape[1:]), np.float16)  # halva minnet; 0,1 % noggrannhet räcker
        for i in range(288):
            k = k0 + i
            iv[i] = a1.interval_mean(fr[k - 1], fr[k], self.rd.motion_at(k).astype(np.float64))
        return sums(iv)


SYSTEMS = {"A0": A0, "A1": A1}


def build_dag(day_s: str, rd: Radardag) -> Dag:
    from pyproj import Transformer
    grid = rd.grid
    elev = np.load(HOJD)["h"].astype(np.float32)
    h, w = grid.shape
    rr, cc = np.mgrid[0:h, 0:w]
    x, y = grid.transform * (cc + 0.5, rr + 0.5)
    lon, lat = Transformer.from_crs(grid.crs, "EPSG:4326", always_xy=True).transform(x, y)
    lov = lovart_mask(elev, rd.hourly_motion(), np.asarray(lat), np.asarray(lon))
    return Dag(day_s, grid.shape, load_gauges(day_s, "kvart", grid), load_gauges(day_s, "timme", grid), elev, lov)


def cmd_kor(a) -> None:
    todo = [a.dag] if a.dag else days(a.del_)
    i, n = (int(x) for x in a.bit.split("/"))
    for day_s in todo[i::n]:
        assert day_s in days("validering") + days("traning")
        targets = {s: OUT / s / f"{day_s}.json" for s in a.system}
        if all(p.exists() for p in targets.values()):
            continue
        t = time.time()
        rd = Radardag(day_s)
        dag = build_dag(day_s, rd)
        a0 = None
        for s, p in targets.items():
            if p.exists():
                continue
            sysm = SYSTEMS[s](rd)
            if a0 is not None:
                sysm._frames = a0._frames  # samma A0-bilder
            res = evaluate(sysm, dag)
            if hasattr(sysm, "_frames"):
                a0 = sysm
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(res))
            print(day_s, s, f"{time.time() - t:.0f} s", "mätare", len(dag.timme), len(dag.kvart), flush=True)
            del sysm
        # släpp dagens bilder innan nästa dag läses (annars ligger två dagar i minnet samtidigt)
        del rd, dag, a0
        import gc
        gc.collect()


def load_results(namn: str, part: str) -> dict[str, dict]:
    out = {}
    for d in days(part):
        p = OUT / namn / f"{d}.json"
        if p.exists():
            out[d] = json.loads(p.read_text())
    return out


def cmd_tabell(a) -> None:
    sys_r = load_results(a.system[0], a.del_)
    base = load_results(a.mot, a.del_) if a.mot else None
    tab = table(sys_r, base)
    print(f"{len(sys_r)} dagar")
    print(markdown(tab, a.system[0], a.mot))
    if base is not None:
        v, v0 = verdict(tab), verdict(tab, min_days=0)
        vg, vg0 = verdict(tab, regel="gammal"), verdict(tab, min_days=0, regel="gammal")
        print("\nDomen (kvot våt):", json.dumps(v, ensure_ascii=False, indent=1))
        print("\nDomen utan kravet på underlag:", json.dumps(v0, ensure_ascii=False, indent=1))
        print("\nDomen med den gamla regeln (kvot summa):", json.dumps(vg, ensure_ascii=False, indent=1))
        print("\nDomen med den gamla regeln utan kravet på underlag:", json.dumps(vg0, ensure_ascii=False, indent=1))
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / f"tabell_{a.system[0]}_mot_{a.mot}_{a.del_}.json").write_text(
            json.dumps({"tabell": tab, "dom": v, "dom_utan_underlagskrav": v0, "dom_gammal_regel": vg,
                        "dom_gammal_regel_utan_underlagskrav": vg0, "dagar": sorted(sys_r)},
                       ensure_ascii=False, indent=1, default=float))


def set_out(path: str | None) -> None:
    """Byter katalogen för dagfiler och tabeller (--ut i domare.py, filter.py och a2.py)."""
    global OUT
    if path:
        OUT = Path(path)


def compare_old(new: dict, old: dict) -> list[str]:
    """Skillnaderna mellan en ny och en gammal dagfil: alla summor i den gamla ska vara exakt
    desamma i den nya, och den nya ska bara ha saw och sgw utöver dem."""
    bad = []
    if set(new) != set(old):
        bad.append(f"nycklarna {sorted(set(new) ^ set(old))}")
    for key in old:
        n = new.get(key, {})
        extra = set(n) - set(old[key])
        if extra != (set() if key == "rutor" else {"saw", "sgw"}):
            bad.append(f"{key}: nya summor {sorted(extra)}")
        for c, v in old[key].items():
            if n.get(c) != v:
                bad.append(f"{key} {c}: {v} mot {n.get(c)}")
    return bad


def cmd_kontroll(a) -> None:
    """De gamla måtten oförändrade: dagfilerna i OUT mot de gamla i OUT_V1."""
    bad, n = [], 0
    for s in a.system:
        for d in [a.dag] if a.dag else days(a.del_):
            p_new, p_old = OUT / s / f"{d}.json", OUT_V1 / s / f"{d}.json"
            if not (p_new.exists() and p_old.exists()):
                continue
            n += 1
            bad += [f"{s} {d} {b}" for b in compare_old(json.loads(p_new.read_text()), json.loads(p_old.read_text()))]
    print(f"{n} dagfiler jämförda, {len(bad)} skillnader")
    for b in bad[:50]:
        print(" ", b)
    if bad or not n:
        sys.exit(1)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cmd", choices=["kor", "tabell", "kontroll"])
    p.add_argument("system", nargs="+")
    p.add_argument("--del", dest="del_", default="validering", choices=["validering", "traning"])
    p.add_argument("--dag")
    p.add_argument("--mot")
    p.add_argument("--bit", default="0/1", help="i/n: var n:e dag från och med den i:e (för två processer)")
    p.add_argument("--ut", help=f"katalogen för dagfiler och tabeller (standard {OUT})")
    a = p.parse_args()
    set_out(a.ut)
    {"kor": cmd_kor, "tabell": cmd_tabell, "kontroll": cmd_kontroll}[a.cmd](a)


if __name__ == "__main__":
    main()
