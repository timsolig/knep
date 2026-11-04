"""MEPS i hålet: MEPS rättad mot radarn utanför hålet, och blandningar med den flyttade analysen.

    uv run python experiments/bortfall/meps_hal.py sok --processer 2 --logg /data/bortfall/logg/meps_sok.log
    uv run python experiments/bortfall/domare.py kor meps_hal:Meps meps_hal:Blandning --processer 2

Systemen (för domaren, se domare.py)
------------------------------------
- `Meps`: hålet fylls med MEPS rättad mot radarn utanför hålet, som i knep.seamless: läget med
  optiskt flöde och mängden med kvantilavbildning, båda skattade på senaste radartimmen (medel av
  de senaste 12 bilderna) mot MEPS i timmens mitt, och utjämnade mellan bilderna med samma minne
  som i drift (seamless._per_cycle). Under bortfallet skattas rättningen bara utanför hålet. Inne
  i hålet, där radarn saknas, sätts lägesrättningen till ett utjämnat medel av den utanför.
  MEPS-timmarna tolkas som intensiteten mitt i timmen och interpoleras i tiden (som
  seamless.meps_at), men bara timmar som har börjat används (domaren ger inte fler).
- `Blandning`: den flyttade analysen (composite.fill_gaps som i drift, men utan att släppa
  pixlarna efter 90 min) och den rättade MEPS blandas per skala med vikter efter bortfallets
  ålder, som seamless.blend gör med ledtiden: den flyttade analysens vikt är
  1 / (1 + (ålder / t50) ** form), med ett t50 för de små skalorna och ett för de stora
  (gaussisk skalgräns 30 km). Sist får hålet en värdefördelning mellan den flyttade analysens och
  MEPS:s, med de små skalornas vikt. Vikterna är valda på träningsfallen (`sok`) och frysta i
  meps_vikter.json.
- Fall utan MEPS (2019, äldre rutnät) får `fylld` (driften), så att systemen inte straffas för
  data som saknas; det gäller 16 av 128 valideringsfall.

Valet av vikter (`sok`)
-----------------------
Ett urval av träningsfallen (de två längsta per dag) körs en gång; den flyttade analysen och den
rättade MEPS räknas en gång per fall, och varje kandidat bedöms med domarens egna summor
(domare.bild_sums) på varannan bild. Poängen är medlet över de tre åldersklasserna av medlet av de
fyra FSS och de tre CSI. Kandidaten med högst poäng skrivs till meps_vikter.json.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass, replace
import warnings
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "src"))

import domare  # noqa: E402
from knep import composite, seamless  # noqa: E402

VIKTER = HERE / "meps_vikter.json"


@dataclass
class Vikter:
    t50_small: float = 60.0   # min: ålder där den flyttade analysens vikt för de små skalorna är 0,5
    t50_large: float = 150.0  # min: samma för de stora skalorna
    shape: float = 2.5
    sigma_km: float = 30.0
    match: bool = True


def las_vikter(path: Path = VIKTER) -> Vikter:
    if not path.exists():
        return Vikter()
    d = json.loads(path.read_text())
    return Vikter(**d["vikter"])


# --- MEPS i tiden och rättningen --------------------------------------------------------------

def meps_vid(meps: dict, t) -> np.ndarray | None:
    """MEPS-intensiteten vid t ur timsummorna (timmens slut -> mm/h), linjärt mellan timmarnas
    mittpunkter och konstant utanför. None om ingen timme finns."""
    if not meps:
        return None
    slut = sorted(meps)
    mitt = [e - timedelta(minutes=30) for e in slut]
    if t <= mitt[0]:
        return meps[slut[0]]
    if t >= mitt[-1]:
        return meps[slut[-1]]
    for i in range(len(mitt) - 1):
        if mitt[i] <= t <= mitt[i + 1]:
            w = (t - mitt[i]) / (mitt[i + 1] - mitt[i])
            return ((1 - w) * meps[slut[i]] + w * meps[slut[i + 1]]).astype(np.float32)
    return meps[slut[-1]]


def korning_vid(meta: dict, t) -> str:
    """Körningen för MEPS-timmen som innehåller t (för att nollställa rättningen vid byte)."""
    tider, korn = meta.get("meps_tid", []), meta.get("meps_korning", [])
    for e, k in zip(tider, korn):
        e = datetime.fromisoformat(e)
        if e - timedelta(hours=1) <= t < e:
            return k.split("+")[0]
    return korn[-1].split("+")[0] if korn else ""


def fyll_i_hal(x: np.ndarray, hole: np.ndarray, sigma_px: float = 25.0) -> np.ndarray:
    """Ersätt x i hålet med ett gaussiskt viktat medel av x utanför (globalt medel där det är glest)."""
    w = (~hole & np.isfinite(x)).astype(np.float32)
    if w.sum() == 0:
        return x
    v = np.where(w > 0, x, 0).astype(np.float32)
    num, den = seamless.gaussian_filter(v, sigma_px), seamless.gaussian_filter(w, sigma_px)
    glob = float(v.sum() / w.sum())
    fill = np.where(den > 0.05, num / np.maximum(den, 1e-6), glob)
    return np.where(hole, fill, x).astype(np.float32)


class Rattning:
    """MEPS rättad mot radarn (seamless.assimilate/corrected), med hålet maskat under bortfallet."""

    def __init__(self, hole: np.ndarray, p: seamless.Params | None = None):
        self.hole = hole
        self.p = p or seamless.Params()
        self.pc = seamless._per_cycle(self.p)
        self.state = seamless.State()
        self.fonster: list[np.ndarray] = []

    def lagg_till(self, bild: np.ndarray) -> None:
        self.fonster = (self.fonster + [bild])[-12:]

    def assimilera(self, meps: dict, meta: dict, t, under_bortfall: bool) -> None:
        if not meps or len(self.fonster) < 6:
            return
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            radar_tim = np.nanmean(np.stack(self.fonster), axis=0)
        if under_bortfall:
            radar_tim = radar_tim.copy()
            radar_tim[self.hole] = np.nan
        tm = t - timedelta(minutes=2.5 * (len(self.fonster) - 1))   # mitt i radartimmen
        m = meps_vid(meps, tm)
        run = korning_vid(meta, t)
        ny = self.state.run != run
        self.state = seamless.assimilate(self.state, run, m, radar_tim, self.p if ny else self.pc)
        if self.state.dx is not None:
            self.state.dx = fyll_i_hal(self.state.dx, self.hole)
            self.state.dy = fyll_i_hal(self.state.dy, self.hole)

    def falt(self, meps: dict, t) -> np.ndarray | None:
        m = meps_vid(meps, t)
        if m is None:
            return None
        # ledtid 0: lägesrättningen gäller fullt; rättningen skattas om varje bild
        return seamless.corrected(m, 0.0, self.state, self.p)


# --- blandningen ------------------------------------------------------------------------------

def vikt(age_min: float, t50: float, shape: float) -> float:
    if t50 <= 0:
        return 0.0
    if not np.isfinite(t50):
        return 1.0
    return seamless.weight(age_min, t50, shape)


def blanda(flytt: np.ndarray, meps: np.ndarray, radar: np.ndarray, hole: np.ndarray, age_min: float,
           v: Vikter) -> np.ndarray:
    """Hålet som en blandning per skala av den flyttade analysen och MEPS; radarn utanför.

    flytt: flyttad analys (NaN där den saknas), meps: rättad MEPS, radar: bilden med NaN i hålet.
    """
    ws, wl = vikt(age_min, v.t50_small, v.shape), vikt(age_min, v.t50_large, v.shape)
    m = np.nan_to_num(meps).astype(np.float32)
    inne = np.where(np.isfinite(flytt), flytt, m)
    c = np.where(hole, inne, np.where(np.isfinite(radar), radar, m)).astype(np.float32)
    s = v.sigma_km / 2.0
    cl, ml = seamless.gaussian_filter(c, s), seamless.gaussian_filter(m, s)
    out = wl * cl + (1 - wl) * ml + ws * (c - cl) + (1 - ws) * (m - ml)
    out = np.maximum(out, 0).astype(np.float32)
    if v.match and 0 < ws < 1:
        ok = hole & np.isfinite(meps)
        a = np.where(np.isfinite(flytt[ok]), flytt[ok], meps[ok])
        target = ws * np.sort(a) + (1 - ws) * np.sort(meps[ok])
        order = np.argsort(out[ok] + 1e-3 * seamless.gaussian_filter(out, 2.0)[ok], kind="stable")
        vals = np.empty(order.size, np.float32)
        vals[order] = target
        out[ok] = vals
    res = radar.copy()
    res[hole] = out[hole]
    return res


# --- systemen ---------------------------------------------------------------------------------

class Flytt(domare.Fylld):
    """fill_gaps som i drift men utan att släppa pixlarna efter max_age (standard: aldrig)."""

    namn = "flytt"
    max_age = 1e9

    def _ett(self, b: np.ndarray) -> np.ndarray:
        src = np.where(np.isfinite(b), composite.SOURCE_SMHI, composite.SOURCE_NONE).astype(np.uint8)
        out, _, _, self.state = composite.fill_gaps(b, src, self.state, self.motion, max_age=self.max_age)
        self.analyser = (self.analyser + [out])[-7:]
        from knep.model import motion_field
        self.motion = motion_field(np.stack(self.analyser), 3, 3, 4) if len(self.analyser) >= 2 else None
        return out


class Meps:
    """Hålet fylls med MEPS rättad mot radarn utanför hålet. Utan MEPS: fylld."""

    namn = "meps"

    def start(self, ind: domare.Indata) -> None:
        self.utan = not ind.meta.get("meps_tid")
        if self.utan:
            self.reserv = domare.Fylld()
            self.reserv.start(ind)
            return
        self.r = Rattning(ind.hal)
        for b in ind.forfluten:
            self.r.lagg_till(b)
        self.forsta = True

    def _meps(self, ind: domare.Indata) -> np.ndarray | None:
        if self.forsta:
            # uppvärmningens timme mot MEPS innan bortfallet: hela fältet är riktig radar
            self.r.assimilera(ind.meps, ind.meta, ind.tid - timedelta(minutes=5), under_bortfall=False)
            self.forsta = False
        self.r.lagg_till(ind.bild)
        self.r.assimilera(ind.meps, ind.meta, ind.tid, under_bortfall=True)
        return self.r.falt(ind.meps, ind.tid)

    def steg(self, k: int, ind: domare.Indata) -> np.ndarray:
        if self.utan:
            return self.reserv.steg(k, ind)
        m = self._meps(ind)
        out = ind.bild.copy()
        if m is not None:
            out[ind.hal] = m[ind.hal]
        return out


class Blandning(Meps):
    """Den flyttade analysen och den rättade MEPS blandade per skala med vikter efter åldern."""

    namn = "blandning"
    vikter: Vikter | None = None

    def start(self, ind: domare.Indata) -> None:
        super().start(ind)
        if self.utan:
            return
        self.v = self.vikter or las_vikter()
        self.flytt = Flytt()
        self.flytt.start(ind)

    def steg(self, k: int, ind: domare.Indata) -> np.ndarray:
        if self.utan:
            return self.reserv.steg(k, ind)
        a = self.flytt.steg(k, ind)
        m = self._meps(ind)
        if m is None:
            return np.where(ind.hal & (5 * (k + 1) > 90), np.nan, a)
        return blanda(np.where(ind.hal, a, np.nan), m, ind.bild, ind.hal, 5 * (k + 1), self.v)


# --- valet av vikter på träningsfallen --------------------------------------------------------

def kandidater() -> dict[str, Vikter]:
    inf = float("inf")
    c = {"bara_meps": Vikter(0.0, 0.0, match=False), "bara_flytt": Vikter(inf, inf, match=False)}
    for t in (30, 60, 90, 120, 180, 240, 360):
        for kvot in (1.0, 2.5):
            c[f"t{t}_x{kvot:g}"] = Vikter(float(t), float(t * kvot))
    c["t60_x2.5_utan_match"] = Vikter(60.0, 150.0, match=False)
    c["t60_x2.5_form5"] = Vikter(60.0, 150.0, shape=5.0)
    return c


def urval(index: list[dict]) -> list[dict]:
    """De två längsta fallen per träningsdag (längst först, sedan namnet), bara med MEPS."""
    dagar: dict[str, list[dict]] = {}
    for c in index:
        if c.get("meps_tid"):
            dagar.setdefault(c["dag"], []).append(c)
    out = []
    for d in sorted(dagar):
        out += sorted(dagar[d], key=lambda c: (-c["langd_min"], c["namn"]))[:2]
    return out


def sok_fall(path: Path, var_annan: bool = True) -> dict:
    """Kör den flyttade analysen och MEPS en gång och bedöm alla kandidater med domarens summor."""
    t0 = time.monotonic()
    fall = domare.Fall(path)
    ind = fall.indata()
    kand = kandidater()
    flytt, meps = Flytt(), Meps()
    flytt.start(ind)
    meps.start(ind)
    band = domare.kantband(fall.hal)
    summor = {n: [domare.tom_klass() for _ in domare.KLASSER] for n in kand}
    for k in range(fall.n):
        t = fall.tider[fall.k0 + k]
        ind.bild, ind.tid = fall.maskad(k), t
        ind.meps, ind.matare = fall.meps_till(t), {}
        a = flytt.steg(k, ind)
        m = meps._meps(ind)
        kl = domare.klass_for(5 * (k + 1))
        if kl is None or m is None or (var_annan and k % 2):
            continue
        o = fall.radar[fall.k0 + k]
        for n, v in kand.items():
            f = blanda(np.where(fall.hal, a, np.nan), m, ind.bild, fall.hal, 5 * (k + 1), v)
            domare.bild_sums(summor[n][kl], f, o, fall.hal, band)
    return {"namn": fall.meta["namn"], "dag": fall.dag, "summor": summor,
            "sekunder": round(time.monotonic() - t0, 1)}


def poang(m: dict) -> float:
    keys = [k for k in domare.MATT if k.startswith(("fss", "csi"))]
    return float(np.mean([m[k] for k in keys]))


def sok(a) -> None:
    index = json.loads((domare.FALL / "traning" / "index.json").read_text())["fall"]
    valda = urval(index)
    if a.fall:
        valda = valda[: a.fall]
    paths = [domare.FALL / "traning" / c["fil"] for c in valda]
    print("fall i urvalet:", len(paths), flush=True)
    res = []
    if a.processer > 1:
        from multiprocessing import Pool

        with Pool(a.processer) as pool:
            for i, r in enumerate(pool.imap(sok_fall, paths)):
                res.append(r)
                print("sok", i + 1, len(paths), r["namn"], r["sekunder"], "s", flush=True)
    else:
        for i, p in enumerate(paths):
            res.append(sok_fall(p))
            print("sok", i + 1, len(paths), res[-1]["namn"], res[-1]["sekunder"], "s", flush=True)
    kand = kandidater()
    tab = {}
    for n in kand:
        per_kl = [domare.matt(domare.summera([r["summor"][n][kl] for r in res])) for kl in range(len(domare.KLASSER))]
        tab[n] = {"klasser": per_kl, "poang": float(np.mean([poang(m) for m in per_kl]))}
    basta = max((n for n in kand if n not in ("bara_meps", "bara_flytt")), key=lambda n: tab[n]["poang"])
    out_dir = domare.RESULTAT / "traning"
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"_prov{a.fall}" if a.fall else ""
    (out_dir / f"meps_sok{suffix}.json").write_text(json.dumps(
        {"fall": [r["namn"] for r in res], "kandidater": {n: asdict(v) for n, v in kand.items()},
         "tabell": tab, "basta": basta}, default=str) + "\n")
    for n in sorted(tab, key=lambda n: -tab[n]["poang"]):
        kl = tab[n]["klasser"]
        print(f"{n:22s} poäng {tab[n]['poang']:.4f}  " + "  ".join(
            f"[{domare.klassnamn(i)}: FSS1/30 {kl[i]['fss_1_30']:.3f} FSS5/30 {kl[i]['fss_5_30']:.3f} "
            f"CSI1 {kl[i]['csi_1']:.3f} vol {kl[i]['vol']:.2f}]" for i in range(3)), flush=True)
    if not a.fall:
        VIKTER.write_text(json.dumps({"vald": basta, "vikter": asdict(kand[basta]),
                                      "fall": len(res), "poang": tab[basta]["poang"]}, indent=1) + "\n")
        print("valt:", basta, flush=True)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cmd", choices=["sok"])
    p.add_argument("--fall", type=int)
    p.add_argument("--processer", type=int, default=1)
    p.add_argument("--logg", type=Path)
    a = p.parse_args()
    if a.processer > 2:
        raise SystemExit("högst två processer i natt")
    if a.logg:
        sys.stdout = sys.stderr = open(a.logg, "a", buffering=1)
    {"sok": sok}[a.cmd](a)


if __name__ == "__main__":
    main()
