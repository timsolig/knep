"""Provkörning av A2T som andra facit i verify.py på en träningsdag (uppgift 0008).

En historisk cykel per timme med --a2 --a2-matare (som experiments/analys/a2_cykel_prov.py), och
efter varje cykel verifieringens steg (verify.cycle) som i drift. cli.py kör inte verifieringen med
--time, så cykelns rutor fångas när Renderer.write anropas, och mätarna till verifieringen läses ur
arkivet (a2_cykel.las_arkiv) och skrivs som gauges.json. A2T:s timsummor sparar cykeln själv i
cache/verif/a2t/. Radarbilderna länkas från /data/radar, så att inget hämtas.

    uv run python experiments/verifiering/a2t_facit_prov.py --dag 2020-07-24 --fran 6 --till 16 \
        --ut /data/verif_prov/2020-07-24

Bara träningsdagar (domare.days("traning")). Skriver resultat.json med tiderna och ett par tal ur
verif.json.
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

from knep import analys, cli, render, verify  # noqa: E402
from knep.analys import a2_cykel  # noqa: E402


def _storlek(p: Path) -> tuple[int, int]:
    filer = [f for f in p.glob("*.npz") if f.is_file()] if p.exists() else []
    return len(filer), sum(f.stat().st_size for f in filer)


def _tal(doc: dict) -> dict:
    """CSI 1 mm och FSS 1 mm på 20 km vid +1 h för Tim-KNEP och persistensen, mot radarn, A2T och mätarna."""
    w = doc["windows"]["7"]
    i1, f1, s20 = verify.THRESHOLDS.index(1.0), verify.FSS_THRESHOLDS.index(1.0), verify.FSS_KM.index(20)
    out = {}
    for obs in ("radar", "a2t", "gauges"):
        for m in ("ours", "persistens", "radar", "a2t"):
            e = (w.get(obs) or {}).get("models", {}).get(m)
            if not e:
                continue
            r = {"timmar": e["hours"], "csi1": [x[i1][0] for x in e["scores"]["csi"]], "kvot": [x[0] for x in e["cont"]["ratio"]]}
            if "fss" in e:
                r["fss1_20km"] = [x[f1][s20][0] for x in e["fss"]]
            out[f"{obs}/{m}"] = r
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dag", required=True)
    ap.add_argument("--fran", type=int, default=6)
    ap.add_argument("--till", type=int, default=16)
    ap.add_argument("--ut", type=Path, required=True)
    ap.add_argument("--matare", type=Path, default=Path("/data/bortfall/matare"))
    a = ap.parse_args()
    assert a.dag in D.days("traning"), "bara träningsdagar"
    day = datetime.fromisoformat(a.dag).replace(tzinfo=UTC)
    cache, out = a.ut / "cache", a.ut / "out"
    cache.mkdir(parents=True, exist_ok=True)
    for src in sorted((D.RADAR / f"{day:%Y/%m/%d}").glob("*.tif")):
        dst = cache / src.name
        if not dst.exists():
            dst.symlink_to(src)

    fangat = {}
    skriv = render.Renderer.write

    def fanga(self, out_, analysis, frames, extra=None):
        fangat.update(grid=self.grid, frames=frames)
        return skriv(self, out_, analysis, frames, extra)

    render.Renderer.write = fanga
    res = {"dag": a.dag, "cykler": []}
    for h in range(a.fran, a.till + 1):
        t0 = day + timedelta(hours=h)
        rad = {"tid": t0.isoformat()}
        t = time.monotonic()
        rc = cli.main(["--time", t0.isoformat(), "--cache", str(cache), "--out", str(out), "--keep-cache",
                       "--history", "13", "--no-bias", "--a2", "--a2-matare", str(a.matare)])
        rad["s_cykel"], rad["rc"] = round(time.monotonic() - t, 1), rc
        t = time.monotonic()
        (out / "gauges.json").write_text(json.dumps(a2_cykel.las_arkiv(a.matare, t0)))
        v = verify.cycle(cache / "verif", out, fangat["grid"], t0, fangat["frames"],
                         lambda tt: analys.source_of(cache / "state", tt))
        rad["s_verif"] = round(time.monotonic() - t, 1)
        rad["verif"] = v
        rad["a2t_npz"] = _storlek(cache / "verif" / "a2t")
        rad["pending"] = sorted(p.stem for p in (cache / "verif" / "pending").glob("*.npz"))
        rad["obs60"] = len(list((cache / "verif" / "obs60").glob("*.npy")))
        print(json.dumps(rad, ensure_ascii=False), flush=True)
        res["cykler"].append(rad)
    if (out / verify.FILE).exists():
        doc = json.loads((out / verify.FILE).read_text())
        w = doc["windows"]["7"]
        res["underlag"] = {k: w.get(k) for k in ("issues", "obs_hours", "gauge_hours", "a2t_hours", "a2t_gauges")}
        res["tal"] = _tal(doc)
        res["verif_json_byte"] = (out / verify.FILE).stat().st_size
    (a.ut / "resultat.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
