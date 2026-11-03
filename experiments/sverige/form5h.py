"""Formsviten 0 till 5 h: vilken blandning ger bäst prognos och naturtrognast nederbördsfält?

    python experiments/sverige/form5h.py --part validering [--system kedja persistens meps_rättad sömlös adaptiv]
    python experiments/sverige/form5h.py --part validering --summary     # bara sammanställningen

Samma utfärdandetider, system och yta som verify5h.py (varje hel timme på dagarna, kvartsmedel
mot radarn), och dessutom:

  punktmått     CSI, FSS och volym som i verify5h.py, men per dag, så att skillnaderna kan
                prövas med bootstrap över dagarna
  form          spektrum, SAL, objekt, kanter och fördelning (form.py) vid 30 min och 1 till 5 h
  tid           förändringen mellan kvartarna mot radarns (står prognosen still, hoppar den?)
  samstämmighet prognoserna för samma tid från två körningar en timme isär: hur mycket skiljer
                de sig, och skiljer de sig mer när MEPS har bytt körning emellan?

Jämförelsen mellan två system (--pair, standard adaptiv mot sömlös) görs med parad bootstrap
över dagarna (dagarna dras med återläggning, 2000 gånger): skillnaden och dess 95 %-intervall.

Resultat: /data/sverige/resultat/form_<del>.jsonl.gz och .npz (rådata), och
experiments/sverige/form_<del>.md (sammanställningen).
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).parent))
import form  # noqa: E402
from data import CYCLE, load_days  # noqa: E402
from knep import nwp  # noqa: E402
from verify5h import (CHAIN_DIR, FSS_THR, NQ, OUT, Q, SCALES_KM, THR, Meps, Obs, Scores,  # noqa: E402
                      chain_forecast, meps_quarters, systems_for)

SHAPE_K = [1, 3, 7, 11, 15, 19]            # kvartar: 30 min, 1, 2, 3, 4 och 5 h
CONS_K = [3, 7, 11, 15]                    # den nya körningens kvart; den förra har k + 4
GROUPS = {"0 till 1 h": range(0, 4), "1 till 3 h": range(4, 12), "3 till 5 h": range(12, 20)}
SYSTEMS = ["kedja", "persistens", "meps_rättad", "sömlös", "adaptiv"]
HERE = Path(__file__).parent


def run(part: str, names: list[str], limit: int | None = None) -> tuple[list, dict]:
    systems = systems_for(names)
    obs, meps = Obs(), Meps()
    records, day_scores = [], {}
    started, issues = time.monotonic(), 0
    for d in load_days(part):
        day = datetime.fromisoformat(d["day"]).replace(tzinfo=UTC)
        if not (CHAIN_DIR / d["day"] / "klar").exists():
            continue
        sc = Scores(names)
        state, prev = {}, None
        base = {"dag": d["day"], "art": d["kind"]}
        for h in range(24):
            t = day + timedelta(hours=h)
            obs.forget(t - timedelta(hours=2))
            fc = chain_forecast(d["day"], t)
            analysis = obs.frame(t) if fc is not None else None
            if analysis is None or obs.grid is None:
                prev = None
                continue
            chain, motion = fc
            mq = meps_quarters(meps, t, obs.grid)
            if mq is None:
                prev = None
                continue
            run_t = nwp.available(t, CYCLE)
            ctx = {"t": t, "chain": chain, "motion": motion, "meps": mq, "analysis": analysis, "grid": obs.grid,
                   "meps_i": meps_quarters(meps, t, obs.grid, interpolate=True),
                   "meps_prev": meps_quarters(meps, t, obs.grid, interpolate=True, lag=1),
                   "obs": obs, "state": state, "meps_run": meps.on(run_t, obs.grid)}
            fcs = {n: fn(ctx) for n, fn in systems.items()}
            mask_base = np.isfinite(chain[0])
            for n in names:
                mask_base &= np.isfinite(fcs[n]).all(axis=0)
            oq = [obs.quarter(t + (k + 1) * Q) for k in range(NQ)]

            # punktmåtten, som i verify5h.run
            hour_f = {n: np.zeros(analysis.shape, np.float32) for n in names}
            hour_o = np.zeros(analysis.shape, np.float32)
            hour_m = mask_base.copy()
            for k in range(NQ):
                o = oq[k]
                if o is None:
                    hour_m[:] = False
                    continue
                m = mask_base & np.isfinite(o)
                on = np.nan_to_num(o)
                fo = sc.fractions(on, m)
                for i, n in enumerate(names):
                    f = np.nan_to_num(fcs[n][k])
                    sc.add(i, k, f, on, m, fo)
                    hour_f[n] += f / 4
                hour_o += on / 4
                hour_m &= np.isfinite(o)
                if k % 4 == 3:
                    fo = sc.fractions(hour_o, hour_m)
                    for i, n in enumerate(names):
                        sc.add_hour(i, k // 4, hour_f[n], hour_o, hour_m, fo)
                        hour_f[n][:] = 0
                    hour_o[:] = 0
                    hour_m = mask_base.copy()

            # formen
            for k in SHAPE_K:
                o = oq[k]
                if o is None:
                    continue
                m = mask_base & np.isfinite(o)
                on = np.nan_to_num(o)
                ts = form.tiles(m, on)
                ps_o = form.spectrum(on, ts)
                for n in names:
                    f = np.nan_to_num(fcs[n][k])
                    region = m & ((on >= 0.1) | (f >= 0.1))
                    records.append(base | {"typ": "form", "sys": n, "k": k} | form.shape_metrics(f, on, m, ts, ps_o, region))

            # förändringen mellan kvartarna
            mt = mask_base.copy()
            for o in oq:
                if o is not None:
                    mt &= np.isfinite(o)
            for n in names:
                records.append(base | {"typ": "tid", "sys": n, "v": form.temporal(list(fcs[n]), oq, mt)})

            # samstämmighet med förra körningen
            if prev is not None and prev["t"] == t - timedelta(hours=1):
                switch = prev["run"] != run_t
                for k in CONS_K:
                    for n in names:
                        new, old = fcs[n][k], prev[n][k + 4]
                        m = mask_base & prev["mask"]
                        j, s = form.jump(new, old, m), form.fss(new, old, m)
                        if j is not None:
                            records.append(base | {"typ": "hopp", "sys": n, "k": k, "byte": switch, "hopp": j,
                                                   "fss_par": s})
            prev = {"t": t, "run": run_t, "mask": mask_base} | {n: fcs[n] for n in names}

            issues += 1
            if limit and issues >= limit:
                break
        day_scores[d["day"]] = {"art": d["kind"], "ct": sc.ct, "fss": sc.fss, "vol": sc.vol, "n": sc.n,
                                "hct": sc.hct, "hfss": sc.hfss}
        print(f"{d['day']}: {issues} utfärdandetider, {time.monotonic() - started:.0f} s", flush=True)
        if limit and issues >= limit:
            break
    return records, day_scores


# ---------- lagring ----------

def save(part: str, names, records, day_scores, tag=None) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stem = OUT / f"form_{tag or part}"
    with gzip.open(stem.with_suffix(".jsonl.gz"), "wt") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")
    days = sorted(day_scores)
    arrays = {"systems": np.array(names), "days": np.array(days), "kinds": np.array([day_scores[d]["art"] for d in days])}
    for key in ("ct", "fss", "vol", "n", "hct", "hfss"):
        arrays[key] = np.stack([day_scores[d][key] for d in days])
    np.savez_compressed(stem.with_suffix(".npz"), **arrays)


def load(part: str, tag=None):
    stem = OUT / f"form_{tag or part}"
    with gzip.open(stem.with_suffix(".jsonl.gz"), "rt") as fh:
        records = [json.loads(line) for line in fh]
    return records, dict(np.load(stem.with_suffix(".npz")))


# ---------- sammanställning ----------

B = 2000
RNG = np.random.default_rng(20261101)


def boot(per_day: np.ndarray, stat) -> tuple[float, float, float]:
    """per_day: (dagar, ...) summor; stat tar summan över dagarna och ger ett tal. Ger värdet och
    95 %-intervallet över dagarna dragna med återläggning."""
    nd = per_day.shape[0]
    full = stat(per_day.sum(0))
    idx = RNG.integers(0, nd, (B, nd))
    vals = np.array([stat(per_day[i].sum(0)) for i in idx])
    lo, hi = np.nanquantile(vals, [0.025, 0.975])
    return float(full), float(lo), float(hi)


def fmt_ci(v, lo, hi, better_low=False):
    sig = ""
    if (hi < 0 or lo > 0) and abs(v) >= 5e-4:  # skilt från noll, och inte bara avrundningsbrus
        sig = " ✓" if (hi < 0) == better_low else " ✗"
    return f"{v:+.3f} [{lo:+.3f}, {hi:+.3f}]{sig}"


def _fss(x):
    return 1 - x[..., 0] / np.maximum(x[..., 1], 1e-9)


def _csi(ct):
    return ct[..., 0] / np.maximum(ct.sum(-1), 1)


def score_section(arr, names, pair) -> list[str]:
    a, b = names.index(pair[0]), names.index(pair[1])
    lines = ["## Punktmått", "",
             f"Medel över kvartarna i varje intervall. Skillnaden är {pair[0]} minus {pair[1]} med 95 %-intervall "
             "(bootstrap över dagarna); ✓ betyder att intervallet ligger helt på den bättre sidan för "
             f"{pair[0]}, ✗ helt på den sämre.", ""]
    metrics = []
    for j, thr in enumerate(FSS_THR):
        for s, km in enumerate(SCALES_KM):
            metrics.append((f"FSS {thr:g} mm/h {km} km", "fss", (j, s), _fss, False))
    for j, thr in enumerate(THR):
        metrics.append((f"CSI {thr:g} mm/h", "ct", (j,), _csi, False))
    header = "| Mått | Intervall | " + " | ".join(names) + f" | {pair[0]} − {pair[1]} |"
    lines += [header, "|" + "---|" * (len(names) + 3)]
    for label, key, ix, fn, low in metrics:
        x = arr[key]  # (dagar, system, NQ, ...)
        for g, ks in GROUPS.items():
            sel = lambda i: x[:, i][:, list(ks)][(slice(None), slice(None)) + ix]  # (dagar, kvartar, ...)
            vals = [float(fn(sel(i).sum(0)).mean()) for i in range(len(names))]
            pd = np.stack([sel(a), sel(b)], 1)  # (dagar, 2, kvartar, ...)
            d = boot(pd, lambda s: float(fn(s[0]).mean() - fn(s[1]).mean()))
            lines.append(f"| {label} | {g} | " + " | ".join(f"{v:.3f}" for v in vals) + f" | {fmt_ci(*d, low)} |")
    # volym: |log(kvot)| per kvart, lägre är bättre
    v = arr["vol"]
    for g, ks in GROUPS.items():
        def lv(s):
            ok = (s[..., 0] > 0) & (s[..., 1] > 0)
            return np.abs(np.log(s[..., 0][ok] / s[..., 1][ok])).mean() if ok.any() else np.nan
        vals = [float((v[:, i][:, list(ks)].sum(0)[..., 0] / v[:, i][:, list(ks)].sum(0)[..., 1]).mean()) for i in range(len(names))]
        pd = np.stack([v[:, a][:, list(ks)], v[:, b][:, list(ks)]], 1)
        d = boot(pd, lambda s: float(lv(s[0]) - lv(s[1])))
        lines.append(f"| Volym (kvot; skillnad i abs. log) | {g} | " + " | ".join(f"{x:.3f}" for x in vals) + f" | {fmt_ci(*d, True)} |")
    return lines + [""]


def _per_day(records, days, key, sys_, filt, absolute):
    """(dagar, 2): summa och antal av key (eller |key|) per dag för system sys_."""
    out = np.zeros((len(days), 2))
    di = {d: i for i, d in enumerate(days)}
    for r in records:
        if r["sys"] == sys_ and key in r and filt(r) and r[key] is not None and np.isfinite(r[key]):
            v = abs(r[key]) if absolute else r[key]
            out[di[r["dag"]]] += [v, 1]
    return out


def _mean(x):
    return x[..., 0] / np.maximum(x[..., 1], 1e-9)


SHAPE_KEYS = ([f"spek_{lo}_{hi}" for lo, hi in form.BANDS_KM] + ["S", "A", "L"]
              + [f"obj_antal_{t:g}" for t in form.OBJ_THR] + [f"obj_storlek_{t:g}" for t in form.OBJ_THR]
              + ["kanter"] + [f"q{q * 100:g}" for q in form.QS] + [f"yta_{t:g}" for t in form.WET])
def _label(key: str) -> str:
    if key.startswith("spek_"):
        lo, hi = key.split("_")[1:]
        return f"effekt i bandet {lo} till {hi} km (log kvot)"
    if key.startswith("obj_"):
        what, thr = key.split("_")[1:]
        return f"{'antal' if what == 'antal' else 'storlek på'} regnområden över {thr} mm/h (log kvot)"
    if key.startswith("yta_"):
        return f"yta över {key[4:]} mm/h (log kvot)"
    if key.startswith("q"):
        return f"kvantil {key[1:]} % över ytan (log kvot)"
    return {"S": "SAL struktur", "A": "SAL amplitud", "L": "SAL läge", "kanter": "kanternas branthet (log kvot)"}[key]


def shape_section(records, days, names, pair) -> list[str]:
    form_r = [r for r in records if r["typ"] == "form"]
    leads = [f"{(k + 1) * 15} min" if k < 3 else f"{(k + 1) // 4} h" for k in SHAPE_K]
    lines = ["## Formen", "",
             "Medelavvikelse mot radarn per ledtid (0 är rätt; log kvot, utom SAL). Under varje mått: "
             f"skillnaden i medelbelopp (|avvikelse|, lägre är bättre) {pair[0]} minus {pair[1]} med 95 %-intervall.", ""]
    for key in SHAPE_KEYS:
        lines += [f"### {_label(key)}", "", "| System | " + " | ".join(leads) + " |", "|---|" + "---|" * len(leads)]
        for n in names:
            row = [_mean(_per_day(form_r, days, key, n, lambda r, k=k: r["k"] == k, False).sum(0)) for k in SHAPE_K]
            lines.append(f"| {n} | " + " | ".join(f"{v:+.3f}" for v in row) + " |")
        diffs = []
        for g, ks in GROUPS.items():
            sel = [k for k in SHAPE_K if k in ks]
            pa = _per_day(form_r, days, key, pair[0], lambda r: r["k"] in sel, True)
            pb = _per_day(form_r, days, key, pair[1], lambda r: r["k"] in sel, True)
            d = boot(np.stack([pa, pb], 1), lambda s: float(_mean(s[0]) - _mean(s[1])))
            diffs.append(f"{g}: {fmt_ci(*d, True)}")
        lines += ["", "Belopp, " + "; ".join(diffs), ""]
    return lines


def time_section(records, days, names, pair) -> list[str]:
    tr = [r for r in records if r["typ"] == "tid"]
    lines = ["## Förändringen mellan kvartarna", "",
             "log(prognosens förändring från kvarten före / radarns), medel. Negativt: prognosen ändras för lite "
             "(står still eller är utjämnad); positivt: för mycket (hoppar). Kolumnen är kvarten som förändringen slutar i.", ""]
    ks = [1, 3, 4, 7, 8, 11, 12, 15, 16, 19]
    lines += ["| System | " + " | ".join(f"{(k + 1) * 15}" for k in ks) + " | medelbelopp |", "|---|" + "---|" * (len(ks) + 1)]
    di = {d: i for i, d in enumerate(days)}
    acc = {}
    for n in names:
        s = np.zeros((len(days), NQ - 1, 2))
        sa = np.zeros((len(days), 2))
        for r in tr:
            if r["sys"] != n:
                continue
            for k, v in enumerate(r["v"]):
                if v is not None and np.isfinite(v):
                    s[di[r["dag"]], k] += [v, 1]
                    sa[di[r["dag"]]] += [abs(v), 1]
        acc[n] = sa
        tot = s.sum(0)
        lines.append(f"| {n} | " + " | ".join(f"{_mean(tot[k - 1]):+.3f}" for k in ks) + f" | {_mean(sa.sum(0)):.3f} |")
    d = boot(np.stack([acc[pair[0]], acc[pair[1]]], 1), lambda s: float(_mean(s[0]) - _mean(s[1])))
    return lines + ["", f"Medelbelopp {pair[0]} minus {pair[1]}: {fmt_ci(*d, True)}", ""]


def consistency_section(records, days, names, pair) -> list[str]:
    hr = [r for r in records if r["typ"] == "hopp"]
    lines = ["## Samstämmighet mellan körningarna", "",
             "Prognoserna för samma kvart från två körningar en timme isär. Hopp: medel av |ny − förra| genom "
             "medelintensiteten (lägre är lugnare). FSS-par: FSS 1 mm/h på 30 km mellan dem (1 är samma bild). "
             "Ledtiden är den nya körningens; uppdelat på om MEPS bytte körning emellan.", ""]
    for key, low in (("hopp", True), ("fss_par", False)):
        lines += [f"### {'Hopp' if key == 'hopp' else 'FSS-par'}", "",
                  "| System | MEPS-byte | " + " | ".join(f"{(k + 1) // 4} h" for k in CONS_K) + " | alla |",
                  "|---|---|" + "---|" * (len(CONS_K) + 1)]
        for n in names:
            for sw in (False, True):
                row = [_mean(_per_day(hr, days, key, n, lambda r, k=k, sw=sw: r["k"] == k and r["byte"] == sw, False).sum(0))
                       for k in CONS_K]
                allv = _mean(_per_day(hr, days, key, n, lambda r, sw=sw: r["byte"] == sw, False).sum(0))
                lines.append(f"| {n} | {'ja' if sw else 'nej'} | " + " | ".join(f"{v:.3f}" for v in row) + f" | {allv:.3f} |")
        for sw in (False, True):
            pa = _per_day(hr, days, key, pair[0], lambda r, sw=sw: r["byte"] == sw, False)
            pb = _per_day(hr, days, key, pair[1], lambda r, sw=sw: r["byte"] == sw, False)
            d = boot(np.stack([pa, pb], 1), lambda s: float(_mean(s[0]) - _mean(s[1])))
            lines.append(f"\n{pair[0]} minus {pair[1]}, MEPS-byte {'ja' if sw else 'nej'}: {fmt_ci(*d, low)}")
        lines.append("")
    return lines


def season_section(records, arr, names, pair) -> list[str]:
    days, kinds = list(arr["days"]), list(arr["kinds"])
    lines = ["## Per årstid", "", "FSS 1 mm/h på 30 km och |S| (SAL struktur), medel 1 till 5 h.", "",
             "| Årstid | Dagar | " + " | ".join(f"FSS {n}" for n in names) + " | " + " | ".join(f"\\|S\\| {n}" for n in names) + " |",
             "|---|---|" + "---|" * (2 * len(names))]
    j, s = FSS_THR.index(1.0), SCALES_KM.index(30)
    for kind in sorted(set(kinds)):
        sel = [i for i, k in enumerate(kinds) if k == kind]
        x = arr["fss"][sel][:, :, 4:, j, s].sum(0)  # (system, kvartar, 2)
        f = [float(_fss(x[i]).mean()) for i in range(len(names))]
        dset = {days[i] for i in sel}
        fr = [r for r in records if r["typ"] == "form" and r["dag"] in dset and r["k"] >= 3]
        sv = [_mean(_per_day(fr, days, "S", n, lambda r: True, True).sum(0)) for n in names]
        lines.append(f"| {kind} | {len(sel)} | " + " | ".join(f"{v:.3f}" for v in f) + " | " + " | ".join(f"{v:.3f}" for v in sv) + " |")
    return lines + [""]


def summarize(part: str, pair, tag=None) -> str:
    records, arr = load(part, tag)
    names, days = list(arr["systems"]), list(arr["days"])
    n_issue = int(arr["n"][:, 0, 0].sum())
    head = [f"# Formsviten, {part}", "",
            f"{len(days)} dagar, {n_issue} utfärdandetider, system: {', '.join(names)}. "
            f"Skapad av `experiments/sverige/form5h.py`; måtten beskrivs i `form.py`.", ""]
    body = (score_section(arr, names, pair) + shape_section(records, days, names, pair)
            + time_section(records, days, names, pair) + consistency_section(records, days, names, pair)
            + season_section(records, arr, names, pair))
    return "\n".join(head + body)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--part", default="validering")
    p.add_argument("--system", nargs="+", default=SYSTEMS)
    p.add_argument("--pair", nargs=2, default=["adaptiv", "sömlös"])
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--tag", default=None)
    p.add_argument("--summary", action="store_true", help="bara sammanställningen ur sparade rådata")
    a = p.parse_args()
    if a.part == "test":
        sys.exit("testdelen körs en gång, i slutet, med verify5h.py; formsviten är för valet på valideringsdelen")
    if not a.summary:
        records, day_scores = run(a.part, a.system, a.limit)
        save(a.part, a.system, records, day_scores, a.tag)
    md = summarize(a.part, a.pair, a.tag)
    (HERE / f"form_{a.tag or a.part}.md").write_text(md + "\n")
    print(md)


if __name__ == "__main__":
    main()
