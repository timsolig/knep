"""MEPS, MetCoOps vädermodell, som underlag för prognosen bortom de första timmarna.

Deterministiska körningar var 3:e timme på 2,5 km i en lambertprojektion (samma rutnät som SNOW,
se compare.MEPS), tillgängliga cirka 2 h 20 min efter körtiden på thredds.met.no. Nederbörden
är ackumulerad från körtiden; här blir den timsummor i mm, alltså medelintensitet i mm/h.

Bara ett utsnitt som täcker radarns rutnät hämtas, via OPeNDAP, och det räknas om till radarns
rutnät bilinjärt.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import requests
from rasterio.transform import Affine, array_bounds
from rasterio.warp import Resampling, reproject

from . import compare
from .radar import Grid

log = logging.getLogger("knep")

LATEST = "https://thredds.met.no/thredds/dodsC/mepslatest/meps_det_2_5km_{t:%Y%m%dT%H}Z.ncml"
# arkivet har bytt namn: meps_det_2_5km till 2023, meps_det_sfc från 2024 (2019 och tidigare
# ligger på ett annat, mindre rutnät och används inte)
ARCHIVE = ["https://thredds.met.no/thredds/dodsC/meps25epsarchive/{t:%Y/%m/%d}/meps_det_2_5km_{t:%Y%m%dT%H}Z.nc",
           "https://thredds.met.no/thredds/dodsC/meps25epsarchive/{t:%Y/%m/%d}/meps_det_sfc_{t:%Y%m%dT%H}Z.ncml"]
CATALOG = "https://thredds.met.no/thredds/catalog/mepslatest/catalog.xml"
LAG = timedelta(hours=2, minutes=30)   # från körtid till att körningen finns, med marginal
LEADS = 11                              # timmar som hämtas per körning
HOUR = timedelta(hours=1)


@dataclass
class Run:
    """En körnings timsummor på ett utsnitt av MEPS rutnät. hourly[k] gäller timmen (run + k, run + k + 1]."""

    run: datetime
    hourly: np.ndarray      # (timmar, rader, kolumner) mm per timme, rad 0 längst i söder som i filen
    rows: tuple[int, int]
    cols: tuple[int, int]

    def grid(self) -> Grid:
        """Utsnittets rutnät med norr uppåt (som radarns)."""
        r0, r1 = self.rows
        c0, _ = self.cols
        res = compare.MEPS_RES
        west = compare.MEPS_X0 - res / 2 + c0 * res
        north = compare.MEPS_Y0 + (r1 - 1) * res + res / 2
        return Grid(compare.MEPS_CRS, Affine(res, 0, west, 0, -res, north), (r1 - r0, self.cols[1] - c0))

    def on(self, target: Grid) -> np.ndarray:
        """Timsummorna på målrutnätet, (timmar, H, W) i mm/h; NaN utanför utsnittet."""
        src = self.grid()
        out = np.full((len(self.hourly),) + tuple(target.shape), np.nan, np.float32)
        for k, f in enumerate(self.hourly):
            reproject(f[::-1].astype(np.float32), out[k], src_transform=src.transform, src_crs=src.crs, src_nodata=np.nan,
                      dst_transform=target.transform, dst_crs=target.crs, dst_nodata=np.nan, resampling=Resampling.bilinear)
        return out

    def hour_ending(self, t: datetime) -> int | None:
        """Index för timmen som innehåller (t - 5 min, t], eller None om körningen inte räcker."""
        k = int((t - self.run - timedelta(seconds=1)) // HOUR)
        return k if 0 <= k < len(self.hourly) else None

    def save(self, path: Path) -> None:
        tmp = path.with_suffix(".tmp.npz")
        np.savez_compressed(tmp, hourly=self.hourly.astype(np.float16), rows=self.rows, cols=self.cols,
                            run=self.run.strftime("%Y%m%dT%H"))
        tmp.replace(path)

    @classmethod
    def load(cls, path: Path) -> "Run":
        d = np.load(path)
        run = datetime.strptime(str(d["run"]), "%Y%m%dT%H").replace(tzinfo=UTC)
        return cls(run, d["hourly"].astype(np.float32), tuple(int(x) for x in d["rows"]), tuple(int(x) for x in d["cols"]))


def box(grid: Grid, margin: int = 3) -> tuple[tuple[int, int], tuple[int, int]]:
    """Rader och kolumner i MEPS rutnät (rad 0 i söder) som täcker målrutnätet."""
    from pyproj import Transformer

    west, south, east, north = array_bounds(*grid.shape, grid.transform)
    to = Transformer.from_crs(grid.crs, compare.MEPS_CRS, always_xy=True)
    xs, ys = np.meshgrid(np.linspace(west, east, 60), np.linspace(south, north, 60))
    mx, my = to.transform(xs, ys)
    col = lambda x: int(np.floor((x - compare.MEPS_X0) / compare.MEPS_RES))
    row = lambda y: int(np.floor((y - compare.MEPS_Y0) / compare.MEPS_RES))
    h, w = compare.MEPS_SHAPE
    return ((max(row(my.min()) - margin, 0), min(row(my.max()) + margin + 1, h)),
            (max(col(mx.min()) - margin, 0), min(col(mx.max()) + margin + 1, w)))


def fetch(session: requests.Session, run: datetime, rows, cols, archive: bool = False, leads: int = LEADS) -> Run:
    q = f"precipitation_amount_acc[0:1:{leads}][0:1:0][{rows[0]}:1:{rows[1] - 1}][{cols[0]}:1:{cols[1] - 1}]"
    for url in ([u.format(t=run) for u in ARCHIVE] if archive else [LATEST.format(t=run)]):
        r = session.get(url + ".dods?" + q, timeout=300)
        if r.status_code != 404:
            break
    r.raise_for_status()
    (acc,) = compare.dods_arrays(r.content, [">f4"])
    acc = acc.reshape(leads + 1, rows[1] - rows[0], cols[1] - cols[0])
    acc[~(acc < 1e30)] = np.nan
    return Run(run, np.clip(np.diff(acc, axis=0), 0, None).astype(np.float32), tuple(rows), tuple(cols))


def latest_run(session: requests.Session) -> datetime:
    r = session.get(CATALOG, timeout=30)
    r.raise_for_status()
    stamps = re.findall(r'name="meps_det_2_5km_(\d{8}T\d{2})Z\.ncml"', r.text)
    if not stamps:
        raise ValueError("inga MEPS-körningar i katalogen")
    return datetime.strptime(max(stamps), "%Y%m%dT%H").replace(tzinfo=UTC)


def available(now: datetime, cycle: int = 3) -> datetime:
    """Senaste körningen som rimligen finns vid now (för verifieringen på arkivet), med en
    körning var cycle:e timme."""
    t = now - LAG
    return t.replace(hour=t.hour - t.hour % cycle, minute=0, second=0, microsecond=0)
