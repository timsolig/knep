"""Molnmasken från MSG (SEVIRI, EUMETSAT:s EO:EUM:DAT:MSG:CLM, var 15:e minut sedan 2004) på SMHI:s rutnät.

    uv run --with eccodes python experiments/kallor/satellit.py hamta 2024-07-28 [fler dagar]
    uv run --with eccodes python experiments/kallor/satellit.py hamta --alla     analysens och bortfallens dagar

Varje dag sparas som /data/kallor/msgclm/<dag>.npz med `tid` (sekunder sedan 1970, bildens start) och
`kod` (antal, 887, 471) uint8 på SMHI:s 2 km-rutnät (EPSG:3006): 0 klart över vatten, 1 klart över land,
2 moln, 3 saknas. Rutnätet tas närmaste-granne ur SEVIRI:s geostationära vy (cirka 4 till 6 km vid
Sverige). Orienteringen är kontrollerad mot land och hav på en klar dag (se index_for). Norr om cirka 66 N
beräknas ingen molnmask (för snett från satelliten), där är koden 3.

I realtid finns bilden från kvarten som börjar s cirka 20 minuter senare (skanningen tar 12 minuter,
sedan bearbetningen); `senaste(dag, t)` ger därför den senaste bilden som börjar senast t − FORDROJNING.
Nyckeln läses ur ~/.config/eumetsat/credentials (rad 1 nyckeln, rad 2 hemligheten) och skrivs aldrig ut.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
import urllib.parse
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

UT = Path("/data/kallor/msgclm")
FORDROJNING = timedelta(minutes=20)
SAMLING = "EO:EUM:DAT:MSG:CLM"
API = "https://api.eumetsat.int"
# SMHI:s kompositrutnät (samma som radarbilderna och fallen i experiments/bortfall)
TRANSFORM = (2014.9581656050955, 0.0, 126648.404, 0.0, -2014.9581657271704, 7771252.876)
FORM = (887, 471)
KLART = (0, 1)
MOLN = 2


def rutnat_lonlat():
    from pyproj import Transformer

    h, w = FORM
    jj, ii = np.mgrid[0:h, 0:w]
    a, b, c, d, e, f = TRANSFORM
    x, y = a * (ii + 0.5) + b * (jj + 0.5) + c, d * (ii + 0.5) + e * (jj + 0.5) + f
    return Transformer.from_crs(3006, 4326, always_xy=True).transform(x, y)


def index_for(nr: float, dx: int, dy: int, xp: float, yp: float, lon0: float = 0.0):
    """(rad, kolumn) i SEVIRI-bilden för varje ruta i SMHI:s rutnät. GRIB-värdena går med raden från söder
    mot norr (jScansPositively) och kolumnen från öster mot väster (iScansNegatively). Kontrollerat på
    värmeböljan 2018-07-26 12:00: Vänern, Vättern, Småland, Uppland, Dalarna och Jylland klart land,
    Hanöbukten, Östersjön, Bottenhavet och Nordsjön klart hav."""
    from pyproj import Proj

    a, b = 6378169.0, 6356583.8
    dist = nr / 1e6 * a
    h = dist - a
    ax, ay = 2 * np.arcsin(a / dist) / dx, 2 * np.arcsin(a / dist) / dy
    p = Proj(proj="geos", h=h, a=a, b=b, lon_0=lon0, sweep="y")
    lon, lat = rutnat_lonlat()
    x, y = p(lon, lat)
    col = np.round(xp - x / (h * ax)).astype(np.int32)
    row = np.round(yp + y / (h * ay)).astype(np.int32)
    return row, col


def las_grib(data: bytes):
    import tempfile

    import eccodes

    with tempfile.TemporaryFile() as fh:
        fh.write(data)
        fh.seek(0)
        g = eccodes.codes_grib_new_from_file(fh)
    try:
        k = {n: eccodes.codes_get(g, n) for n in ("Nx", "Ny", "dx", "dy", "XpInGridLengths", "YpInGridLengths", "Nr")}
        try:
            k["lon0"] = float(eccodes.codes_get(g, "longitudeOfSubSatellitePointInDegrees"))
        except Exception:  # noqa: BLE001
            k["lon0"] = 0.0
        v = eccodes.codes_get_values(g).reshape(k["Ny"], k["Nx"])
    finally:
        eccodes.codes_release(g)
    return v, k


def till_rutnat(v: np.ndarray, row: np.ndarray, col: np.ndarray) -> np.ndarray:
    ok = (row >= 0) & (row < v.shape[0]) & (col >= 0) & (col < v.shape[1])
    out = np.full(FORM, 3, np.uint8)
    out[ok] = np.nan_to_num(v[row[ok], col[ok]], nan=3).astype(np.uint8)
    return out


def _token(session) -> str:
    rad = (Path.home() / ".config/eumetsat/credentials").read_text().splitlines()
    r = session.post(f"{API}/token", data={"grant_type": "client_credentials"}, auth=(rad[0].strip(), rad[1].strip()), timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def hamta_dag(dag: str, session=None) -> Path:
    import requests

    session = session or requests.Session()
    ut = UT / f"{dag}.npz"
    if ut.exists():
        return ut
    UT.mkdir(parents=True, exist_ok=True)
    tok, t_tok = _token(session), time.monotonic()
    d0 = datetime.fromisoformat(dag).replace(tzinfo=UTC)
    q = {"format": "json", "pi": SAMLING, "c": 200, "dtstart": f"{(d0 - timedelta(minutes=30)):%Y-%m-%dT%H:%M:%SZ}",
         "dtend": f"{(d0 + timedelta(days=1)):%Y-%m-%dT%H:%M:%SZ}"}
    feats = session.get(f"{API}/data/search-products/1.0.0/os", params=q, headers={"Authorization": f"Bearer {tok}"},
                        timeout=60).json().get("features", [])
    tider, koder, idx = [], [], None
    for ft in sorted(feats, key=lambda f: f["properties"]["date"]):
        if time.monotonic() - t_tok > 1800:
            tok, t_tok = _token(session), time.monotonic()
        start = datetime.fromisoformat(ft["properties"]["date"].split("/")[0].replace("Z", "+00:00"))
        url = (f"{API}/data/download/1.0.0/collections/{urllib.parse.quote(SAMLING, safe='')}/products/"
               f"{urllib.parse.quote(ft['id'], safe='')}")
        for forsok in range(4):
            try:
                r = session.get(url, headers={"Authorization": f"Bearer {tok}"}, timeout=120)
                if r.status_code == 200:
                    break
            except requests.RequestException:
                pass
            time.sleep(5 * 2 ** forsok)
        else:
            print(f"{dag} {start:%H:%M}: kunde inte hämtas", flush=True)
            continue
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            grb = [n for n in z.namelist() if n.endswith(".grb")]
            v, k = las_grib(z.read(grb[0]))
        if idx is None:
            idx = index_for(k["Nr"], k["dx"], k["dy"], k["XpInGridLengths"], k["YpInGridLengths"], k["lon0"])
        tider.append(start.timestamp())
        koder.append(till_rutnat(v, *idx))
    np.savez_compressed(ut, tid=np.array(tider, np.float64), kod=np.array(koder, np.uint8))
    print(f"{dag}: {len(tider)} bilder", flush=True)
    return ut


class Molnmask:
    """Läser en dags molnmask och ger den senaste som fanns i realtid vid t."""

    def __init__(self, dag: str):
        p = UT / f"{dag}.npz"
        z = np.load(p) if p.exists() else None
        self.tid = z["tid"] if z is not None else np.zeros(0)
        self.kod = z["kod"] if z is not None else np.zeros((0,) + FORM, np.uint8)

    def senaste(self, t: datetime, n: int = 1) -> np.ndarray | None:
        """(n, 887, 471) de n senaste bilderna som fanns vid t (start <= t − FORDROJNING), eller None."""
        i = int(np.searchsorted(self.tid, (t - FORDROJNING).timestamp(), side="right"))
        if i < n or (t - FORDROJNING).timestamp() - self.tid[i - 1] > 3600:
            return None
        return self.kod[i - n:i]

    def klart(self, t: datetime, n: int = 1) -> np.ndarray:
        """True där alla de n senaste bilderna säger klart; False där det saknas bild."""
        k = self.senaste(t, n)
        return np.zeros(FORM, bool) if k is None else np.isin(k, KLART).all(axis=0)

    def moln(self, t: datetime) -> np.ndarray:
        """True där den senaste bilden säger moln eller saknas (då hindrar masken inget)."""
        k = self.senaste(t, 1)
        return np.ones(FORM, bool) if k is None else (k[0] == MOLN) | (k[0] == 3)


def alla_dagar() -> list[str]:
    here = Path(__file__).resolve().parents[1]
    dj = json.loads((here / "sverige/dagar.json").read_text())
    dagar = {d["day"] for d in dj if d["part"] == "validering"}   # aldrig testdelen
    dagar |= {d["day"] for d in json.loads((here / "projektion/traning.json").read_text())}
    for del_ in ("traning", "validering"):
        for p in Path(f"/data/bortfall/fall/{del_}").glob("*.npz"):
            dagar.add(f"{p.name[:4]}-{p.name[4:6]}-{p.name[6:8]}")
    test = {d["day"] for d in dj if d["part"] == "test"}
    return sorted(dagar - test)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cmd", choices=["hamta"])
    p.add_argument("dagar", nargs="*")
    p.add_argument("--alla", action="store_true")
    a = p.parse_args()
    import requests

    s = requests.Session()
    for d in (alla_dagar() if a.alla else a.dagar):
        try:
            hamta_dag(d, s)
        except Exception as e:  # noqa: BLE001
            print(f"{d}: fel {e}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
