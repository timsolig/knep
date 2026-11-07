"""A2: analysen rättad mot SMHI:s regnmätare (kvart och timme), bedömd med domaren.

    uv run python experiments/analys/a2.py a1falt [--bit 0/2]      # A1:s fält för valideringen, sparas
    uv run python experiments/analys/a2.py punkter [--bit 0/2]     # radarn vid mätarna, träningsdagarna
    uv run python experiments/analys/a2.py trana                   # välj parametrarna på träningsdagarna
    uv run python experiments/analys/a2.py kor [--bit 0/2]         # A2 genom domaren på valideringen
    uv run python experiments/analys/a2.py tid                     # tiden för en timme på hela rutnätet

Metoden, för varje period (timme eller kvart) med de mätare systemet får se:

1. Rättning i stor skala: en jämn kvot k(x) = (Σ w·g + α) / (Σ w·a + α) över mätarpar
   (mätare g, A1 a i mätarens ruta) från de senaste WIN timmarna fram till och med perioden, med
   Gaussvikter w med längdskalan L_STOR. α (mm) krymper kvoten mot 1 där mätarna är få eller torra.
   Kvoten klipps till [1/4, 4]. Bakgrunden är b = sqrt(k·A1).
2. Optimal interpolation av återstoden i kvadratrotsskala: innovationerna d = sqrt(g) − b vid
   mätarna, bakgrundens fel σ_b(x)² = SB²·(1 + C·(avstånd till närmaste radar / 100 km)²) med
   korrelationen exp(−r/L), mätarnas fel SO². Tillskottet räknas på vart 4:e ruta och interpoleras
   upp; A2 = max(b + Δ, 0)².
3. Torrmask: där A1 är under TORR (mm per period) och alla mätare inom R_TORR km som systemet ser
   är torra (minst en) sätts A2 till 0. Regn tas alltså bara bort där både radarn och mätarna säger
   torrt.

Parametrarna väljs på träningsdagarna (experiments/projektion/traning.json) med samma
korsvalidering som domaren, men på punkterna och med A0 utan utfyllnad som bakgrund i stället för A1
(A1 kostar cirka 10 minuter per dag). Valideringen bedöms med domaren mot A0 och A1. Testdelen läses
aldrig (domare.days kontrollerar det).
"""

from __future__ import annotations

import argparse
import gc
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from scipy.ndimage import distance_transform_edt
from scipy.spatial import cKDTree
from scipy.spatial.distance import cdist

HERE = Path(__file__).resolve().parent


def _load_domare():
    """Analysens domare via sökvägen och under ett eget namn (andra domare.py finns i experimenten)."""
    import importlib.util
    name = "analys_domare"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, HERE / "domare.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    return sys.modules[name]


D = _load_domare()

OUT = Path("/data/analys/a2")
STEP = 4  # tillskottet räknas på var 4:e ruta

# frysta efter träningen (se trana); ändra inte efter att valideringen har körts
# timmen: koordinatsökningen i trana (28 träningsdagar). Kvarten: stora skalan från timmen, L, SB, SO och
# R_TORR valda i trana --res kvart (försök 2); sökningen behöll startvärdena (timmens SB och SO gånger
# 0,5 och timmens R_TORR), eftersom inget annat värde sänkte målet med mer än 1e-5.
PARAMS = {
    "timme": {"L_STOR": 75.0, "ALFA": 8.0, "WIN": 6, "L": 40.0, "SB": 1.6, "C": 1.0, "SO": 0.3,
              "TORR": 0.05, "R_TORR": 80.0},
    "kvart": {"L_STOR": 75.0, "ALFA": 8.0, "WIN": 6, "L": 40.0, "SB": 0.8, "C": 1.0, "SO": 0.15,
              "TORR": 0.0125, "R_TORR": 80.0},
}
KMAX = 4.0

# varianterna mot de falska ekona per kvart (uppgiften a2-falska-ekon, 2026-11-07): ändringar i
# PARAMS["kvart"], valda på träningspunkterna (a2.py varianter) och frysta innan valideringen kördes.
# Timmen är oförändrad. K_SVAG: ingen uppskalning (k = min(k, 1)) där A1 är under K_SVAG mm.
# TORR2, R_TORR2: A2 = 0 där A1 är under TORR2 mm och alla sedda mätare inom R_TORR2 km är torra.
# SVAG_TAK: dessutom A2 högst A1 där 0 < A1 < K_SVAG (varken kvoten eller OI lyfter svagt eko).
# Valet (26 varianter, /data/analys/a2/varianter_*.json): alla varianter som sänker falskt över 400 m och
# på lovart höjer målet. A2S är den med lägst mål bland dem som sänker falskt i båda; A2T den med lägst mål
# bland dem som sänker falskt över 400 m och på lovart med minst 0,002 (två tredjedelar av A2:s underskott
# mot A1 på valideringen enligt uppgift 3).
FRYSTA: dict[str, dict] = {
    "A2S": {"K_SVAG": 0.1},
    "A2T": {"K_SVAG": 0.125, "SVAG_TAK": True},
    # A2T med kontrollen av mätarna i indata (uppgiften a2t-kontroll-matare, 2026-11-07), vald på
    # träningen (a2.py varianter_qc, ren och med 1 % syntetiska fel) och fryst innan valideringen kördes:
    # per upplösning lägst mål med de syntetiska felen bland varianterna som inte höjer falskt över 400 m
    # eller på lovart, har högst 0,5 % högre mål på rena data och kastar högst 2 %. Skyddet över 400 m gav
    # samma värden som utan; vid lika valdes skyddet.
    "A2TK": {"K_SVAG": 0.125, "SVAG_TAK": True, "QC_T": 3.0, "QC_R": 50.0, "QC_SKYDD400": True,
             "timme": {"QC_T": 2.5, "QC_R": 50.0, "QC_SKYDD400": True}},
}

# kontrollen av mätarna (uppgiften a2t-kontroll-matare): av som standard (QC_T saknas eller 0). Se kontroll().
QC_STD = {"QC_R": 40.0, "QC_NMIN": 2, "QC_SMIN": None, "QC_SKYDD400": True}


# ---------------------------------------------------------------- kontrollen av mätarna

def kontroll(xy, mm, bg, rng_km, over400, p) -> np.ndarray:
    """Mätare som kastas för perioden (bool per mätare), bara bland mätarna som systemet ser.

    I kvadratrotsskala jämförs varje mätare med en skattning ur grannarna inom QC_R km (utan mätaren
    själv, Gaussvikter med längden QC_R/2, minst QC_NMIN grannar) och med bakgrunden bg (A1 efter
    kvoten). e_n = √g − grannarna och e_b = (√g − √bg) / √(1 + C·(radaravstånd/100)²), så att radarn
    litas mindre på långt från radarn. Spridningen σ är 1,4826 · MAD av e över periodens mätare där
    någon sida är våt, men minst QC_SMIN (√mm; standard SO). Mätaren kastas om e_n och e_b har samma
    tecken och båda är över QC_T · σ: för torr mot både grannarna och radarn (0 i regn) eller för våt
    mot både grannarna och radarn. Med QC_SKYDD400 kastas en för våt mätare aldrig över 400 m, där
    radarn missar låg nederbörd (det A2 ska fånga). Utan grannar kastas ingenting.
    QC_T = 0 (standard) stänger av kontrollen."""
    T = p.get("QC_T", 0.0)
    n = len(mm)
    out = np.zeros(n, bool)
    if T <= 0 or n < 3:
        return out
    q = dict(QC_STD, **{k: v for k, v in p.items() if k.startswith("QC_")})
    R, smin = q["QC_R"], q["QC_SMIN"] if q["QC_SMIN"] is not None else p["SO"]
    ok = np.isfinite(mm) & np.isfinite(bg)
    s = np.sqrt(np.maximum(mm, 0.0))
    sb = np.sqrt(np.maximum(np.nan_to_num(bg), 0.0))
    tree = cKDTree(xy)
    sp = tree.sparse_distance_matrix(tree, R, output_type="coo_matrix")
    i, j, d = sp.row, sp.col, sp.data
    keep = (i != j) & ok[i] & ok[j]
    i, j, d = i[keep], j[keep], d[keep]
    w = np.exp(-0.5 * (d / (0.5 * R)) ** 2)
    wsum = np.bincount(i, w, n)
    cnt = np.bincount(i, minlength=n)
    nb = np.bincount(i, w * s[j], n) / np.maximum(wsum, 1e-12)
    valid = ok & (cnt >= q["QC_NMIN"])
    if not valid.any():
        return out
    e_n = s - nb
    e_b = (s - sb) / np.sqrt(1.0 + p["C"] * (rng_km / 100.0) ** 2)

    def sig(e, act):
        a = e[act]
        if len(a) < 10:
            return smin
        return max(1.4826 * float(np.median(np.abs(a - np.median(a)))), smin)

    sn = sig(e_n, valid & ((mm > 0) | (nb > 0)))
    sbb = sig(e_b, valid & ((mm > 0) | (sb > 0)))
    low = valid & (e_n < -T * sn) & (e_b < -T * sbb)
    high = valid & (e_n > T * sn) & (e_b > T * sbb)
    if q["QC_SKYDD400"]:
        high &= ~np.asarray(over400, bool)
    return low | high


# ---------------------------------------------------------------- geometri

def radar_range_km(grid) -> np.ndarray:
    """Avståndet till närmaste radar i knep.analys.composite.RADARS, km per ruta."""
    from pyproj import Transformer
    from knep.analys.composite import RADARS
    tr = Transformer.from_crs("EPSG:4326", grid.crs, always_xy=True)
    h, w = grid.shape
    rr, cc = np.mgrid[0:h, 0:w]
    x, y = grid.transform * (cc + 0.5, rr + 0.5)
    best = np.full((h, w), np.inf, np.float32)
    for lat, lon, _, _ in RADARS.values():
        x0, y0 = tr.transform(lon, lat)
        best = np.minimum(best, (np.hypot(x - x0, y - y0) / 1000.0).astype(np.float32))
    return best


def fold_dist(shape) -> np.ndarray:
    """(FOLDS, H, W): avståndet i km till grupp k (0 inne i gruppen)."""
    f = D.fold_map(shape)
    return np.stack([distance_transform_edt(f != k) * D.RES_KM for k in range(D.FOLDS)]).astype(np.float32)


# ---------------------------------------------------------------- själva analysen

def stor_kvot(xy_t, xy_g, g, a, p) -> np.ndarray:
    """Kvoten i stor skala i punkterna xy_t (km) ur paren (g mätare, a radar) i xy_g."""
    ok = np.isfinite(g) & np.isfinite(a)
    if not ok.any():
        return np.ones(len(xy_t))
    xy_g, g, a = xy_g[ok], g[ok], a[ok]
    d2 = cdist(xy_t, xy_g, "sqeuclidean")
    w = np.exp(-0.5 * d2 / p["L_STOR"] ** 2)
    k = (w @ g + p["ALFA"]) / (w @ a + p["ALFA"])
    return np.clip(k, 1.0 / KMAX, KMAX)


def oi_vikter(xy_g, sb_g, d, p) -> np.ndarray:
    """Lös (B + R) v = d för mätarna (B = σ_b σ_b exp(−r/L), R = SO² I)."""
    r = cdist(xy_g, xy_g)
    B = sb_g[:, None] * sb_g[None, :] * np.exp(-r / p["L"])
    B[np.diag_indices_from(B)] += p["SO"] ** 2
    return np.linalg.solve(B, d)


def oi_tillskott(xy_t, sb_t, xy_g, sb_g, v, p) -> np.ndarray:
    r = cdist(xy_t, xy_g).astype(np.float32)
    k = np.exp(r * np.float32(-1.0 / p["L"]))
    return sb_t * (k @ (sb_g * v).astype(np.float32))


def sigma_b(rng_km, p):
    return p["SB"] * np.sqrt(1.0 + p["C"] * (rng_km / 100.0) ** 2)


def svag_kvot(ratio, bg, p):
    """Varianten utan uppskalning av svagt eko: där A1 är under K_SVAG gäller min(k, 1).

    K_SVAG = 0 (standard) ändrar ingenting."""
    ks = p.get("K_SVAG", 0.0)
    if ks <= 0:
        return ratio
    return np.where(bg < ks, np.minimum(ratio, 1.0), ratio)


def svag_tak(out, bg, p):
    """Varianten med tak över svagt eko (SVAG_TAK): där 0 < A1 < K_SVAG blir A2 högst A1, så att varken
    kvoten eller OI lyfter ett svagt eko. Där A1 är 0 får OI fortfarande lägga till regn."""
    ks = p.get("K_SVAG", 0.0)
    if ks <= 0 or not p.get("SVAG_TAK", False):
        return out
    return np.where((bg > 0) & (bg < ks), np.minimum(out, bg), out)


def analys_punkter(t_bg, t_xy, t_rng, ratio_t, g_xy, g_mm, g_bg, g_rng, ratio_g, g_wet_tree, p,
                   torrmask=True):
    """A2 i målpunkterna för en period.

    t_bg: A1 i målpunkterna (mm per period); g_*: periodens mätare som systemet ser;
    ratio_t, ratio_g: kvoten i stor skala i målen och vid mätarna."""
    ratio_t, ratio_g = svag_kvot(ratio_t, t_bg, p), svag_kvot(ratio_g, g_bg, p)
    out = ratio_t * t_bg
    ok_g = np.isfinite(g_bg) & np.isfinite(g_mm)
    if ok_g.sum() >= 1:
        bg_g = np.sqrt(np.maximum(ratio_g[ok_g] * g_bg[ok_g], 0))
        d = np.sqrt(g_mm[ok_g]) - bg_g
        sbg = sigma_b(g_rng[ok_g], p)
        v = oi_vikter(g_xy[ok_g], sbg, d, p)
        inc = oi_tillskott(t_xy, sigma_b(t_rng, p), g_xy[ok_g], sbg, v, p)
        out = np.maximum(np.sqrt(np.maximum(out, 0)) + inc, 0) ** 2
    out = svag_tak(out, t_bg, p)
    if torrmask and len(g_mm):
        tree = cKDTree(g_xy)
        nb = tree.query_ball_point(t_xy, p["R_TORR"])
        wet = g_mm > 0
        dry_g = np.array([len(n) > 0 and not wet[n].any() for n in nb], bool)
        out = np.where(dry_g & (t_bg < p["TORR"]), 0.0, out)
        if p.get("TORR2", 0.0) > 0:
            # torrmasken över svagt eko: A1 under TORR2 och alla sedda mätare inom R_TORR2 torra
            nb2 = tree.query_ball_point(t_xy, p.get("R_TORR2", p["R_TORR"]))
            dry2 = np.array([len(n) > 0 and not wet[n].any() for n in nb2], bool)
            out = np.where(dry2 & (t_bg < p["TORR2"]), 0.0, out)
    return np.where(np.isfinite(t_bg), out, np.nan)


# ---------------------------------------------------------------- A1:s fält för valideringen

def a1_path(day_s):
    return OUT / "a1falt" / f"{day_s}.npz"


def cmd_a1falt(a):
    i, n = (int(x) for x in a.bit.split("/"))
    for day_s in D.days("validering")[i::n]:
        p = a1_path(day_s)
        if p.exists():
            continue
        t = time.time()
        rd = D.Radardag(day_s)
        kv, tm = D.A1(rd).falt(None, None)
        p.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(p, kvart=kv.astype(np.float16), timme=tm.astype(np.float16))
        print(day_s, "A1", f"{time.time() - t:.0f} s", flush=True)
        del rd, kv, tm
        gc.collect()


# ---------------------------------------------------------------- punkterna på träningsdagarna

def cmd_punkter(a):
    from knep.analys import radar
    i, n = (int(x) for x in a.bit.split("/"))
    rng = None
    for day_s in D.days("traning")[i::n]:
        p = OUT / "punkter" / f"{day_s}.npz"
        if p.exists():
            continue
        t = time.time()
        day = datetime.fromisoformat(day_s).replace(tzinfo=UTC)
        frames, grid = [], None
        for k in range(1, 289):
            f = D.frame_path(day + k * radar.STEP)
            if f.exists():
                r, g = radar.read_rain(f)
                grid = grid or g
                frames.append(r)
            else:
                frames.append(None)
        shp = grid.shape
        iv = np.stack([f if f is not None else np.full(shp, np.nan, np.float32) for f in frames])
        del frames
        kv, tm = D.sums(iv)
        del iv
        if rng is None:
            rng = radar_range_km(grid)
        out = {}
        for res, F in (("kvart", kv), ("timme", tm)):
            m = D.load_gauges(day_s, res, grid)
            out.update({f"{res}_{k}": getattr(m, k) for k in ("station", "r", "c", "t", "mm")})
            out[f"{res}_a"] = F[m.t, m.r, m.c]
            out[f"{res}_rng"] = rng[m.r, m.c]
        out["shape"] = np.array(shp)
        p.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(p, **out)
        print(day_s, "punkter", f"{time.time() - t:.0f} s", len(out["timme_mm"]), flush=True)
        del kv, tm
        gc.collect()


def terr_path(day_s):
    return OUT / "punkter_terr" / f"{day_s}.npz"


def cmd_terrang(a):
    """Höjden och lovartsidan (som i domaren) i mätarnas rutor på träningsdagarna, för diagnosen.

    Rörelsen läses ur domarens cache (OUT/rorelse) och räknas, och sparas där, om den saknas."""
    from pyproj import Transformer
    from knep.analys import radar
    i, n = (int(x) for x in a.bit.split("/"))
    elev = np.load(D.HOJD)["h"].astype(np.float32)
    for day_s in D.days("traning")[i::n]:
        p = terr_path(day_s)
        if p.exists() or not (OUT / "punkter" / f"{day_s}.npz").exists():
            continue
        t = time.time()
        rd = D.Radardag(day_s)
        rd.sparse_motion()
        grid = rd.grid
        rd.rain = None  # bilderna behövs inte längre
        gc.collect()
        h, w = grid.shape
        rr, cc = np.mgrid[0:h, 0:w]
        x, y = grid.transform * (cc + 0.5, rr + 0.5)
        lon, lat = Transformer.from_crs(grid.crs, "EPSG:4326", always_xy=True).transform(x, y)
        lov = D.lovart_mask(elev, rd.hourly_motion(), np.asarray(lat), np.asarray(lon))
        z = np.load(OUT / "punkter" / f"{day_s}.npz")
        out = {}
        for res in ("kvart", "timme"):
            r, c, tt = z[f"{res}_r"], z[f"{res}_c"], z[f"{res}_t"]
            hour = tt if res == "timme" else tt // 4
            out[f"{res}_elev"] = elev[r, c]
            out[f"{res}_lovart"] = lov[hour, r, c]
        p.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(p, **out)
        print(day_s, "terräng", f"{time.time() - t:.0f} s", flush=True)
        del rd, lov
        gc.collect()


# ---------------------------------------------------------------- träningen på punkterna

class Punktdag:
    """Mätarna och radarn i mätarnas rutor för en träningsdag, med grupperna som i domaren."""

    def __init__(self, path: Path):
        z = np.load(path)
        shape = tuple(int(x) for x in z["shape"])
        self.day = path.stem
        folds = D.fold_map(shape)
        fd = fold_dist(shape)
        self.res = {}
        for res in ("kvart", "timme"):
            r, c = z[f"{res}_r"], z[f"{res}_c"]
            self.res[res] = dict(
                t=z[f"{res}_t"], mm=z[f"{res}_mm"].astype(float), a=z[f"{res}_a"].astype(float),
                rng=z[f"{res}_rng"].astype(float), xy=np.c_[c, r].astype(float) * D.RES_KM,
                fold=folds[r, c], dist=fd[:, r, c], station=z[f"{res}_station"])
            # indata till A2 (kan bytas mot värden med syntetiska fel); domaren bedömer mot mm
            self.res[res]["mm_in"] = self.res[res]["mm"]
        tp = terr_path(path.stem)
        if tp.exists():
            zt = np.load(tp)
            for res in ("kvart", "timme"):
                self.res[res]["over400"] = zt[f"{res}_elev"] > D.HIGH_M
                self.res[res]["lovart"] = zt[f"{res}_lovart"].astype(bool)


def _over400(Q, sel):
    return Q["over400"][sel] if "over400" in Q else np.zeros(int(np.count_nonzero(sel)), bool)


def _kontroll_timme(H, seen_h, ph):
    """Timmätare som kontrollen kastar (bool per rad i H), bland de sedda, med timmens kvot."""
    flag = np.zeros(len(H["mm"]), bool)
    if ph is None or ph.get("QC_T", 0.0) <= 0:
        return flag
    for hour in range(24):
        gs = seen_h & (H["t"] == hour)
        if gs.sum() < 3:
            continue
        win = seen_h & (H["t"] <= hour) & (H["t"] > hour - ph["WIN"])
        rg = stor_kvot(H["xy"][gs], H["xy"][win], H["mm_in"][win], H["a"][win], ph)
        bg = svag_kvot(rg, H["a"][gs], ph) * H["a"][gs]
        flag[np.flatnonzero(gs)] = kontroll(H["xy"][gs], H["mm_in"][gs], bg, H["rng"][gs], _over400(H, gs), ph)
    return flag


def _predict_day(pd: Punktdag, res: str, p: dict, torrmask=True, full=False, ph=None, rec=None):
    """A2 i varje mätare i gruppen k ur mätarna som syns när grupp k bedöms. Ger (g, a, a2), och med
    full=True också kvoten k i målen och målens index i pd.res[res].

    ph: timmens parametrar för kontrollen av timmätarna (i kvoten och, för timmen, i OI); för timmen
    gäller p. rec: lista som får (res, index i pd.res[res] för indata, kastade) per grupp och period."""
    H, Q = pd.res["timme"], pd.res[res]
    if res == "timme":
        ph = p
    G, A, P, K, I = [], [], [], [], []
    nper = D.NPER[res]
    for k in range(D.FOLDS):
        seen_h = H["dist"][k] > D.BUFFER_KM
        seen_q = Q["dist"][k] > D.BUFFER_KM
        hflag = _kontroll_timme(H, seen_h, ph)
        if hflag.any():
            seen_h = seen_h & ~hflag
            if res == "timme":
                seen_q = seen_h
        if rec is not None and res == "timme" and ph.get("QC_T", 0.0) > 0:
            for t in range(nper):
                gs0 = (H["dist"][k] > D.BUFFER_KM) & (H["t"] == t)
                rec.append(("timme", np.flatnonzero(gs0), hflag[gs0]))
        for t in range(nper):
            hour = t if res == "timme" else t // 4
            tgt = (Q["t"] == t) & (Q["fold"] == k) & np.isfinite(Q["a"])
            if not tgt.any():
                continue
            win = seen_h & (H["t"] <= hour) & (H["t"] > hour - p["WIN"])
            gs = seen_q & (Q["t"] == t)
            rg = stor_kvot(Q["xy"][gs], H["xy"][win], H["mm_in"][win], H["a"][win], p)
            if res == "kvart" and p.get("QC_T", 0.0) > 0:
                bg = svag_kvot(rg, Q["a"][gs], p) * Q["a"][gs]
                fl = kontroll(Q["xy"][gs], Q["mm_in"][gs], bg, Q["rng"][gs], _over400(Q, gs), p)
                if rec is not None:
                    rec.append(("kvart", np.flatnonzero(gs), fl))
                if fl.any():
                    gs = gs.copy()
                    gs[np.flatnonzero(gs)[fl]] = False
                    rg = rg[~fl]
            rt = stor_kvot(Q["xy"][tgt], H["xy"][win], H["mm_in"][win], H["a"][win], p)
            a2 = analys_punkter(Q["a"][tgt], Q["xy"][tgt], Q["rng"][tgt], rt, Q["xy"][gs], Q["mm_in"][gs],
                                Q["a"][gs], Q["rng"][gs], rg, None, p, torrmask)
            G.append(Q["mm"][tgt]); A.append(Q["a"][tgt]); P.append(a2)
            K.append(rt); I.append(np.flatnonzero(tgt))
    if full:
        return tuple(np.concatenate(x) for x in (G, A, P, K, I))
    return np.concatenate(G), np.concatenate(A), np.concatenate(P)


def _score(g, a):
    ok = np.isfinite(a)
    g, a = g[ok], a[ok]
    out = {"MAE": float(np.abs(a - g).mean()), "kvot": float(a.sum() / g.sum()),
           "rmse_sqrt": float(np.sqrt(((np.sqrt(a) - np.sqrt(g)) ** 2).mean()))}
    for thr in (0.5, 1.0, 5.0):
        fa, ob = a >= thr, g >= thr
        out[f"CSI{thr:g}"] = float((fa & ob).sum() / max(1, (fa | ob).sum()))
    return out


def score_params(pdays, res, p, torrmask=True):
    G, A, P = [], [], []
    for pd in pdays:
        g, a, a2 = _predict_day(pd, res, p, torrmask)
        G.append(g); A.append(a); P.append(a2)
    g, a, a2 = np.concatenate(G), np.concatenate(A), np.concatenate(P)
    thr = D.ECHO[res]
    s2, s0 = _score(g, a2), _score(g, a)
    s2["falskt"] = float((a2[g == 0] > thr).mean())
    s0["falskt"] = float((a[g == 0] > thr).mean())
    return s2, s0


def _kast_add(kast, pd, rec):
    """Räknar kastade bland indata ur rec (se _predict_day) per upplösning och delmängd."""
    for res, idx, fl in rec:
        Q = pd.res[res]
        d = kast.setdefault(res, {})
        subs = {"alla": np.ones(len(idx), bool)}
        for s in ("over400", "lovart"):
            if s in Q:
                subs[s] = Q[s][idx]
        if "syn" in Q:
            for code, namn in SYN_TYPER.items():
                subs[f"syn_{namn}"] = Q["syn"][idx] == code
        for s, m in subs.items():
            n, f = d.get(s, (0, 0))
            d[s] = (n + int(m.sum()), f + int((fl & m).sum()))


def _kast_final(kast):
    return {res: {s: {"n": n, "kastade": f, "andel": f / n if n else float("nan")} for s, (n, f) in d.items()}
            for res, d in kast.items()}


def _collect(pdays, res, p, ph=None, kast=None):
    """Alla mål på dagarna: g, a (bakgrunden), a2, k och delmängderna (över 400 m, lovart)."""
    out = {k: [] for k in ("g", "a", "a2", "k", "over400", "lovart")}
    for pd in pdays:
        rec = [] if kast is not None else None
        g, a, a2, k, idx = _predict_day(pd, res, p, full=True, ph=ph, rec=rec)
        if rec:
            _kast_add(kast, pd, rec)
        Q = pd.res[res]
        out["g"].append(g); out["a"].append(a); out["a2"].append(a2); out["k"].append(k)
        for s in ("over400", "lovart"):
            out[s].append(Q[s][idx] if s in Q else np.zeros(len(idx), bool))
    return {k: np.concatenate(v) for k, v in out.items()}


def score_full(pdays, res, p, ph=None, kast=None):
    """Målet och måtten som i score_params, och falskt vid torr mätare för alla, över 400 m och lovart.

    ph: timmens parametrar för kontrollen av timmätarna när kvarten räknas. kast: dict som får
    andelen kastade bland indata (alla, över 400 m, lovart och per typ av syntetiskt fel)."""
    c = _collect(pdays, res, p, ph, kast)
    s = _score(c["g"], c["a2"])
    s["mal"] = float(_objective(s))
    thr = D.ECHO[res]
    dry = c["g"] == 0
    for name, sel in (("alla", np.ones(len(dry), bool)), ("over400", c["over400"]), ("lovart", c["lovart"])):
        m = dry & sel & np.isfinite(c["a2"])
        s[f"falskt_{name}"] = float((c["a2"][m] > thr).mean()) if m.any() else float("nan")
        s[f"ntorr_{name}"] = int(m.sum())
    return s


def cmd_diagnos(a):
    """Var de falska ekona per kvart (och timme) kommer ifrån: bakgrunden redan över tröskeln, lyft av
    kvoten k eller lyft av OI-tillskottet. Bara träningsdagarna."""
    pdays = _train_pdays(a)
    result = {}
    for res in a.res:
        p = PARAMS[res]
        c = _collect(pdays, res, p)
        thr = D.ECHO[res]
        ka = svag_kvot(c["k"], c["a"], p) * c["a"]
        dry = (c["g"] == 0) & np.isfinite(c["a2"])
        rows = {}
        for name, sel in (("alla", np.ones(len(dry), bool)), ("over400", c["over400"]), ("lovart", c["lovart"])):
            m = dry & sel
            f2 = m & (c["a2"] > thr)
            r = {
                "torra": int(m.sum()),
                "falskt bakgrund": float((c["a"][m] > thr).mean()),
                "falskt A2": float(f2.sum() / m.sum()),
                "A2 falskt, bakgrund redan över": int((f2 & (c["a"] > thr)).sum()),
                "A2 falskt, lyft av k": int((f2 & (c["a"] <= thr) & (ka > thr)).sum()),
                "A2 falskt, lyft av OI": int((f2 & (ka <= thr)).sum()),
                "bakgrund falskt, borttaget av A2": int((m & (c["a"] > thr) & (c["a2"] <= thr)).sum()),
                "k median vid lyft av k": float(np.median(c["k"][f2 & (c["a"] <= thr) & (ka > thr)]))
                if (f2 & (c["a"] <= thr) & (ka > thr)).any() else float("nan"),
                "k medel vid torra": float(c["k"][m].mean()),
                "bakgrund median vid lyft": float(np.median(c["a"][f2 & (c["a"] <= thr)]))
                if (f2 & (c["a"] <= thr)).any() else float("nan"),
            }
            # bakgrundens värde vid de falska ekona (klasser)
            ab = c["a"][f2 & (c["a"] <= thr)]
            r["bakgrund vid lyft: 0"] = int((ab == 0).sum())
            r["bakgrund vid lyft: (0, 0,05]"] = int(((ab > 0) & (ab <= 0.05)).sum())
            r["bakgrund vid lyft: (0,05, thr]"] = int((ab > 0.05).sum())
            rows[name] = r
        result[res] = rows
        print(res, json.dumps(rows, ensure_ascii=False, indent=1), flush=True)
    (OUT / "diagnos.json").write_text(json.dumps(result, ensure_ascii=False, indent=1))


# varianterna som prövas för kvarten på träningen: (namn, ändringar i PARAMS["kvart"])
VARIANTER = (
    [("standard", {})]
    + [(f"K_SVAG={v:g}", {"K_SVAG": v}) for v in (0.1, 0.125, 0.2, 0.3)]
    + [(f"K_SVAG={v:g} tak", {"K_SVAG": v, "SVAG_TAK": True}) for v in (0.1, 0.125, 0.2, 0.3)]
    + [(f"TORR2={v:g} R={r:g}", {"TORR2": v, "R_TORR2": r}) for v in (0.1, 0.2, 0.3) for r in (30.0, 40.0, 80.0)]
    + [(f"K_SVAG={k:g} tak TORR2={v:g} R={r:g}", {"K_SVAG": k, "SVAG_TAK": True, "TORR2": v, "R_TORR2": r})
       for k in (0.125, 0.2) for v in (0.1, 0.2) for r in (40.0, 80.0)]
)


# ---------------------------------------------------------------- kontrollen av mätarna på träningen

SYN_TYPER = {0: "riktig", 1: "noll", 2: "x5", 3: "fast"}
SYN_FAST = {"kvart": 0.5, "timme": 2.0}  # det fasta värdet (mm per period)


def syntetiska_fel(pd: Punktdag, frac=0.01, seed=0):
    """Sätter cirka frac av mätarperioderna i indata (mm_in) till 0 i regn, ×5 i regn eller ett fast
    värde (en tredjedel var), kvart och timme var för sig. Regn är minst ekotröskeln. Domaren bedömer
    fortfarande mot mm."""
    rng = np.random.default_rng([seed, int(datetime.fromisoformat(pd.day).timestamp()) // 86400])
    for res in ("kvart", "timme"):
        Q = pd.res[res]
        n = len(Q["mm"])
        m = int(round(frac * n / 3))
        syn = np.zeros(n, np.int8)
        mm = Q["mm"].copy()
        wet = np.flatnonzero(Q["mm"] >= D.ECHO[res])  # regn: minst ekotröskeln (0,125 mm per kvart, 0,5 per timme)
        pick = rng.choice(wet, size=min(2 * m, len(wet)), replace=False)
        noll, x5 = pick[: len(pick) // 2], pick[len(pick) // 2:]
        rest = np.setdiff1d(np.arange(n), pick)
        fast = rng.choice(rest, size=min(m, len(rest)), replace=False)
        mm[noll], syn[noll] = 0.0, 1
        mm[x5], syn[x5] = 5 * mm[x5], 2
        mm[fast], syn[fast] = SYN_FAST[res], 3
        Q["mm_in"], Q["syn"] = mm, syn


def _qc(T, R, skydd):
    return {"QC_T": T, "QC_R": R, "QC_SKYDD400": skydd}


# varianterna av kontrollen (namn, ändringar i PARAMS för upplösningen ovanpå A2T)
VARIANTER_QC = (
    [("A2T", {})]
    + [(f"T={T:g} R={R:g}{' skydd400' if s else ''}", _qc(T, R, s))
       for T in (2.0, 2.5, 3.0, 4.0) for R in (25.0, 50.0) for s in (True, False)]
)


def _a2t(res):
    return dict(system_params("A2T")[res])


def cmd_kontroll(a):
    """Diagnosen: kontrollen med alla mätare (som i drift) på träningsdagarna, för en variant
    (--qc T R skydd). Kastade perioder per upplösning, över 400 m, lovart, typ och station."""
    pdays = _train_pdays(a)
    T, R, skydd = float(a.qc[0]), float(a.qc[1]), a.qc[2] in ("1", "ja", "True")
    result = {}
    for res in a.res:
        p = dict(_a2t(res), **_qc(T, R, skydd))
        ph = dict(_a2t("timme"), **_qc(T, R, skydd))
        n_in = n_fl = n400 = f400 = nlov = flov = nlow = 0
        stn, stn_all, perdag, stn_dagar = {}, {}, {}, {}
        for pd in pdays:
            H, Q = pd.res["timme"], pd.res[res]
            alla_h = np.ones(len(H["mm"]), bool)
            fl_day = np.zeros(len(Q["mm"]), bool)
            for t in range(D.NPER[res]):
                hour = t if res == "timme" else t // 4
                gs = (Q["t"] == t) & np.isfinite(Q["a"])
                if gs.sum() < 3:
                    continue
                win = alla_h & (H["t"] <= hour) & (H["t"] > hour - ph["WIN"])
                rg = stor_kvot(Q["xy"][gs], H["xy"][win], H["mm"][win], H["a"][win], p)
                bg = svag_kvot(rg, Q["a"][gs], p) * Q["a"][gs]
                fl = kontroll(Q["xy"][gs], Q["mm"][gs], bg, Q["rng"][gs], _over400(Q, gs), p)
                idx = np.flatnonzero(gs)
                fl_day[idx[fl]] = True
                nlow += int((fl & (Q["mm"][gs] < bg)).sum())
            ok = np.isfinite(Q["a"])
            n_in += int(ok.sum()); n_fl += int(fl_day.sum())
            o4, lv = Q.get("over400", np.zeros(len(ok), bool)), Q.get("lovart", np.zeros(len(ok), bool))
            n400 += int((ok & o4).sum()); f400 += int((fl_day & o4).sum())
            nlov += int((ok & lv).sum()); flov += int((fl_day & lv).sum())
            perdag[pd.day] = int(fl_day.sum())
            for s in Q["station"][fl_day]:
                stn[int(s)] = stn.get(int(s), 0) + 1
            for s in np.unique(Q["station"][fl_day]):
                stn_dagar[int(s)] = stn_dagar.get(int(s), 0) + 1
            for s in Q["station"][ok]:
                stn_all[int(s)] = stn_all.get(int(s), 0) + 1
        ofta = sorted(stn.items(), key=lambda x: -x[1])[:15]
        result[res] = {
            "perioder": n_in, "kastade": n_fl, "andel": n_fl / n_in,
            "over400": {"perioder": n400, "kastade": f400, "andel": f400 / max(1, n400)},
            "lovart": {"perioder": nlov, "kastade": flov, "andel": flov / max(1, nlov)},
            "for_torra": nlow, "for_vata": n_fl - nlow,
            "stationer_kastade": len(stn),
            "ofta": [{"station": s, "kastade": k, "perioder": stn_all[s], "andel": k / stn_all[s],
                      "dagar": stn_dagar[s]} for s, k in ofta],
            "stationer_fler_an_3_dagar": sum(v > 3 for v in stn_dagar.values()),
            "per_dag": perdag,
        }
        print(res, json.dumps({k: v for k, v in result[res].items() if k != "per_dag"}, ensure_ascii=False),
              flush=True)
    name = f"kontroll_T{T:g}_R{R:g}_{'skydd' if skydd else 'utan'}.json"
    (OUT / name).write_text(json.dumps(result, ensure_ascii=False, indent=1))


def cmd_varianter_qc(a):
    """Varianterna av kontrollen på träningspunkterna (korsvalideringen som i trana), utan och med
    syntetiska fel (--syntet). Varje upplösning för sig ovanpå A2T; --ph T R skydd lägger dessutom
    till kontrollen av timmätarna när kvarten räknas (för kombinationen)."""
    pdays = _train_pdays(a)
    if a.syntet:
        for pd in pdays:
            syntetiska_fel(pd, a.syntet)
    i, n = (int(x) for x in a.bit.split("/"))
    tag = ("syntet" if a.syntet else "ren") + ("_ph" if a.ph else "") + (f"_prov{a.dagar}" if a.dagar else "")
    path = OUT / f"varianter_qc_{tag}_{i}.json"
    result = json.loads(path.read_text()) if path.exists() else {}
    ph = None
    if a.ph:
        ph = dict(_a2t("timme"), **_qc(float(a.ph[0]), float(a.ph[1]), a.ph[2] in ("1", "ja", "True")))
    for res in a.res:
        rows = result.get(res, {})
        for namn, ch in VARIANTER_QC[i::n]:
            if namn in rows or (a.bara and namn not in a.bara):
                continue
            t = time.time()
            kast = {}
            s = score_full(pdays, res, dict(_a2t(res), **ch), ph=ph if res == "kvart" else None, kast=kast)
            rows[namn] = {"andring": ch, **s, "kast": _kast_final(kast)}
            print(res, namn, f"{time.time() - t:.0f} s", json.dumps(rows[namn], ensure_ascii=False), flush=True)
            result[res] = rows
            path.write_text(json.dumps(result, ensure_ascii=False, indent=1))


def _train_pdays(a):
    files = sorted((OUT / "punkter").glob("*.npz"))
    tr = set(D.days("traning"))
    files = [f for f in files if f.stem in tr]
    if getattr(a, "dagar", 0):
        files = files[: a.dagar]
    pdays = [Punktdag(f) for f in files]
    print(len(pdays), "träningsdagar,", sum("over400" in pd.res["kvart"] for pd in pdays), "med terrängen",
          flush=True)
    return pdays


def cmd_varianter(a):
    """Varianterna mot de falska ekona, på träningspunkterna (samma korsvalidering som trana)."""
    pdays = _train_pdays(a)
    i, n = (int(x) for x in a.bit.split("/"))
    path = OUT / ("varianter.json" if n == 1 else f"varianter_{i}.json")
    result = json.loads(path.read_text()) if path.exists() else {}
    for res in a.res:
        rows = result.get(res, {})
        for namn, ch in VARIANTER[i::n]:
            if namn in rows:
                continue
            t = time.time()
            rows[namn] = {"andring": ch, **score_full(pdays, res, dict(PARAMS[res], **ch))}
            print(res, namn, f"{time.time() - t:.0f} s", json.dumps(rows[namn], ensure_ascii=False), flush=True)
            result[res] = rows
            path.write_text(json.dumps(result, ensure_ascii=False, indent=1))


GRID = {
    "L_STOR": [75.0, 150.0, 300.0],
    "ALFA": [0.5, 2.0, 8.0],
    "WIN": [1, 3, 6],
    "L": [10.0, 20.0, 40.0, 80.0],
    "SB": None,  # skalas per upplösning nedan
    "C": [0.0, 1.0, 4.0],
    "SO": None,
    "R_TORR": [20.0, 40.0, 80.0],
}


def _objective(s):
    # MAE är huvudmåttet; avståndet från kvoten 1 straffas så att en torr rättning inte vinner på MAE
    return s["MAE"] * (1.0 + 0.5 * abs(np.log(s["kvot"])))


def cmd_trana(a):
    files = sorted((OUT / "punkter").glob("*.npz"))
    tr = set(D.days("traning"))
    files = [f for f in files if f.stem in tr]
    if a.dagar:
        files = files[: a.dagar]
    pdays = [Punktdag(f) for f in files]
    print(len(pdays), "träningsdagar", flush=True)
    path = OUT / "trana.json"
    result = json.loads(path.read_text()) if path.exists() else {}
    for res in a.res:
        p = dict(PARAMS[res])
        keys = ("L", "SB", "SO", "L_STOR", "ALFA", "WIN", "C", "R_TORR")
        if res == "kvart":
            # kvarten tar stora skalans val från timmen (samma timmätare) och väljer bara sina egna fel
            keys = ("L", "SB", "SO", "R_TORR")
            if "timme" in result:
                p.update({k: result["timme"]["params"][k] for k in ("L_STOR", "ALFA", "WIN", "C")})
        sc = 1.0 if res == "timme" else 0.5
        grid = dict(GRID, SB=[0.2 * sc, 0.4 * sc, 0.8 * sc, 1.6 * sc], SO=[0.1 * sc, 0.3 * sc, 0.6 * sc])
        s2, s0 = score_params(pdays, res, p)
        best = _objective(s2)
        log = [{"p": dict(p), "s": s2}]
        print(res, "A0:", json.dumps(s0), flush=True)
        print(res, "start:", json.dumps(s2), flush=True)
        for sweep in range(1):
            changed = False
            for key in keys:
                for v in grid[key]:
                    if v == p[key]:
                        continue
                    q = dict(p, **{key: v})
                    s = score_params(pdays, res, q)[0]
                    log.append({"p": q, "s": s})
                    o = _objective(s)
                    if o < best - 1e-5:
                        best, p, changed = o, q, True
                        print(res, "bättre", key, v, json.dumps(s), flush=True)
            if not changed:
                break
        s2, _ = score_params(pdays, res, p)
        s_nomask, _ = score_params(pdays, res, p, torrmask=False)
        p1 = dict(p, ALFA=1e9)  # utan rättningen i stor skala (kvoten 1)
        s_nostor, _ = score_params(pdays, res, p1)
        result[res] = {"params": p, "A2": s2, "A0": s0, "utan_torrmask": s_nomask, "utan_stor_skala": s_nostor,
                       "logg": log}
        print(res, "valt:", json.dumps(p), json.dumps(s2), flush=True)
        path.write_text(json.dumps(result, indent=1, ensure_ascii=False))


# ---------------------------------------------------------------- A2 på hela rutnätet

def _up(coarse: np.ndarray, shape, step: int = STEP) -> np.ndarray:
    """Bilinjärt från rutorna 0, step, 2·step, ... till hela rutnätet."""
    import cv2
    h, w = shape
    mx, my = np.meshgrid(np.arange(w, dtype=np.float32) / step, np.arange(h, dtype=np.float32) / step)
    return cv2.remap(np.ascontiguousarray(coarse, dtype=np.float32), mx, my, cv2.INTER_LINEAR,
                     borderMode=cv2.BORDER_REPLICATE)


class A2:
    """A1 rättad mot mätarna: kvot i stor skala, optimal interpolation i kvadratrotsskala, torrmask."""

    namn = "A2"
    matare = True

    def __init__(self, kvart1: np.ndarray, timme1: np.ndarray, rng_km: np.ndarray, params=None):
        self.kv1, self.tm1 = kvart1, timme1
        self.shape = timme1.shape[1:]
        self.params = params or PARAMS
        self.rng_full = rng_km
        h, w = self.shape
        rr, cc = np.mgrid[0:h:STEP, 0:w:STEP]
        self.cshape = rr.shape
        self.cxy = np.c_[cc.ravel(), rr.ravel()].astype(float) * D.RES_KM
        self.crng = rng_km[::STEP, ::STEP].ravel().astype(float)
        rr, cc = np.mgrid[0:h:4 * STEP, 0:w:4 * STEP]  # kvoten i stor skala på ett glesare rutnät
        self.kshape = rr.shape
        self.kxy = np.c_[cc.ravel(), rr.ravel()].astype(float) * D.RES_KM

    def _period(self, F1, m: D.Matare, sel, ratio_c, ratio_g, p):
        """A2 på hela rutnätet för en period: F1 A1 (H, W), m.subset(sel) periodens mätare."""
        g = m.subset(sel)
        xy = np.c_[g.c, g.r].astype(float) * D.RES_KM
        a = F1[g.r, g.c].astype(float)
        F0 = np.nan_to_num(F1, nan=0.0)
        ratio_f = svag_kvot(_up(ratio_c, self.shape, 4 * STEP), F0, p)
        ratio_g = svag_kvot(ratio_g, a, p)
        out = np.maximum(ratio_f * F0, 0.0)
        ok = np.isfinite(a)
        if ok.any():
            bg = np.sqrt(np.maximum(ratio_g[ok] * a[ok], 0.0))
            d = np.sqrt(g.mm[ok]) - bg
            sbg = sigma_b(self.rng_full[g.r[ok], g.c[ok]].astype(float), p)
            v = oi_vikter(xy[ok], sbg, d, p)
            inc = oi_tillskott(self.cxy, sigma_b(self.crng, p), xy[ok], sbg, v, p).reshape(self.cshape)
            out = np.maximum(np.sqrt(out) + _up(inc, self.shape), 0.0) ** 2
        out = svag_tak(out, F0, p)
        if len(g):
            # torrmasken på det glesa rutnätet (närmaste mätare och närmaste våta mätare), upp med närmaste
            d_any = cKDTree(xy).query(self.cxy, distance_upper_bound=p["R_TORR"] + 1)[0]
            wet = g.mm > 0
            d_wet = cKDTree(xy[wet]).query(self.cxy, distance_upper_bound=p["R_TORR"] + 1)[0] if wet.any() \
                else np.full(len(self.cxy), np.inf)
            dry_c = ((d_any <= p["R_TORR"]) & (d_wet > p["R_TORR"])).reshape(self.cshape)
            h, w = self.shape
            dry = np.repeat(np.repeat(dry_c, STEP, 0), STEP, 1)[:h, :w]
            dry &= F0 < p["TORR"]
            out[dry] = 0.0
            if p.get("TORR2", 0.0) > 0:
                # torrmasken över svagt eko (se analys_punkter)
                r2 = p.get("R_TORR2", p["R_TORR"])
                d_any2 = cKDTree(xy).query(self.cxy, distance_upper_bound=r2 + 1)[0]
                d_wet2 = cKDTree(xy[wet]).query(self.cxy, distance_upper_bound=r2 + 1)[0] if wet.any() \
                    else np.full(len(self.cxy), np.inf)
                dry2 = ((d_any2 <= r2) & (d_wet2 > r2)).reshape(self.cshape)
                dry2 = np.repeat(np.repeat(dry2, STEP, 0), STEP, 1)[:h, :w] & (F0 < p["TORR2"])
                out[dry2] = 0.0
        return np.where(np.isfinite(F1), out, np.nan).astype(np.float32)

    def _over400(self, dag, m):
        elev = getattr(dag, "elev", None)
        if elev is None:
            return np.zeros(len(m), bool)
        return elev[m.r, m.c] > D.HIGH_M

    def _kontroll(self, dag, m, sel, a, ratio_g, p):
        """Kontrollen av periodens mätare m.subset(sel) (se kontroll()); ger de kastade."""
        g = m.subset(sel)
        xy = np.c_[g.c, g.r].astype(float) * D.RES_KM
        bg = svag_kvot(ratio_g, a, p) * a
        return kontroll(xy, g.mm, bg, self.rng_full[g.r, g.c].astype(float), self._over400(dag, g), p)

    def falt(self, dag, matare, hours=range(24)):
        mq, mh = matare
        kv = np.full(self.kv1.shape, np.nan, np.float32)
        tm = np.full(self.tm1.shape, np.nan, np.float32)
        a_h = self.tm1[mh.t, mh.r, mh.c].astype(float)
        xy_h = np.c_[mh.c, mh.r].astype(float) * D.RES_KM
        ph = self.params["timme"]
        self.kastade = []  # (res, station, period) för kontrollen
        if ph.get("QC_T", 0.0) > 0:
            # timmätarna som kontrollen kastar tas bort ur kvoten och ur timmens OI
            flag = np.zeros(len(mh), bool)
            for hour in range(24):
                sel = mh.t == hour
                if sel.sum() < 3:
                    continue
                win = (mh.t <= hour) & (mh.t > hour - ph["WIN"])
                rg = stor_kvot(xy_h[sel], xy_h[win], mh.mm[win], a_h[win], ph)
                flag[np.flatnonzero(sel)] = self._kontroll(dag, mh, sel, a_h[sel], rg, ph)
            self.kastade += [("timme", s, t) for s, t in zip(mh.station[flag], mh.t[flag])]
            mh = mh.subset(~flag)
            a_h, xy_h = a_h[~flag], xy_h[~flag]
        for hour in hours:
            for res in ("timme", "kvart"):
                p = self.params[res]
                win = (mh.t <= hour) & (mh.t > hour - p["WIN"])
                ratio_c = stor_kvot(self.kxy, xy_h[win], mh.mm[win], a_h[win], p).reshape(self.kshape)
                m = mh if res == "timme" else mq
                periods = [hour] if res == "timme" else range(4 * hour, 4 * hour + 4)
                F = self.tm1 if res == "timme" else self.kv1
                for t in periods:
                    sel = m.t == t
                    xy = np.c_[m.c[sel], m.r[sel]].astype(float) * D.RES_KM
                    ratio_g = stor_kvot(xy, xy_h[win], mh.mm[win], a_h[win], p)
                    if res == "kvart" and p.get("QC_T", 0.0) > 0 and sel.sum() >= 3:
                        a = F[t][m.r[sel], m.c[sel]].astype(float)
                        fl = self._kontroll(dag, m, sel, a, ratio_g, p)
                        if fl.any():
                            idx = np.flatnonzero(sel)[fl]
                            self.kastade += [("kvart", s, t) for s in m.station[idx]]
                            sel = sel.copy()
                            sel[idx] = False
                            ratio_g = ratio_g[~fl]
                    (tm if res == "timme" else kv)[t] = self._period(F[t].astype(np.float32), m, sel, ratio_c, ratio_g, p)
        return kv, tm


def _load_val(day_s):
    rd = D.Radardag(day_s)
    dag = D.build_dag(day_s, rd)
    grid = rd.grid
    del rd
    gc.collect()
    z = np.load(a1_path(day_s))
    return dag, grid, z["kvart"].astype(np.float32), z["timme"].astype(np.float32)


def make_a2(kv1, tm1, grid, params=None):
    return A2(kv1, tm1, radar_range_km(grid), params)


def system_params(namn: str) -> dict:
    """Parametrarna för A2 (PARAMS) eller en fryst variant i FRYSTA (ändringar för kvarten, och för
    timmen under nyckeln "timme")."""
    if namn == "A2":
        return PARAMS
    ch = dict(FRYSTA[namn])
    th = ch.pop("timme", {})  # ändringar för timmen (bara kontrollen av mätarna)
    return {"timme": dict(PARAMS["timme"], **th), "kvart": dict(PARAMS["kvart"], **ch)}


def cmd_kor(a):
    i, n = (int(x) for x in a.bit.split("/"))
    todo = [a.dag] if a.dag else D.days("validering")[i::n]
    namn = a.namn
    params = system_params(namn)
    for day_s in todo:
        assert day_s in D.days("validering")
        target = D.OUT / namn / f"{day_s}.json"
        if target.exists() or not a1_path(day_s).exists():
            continue
        t = time.time()
        dag, grid, kv1, tm1 = _load_val(day_s)
        t1 = time.time()
        res = D.evaluate(make_a2(kv1, tm1, grid, params), dag)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(res))
        print(day_s, namn, f"läst {t1 - t:.0f} s, A2 och domaren {time.time() - t1:.0f} s", flush=True)
        del dag, kv1, tm1
        gc.collect()


def cmd_tid(a):
    day_s = a.dag or "2023-08-08"
    dag, grid, kv1, tm1 = _load_val(day_s)
    s = make_a2(kv1, tm1, grid)
    hour = 14
    t = time.time()
    s.falt(dag, (dag.kvart, dag.timme), hours=[hour])
    dt = time.time() - t
    print(f"{day_s} timme {hour}: en timme och dess fyra kvartar på hela rutnätet {dt:.2f} s "
          f"({len(dag.timme.t[dag.timme.t == hour])} timmätare, {(dag.kvart.t // 4 == hour).sum()} kvartsvärden)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["a1falt", "punkter", "terrang", "diagnos", "varianter", "trana", "kor",
                                    "tid", "kontroll", "varianter_qc"])
    ap.add_argument("--qc", nargs=3, default=["4", "50", "1"], help="kontroll: T R skydd400 (1/0)")
    ap.add_argument("--ph", nargs=3, help="varianter_qc: kontrollen av timmätarna i kvarten, T R skydd400")
    ap.add_argument("--bara", nargs="+", help="varianter_qc: bara de här varianterna")
    ap.add_argument("--syntet", type=float, default=0.0, help="varianter_qc: andel syntetiska fel i indata")
    ap.add_argument("--bit", default="0/1")
    ap.add_argument("--dag")
    ap.add_argument("--namn", default="A2", help="kor: A2 eller en fryst variant i FRYSTA")
    ap.add_argument("--res", nargs="+", default=["timme", "kvart"])
    ap.add_argument("--dagar", type=int, default=0, help="trana: bara de första dagarna (provkörning)")
    a = ap.parse_args()
    {"a1falt": cmd_a1falt, "punkter": cmd_punkter, "terrang": cmd_terrang, "diagnos": cmd_diagnos,
     "varianter": cmd_varianter, "trana": cmd_trana, "kor": cmd_kor, "tid": cmd_tid,
     "kontroll": cmd_kontroll, "varianter_qc": cmd_varianter_qc}[a.cmd](a)


if __name__ == "__main__":
    main()
