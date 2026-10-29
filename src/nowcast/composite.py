"""Egen komposit som klarar radarbortfall.

Analysen byggs i lager, bäst först, på SMHI-kompositens rutnät (EPSG:3006, 2 km):

  1. SMHI:s komposit där den har data.
  2. Egen komposit av enskilda radarvolymer (ODIM PVOL) från svenska och
     grannländernas radarer, där SMHI:s komposit saknar data. Lägsta elevationen,
     och per pixel vinner den radar som ser lägst ner i atmosfären.
  3. OPERA-kompositen för Europa.
  4. Lagrangesk utfyllnad: förra analysen flyttad med rörelsefältet, med en kvalitet
     som avtar med tiden sedan pixeln senast sågs av en radar.

Volymer och OPERA-komposit hämtas från EUMETNET:s öppna radardata (CC BY 4.0) via
`sources.py`; den här modulen är ren numpy och testbar utan nätverk.

Varje pixel får en källa (SOURCE_*) och en kvalitet 0..1 som följer med till kartan.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from pyproj import CRS, Transformer

SOURCE_SMHI, SOURCE_VOLUME, SOURCE_OPERA, SOURCE_ADVECTED, SOURCE_NONE = 0, 1, 2, 3, 255
ZR_A, ZR_B = 200.0, 1.5
KE_A = 4.0 / 3.0 * 6371000.0  # effektiv jordradie för strålgången

# Aktiva radarer i och runt Sverige enligt OPERA:s register: (lat, lon, höjd m, räckvidd km)
RADARS = {
    "sekrn": (67.7088, 20.6178, 647, 240), "sella": (65.4309, 21.8650, 68, 240),
    "seosd": (63.2951, 14.7591, 466, 240), "seoer": (63.6395, 18.4019, 508, 240),
    "sehuv": (61.5771, 16.7144, 375, 240), "selek": (60.7230, 14.8776, 439, 240),
    "sebaa": (59.6110, 17.5833, 59, 240), "sehem": (57.3035, 18.4001, 59, 240),
    "seatv": (58.1059, 15.9363, 200, 240), "sevax": (58.2556, 12.8260, 128, 240),
    "seang": (56.3675, 12.8517, 187, 240), "sekaa": (56.2955, 15.6102, 106, 240),
    "nohur": (59.6272, 10.5645, 347, 240), "nohfj": (61.2318, 10.5273, 1064, 240),
    "norsa": (63.6905, 10.2037, 605, 240), "nosmn": (65.2201, 11.9926, 302, 240),
    "norst": (67.5307, 12.0986, 3, 240), "noand": (69.2414, 16.0028, 433, 240),
    "fikor": (60.1285, 21.6434, 35, 250), "fivim": (63.1048, 23.8209, 172, 250),
    "fiuta": (64.7749, 26.3189, 85, 250), "filuo": (67.1391, 26.8969, 514, 250),
    "dkste": (55.3262, 12.4493, 42, 240), "dkbor": (55.1127, 14.8875, 162, 240),
    "dksin": (57.4893, 10.1365, 104, 240),
}


@dataclass
class Sweep:
    """En elevation från en radarvolym: dBZ per (stråle, gate), NaN = ingen data, -32 = inget eko."""

    site: str
    lat: float
    lon: float
    height: float
    elangle: float
    rstart: float  # m till första gatens mitt
    rscale: float  # m mellan gates
    a1gate: int  # stråle som mättes först (ODIM), påverkar inte azimuten
    dbz: np.ndarray  # (nrays, nbins)


def read_pvol(path: Path, quantity: str = "DBZH") -> Sweep:
    """Läs lägsta elevationen med given storhet ur en ODIM HDF5-volym."""
    import h5py

    with h5py.File(path, "r") as h:
        src = h["what"].attrs["source"].decode() if isinstance(h["what"].attrs["source"], bytes) else str(h["what"].attrs["source"])
        nod = dict(p.split(":", 1) for p in src.split(",") if ":" in p).get("NOD", "okänd")
        lat, lon, hgt = (float(h["where"].attrs[k]) for k in ("lat", "lon", "height"))
        best = None
        for name in h:
            if not name.startswith("dataset"):
                continue
            ds = h[name]
            el = float(ds["where"].attrs["elangle"])
            for dn in ds:
                if not dn.startswith("data"):
                    continue
                what = ds[dn]["what"].attrs
                q = what["quantity"].decode() if isinstance(what["quantity"], bytes) else str(what["quantity"])
                if q == quantity and (best is None or el < best[0]):
                    best = (el, name, dn)
        if best is None:
            raise ValueError(f"{path}: ingen {quantity}")
        el, name, dn = best
        ds = h[name]
        w, what = ds["where"].attrs, ds[dn]["what"].attrs
        raw = ds[dn]["data"][...].astype(np.float32)
        dbz = raw * float(what["gain"]) + float(what["offset"])
        dbz[raw == float(what["nodata"])] = np.nan
        dbz[raw == float(what["undetect"])] = -32.0
        return Sweep(nod, lat, lon, hgt, el, float(w["rstart"]) * 1000 + float(w["rscale"]) / 2,
                     float(w["rscale"]), int(w.get("a1gate", 0)), dbz)


@dataclass
class TargetGrid:
    """Rutnät med pixelcentrum i EPSG:3006, som SMHI-kompositen."""

    west: float
    north: float
    res: float
    shape: tuple[int, int]
    _cache: dict = field(default_factory=dict, repr=False)

    def centres(self):
        h, w = self.shape
        x = self.west + (np.arange(w) + 0.5) * self.res
        y = self.north - (np.arange(h) + 0.5) * self.res
        return np.meshgrid(x, y)

    def lookup(self, s: Sweep):
        """(stråle, gate, strålhöjd) för varje pixel, sparat per radar och geometri."""
        nrays, nbins = s.dbz.shape
        key = (s.site, round(s.elangle, 2), nrays, nbins, s.rscale, s.rstart)
        if key not in self._cache:
            aeqd = CRS.from_proj4(f"+proj=aeqd +lat_0={s.lat} +lon_0={s.lon} +datum=WGS84 +units=m")
            to_radar = Transformer.from_crs(CRS.from_epsg(3006), aeqd, always_xy=True)
            X, Y = self.centres()
            x, y = to_radar.transform(X, Y)
            ground = np.hypot(x, y)
            az = (np.degrees(np.arctan2(x, y)) + 360.0) % 360.0
            el = np.radians(s.elangle)
            # avstånd längs strålen och strålhöjd med 4/3-jordmodellen
            slant = ground / np.cos(el)
            beam = np.sqrt(slant**2 + KE_A**2 + 2 * slant * KE_A * np.sin(el)) - KE_A + s.height
            # ODIM lagrar strålarna medurs från norr; a1gate anger bara vilken stråle som mättes först
            ray = (az / 360.0 * nrays).astype(int) % nrays
            gate = np.round((slant - s.rstart) / s.rscale).astype(int)
            inside = (gate >= 0) & (gate < nbins)
            self._cache[key] = (ray, np.clip(gate, 0, nbins - 1), inside, beam.astype(np.float32))
        return self._cache[key]


def grid_sweep(s: Sweep, grid: TargetGrid, max_range_km: float = 240.0):
    """Lägg en elevation på rutnätet. Returnerar dBZ och kvalitet (0 utanför räckvidd)."""
    ray, gate, inside, beam = grid.lookup(s)
    dbz = np.where(inside, s.dbz[ray, gate], np.nan).astype(np.float32)
    rng_ok = inside & ((gate * s.rscale + s.rstart) <= max_range_km * 1000)
    # låg stråle är bättre: kvalitet 1 vid marken, 0,37 vid 2 km höjd
    q = np.where(rng_ok & np.isfinite(dbz), np.exp(-np.maximum(beam, 0) / 2000.0), 0.0).astype(np.float32)
    return np.where(rng_ok, dbz, np.nan), q


def mosaic(layers):
    """Slå ihop (dBZ, kvalitet) från flera radarer: kvalitetsviktat medel i Z med vikter q^4.

    Vikten q^4 gör att den lägsta strålen dominerar men skarvarna blir mjuka.
    Returnerar dBZ (NaN där ingen radar ser) och bästa kvalitet per pixel.
    """
    num = den = best = None
    for dbz, q in layers:
        z = np.where(np.isfinite(dbz), 10 ** (np.nan_to_num(dbz, nan=-32.0) / 10), 0.0)
        w = np.where(np.isfinite(dbz), q.astype(np.float64) ** 4, 0.0)
        num = z * w if num is None else num + z * w
        den = w if den is None else den + w
        best = q if best is None else np.maximum(best, q)
    with np.errstate(invalid="ignore", divide="ignore"):
        dbz = np.where(den > 0, 10 * np.log10(np.maximum(num / np.where(den > 0, den, 1), 1e-4)), np.nan)
    return dbz.astype(np.float32), best


def dbz_to_rain(dbz):
    rain = (10 ** (dbz / 10) / ZR_A) ** (1 / ZR_B)
    rain[dbz <= 0] = 0.0  # under 0 dBZ räknas som inget regn, som SMHI:s komposit nära noll
    return rain.astype(np.float32)


@dataclass
class GapState:
    """Det som behöver sparas mellan körningar för utfyllnaden."""

    analysis: np.ndarray  # senaste analys i mm/h, NaN utanför
    age: np.ndarray  # minuter sedan pixeln senast hade riktig radardata
    expected: np.ndarray  # andel av körningarna senaste dygnet där pixeln hade data (0..1)

    @classmethod
    def load(cls, path: Path):
        if not path.exists():
            return None
        d = np.load(path)
        return cls(d["analysis"], d["age"], d["expected"])

    def save(self, path: Path):
        tmp = path.with_suffix(".tmp.npz")
        np.savez_compressed(tmp, analysis=self.analysis, age=self.age, expected=self.expected)
        tmp.replace(path)


def advect(field_, motion, steps=1):
    """Flytta ett fält med rörelsefältet (pixlar per 5 min) med semi-Lagrangesk interpolation."""
    from pysteps.extrapolation.semilagrangian import extrapolate

    return extrapolate(np.nan_to_num(field_), motion, steps, outval=np.nan)[-1]


def _age_smooth(moved, age, per_px_min=15.0, max_sigma=4.0):
    """Utjämnar en flyttad analys mer ju äldre den är: sigma = ålder/15 min pixlar, högst 4 (8 km)."""
    from scipy.ndimage import gaussian_filter

    out = moved.copy()
    base = np.nan_to_num(moved)
    for sigma in (1.0, 2.0, 3.0, max_sigma):
        sel = np.isfinite(moved) & (age / per_px_min >= sigma - 0.5)
        if sel.any():
            out[sel] = gaussian_filter(base, sigma)[sel]
    return out


def fill_gaps(rain, source, state: GapState | None, motion, dt_min=5.0, max_age=90.0, tau=30.0, expect_min=0.5,
              smooth=False):
    """Fyll pixlar som brukar ha data men saknar data nu med förra analysen flyttad med rörelsen.

    rain, source: aktuell analys och källa per pixel efter lager 1 till 3 (NaN och SOURCE_NONE där inget finns).
    Returnerar (rain, source, quality, ny GapState). Kvaliteten för utfyllda pixlar är exp(-ålder/tau),
    och efter max_age minuter släpps pixeln som saknad.
    """
    have = np.isfinite(rain)
    quality = np.where(have, 1.0, 0.0).astype(np.float32)
    if state is None:
        expected = have.astype(np.float32)
        age = np.where(have, 0.0, np.inf).astype(np.float32)
        return rain, source, quality, GapState(rain.copy(), age, expected)
    # förväntad täckning: långsamt glidande andel (cirka ett dygn vid 5 min)
    expected = (state.expected * (1 - 1 / 288) + have / 288).astype(np.float32)
    age = np.where(have, 0.0, state.age + dt_min).astype(np.float32)
    gap = ~have & (state.expected >= expect_min) & (age <= max_age)
    out = rain.copy()
    src = source.copy()
    if gap.any():
        moved = advect(state.analysis, motion) if motion is not None else state.analysis
        ok = gap & np.isfinite(moved)
        out[ok] = moved[ok]
        src[ok] = SOURCE_ADVECTED
        quality[ok] = np.exp(-age[ok] / tau)
        if smooth:
            # osäkerheten växer med åldern: fältet jämnas ut i stället för att flytta skarpa kärnor
            # som inte längre är observerade (prövas i experiments/outage.py). Tillståndet behåller
            # det outjämnade fältet så att utjämningen inte läggs på varje cykel.
            shown = out.copy()
            shown[ok] = _age_smooth(moved, np.where(ok, age, 0.0))[ok]
            return shown, src, quality, GapState(out.copy(), age, expected)
    return out, src, quality, GapState(out.copy(), age, expected)


def layer(rain, source, extra, code):
    """Lägg till en reservkälla (mm/h, NaN där den saknas) där analysen saknar data."""
    fill = ~np.isfinite(rain) & np.isfinite(extra)
    rain = np.where(fill, extra, rain)
    source = np.where(fill, code, source).astype(np.uint8)
    return rain, source


def missing_radars(rain, grid: TargetGrid, expected, radius_km=100.0, frac=0.5):
    """Svenska radarer vars närområde till stor del saknar data trots att det brukar finnas."""
    X, Y = grid.centres()
    to_grid = Transformer.from_crs(CRS.from_epsg(4326), CRS.from_epsg(3006), always_xy=True)
    out = []
    for code, (lat, lon, _, _) in RADARS.items():
        if not code.startswith("se"):
            continue
        x0, y0 = to_grid.transform(lon, lat)
        near = (np.hypot(X - x0, Y - y0) <= radius_km * 1000) & (expected >= 0.5)
        if near.sum() and (~np.isfinite(rain[near])).mean() >= frac:
            out.append(code)
    return out
