"""Inventering av radarns artefakter i SMHI:s komposit (uppgift 1 natten 2026-11-06).

    uv run python experiments/analys/artefakter.py dag [--del 0/2]   räknar per dag, sparar under /data/analys/artefakter/dag/
    uv run python experiments/analys/artefakter.py karta              slår ihop dagarna till kartor.npz och tabeller

Bara tränings- och valideringsdagarna läses (aldrig delen test i dagar.json, inte heller mätarna för dem).

Per ruta och dag räknas (alla som summor och antal så att dagarna kan läggas ihop eller bootstrappas):

  nv     bilder med täckning
  ne     bilder med eko (R >= 0,1 mm/h), ne5 med R >= 0,5 mm/h
  sd,sd2 summa och kvadratsumma av dBZ där det är eko (medel och spridning över tiden)
  tex    summa |dBZ - medel av 3x3-grannarna| där det är eko (texturen; inget eko räknas som 0 dBZ)
  d5,n5  summa |dBZ(t) - dBZ(t-5 min)| där det är eko i någon av bilderna (tidsvariationen)
  flip   antal byten mellan eko och inget eko från en bild till nästa (blinkande eko)
  iso    eko där mindre än 3 % av rutorna inom 21x21 (42 km) har eko (isolerade prickar)
  Stillastående (var 15:e minut, där rörelsen över 15 min är minst 3 rutor, 6 km):
  nm     eko både nu och för 15 min sedan
  se,sl  summa |dBZ(t) - dBZ(t-15)| på platsen (Euler) och längs rörelsen (Lagrange)
  still  antal där Euler-ändringen är högst 1 dB och Lagrange minst 3 dB större
  Mätarna (p7, timsumma, timmen slutar vid tidsstämpeln):
  ndv,nde  bilder och ekobilder under timmar då minst en mätare inom 25 km finns och alla är torra (0 mm)
  nwv,nwe  samma under timmar med minst en våt mätare (>= 0,1 mm) inom 25 km
  Lyftet (rörelsen som vind mot höjdmodellens lutning, w = v . grad h i m per 5 min):
  nup,neu  bilder med w > 5 m och ekobilder bland dem; ndn,ned samma med w < -5 m
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
from scipy.ndimage import uniform_filter
from scipy.signal import fftconvolve

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from knep.analys import radar  # noqa: E402

OUT = Path("/data/analys/artefakter")
RADAR = Path("/data/radar")
HOJD = Path("/data/projektion/hojd_2km.npz")
GAUGES = Path("/data/bortfall/matare/p7.npz")
ECHO, ECHO5 = 0.1, 0.5


def days() -> list[tuple[str, str]]:
    """(dag, del) för träning och validering. Testdelen tas aldrig med."""
    val = [d["day"] for d in json.loads((ROOT / "experiments/sverige/dagar.json").read_text()) if d["part"] == "validering"]
    tr = [d["day"] for d in json.loads((ROOT / "experiments/projektion/traning.json").read_text())]
    test = {d["day"] for d in json.loads((ROOT / "experiments/sverige/dagar.json").read_text()) if d["part"] == "test"}
    out = [(d, "traning") for d in tr] + [(d, "validering") for d in val]
    assert not test & {d for d, _ in out}
    return sorted(out)


def dbz_of(rain: np.ndarray) -> np.ndarray:
    """dBZ ur mm/h; inget eko och utanför täckning blir 0 dBZ."""
    r = np.nan_to_num(rain, nan=0.0)
    z = np.zeros_like(r)
    ok = r > 0
    z[ok] = 10 * np.log10(200.0 * r[ok] ** 1.5)
    return np.maximum(z, 0.0).astype(np.float32)


def grid_xy(grid: radar.Grid):
    """Mätarnas plats som rad och kolumn på radarns rutnät."""
    from pyproj import Transformer
    tr = Transformer.from_crs("EPSG:4326", grid.crs, always_xy=True)
    inv = ~grid.transform

    def to_rc(lat, lon):
        x, y = tr.transform(lon, lat)
        c, r = inv * (np.asarray(x), np.asarray(y))
        return np.asarray(r), np.asarray(c)
    return to_rc


def gauge_hours(day: datetime, grid: radar.Grid) -> dict[int, tuple[np.ndarray, np.ndarray]]:
    """Per timslut (epoksekunder): antal mätare och antal våta mätare inom 25 km av varje ruta."""
    z = np.load(GAUGES)
    t0, t1 = int(day.timestamp()), int((day + timedelta(days=1)).timestamp())
    keep = (z["time"] > t0) & (z["time"] <= t1)  # bara dagens timmar läses vidare
    lat, lon, tt, mm = z["lat"][keep], z["lon"][keep], z["time"][keep], z["mm"][keep]
    r, c = grid_xy(grid)(lat, lon)
    h, w = grid.shape
    rad = 12.5  # 25 km i rutor om 2 km
    yy, xx = np.mgrid[-13:14, -13:14]
    disk = ((yy ** 2 + xx ** 2) <= rad ** 2).astype(np.float32)
    out = {}
    for t in np.unique(tt):
        s = (tt == t) & np.isfinite(mm) & (r >= 0) & (r < h) & (c >= 0) & (c < w)
        allg, wet = np.zeros((h, w), np.float32), np.zeros((h, w), np.float32)
        ri, ci = r[s].astype(int), c[s].astype(int)
        np.add.at(allg, (ri, ci), 1)
        np.add.at(wet, (ri, ci), (mm[s] >= 0.1).astype(np.float32))
        n = np.rint(fftconvolve(allg, disk, mode="same"))
        nw = np.rint(fftconvolve(wet, disk, mode="same"))
        out[int(t)] = (n, nw)
    return out


def run_day(day_s: str) -> None:
    from knep.prognos.model import motion_field
    import cv2

    day = datetime.fromisoformat(day_s).replace(tzinfo=UTC)
    target = OUT / "dag" / f"{day_s}.npz"
    if target.exists():
        return
    t_start = time.time()
    times = [day + k * radar.STEP for k in range(288)]
    paths = [RADAR / f"{t:%Y/%m/%d}" / f"{t:%Y%m%d%H%M}.tif" for t in times]
    grid = None
    for p in paths:
        if p.exists():
            _, grid = radar.read_rain(p)
            break
    h, w = grid.shape
    hz = np.load(HOJD)["h"].astype(np.float32)
    dhdy, dhdx = np.gradient(hz)  # m per ruta
    gh = gauge_hours(day, grid)

    A = {k: np.zeros((h, w), np.float32) for k in
         "nv ne ne5 sd sd2 tex d5 n5 flip iso nm se sl still ndv nde nwv nwe nup neu ndn ned".split()}
    buf_rain: dict[int, np.ndarray] = {}
    prev_dbz, prev_echo = None, None
    hist_dbz: dict[int, np.ndarray] = {}
    motion = None
    mean_uv, n_uv, missing = np.zeros(2), 0, 0
    mx, my = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    sparse = {}
    for k, (t, p) in enumerate(zip(times, paths)):
        if not p.exists():
            missing += 1
            prev_dbz = prev_echo = None
            continue
        rain, _ = radar.read_rain(p)
        buf_rain[k] = rain
        for old in [j for j in buf_rain if j < k - 6]:
            del buf_rain[old]
        cov = np.isfinite(rain)
        r0 = np.nan_to_num(rain, nan=0.0)
        echo = cov & (r0 >= ECHO)
        dbz = dbz_of(rain)
        A["nv"] += cov
        A["ne"] += echo
        A["ne5"] += cov & (r0 >= ECHO5)
        A["sd"] += np.where(echo, dbz, 0)
        A["sd2"] += np.where(echo, dbz * dbz, 0)
        A["tex"] += np.where(echo, np.abs(dbz - (uniform_filter(dbz, 3) * 9 - dbz) / 8), 0)
        frac = uniform_filter(echo.astype(np.float32), 21)
        A["iso"] += echo & (frac < 0.03)
        if prev_dbz is not None:
            either = cov & (echo | prev_echo)
            A["d5"] += np.where(either, np.abs(dbz - prev_dbz), 0)
            A["n5"] += either
            A["flip"] += cov & (echo != prev_echo)
        prev_dbz, prev_echo = dbz, echo

        # rörelsen var 30:e minut ur bilderna t-30, t-15 och t (som kedjan)
        if k % 6 == 0 and all(j in buf_rain for j in (k - 6, k - 3, k)):
            obs = np.stack([buf_rain[k - 6], buf_rain[k - 3], buf_rain[k]])
            try:
                motion = motion_field(obs, gap=1, n=3, step=4).astype(np.float32) / 3.0  # rutor per 5 min
            except Exception as e:  # noqa: BLE001
                print(day_s, t, "rörelse", e, file=sys.stderr)
                motion = None
            if motion is not None:
                mean_uv += motion.reshape(2, -1).mean(1)
                n_uv += 1
                sparse[f"{t:%H%M}"] = motion[:, ::8, ::8].astype(np.float16)
        if motion is not None:
            wlift = motion[0] * dhdx + motion[1] * dhdy  # m per 5 min, positivt mot sluttningen
            up, dn = cov & (wlift > 5), cov & (wlift < -5)
            A["nup"] += up
            A["neu"] += up & echo
            A["ndn"] += dn
            A["ned"] += dn & echo
        if k % 3 == 0:
            hist_dbz[k] = (dbz, echo)
            hist_dbz.pop(k - 6, None)
            if motion is not None and (k - 3) in hist_dbz:
                d15, e15 = hist_dbz[k - 3]
                disp = 3 * motion
                moving = np.hypot(disp[0], disp[1]) >= 3
                adv = cv2.remap(d15, mx - disp[0], my - disp[1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
                m = cov & echo & e15 & moving
                E, L = np.abs(dbz - d15), np.abs(dbz - adv)
                A["nm"] += m
                A["se"] += np.where(m, E, 0)
                A["sl"] += np.where(m, L, 0)
                A["still"] += m & (E <= 1.0) & (L >= E + 3.0)
        # mätartimmen: tidsstämpeln är timmens slut, bilden t hör till timmen som slutar vid nästa hela timme
        end = t.replace(minute=0) + (timedelta(hours=1) if t.minute else timedelta(0))
        g = gh.get(int(end.timestamp()))
        if g is not None:
            n, nw = g
            dry = cov & (n >= 1) & (nw == 0)
            wet = cov & (nw >= 1)
            A["ndv"] += dry
            A["nde"] += dry & echo
            A["nwv"] += wet
            A["nwe"] += wet & echo
    target.parent.mkdir(parents=True, exist_ok=True)
    counts = {k: v.astype(np.uint16) for k, v in A.items() if k not in ("sd", "sd2", "tex", "d5", "se", "sl")}
    sums = {k: A[k].astype(np.float32) for k in ("sd", "sd2", "tex", "d5", "se", "sl")}
    np.savez_compressed(target.with_suffix(".tmp.npz"), **counts, **sums,
                        mean_uv=mean_uv / max(n_uv, 1), missing=missing, **{f"uv_{k}": v for k, v in sparse.items()})
    target.with_suffix(".tmp.npz").replace(target)
    print(day_s, f"{time.time() - t_start:.0f} s", "saknas", missing, "medelrörelse", np.round(mean_uv / max(n_uv, 1), 2), flush=True)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cmd", choices=["dag", "karta"])
    p.add_argument("--del", dest="part", default="0/1", help="i/n: var n:e dag med början i i")
    p.add_argument("--dagar", nargs="*")
    a = p.parse_args()
    if a.cmd == "dag":
        i, n = map(int, a.part.split("/"))
        ds = a.dagar or [d for d, _ in days()][i::n]
        allowed = {d for d, _ in days()}
        for d in ds:
            assert d in allowed, d
            run_day(d)
    else:
        from karta import main as karta_main  # noqa: PLC0415
        karta_main()


if __name__ == "__main__":
    main()
