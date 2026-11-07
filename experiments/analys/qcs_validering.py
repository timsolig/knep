"""Stationsdygnen som A2TS:s kontroll kastar på valideringen med alla mätare (som i drift), bara som
redovisning efter domarens körning (uppgift 0007). Ingenting väljs här. Testdelen läses aldrig
(domare.days kontrollerar det).

    uv run python experiments/analys/qcs_validering.py
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a2  # noqa: E402

D = a2.D


def main():
    from knep.analys import radar
    q = a2.system_params("A2TS")["kvart"]["QCS"]
    elev = np.load(D.HOJD)["h"].astype(np.float32)
    out, n_sd = [], 0
    for day_s in D.days("validering"):
        day = datetime.fromisoformat(day_s).replace(tzinfo=UTC)
        f = next(iter(sorted((D.RADAR / f"{day:%Y/%m/%d}").glob("*.tif"))))
        _, grid = radar.read_rain(f)
        z = np.load(a2.a1_path(day_s))
        rader = {}
        for res, F in (("kvart", z["kvart"]), ("timme", z["timme"])):
            m = D.load_gauges(day_s, res, grid)
            rader[res] = {"station": m.station, "t": m.t, "mm": m.mm,
                          "a": F[m.t, m.r, m.c].astype(float), "xy": np.c_[m.c, m.r].astype(float) * D.RES_KM,
                          "over400": elev[m.r, m.c] > D.HIGH_M}
        n_sd += len(np.union1d(rader["kvart"]["station"], rader["timme"]["station"]))
        kast = a2.stationsdygn(rader, q)
        for s in sorted(kast):
            rad = {"dag": day_s, "station": s}
            for res, r in rader.items():
                i = r["station"] == s
                torr, noll = a2.stationsfel(**r, q=q, res=res)
                rad[res] = {"perioder": int(i.sum()), "summa": round(float(r["mm"][i].sum()), 1),
                            "radar": round(float(np.nansum(r["a"][i])), 1), "over400": bool(r["over400"][i].any()),
                            "vat_mot_torrt": torr.get(s, 0), "noll_mot_vatt": noll.get(s, 0)}
            out.append(rad)
            print(json.dumps(rad, ensure_ascii=False), flush=True)
    res = {"stationsdygn": n_sd, "kastade": len(out), "andel": len(out) / n_sd, "lista": out}
    print(n_sd, "stationsdygn,", len(out), "kastade", flush=True)
    (a2.OUT / "stationer_validering.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
