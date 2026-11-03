"""Samla SMHI:s SNOW-körningar för verifieringen mot radarn (SNOW har inget öppet arkiv).

    nohup python experiments/sverige/snow_samla.py > /data/snow/samla.log 2>&1 &

Var 5:e minut läses createdtime; när referenstiden är ny hämtas medianen för timmarna som
slutar 1 till 6 h efter referenstiden (timmen som slutar närmast efter den räknas som timme 1)
och sparas på MEPS rutnät som /data/snow/ÅÅÅÅMMDD/snow_<referenstid>.npz (float16, timmarnas
sluttider i "ends"). Körningar som missas går inte att hämta i efterhand.
"""

from __future__ import annotations

import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from knep import compare  # noqa: E402

ROOT = Path("/data/snow")
HOURS = 6


def created(session) -> datetime | None:
    r = session.get(f"{compare.SNOW}/createdtime.json", timeout=30)
    r.raise_for_status()
    return compare._parse(r.json()["referenceTime"])


def collect(session, ref: datetime) -> Path | None:
    first = ref.replace(minute=0, second=0, microsecond=0) + compare.HOUR
    ends, fields = [], []
    for k in range(HOURS):
        end = first + k * compare.HOUR
        got = compare.snow_field(session, end)
        if got is None:
            continue
        field, r = got
        if r and compare._parse(r) != ref:  # en nyare körning hann komma; ta den nästa gång
            return None
        ends.append(end.strftime("%Y-%m-%dT%H:%M:%SZ"))
        fields.append(field.astype(np.float16))
    if not fields:
        return None
    d = ROOT / f"{ref:%Y%m%d}"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"snow_{ref:%Y%m%dT%H%M}.npz"
    np.savez_compressed(p, ref=np.array(ref.strftime("%Y-%m-%dT%H:%M:%SZ")), ends=np.array(ends), median=np.stack(fields))
    return p


def main() -> None:
    session = requests.Session()
    session.headers["Accept-Encoding"] = "gzip"
    last = None
    while True:
        try:
            ref = created(session)
            if ref is not None and ref != last:
                p = collect(session, ref)
                if p is not None:
                    last = ref
                    print(f"{datetime.now(UTC):%Y-%m-%d %H:%M} {p.name}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"{datetime.now(UTC):%Y-%m-%d %H:%M} fel: {e}", flush=True)
        time.sleep(300 - time.time() % 300 + 30)


if __name__ == "__main__":
    main()
