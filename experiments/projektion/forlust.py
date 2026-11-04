"""Uppgift 2 (förlust): var i kedjan försvinner extremerna?

    uv run python experiments/projektion/forlust.py kör [--dagar N] [--procs 2]
    uv run python experiments/projektion/forlust.py tabell

Varje utgåva på träningsdagarna (2 km, timmarna TIMMAR) körs kedjan steg för steg som
model.Chain.run, och varje mellanled bedöms som ett eget system med domarens summor (domare.Acc,
utan spektrum utom där det anges) mot radarns kvartsmedel på domarens rutor:

  persistens      analysen oförändrad
  nn              analysen flyttad med närmaste granne: värdena bevaras, bara randen och
                  rörelsefältets deformation ändrar fördelningen
  bilinjar        kedjans bilinjära flytt (det fält som matchas)
  matchad_analys  bilinjar matchad mot hela analysens fördelning (Chain(target="analysis"))
  matchad         bilinjar matchad mot nn (kedjan, steg 3)
  platskarta      matchad med platskartan (kedjan som den körs utan extremmodell)
  somlos          platskarta blandad med MEPS rättad mot radarn (seamless.blend, sommodell "sömlös")

och på de inre rutorna (där flyttens avgångspunkt låg inom täckningen vid utgåvan, så att
inget har kommit in över randen) för nn_inre, bilinjar_inre och matchad_inre. nn_inre mot
radarn på samma rutor är radarns eget avtagande i lagrangeska koordinater (med kedjans
rörelse); skillnaden mellan nn och nn_inre är det som kommer in över randen.

Rörelsefältets deformation: för varje ledtid summan av Jacobianen för avgångspunkterna
(källytan per målruta) över rutorna där nn är minst 5 mm/h, och antalet sådana rutor.

Extremmodellen ingår inte: extremes.apply(rescale=False), som drift använder, lämnar fältet
orört (models/extremes.pkl finns inte i utcheckningen, och den ändrar bara sannolikheterna).

Summorna per dygn: /data/projektion/forlust/<dag>.npz.
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import domare as D  # noqa: E402

sys.path.insert(0, str(HERE.parent / "sverige"))
from data import radar_path  # noqa: E402
from knep import advect, model, radar, seamless  # noqa: E402

OUT = D.ROOT / "forlust"
TIMMAR = [3, 11, 17]                 # tre utgåvor per dygn ryms i nattens tid (cirka 40 s styck)
QS = D.SHOW                          # kvartarna 1, 2, 4, 8, 12, 20: 15, 30 min, 1, 2, 3, 5 h
STAGES = ["persistens", "nn", "bilinjar", "matchad_analys", "matchad", "platskarta", "somlos",
          "nn_inre", "bilinjar_inre", "matchad_inre"]
SPEC_STAGES = {"nn", "bilinjar", "matchad", "platskarta", "somlos"}  # formen (spektrum) bara för dessa


class Acc(D.Acc):
    """domare.Acc för ledtiderna QS, med spektrum bara när spec=True (det är det dyra)."""

    def __init__(self, res, spec):
        super().__init__(res)
        self.want_spec = spec
        L = len(QS)
        self.d = {k: np.zeros((L,) + v.shape[1:]) for k, v in self.d.items()}

    def add(self, i, f, o, m, old=None):
        if self.want_spec:
            return super().add(i, f, o, m, old)
        spec, self.spec = self.spec, None
        try:
            d = self.d
            f, o = np.where(m, np.nan_to_num(f), 0.0).astype(np.float32), np.where(m, o, 0.0).astype(np.float32)
            d["n"][i] += 1
            d["hist_f"][i] += D.wet_hist(f[m])
            d["hist_o"][i] += D.wet_hist(o[m])
            size = max(1, round(D.BLOCK_KM / self.res))
            bf, bo = D.block_max(f, m, size), D.block_max(o, m, size)
            d["bmax_f"][i] += np.histogram(bf[bf >= D.BMAX_WET], D.EDGES)[0]
            d["bmax_o"][i] += np.histogram(bo[bo >= D.BMAX_WET], D.EDGES)[0]
            d["area_f"][i] += [(f[m] >= t).sum() for t in D.AREA_THR]
            d["area_o"][i] += [(o[m] >= t).sum() for t in D.AREA_THR]
            d["vol"][i] += [f[m].sum(), o[m].sum()]
            for j, t in enumerate(D.CT_THR):
                d["ct"][i, j] += D.contingency(f, o, m, t)
            for j, (t, km) in enumerate(D.FSS_CASES):
                d["fss"][i, j] += D.fss_sums(f, o, m, t, int(round(km / self.res)) | 1)
        finally:
            self.spec = spec


def jacobian(mx, my):
    """det av d(mx, my)/d(x, y): källans yta per målruta."""
    mxy, mxx = np.gradient(mx)
    myy, myx = np.gradient(my)
    return mxx * myy - mxy * myx


def warm_state(t, ctx, sysm):
    """Platskartans tillstånd vid t som efter domarens uppvärmning: fc30 ur observe för t-85..t-35 min
    (giltiga t-55..t-5) och analyserna för t-55..t-5. Det är de par location_map använder vid t."""
    sysm.reset()
    for k in range(17, 0, -1):
        tau = t - k * D.STEP
        if k >= 7:
            sysm.observe(tau, ctx)
        else:
            a = ctx.frame(tau)
            if a is not None and ctx.history(tau) is not None:
                sysm.state.obs[tau.isoformat()] = a.astype(np.float32)
                sysm.state.prune(tau)
    return sysm.state


def run_issue(t, ctx, sysm, grid, meps, mstate, accs, jac):
    obs = ctx.history(t)
    motion = ctx.motion(t)
    if obs is None or motion is None:
        return False
    analysis = obs[-1]
    cov = np.isfinite(analysis)
    a = np.nan_to_num(analysis).astype(np.float32)
    steps = D.NQ * 3
    need = sorted({3 * (q - 1) + j for q in QS for j in range(3)})  # 5-minutersstegen i de bedömda kvartarna
    nn, bl, cv, J = {}, {}, {}, {}
    for k, (mx, my, outside) in enumerate(advect.displacements(motion, steps)):
        if k not in need:
            continue
        b = advect.warp(a, mx, my, outside, 1)
        n = advect.warp(a, mx, my, outside, 0)
        c = advect.warp(cov.astype(np.float32), mx, my, outside, 0, outval=0.0)
        b[~cov], n[~cov] = np.nan, np.nan
        bl[k], nn[k], cv[k], J[k] = b, n, c >= 0.5, jacobian(mx, my)
    state = warm_state(t, ctx, sysm)
    corr = model.location_map(state, t, analysis.shape)
    # MEPS: rättningen assimileras vid utgåvan som i sommodell (en gång per utgåva, tillståndet per dygn)
    mq = got = None
    if meps is not None:
        import verify5h as V
        got = meps.on(V.nwp.available(t, V.CYCLE), grid)
        if got is not None:
            run, on = got
            h = run.hour_ending(t)
            fs = [ctx_full_frame(ctx, t - k * D.STEP) for k in range(12)]
            fs = [f for f in fs if f is not None]
            if h is not None and len(fs) >= 9:
                mstate[0] = seamless.assimilate(mstate[0], run.run.isoformat(), on[h], np.mean(fs, axis=0), seamless.Params())
            mq = V.meps_quarters(meps, t, grid, interpolate=True)
    for i, q in enumerate(QS):
        o = ctx.quarter(t + q * D.Q)
        if o is None:
            continue
        m = cov & np.isfinite(o)
        ks = [3 * (q - 1) + j for j in range(3)]
        inner = m & np.all([cv[k] for k in ks], axis=0)
        f = {"persistens": analysis, "nn": np.mean([nn[k] for k in ks], 0), "bilinjar": np.mean([bl[k] for k in ks], 0)}
        ma = [model.cdf_match(bl[k], analysis) for k in ks]
        mt = [model.cdf_match(bl[k], nn[k]) for k in ks]
        f["matchad_analys"] = np.mean(ma, 0)
        f["matchad"] = np.mean(mt, 0)
        f["platskarta"] = np.mean([x * 10 ** (corr * min(1.0, (k + 1) / 6) / 10) for x, k in zip(mt, ks)], 0)
        f["platskarta"][~cov] = np.nan
        if mq is not None and mstate[0].qm is not None:
            lead = 15 * q - 7.5
            p = seamless.Params()
            f["somlos"] = seamless.blend(f["platskarta"], seamless.corrected(mq[q - 1], lead, mstate[0], p), lead, p)
        for s in STAGES:
            if s.endswith("_inre"):
                accs[s].add(i, f[s[:-5]], o, inner)
            elif s in f:
                accs[s].add(i, f[s], o, m)
        for k in ks:
            w = (nn[k] >= 5.0) & m
            jac[i] += [J[k][w].sum(), w.sum(), np.log(np.maximum(J[k][w], 1e-3)).sum()]
    return True


def ctx_full_frame(ctx, t):
    return ctx.frame(t)


def run_day(day: str) -> None:
    path = OUT / f"{day}.npz"
    if path.exists():
        return
    import verify5h as V
    started = time.monotonic()
    ctx = D.Ctx(day, 2)
    sysm = D.KedjaOm()
    accs = {s: Acc(2.0, s in SPEC_STAGES) for s in STAGES}
    jac = np.zeros((len(QS), 3))
    d0 = datetime.fromisoformat(day).replace(tzinfo=UTC)
    grid = None
    for k in range(288):
        p = radar_path(d0 + k * D.STEP)
        if p.exists():
            try:
                grid = radar.read_rain(p)[1]
                break
            except Exception:  # noqa: BLE001
                pass
    meps, mstate, n = V.Meps(), [seamless.State()], 0
    for h in TIMMAR:
        t = d0 + timedelta(hours=h)
        ctx.forget(t - timedelta(hours=2))
        if ctx.frame(t) is None:
            continue
        n += run_issue(t, ctx, sysm, grid, meps, mstate, accs, jac)
        print(f"  {day} {h:02d}: {time.monotonic() - started:.0f} s", flush=True)
    out = {f"{s}__{k}": v for s, a in accs.items() for k, v in a.d.items()}
    out |= {"jac": jac, "issues": np.array(n), "seconds": np.array(time.monotonic() - started)}
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp.npz")
    np.savez_compressed(tmp, **out)
    tmp.replace(path)
    print(f"{day}: {n} utgåvor på {time.monotonic() - started:.0f} s", flush=True)


# ---------- tabellen ----------

MÅTT = ["q99", "q99.9", "yta5", "yta10", "yta20", "volym", "blockmax_q50", "blockmax_q90", "blockmax_antal",
        "fss5_30", "fss10_30", "csi5", "sedi10", "fss1_30", "form8_16", "form4_8"]


def load_all(days):
    per = {}
    for d in days:
        p = OUT / f"{d}.npz"
        if p.exists():
            per[d] = dict(np.load(p))
    return per


def stage_sums(per, days, s, w=None):
    w = np.ones(len(days)) if w is None else w
    out = {}
    for k in D.SUMKEYS:
        key = f"{s}__{k}"
        if key not in per[days[0]]:
            return None
        out[k] = sum(wi * per[d][key] for wi, d in zip(w, days))
    return out


def stage_scores(per, days, s, w=None):
    ss = stage_sums(per, days, s, w)
    if ss is None or ss["n"].sum() == 0:
        return None
    out = {m: D.METRICS[m][0](ss) for m in MÅTT}
    if s not in SPEC_STAGES:  # spektrum räknades inte: formen saknas (inte 0)
        for m in ("form4_8", "form8_16"):
            out[m] = np.full(len(QS), np.nan)
    return out


def table(nboot: int = 1000) -> str:
    days = [d for d in D.mode_days("traning") if (OUT / f"{d}.npz").exists()]
    per = load_all(days)
    lines = [f"# Förlusten steg för steg, {len(days)} träningsdygn, "
             f"{int(sum(per[d]['issues'] for d in days))} utgåvor (kl {', '.join(f'{h:02d}' for h in TIMMAR)}), 2 km", ""]
    head = "| steg | " + " | ".join(f"{15 * q} min" if q < 4 else f"{q // 4} h" for q in QS) + " |"
    sep = "|---|" + "---|" * len(QS)
    sc = {s: stage_scores(per, days, s) for s in STAGES}
    rng = np.random.default_rng(0)
    boots = []
    for _ in range(nboot):
        w = np.bincount(rng.integers(0, len(days), len(days)), minlength=len(days)).astype(float)
        boots.append({s: stage_scores(per, days, s, w) for s in STAGES})
    lines += ["Log kvot mot radarn (0 är rätt) för konserveringen och formen; poäng för FSS, CSI och SEDI.",
              "Inom parentes 95 %-intervallet ur bootstrap över dygnen.", ""]
    for m in MÅTT:
        lines += [f"## {m}", "", head, sep]
        for s in STAGES:
            if sc[s] is None:
                continue
            v = sc[s][m]
            bs = np.array([b[s][m] for b in boots if b[s] is not None])
            lo, hi = np.nanpercentile(bs, [2.5, 97.5], axis=0)
            cells = [("." if not np.isfinite(x) else f"{x:+.3f} ({a:+.2f}, {b:+.2f})") for x, a, b in zip(v, lo, hi)]
            lines.append(f"| {s} | " + " | ".join(cells) + " |")
        lines.append("")
    # stegens bidrag: differensen i log kvot mellan på varandra följande steg, med intervall
    lines += ["## Stegens bidrag (ändringen i log kvot från föregående steg)", ""]
    pairs = [("radarns avtagande, lagrangeskt (radarn mot nn, inre rutor)", None, "nn_inre"),
             ("in över randen (nn mot nn_inre)", "nn_inre", "nn"),
             ("bilinjär flytt (bilinjar mot nn)", "nn", "bilinjar"),
             ("matchning mot nn (matchad mot bilinjar)", "bilinjar", "matchad"),
             ("målet utan det som lämnat området (matchad mot matchad_analys)", "matchad_analys", "matchad"),
             ("platskartan (platskarta mot matchad)", "matchad", "platskarta"),
             ("MEPS-blandningen (somlos mot platskarta)", "platskarta", "somlos")]
    for m in ["yta5", "yta10", "yta20", "volym", "q99.9", "blockmax_q90", "blockmax_antal", "form8_16", "form4_8"]:
        lines += [f"### {m}", "", head.replace("steg", "bidrag"), sep]
        for name, a, b in pairs:
            if sc[b] is None or (a and sc[a] is None):
                continue
            val = lambda S: S[b][m] - (S[a][m] if a else 0.0)
            v = val(sc)
            bs = np.array([val(B) for B in boots if B[b] is not None and (a is None or B[a] is not None)])
            lo, hi = np.nanpercentile(bs, [2.5, 97.5], axis=0)
            cells = [("." if not np.isfinite(x) else f"{x:+.3f} ({p:+.2f}, {r:+.2f})") for x, p, r in zip(v, lo, hi)]
            lines.append(f"| {name} | " + " | ".join(cells) + " |")
        lines.append("")
    jac = sum(per[d]["jac"] for d in days)
    lines += ["## Rörelsefältets deformation där nn ≥ 5 mm/h", "",
              "Medel av Jacobianen (källyta per målruta; under 1 betyder att flytten sträcker ut ytan) "
              "och medel av dess logaritm.", "", head.replace("steg", "mått"), sep,
              "| medel J | " + " | ".join(f"{a / max(b, 1):.3f}" for a, b, _ in jac) + " |",
              "| medel log J | " + " | ".join(f"{c / max(b, 1):+.3f}" for _, b, c in jac) + " |", ""]
    secs = [float(per[d]["seconds"]) for d in days]
    lines.append(f"Körtid {sum(secs) / 60:.0f} min processortid, {np.mean(secs):.0f} s per dygn.")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vad", choices=["kör", "tabell"])
    ap.add_argument("--dagar", type=int, default=None)
    ap.add_argument("--dag", nargs="*", default=None)
    ap.add_argument("--procs", type=int, default=2)
    a = ap.parse_args()
    if a.vad == "tabell":
        text = table()
        (D.RESULTS / "forlust.md").write_text(text)
        print(text)
        return
    days = a.dag or D.mode_days("traning")[: a.dagar]
    if a.procs <= 1:
        for d in days:
            run_day(d)
    else:
        from multiprocessing import get_context
        with get_context("fork").Pool(a.procs, maxtasksperchild=1) as pool:
            list(pool.imap_unordered(run_day, days))


if __name__ == "__main__":
    main()
