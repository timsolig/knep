"""A1: nederbörden per 5 min, kvart och timme med bilderna interpolerade längs rörelsen.

SMHI:s komposit är ögonblicksbilder var 5:e minut. A0 (analysen som den är) låter varje bild gälla
de fem minuterna före den, så en cell som flyttar sig 10 km på 5 min blir ett pärlband av fläckar i
en kvarts- eller timsumma. A1 fyller i tiden mellan två bilder: fältet vid tiden τ (0..1 av
intervallet) är den första bilden flyttad framåt τ steg och den andra flyttad bakåt 1 − τ steg längs
rörelsefältet, viktade linjärt i tiden (samma idé som pysteps temporal interpolation). Medlet över
SUB tider per intervall ger intervallets medelintensitet, och kvart och timme är medel av intervallen,
så alla tre upplösningarna stämmer med varandra.

Där en av bilderna saknar data (utanför täckningen, eller flyttad ut ur rutnätet) används bara den
andra; där ingen har data blir A1 NaN, som A0.

Rörelsefältet är kedjans (knep.prognos, pixlar per 5 min) i samma cykel. Intervallen räknas en gång,
när båda bilderna finns, och sparas i tillståndet (a1_ÅÅÅÅMMDDTTMM.npz), så att en hel timme finns
även när en cykel bara ser de senaste tolv bilderna.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

from ..prognos import advect
from . import radar

log = logging.getLogger("knep.analys.a1")

SUB = 5  # tider per 5-minutersintervall, en per minut


def interval_mean(f0: np.ndarray, f1: np.ndarray, motion: np.ndarray, sub: int = SUB) -> np.ndarray:
    """Medelintensiteten under intervallet från bilden f0 till bilden f1, i mm/h.

    motion: (2, H, W) i pixlar per intervall. NaN i en bild räknas som att den bilden inte vet.
    """
    tau = (np.arange(sub, dtype=float) + 0.5) / sub
    v0, v1 = np.isfinite(f0), np.isfinite(f1)
    a, b = np.where(v0, f0, 0.0).astype(np.float32), np.where(v1, f1, 0.0).astype(np.float32)
    fa, ma = advect.extrapolate([a, v0.astype(np.float32)], motion, list(tau), outval=0.0)
    # bakåt från f1: tiderna 1 − τ i stigande ordning, och sedan tillbaka i τ:s ordning
    fb, mb = advect.extrapolate([b, v1.astype(np.float32)], -motion, list(1.0 - tau[::-1]), outval=0.0)
    fb, mb = fb[::-1], mb[::-1]
    w0 = (1.0 - tau)[:, None, None] * ma
    w1 = tau[:, None, None] * mb
    w = w0 + w1
    with np.errstate(invalid="ignore", divide="ignore"):
        f = np.where(w > 1e-6, (w0 * fa + w1 * fb) / w, np.nan)
    ok = np.isfinite(f)
    n = ok.sum(axis=0)
    out = np.where(n > 0, np.where(ok, f, 0.0).sum(axis=0) / np.maximum(n, 1), np.nan)
    out = np.where(v0 | v1, out, np.nan)  # utanför täckningen i båda bilderna: NaN, som A0
    return np.maximum(out, 0.0).astype(np.float32)


def _path(state_dir: Path, t: datetime) -> Path:
    return state_dir / f"a1_{t:%Y%m%dT%H%M}.npz"


def update(state_dir: Path, times: list[datetime], rain: np.ndarray, motion: np.ndarray | None,
           keep_hours: float = 1.25) -> list[tuple[datetime, np.ndarray]]:
    """Räkna de intervall som saknas bland analyserna (times, rain) och returnera alla sparade.

    Ett intervall räknas bara mellan två bilder som ligger 5 min isär. Intervall äldre än
    keep_hours före den senaste bilden tas bort. Returnerar (intervallets slut, fält), äldst först.
    """
    state_dir.mkdir(parents=True, exist_ok=True)
    if motion is not None:
        for k in range(1, len(times)):
            t0, t1 = times[k - 1], times[k]
            p = _path(state_dir, t1)
            if t1 - t0 != radar.STEP or p.exists():
                continue
            f = interval_mean(rain[k - 1], rain[k], motion)
            tmp = p.with_name(p.stem + ".tmp.npz")
            np.savez_compressed(tmp, rain=f.astype(np.float16))
            tmp.replace(p)
    newest = max(times) if times else None
    out = []
    for p in sorted(state_dir.glob("a1_*.npz")):
        if p.name.endswith(".tmp.npz"):
            continue
        t = datetime.strptime(p.stem[3:], "%Y%m%dT%H%M").replace(tzinfo=UTC)
        if newest is not None and (t < newest - timedelta(hours=keep_hours) or t > newest):
            p.unlink()
            continue
        try:
            out.append((t, np.load(p)["rain"].astype(np.float32)))
        except (OSError, KeyError, ValueError) as e:
            log.warning("kunde inte läsa %s: %s", p.name, e)
            p.unlink(missing_ok=True)
    return out
