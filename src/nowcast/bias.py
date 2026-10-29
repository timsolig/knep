"""Volymkorrektion mot SMHI:s regnmätare, så att radarns årsvolym stämmer.

Radarn underskattar mer ju högre den lägsta strålen går (strålen går över låg nederbörd och
missar ökningen nedåt), och hur mycket beror på årstiden: snö, smältband och låga moln. Metoden
följer därför BALTEX-justeringen (Michelson m.fl. 2000, SMHI RMK 90), men som klimatologi:

    log K(x, m) = a_m + b_m h(x) + c_m h(x)² + r(x)

h är höjden i km på den lägsta radarstrålen över pixeln. a, b och c skattas per månad med viktad
minsta kvadrat på log(mätare/radar) per station och månad, grannmånaderna med halv vikt och krympt
mot årets koefficienter där underlaget är tunt. Avvikande stationer viktas ned som i BALTEX
(linjärt mellan en och två standardavvikelser). r är stationernas kvarvarande avvikelse med
Barnes-viktning, krympt mot noll där mätarna är glesa; den fångar det som inte beror på höjden,
som strålblockering och klotterfilter.

Nivån skalar alla intensiteter lika, så den kan inte trycka ned toppar för att få summan rätt.
Formen får en egen term: efter nivån jämförs timkvantilerna (99 till 99,95 %) för mätare och radar,
och om radarns svans ligger fel skattas en exponent γ som bara verkar över 5 mm/h. Sist stängs
nivån per månad så att nätets summa stämmer med svanstermen på plats. Svansen jämförs mot radarns
mittpixel; mätarens punktvärde är något spetsigare än en 2 km-pixel, så γ hålls inom snäva gränser.

Ovanpå kartan ligger en medelfältsfaktor för de senaste sju dygnen (hela nätet, krympt mot 1),
som tar det klimatologin missar ett visst år. Den räknas bara på timmar under 10 mm, så att ett
skyfall som radarn missar inte ändrar nästa veckas nivå.

Radarns timsummor räknas på den råa analysen (SMHI:s egna pixlar, före korrektionen) vid varje
station, mätarnas timvärden är SMHI:s automatiska stationer (parameter 7, summa 1 timme, värdet
gäller timmen som slutar vid tidsstämpeln). Båda sparas per dygn i en katalog, löpande i driften
och bakåt ur arkivet med `nowcast-bias`.
"""

from __future__ import annotations

import argparse
import calendar
import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter

from . import composite

log = logging.getLogger("nowcast.bias")

METOBS = "https://opendata-download-metobs.smhi.se/api/version/1.0/parameter/7"
ELEV_DEG = 0.5  # lägsta elevationen i SMHI:s komposit
H_MAX = 5.0  # km; strålhöjder över detta behandlas som 5 km
LOGK_MAX = np.log(4.0)  # korrektionen hålls inom en fjärdedel till fyra gånger
BARNES_KM = 40.0
SHRINK_RESID = 0.5  # i stationsvikter: en ensam station får ungefär två tredjedelar av sin avvikelse
MIN_FRAMES = 10  # av 12 för en giltig radartimme
MFB_DAYS = 7
MIN_DAYS = 60  # dygn med par av radar och mätare innan en kandidat sparas
MFB_N0 = 200.0  # våta stationstimmar som ger halv vikt åt medelfältsfaktorn
MFB_MAX = 10.0  # mm på en timme; kraftigare timmar räknas inte i medelfältsfaktorn
TAIL_R0 = 5.0  # mm/h där svanstermen börjar
TAIL_Q = (0.99, 0.995, 0.999, 0.9995)  # kvantiler av våta timmar
TAIL_GAMMA = (-0.2, 0.3)  # gränser för svansens exponent


# ---- geometri ----------------------------------------------------------------

def beam_height(grid: composite.TargetGrid, radars=None, elev_deg=ELEV_DEG) -> np.ndarray:
    """Höjd i km över havet för den lägsta strålen över varje pixel (4/3-jordradie). NaN utom räckhåll."""
    from pyproj import Transformer

    radars = radars or composite.RADARS
    X, Y = grid.centres()
    to_grid = Transformer.from_crs("EPSG:4326", "EPSG:3006", always_xy=True)
    el = np.deg2rad(elev_deg)
    best = np.full(grid.shape, np.inf, np.float32)
    for lat, lon, height, rng_km in radars.values():
        x0, y0 = to_grid.transform(lon, lat)
        d = np.hypot(X - x0, Y - y0)
        h = np.sqrt(d**2 + composite.KE_A**2 + 2 * d * composite.KE_A * np.sin(el)) - composite.KE_A + height
        h = np.where(d <= rng_km * 1000, h, np.inf)
        best = np.minimum(best, h.astype(np.float32))
    return np.where(np.isfinite(best), best / 1000.0, np.nan).astype(np.float32)


@dataclass
class Stations:
    ids: np.ndarray  # int64
    lat: np.ndarray
    lon: np.ndarray

    def pixels(self, grid: composite.TargetGrid):
        from pyproj import Transformer

        x, y = Transformer.from_crs("EPSG:4326", "EPSG:3006", always_xy=True).transform(self.lon, self.lat)
        col = np.floor((np.asarray(x) - grid.west) / grid.res).astype(int)
        row = np.floor((grid.north - np.asarray(y)) / grid.res).astype(int)
        inside = (row >= 1) & (row < grid.shape[0] - 1) & (col >= 1) & (col < grid.shape[1] - 1)
        return row, col, inside

    def save(self, path: Path):
        path.write_text(json.dumps({"ids": self.ids.tolist(), "lat": self.lat.tolist(), "lon": self.lon.tolist()}))

    @classmethod
    def load(cls, path: Path) -> "Stations | None":
        if not path.exists():
            return None
        d = json.loads(path.read_text())
        return cls(np.array(d["ids"], np.int64), np.array(d["lat"]), np.array(d["lon"]))


# ---- hämtning från SMHI:s öppna observationer -------------------------------

def fetch_stations(session) -> Stations:
    r = session.get(f"{METOBS}.json", timeout=30)
    r.raise_for_status()
    st = [s for s in r.json()["station"] if s.get("active")]
    return Stations(np.array([s["id"] for s in st], np.int64), np.array([s["latitude"] for s in st]),
                    np.array([s["longitude"] for s in st]))


def _ms(t) -> datetime:
    return datetime.fromtimestamp(int(t) / 1000, UTC)


def fetch_latest_hour(session) -> list[tuple[int, datetime, float]]:
    """Senaste timmen för alla stationer i ett anrop: (station, timmens slut, mm)."""
    r = session.get(f"{METOBS}/station-set/all/period/latest-hour/data.json", timeout=30)
    r.raise_for_status()
    out = []
    for s in r.json().get("station", []):
        for v in s.get("value") or []:
            if v.get("value") not in (None, "") and v.get("quality") in ("G", "Y"):
                out.append((int(s["key"]), _ms(v["date"]), float(v["value"])))
    return out


def fetch_station(session, sid: int, period: str) -> list[tuple[int, datetime, float]]:
    """En stations timvärden: period latest-day eller latest-months (json), corrected-archive (csv)."""
    if period == "corrected-archive":
        r = session.get(f"{METOBS}/station/{sid}/period/corrected-archive/data.csv", timeout=120)
        r.raise_for_status()
        return parse_archive_csv(r.text, sid)
    r = session.get(f"{METOBS}/station/{sid}/period/{period}/data.json", timeout=60)
    r.raise_for_status()
    return [(sid, _ms(v["date"]), float(v["value"])) for v in r.json().get("value") or []
            if v.get("value") not in (None, "") and v.get("quality") in ("G", "Y")]


_ROW = re.compile(r"^(\d{4}-\d{2}-\d{2});(\d{2}):(\d{2}):\d{2};([-\d.]+);([GYR])", re.M)


def parse_archive_csv(text: str, sid: int) -> list[tuple[int, datetime, float]]:
    out = []
    for m in _ROW.finditer(text):
        if m.group(5) == "R":
            continue
        t = datetime.fromisoformat(m.group(1)).replace(hour=int(m.group(2)), minute=int(m.group(3)), tzinfo=UTC)
        out.append((sid, t, float(m.group(4))))
    return out


# ---- lagring per dygn --------------------------------------------------------

def hour_end(t: datetime) -> datetime:
    """Slutet på timmen som en 5-minutersbild giltig vid t hör till (bilden gäller de fem minuterna före t)."""
    h = t.replace(minute=0, second=0, microsecond=0)
    return h if t == h else h + timedelta(hours=1)


class Store:
    """Timsummor per station och dygn: radar_ÅÅÅÅMMDD.npz och gauge_ÅÅÅÅMMDD.npz.

    Index 0..23 i ett dygn är timmen som slutar 00, 01, ..., 23 UTC det dygnet.
    """

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, kind, d: date):
        return self.root / f"{kind}_{d:%Y%m%d}.npz"

    def _load(self, kind, d, ids):
        p = self._path(kind, d)
        n = len(ids)
        if kind == "radar":
            empty = {"sum": np.zeros((24, n), np.float32), "cnt": np.zeros((24, n), np.uint8), "last": 0}
        else:
            empty = {"val": np.full((24, n), np.nan, np.float32)}
        if not p.exists():
            return empty
        z = np.load(p)
        pos = {int(s): k for k, s in enumerate(z["ids"])}
        out = empty
        take = np.array([pos.get(int(s), -1) for s in ids])
        have = take >= 0
        for key in out:
            if key == "last":
                out[key] = int(z["last"]) if "last" in z.files else 0
                continue
            out[key][:, have] = z[key][:, take[have]]
        return out

    def _save(self, kind, d, ids, arrays):
        p = self._path(kind, d)
        tmp = p.with_suffix(".tmp.npz")
        np.savez_compressed(tmp, ids=np.asarray(ids, np.int64), **arrays)
        tmp.replace(p)

    def flush(self):
        """Skriver dygnet som hålls i minnet (bara vid add_radar(..., keep=True))."""
        if getattr(self, "_open", None):
            day, ids, d = self._open
            self._save("radar", day, ids, {"sum": d["sum"], "cnt": d["cnt"], "last": np.int64(d["last"])})
            self._open = None

    def add_radar(self, t: datetime, rain: np.ndarray, source: np.ndarray | None, stations: Stations,
                  grid: composite.TargetGrid, keep: bool = False) -> bool:
        """Lägger till en 5-minutersbild (mm/h, rå analys) vid stationerna. Varje bild räknas en gång.

        keep: håll dygnet i minnet och skriv först när dygnet byts eller vid flush() (för bakåtfyllnad).
        """
        he = hour_end(t)
        cur = getattr(self, "_open", None)
        if cur and (cur[0] != he.date() or not np.array_equal(cur[1], stations.ids)):
            self.flush()
            cur = None
        d = cur[2] if cur else self._load("radar", he.date(), stations.ids)
        stamp = int(t.timestamp())
        if stamp <= d["last"]:
            return False
        row, col, inside = stations.pixels(grid)
        vals = np.full(len(stations.ids), np.nan, np.float32)
        ok = rain if source is None else np.where(source == composite.SOURCE_SMHI, rain, np.nan)
        # mittpixeln: ett medel över grannarna skulle jämna ut toppar och se ut som underskattad svans
        vals[inside] = ok[row[inside], col[inside]]
        good = np.isfinite(vals)
        d["sum"][he.hour, good] += vals[good] * (5.0 / 60.0)
        d["cnt"][he.hour, good] += 1
        d["last"] = stamp
        if keep:
            self._open = (he.date(), stations.ids, d)
        else:
            self._save("radar", he.date(), stations.ids, {"sum": d["sum"], "cnt": d["cnt"], "last": np.int64(stamp)})
        return True

    def add_gauges(self, records, ids=None):
        """records: (station, timmens slut, mm). Skriver över tidigare värden för samma timme."""
        by_day = {}
        for sid, t, v in records:
            by_day.setdefault(t.date(), []).append((sid, t.hour, v))
        for d, recs in by_day.items():
            p = self._path("gauge", d)
            known = set(np.load(p)["ids"].tolist()) if p.exists() else set()
            day_ids = np.array(sorted(known | set(ids if ids is not None else []) | {r[0] for r in recs}), np.int64)
            cur = self._load("gauge", d, day_ids)
            pos = {int(s): k for k, s in enumerate(day_ids)}
            for sid, h, v in recs:
                cur["val"][h, pos[sid]] = v
            self._save("gauge", d, day_ids, cur)

    def pairs(self, start: date, end: date, ids: np.ndarray):
        """Timvärden (dygn*24, stationer) för mätare och radar, NaN där någon saknas, samt timmarnas sluttider."""
        G, R, T = [], [], []
        d = start
        while d <= end:
            if self._path("radar", d).exists() and self._path("gauge", d).exists():
                r = self._load("radar", d, ids)
                g = self._load("gauge", d, ids)["val"]
                cnt = r["cnt"].astype(np.float32)
                rr = np.where(cnt >= MIN_FRAMES, r["sum"] * 12.0 / np.maximum(cnt, 1), np.nan)
                both = np.isfinite(rr) & np.isfinite(g)
                G.append(np.where(both, g, np.nan))
                R.append(np.where(both, rr, np.nan))
                T += [datetime(d.year, d.month, d.day, tzinfo=UTC) + timedelta(hours=h) for h in range(24)]
            d += timedelta(days=1)
        if not G:
            return np.zeros((0, len(ids))), np.zeros((0, len(ids))), []
        return np.concatenate(G), np.concatenate(R), T


# ---- skattning ---------------------------------------------------------------

def monthly_sums(G, R, times):
    """Summor per (kalendermånad, station) över alla år: mätare, radar och antal våta timmar."""
    months = np.array([(t - timedelta(minutes=1)).month - 1 for t in times])
    n = G.shape[1]
    sg, sr, wet = np.zeros((12, n)), np.zeros((12, n)), np.zeros((12, n))
    for m in range(12):
        sel = months == m
        if not sel.any():
            continue
        g, r = G[sel], R[sel]
        sg[m] = np.nansum(g, axis=0)
        sr[m] = np.nansum(r, axis=0)
        wet[m] = np.sum((np.nan_to_num(g) >= 0.1) | (np.nan_to_num(r) >= 0.1), axis=0)
    return sg, sr, wet


def _wls(X, y, w, prior, lam):
    A = X.T @ (w[:, None] * X) + np.diag(lam)
    b = X.T @ (w * y) + lam * prior
    return np.linalg.solve(A, b)


def _design(h):
    h = np.clip(h, 0, H_MAX)
    return np.stack([np.ones_like(h), h, h**2], axis=1)


def fit_coefficients(sg, sr, h_st, min_total=10.0):
    """Koefficienter (12, 3) och vikter per (månad, station). Robust: två varv med nedviktning."""
    y = np.log((sg + 1.0) / (sr + 1.0))
    w = np.where((sg + sr >= min_total) & np.isfinite(h_st)[None, :], np.minimum(sg + sr, 200.0) / 200.0, 0.0)
    h = np.nan_to_num(h_st, nan=H_MAX)
    X = _design(h)
    coef = np.zeros((12, 3))
    rob = np.ones_like(w)
    for _ in range(2):
        ww = w * rob
        # årets koefficienter: alla månader, svagt krympta mot ingen höjdberoende
        Xa = np.tile(X, (12, 1))
        annual = _wls(Xa, y.ravel(), ww.ravel(), np.zeros(3), np.array([0.0, 0.5, 2.0]))
        for m in range(12):
            rows, ys, ws = [], [], []
            for dm, f in ((-1, 0.5), (0, 1.0), (1, 0.5)):
                mm = (m + dm) % 12
                rows.append(X); ys.append(y[mm]); ws.append(f * ww[mm])
            Xm, ym, wm = np.concatenate(rows), np.concatenate(ys), np.concatenate(ws)
            coef[m] = _wls(Xm, ym, wm, annual, np.array([0.2, 2.0, 2.0]))
        e = y - np.einsum("mk,sk->ms", coef, X)
        valid = w > 0
        if valid.sum() < 5:
            break
        sigma = 1.4826 * np.median(np.abs(e[valid] - np.median(e[valid]))) + 1e-3
        rob = np.clip(2.0 - np.abs(e) / sigma, 0.0, 1.0)
    # nedviktningen gäller polynomet; restkartan får alla stationer, eftersom en avvikelse som håller
    # i sig över månaderna oftast är verklig (blockering), och den begränsas ändå av klippningen
    return coef, w, y


def barnes(values, weights, row, col, shape, res_m, length_km=BARNES_KM, shrink=SHRINK_RESID):
    """Barnes-viktat medel av stationsvärden på rutnätet, krympt mot noll där vikterna är små."""
    sigma = length_km * 1000.0 / res_m
    num, den = np.zeros(shape), np.zeros(shape)
    np.add.at(num, (row, col), weights * values)
    np.add.at(den, (row, col), weights)
    k = 2 * np.pi * sigma**2  # så att en ensam station får sin vikt i sin egen pixel
    num = gaussian_filter(num, sigma, mode="constant") * k
    den = gaussian_filter(den, sigma, mode="constant") * k
    return (num / (den + shrink)).astype(np.float32)


@dataclass
class Correction:
    """log K(x, månad) för nivån plus en svansterm för formen.

    Nivån skalar alla intensiteter lika och kan därför inte platta till toppar. Svanstermen
    R → R·(R/R0)^γ över R0 rättar radarns svans mot mätarnas timkvantiler; den skattas efter
    nivån, och nivån stängs sist så att volymen stämmer med svanstermen på plats.
    """

    coef: np.ndarray  # (12, 3) per kalendermånad, värdet gäller mitten av månaden
    resid: np.ndarray  # (H, W) log-faktor
    beam: np.ndarray  # (H, W) km
    mfb: float = 0.0  # log-faktor för senaste sju dygnen
    mfb_time: str = ""
    gamma: float = 0.0  # svansens exponent
    r0: float = TAIL_R0  # mm/h där svanstermen börjar

    def _coef(self, t: datetime):
        # mitten av månaderna som stödpunkter, linjärt emellan
        days = calendar.monthrange(t.year, t.month)[1]
        pos = (t.month - 1) + (t.day - 1 + t.hour / 24) / days - 0.5
        m0 = int(np.floor(pos)) % 12
        f = pos - np.floor(pos)
        return (1 - f) * self.coef[m0] + f * self.coef[(m0 + 1) % 12]

    def factor_at(self, t: datetime, row, col) -> np.ndarray:
        """Nivåfaktorn i några pixlar (snabbt, för skattningen vid stationerna)."""
        c = self._coef(t)
        h = np.clip(np.nan_to_num(self.beam[row, col], nan=H_MAX), 0, H_MAX)
        lk = np.clip(c[0] + c[1] * h + c[2] * h**2, -LOGK_MAX, LOGK_MAX) + self.resid[row, col]
        if self.mfb_time:
            age = (t - datetime.fromisoformat(self.mfb_time)).total_seconds() / 86400
            if 0 <= age < 3:
                lk = lk + self.mfb
        return np.exp(np.clip(lk, -LOGK_MAX, LOGK_MAX)).astype(np.float32)

    def logk(self, t: datetime) -> np.ndarray:
        c = self._coef(t)
        h = np.clip(np.nan_to_num(self.beam, nan=H_MAX), 0, H_MAX)
        poly = np.clip(c[0] + c[1] * h + c[2] * h**2, -LOGK_MAX, LOGK_MAX)
        lk = poly + self.resid
        if self.mfb_time:
            age = (t - datetime.fromisoformat(self.mfb_time)).total_seconds() / 86400
            if 0 <= age < 3:
                lk = lk + self.mfb
        return np.clip(lk, -LOGK_MAX, LOGK_MAX).astype(np.float32)

    def factor(self, t: datetime) -> np.ndarray:
        return np.exp(self.logk(t))

    def tail(self, r):
        """Svanstermen på intensiteter (mm/h) eller timsummor (mm) som redan har nivåfaktorn."""
        if not self.gamma:
            return r
        with np.errstate(invalid="ignore", divide="ignore"):
            boost = np.where(r > self.r0, (np.maximum(r, self.r0) / self.r0) ** self.gamma, 1.0)
        return (r * boost).astype(np.float32)

    def apply(self, rain: np.ndarray, t: datetime) -> np.ndarray:
        """Korrigerad analys (mm/h), för ett fält (H, W) eller en stapel (T, H, W) vid tiden t."""
        return self.tail(rain * self.factor(t))

    def save(self, path: Path):
        tmp = Path(path).with_suffix(".tmp.npz")
        np.savez_compressed(tmp, coef=self.coef, resid=self.resid.astype(np.float16), beam=self.beam.astype(np.float16),
                            mfb=np.float64(self.mfb), mfb_time=np.array(self.mfb_time),
                            gamma=np.float64(self.gamma), r0=np.float64(self.r0))
        tmp.replace(path)

    @classmethod
    def load(cls, path: Path) -> "Correction | None":
        if not Path(path).exists():
            return None
        z = np.load(path)
        return cls(z["coef"], z["resid"].astype(np.float32), z["beam"].astype(np.float32), float(z["mfb"]), str(z["mfb_time"]),
                   float(z["gamma"]) if "gamma" in z.files else 0.0, float(z["r0"]) if "r0" in z.files else TAIL_R0)


def station_factors(corr: Correction, T, row, col, inside):
    """Nivåfaktorn vid stationerna per timme (räknad en gång per dygn, den ändras långsamt)."""
    k = np.full((len(T), len(row)), np.nan, np.float32)
    r, c = np.clip(row, 0, corr.beam.shape[0] - 1), np.clip(col, 0, corr.beam.shape[1] - 1)
    for i in range(0, len(T), 24):
        k[i : i + 24] = np.where(inside, corr.factor_at(T[i], r, c), np.nan)
    return k


def tail_quantiles(G, R):
    """Timkvantiler för våta timmar, mätare och radar, sammanslaget över stationer."""
    wet = np.isfinite(G) & np.isfinite(R) & ((G >= 0.1) | (R >= 0.1))
    if wet.sum() < 2000:
        return None
    return np.quantile(G[wet], TAIL_Q), np.quantile(R[wet], TAIL_Q)


def fit_tail(G, Rk, r0=TAIL_R0):
    """γ ur kvantilerna över r0: log(qG/qR) = γ log(qR/r0), krympt och begränsat."""
    q = tail_quantiles(G, Rk)
    if q is None:
        return 0.0
    qg, qr = q
    use = qr > r0
    if use.sum() < 2:
        return 0.0
    x, y = np.log(qr[use] / r0), np.log(qg[use] / qr[use])
    gamma = float((x * y).sum() / ((x * x).sum() + 0.5))  # krympt mot noll när svansen är kort
    return float(np.clip(gamma, *TAIL_GAMMA))


def fit(store: Store, stations: Stations, grid: composite.TargetGrid, start: date, end: date, beam=None,
        mfb_end: datetime | None = None):
    """Skattar korrektionen ur lagrade timvärden. Returnerar (Correction, rapport).

    Ordningen är nivå (polynom och restkarta), svans, och sist volymslutning per månad.
    """
    beam = beam_height(grid) if beam is None else beam
    G, R, T = store.pairs(start, end, stations.ids)
    row, col, inside = stations.pixels(grid)
    h_st = np.where(inside, beam[np.clip(row, 0, grid.shape[0] - 1), np.clip(col, 0, grid.shape[1] - 1)], np.nan)
    sg, sr, _ = monthly_sums(G, R, T)
    coef, w, y = fit_coefficients(sg, sr, h_st)
    X = _design(np.nan_to_num(h_st, nan=H_MAX))
    e = y - np.einsum("mk,sk->ms", coef, X)
    ws = w.sum(axis=0)
    r_st = np.clip(np.where(ws > 0, (w * e).sum(axis=0) / np.maximum(ws, 1e-9), 0.0), -np.log(3), np.log(3))
    W = ws / 12.0
    ok = inside & (ws > 0)
    resid = barnes(r_st[ok], W[ok], row[ok], col[ok], grid.shape, grid.res)
    corr = Correction(coef, resid, beam)
    if T:
        K = station_factors(corr, T, row, col, inside)
        corr.gamma = fit_tail(G[:, ok], (R * K)[:, ok])
        # volymslutning: nätets summa per månad ska stämma med svanstermen på plats (två varv,
        # eftersom månaderna interpoleras mot varandra)
        months = np.array([(t - timedelta(minutes=1)).month - 1 for t in T])
        for _ in range(2):
            K = station_factors(corr, T, row, col, inside)
            Rt = corr.tail(R * K)
            for m in range(12):
                sel = months == m
                g, rk = np.nansum(G[sel][:, ok]), np.nansum(Rt[sel][:, ok])
                if g + rk >= 50.0:
                    corr.coef[m, 0] += np.log((g + 1.0) / (rk + 1.0))
    if mfb_end is not None:
        corr.mfb, corr.mfb_time = mean_field_bias(G, R, T, corr, row, col, inside, mfb_end)
    return corr, report(G, R, T, corr, row, col, inside)


def mean_field_bias(G, R, T, corr, row, col, inside, end: datetime):
    """log-faktor för hela nätet de senaste sju dygnen efter korrektionen, krympt mot noll.

    Bara timmar under 10 mm, så att ett enskilt skyfall som radarn missar inte styr nästa veckas nivå.
    """
    sel = np.array([end - timedelta(days=MFB_DAYS) < t <= end for t in T]) if T else np.zeros(0, bool)
    if not sel.any():
        return 0.0, ""
    g, r = G[sel][:, inside], R[sel][:, inside]
    k = corr.factor_at(end, row[inside], col[inside])  # faktorn ändras långsamt; en räcker för sju dygn
    rk = corr.tail(r * k[None, :])
    calm = (np.nan_to_num(g) < MFB_MAX) & (np.nan_to_num(rk) < MFB_MAX)
    sg, srk = np.nansum(np.where(calm, g, np.nan)), np.nansum(np.where(calm, rk, np.nan))
    n = np.sum(calm & ((np.nan_to_num(g) >= 0.1) | (np.nan_to_num(rk) >= 0.1)))
    b = np.log((sg + 5.0) / (srk + 5.0)) * n / (n + MFB_N0)
    return float(np.clip(b, -np.log(2), np.log(2))), end.isoformat()


def _summary(G, R, Rc, use):
    tg, tr, trc = np.nansum(G, axis=0), np.nansum(R, axis=0), np.nansum(Rc, axis=0)
    use = use & (tg >= 50)
    if not use.any():
        return {}
    before, after = tr[use] / tg[use], trc[use] / tg[use]
    out = {
        "volym_före": float(tr[use].sum() / tg[use].sum()),
        "volym_efter": float(trc[use].sum() / tg[use].sum()),
        "median_före": float(np.median(before)), "median_efter": float(np.median(after)),
        "inom_20_proc_före": float(np.mean(np.abs(np.log(before)) <= np.log(1.2))),
        "inom_20_proc_efter": float(np.mean(np.abs(np.log(after)) <= np.log(1.2))),
    }
    q0, q1 = tail_quantiles(G[:, use], R[:, use]), tail_quantiles(G[:, use], Rc[:, use])
    if q0 is not None:
        for p, a, b, c in zip(TAIL_Q, q0[0], q0[1], q1[1]):
            out[f"kvantil_{p * 100:g}_mätare_mm"] = float(a)
            out[f"kvantil_{p * 100:g}_före"] = float(b / a) if a else None
            out[f"kvantil_{p * 100:g}_efter"] = float(c / a) if a else None
    return out


def report(G, R, T, corr, row, col, inside):
    """Årsvolym per station och timkvantiler före och efter korrektionen (kvot radar/mätare)."""
    out = {"stationer": int((np.nansum(G, axis=0) > 0).sum()), "timmar": len(T), "gamma": corr.gamma}
    if not T:
        return out
    Rc = corr.tail(R * station_factors(corr, T, row, col, inside))
    return out | _summary(G, R, Rc, inside)


def cross_validate(store, stations, grid, start, end, folds=5, seed=0, beam=None):
    """Stationsvis korsvalidering: kartan skattas utan en femtedel av stationerna och prövas på dem."""
    beam = beam_height(grid) if beam is None else beam
    rng = np.random.default_rng(seed)
    fold = rng.integers(0, folds, len(stations.ids))
    G, R, T = store.pairs(start, end, stations.ids)
    row, col, inside = stations.pixels(grid)
    Rc = np.full_like(R, np.nan)
    for f in range(folds):
        train = fold != f
        sub = Stations(stations.ids[train], stations.lat[train], stations.lon[train])
        corr, _ = fit(store, sub, grid, start, end, beam=beam)
        test = ~train & inside
        K = station_factors(corr, T, row, col, inside)
        Rc[:, test] = corr.tail(R[:, test] * K[:, test])
    return _summary(G, R, Rc, inside)


# ---- drift -------------------------------------------------------------------

class Operational:
    """Det driften gör varje cykel: räkna radarns timsummor, hämta mätarna en gång i timmen och
    en gång per dygn räkna veckofaktorn och en kandidat till ny karta. Allt är best effort och
    stoppar aldrig prognosen.

    Kartan som används är den fastlåsta i models/bias.npz (en version från GitHub Releases, se
    models.py). Driften skriver aldrig över den: kandidaten hamnar i cache/bias/kandidat.npz med
    sin rapport, och blir en ny version först när den släpps och låses i models/models.json.
    Veckofaktorn räknas mot den fastlåsta kartan och sparas i cache/bias/vecka.json.
    """

    def __init__(self, root: Path, model_path: Path, years: float = 3.0):
        self.root = Path(root)
        self.store = Store(self.root)
        self.model_path = Path(model_path)
        self.years = years
        self.meta_path = self.root / "meta.json"
        self.meta = json.loads(self.meta_path.read_text()) if self.meta_path.exists() else {}

    def _save_meta(self):
        self.meta_path.write_text(json.dumps(self.meta))

    def step(self, session, t: datetime, rain, source, grid: composite.TargetGrid):
        stations = Stations.load(self.root / "stations.json")
        if stations is None or self.meta.get("stations_day") != f"{t:%Y-%m}":
            try:
                stations = fetch_stations(session)
                stations.save(self.root / "stations.json")
                self.meta["stations_day"] = f"{t:%Y-%m}"
            except Exception as e:  # noqa: BLE001
                log.warning("kunde inte hämta stationslistan: %s", e)
        if stations is None:
            return
        self.store.add_radar(t, rain, source, stations, grid)
        hour = t.replace(minute=0, second=0, microsecond=0)
        if t.minute >= 20 and self.meta.get("gauge_hour") != hour.isoformat():
            try:
                recs = fetch_latest_hour(session)
                self.store.add_gauges(recs, stations.ids)
                self.meta["gauge_hour"] = hour.isoformat()
            except Exception as e:  # noqa: BLE001
                log.warning("kunde inte hämta mätarna: %s", e)
        if t.hour == 3 and self.meta.get("fit_day") != t.date().isoformat():
            self.meta["fit_day"] = t.date().isoformat()
            try:
                self.nightly(stations, grid, t)
            except Exception as e:  # noqa: BLE001
                log.warning("kunde inte skatta volymkorrektionen: %s", e)
        self._save_meta()

    def nightly(self, stations: Stations, grid: composite.TargetGrid, t: datetime):
        pinned = Correction.load(self.model_path)
        row, col, inside = stations.pixels(grid)
        if pinned is not None:
            G, R, T = self.store.pairs((t - timedelta(days=MFB_DAYS + 1)).date(), t.date(), stations.ids)
            mfb, when = mean_field_bias(G, R, T, pinned, row, col, inside, t)
            (self.root / "vecka.json").write_text(json.dumps({"mfb": mfb, "time": when}))
        start = (t - timedelta(days=round(365 * self.years))).date()
        cand, rep = fit(self.store, stations, grid, start, t.date())
        rep["dygn"] = rep.get("timmar", 0) // 24
        if rep["dygn"] >= MIN_DAYS:
            cand.save(self.root / "kandidat.npz")
        (self.root / "kandidat.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1))
        self.meta["fit_report"] = rep
        log.info("kandidat till volymkarta: %s", rep)


def load_week(root: Path):
    """Veckofaktorn från driften: (log-faktor, tid) eller None."""
    p = Path(root) / "vecka.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text())
    return (float(d["mfb"]), d["time"]) if d.get("time") else None


# ---- kommandorad -------------------------------------------------------------

def _grid_from_tif(path: Path) -> composite.TargetGrid:
    import rasterio

    with rasterio.open(path) as src:
        t = src.transform
        return composite.TargetGrid(t.c, t.f, t.a, (src.height, src.width))


def main(argv=None) -> int:
    import requests

    from . import radar

    p = argparse.ArgumentParser(prog="nowcast-bias", description="Volymkorrektion mot SMHI:s regnmätare")
    p.add_argument("--store", type=Path, default=Path("cache/bias"))
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gauges", help="hämta mätarnas timvärden bakåt (arkiv och senaste månaderna)")
    g.add_argument("--archive", action="store_true", help="även kontrollerat arkiv (csv, längre bakåt)")
    r = sub.add_parser("radar", help="räkna radarns timsummor vid stationerna ur ett arkiv av SMHI-kompositer")
    r.add_argument("--archive", type=Path, help="katalog med radar_ÅÅMMDDTTMM.tif eller ÅÅÅÅMMDDTTMM.tif")
    r.add_argument("--download", action="store_true", help="hämta från SMHI i stället")
    r.add_argument("--start", type=date.fromisoformat, required=True)
    r.add_argument("--end", type=date.fromisoformat, required=True)
    f = sub.add_parser("fit", help="skatta kartan och skriv models/bias.npz")
    f.add_argument("--start", type=date.fromisoformat, required=True)
    f.add_argument("--end", type=date.fromisoformat, required=True)
    f.add_argument("--grid", type=Path, required=True, help="en SMHI-komposit (tif) som anger rutnätet")
    f.add_argument("--out", type=Path, default=Path("models/bias.npz"))
    f.add_argument("--cv", action="store_true", help="stationsvis korsvalidering")
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    session = requests.Session()
    session.headers["User-Agent"] = "nowcast/0.1 (hobbyprojekt)"
    store = Store(a.store)

    if a.cmd == "gauges":
        stations = fetch_stations(session)
        stations.save(a.store / "stations.json")
        for sid in stations.ids:
            recs = []
            for period in (["corrected-archive"] if a.archive else []) + ["latest-months"]:
                try:
                    recs += fetch_station(session, int(sid), period)
                except requests.RequestException as e:
                    log.warning("station %s %s: %s", sid, period, e)
            store.add_gauges(recs, stations.ids)
            log.info("station %s: %d timvärden", sid, len(recs))
        return 0

    if a.cmd == "radar":
        stations = Stations.load(a.store / "stations.json")
        if stations is None:
            log.error("kör först: nowcast-bias gauges")
            return 1
        t = datetime(a.start.year, a.start.month, a.start.day, tzinfo=UTC)
        end = datetime(a.end.year, a.end.month, a.end.day, tzinfo=UTC) + timedelta(days=1)
        grid = None
        while t < end:
            path = None
            if a.archive:
                for name in (f"radar_{t:%y%m%d%H%M}.tif", f"{t:%Y%m%d%H%M}.tif"):
                    for cand in (a.archive / name, a.archive / f"{t:%Y/%m/%d}" / name):
                        if cand.exists():
                            path = cand
            elif a.download:
                tifs = a.store / "tif"
                tifs.mkdir(exist_ok=True)
                try:
                    path = radar.fetch(t, tifs, session)
                except requests.RequestException:
                    path = None
            if path is not None:
                rain, _ = radar.read_rain(path)
                grid = grid or _grid_from_tif(path)
                store.add_radar(t, rain, None, stations, grid, keep=True)
                if a.download:
                    path.unlink()
            t += radar.STEP
            if t.minute == 0 and t.hour == 0:
                log.info("radar %s klar", (t - timedelta(days=1)).date())
        store.flush()
        return 0

    if a.cmd == "fit":
        stations = Stations.load(a.store / "stations.json")
        grid = _grid_from_tif(a.grid)
        corr, rep = fit(store, stations, grid, a.start, a.end)
        a.out.parent.mkdir(parents=True, exist_ok=True)
        corr.save(a.out)
        print(json.dumps({"i_urvalet": rep}, ensure_ascii=False, indent=1))
        if a.cv:
            print(json.dumps({"korsvaliderat": cross_validate(store, stations, grid, a.start, a.end)}, ensure_ascii=False, indent=1))
        print("koefficienter per månad (a, b, c):")
        for m, c in enumerate(corr.coef):
            print(f"  {m + 1:2d}: {c[0]:+.3f} {c[1]:+.3f} {c[2]:+.3f}  faktor vid 1/3/5 km: "
                  + " ".join(f"{np.exp(c[0] + c[1] * h + c[2] * h * h):.2f}" for h in (1, 3, 5)))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
