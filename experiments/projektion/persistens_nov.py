"""Varför slår persistensen Tim-KNEP 4 och 5 november 2026? Radarn ur SMHI:s arkiv och kedjan utan MEPS.

Hämtar kompositerna 2026-11-04 17:00 till 2026-11-05 06:00 till /data/projektion/drift/radar/ (finns inte
i /data/radar, som slutar 2025), räknar timsummor i block om 2 som verify.py och jämför för utgåvorna
19:05 till 00:05 (de sex i verif.json):

- persistensen, radarns timme som slutar hh, mot timmen som slutar hh + k;
- kedjan (Chain.run utan MEPS, utan extremmodell, utan volymkorrektion och med tomt tillstånd) mot samma timme;
- hur stillastående regnet är: andelen av ytan över 1 mm i timmen hh + k som också var över 1 mm i timmen hh,
  och förskjutningen som ger bäst korrelation mellan timmarna.

Kör: uv run python experiments/projektion/persistens_nov.py [--no-chain]
"""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import requests

from knep import model, radar, render, verify

STEP, HOUR = timedelta(minutes=5), timedelta(hours=1)
DIR = Path("/data/projektion/drift/radar")
FIRST = datetime(2026, 11, 4, 17, 0, tzinfo=UTC)
LAST = datetime(2026, 11, 5, 6, 0, tzinfo=UTC)
ISSUES = [datetime(2026, 11, 4, 19, 5, tzinfo=UTC) + k * HOUR for k in range(6)]
THR = verify.THRESHOLDS


def frames() -> dict[datetime, np.ndarray]:
    DIR.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    s.headers["User-Agent"] = "knep/0.1 (hobbyprojekt)"
    out, t = {}, FIRST
    while t <= LAST:
        try:
            out[t], grid = radar.read_rain(radar.fetch(t, DIR, s))
        except requests.RequestException as e:
            print("saknas", t, e, flush=True)
        t += STEP
    return out, grid


def hour(fr, end):
    st = [verify.block(fr[end - j * STEP]) for j in range(12) if end - j * STEP in fr]
    if len(st) < verify.MIN_FRAMES:
        return None
    st = np.stack(st)
    n = np.isfinite(st).sum(0)
    return np.where(n >= verify.MIN_FRAMES, np.nansum(st, 0) / np.maximum(n, 1), np.nan).astype(np.float32)


def ct(f, o, m):
    a = []
    for thr in THR:
        fy, oy = f[m] >= thr, o[m] >= thr
        a.append([int((fy & oy).sum()), int((fy & ~oy).sum()), int((~fy & oy).sum())])
    return np.array(a)


def best_shift(a, b, r=12):
    """Förskjutningen (rader, kolumner, i block om 4 km) av a som bäst stämmer med b, och korrelationen."""
    a, b = np.nan_to_num(a), np.nan_to_num(b)
    best = (0, 0, -1.0)
    for dy in range(-r, r + 1, 2):
        for dx in range(-r, r + 1, 2):
            s = np.roll(np.roll(a, dy, 0), dx, 1)
            c = np.corrcoef(s.ravel(), b.ravel())[0, 1]
            if c > best[2]:
                best = (dy, dx, float(c))
    return best


def main(argv):
    fr, grid = frames()
    print("bilder", len(fr), flush=True)
    hours = {e: hour(fr, e) for e in (FIRST + k * HOUR for k in range(1, 14))}
    res = {"wet": {}, "issues": []}
    for e, h in hours.items():
        if h is not None:
            res["wet"][e.isoformat()] = {"n": int(np.isfinite(h).sum()), "ge1": int((h >= 1).sum()),
                                         "ge01": int((h >= 0.1).sum()), "mean": float(np.nanmean(h))}
    chain = model.Chain(None)
    tot = {s: np.zeros((verify.LEADS, len(THR), 3), np.int64) for s in ("persistens", "kedja")}
    for t0 in ISSUES:
        hh = verify._floor(t0)
        P = hours[hh]
        ours = {}
        if "--no-chain" not in argv:
            obs = np.stack([fr[t0 - k * STEP] for k in range(11, -1, -1)])
            started = time.monotonic()
            r = chain.run(obs, t0, verify.LEADS * 12, model.State())
            fcf = [(t0 - k * STEP, "obs", fr[t0 - k * STEP]) for k in range(11, -1, -1)]
            fcf += [(t0 + (k + 1) * STEP, "fc", f) for k, f in enumerate(r.rain)]
            ours = {e: verify.block(f) for e, _, _, f in render.aggregate(fcf, 60)}
            print(t0, "kedjan", round(time.monotonic() - started), "s", flush=True)
        entry = {"issue": t0.isoformat(), "leads": []}
        for k in range(1, verify.LEADS + 1):
            e = hh + k * HOUR
            O = hours.get(e)
            if O is None or P is None:
                continue
            m = np.isfinite(O) & np.isfinite(P)
            c = ct(P, O, m)
            tot["persistens"][k - 1] += c
            wet = O >= 1
            row = {"k": k, "n": int(m.sum()), "persistens_ct1": c[THR.index(1.0)].tolist(),
                   "kvar": float((wet & (P >= 1) & m).sum() / max((wet & m).sum(), 1)),
                   "shift": best_shift(np.where(m, P, 0), np.where(m, O, 0))}
            if e in ours:
                F = ours[e]
                mk = m & np.isfinite(F)
                ck = ct(F, O, mk)
                tot["kedja"][k - 1] += ck
                cp = ct(P, O, mk)
                row |= {"kedja_ct1": ck[THR.index(1.0)].tolist(), "persistens_ct1_samma": cp[THR.index(1.0)].tolist(),
                        "kedja_ratio": float(np.nansum(F[mk]) / max(np.nansum(O[mk]), 1e-9))}
            entry["leads"].append(row)
            print(json.dumps(row), flush=True)
        res["issues"].append(entry)
    for s, x in tot.items():
        a, b, c = x[..., 0], x[..., 1], x[..., 2]
        res[f"csi_{s}"] = np.round(a / np.maximum(a + b + c, 1), 3).tolist()
        print(s, "CSI per ledtid (rader) och tröskel", res[f"csi_{s}"])
    out = Path("experiments/projektion/results")
    out.mkdir(parents=True, exist_ok=True)
    (out / "persistens_nov.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
