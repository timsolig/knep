"""Tidigare utgåvor: prognosernas timsummor sparas varje timme, så att sidan kan jämföra dem med radarn.

Sidan visar senaste utgåvan var 5:e minut och tidigare utgåvor per timme, som SNOW. Därför sparas
bara timbilderna: Tim-KNEP:s timsummor (ritas här ur 5-minutersrutorna) och MET Norges och SNOW:s
från samma cykel. En utgåva sparas första cykeln i varje timme, normalt analysen hh:00, i
runs/<utgåvans tid>/ med en run.json, och tas bort efter HOURS timmar. Facit, radarns timsummor,
finns i hist/ (render.Renderer.history).

Bilderna är ungefär 150 kB per utgåva, så tolv timmar blir under 2 MB.
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

from . import render

DIR = "runs"
HOURS = 12
WITHIN = timedelta(minutes=15)  # en utgåva sparas bara om cykeln ligger så här nära heltimmen


def _iso(t: datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def due(out: Path, t0: datetime) -> bool:
    """Ska analysen t0 sparas som utgåva: första cykeln i timmen, inom WITHIN efter heltimmen."""
    hour = t0.replace(minute=0, second=0, microsecond=0)
    if t0 - hour > WITHIN:
        return False
    return not any((out / DIR).glob(f"{hour:%Y%m%dT%H}*/run.json"))


def archive(out: Path, rend: render.Renderer, t0: datetime, frames: list[tuple], compare: dict | None) -> dict:
    """Spara utgåvan t0: Tim-KNEP:s timmar ur frames och jämförelsekällornas timbilder ur out.

    frames: (tid, sort, fält, ...) som till Renderer.write. Bara timmar som slutar efter t0 sparas.
    """
    name = f"{t0:%Y%m%dT%H%M}"
    d = out / DIR / name
    tmp = out / DIR / f".{name}.tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    models = {}
    ours = []
    for end, start, kind, field in render.aggregate([fr[:3] for fr in frames], 60):
        if end <= t0:
            continue
        fname = f"ours_{end:%H%M}.png"
        rend.png(field, tmp / fname)
        ours.append({"time": _iso(end), "start": _iso(start), "kind": kind, "file": f"{DIR}/{name}/{fname}"})
    models["ours"] = {"bounds": rend.bounds, "frames60": ours}
    for key, e in (compare or {}).items():
        if not isinstance(e, dict) or "frames60" not in e:
            continue
        lst = []
        for f in e["frames60"]:
            src = out / f["file"]
            if _parse(f["time"]) <= t0 or not src.exists():
                continue
            fname = f"{key}_{Path(f['file']).name}"
            shutil.copyfile(src, tmp / fname)
            lst.append({"time": f["time"], "start": f["start"], "file": f"{DIR}/{name}/{fname}"})
        models[key] = {"bounds": e["bounds"], "reference": e.get("reference", ""), "frames60": lst}
    run = {"issued": _iso(t0), "models": models}
    (tmp / "run.json").write_text(json.dumps(run))
    shutil.rmtree(d, ignore_errors=True)
    tmp.replace(d)
    return run


def listing(out: Path, now: datetime, hours: float = HOURS) -> list[dict]:
    """De sparade utgåvorna, nyast först; de som är äldre än hours tas bort."""
    root = out / DIR
    runs = []
    for p in sorted(root.glob("*/run.json")) if root.exists() else []:
        try:
            run = json.loads(p.read_text())
            issued = _parse(run["issued"])
        except (ValueError, KeyError, OSError):
            shutil.rmtree(p.parent, ignore_errors=True)
            continue
        if issued < now - timedelta(hours=hours) or issued > now:
            shutil.rmtree(p.parent, ignore_errors=True)
            continue
        runs.append(run)
    for tmp in root.glob(".*.tmp") if root.exists() else []:  # en avbruten arkivering
        shutil.rmtree(tmp, ignore_errors=True)
    return sorted(runs, key=lambda r: r["issued"], reverse=True)
