"""Artefakter bild för bild: ekrar (solstrålar och störningar) och skurar av prickar (anaprop),
uppgift 1 natten 2026-11-06, försök 2.

    uv run python experiments/analys/bild.py dag [--del 0/2]   per dag till /data/analys/artefakter/bild_dag/
    uv run python experiments/analys/bild.py sammanstall        till /data/analys/artefakter/bild_tabell.json

Bara tränings- och valideringsdagarna (days() i artefakter.py, som kontrollerar att ingen testdag kommer med).

Ekrar per bild: för varje radar i composite.RADARS räknas andelen eko (R >= 0,1 mm/h) i strålar om 1 grad
på 40 till 200 km avstånd, uppdelat i fyra avståndsband om 40 km. En eker är en stråle där andelen eko är minst
0,4 totalt och minst 0,25 i minst tre av de fyra banden (radiellt lång), medan medianen av strålarna 3 till 10
grader åt sidan är högst 0,1 (smal). Solens azimut och höjd räknas för bildens tid och radarns plats.

Prickar per bild: per radar och bild räknas eko inom 150 km som är isolerade (under 3 % eko inom 42 km) och
har texturen |dBZ - grannarnas medel| >= 8 dB. Samma sak räknas utanför de kända klotterrutorna
(kandidaterna på träningsdagarna i kartor.npz och vindkraftsrutorna, utvidgade en ruta), både isolerade
(prickar_nya) och alla kantiga ekon (kantigt_nytt). Under timmar då mätarna inom 25 km (p7) är torra räknas samma
sak för sig. Skurarna (anaprop och tillfälligt klotter) hittas i sammanställningen som timmar där antalet ligger
långt över radarns median.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
from scipy.ndimage import binary_dilation, uniform_filter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from artefakter import ECHO, OUT, RADAR, days, dbz_of, gauge_hours, grid_xy  # noqa: E402
from knep.analys import composite, radar  # noqa: E402

warnings.filterwarnings("ignore", category=RuntimeWarning)
DAG = OUT / "bild_dag"
RMIN, RMAX, BAND = 20, 100, 20  # rutor om 2 km: 40..200 km, band om 40 km
NB = 360


def sun(t: datetime, lat: float, lon: float) -> tuple[float, float]:
    """Solens azimut (från norr, medurs) och höjd i grader, NOAA:s förenklade formler."""
    doy = t.timetuple().tm_yday
    hr = t.hour + t.minute / 60
    g = 2 * np.pi / 365 * (doy - 1 + (hr - 12) / 24)
    eqt = 229.18 * (0.000075 + 0.001868 * np.cos(g) - 0.032077 * np.sin(g) - 0.014615 * np.cos(2 * g) - 0.040849 * np.sin(2 * g))
    dec = (0.006918 - 0.399912 * np.cos(g) + 0.070257 * np.sin(g) - 0.006758 * np.cos(2 * g) + 0.000907 * np.sin(2 * g)
           - 0.002697 * np.cos(3 * g) + 0.00148 * np.sin(3 * g))
    tst = hr * 60 + eqt + 4 * lon
    ha = np.radians(tst / 4 - 180)
    phi = np.radians(lat)
    cz = np.sin(phi) * np.sin(dec) + np.cos(phi) * np.cos(dec) * np.cos(ha)
    zen = np.arccos(np.clip(cz, -1, 1))
    az = np.degrees(np.arctan2(np.sin(ha), np.cos(ha) * np.sin(phi) - np.tan(dec) * np.cos(phi))) + 180
    return float(az % 360), float(90 - np.degrees(zen))


def geometry(grid: radar.Grid):
    """Per radar: index för (stråle, band) för rutorna 40..200 km bort och masken inom 150 km."""
    h, w = grid.shape
    to_rc = grid_xy(grid)
    yy, xx = np.mgrid[0:h, 0:w]
    geo = {}
    for code, (lat, lon, _, _) in composite.RADARS.items():
        r, c = to_rc(np.array([lat]), np.array([lon]))
        r0, c0 = float(r[0]), float(c[0])
        # azimuten på rutnätet; UTM 33 är nära nog nordorienterad för strålar om 1 grad i Sverige,
        # men meridiankonvergensen rättas ändå med radarns longitud
        conv = (lon - 15.0) * np.sin(np.radians(lat))
        dy, dx = yy - r0, xx - c0
        d = np.hypot(dy, dx)
        az = (np.degrees(np.arctan2(dx, -dy)) + conv + 360) % 360
        m = (d >= RMIN) & (d < RMAX)
        if m.sum() < 2000:
            continue
        idx = np.flatnonzero(m)
        b = (az.ravel()[idx]).astype(int) % NB
        band = ((d.ravel()[idx] - RMIN) // BAND).astype(int)
        near = np.flatnonzero(d.ravel() < 75)
        geo[code] = (idx, b * 4 + band, near, lat, lon)
    return geo


def run_day(day_s: str, om: bool = False) -> None:
    day = datetime.fromisoformat(day_s).replace(tzinfo=UTC)
    target = DAG / f"{day_s}.json"
    if target.exists() and not om:
        return
    t0 = time.time()
    times = [day + k * radar.STEP for k in range(288)]
    paths = [RADAR / f"{t:%Y/%m/%d}" / f"{t:%Y%m%d%H%M}.tif" for t in times]
    grid = next(radar.read_rain(p)[1] for p in paths if p.exists())
    geo = geometry(grid)
    gh = gauge_hours(day, grid)
    # kända klotterrutor (kandidater på träningsdagarna och vindkraftsrutor, utvidgade en ruta), så att
    # tillfälliga prickar (anaprop) kan skiljas från det fasta klottret
    km = np.load(OUT / "kartor.npz")
    known = binary_dilation(km["kandidat"] | km["vind"], iterations=1).ravel()
    spokes, dots = [], []
    for t, p in zip(times, paths):
        if not p.exists():
            continue
        rain, _ = radar.read_rain(p)
        cov = np.isfinite(rain)
        echo = cov & (np.nan_to_num(rain, nan=0.0) >= ECHO)
        dbz = dbz_of(rain)
        tex = np.abs(dbz - (uniform_filter(dbz, 3) * 9 - dbz) / 8)
        frac = uniform_filter(echo.astype(np.float32), 21)
        sharp = (echo & (tex >= 8)).ravel()
        dot = sharp & (frac < 0.03).ravel()
        dot_new = dot & ~known
        sharp_new = sharp & ~known
        end = t.replace(minute=0) + (timedelta(hours=1) if t.minute else timedelta(0))
        g = gh.get(int(end.timestamp()))
        dry = (cov & (g[0] >= 1) & (g[1] == 0)).ravel() if g is not None else None
        ef, cf = echo.ravel(), cov.ravel()
        for code, (idx, key, near, lat, lon) in geo.items():
            e = np.bincount(key, ef[idx], NB * 4).reshape(NB, 4)
            n = np.bincount(key, cf[idx], NB * 4).reshape(NB, 4)
            fb = np.where(n >= 3, e / np.maximum(n, 1), np.nan)
            tot = np.where(n.sum(1) >= 20, e.sum(1) / np.maximum(n.sum(1), 1), np.nan)
            if np.isfinite(tot).sum() > 200:
                side = np.stack([np.roll(tot, s) for s in (*range(3, 11), *range(-10, -2))])
                with np.errstate(all="ignore"):
                    med = np.nanmedian(side, 0)
                    hit = (tot >= 0.4) & ((fb >= 0.25).sum(1) >= 3) & (med <= 0.1)
                if hit.any():
                    saz, sel = sun(t, lat, lon)
                    for a in np.flatnonzero(hit):
                        spokes.append({"t": f"{t:%Y-%m-%dT%H:%M}", "radar": code, "az": int(a), "andel": round(float(tot[a]), 3),
                                       "sida": round(float(med[a]), 3), "sol_az": round(saz, 1), "sol_hojd": round(sel, 1)})
            nd = int(dot[near].sum())
            ne = int(ef[near].sum())
            rec = {"t": f"{t:%Y-%m-%dT%H:%M}", "radar": code, "eko": ne, "prickar": nd,
                   "prickar_nya": int(dot_new[near].sum()), "kantigt_nytt": int(sharp_new[near].sum())}
            if dry is not None:
                dn = dry[near]
                rec["torr_rutor"] = int(dn.sum())
                rec["torr_eko"] = int((ef[near] & dn).sum())
                rec["torr_prickar"] = int((dot[near] & dn).sum())
                rec["torr_prickar_nya"] = int((dot_new[near] & dn).sum())
                rec["torr_kantigt_nytt"] = int((sharp_new[near] & dn).sum())
            dots.append(rec)
    DAG.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"ekrar": spokes, "prickar": dots}))
    print(day_s, f"{time.time() - t0:.0f} s", "ekrar", len(spokes), flush=True)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cmd", choices=["dag", "sammanstall"])
    p.add_argument("--del", dest="part", default="0/1")
    p.add_argument("--dagar", nargs="*")
    p.add_argument("--om", action="store_true", help="räkna om dagar som redan finns")
    a = p.parse_args()
    allowed = {d for d, _ in days()}
    if a.cmd == "dag":
        i, n = map(int, a.part.split("/"))
        for d in a.dagar or sorted(allowed)[i::n]:
            assert d in allowed, d
            run_day(d, a.om or bool(a.dagar))
    else:
        from bild_sammanstall import main as sm  # noqa: PLC0415
        sm()


if __name__ == "__main__":
    main()
