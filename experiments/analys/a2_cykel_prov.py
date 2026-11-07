"""Provkörning av valet --a2 i cykeln på en träningsdag (uppgift 0004).

Radarbilderna länkas från /data/radar till en egen cache, så att cykeln inte hämtar något, och
mätarna läses ur arkivet /data/bortfall/matare/p7.npz och p14.npz (--a2-matare). En cykel per timme
med --history 13 (en hel timme A1 per cykel); varje cykel körs först utan och sedan med --a2 i var sin
katalog, så att den extra tiden syns. Resultatet (tider, filer, storlek) skrivs som JSON.

    uv run python experiments/analys/a2_cykel_prov.py --dag 2020-07-24 --fran 6 --till 16 \
        --ut /data/analys/a2/cykel_prov

Bara träningsdagar (domare.days("traning")).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1].parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments/analys"))

import domare as D  # noqa: E402

from knep import cli  # noqa: E402


def _storlek(p: Path, pattern: str) -> tuple[int, int]:
    filer = [f for f in p.glob(pattern) if f.is_file()]
    return len(filer), sum(f.stat().st_size for f in filer)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dag", required=True)
    ap.add_argument("--fran", type=int, default=6, help="första timmens slut (UTC)")
    ap.add_argument("--till", type=int, default=16, help="sista timmens slut (UTC)")
    ap.add_argument("--ut", type=Path, required=True)
    ap.add_argument("--matare", type=Path, default=Path("/data/bortfall/matare"))
    ap.add_argument("--utan", action="store_true", help="kör också varje cykel utan --a2 (för tiden)")
    a = ap.parse_args()
    assert a.dag in D.days("traning"), "bara träningsdagar"
    day = datetime.fromisoformat(a.dag).replace(tzinfo=UTC)
    res = {"dag": a.dag, "cykler": []}
    for namn in (["utan"] if a.utan else []) + ["med"]:
        cache = a.ut / namn / "cache"
        cache.mkdir(parents=True, exist_ok=True)
        for src in sorted((D.RADAR / f"{day:%Y/%m/%d}").glob("*.tif")):
            dst = cache / src.name
            if not dst.exists():
                dst.symlink_to(src)
    for h in range(a.fran, a.till + 1):
        t0 = day + timedelta(hours=h)
        rad = {"tid": t0.isoformat()}
        for namn in (["utan"] if a.utan else []) + ["med"]:
            base = a.ut / namn
            args = ["--time", t0.isoformat(), "--cache", str(base / "cache"), "--out", str(base / "out"),
                    "--keep-cache", "--history", "13", "--no-bias", "--no-verify"]
            if namn == "med":
                args += ["--a2", "--a2-matare", str(a.matare)]
            t = time.monotonic()
            rc = cli.main(args)
            rad[f"s_{namn}"] = round(time.monotonic() - t, 1)
            rad[f"rc_{namn}"] = rc
        out = a.ut / "med" / "out"
        m = json.loads((out / "manifest.json").read_text())
        lv = (m.get("levels") or {}).get("a2")
        rad["a2_timmar"] = [f["time"] for f in lv["frames60"]] if lv else None
        rad["a2_kvartar"] = len(lv["frames15"]) if lv else None
        rad["a2_png"] = _storlek(out / "a2", "*.png")
        rad["a1t_npz"] = _storlek(a.ut / "med" / "cache" / "state", "a1t_*.npz")
        print(json.dumps(rad, ensure_ascii=False), flush=True)
        res["cykler"].append(rad)
    (a.ut / "resultat.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
