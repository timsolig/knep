"""Simulerade radarbortfall ur riktiga timmar, med radarn som facit.

    uv run python experiments/bortfall/fall.py hal                     hålens storlek per radarkombination
    uv run python experiments/bortfall/fall.py bygg --del validering   fallen för en del (eller traning)
    uv run python experiments/bortfall/fall.py bygg --del traning --dagar 2020-02-10 --per-dag 2   provkörning
    uv run python experiments/bortfall/fall.py kontroll                vad som finns under /data/bortfall/fall

Ett fall är en eller flera svenska radarer (composite.RADARS) som släcks i 30 min till 6 h.
Hålet är de pixlar som radarn brukar täcka (SMHI-kompositen har data i minst halva dygnet),
som ligger inom 240 km från någon av de släckta radarerna och där ingen annan radar i RADARS
når inom 240 km. Starten väljs när det regnar i hålet (minst 3 % och 100 pixlar med minst
0,5 mm/h), och fönstret är 60 min före starten (uppvärmning, riktig radar) till bortfallets
slut. Varje fall sparas som en komprimerad npz:

    meta      json: dag, del, start, längd, radarer, utsnitt, tider, MEPS-körningar, mätare
    radar     uint8 (T, h, w) SMHI:s koder i utsnittet, en bild var 5:e minut från start - 60 min
              till slutet (dBZ = 0,4 v - 30, 0 = inget eko, 255 = ingen data). Facit i hålet
              och riktig radar utanför det. Hela fältet finns i /data/radar/ om det behövs.
    hal       bool (h, w) hålet
    avstand   uint16 (h, w) km till närmaste radar som fungerar
    meps      float16 (timmar, h, w) mm per timme på radarns rutnät; timme k gäller
              (meps_tid[k] - 1 h, meps_tid[k]] ur senaste körningen som fanns när timmen
              började (nwp.available med 6 h, som i experiments/sverige). NaN om MEPS saknas.
    matare_*  regnmätarna i utsnittet i fönstret (p7 timme, p14 kvart om den finns):
              station, lat, lon, rad, kol, tid (unix-sekunder, periodens slut), mm, i_hal

Källor som inte sparas: OPERA-kompositen innehåller de släckta radarerna och vore fusk, och
enskilda volymer finns i arkivet bara från 2025 (och de svenska bara som SCAN), se rapport 1.

Fallen dras med fast frö per dag. Per dag väljs högst --per-dag fall med olika
radarkombinationer, längderna i tur och ordning ur LANGDER så att alla åldrar får fall.
Bara dagarna i traning.json och delen validering i experiments/sverige/dagar.json används;
testdelen läses aldrig.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import shutil
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "sverige"))
sys.path.insert(0, str(HERE.parents[1] / "src"))
import data as sv  # noqa: E402

from knep import composite, nwp, radar  # noqa: E402

DATA = Path("/data")
OUT = DATA / "bortfall" / "fall"
GAUGES = DATA / "bortfall" / "matare"
MIN_FREE = 2 * 1024**3

RANGE_KM = 240.0          # räckvidden för både de släckta och de andra radarerna
LANGDER = (30, 60, 120, 180, 360)  # min
UPPVARMNING = 60          # min riktig radar före bortfallet
EFTER = 180               # min efter bortfallet som ska finnas i /data/radar (för prognosen efteråt)
STEG = 15                 # min mellan provade starttider
VAT_MM = 0.5
VAT_ANDEL, VAT_PX = 0.03, 100
MIN_HAL_PX = 300          # 1200 km²
PAR_KM, TRIPPEL_KM, FYRA_KM = 300.0, 330.0, 360.0   # grannar för två, tre och fyra i taget
MARGINAL_PX = 75          # 150 km runt hålet i utsnittet
SWEDISH = sorted(c for c in composite.RADARS if c.startswith("se"))

# mm/h för varje kod 0..255, samma formel som radar.read_rain
_DBZ = np.arange(256, dtype=np.float32) * radar.GAIN + radar.OFFSET
LUT = ((10.0 ** (_DBZ / 10.0) / radar.ZR_A) ** (1.0 / radar.ZR_B)).astype(np.float32)
LUT[radar.NO_ECHO] = 0.0
LUT[radar.NO_DATA] = np.nan


def to_rain(raw: np.ndarray) -> np.ndarray:
    return LUT[raw]


def read_raw(path: Path) -> np.ndarray:
    with rasterio.open(path) as src:
        return src.read(1)


# --- geometri ---------------------------------------------------------------------------------

def centres(transform, shape):
    h, w = shape
    x = transform.c + (np.arange(w) + 0.5) * transform.a
    y = transform.f + (np.arange(h) + 0.5) * transform.e
    return np.meshgrid(x, y)


def radar_xy(codes=None) -> dict[str, tuple[float, float]]:
    to = Transformer.from_crs("EPSG:4326", "EPSG:3006", always_xy=True)
    return {c: to.transform(lon, lat) for c, (lat, lon, _, _) in composite.RADARS.items() if codes is None or c in codes}


def distances_km(X, Y, xy: dict) -> dict[str, np.ndarray]:
    return {c: (np.hypot(X - x, Y - y) / 1000.0).astype(np.float32) for c, (x, y) in xy.items()}


def hole_mask(dist: dict[str, np.ndarray], off, coverage, range_km=RANGE_KM) -> np.ndarray:
    """Inom räckvidd från någon släckt radar, utom räckvidd från alla andra, och där radarn brukar ha data."""
    off = set(off)
    near_off = np.zeros(coverage.shape, bool)
    near_other = np.zeros(coverage.shape, bool)
    for c, d in dist.items():
        if c in off:
            near_off |= d <= range_km
        else:
            near_other |= d <= range_km
    return near_off & ~near_other & coverage


def nearest_working_km(dist: dict[str, np.ndarray], off) -> np.ndarray:
    return np.min([d for c, d in dist.items() if c not in set(off)], axis=0)


def combinations(xy: dict) -> list[tuple[str, ...]]:
    """Enstaka svenska radarer, grannar två, tre och fyra i taget, och alla svenska (SMHI:s komposit nere)."""
    d = lambda a, b: np.hypot(xy[a][0] - xy[b][0], xy[a][1] - xy[b][1]) / 1000.0
    close = lambda g, km: all(d(a, b) <= km for a, b in itertools.combinations(g, 2))
    out = [(c,) for c in SWEDISH]
    for n, km in ((2, PAR_KM), (3, TRIPPEL_KM), (4, FYRA_KM)):
        out += [g for g in itertools.combinations(SWEDISH, n) if close(g, km)]
    out.append(tuple(SWEDISH))
    return out


def unique_holes(holes: dict, min_px=MIN_HAL_PX, same_iou=0.9) -> dict:
    """Hål med minst min_px pixlar; nästan samma hål (IoU över same_iou) räknas en gång, med färst radarer."""
    kept = {}
    for combo in sorted(holes, key=lambda c: (len(c), c)):
        m = holes[combo]
        n = int(m.sum())
        if n < min_px:
            continue
        if any((m & k).sum() / (m | k).sum() > same_iou for k in kept.values()):
            continue
        kept[combo] = m
    return kept


def crop_box(mask: np.ndarray, margin=MARGINAL_PX):
    rows, cols = np.nonzero(mask)
    h, w = mask.shape
    return (max(int(rows.min()) - margin, 0), min(int(rows.max()) + margin + 1, h),
            max(int(cols.min()) - margin, 0), min(int(cols.max()) + margin + 1, w))


# --- urval ------------------------------------------------------------------------------------

def frame_times(d: date) -> list[datetime]:
    """Bilderna som finns lokalt för dagen: 90 min före till 5 h efter dygnet."""
    day = datetime(d.year, d.month, d.day, tzinfo=UTC)
    n = int((timedelta(hours=29) + timedelta(minutes=90)) / radar.STEP) + 1
    return [day - timedelta(minutes=90) + k * radar.STEP for k in range(n)]


def eligible_starts(present: set[datetime], starts, minutes: int) -> list[datetime]:
    """Starttider där hela fönstret (uppvärmning, bortfall och EFTER min efteråt) finns."""
    out = []
    for t0 in starts:
        t = t0 - timedelta(minutes=UPPVARMNING)
        end = t0 + timedelta(minutes=minutes + EFTER)
        ok = True
        while t <= end:
            if t not in present:
                ok = False
                break
            t += radar.STEP
        if ok:
            out.append(t0)
    return out


def wet_enough(rain: np.ndarray, hole: np.ndarray) -> bool:
    r = rain[hole]
    r = r[np.isfinite(r)]
    if r.size == 0:
        return False
    wet = int((r >= VAT_MM).sum())
    return wet >= VAT_PX and wet / r.size >= VAT_ANDEL


def seed_for(day: date, part: str) -> int:
    return int.from_bytes(hashlib.sha256(f"bortfall-{part}-{day}".encode()).digest()[:4], "little")


def choose(day: date, part: str, holes: dict, wet: dict, present: set, per_day: int) -> list[tuple]:
    """Fall för dagen: (radarer, start, längd). Olika kombinationer, längderna i tur och ordning.

    holes: kombination -> mask, wet: (kombination, start) -> bool för starttiderna dygnet runt.
    """
    rng = np.random.default_rng(seed_for(day, part))
    combos = list(holes)
    order = rng.permutation(len(combos))
    k0 = int(rng.integers(len(LANGDER)))
    chosen = []
    for i in order:
        if len(chosen) >= per_day:
            break
        combo = combos[i]
        minutes = LANGDER[(k0 + len(chosen)) % len(LANGDER)]
        starts = sorted(t for (c, t), w in wet.items() if c == combo and w)
        starts = eligible_starts(present, starts, minutes)
        if not starts:
            continue
        chosen.append((combo, starts[int(rng.integers(len(starts)))], minutes))
    return chosen


# --- MEPS och mätare --------------------------------------------------------------------------

def meps_hours(t_first: datetime, t_last: datetime) -> list[datetime]:
    """Hela timmar (timmens slut) som täcker (t_first - 5 min, t_last]."""
    h = t_first.replace(minute=0, second=0, microsecond=0)
    if h < t_first:
        h += timedelta(hours=1)
    out = [h]
    while out[-1] < t_last:
        out.append(out[-1] + timedelta(hours=1))
    return out


class Meps:
    """Körningarna på radarns rutnät, laddade vid behov."""

    def __init__(self, grid: radar.Grid):
        self.grid = grid
        self._cache: dict = {}

    def run_for(self, hour_start: datetime) -> datetime | None:
        """Senaste körningen som fanns när timmen började och som finns lokalt."""
        run = nwp.available(hour_start, sv.CYCLE)
        for _ in range(4):
            if sv.meps_path(run).exists():
                return run
            run -= timedelta(hours=sv.CYCLE)
        return None

    def field(self, run: datetime) -> np.ndarray | None:
        if run not in self._cache:
            try:
                r = nwp.Run.load(sv.meps_path(run))
                self._cache = {run: r.on(self.grid)}  # en körning i minnet åt gången
            except (OSError, ValueError, KeyError) as e:
                print("MEPS kan inte läsas", run, e, flush=True)
                self._cache = {run: None}
        return self._cache[run]

    def hours(self, ends: list[datetime], box) -> tuple[np.ndarray, list[str]]:
        r0, r1, c0, c1 = box
        out = np.full((len(ends), r1 - r0, c1 - c0), np.nan, np.float32)
        runs = []
        for k, end in enumerate(ends):
            run = self.run_for(end - timedelta(hours=1))
            f = self.field(run) if run is not None else None
            lead = int((end - run) // timedelta(hours=1)) - 1 if run is not None else -1
            if f is None or not (0 <= lead < len(f)):
                runs.append("")
                continue
            out[k] = f[lead, r0:r1, c0:c1]
            runs.append(f"{run:%Y%m%dT%H}+{lead}")
        return out.astype(np.float16), runs


def load_gauges() -> dict[str, dict]:
    out = {}
    for p in (7, 14):
        path = GAUGES / f"p{p}.npz"
        if path.exists():
            z = np.load(path)
            out[f"p{p}"] = {k: z[k] for k in z.files}
    return out


def gauges_in(g: dict, transform, box, hole, t_first: datetime, t_last: datetime) -> dict[str, np.ndarray]:
    to = Transformer.from_crs("EPSG:4326", "EPSG:3006", always_xy=True)
    sel = (g["time"] > t_first.timestamp()) & (g["time"] <= t_last.timestamp())
    x, y = to.transform(g["lon"][sel].astype(float), g["lat"][sel].astype(float))
    col = np.floor((np.asarray(x) - transform.c) / transform.a).astype(int) - box[2]
    row = np.floor((np.asarray(y) - transform.f) / transform.e).astype(int) - box[0]
    h, w = hole.shape
    inside = (row >= 0) & (row < h) & (col >= 0) & (col < w)
    ih = np.zeros(inside.shape, bool)
    ih[inside] = hole[row[inside], col[inside]]
    return {"station": g["station"][sel][inside], "lat": g["lat"][sel][inside], "lon": g["lon"][sel][inside],
            "rad": row[inside].astype(np.int16), "kol": col[inside].astype(np.int16),
            "tid": g["time"][sel][inside], "mm": g["mm"][sel][inside], "i_hal": ih[inside]}


# --- byggandet --------------------------------------------------------------------------------

def days_for(part: str) -> list[date]:
    if part == "traning":
        days = [date.fromisoformat(d["day"]) for d in json.loads((HERE / "traning.json").read_text())]
        frozen = [date.fromisoformat(d["day"]) for d in json.loads(sv.DAYS.read_text())]
        assert not [d for d in days if any(abs((d - f).days) <= 2 for f in frozen)]
        return days
    if part == "validering":
        return [date.fromisoformat(d["day"]) for d in sv.load_days("validering")]
    raise ValueError(f"okänd del {part}; testdelen används inte")


def case_name(combo, t0: datetime, minutes: int) -> str:
    who = "alla" if len(combo) == len(SWEDISH) else "-".join(combo)
    return f"{t0:%Y%m%dT%H%M}_{minutes:03d}_{who}"


def build_day(d: date, part: str, per_day: int, out: Path, gauges: dict) -> list[dict]:
    times = frame_times(d)
    present = {t for t in times if sv.radar_path(t).exists()}
    if not present:
        print(d, "ingen radar lokalt", flush=True)
        return []
    first = sv.radar_path(min(present))
    with rasterio.open(first) as src:
        transform, shape = src.transform, src.shape
        grid = radar.Grid(src.crs or rasterio.crs.CRS.from_epsg(3006), transform, shape)
    X, Y = centres(transform, shape)
    xy = radar_xy()
    dist = distances_km(X, Y, xy)

    # täckningen och regnet var 15:e minut genom dygnet
    day0 = datetime(d.year, d.month, d.day, tzinfo=UTC)
    starts = [day0 + timedelta(minutes=STEG * k) for k in range(24 * 60 // STEG)]
    probe = {t: to_rain(read_raw(sv.radar_path(t))) for t in starts if t in present}
    coverage = np.mean([np.isfinite(r) for r in probe.values()], axis=0) >= 0.5
    holes = unique_holes({c: hole_mask(dist, c, coverage) for c in combinations(xy)})
    wet = {(c, t): wet_enough(r, m) for c, m in holes.items() for t, r in probe.items()}
    del probe

    meps = Meps(grid)
    done = []
    for combo, t0, minutes in choose(d, part, holes, wet, present, per_day):
        if shutil.disk_usage(DATA).free < MIN_FREE:
            print("AVBRYTER: mindre än 2 GB ledigt på /data", flush=True)
            break
        hole = holes[combo]
        box = crop_box(hole)
        r0, r1, c0, c1 = box
        t_first = t0 - timedelta(minutes=UPPVARMNING)
        t_end = t0 + timedelta(minutes=minutes)
        window = [t_first + k * radar.STEP for k in range(int((t_end - t_first) / radar.STEP) + 1)]
        raw = np.stack([read_raw(sv.radar_path(t))[r0:r1, c0:c1] for t in window])
        mfield, runs = meps.hours(meps_hours(t_first, t_end), box) if d.year >= 2020 else (np.zeros((0, r1 - r0, c1 - c0), np.float16), [])
        hcrop = hole[r0:r1, c0:c1]
        meta = {
            "namn": case_name(combo, t0, minutes), "dag": d.isoformat(), "del": part,
            "start": t0.isoformat(), "langd_min": minutes, "slut": t_end.isoformat(),
            "radarer": list(combo), "forsta_bild": t_first.isoformat(), "steg_min": 5,
            "bilder": len(window), "uppvarmning_bilder": UPPVARMNING // 5,
            "utsnitt": [r0, r1, c0, c1], "rutnat": {"transform": list(transform)[:6], "shape": list(shape), "crs": "EPSG:3006"},
            "hal_px": int(hole.sum()),
            "vat_andel_start": float(np.nanmean(to_rain(raw[UPPVARMNING // 5])[hcrop] >= VAT_MM)),
            "meps_tid": [h.isoformat() for h in meps_hours(t_first, t_end)] if mfield.shape[0] else [],
            "meps_korning": runs,
            "efter_min_lokalt": EFTER,
            "matare": sorted(gauges),
        }
        arrays = {"radar": raw, "hal": hcrop,
                  "avstand": np.round(nearest_working_km(dist, combo)[r0:r1, c0:c1]).astype(np.uint16),
                  "meps": mfield}
        for p, g in gauges.items():
            for k, v in gauges_in(g, transform, box, hcrop, t_first, t_end).items():
                arrays[f"matare_{p}_{k}"] = v
        path = out / f"{meta['namn']}.npz"
        tmp = path.with_name(path.stem + ".tmp.npz")
        np.savez_compressed(tmp, meta=np.array(json.dumps(meta, ensure_ascii=False)), **arrays)
        tmp.replace(path)
        meta["fil"] = path.name
        meta["storlek"] = path.stat().st_size
        done.append(meta)
        print(d, meta["namn"], f"hål {meta['hal_px']} px", f"våt {meta['vat_andel_start']:.2f}",
              f"{meta['storlek'] / 1e6:.1f} MB", flush=True)
    print(d, f"{len(holes)} kombinationer med hål, {len(done)} fall", flush=True)
    return done


def write_index(out: Path, part: str) -> None:
    cases = []
    for p in sorted(out.glob("*.npz")):
        if p.name.endswith(".tmp.npz"):
            continue
        with np.load(p) as z:
            m = json.loads(str(z["meta"]))
        m["fil"], m["storlek"] = p.name, p.stat().st_size
        cases.append(m)
    (out / "index.json").write_text(json.dumps({"del": part, "fall": cases}, indent=1, ensure_ascii=False) + "\n")
    print(part, len(cases), "fall i index,", f"{sum(c['storlek'] for c in cases) / 1e6:.0f} MB", flush=True)


def build(a) -> None:
    out = OUT / a.part
    out.mkdir(parents=True, exist_ok=True)
    days = days_for(a.part)
    if a.dagar:
        wanted = {date.fromisoformat(x) for x in a.dagar}
        days = [d for d in days if d in wanted]
    gauges = load_gauges()
    print(a.part, len(days), "dagar, mätare:", sorted(gauges) or "inga", flush=True)
    budget = a.max_gb * 1e9
    for d in days:
        if any(p.name.startswith(d.strftime("%Y%m%d")) for p in out.glob("*.npz")) and not a.om:
            print(d, "finns redan", flush=True)
            continue
        for m in build_day(d, a.part, a.per_dag, out, gauges):
            budget -= m["storlek"]
        if budget <= 0:
            print("AVBRYTER: datataket för körningen är nått", flush=True)
            break
    write_index(out, a.part)


def holes_report(a) -> None:
    """Hålens storlek per kombination, med täckningen från en bild."""
    p = next((DATA / "radar").rglob("*.tif"))
    with rasterio.open(p) as src:
        transform, shape = src.transform, src.shape
    coverage = np.isfinite(to_rain(read_raw(p)))
    X, Y = centres(transform, shape)
    xy = radar_xy()
    dist = distances_km(X, Y, xy)
    all_holes = {c: hole_mask(dist, c, coverage) for c in combinations(xy)}
    kept = unique_holes(all_holes)
    for combo, m in all_holes.items():
        n = int(m.sum())
        print(f"{'-'.join(combo) if len(combo) < 5 else 'alla svenska':40s} {n:7d} px {n * 4:8d} km²",
              "används" if combo in kept else "")
    print(len(kept), "olika hål med minst", MIN_HAL_PX, "px")


def check(a) -> None:
    for part in ("traning", "validering"):
        idx = OUT / part / "index.json"
        if not idx.exists():
            print(part, "inget index")
            continue
        cases = json.loads(idx.read_text())["fall"]
        print(part, len(cases), "fall,", len({c["dag"] for c in cases}), "dagar,",
              f"{sum(c['storlek'] for c in cases) / 1e6:.0f} MB")
        for L in LANGDER:
            print("  ", L, "min:", sum(c["langd_min"] == L for c in cases))
        sizes = {}
        for c in cases:
            sizes[len(c["radarer"])] = sizes.get(len(c["radarer"]), 0) + 1
        print("   radarer per fall:", dict(sorted(sizes.items())))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cmd", choices=["hal", "bygg", "kontroll"])
    p.add_argument("--del", dest="part", choices=["traning", "validering"], default="validering")
    p.add_argument("--dagar", nargs="*", help="bara de här dagarna (provkörning)")
    p.add_argument("--per-dag", dest="per_dag", type=int, default=8)
    p.add_argument("--om", action="store_true", help="bygg om dagar som redan har fall")
    p.add_argument("--max-gb", dest="max_gb", type=float, default=0.4, help="högsta mängd ny data för körningen")
    p.add_argument("--logg", type=Path, help="skriv utdata till den här filen (läggs till)")
    a = p.parse_args()
    if a.logg:
        sys.stdout = sys.stderr = open(a.logg, "a", buffering=1)
    {"hal": holes_report, "bygg": build, "kontroll": check}[a.cmd](a)


if __name__ == "__main__":
    main()
