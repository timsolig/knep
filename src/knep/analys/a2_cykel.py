"""A2T i cykeln (valet --a2 i cli.py, av som standard): A1 rättad mot regnmätarna, timme och kvart bakåt.

1. A1:s timsumma och fyra kvartssummor (mm per period) sparas en gång per timme i tillståndet
   (a1t_ÅÅÅÅMMDDTTMM.npz, tiden är timmens slut), när A1:s tolv intervall för timmen finns, och
   ligger kvar i BEHALL timmar. Ur dem byggs A2T:s fönster på sex timmar utan att A1 räknas om.
2. Mätarna tas ur gauges.json (gauges.py, timme "60" och kvart "15", 12 h) eller, för historiska
   körningar, ur arkivfilerna p7.npz och p14.npz (las_arkiv). Inga egna anrop till SMHI.
3. Mätarna kommer ungefär en timme efter radarn. Varje cykel ser på timmarna de senaste RAKNA
   timmarna som har A1 och minst en timmätare, och räknar A2T (a2.A2T.timme) för en timme som inte
   är räknad, eller igen när antalet mätarvärden för timmen och dess fönster har ökat med minst
   OMRAKNA_ANDEL eller när förra räkningen är minst OMRAKNA_MIN minuter gammal och något har kommit.
   Antalet står i filnamnet (h20261107T1000_n512.png), så att sidan inte visar en gammal bild ur
   webbläsarens cache när timmen räknas om.
4. Kartorna ritas med render.Renderer.periods till a2/ och listas som history, under levels.a2 i
   manifestet. En timme utan mätare ritas inte.

Mätarna kontrolleras grovt som i analysens domare: värden under 0 eller över MAX_MM tas bort.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

from . import a2

log = logging.getLogger("knep.analys.a2")

DIR = "a2"  # som render.A2_DIR
TIMME = timedelta(hours=1)
KVART = timedelta(minutes=15)
INTERVALL = timedelta(minutes=5)
RAKNA = 3            # timmar bakåt som räknas (om), mätarna kommer 1 till 2,5 h efter timmen
BEHALL = RAKNA + a2.TIMME["WIN"] + 1   # timmar med A1:s summor i tillståndet
OMRAKNA_ANDEL = 0.1  # räkna om när antalet mätarvärden ökat med minst 10 %
OMRAKNA_MIN = 30     # eller när förra räkningen är minst 30 min gammal och något har kommit
MAX_MM = {"60": 100.0, "15": 60.0}  # som MAX_MM i experiments/analys/domare.py
ARKIV = {"60": "p7.npz", "15": "p14.npz"}


def _iso(t: datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _a1t_path(state_dir: Path, end: datetime) -> Path:
    return state_dir / f"a1t_{end:%Y%m%dT%H%M}.npz"


def summor(intervall: list[np.ndarray | None]) -> tuple[np.ndarray, np.ndarray]:
    """Timsumma (H, W) och fyra kvartssummor (4, H, W) i mm ur tolv intervall i mm/h (None saknas).

    Som sums i experiments/analys/domare.py: en period räknas om minst två tredjedelar av
    intervallen har data, och medlet av de som finns används."""
    shape = next(f for f in intervall if f is not None).shape
    x = np.stack([np.full(shape, np.nan, np.float32) if f is None else np.asarray(f, np.float32)
                  for f in intervall])

    def agg(block):
        n = len(block)
        fin = np.isfinite(block)
        ok = fin.sum(axis=0)
        mean = np.where(fin, block, 0.0).sum(axis=0) / np.maximum(ok, 1)
        return (np.where(ok * 3 >= 2 * n, mean, np.nan) * (n * 5 / 60.0)).astype(np.float32)

    return agg(x), np.stack([agg(x[3 * i:3 * i + 3]) for i in range(4)])


def spara_a1(state_dir: Path, frames: list[tuple[datetime, np.ndarray]], now: datetime) -> list[datetime]:
    """Spara A1:s summor för varje hel timme bland intervallen (a1.update) som inte redan är sparad.

    En timme sparas när intervallet som slutar på timmen finns och minst åtta av tolv finns; gamla
    filer (äldre än BEHALL timmar före now, eller efter now) tas bort. Returnerar de nya timmarna."""
    state_dir.mkdir(parents=True, exist_ok=True)
    by_t = {t: f for t, f in frames}
    nya = []
    for end in sorted({t.replace(minute=0, second=0, microsecond=0) for t in by_t}):
        if end not in by_t or end < now - timedelta(hours=BEHALL) or end > now:
            continue
        p = _a1t_path(state_dir, end)
        if p.exists():
            continue
        iv = [by_t.get(end - TIMME + (k + 1) * INTERVALL) for k in range(12)]
        if sum(f is not None for f in iv) < 8:
            continue
        tm, kv = summor(iv)
        tmp = p.with_name(p.stem + ".tmp.npz")
        np.savez_compressed(tmp, timme=tm.astype(np.float16), kvartar=kv.astype(np.float16))
        tmp.replace(p)
        nya.append(end)
    for p in state_dir.glob("a1t_*.npz"):
        if p.name.endswith(".tmp.npz"):
            continue
        t = datetime.strptime(p.stem[4:], "%Y%m%dT%H%M").replace(tzinfo=UTC)
        if t < now - timedelta(hours=BEHALL) or t > now:
            p.unlink()
    return nya


def las_a1(state_dir: Path, end: datetime) -> tuple[np.ndarray, np.ndarray] | None:
    """A1:s timsumma och kvartssummor (float32, mm) för timmen som slutar end, eller None."""
    try:
        z = np.load(_a1t_path(state_dir, end))
        return z["timme"].astype(np.float32), z["kvartar"].astype(np.float32)
    except (OSError, KeyError, ValueError):
        return None


def las_gauges_json(out: Path) -> dict | None:
    """Mätarna som gauges.py har sparat (stationer och värden per tid för "60" och "15")."""
    try:
        return json.loads((out / "gauges.json").read_text())
    except (FileNotFoundError, ValueError):
        return None


def las_arkiv(katalog: Path, now: datetime, hours: float = 12.0) -> dict:
    """Testkroken för historiska körningar: arkivfilerna p7.npz och p14.npz (station, lat, lon, time i
    Unix-sekunder för periodens slut, mm) i samma form som gauges.json, för hours timmar till och med now."""
    doc = {"stations": {}}
    t1 = int(now.timestamp())
    t0 = t1 - int(hours * 3600)
    for res, name in ARKIV.items():
        z = np.load(katalog / name)
        tt = z["time"]
        keep = (tt > t0) & (tt <= t1)
        series: dict[str, dict] = {}
        for st, lat, lon, t, mm in zip(z["station"][keep], z["lat"][keep], z["lon"][keep], tt[keep], z["mm"][keep]):
            sid = str(int(st)) if np.issubdtype(type(st), np.number) else str(st)
            doc["stations"].setdefault(sid, [float(lat), float(lon), ""])
            series.setdefault(_iso(datetime.fromtimestamp(int(t), UTC)), {}).setdefault(sid, float(mm))
        doc[res] = series
    return doc


class Platser:
    """Stationernas rad och kolumn på rutnätet (som _to_rc i analysens domare), räknade en gång."""

    def __init__(self, grid, stations: dict):
        from pyproj import Transformer
        ids = list(stations)
        h, w = grid.shape
        self.rc = {}
        if not ids:
            return
        lat = np.array([stations[s][0] for s in ids], float)
        lon = np.array([stations[s][1] for s in ids], float)
        tr = Transformer.from_crs("EPSG:4326", grid.crs, always_xy=True)
        x, y = tr.transform(lon, lat)
        c, r = (~grid.transform) * (np.asarray(x), np.asarray(y))
        r, c = np.floor(np.asarray(r)).astype(int), np.floor(np.asarray(c)).astype(int)
        for s, ri, ci in zip(ids, r, c):
            if 0 <= ri < h and 0 <= ci < w:
                self.rc[s] = (int(ri), int(ci))

    def matare(self, doc: dict, res: str, end: datetime) -> a2.Matare:
        """Periodens mätare (värdet vid end gäller perioden som slutar end) inom rutnätet och gränserna."""
        vals = (doc.get(res) or {}).get(_iso(end)) or {}
        rad, kol, mm = [], [], []
        for sid in sorted(vals):
            v = vals[sid]
            if sid not in self.rc or v is None or not np.isfinite(v) or v < 0 or v > MAX_MM[res]:
                continue
            rad.append(self.rc[sid][0])
            kol.append(self.rc[sid][1])
            mm.append(v)
        return a2.Matare(np.array(rad, int), np.array(kol, int), np.array(mm, float))


def indata(state_dir: Path, doc: dict, platser: Platser, end: datetime):
    """Allt A2T.timme behöver för timmen som slutar end: (a1_timme, a1_kvartar, fönster, timmätare,
    kvartsmätare), eller None om A1 saknas för timmen. Fönstrets timmar utan A1 får NaN (räknas inte)."""
    a1 = las_a1(state_dir, end)
    if a1 is None:
        return None
    a1h, a1q = a1
    delar = []
    for k in range(a2.TIMME["WIN"] - 1, -1, -1):  # äldst först
        e = end - k * TIMME
        m = platser.matare(doc, "60", e)
        f = a1h if k == 0 else (las_a1(state_dir, e) or (None, None))[0]
        delar.append((m, np.full(len(m), np.nan) if f is None else f[m.rad, m.kol].astype(float)))
    fon = a2.Matare(np.concatenate([m.rad for m, _ in delar]), np.concatenate([m.kol for m, _ in delar]),
                    np.concatenate([m.mm for m, _ in delar]), np.concatenate([a for _, a in delar]))
    tim = platser.matare(doc, "60", end)
    kvm = [platser.matare(doc, "15", end - TIMME + (i + 1) * KVART) for i in range(4)]
    return a1h, a1q, fon, tim, kvm


def _antal(fon, tim, kvm) -> int:
    return len(fon) + len(tim) + sum(len(m) for m in kvm)


def _ska_raknas(end: datetime, n: int, now_wall: float, d: Path) -> bool:
    """Om timmen ska räknas: ingen bild, eller fler mätarvärden än sist (se modulens docstring)."""
    gamla = sorted(d.glob(f"h{end:%Y%m%dT%H%M}_n*.png"))
    if not gamla:
        return True
    n_old = max(int(p.stem.split("_n")[1]) for p in gamla)
    if n <= n_old:
        return False
    alder_min = (now_wall - max(p.stat().st_mtime for p in gamla)) / 60.0
    return n >= n_old * (1 + OMRAKNA_ANDEL) or alder_min >= OMRAKNA_MIN


def rakna(state_dir: Path, out: Path, grid, now: datetime, doc: dict | None,
          modell: a2.A2T | None = None) -> list[tuple[datetime, np.ndarray, np.ndarray, str]]:
    """A2T för de senaste RAKNA timmarna som har A1 och timmätare och behöver räknas (om).

    Returnerar (timmens slut, timsumma (H, W), kvartssummor (4, H, W), märke) i mm per period."""
    res = []
    if not doc:
        return res
    platser = Platser(grid, doc.get("stations", {}))
    newest = now.replace(minute=0, second=0, microsecond=0)
    for k in range(RAKNA, -1, -1):
        end = newest - k * TIMME
        x = indata(state_dir, doc, platser, end)
        if x is None or not len(x[3]):
            continue  # ingen A1 eller ingen timmätare: inget visas för timmen
        n = _antal(*x[2:])
        if not _ska_raknas(end, n, time.time(), out / DIR):
            continue
        if modell is None:
            modell = a2.A2T.fran_grid(grid)
        t = time.monotonic()
        tm, kv = modell.timme(*x)
        res.append((end, tm, kv, f"n{n}"))
        log.info("A2T %s: %d timmätare, %d i fönstret, %d kvartsvärden på %.1f s", _iso(end), len(x[3]),
                 len(x[2]), sum(len(m) for m in x[4]), time.monotonic() - t)
    return res


def kor(state_dir: Path, out: Path, rend, a1_frames: list[tuple[datetime, np.ndarray]], now: datetime,
        hours: float, doc: dict | None, modell: a2.A2T | None = None) -> dict:
    """En cykel: spara A1:s timmar, räkna A2T för de timmar som behöver det och rita dem till a2/.

    Returnerar listan för levels.a2 (samma form som Renderer.history)."""
    start = time.monotonic()
    spara_a1(state_dir, a1_frames, now)
    items = []
    for end, tm, kv, tag in rakna(state_dir, out, rend.grid, now, doc, modell):
        items.append((end, 60, tm, tag))  # mm per timme är mm/h
        items += [(end - TIMME + (i + 1) * KVART, 15, kv[i] * 4.0, tag) for i in range(4)]
    res = rend.periods(out, items, now, hours, directory=DIR)
    log.info("A2: %d timmar räknade, %d bilder på %.1f s", len(items) // 5,
             len(res["frames60"]) + len(res["frames15"]), time.monotonic() - start)
    return res
