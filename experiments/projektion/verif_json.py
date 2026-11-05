"""Sammanfatta en verif.json: timmar, n, händelser, CSI, FBI och kvoten per modell och ledtid."""

import json
import sys


def r(v):
    return None if v is None else round(v, 3)


def main(path: str, window: str = "7") -> None:
    d = json.load(open(path))
    e = d["windows"][window]
    print({k: v for k, v in e.items() if k not in ("radar", "gauges", "stations", "diff")})
    print("trösklar", d["thresholds"])
    for obs in ("radar", "gauges"):
        for m, x in e[obs]["models"].items():
            print(obs, m, "hours", x["hours"], "n", x["n"], "events", x["events"])
            for s in ("csi", "fbi", "pod", "far"):
                print("  ", s, [[r(v[0]) for v in lead] for lead in x["scores"][s]])
            print("   ratio", [r(v[0]) for v in x["cont"]["ratio"]], "me", [r(v[0]) for v in x["cont"]["me"]])
            if "fss" in x:
                print("   fss 1mm", [[r(v[0]) for v in lead[1]] for lead in x["fss"]])
    for m, x in e["radar"]["diff"].items():
        print("diff mot Tim-KNEP på samma block", m, "csi", [[[r(v) for v in t] for t in lead] for lead in x["scores"]["csi"]])
    if "daily" in d:
        print("dygn", d["daily"]["days"])
        for m, x in d["daily"]["radar"].items():
            print("daily", m, "ct lead1..5 thr1mm", [[day[k][2] for k in range(5)] for day in x["ct"]])


if __name__ == "__main__":
    main(*sys.argv[1:])
