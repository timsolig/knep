"""Namngivna väderhändelser: kör modellen i efterhand och skriv data till sidans flikar.

För varje händelse körs kedjan var 5:e minut och KNEP-proxyn varje kvart över händelsens
tidsfönster, precis som i drift: vid varje klocktid används den senaste prognosen som
hunnit bli klar (kedjan 3 min, proxyn 10 min efter sin analystid). Det som skrivs:

  manifest.json   händelsen, rutor per upplösning och visningstid, poäng per upplösning och
                  horisont, tidsserie
  *.png           radar, kedjans och proxyns prognos sedd 30 och 60 min i förväg, i tre upplösningar:
                  momentant var 5:e minut, kvartssumma (som KNEP) och timsumma (som SNOW, med
                  prognosen som fanns när timmen började), samt sannolikhet för minst 10 mm/h

    knep-case build hans-2023 --out web/cases
    knep-case index --out web/cases
"""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
from pysteps.extrapolation.semilagrangian import extrapolate
from scipy.ndimage import uniform_filter

from . import composite, model, render

log = logging.getLogger("knep.cases")
STEP = timedelta(minutes=5)
QUARTER = timedelta(minutes=15)
HORIZONS = (15, 30, 45, 60)
LAT_OURS, LAT_PROXY = 5, 10  # minuter från analys till att prognosen kan användas (5-minutersupplösning)


@dataclass(frozen=True)
class Event:
    slug: str
    name: str
    start: datetime
    end: datetime
    kind: str
    text: str
    links: tuple = ()
    source: str = "smhi"


def _t(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


EVENTS = {
    e.slug: e
    for e in [
        Event("hans-2023", "Ovädret Hans", _t("2023-08-07T21:00Z"), _t("2023-08-08T21:00Z"), "regn",
              "Lågtrycket Hans låg kvar över södra Sverige 6 till 10 augusti 2023. Kallfronten den 8 augusti gav "
              "Ullared 83,6 mm och Göteborg 55,6 mm på ett dygn.",
              ("https://www.smhi.se/klimat/klimatet-da-och-nu/manadens-vader-och-vatten-i-sverige/manadens-vader-och-vatten-i-sverige/2023-08-31-augusti-2023---lagtrycket-hans-och-rekordmycket-regn",)),
        Event("anna-2026", "Snöovädret Anna", _t("2026-01-01T00:00Z"), _t("2026-01-02T00:00Z"), "snö",
              "Anna kom in från nordväst under nyårsnatten 2026 med röd varning för snö i Gävleborg. Härnebo gick "
              "från 4 till 101 cm snödjup på två dygn. Intensiteten räknas med regnets Z-R-samband, så nivåerna är "
              "ungefärliga för snö.",
              ("https://www.svt.se/vader/januari2026analys",)),
        Event("gavle-2021", "Skyfallet i Gävle", _t("2021-08-17T18:00Z"), _t("2021-08-18T06:00Z"), "regn",
              "161,6 mm på ett dygn i Gävle 17 till 18 augusti 2021, varav 101 mm på två timmar strax efter midnatt.",
              ("https://www.smhi.se/kunskapsbanken/hydrologi/historiska-oversvamningar/2021---skyfall-i-gavle",)),
    ]
}


def proxy_forecast(acc15, steps=5):
    """KNEP-proxyn: Lucas-Kanade på tre kvartsmedel, extrapolering i 15-minuterssteg."""
    v = model._quiet(model.dense_lucaskanade, model._db(np.stack(acc15)))
    fc = extrapolate(np.nan_to_num(acc15[-1]), v, steps)
    fc[:, ~np.isfinite(acc15[-1])] = np.nan
    return fc.astype(np.float32)


@dataclass
class Scores:
    thresholds: tuple = (1.0, 5.0, 10.0)
    c: dict = field(default_factory=dict)  # (system, horisont, tröskel) -> [träff, miss, falsklarm, korrekt nej]
    vol: dict = field(default_factory=dict)  # (system, horisont) -> [summa prognos, summa radar]

    def add(self, system, h, f, o):
        ok = np.isfinite(o) & np.isfinite(f)
        f, o = f[ok], o[ok]
        for t in self.thresholds:
            a, b = f >= t, o >= t
            v = np.array([np.sum(a & b), np.sum(~a & b), np.sum(a & ~b), np.sum(~a & ~b)], float)
            self.c[(system, h, t)] = self.c.get((system, h, t), 0) + v
        self.vol[(system, h)] = self.vol.get((system, h), 0) + np.array([f.sum(), o.sum()], float)

    def table(self):
        out = {}
        for (s, h, t), (a, b, c, d) in self.c.items():
            n = a + b + c + d
            r = (a + b) * (a + c) / n if n else 0
            ets = (a - r) / (a + b + c - r) if (a + b + c - r) else None
            den = np.sqrt((a + c) * (a + b) * (d + c) * (d + b))
            mcc = (a * d - c * b) / den if den else None
            H = a / (a + b) if (a + b) else None
            F = c / (c + d) if (c + d) else None
            sedi = None
            if H and F and 0 < H < 1 and 0 < F < 1:
                sedi = (np.log(F) - np.log(H) - np.log(1 - F) + np.log(1 - H)) / (np.log(F) + np.log(H) + np.log(1 - F) + np.log(1 - H))
            row = out.setdefault(s, {})
            for name, val in ((f"ETS {t:g} mm/h", ets), (f"MCC {t:g} mm/h", mcc), (f"SEDI {t:g} mm/h", sedi),
                              (f"Träffar {t:g} mm/h", a + b)):
                row.setdefault(name, {})[str(h)] = None if val is None else round(float(val), 3)
        for (s, h), (sf, so) in self.vol.items():
            out.setdefault(s, {}).setdefault("Volym", {})[str(h)] = round(float(sf / so), 3) if so > 0 else None
        return out


RES = (5, 15, 60)
PERSPECTIVE = {
    5: "senaste prognos vid varje klocktid, momentan radar var 5:e minut",
    15: "senaste prognos vid varje klocktid, 15-minuters medelintensitet",
    60: "prognos som fanns när timmen började, timmens medelintensitet",
}


def build(event: Event, frames, grid, out: Path, chain: model.Chain):
    """frames(times) -> lista med mm/h-fält eller None per tid. grid: radar.Grid för renderingen.

    Rutor och poäng i tre upplösningar: momentant var 5:e minut, summa per kvart (som KNEP) och
    summa per timme (som SNOW). Summorna ritas som medelintensitet med samma färger som 5 min.
    """
    out.mkdir(parents=True, exist_ok=True)
    first = event.start - 13 * STEP
    last = event.end + 13 * STEP
    times = [first + k * STEP for k in range(int((last - first) / STEP) + 1)]
    raw = frames(times)
    shape = next(f.shape for f in raw if f is not None)
    raw = [f if f is not None else np.full(shape, np.nan, np.float32) for f in raw]
    idx = {t: k for k, t in enumerate(times)}
    rend = render.Renderer(grid)
    analysis = [None] * len(times)
    gap_state, motion, state = None, None, model.State()
    ours, proxy = {}, {}
    scores = {r: Scores() for r in RES}
    frames_out = {r: [] for r in RES}
    series = []
    src0 = np.zeros(shape, np.uint8)

    def mean_of(fields, t, n):
        k = idx.get(t)
        if k is None or k < n - 1 or any(fields[j] is None for j in range(k - n + 1, k + 1)):
            return None
        return np.mean([fields[j] for j in range(k - n + 1, k + 1)], axis=0)

    def fc_mean(t, leads):
        return np.mean([ours[t][0][L - 1].astype(np.float32) for L in leads], axis=0)

    written = set()

    def png(field, name):
        if name not in written:  # samma ruta kan höra till flera upplösningar
            rend.png(field, out / name)
            written.add(name)
        return name

    def quarter_ceil(t):
        q = t.replace(second=0, microsecond=0)
        while q.minute % 15:
            q += STEP
        return q

    def latest_proxy(limit):
        return max((p for p in proxy if p <= limit), default=None)

    for k, t in enumerate(times):
        a, _, _, gap_state = composite.fill_gaps(raw[k], src0, gap_state, motion)
        analysis[k] = a
        if k < 6 or t > event.end:
            continue
        res = chain.run(np.stack(analysis[k - 6 : k + 1]), t, 13, state)
        motion = res.motion
        ours[t] = (res.rain.astype(np.float16), None if res.prob is None else res.prob[2, 6].astype(np.float16))
        if t.minute % 15 == 0:
            q3 = [mean_of(analysis, t - m * QUARTER, 3) for m in (2, 1, 0)]
            if all(x is not None for x in q3):
                proxy[t] = proxy_forecast(q3).astype(np.float16)
        c = t + timedelta(minutes=LAT_OURS)  # klocktiden när körningen t kan användas

        # poäng, 5 min: momentan radar, proxyns kvart gäller hela kvarten
        q = latest_proxy(c - timedelta(minutes=LAT_PROXY))
        for v in (c + timedelta(minutes=m) for m in range(15, 65, 5)):
            L = int((v - t) / STEP)
            if L > 13 or idx.get(v) is None or q is None:
                continue
            step = int((quarter_ceil(v) - q) / QUARTER)
            if not 1 <= step <= 5:
                continue
            hb = 15 * (int((v - c).total_seconds() // 60) // 15)
            f_ours = ours[t][0][L - 1].astype(np.float32)
            f_proxy = proxy[q][step - 1].astype(np.float32)
            both = np.isfinite(f_ours) & np.isfinite(f_proxy)
            scores[5].add("Ny kedja", hb, np.where(both, f_ours, np.nan), raw[idx[v]])
            scores[5].add("KNEP-proxy", hb, np.where(both, f_proxy, np.nan), raw[idx[v]])

        # poäng, 15 min: kvartsmedel
        for v in (c + timedelta(minutes=m) for m in range(15, 65, 5)):
            if v.minute % 15:
                continue
            hb = 15 * (int((v - c).total_seconds() // 60) // 15)
            truth = mean_of(raw, v, 3)
            if truth is None or q is None:
                continue
            leads = [int((v - m * STEP - t) / STEP) for m in (2, 1, 0)]
            step = int((v - q) / QUARTER)
            if min(leads) < 1 or max(leads) > 13 or not 1 <= step <= 5:
                continue
            f_ours, f_proxy = fc_mean(t, leads), proxy[q][step - 1].astype(np.float32)
            both = np.isfinite(f_ours) & np.isfinite(f_proxy)
            scores[15].add("Ny kedja", hb, np.where(both, f_ours, np.nan), truth)
            scores[15].add("KNEP-proxy", hb, np.where(both, f_proxy, np.nan), truth)

        # poäng och visning, 1 h: prognosen som fanns när timmen började (körd 65 min före timmens slut)
        H = t + timedelta(minutes=65)
        if H.minute == 0 and event.start <= H <= event.end:
            qh = latest_proxy(H - timedelta(minutes=60 + LAT_PROXY))
            steps = [int((H - m * QUARTER - qh) / QUARTER) for m in (3, 2, 1, 0)] if qh is not None else []
            f_ours = fc_mean(t, range(2, 14))
            entry = _frame(frames_out[60], H)
            entry["kedja"] = png(f_ours, f"h_kedja_{H:%Y%m%d%H%M}.png")
            truth = mean_of(raw, H, 12)
            if steps and all(1 <= s_ <= 5 for s_ in steps):
                f_proxy = np.mean([proxy[qh][s_ - 1].astype(np.float32) for s_ in steps], axis=0)
                entry["proxy"] = png(f_proxy, f"h_proxy_{H:%Y%m%d%H%M}.png")
                if truth is not None:
                    both = np.isfinite(f_ours) & np.isfinite(f_proxy)
                    scores[60].add("Ny kedja", 60, np.where(both, f_ours, np.nan), truth)
                    scores[60].add("KNEP-proxy", 60, np.where(both, f_proxy, np.nan), truth)

        # visning, 5 och 15 min: vad användaren såg 30 och 60 min före tiden d
        d = t + timedelta(minutes=35)
        if event.start <= d <= event.end:
            e5 = _frame(frames_out[5], d)
            e5["kedja30"] = png(ours[t][0][6].astype(np.float32), f"kedja30_{d:%Y%m%d%H%M}.png")
            if ours[t][1] is not None:
                name = f"p10_{d:%Y%m%d%H%M}.png"
                rend.png_prob(ours[t][1].astype(np.float32), out / name)
                written.add(name)
                e5["p10"] = name
            # proxyns kvart gäller hela kvarten; samma ruta som i 15-minutersvyn när körningen är densamma
            qd = latest_proxy(d - timedelta(minutes=30 + LAT_PROXY))
            Q = quarter_ceil(d)
            if qd is not None and 1 <= int((Q - qd) / QUARTER) <= 5:
                e5["proxy30"] = png(proxy[qd][int((Q - qd) / QUARTER) - 1].astype(np.float32),
                                    f"proxy30_{qd:%Y%m%d%H%M}_{Q:%Y%m%d%H%M}.png")
        for lead_min, tag in ((35, "30"), (65, "60")):
            d = t + timedelta(minutes=lead_min)
            if d.minute % 15 or d > event.end or d < event.start:
                continue
            L = lead_min // 5
            e15 = _frame(frames_out[15], d)
            e15[f"kedja{tag}"] = png(fc_mean(t, (L - 2, L - 1, L)), f"q_kedja{tag}_{d:%Y%m%d%H%M}.png")
            if tag == "30":
                qd = latest_proxy(d - timedelta(minutes=30 + LAT_PROXY))
                if qd is not None and 1 <= int((d - qd) / QUARTER) <= 5:
                    e15["proxy30"] = png(proxy[qd][int((d - qd) / QUARTER) - 1].astype(np.float32),
                                         f"proxy30_{qd:%Y%m%d%H%M}_{d:%Y%m%d%H%M}.png")

        for old in [p for p in ours if p < t - 14 * STEP]:
            del ours[old]
        for old in [p for p in proxy if p < t - 6 * QUARTER]:
            del proxy[old]

    # radar i alla upplösningar; täckning: pixlar med data i minst halva händelsen
    cover = np.mean([np.isfinite(f) for f in raw], axis=0) >= 0.5
    for k, t in enumerate(times):
        if not event.start <= t <= event.end:
            continue
        _frame(frames_out[5], t)["radar"] = png(raw[k], f"radar_{t:%Y%m%d%H%M}.png")
        if t.minute % 15 == 0 and (m15 := mean_of(raw, t, 3)) is not None:
            _frame(frames_out[15], t)["radar"] = png(m15, f"q_radar_{t:%Y%m%d%H%M}.png")
        if t.minute == 0 and (m60 := mean_of(raw, t, 12)) is not None:
            _frame(frames_out[60], t)["radar"] = png(m60, f"h_radar_{t:%Y%m%d%H%M}.png")
        o = raw[k][np.isfinite(raw[k])]
        series.append({"time": render._iso(t), "max": round(float(o.max()), 1) if o.size else None,
                       "area5": int((o >= 5).sum()) * (grid.transform.a / 1000) ** 2,
                       "saknas": round(float(np.isnan(raw[k][cover]).mean()), 3) if cover.any() else 0.0})
    for r in RES:
        frames_out[r].sort(key=lambda e: e["time"])
    for f in out.glob("*.png"):
        if f.name not in written:
            f.unlink()
    manifest = {
        "slug": event.slug, "name": event.name, "kind": event.kind, "text": event.text, "links": list(event.links),
        "start": render._iso(event.start), "end": render._iso(event.end), "bounds": rend.bounds,
        "legend": render.legend(5), "legends": {str(r): render.legend(r) for r in RES},
        "units": {str(r): render.UNITS[r] for r in RES}, "prob_legend": render.prob_legend(),
        "res": {str(r): frames_out[r] for r in RES}, "series": series,
        "scores": {str(r): {"horizons": [60] if r == 60 else list(HORIZONS), "perspective": PERSPECTIVE[r],
                            "systems": scores[r].table()} for r in RES},
        "generated": render._iso(datetime.now(UTC)),
    }
    tmp = out / "manifest.json.tmp"
    tmp.write_text(json.dumps(manifest, indent=1, ensure_ascii=False))
    tmp.replace(out / "manifest.json")
    log.info("%s: %s rutor", event.slug, {r: len(v) for r, v in frames_out.items()})
    return manifest


def _frame(frames_out, t):
    iso = render._iso(t)
    for e in frames_out:
        if e["time"] == iso:
            return e
    e = {"time": iso}
    frames_out.append(e)
    return e


def write_index(root: Path):
    items = []
    for m in sorted(root.glob("*/manifest.json")):
        d = json.loads(m.read_text())
        items.append({k: d[k] for k in ("slug", "name", "kind", "start", "end", "text")} | {"path": m.parent.name})
    items.sort(key=lambda x: x["start"], reverse=True)
    (root / "index.json").write_text(json.dumps(items, indent=1, ensure_ascii=False))
    return items


def smhi_frames(cache: Path):
    import requests

    from . import radar

    session = requests.Session()
    session.headers["User-Agent"] = "knep/0.1 (hobbyprojekt)"
    grid_holder = {}

    def get(times):
        out = []
        for t in times:
            try:
                rain, grid = radar.read_rain(radar.fetch(t, cache, session))
                grid_holder["grid"] = grid
                out.append(rain)
            except Exception as e:  # saknad bild blir ett bortfall som kompositen fyller
                log.warning("saknar %s: %s", t, e)
                out.append(None)
        return out

    return get, grid_holder


def main(argv=None):
    p = argparse.ArgumentParser(prog="knep-case", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="bygg en händelse")
    b.add_argument("slug", choices=sorted(EVENTS))
    b.add_argument("--out", type=Path, default=Path("web/cases"))
    b.add_argument("--cache", type=Path, default=Path("cache/cases"))
    b.add_argument("--model", type=Path, default=Path("models/extremes.pkl"), help="tränad extremkalibrering")
    i = sub.add_parser("index", help="skriv index.json över byggda händelser")
    i.add_argument("--out", type=Path, default=Path("web/cases"))
    sub.add_parser("list", help="visa kända händelser")
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if a.cmd == "list":
        for e in EVENTS.values():
            print(f"{e.slug:12s} {e.name:22s} {e.start:%Y-%m-%d %H:%M} till {e.end:%Y-%m-%d %H:%M} UTC")
        return 0
    if a.cmd == "index":
        write_index(a.out)
        return 0
    e = EVENTS[a.slug]
    a.cache.mkdir(parents=True, exist_ok=True)
    get, holder = smhi_frames(a.cache)
    times = [e.start - 8 * STEP]
    get(times)  # första bilden ger rutnätet
    if "grid" not in holder:
        log.error("kunde inte hämta någon radarbild för %s", e.slug)
        return 1
    build(e, get, holder["grid"], a.out / e.slug, model.Chain(a.model if a.model.exists() else None, prob_steps=7))
    write_index(a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
