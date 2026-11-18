"""Verifiering: timsummorna från Tim-KNEP, MET Norge och SNOW mot radarn och SMHI:s regnmätare, 7 och 30 dygn bakåt.

Allt räknas på Pi:n och skrivs till verif.json bredvid manifestet; sidan ritar bara upp det.

Utgåvan. Första cykeln i varje timme (samma regel som runs.py) sparas prognoserna för de LEADS
timmar som slutar hh+1 till hh+5, där hh är utgåvans heltimme, i cache/verif/pending/: Tim-KNEP ur
cykelns rutor, MET Norges och SNOW:s senaste lopp som fanns i cykeln (compare.py sparar dem i
cache/verif/src/) och persistens, radarns timme som slutar hh. Ledtiden k är timmen som slutar k
timmar efter heltimmen, lika för alla modeller oavsett hur gammalt deras lopp var. Hur gamla
loppen var redovisas i verif.json.

Rutnätet. Radarns rutnät (2 km, EPSG:3006) i block om BLOCK gånger BLOCK, alltså 4 km som MET
Norges glesade fält. Tim-KNEP och radarn medlas i blocken, MET Norge och SNOW omprojiceras med medel.

Facit, radarn. Analysen som sidan visar (volymkorrigerad), men bara block där alla pixlar är
uppmätta (SMHI, OPERA eller radarvolymer) i minst MIN_FRAMES av timmens 12 bilder. Utfyllnad med
flyttad analys räknas inte. Tim-KNEP utgår från samma analys, vilket gynnar den mot radarn.

Facit, mätarna. SMHI:s timsummor (parameter 7, kvalitet G och Y, ur gauges.json) mot modellens
värde i blocket där mätaren står. Värden över GAUGE_MAX mm räknas inte (felaktiga värden finns i
arkivet). Radarn verifieras också mot mätarna, som jämförelse. Mätarna kommer ungefär en timme
efter radarn, så en utgåva räknas först GAUGE_DELAY efter sin sista timme.

Facit, A2T. Analysen rättad mot mätarna (analys/a2.py, i cykeln med --a2), vid sidan av radarn och
inte i stället för den. a2_cykel.kor sparar A2T:s timsumma på verifieringens rutnät i
cache/verif/a2t/ (store_a2t) varje gång timmen räknas (om); en senare omräkning skriver över den
förra, så att räkningen tar den senaste versionen. A2T kommer 1 till 2,5 h efter timmen, inom
GAUGE_DELAY, så väntetiden ändras inte. Gruppen a2t räknas som radar på blocken där A2T, radarns
mask och prognosen finns; saknas A2T för en ledtid räknas bara radarn. I mätargruppen är A2T en
kandidat som radarn, men A2T har sett mätarna, så A2T i mätarens ruta är nästan mätaren och A2T-facit
och mätarfacit är inte två oberoende bevis.

Urvalet. Varje modell räknas på de block och timmar där facit, modellen och Tim-KNEP finns.
Skillnaden mot Tim-KNEP räknas parvis: Tim-KNEP på exakt samma block och timmar som den andra
modellen (nyckeln ours@met), så att en modell som bara räknar två timmar inte jämförs mot ett
annat urval.

Tabellerna summeras per dygn (UTC, efter utgåvans heltimme) i cache/verif/days/ och behålls i
KEEP_DAYS dygn. Osäkerheten är bootstrap över dygnen (BOOT dragningar, 90 %-intervall), eftersom
timmar och block samma dygn hänger ihop.
"""

from __future__ import annotations

import json
import logging
import warnings
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
from rasterio.crs import CRS
from rasterio.transform import Affine
from rasterio.warp import Resampling, reproject

from . import render
from .analys import composite
from .analys.radar import Grid

log = logging.getLogger("knep")

HOUR = timedelta(hours=1)
STEP = timedelta(minutes=5)
WITHIN = timedelta(minutes=15)  # som runs.WITHIN: utgåvan är första cykeln i timmen
BLOCK = 2
LEADS = 5
THRESHOLDS = [0.1, 0.5, 1.0, 2.0, 4.0]  # mm under timmen
FSS_THRESHOLDS = [0.5, 1.0, 4.0]
FSS_KM = [4, 20, 60]  # fönstrets sida; 4 km är blocket självt, alltså punktvis
MIN_FRAMES = 11
MIN_CELLS = 50
GAUGE_DELAY = timedelta(hours=2, minutes=30)
GAUGE_MAX = 60.0
KEEP_DAYS = 35
A2T_KEEP = timedelta(hours=12)  # utgåvan räknas 7,5 h efter sin heltimme
WINDOWS = (7, 30)
BOOT = 1000
MEASURED = (composite.SOURCE_SMHI, composite.SOURCE_OPERA, composite.SOURCE_VOLUME)
MODELS = ("ours", "met", "snow", "persistens")
FILE = "verif.json"
AREA = "verif/area.png"

# kontinuerliga summor: antal, Σf, Σo, Σf², Σo², Σfo, Σ|f − o|
CONT = ("n", "sf", "so", "sff", "soo", "sfo", "sabs")


def _iso(t: datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _floor(t: datetime) -> datetime:
    return t.replace(minute=0, second=0, microsecond=0)


def vgrid(grid: Grid) -> Grid:
    """Verifieringens rutnät: radarns i block om BLOCK gånger BLOCK."""
    t = grid.transform
    return Grid(grid.crs, Affine(t.a * BLOCK, t.b, t.c, t.d, t.e * BLOCK, t.f), (grid.shape[0] // BLOCK, grid.shape[1] // BLOCK))


def block(field: np.ndarray) -> np.ndarray:
    """Medel i blocken. Ett block med någon NaN blir NaN."""
    h, w = field.shape[0] // BLOCK, field.shape[1] // BLOCK
    return field[:h * BLOCK, :w * BLOCK].reshape(h, BLOCK, w, BLOCK).astype(np.float32).mean(axis=(1, 3))


def source_dir(vdir: Path) -> Path:
    """Där compare.py lägger jämförelsekällornas timsummor."""
    return vdir / "src"


def store_hours(store: Path, name: str, reference: str, fetched: datetime, hours: list[tuple[datetime, np.ndarray]], grid: Grid) -> None:
    """Spara ett lopps timsummor (mm/h) för verifieringen. Anropas av compare.py."""
    if not hours:
        return
    store.mkdir(parents=True, exist_ok=True)
    tmp = store / f".{name}.tmp.npz"
    np.savez_compressed(tmp, ends=np.array([int(e.timestamp()) for e, _ in hours], np.int64),
                        fields=np.stack([f for _, f in hours]).astype(np.float16),
                        transform=np.array(grid.transform[:6], np.float64), crs=np.array(grid.crs.to_wkt()),
                        reference=np.array(reference), fetched=np.array(_iso(fetched)))
    tmp.replace(store / f"{name}.npz")


# ---------- facit: radarns timsummor ----------

def observe(vdir: Path, frames: list[tuple[datetime, np.ndarray]], source_of) -> None:
    """Lägg cykelns analyser i lagret och spara timmar som blivit hela.

    frames: (tid, fält i mm/h) för analyserna; source_of(t): källkoderna för analysen t, eller None.
    """
    d5, d60 = vdir / "obs5", vdir / "obs60"
    d5.mkdir(parents=True, exist_ok=True)
    d60.mkdir(parents=True, exist_ok=True)
    for t, f in frames:
        p = d5 / f"{t:%Y%m%dT%H%M}.npy"
        if p.exists():
            continue
        src = source_of(t)
        if src is None or src.shape != f.shape:
            continue
        np.save(p, block(np.where(np.isin(src, MEASURED), f, np.nan)).astype(np.float16))
    if not frames:
        return
    latest = max(t for t, _ in frames)
    for k in range(3):
        end = _floor(latest) - k * HOUR
        out = d60 / f"{end:%Y%m%dT%H}.npy"
        if out.exists():
            continue
        have = [np.load(p).astype(np.float32) for j in range(12) if (p := d5 / f"{end - j * STEP:%Y%m%dT%H%M}.npy").exists()]
        if len(have) < 12 and latest < end + 2 * STEP:  # bilden kan komma i nästa cykel
            continue
        if len(have) < MIN_FRAMES:
            continue
        st = np.stack(have)
        n = np.isfinite(st).sum(0)
        hour = np.where(n >= MIN_FRAMES, np.nansum(st, 0) / np.maximum(n, 1), np.nan)
        np.save(out, hour.astype(np.float16))
    _prune(d5, "*.npy", latest - 3 * HOUR, "%Y%m%dT%H%M")
    _prune(d60, "*.npy", latest - (LEADS + 9) * HOUR, "%Y%m%dT%H")


def _prune(d: Path, pattern: str, oldest: datetime, fmt: str) -> None:
    for p in d.glob(pattern):
        try:
            t = datetime.strptime(p.stem, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
        if t < oldest:
            p.unlink()


def obs_hour(vdir: Path, end: datetime) -> np.ndarray | None:
    p = vdir / "obs60" / f"{end:%Y%m%dT%H}.npy"
    return np.load(p).astype(np.float32) if p.exists() else None


# ---------- facit: A2T:s timsummor ----------

def a2t_dir(vdir: Path) -> Path:
    return vdir / "a2t"


def store_a2t(vdir: Path, end: datetime, field: np.ndarray, n: int, now: datetime) -> None:
    """Spara A2T:s timsumma (mm, radarns rutnät) för timmen som slutar end, i block. Anropas av a2_cykel.kor.

    En senare omräkning av samma timme skriver över den förra. n: antalet mätarvärden (märket)."""
    d = a2t_dir(vdir)
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / f".{end:%Y%m%dT%H}.tmp.npz"
    np.savez_compressed(tmp, hour=block(field).astype(np.float16), n=np.array(int(n), np.int64),
                        computed=np.array(_iso(now)))
    tmp.replace(d / f"{end:%Y%m%dT%H}.npz")
    _prune(d, "*.npz", now - A2T_KEEP, "%Y%m%dT%H")


def a2t_hour(vdir: Path, end: datetime) -> tuple[np.ndarray, int] | None:
    """A2T:s timsumma i block och antalet mätarvärden, eller None."""
    try:
        with np.load(a2t_dir(vdir) / f"{end:%Y%m%dT%H}.npz") as z:
            return z["hour"].astype(np.float32), int(z["n"])
    except (OSError, KeyError, ValueError):
        return None


# ---------- utgåvan ----------

def due(vdir: Path, t0: datetime) -> bool:
    hour = _floor(t0)
    return t0 - hour <= WITHIN and not (vdir / "pending" / f"{hour:%Y%m%dT%H}.npz").exists()


def _warp(field: np.ndarray, src: Grid, dst: Grid) -> np.ndarray:
    out = np.full(dst.shape, np.nan, np.float32)
    reproject(np.asarray(field, np.float32), out, src_transform=src.transform, src_crs=src.crs, src_nodata=np.nan,
              dst_transform=dst.transform, dst_crs=dst.crs, dst_nodata=np.nan, resampling=Resampling.average)
    return out


def _source_hours(store: Path, name: str, t0: datetime) -> dict[datetime, tuple[np.ndarray, Grid, str]]:
    """Källans timmar som fanns i cykeln t0: för varje sluttid det senaste loppet."""
    best: dict[datetime, tuple[str, int, Path]] = {}
    for p in sorted(store.glob(f"{name}*.npz")) if store.exists() else []:
        try:
            with np.load(p) as d:
                fetched, ref, ends = _parse(str(d["fetched"])), str(d["reference"]), d["ends"]
        except (OSError, KeyError, ValueError):
            continue
        if fetched > t0 or fetched < t0 - 6 * HOUR:
            continue
        for i, e in enumerate(ends):
            end = datetime.fromtimestamp(int(e), UTC)
            if end not in best or ref > best[end][0]:
                best[end] = (ref, i, p)
    out = {}
    for end, (ref, i, p) in best.items():
        with np.load(p) as d:
            grid = Grid(CRS.from_wkt(str(d["crs"])), Affine(*d["transform"]), d["fields"].shape[1:])
            out[end] = (d["fields"][i].astype(np.float32), grid, ref)
    return out


def issue(vdir: Path, grid: Grid, t0: datetime, frames: list[tuple]) -> dict:
    """Spara utgåvan t0 på verifieringens rutnät. frames: (tid, sort, fält, ...) som till Renderer.write."""
    vg, hour = vgrid(grid), _floor(t0)
    ends = [hour + k * HOUR for k in range(1, LEADS + 1)]
    arrays, refs = {}, {"ours": _iso(t0)}
    ours = {end: f for end, _, _, f in render.aggregate([fr[:3] for fr in frames], 60)}
    for k, end in enumerate(ends, 1):
        if end in ours:
            arrays[f"ours_{k}"] = block(ours[end]).astype(np.float16)
    pers = obs_hour(vdir, hour)
    if pers is not None:
        refs["persistens"] = _iso(hour)
        for k in range(1, LEADS + 1):
            arrays[f"persistens_{k}"] = pers.astype(np.float16)
    for name in ("met", "snow"):
        got = _source_hours(source_dir(vdir), name, t0)
        lead_refs = []
        for k, end in enumerate(ends, 1):
            if end in got:
                field, src, ref = got[end]
                arrays[f"{name}_{k}"] = _warp(field, src, vg).astype(np.float16)
                lead_refs.append(ref)
        if lead_refs:
            refs[name] = max(lead_refs)
    meta = {"issued": _iso(t0), "hour": _iso(hour), "refs": refs, "shape": list(vg.shape)}
    d = vdir / "pending"
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / f".{hour:%Y%m%dT%H}.tmp.npz"
    np.savez_compressed(tmp, meta=np.array(json.dumps(meta)), **arrays)
    tmp.replace(d / f"{hour:%Y%m%dT%H}.npz")
    # jämförelsekällornas gamla lopp behövs inte längre
    for p in source_dir(vdir).glob("*.npz") if source_dir(vdir).exists() else []:
        try:
            with np.load(p) as z:
                old = _parse(str(z["fetched"])) < t0 - 6 * HOUR
        except (OSError, KeyError, ValueError):
            old = True
        if old:
            p.unlink()
    return meta


# ---------- tabellerna ----------

def contingency(f: np.ndarray, o: np.ndarray) -> np.ndarray:
    """(tröskel, [träff, falsklarm, miss, rätt torrt])."""
    out = np.zeros((len(THRESHOLDS), 4), np.int64)
    for i, thr in enumerate(THRESHOLDS):
        fy, oy = f >= thr, o >= thr
        a, b, c = int((fy & oy).sum()), int((fy & ~oy).sum()), int((~fy & oy).sum())
        out[i] = a, b, c, f.size - a - b - c
    return out


def continuous(f: np.ndarray, o: np.ndarray) -> np.ndarray:
    f, o = f.astype(np.float64), o.astype(np.float64)
    return np.array([f.size, f.sum(), o.sum(), (f * f).sum(), (o * o).sum(), (f * o).sum(), np.abs(f - o).sum()])


def _boxsum(I: np.ndarray, win: int) -> np.ndarray:
    """Antalet i ett centrerat fönster win gånger win över de två sista axlarna, noll utanför (summerad areatabell)."""
    h = win // 2
    P = np.pad(I, [(0, 0)] * (I.ndim - 2) + [(h + 1, h), (h + 1, h)]).cumsum(-2, dtype=np.int32).cumsum(-1, dtype=np.int32)
    return P[..., win:, win:] - P[..., :-win, win:] - P[..., win:, :-win] + P[..., :-win, :-win]


def fss_many(fields: dict[str, np.ndarray], O: np.ndarray, mask: np.ndarray, km: float) -> dict[str, np.ndarray]:
    """FSS-summorna för flera prognoser på samma block: (tröskel, skala, [Σ(Pf − Po)², Σ(Pf² + Po²)]).

    Andelarna räknas bara ur blocken i mask. Facit och masken räknas en gång för alla prognoser.
    """
    keys = list(fields)
    out = {k: np.zeros((len(FSS_THRESHOLDS), len(FSS_KM), 2)) for k in keys}
    rows, cols = np.nonzero(mask)
    if not rows.size or not keys:
        return out
    r0, r1, c0, c1 = rows.min(), rows.max() + 1, cols.min(), cols.max() + 1  # bara rutan runt facit
    m = mask[r0:r1, c0:c1]
    thr = np.asarray(FSS_THRESHOLDS, np.float32)[:, None, None]
    Io = ((O[r0:r1, c0:c1] >= thr) & m).astype(np.uint8)
    If = np.stack([(fields[k][r0:r1, c0:c1] >= thr) & m for k in keys]).astype(np.uint8)  # (prognos, tröskel, rad, kolumn)
    M = m.astype(np.uint8)
    Mf = M.astype(np.float32)
    for j, scale in enumerate(FSS_KM):
        win = max(1, round(scale / km)) | 1
        if win == 1:
            po, pf = Io.astype(np.float32), If.astype(np.float32)
        else:
            inv = Mf / np.maximum(_boxsum(M, win), 1)  # 1 / antalet block i fönstret, 0 utanför masken
            po, pf = _boxsum(Io, win) * inv, _boxsum(If, win) * inv
        num = ((pf - po) ** 2).sum((-2, -1), dtype=np.float64)
        den = (pf * pf + po * po).sum((-2, -1), dtype=np.float64)
        for i, k in enumerate(keys):
            out[k][:, j, 0], out[k][:, j, 1] = num[i], den[i]
    return out


def fss_parts(F: np.ndarray, O: np.ndarray, mask: np.ndarray, km: float) -> np.ndarray:
    return fss_many({"f": F}, O, mask, km)["f"]


class Day:
    """Summorna för ett dygn."""

    def __init__(self, path: Path, shape: tuple[int, int]):
        self.path = path
        self.arrays: dict[str, np.ndarray] = {}
        self.meta = {"issues": 0, "issued": [], "stations": {}, "lags": {}, "obs_hours": 0, "gauge_hours": 0,
                     "a2t_hours": 0, "a2t_n": 0}
        self.area = np.zeros(shape, np.uint16)
        if path.exists():
            with np.load(path) as d:
                self.meta = json.loads(str(d["meta"]))
                self.meta.setdefault("a2t_hours", 0)  # dygn från före A2T
                self.meta.setdefault("a2t_n", 0)
                self.arrays = {k: d[k] for k in d.files if k not in ("meta", "area")}
                if d["area"].shape == tuple(shape):
                    self.area = d["area"]

    def _get(self, name: str, shape: tuple, dtype) -> np.ndarray:
        if name not in self.arrays:
            self.arrays[name] = np.zeros(shape, dtype)
        return self.arrays[name]

    def add(self, obs: str, key: str, k: int, f: np.ndarray, o: np.ndarray, fss: np.ndarray | None = None) -> None:
        i = k - 1
        self._get(f"{obs}/{key}/ct", (LEADS, len(THRESHOLDS), 4), np.int64)[i] += contingency(f, o)
        self._get(f"{obs}/{key}/c", (LEADS, len(CONT)), np.float64)[i] += continuous(f, o)
        self._get(f"{obs}/{key}/hours", (LEADS,), np.int64)[i] += 1
        if fss is not None:
            self._get(f"{obs}/{key}/fss", (LEADS, len(FSS_THRESHOLDS), len(FSS_KM), 2), np.float64)[i] += fss

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(f".{self.path.stem}.tmp.npz")
        np.savez_compressed(tmp, meta=np.array(json.dumps(self.meta)), area=self.area, **self.arrays)
        tmp.replace(self.path)


def _gauge_points(gauges: dict | None, end: datetime, grid: Grid):
    """Mätarna med en timsumma som slutar end: id, rad, kolumn, värde och stationens uppgifter."""
    vals = ((gauges or {}).get("60") or {}).get(_iso(end)) or {}
    stations = (gauges or {}).get("stations") or {}
    ids = [sid for sid in vals if sid in stations and 0 <= vals[sid] <= GAUGE_MAX]
    if not ids:
        return [], np.zeros(0, int), np.zeros(0, int), np.zeros(0), stations
    from pyproj import Transformer
    tr = Transformer.from_crs("EPSG:4326", grid.crs, always_xy=True)
    x, y = tr.transform([stations[s][1] for s in ids], [stations[s][0] for s in ids])
    t = grid.transform  # rutnätet är inte vridet
    col = np.floor((np.asarray(x) - t.c) / t.a).astype(int)
    row = np.floor((np.asarray(y) - t.f) / t.e).astype(int)
    ok = (row >= 0) & (row < grid.shape[0]) & (col >= 0) & (col < grid.shape[1])
    ids = [s for s, k in zip(ids, ok) if k]
    return ids, row[ok], col[ok], np.array([vals[s] for s in ids], np.float64), stations


def _add_fields(day: Day, obs: str, k: int, fc: dict, O: np.ndarray, base: np.ndarray, km: float) -> None:
    """Alla modeller mot facit O på blocken base (där facit och Tim-KNEP finns), med paren mot Tim-KNEP."""
    F0 = fc["ours"]
    # modellerna med samma block som Tim-KNEP räknas tillsammans; de andra var för sig
    groups: dict[str, tuple[np.ndarray, dict]] = {}
    for m, F in fc.items():
        mask = base & np.isfinite(F)
        if mask.sum() < MIN_CELLS:
            continue
        g = "base" if np.array_equal(mask, base) else m
        groups.setdefault(g, (mask, {}))[1][m] = F
    for mask, Fs in groups.values():
        parts = fss_many(Fs | {"ours": F0}, O, mask, km)
        for m, F in Fs.items():
            day.add(obs, m, k, F[mask], O[mask], parts[m])
            if m != "ours":
                day.add(obs, f"ours@{m}", k, F0[mask], O[mask], parts["ours"])


def score(vdir: Path, grid: Grid, now: datetime, gauges: dict | None) -> int:
    """Räkna utgåvorna vars sista timme är äldre än GAUGE_DELAY; returnerar hur många."""
    vg = vgrid(grid)
    km = abs(vg.transform.a) / 1000
    done = 0
    for p in sorted((vdir / "pending").glob("*.npz")) if (vdir / "pending").exists() else []:
        try:
            with np.load(p) as z:
                meta = json.loads(str(z["meta"]))
                fields = {k: z[k] for k in z.files if k != "meta"}
        except (OSError, KeyError, ValueError):
            p.unlink()
            continue
        hour = _parse(meta["hour"])
        if now < hour + LEADS * HOUR + GAUGE_DELAY:
            continue
        if tuple(meta["shape"]) != vg.shape:
            log.warning("verifiering: utgåvan %s har ett annat rutnät, hoppas över", meta["hour"])
            p.unlink()
            continue
        day = Day(vdir / "days" / f"{hour:%Y-%m-%d}.npz", vg.shape)
        issued = _parse(meta["issued"])
        for name, ref in meta["refs"].items():
            if name not in ("ours", "persistens"):
                day.meta["lags"].setdefault(name, []).append(round((issued - _parse(ref)).total_seconds() / 60))
        for k in range(1, LEADS + 1):
            end = hour + k * HOUR
            fc = {m: fields[f"{m}_{k}"].astype(np.float32) for m in MODELS if f"{m}_{k}" in fields}
            if "ours" not in fc:
                continue
            F0 = fc["ours"]
            O = obs_hour(vdir, end)
            a2t = a2t_hour(vdir, end)
            A = a2t[0] if a2t is not None and a2t[0].shape == vg.shape else None
            if O is not None:
                base = np.isfinite(O) & np.isfinite(F0)
                if base.sum() >= MIN_CELLS:
                    day.meta["obs_hours"] += 1
                    day.area += base.astype(np.uint16)
                    _add_fields(day, "radar", k, fc, O, base, km)
                if A is not None:  # A2T bara där radarn också är facit
                    base_a = base & np.isfinite(A)
                    if base_a.sum() >= MIN_CELLS:
                        day.meta["a2t_hours"] += 1
                        day.meta["a2t_n"] += a2t[1]
                        _add_fields(day, "a2t", k, fc, A, base_a, km)
            ids, row, col, g, stations = _gauge_points(gauges, end, vg)
            if len(ids):
                cand = dict(fc)
                if O is not None:
                    cand["radar"] = O
                if A is not None:  # A2T har sett mätarna, så det här är ingen oberoende jämförelse
                    cand["a2t"] = A
                f0 = F0[row, col]
                used = np.zeros(len(ids), bool)
                for m, F in cand.items():
                    f = F[row, col]
                    ok = np.isfinite(f) & np.isfinite(f0)
                    if not ok.any():
                        continue
                    day.add("gauges", m, k, f[ok], g[ok])
                    if m != "ours":
                        day.add("gauges", f"ours@{m}", k, f0[ok], g[ok])
                    else:
                        used = ok
                if used.any():
                    day.meta["gauge_hours"] += 1
                    for sid in (s for s, u in zip(ids, used) if u):
                        st = day.meta["stations"].setdefault(sid, [0, *stations[sid][:3]])
                        st[0] += 1
        day.meta["issues"] += 1
        day.meta["issued"].append(meta["issued"])
        day.save()
        p.unlink()
        done += 1
    oldest = (now - timedelta(days=KEEP_DAYS)).date()
    for p in (vdir / "days").glob("*.npz") if (vdir / "days").exists() else []:
        try:
            if date.fromisoformat(p.stem) < oldest:
                p.unlink()
        except ValueError:
            pass
    return done


# ---------- måtten ----------

def _div(a, b):
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(b != 0, a / np.where(b != 0, b, 1), np.nan)


def dichotomous(ct: np.ndarray) -> dict[str, np.ndarray]:
    """Måtten ur en kontingenstabell [..., 4] = träff, falsklarm, miss, rätt torrt."""
    a, b, c, d = (ct[..., i].astype(np.float64) for i in range(4))
    n = a + b + c + d
    ar = _div((a + b) * (a + c), n)
    H, F = _div(a, a + c), _div(b, b + d)
    with np.errstate(divide="ignore", invalid="ignore"):
        lf, lh, l1f, l1h = np.log(F), np.log(H), np.log(1 - F), np.log(1 - H)
        sedi = _div(lf - lh - l1f + l1h, lf + lh + l1f + l1h)
        sedi = np.where(np.isfinite(sedi), sedi, np.nan)
    return {
        "pod": H,
        "far": _div(b, a + b),
        "pofd": F,
        "csi": _div(a, a + b + c),
        "ets": _div(a - ar, a + b + c - ar),
        "hss": _div(2 * (a * d - b * c), (a + c) * (c + d) + (a + b) * (b + d)),
        "pss": H - F,
        "mcc": _div(a * d - b * c, np.sqrt((a + b) * (a + c) * (b + d) * (c + d))),
        "fbi": _div(a + b, a + c),
        "sedi": sedi,
    }


def continuous_scores(c: np.ndarray) -> dict[str, np.ndarray]:
    n, sf, so, sff, soo, sfo, sabs = (c[..., i] for i in range(len(CONT)))
    with np.errstate(divide="ignore", invalid="ignore"):
        cov = n * sfo - sf * so
        r = _div(cov, np.sqrt(np.maximum(n * sff - sf * sf, 0) * np.maximum(n * soo - so * so, 0)))
        rmse = np.sqrt(np.maximum(_div(sff - 2 * sfo + soo, n), 0))
    return {"me": _div(sf - so, n), "mae": _div(sabs, n), "rmse": rmse, "r": r, "ratio": _div(sf, so)}


def fss_scores(x: np.ndarray) -> np.ndarray:
    return 1 - _div(x[..., 0], x[..., 1])


OBS = ("radar", "gauges", "a2t")  # facit: radarn, mätarna och A2T
DICHOTOMOUS = ("ets", "csi", "pod", "far", "fbi", "hss", "pss", "mcc", "sedi", "pofd")
CONTINUOUS = ("mae", "rmse", "me", "r", "ratio")


def _round(x, nd=4):
    """Till JSON: avrundat, med None för det som inte är definierat."""
    a = np.round(np.asarray(x, np.float64), nd)
    o = a.astype(object)
    o[~np.isfinite(a)] = None
    return o.tolist()


def _triple(est, lo, hi):
    """[skattning, nedre, övre] längst in."""
    if lo is None:
        lo = hi = np.full_like(est, np.nan)
    return _round(np.stack([est, lo, hi], -1))


def _stack(days: list[Day], name: str, shape: tuple, dtype) -> np.ndarray:
    return np.stack([d.arrays.get(name, np.zeros(shape, dtype)) for d in days])


def _interval(samples: np.ndarray, q=(0.05, 0.95)) -> tuple[np.ndarray, np.ndarray]:
    """Kvantilerna över dragningarna (första axeln), utan de dragningar där måttet är odefinierat.

    Närmaste rang i stället för interpolation; snabbare än nanpercentile och lika bra med 1000 dragningar.
    """
    srt = np.sort(samples, axis=0)  # NaN hamnar sist
    n = np.isfinite(samples).sum(0)
    out = []
    for p in q:
        i = np.clip(np.round(p * (n - 1)), 0, None).astype(int)[None]
        v = np.take_along_axis(srt, i, 0)[0]
        out.append(np.where(n >= 0.5 * len(samples), v, np.nan))  # måttet finns inte i hälften av dragningarna: inget intervall
    return out[0], out[1]


def _pick(i: int, ndim: int):
    """Ett index som väljer i på axeln före de ndim sista (modellen eller Tim-KNEP i ett par)."""
    return (Ellipsis, i) + (slice(None),) * ndim


def _window(days: list[Day], seed: int = 0) -> dict:
    """Måtten för dygnen days, med intervall för varje modell och för skillnaden mot Tim-KNEP.

    Bootstrap: varje dragning är hur många gånger varje dygn kom med, så att summorna för alla
    dragningar blir en matrisprodukt, och alla mått räknas på en gång ur dem.
    """
    D = len(days)
    weights = None
    if D >= 3:
        idx = np.random.default_rng(seed).integers(0, D, (BOOT, D))
        weights = np.stack([np.bincount(r, minlength=D) for r in idx]).astype(np.float64)

    def scores(per_day: np.ndarray, fn) -> dict:
        est = fn(per_day.sum(0))
        if weights is None:
            return {k: _triple(v, None, None) for k, v in est.items()}
        smp = fn(np.tensordot(weights, per_day.astype(np.float64), axes=1))
        out = {}
        for k, v in est.items():
            out[k] = _triple(v, *_interval(smp[k]))
        return out

    def diff(fn, ndim):
        return lambda x: {k: v[_pick(0, ndim)] - v[_pick(1, ndim)] for k, v in fn(x).items()}

    dich = lambda x: {k: v for k, v in dichotomous(x).items() if k in DICHOTOMOUS}  # noqa: E731
    cont = lambda x: {k: v for k, v in continuous_scores(x).items() if k in CONTINUOUS}  # noqa: E731
    fss = lambda x: {"fss": fss_scores(x)}  # noqa: E731
    ct_shape, c_shape, f_shape = (LEADS, len(THRESHOLDS), 4), (LEADS, len(CONT)), (LEADS, len(FSS_THRESHOLDS), len(FSS_KM), 2)
    res = {}
    for obs in OBS:
        keys = sorted({k.split("/")[1] for d in days for k in d.arrays if k.startswith(obs + "/")})
        if obs == "a2t" and not keys:
            continue  # utan A2T ser verif.json ut som förut
        res[obs] = {"models": {}, "diff": {}}
        for key in keys:
            if "@" in key:
                continue
            ct = _stack(days, f"{obs}/{key}/ct", ct_shape, np.int64)
            c = _stack(days, f"{obs}/{key}/c", c_shape, np.float64)
            hours = _stack(days, f"{obs}/{key}/hours", (LEADS,), np.int64).sum(0)
            e = {"hours": hours.tolist(), "n": c[..., 0].sum(0).astype(int).tolist(),
                 "events": (ct[..., 0] + ct[..., 2]).sum(0).tolist(), "scores": scores(ct, dich), "cont": scores(c, cont)}
            if obs != "gauges":
                fs = _stack(days, f"{obs}/{key}/fss", f_shape, np.float64)
                e["fss"] = scores(fs, fss)["fss"]
            res[obs]["models"][key] = e
            pair = f"ours@{key}"
            if key == "ours" or not any(f"{obs}/{pair}/ct" in d.arrays for d in days):
                continue
            ct0 = _stack(days, f"{obs}/{pair}/ct", ct_shape, np.int64)
            c0 = _stack(days, f"{obs}/{pair}/c", c_shape, np.float64)
            dd = {"scores": scores(np.stack([ct, ct0], 1), diff(dich, 2)), "cont": scores(np.stack([c, c0], 1), diff(cont, 1))}
            if obs != "gauges":
                fs0 = _stack(days, f"{obs}/{pair}/fss", f_shape, np.float64)
                dd["fss"] = scores(np.stack([fs, fs0], 1), diff(fss, 3))["fss"]
            res[obs]["diff"][key] = dd
    return res


DAY_META = ("issues", "obs_hours", "gauge_hours", "a2t_hours", "a2t_n")


def _daily(days: list[Day]) -> dict:
    """Råa summor per dygn, så att sidan kan räkna måtten för en egen period med samma formler.

    Per modell kontingenstabellerna, de kontinuerliga summorna, FSS-summorna och antalet timmar.
    Under pairs Tim-KNEP:s summor på den andra modellens urval (nyckeln ours@modell i dygnen), så att
    skillnaden mot Tim-KNEP går att räkna; under meta underlaget per dygn.
    """
    out = {"days": [d.path.stem for d in days], "radar": {}, "gauges": {}}
    pairs: dict[str, dict] = {}

    def sums(obs: str, key: str) -> dict:
        e = {"ct": _stack(days, f"{obs}/{key}/ct", (LEADS, len(THRESHOLDS), 4), np.int64).tolist(),
             "c": _round(_stack(days, f"{obs}/{key}/c", (LEADS, len(CONT)), np.float64), 3)}
        if obs != "gauges":
            e["fss"] = _round(_stack(days, f"{obs}/{key}/fss", (LEADS, len(FSS_THRESHOLDS), len(FSS_KM), 2), np.float64), 2)
        e["hours"] = _stack(days, f"{obs}/{key}/hours", (LEADS,), np.int64).tolist()
        return e

    for obs in OBS:
        found = sorted({k.split("/")[1] for d in days for k in d.arrays if k.startswith(obs + "/")})
        keys = [k for k in found if "@" not in k]
        if keys:
            out.setdefault(obs, {})  # a2t bara när den finns
        for key in keys:
            out[obs][key] = sums(obs, key)
        for key in found:
            if key.startswith("ours@"):
                pairs.setdefault(obs, {})[key.split("@", 1)[1]] = sums(obs, key)
    out["pairs"] = pairs
    meta = {k: [int(d.meta.get(k, 0)) for d in days] for k in DAY_META}
    meta["first"] = [min(d.meta["issued"]) if d.meta.get("issued") else None for d in days]
    meta["last"] = [max(d.meta["issued"]) if d.meta.get("issued") else None for d in days]
    out["meta"] = meta
    return out


def _load_days(vdir: Path, shape) -> list[Day]:
    return [Day(p, shape) for p in sorted((vdir / "days").glob("*.npz"))] if (vdir / "days").exists() else []


AREA_LEVELS = [0.02, 0.25, 0.5, 0.75]
AREA_COLORS = np.array([(31, 111, 235, 40), (31, 111, 235, 80), (31, 111, 235, 120), (31, 111, 235, 160)], np.uint8)


def summary(vdir: Path, out: Path, grid: Grid, now: datetime) -> dict:
    """Skriv verif.json och kartan över området; returnerar posten till manifestet."""
    vg = vgrid(grid)
    days = _load_days(vdir, vg.shape)
    today = now.date()
    doc = {"updated": _iso(now), "leads": list(range(1, LEADS + 1)), "thresholds": THRESHOLDS,
           "fss_thresholds": FSS_THRESHOLDS, "fss_km": FSS_KM, "grid_km": round(abs(vg.transform.a) / 1000, 1),
           "gauge_max": GAUGE_MAX, "min_frames": MIN_FRAMES, "boot": BOOT, "windows": {}}
    for w in WINDOWS:
        sel = [d for d in days if date.fromisoformat(d.path.stem) > today - timedelta(days=w)]
        if not sel:
            continue
        e = _window(sel)
        stations: dict[str, list] = {}
        lags: dict[str, list] = {}
        for d in sel:
            for sid, (n, lat, lon, name) in d.meta["stations"].items():
                s = stations.setdefault(sid, [0, lat, lon, name])
                s[0] += n
            for k, v in d.meta["lags"].items():
                lags.setdefault(k, []).extend(v)
        issued = sorted(t for d in sel for t in d.meta["issued"])
        e.update({
            "days": len(sel), "from": sel[0].path.stem, "to": sel[-1].path.stem,
            "issues": sum(d.meta["issues"] for d in sel), "first": issued[0] if issued else None, "last": issued[-1] if issued else None,
            "obs_hours": sum(d.meta["obs_hours"] for d in sel), "gauge_hours": sum(d.meta["gauge_hours"] for d in sel),
            "stations": [[sid, *v[1:], v[0]] for sid, v in sorted(stations.items())],
            "lags": {k: {"median": float(np.median(v)), "max": float(np.max(v)), "n": len(v)} for k, v in lags.items() if v},
        })
        if "a2t" in e:
            n = sum(d.meta.get("a2t_hours", 0) for d in sel)
            e["a2t_hours"] = n
            e["a2t_gauges"] = round(sum(d.meta.get("a2t_n", 0) for d in sel) / max(n, 1), 1)  # mätarvärden per timme
        doc["windows"][str(w)] = e
    if days:
        doc["daily"] = _daily([d for d in days if date.fromisoformat(d.path.stem) > today - timedelta(days=max(WINDOWS))])
        area = sum(d.area.astype(np.float64) for d in days[-max(WINDOWS):])
        hours = max(1, sum(d.meta["obs_hours"] for d in days[-max(WINDOWS):]))
        rend = render.Renderer(vg)
        (out / "verif").mkdir(parents=True, exist_ok=True)
        share = np.where(area > 0, area / hours, np.nan)
        rend._png(share, AREA_LEVELS, AREA_COLORS, out / AREA)
        doc["area"] = {"file": AREA, "bounds": rend.bounds, "levels": AREA_LEVELS}
    out.mkdir(parents=True, exist_ok=True)
    tmp = out / (FILE + ".tmp")
    tmp.write_text(json.dumps(doc, separators=(",", ":"), ensure_ascii=False, allow_nan=False))
    tmp.replace(out / FILE)
    return _entry(doc)


def _entry(doc: dict) -> dict:
    """Posten till manifestet; a2t bara när någon period har A2T som facit."""
    e = {"file": FILE, "updated": doc["updated"], "windows": sorted(int(k) for k in doc["windows"])}
    if any("a2t" in w for w in doc["windows"].values()):
        e["a2t"] = True
    return e


def cycle(vdir: Path, out: Path, grid: Grid, t0: datetime, frames: list[tuple], source_of) -> dict | None:
    """En cykels verifiering: facit, utgåvan om det är dags, räkning och verif.json."""
    observe(vdir, [(t, f) for t, kind, f, *_ in frames if kind == "obs"], source_of)
    if due(vdir, t0):
        issue(vdir, grid, t0, frames)
    try:
        gauges = json.loads((out / "gauges.json").read_text())
    except (FileNotFoundError, ValueError):
        gauges = None
    n = score(vdir, grid, t0, gauges)
    if n or not (out / FILE).exists():
        if not any((vdir / "days").glob("*.npz")) if (vdir / "days").exists() else True:
            return None
        return summary(vdir, out, grid, t0)
    try:
        return _entry(json.loads((out / FILE).read_text()))
    except (FileNotFoundError, ValueError, KeyError):
        return None

