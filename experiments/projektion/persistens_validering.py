"""Slår persistensen kedjan på timsummor även på valideringsdagarna? Samma räkning som verify.py.

Uppgift 1 (2026-11-05): i drift slog radarns timme före utgåvan Tim-KNEP från +2 h, 4 och 5 november.
Radarn för de dygnen finns inte här, så det här skriptet gör samma jämförelse på valideringsdagarna
(bara delen validering i dagar.json), med kedjans prognoser i /data/sverige/kedja (utan MEPS, utan
blandning). Timmen som slutar hh + k jämförs för

- persistensen: radarns timmedel som slutar hh (bilderna hh−0:55 till hh:00);
- kedjan: medlet av kvartarna 4(k−1) till 4k−1 ur utgåvan hh:00.

Allt i block om 2 (4 km, verify.block) och på rutor där radarn, persistensen och kedjan finns.
Utgåvorna tas var --every:e timme. Resultatet hamnar i experiments/projektion/results/persistens_validering.json.

    uv run python experiments/projektion/persistens_validering.py [--days N] [--every 2]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sverige"))
from data import load_days, radar_path  # noqa: E402
from knep import radar, render, verify  # noqa: E402

STEP, HOUR = timedelta(minutes=5), timedelta(hours=1)
KEDJA = Path("/data/sverige/kedja")
THR = (0.1, 1.0, 5.0)
LEADS = 5


def frame(t, cache):
    if t not in cache:
        p = radar_path(t)
        f = None
        if p.exists():
            try:
                f = verify.block(radar.read_rain(p)[0]).astype(np.float32)
            except Exception:  # noqa: BLE001
                f = None
        cache[t] = f
    return cache[t]


def hour(end, cache):
    st = [f for j in range(12) if (f := frame(end - j * STEP, cache)) is not None]
    if len(st) < verify.MIN_FRAMES:
        return None
    st = np.stack(st)
    n = np.isfinite(st).sum(0)
    return np.where(n >= verify.MIN_FRAMES, np.nansum(st, 0) / np.maximum(n, 1), np.nan).astype(np.float32)


def ct(f, o):
    return np.array([[int(((f >= t) & (o >= t)).sum()), int(((f >= t) & (o < t)).sum()),
                      int(((f < t) & (o >= t)).sum())] for t in THR])


def csi(x):
    a, b, c = x[..., 0], x[..., 1], x[..., 2]
    return np.round(a / np.maximum(a + b + c, 1), 3)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=0, help="bara de N första dagarna (provkörning)")
    p.add_argument("--every", type=int, default=2)
    a = p.parse_args()
    days = [d["day"] for d in load_days("validering") if (KEDJA / d["day"] / "klar").exists()]
    if a.days:
        days = days[: a.days]
    res = {"days": {}, "every": a.every, "thr": THR}
    tot = {s: np.zeros((LEADS, len(THR), 3), np.int64) for s in ("persistens", "kedja")}
    for ds in days:
        started = time.monotonic()
        day = datetime.fromisoformat(ds).replace(tzinfo=UTC)
        cache, hours = {}, {}
        dtot = {s: np.zeros((LEADS, len(THR), 3), np.int64) for s in tot}
        kvar = np.zeros((LEADS, 2), np.int64)  # (våta ≥ 1 mm i facit, av dem våta också i timmen hh)
        ratio = np.zeros((LEADS, 3))  # summa kedjan, persistensen, facit
        for h in range(0, 24, a.every):
            t0 = day + h * HOUR
            pk = KEDJA / ds / f"{t0:%H%M}.npz"
            if not pk.exists():
                continue
            with np.load(pk) as z:
                q = render.decode_values(z["codes"])
            P = hours.setdefault(t0, hour(t0, cache))
            if P is None:
                continue
            for k in range(1, LEADS + 1):
                e = t0 + k * HOUR
                O = hours.setdefault(e, hour(e, cache))
                if O is None:
                    continue
                F = verify.block(q[4 * (k - 1): 4 * k].mean(0))
                m = np.isfinite(O) & np.isfinite(P) & np.isfinite(F)
                if m.sum() < verify.MIN_CELLS:
                    continue
                dtot["persistens"][k - 1] += ct(P[m], O[m])
                dtot["kedja"][k - 1] += ct(F[m], O[m])
                w = O[m] >= 1
                kvar[k - 1] += [int(w.sum()), int((w & (P[m] >= 1)).sum())]
                ratio[k - 1] += [F[m].sum(), P[m].sum(), O[m].sum()]
            # bilderna före den här utgåvan behövs inte längre
            for t in [t for t in cache if t < t0 - HOUR]:
                del cache[t]
        for s in tot:
            tot[s] += dtot[s]
        res["days"][ds] = {"csi_persistens": csi(dtot["persistens"]).tolist(), "csi_kedja": csi(dtot["kedja"]).tolist(),
                           "kvar_1mm": np.round(kvar[:, 1] / np.maximum(kvar[:, 0], 1), 3).tolist(),
                           "ratio_kedja": np.round(ratio[:, 0] / np.maximum(ratio[:, 2], 1e-9), 3).tolist(),
                           "ratio_persistens": np.round(ratio[:, 1] / np.maximum(ratio[:, 2], 1e-9), 3).tolist(),
                           "ct_persistens": dtot["persistens"].tolist(), "ct_kedja": dtot["kedja"].tolist()}
        print(ds, f"{time.monotonic() - started:.0f} s", "CSI 1 mm persistens", csi(dtot["persistens"])[:, 1].tolist(),
              "kedja", csi(dtot["kedja"])[:, 1].tolist(), "kvar", res["days"][ds]["kvar_1mm"], flush=True)
    res["csi_persistens"], res["csi_kedja"] = csi(tot["persistens"]).tolist(), csi(tot["kedja"]).tolist()
    print("alla: CSI per ledtid (rader) och tröskel", THR)
    print("persistens", res["csi_persistens"])
    print("kedja", res["csi_kedja"])
    out = Path(__file__).parent / "results"
    out.mkdir(exist_ok=True)
    (out / ("persistens_validering.json" if not a.days else "persistens_validering_prov.json")).write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
