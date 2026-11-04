"""Domaren: kör ett utfyllnadssystem på bortfallsfallen och jämför det med radarn och baslinjen.

    uv run python experiments/bortfall/domare.py kor fylld hal utjamnad --del validering --processer 2
    uv run python experiments/bortfall/domare.py kor fylld --fall 3            provkörning på tre fall
    uv run python experiments/bortfall/domare.py tabell fylld hal utjamnad --mot fylld

Domaren är den enda som avgör om ett system är bättre. Ändra inte måtten för att ett system ska
se bättre ut; behöver de rättas, skriv det i rapporten och kör om baslinjerna.

Systemen
--------
Ett system är en klass med `start(indata)` och `steg(k, indata) -> mm/h (h, w)`. Domaren matar det
bild för bild, så att det bara ser det som hade funnits i realtid:

- `start`: uppvärmningen (60 min riktig radar, `indata.forfluten`), hålet, avståndet till närmaste
  fungerande radar, utsnittets läge och tid.
- `steg(k, ...)`: bortfallets bild k (ålder 5(k + 1) min), med radarn utanför hålet (NaN i hålet),
  MEPS för timmar som har börjat (körningen var tillgänglig vid timmens början, se fall.py) och
  regnmätare med periodens slut minst 60 min före bilden (så sent kommer de i realtid).

Systemet returnerar analysen för hela utsnittet. Domaren använder bara hålet ur den; utanför hålet
sätts den riktiga radarn, så att ett system inte kan påverka sömmen genom att ändra radarn utanför.
NaN i hålet räknas som 0 mm/h (ingen analys).

Bortfallet
----------
Fallets bilder går från 60 min före starten till slutet (fall.py). Bilderna med index
`uppvarmning_bilder` (12) till näst sista saknas, alltså tiderna start <= t < slut, och har
åldern 5, 10, ..., längden min (tid sedan senaste riktiga bilden, som `age` i composite.fill_gaps).
Den sista bilden (vid slutet) är när radarn kommer tillbaka och bedöms inte.

Måtten, per åldersklass (0, 30], (30, 90] och (90, 360] min
----------------------------------------------------------
Pixlarna som bedöms är hålet där radarn har data (m). Alla mått sparas som summor per fall och
klass, så att de kan läggas ihop över dagar och dras om i bootstrap.

- FSS vid 1 och 5 mm/h på 10 och 30 km (fönster 5 och 15 pixlar). Andelarna räknas bara ur
  pixlarna i m (normaliserad faltning), så att radarn utanför hålet inte höjer FSS nära kanten.
  FSS = 1 - sum (Pf - Po)^2 / sum (Pf^2 + Po^2), summerat över pixlar och bilder.
- CSI vid 0,5, 1 och 5 mm/h: träffar / (träffar + missar + falsklarm), summerat.
- Volym: sum system / sum radar i m. Jämförs som |volym - 1|.
- Söm: i ett band 2 pixlar på var sida om hålets kant, medel av | |grad R_system| - |grad R_radar| |
  i mm/h per pixel (centrala differenser). Analysen är system i hålet och radar utanför.
  `som_skev` är samma med tecken (positiv: brantare kant än radarn).
- Mätare (oberoende kontroll): kvartssummor (p14) och timsummor (p7) från mätare i hålet, vars hela
  period ligger i bortfallet. Medelabsolutfel i mm mot mätaren, för systemet och för radarn.
  Klassen ges av åldern vid periodens slut. Värden under 0 och över MATARE_MAX_MM (30 mm per
  kvart, 60 mm per timme) är fel i arkivet och räknas inte.

Bootstrap
---------
Skillnaden system minus baslinje med 95 %-intervall från bootstrap över dagarna (fall samma dag
delar regn och är beroende): dagarna dras med återläggning 2000 gånger med fast frö, summorna läggs
ihop och måttet räknas om. Ett resultat räknas bara om hela intervallet ligger på den bättre sidan.

Resultaten sparas per system i experiments/bortfall/resultat/<del>/<system>.json.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from scipy.ndimage import binary_dilation, binary_erosion, uniform_filter

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1] / "src"))

from knep import composite  # noqa: E402

FALL = Path("/data/bortfall/fall")
RESULTAT = HERE / "resultat"

KLASSER = ((0, 30), (30, 90), (90, 360))   # (a, b] min
FSS_MM = (1.0, 5.0)
FSS_KM = (10, 30)
PIXEL_KM = 2.0
CSI_MM = (0.5, 1.0, 5.0)
SOM_PX = 2
MATARE_FORDROJNING = timedelta(minutes=60)
# Fysisk spärr för mätarna: arkivet har uppenbart felaktiga värden (en station med 180 mm per
# kvart i timmar, ett värde på 498 071 mm). Över 20 mm per kvart och 40 mm per timme finns i
# arkivet nästan bara sådana, så gränserna 30 och 60 mm tar bort felen och inget riktigt skyfall.
MATARE_MAX_MM = {"p14": 30.0, "p7": 60.0}
BOOT_N, BOOT_FRO = 2000, 20261103
MIN_DAGAR = 5   # färre dagar än så ger ingen dom (bootstrapintervallet säger då inget)


def klass_for(age_min: float) -> int | None:
    for i, (a, b) in enumerate(KLASSER):
        if a < age_min <= b:
            return i
    return None


def klassnamn(i: int) -> str:
    a, b = KLASSER[i]
    return f"{a}-{b} min"


def fonster(km: float) -> int:
    """Udda fönsterbredd i pixlar för en skala i km (10 km -> 5, 30 km -> 15)."""
    n = int(round(km / PIXEL_KM))
    return n if n % 2 else n + 1


# --- måtten på en bild ------------------------------------------------------------------------

def _fractions(binary: np.ndarray, m: np.ndarray, n: int) -> np.ndarray:
    """Andel över tröskeln i fönstret n x n, räknat bara över pixlarna i m."""
    num = uniform_filter(np.where(m, binary, 0.0).astype(np.float64), n, mode="constant")
    den = uniform_filter(m.astype(np.float64), n, mode="constant")
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > 1e-9, num / den, 0.0)


def fss_sums(f: np.ndarray, o: np.ndarray, m: np.ndarray, thr: float, n: int) -> tuple[float, float]:
    """(sum (Pf - Po)^2, sum (Pf^2 + Po^2)) över m."""
    pf = _fractions(f >= thr, m, n)[m]
    po = _fractions(o >= thr, m, n)[m]
    return float(((pf - po) ** 2).sum()), float((pf**2 + po**2).sum())


def csi_sums(f: np.ndarray, o: np.ndarray, m: np.ndarray, thr: float) -> tuple[int, int, int]:
    """(träffar, missar, falsklarm) över m."""
    fy, oy = (f >= thr)[m], (o >= thr)[m]
    return int((fy & oy).sum()), int((~fy & oy).sum()), int((fy & ~oy).sum())


def kantband(hole: np.ndarray, px: int = SOM_PX) -> np.ndarray:
    """Pixlarna inom px från hålets kant, på båda sidor."""
    return binary_dilation(hole, iterations=px) & ~binary_erosion(hole, iterations=px, border_value=1)


def gradient(r: np.ndarray) -> np.ndarray:
    gy, gx = np.gradient(r.astype(np.float64))
    return np.hypot(gx, gy)


def som_sums(analys: np.ndarray, radar: np.ndarray, band: np.ndarray) -> tuple[float, float, int]:
    """(sum |ga - gr|, sum (ga - gr), antal) i bandet där radarns gradient finns.

    analys: system i hålet och radar utanför, utan NaN i hålet. NaN utanför täckning ger NaN i
    gradienten och de pixlarna räknas inte.
    """
    ga, gr = gradient(analys), gradient(radar)
    ok = band & np.isfinite(ga) & np.isfinite(gr)
    d = (ga - gr)[ok]
    return float(np.abs(d).sum()), float(d.sum()), int(ok.sum())


def tom_klass() -> dict:
    s = {f"fss_{mm:g}_{km}": [0.0, 0.0] for mm in FSS_MM for km in FSS_KM}
    s |= {f"csi_{mm:g}": [0, 0, 0] for mm in CSI_MM}
    s |= {"vol": [0.0, 0.0], "som": [0.0, 0.0, 0], "px": 0, "bilder": 0}
    s |= {f"m{p}": [0.0, 0.0, 0] for p in ("p14", "p7")}   # sum |sys - g|, sum |radar - g|, antal
    return s


def bild_sums(s: dict, f: np.ndarray, o: np.ndarray, hole: np.ndarray, band: np.ndarray) -> None:
    """Lägg till en bild i klassens summor. f: systemets fält (NaN = 0 i hålet), o: radarn."""
    m = hole & np.isfinite(o)
    f = np.where(hole, np.nan_to_num(f, nan=0.0), o)
    oz = np.nan_to_num(o, nan=0.0)
    fz = np.nan_to_num(f, nan=0.0)
    for mm in FSS_MM:
        for km in FSS_KM:
            a, b = fss_sums(fz, oz, m, mm, fonster(km))
            s[f"fss_{mm:g}_{km}"][0] += a
            s[f"fss_{mm:g}_{km}"][1] += b
    for mm in CSI_MM:
        for i, v in enumerate(csi_sums(fz, oz, m, mm)):
            s[f"csi_{mm:g}"][i] += v
    s["vol"][0] += float(fz[m].sum())
    s["vol"][1] += float(oz[m].sum())
    for i, v in enumerate(som_sums(f, o, band)):
        s["som"][i] += v
    s["px"] += int(m.sum())
    s["bilder"] += 1


# --- från summor till mått --------------------------------------------------------------------

MATT = [f"fss_{mm:g}_{km}" for mm in FSS_MM for km in FSS_KM] + [f"csi_{mm:g}" for mm in CSI_MM] + \
    ["vol", "som", "som_skev", "mae_p14", "mae_p7"]
HOGRE_BATTRE = {k: k.startswith(("fss", "csi")) for k in MATT}


def matt(s: dict) -> dict:
    """Måtten ur summorna (NaN där underlag saknas)."""
    out = {}
    nan = float("nan")
    for mm in FSS_MM:
        for km in FSS_KM:
            a, b = s[f"fss_{mm:g}_{km}"]
            out[f"fss_{mm:g}_{km}"] = 1 - a / b if b > 0 else nan
    for mm in CSI_MM:
        h, mi, fa = s[f"csi_{mm:g}"]
        out[f"csi_{mm:g}"] = h / (h + mi + fa) if h + mi + fa else nan
    out["vol"] = s["vol"][0] / s["vol"][1] if s["vol"][1] > 0 else nan
    out["som"] = s["som"][0] / s["som"][2] if s["som"][2] else nan
    out["som_skev"] = s["som"][1] / s["som"][2] if s["som"][2] else nan
    for p in ("p14", "p7"):
        a, _, n = s[f"m{p}"]
        out[f"mae_{p}"] = a / n if n else nan
    return out


def radar_mae(s: dict) -> dict:
    return {f"mae_{p}": (s[f"m{p}"][1] / s[f"m{p}"][2] if s[f"m{p}"][2] else float("nan")) for p in ("p14", "p7")}


def jamforbar(namn: str, v: float) -> float:
    """Värdet som skillnaden räknas på: volymen som |volym - 1|, sömmen som den är."""
    return abs(v - 1) if namn == "vol" else v


def summera(klasser: list[dict]) -> dict:
    out = tom_klass()
    for s in klasser:
        for k, v in s.items():
            if isinstance(v, list):
                out[k] = [a + b for a, b in zip(out[k], v)]
            else:
                out[k] += v
    return out


# --- indata till systemen ---------------------------------------------------------------------

@dataclass
class Indata:
    """Det ett system får se. Under bortfallet är radarn NaN i hålet."""

    namn: str
    tider: list[datetime]          # alla bildtider i fallet
    k0: int                        # index för bortfallets första bild
    n: int                         # antal bilder i bortfallet
    hal: np.ndarray                # bool (h, w)
    avstand: np.ndarray            # km till närmaste fungerande radar
    forfluten: np.ndarray          # (k0, h, w) mm/h, uppvärmningen
    meta: dict
    bild: np.ndarray | None = None              # aktuell bild, NaN i hålet
    tid: datetime | None = None
    meps: dict = field(default_factory=dict)    # timmens slut -> mm/h (h, w), timmar som börjat
    matare: dict = field(default_factory=dict)  # p7/p14 -> fält som i fall.py, bara det som kommit


class Fall:
    """Ett fall från fall.py, med facit. Facit i hålet under bortfallet ges aldrig till systemet."""

    def __init__(self, path: Path):
        with np.load(path) as z:
            self.meta = json.loads(str(z["meta"]))
            from fall import to_rain  # samma tabell som fallen byggdes med
            self.radar = to_rain(z["radar"])
            self.hal = z["hal"].astype(bool)
            self.avstand = z["avstand"].astype(np.float32)
            self.meps = z["meps"].astype(np.float32)
            self.matare = {}
            for p in ("p7", "p14"):
                keys = [k for k in z.files if k.startswith(f"matare_{p}_")]
                if keys:
                    self.matare[p] = {k.split("_", 2)[2]: z[k] for k in keys}
        m = self.meta
        t0 = datetime.fromisoformat(m["forsta_bild"])
        self.tider = [t0 + timedelta(minutes=5 * k) for k in range(m["bilder"])]
        self.k0 = m["uppvarmning_bilder"]
        self.n = m["langd_min"] // 5
        self.meps_slut = [datetime.fromisoformat(t) for t in m["meps_tid"]]

    @property
    def dag(self) -> str:
        return self.meta["dag"]

    def indata(self) -> Indata:
        return Indata(self.meta["namn"], self.tider, self.k0, self.n, self.hal.copy(), self.avstand.copy(),
                      self.radar[: self.k0].copy(), self.meta)

    def maskad(self, k: int) -> np.ndarray:
        b = self.radar[self.k0 + k].copy()
        b[self.hal] = np.nan
        return b

    def meps_till(self, t: datetime) -> dict:
        return {e: self.meps[i] for i, e in enumerate(self.meps_slut)
                if e - timedelta(hours=1) <= t and i < len(self.meps)}

    def matare_till(self, t: datetime) -> dict:
        grans = (t - MATARE_FORDROJNING).timestamp()
        return {p: {k: v[g["tid"] <= grans] for k, v in g.items()} for p, g in self.matare.items()}


# --- baslinjerna ------------------------------------------------------------------------------

class Hal:
    """Ingen utfyllnad: hålet lämnas tomt."""

    namn = "hal"

    def start(self, ind: Indata) -> None:
        pass

    def steg(self, k: int, ind: Indata) -> np.ndarray:
        return ind.bild


class Fylld:
    """composite.fill_gaps som i drift: förra analysen flyttad med rörelsen, släpps efter 90 min.

    Rörelsen räknas som i kedjan (model.motion_field med gap 3, 3 bilder, step 4) på de senaste
    analyserna, inklusive de utfyllda, och används en cykel senare, precis som i drift där
    motion.npy sparas av förra cykeln. Tillståndet byggs upp över uppvärmningen; den förväntade
    täckningen börjar som andelen bilder med data under uppvärmningen (i drift ett glidande dygn).
    Skillnad mot drift: rörelsen räknas på utsnittet och inte på hela Sverige.
    """

    namn = "fylld"
    smooth = False

    def start(self, ind: Indata) -> None:
        f = ind.forfluten
        have = np.isfinite(f)
        self.state = composite.GapState(f[0].copy(), np.where(have[0], 0.0, np.inf).astype(np.float32),
                                        have.mean(axis=0).astype(np.float32))
        self.analyser = [f[0]]
        self.motion = None
        for b in f[1:]:
            self._ett(b)

    def _ett(self, b: np.ndarray) -> np.ndarray:
        src = np.where(np.isfinite(b), composite.SOURCE_SMHI, composite.SOURCE_NONE).astype(np.uint8)
        out, _, _, self.state = composite.fill_gaps(b, src, self.state, self.motion, smooth=self.smooth)
        # i drift sparas den visade analysen (out) och kedjan räknar rörelsen på den
        self.analyser = (self.analyser + [out])[-7:]
        from knep.model import motion_field
        self.motion = motion_field(np.stack(self.analyser), 3, 3, 4) if len(self.analyser) >= 2 else None
        return out

    def steg(self, k: int, ind: Indata) -> np.ndarray:
        return self._ett(ind.bild)


class Utjamnad(Fylld):
    """fill_gaps med smooth: den flyttade analysen jämnas ut mer ju äldre den är."""

    namn = "utjamnad"
    smooth = True


class Facit:
    """Radarn själv. Bara för kontroll av domaren (FSS och CSI 1, volym 1, söm 0)."""

    namn = "facit"

    def start(self, ind: Indata) -> None:
        pass

    def steg(self, k: int, ind: Indata) -> np.ndarray:
        raise RuntimeError("facit körs av domaren direkt")


SYSTEM = {c.namn: c for c in (Hal, Fylld, Utjamnad, Facit)}


def ladda_system(namn: str):
    """Ett system ur SYSTEM, eller modul:Klass under experiments/bortfall."""
    if namn in SYSTEM:
        return SYSTEM[namn]()
    mod, _, cls = namn.partition(":")
    import importlib

    return getattr(importlib.import_module(mod), cls)()


# --- körningen --------------------------------------------------------------------------------

def matare_sums(s_klasser: list[dict], fall: Fall, analyser: np.ndarray) -> None:
    """Mätarna i hålet vars hela period ligger i bortfallet: |system - mätare| och |radar - mätare|."""
    t_first = fall.tider[fall.k0]
    t_last = fall.tider[fall.k0 + fall.n - 1]
    for p, minutes in (("p14", 15), ("p7", 60)):
        g = fall.matare.get(p)
        if not g or not len(g["tid"]):
            continue
        nb = minutes // 5
        for i in np.nonzero(g["i_hal"])[0]:
            slut = datetime.fromtimestamp(float(g["tid"][i]), tz=t_first.tzinfo)
            forsta = slut - timedelta(minutes=minutes - 5)   # bilderna forsta .. slut täcker perioden
            if forsta < t_first or slut > t_last or not np.isfinite(g["mm"][i]):
                continue
            if not 0 <= g["mm"][i] <= MATARE_MAX_MM[p]:
                continue
            j0 = int((forsta - t_first) / timedelta(minutes=5))
            r, c = int(g["rad"][i]), int(g["kol"][i])
            sys_mm = float(np.nansum(np.nan_to_num(analyser[j0:j0 + nb, r, c], nan=0.0))) * 5 / 60
            rad = fall.radar[fall.k0 + j0:fall.k0 + j0 + nb, r, c]
            if not np.isfinite(rad).all():
                continue
            rad_mm = float(rad.sum()) * 5 / 60
            kl = klass_for(5 * (j0 + nb))
            if kl is None:
                continue
            s = s_klasser[kl][f"m{p}"]
            s[0] += abs(sys_mm - float(g["mm"][i]))
            s[1] += abs(rad_mm - float(g["mm"][i]))
            s[2] += 1


def kor_fall(system, fall: Fall) -> dict:
    """Kör systemet på fallet och returnerar summorna per klass."""
    ind = fall.indata()
    system.start(ind)
    band = kantband(fall.hal)
    klasser = [tom_klass() for _ in KLASSER]
    analyser = np.full((fall.n,) + fall.hal.shape, np.nan, np.float32)
    for k in range(fall.n):
        t = fall.tider[fall.k0 + k]
        if isinstance(system, Facit):
            f = fall.radar[fall.k0 + k]
        else:
            ind.bild, ind.tid = fall.maskad(k), t
            ind.meps, ind.matare = fall.meps_till(t), fall.matare_till(t)
            f = np.asarray(system.steg(k, ind), np.float32)
            if f.shape != fall.hal.shape:
                raise ValueError(f"{system.namn}: fel form {f.shape}")
        analyser[k] = np.where(fall.hal, np.nan_to_num(f, nan=0.0), np.nan)
        kl = klass_for(5 * (k + 1))
        if kl is not None:
            bild_sums(klasser[kl], f, fall.radar[fall.k0 + k], fall.hal, band)
    matare_sums(klasser, fall, analyser)
    return {"namn": fall.meta["namn"], "dag": fall.dag, "langd_min": fall.meta["langd_min"], "klasser": klasser}


def _kor_en(args):
    namn, path = args
    t = time.monotonic()
    r = kor_fall(ladda_system(namn), Fall(path))
    r["sekunder"] = round(time.monotonic() - t, 1)
    return r


def kor(a) -> None:
    idx = json.loads((FALL / a.part / "index.json").read_text())["fall"]
    if a.part not in ("validering", "traning"):
        raise ValueError("testdelen används inte")
    paths = [FALL / a.part / c["fil"] for c in idx]
    if a.fall:
        paths = paths[: a.fall]
    out_dir = RESULTAT / a.part
    out_dir.mkdir(parents=True, exist_ok=True)
    for namn in a.system:
        t0 = time.monotonic()
        jobs = [(namn, p) for p in paths]
        if a.processer > 1:
            from multiprocessing import Pool

            with Pool(a.processer) as pool:
                res = []
                for i, r in enumerate(pool.imap(_kor_en, jobs)):
                    res.append(r)
                    print(namn, i + 1, len(jobs), r["namn"], r["sekunder"], "s", flush=True)
        else:
            res = []
            for i, j in enumerate(jobs):
                res.append(_kor_en(j))
                print(namn, i + 1, len(jobs), res[-1]["namn"], res[-1]["sekunder"], "s", flush=True)
        suffix = "" if not a.fall else f"_prov{a.fall}"
        doc = {"system": namn, "del": a.part, "fall": res, "sekunder": round(time.monotonic() - t0)}
        (out_dir / f"{namn.replace(':', '_')}{suffix}.json").write_text(json.dumps(doc) + "\n")
        print(namn, "klar på", doc["sekunder"], "s", flush=True)


# --- tabellen och bootstrap -------------------------------------------------------------------

def per_dag(res: dict) -> dict[str, list[dict]]:
    """dag -> summor per klass."""
    dagar: dict[str, list[list[dict]]] = {}
    for r in res["fall"]:
        dagar.setdefault(r["dag"], []).append(r["klasser"])
    return {d: [summera([c[i] for c in v]) for i in range(len(KLASSER))] for d, v in dagar.items()}


def bootstrap(a_dag: dict, b_dag: dict, klass: int, n=BOOT_N, seed=BOOT_FRO) -> dict:
    """Skillnaden a - b per mått med 95 %-intervall, dagarna dragna med återläggning."""
    dagar = sorted(set(a_dag) & set(b_dag))
    rng = np.random.default_rng(seed)
    draws = rng.integers(len(dagar), size=(n, len(dagar)))

    def diff(sel):
        ma = matt(summera([a_dag[dagar[i]][klass] for i in sel]))
        mb = matt(summera([b_dag[dagar[i]][klass] for i in sel]))
        return {k: jamforbar(k, ma[k]) - jamforbar(k, mb[k]) for k in MATT}

    point = diff(range(len(dagar)))
    samples = [diff(s) for s in draws]
    out = {}
    for k in MATT:
        v = np.array([s[k] for s in samples], float)
        v = v[np.isfinite(v)]
        lo, hi = (np.percentile(v, [2.5, 97.5]) if v.size else (np.nan, np.nan))
        hb = HOGRE_BATTRE[k]
        if k == "som_skev" or len(dagar) < MIN_DAGAR:
            dom = ""   # bara beskrivande
        elif (lo > 0 and hb) or (hi < 0 and not hb):
            dom = "bättre"
        elif (hi < 0 and hb) or (lo > 0 and not hb):
            dom = "sämre"
        else:
            dom = ""
        out[k] = {"diff": point[k], "lo": float(lo), "hi": float(hi), "dom": dom}
    return out


RUBRIK = {"fss_1_10": "FSS 1 mm 10 km", "fss_1_30": "FSS 1 mm 30 km", "fss_5_10": "FSS 5 mm 10 km",
          "fss_5_30": "FSS 5 mm 30 km", "csi_0.5": "CSI 0,5", "csi_1": "CSI 1", "csi_5": "CSI 5",
          "vol": "volym", "som": "söm", "som_skev": "söm skev", "mae_p14": "MAE kvart", "mae_p7": "MAE timme"}


def _f(v: float, d=3) -> str:
    return "" if not np.isfinite(v) else f"{v:.{d}f}".replace(".", ",")


def tabell_text(resultat: dict[str, dict], mot: str) -> str:
    dag = {k: per_dag(v) for k, v in resultat.items()}
    rader = []
    for kl in range(len(KLASSER)):
        n_fall = sum(1 for c in resultat[mot]["fall"] if c["klasser"][kl]["bilder"])
        tot = summera([d[kl] for d in dag[mot].values()])
        rader.append(f"\n### Ålder {klassnamn(kl)} ({n_fall} fall, {tot['bilder']} bilder, "
                     f"{len(dag[mot])} dagar)\n")
        rader.append("| system | " + " | ".join(RUBRIK[k] for k in MATT) + " |")
        rader.append("|---" * (len(MATT) + 1) + "|")
        for namn, d in dag.items():
            s = summera([x[kl] for x in d.values()])
            m = matt(s)
            rader.append(f"| {namn} | " + " | ".join(_f(m[k]) for k in MATT) + " |")
        m = radar_mae(tot)
        rader.append("| (radarn mot mätarna) | " + " | ".join(_f(m.get(k, np.nan)) for k in MATT) + " |")
        for namn in dag:
            if namn == mot:
                continue
            b = bootstrap(dag[namn], dag[mot], kl)
            cell = lambda x: "" if not np.isfinite(x["diff"]) else \
                f"{_f(x['diff'])} [{_f(x['lo'])}; {_f(x['hi'])}]{' **' + x['dom'] + '**' if x['dom'] else ''}"
            rader.append(f"| {namn} − {mot} | " + " | ".join(cell(b[k]) for k in MATT) + " |")
    return "\n".join(rader) + "\n"


def tabell(a) -> None:
    resultat = {}
    for namn in a.system:
        p = RESULTAT / a.part / f"{namn.replace(':', '_')}{a.suffix}.json"
        resultat[namn] = json.loads(p.read_text())
    if a.mot not in resultat:
        raise SystemExit(f"baslinjen {a.mot} måste vara med bland systemen")
    print(tabell_text(resultat, a.mot))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cmd", choices=["kor", "tabell"])
    p.add_argument("system", nargs="+")
    p.add_argument("--del", dest="part", choices=["traning", "validering"], default="validering")
    p.add_argument("--fall", type=int, help="bara de första n fallen (provkörning)")
    p.add_argument("--processer", type=int, default=1)
    p.add_argument("--mot", default="fylld", help="baslinjen som skillnaden räknas mot")
    p.add_argument("--suffix", default="", help="till exempel _prov3 för en provkörning")
    p.add_argument("--logg", type=Path)
    a = p.parse_args()
    if a.processer > 2:
        raise SystemExit("högst två processer i natt")
    if a.logg:
        sys.stdout = sys.stderr = open(a.logg, "a", buffering=1)
    {"kor": kor, "tabell": tabell}[a.cmd](a)


if __name__ == "__main__":
    main()
