"""Kedjans prognoser 0 till 5 h på de svenska dagarna, sparade som kvartsmedel för verifieringen.

Kedjan körs var 5:e minut genom dygnet som i drift, så att platskartan har sitt tillstånd. De
korta körningarna har 6 steg, det som tillståndet behöver. Varje hel timme körs den 5 h
framåt, och de 20 kvartsmedlen sparas kodade som värdefilen (render.encode_values) i
/data/sverige/kedja/<dag>/<HHMM>.npz, med rörelsefältet glesat 4 gånger.

    python experiments/sverige/kedja.py --shard 0/3      dagarna 0, 3, 6, ... (kör tre parallellt)
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import deque
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).parent))
from data import DATA, load_days, radar_path  # noqa: E402
from knep import model, radar, render  # noqa: E402

OUT = DATA / "sverige" / "kedja"
STEPS = 60          # 5 h i 5-minuterssteg
HISTORY = 12
WARMUP = timedelta(minutes=90)  # platskartan behöver 30-minutersprognoserna från senaste timmen


def read(t: datetime) -> np.ndarray | None:
    p = radar_path(t)
    if not p.exists():
        return None
    try:
        return radar.read_rain(p)[0]
    except Exception:  # noqa: BLE001  en trasig fil räknas som saknad
        return None


def run_day(day: datetime, chain: model.Chain, root: Path = OUT) -> None:
    out = root / f"{day:%Y-%m-%d}"
    out.mkdir(parents=True, exist_ok=True)
    if (out / "klar").exists():
        return
    state, frames = model.State(), deque(maxlen=HISTORY)
    t, end, started, n_long = day - WARMUP, day + timedelta(hours=24), time.monotonic(), 0
    shape = None
    while t < end:
        f = read(t)
        if f is None:
            frames.clear()  # som i drift utan utfyllnad: kedjan startar om när det finns historik igen
        else:
            shape = f.shape
            frames.append(f)
        issue = t >= day and t.minute == 0
        if len(frames) >= 7:
            res = chain.run(np.stack(frames), t, STEPS if issue else 6, state)
            if issue:
                q = res.rain.reshape(STEPS // 3, 3, *shape).mean(axis=1)
                np.savez_compressed(out / f"{t:%H%M}.npz", codes=np.stack([render.encode_values(x) for x in q]),
                                    motion=res.motion[:, ::4, ::4].astype(np.float16))
                n_long += 1
        t += radar.STEP
    (out / "klar").write_text(f"{n_long} prognoser på {time.monotonic() - started:.0f} s\n")
    print(f"{day:%Y-%m-%d}: {n_long} prognoser på {time.monotonic() - started:.0f} s", flush=True)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--shard", default="0/1")
    p.add_argument("--part", default=None, help="validering eller test; standard är alla")
    p.add_argument("--motion-step", type=int, default=1, help="rörelsefältets interpolation på var n:e pixel (model.dense_motion)")
    p.add_argument("--out", type=Path, default=OUT)
    a = p.parse_args()
    i, n = map(int, a.shard.split("/"))
    chain = model.Chain(None, motion_step=a.motion_step)
    days = load_days(a.part)
    for d in days[i::n]:
        run_day(datetime.fromisoformat(d["day"]).replace(tzinfo=UTC), chain, a.out)


if __name__ == "__main__":
    main()
