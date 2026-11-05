"""Uppgift 2 (2026-11-05): den sömlösa prognosen till 5 h som system i domaren, och varianter som
håller kvar topparna i blandningen med MEPS.

    uv run python experiments/projektion/domare.py kör --läge validering_meps --system somlos:Somlos
    uv run python experiments/projektion/somlos.py spara        # kedjan i läget snabb, sparad (4 km)
    uv run python experiments/projektion/somlos.py sök          # slumpsökning med successiv halvering
    uv run python experiments/projektion/somlos.py tid          # körtiden per utgåva på 2 km

Systemet Somlos är kedjan blandad med MEPS rättad mot radarn, som sommodell.blended(P, "rättad")
i experiments/sverige (form5h "sömlös") och forlust.py:

  * kedjan: driftens sparade prognoser (/data/sverige/kedja) på 2 km, annars kedjan körd om här
    och sparad av KedjaSpar (läget snabb, 4 km) under /data/projektion/cache/somlos/
  * MEPS: körningen som fanns vid utgåvan (data.CYCLE = 6 h, 2,5 h fördröjning), interpolerad
    i tiden mitt i varje kvart (seamless.meps_at), på domarens rutnät
  * rättningen (seamless.assimilate) varje hel timme från dygnets början fram till utgåvan, med
    radarns senaste timme, som verifieringen gör; tillståndet börjar om varje dygn
  * blandningen per kvart med ledtiden mitt i kvarten, 15 k − 7,5 min

Saknas MEPS (körningen finns inte eller rättningen har ingen kvantilavbildning än) blir
prognosen kedjan, som i drift när MEPS inte går att hämta.

Varianterna (Var) ändrar bara blandningen, blend_v; med standardvärdena är den exakt
seamless.blend (test_somlos.py):

  t50_q     ledtiden (min) där kedjans vikt i fördelningen (kvantilerna) är 0,5; standard t50_small
  top_w     kedjans lägsta vikt i fördelningen för de höga värdena (0 = av)
  top_thr   mm/h: kedjans värden över top_thr får vikten top_w (övergång från top_thr/2 till top_thr·2)
  fine_lam  så mycket av kedjans små skalor (under fine_km) som läggs till efter blandningen, gånger 1 − ws
  fine_km   skalgränsen för de små skalorna
  t50_fine  en tredje skala: kedjans vikt för skalorna under fine_km har t50_fine (None = två skalor)
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import domare as D  # noqa: E402

sys.path.insert(0, str(HERE.parent / "sverige"))
from data import CYCLE, meps_path, radar_path  # noqa: E402
from knep import nwp, radar, render, seamless  # noqa: E402

CACHE = D.CACHE / "somlos"
NQ = D.NQ


# ---------- blandningen ----------

@dataclass(frozen=True)
class Var:
    t50_small: float = 60.0
    t50_large: float = 150.0
    shape: float = 2.5
    sigma_km: float = 30.0
    t50_q: float | None = None
    top_w: float = 0.0
    top_thr: float = 5.0
    fine_lam: float = 0.0
    fine_km: float = 8.0
    t50_fine: float | None = None

    def params(self, res_km: float) -> seamless.Params:
        return replace(seamless.Params(), t50_small=self.t50_small, t50_large=self.t50_large, shape=self.shape,
                       sigma_km=self.sigma_km, res_km=float(res_km))

    def tag(self) -> str:
        base = Var()
        return "_".join(f"{k}={v:g}" if isinstance(v, float) else f"{k}={v}"
                        for k, v in asdict(self).items() if v != getattr(base, k)) or "bas"


def blend_v(chain_f: np.ndarray, meps_f: np.ndarray, lead: float, p: seamless.Params, v: Var) -> np.ndarray:
    """seamless.blend med variantens val (se modulens text)."""
    g = seamless.gaussian_filter
    w = lambda t50: seamless.weight(lead, t50, p.shape)
    ws, wl = w(p.t50_small), w(p.t50_large)
    has_chain = np.isfinite(chain_f)
    c = np.where(has_chain, chain_f, meps_f)
    cz, m = np.nan_to_num(c), np.nan_to_num(meps_f)
    s = p.sigma_km / p.res_km
    cl, ml = g(cz, s), g(m, s)
    if v.t50_fine is None:
        out = wl * cl + (1 - wl) * ml + ws * (cz - cl) + (1 - ws) * (m - ml)
    else:
        sf = v.fine_km / p.res_km
        cf, mf = g(cz, sf), g(m, sf)
        wf = w(v.t50_fine)
        out = wl * cl + (1 - wl) * ml + ws * (cf - cl) + (1 - ws) * (mf - ml) + wf * (cz - cf) + (1 - wf) * (m - mf)
    if v.fine_lam > 0:
        out = out + v.fine_lam * (1 - ws) * (cz - g(cz, v.fine_km / p.res_km))
    out = np.maximum(out, 0)
    if p.match:
        ok = has_chain & np.isfinite(meps_f)
        sc, sm = np.sort(chain_f[ok]), np.sort(meps_f[ok])
        wq = w(v.t50_q) if v.t50_q is not None else ws
        if v.top_w > 0:
            ramp = np.clip(np.log(np.maximum(sc, 1e-6) / (v.top_thr / 2)) / np.log(4.0), 0.0, 1.0)
            wv = wq + (max(wq, v.top_w) - wq) * ramp
            target = np.sort(wv * sc + (1 - wv) * sm)
        else:
            target = wq * sc + (1 - wq) * sm
        order = np.argsort(out[ok] + 1e-3 * g(out, 2.0)[ok], kind="stable")
        vals = np.empty(order.size, np.float32)
        vals[order] = target
        out = out.astype(np.float32)
        out[ok] = vals
    out[~has_chain & ~np.isfinite(meps_f)] = np.nan
    return out.astype(np.float32)


# ---------- systemen ----------

def chain_cache(res: int, day: str, t: datetime) -> Path:
    return CACHE / f"{res}km" / day / f"{t:%H%M}.npz"


class KedjaSpar(D.KedjaOm):
    """domare.KedjaOm som dessutom sparar prognosen (värdekoder) för Somlos."""

    def forecast(self, t, ctx):
        fc = super().forecast(t, ctx)
        if fc is not None:
            p = chain_cache(ctx.res, ctx.day, t)
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_suffix(".tmp.npz")
            np.savez_compressed(tmp, codes=np.stack([render.encode_values(x) for x in fc]))
            tmp.replace(p)
        return fc


def load_chain(ctx, t):
    p = D.CHAIN_DIR / ctx.day / f"{t:%H%M}.npz"
    if ctx.res == 2 and p.exists():
        return render.decode_values(np.load(p)["codes"])
    p = chain_cache(ctx.res, ctx.day, t)
    if p.exists():
        return render.decode_values(np.load(p)["codes"])
    return None


def day_grid(day: str):
    d0 = datetime.fromisoformat(day).replace(tzinfo=UTC)
    for k in range(288):
        p = radar_path(d0 + k * radar.STEP)
        if p.exists():
            try:
                return radar.read_rain(p)[1]
            except Exception:  # noqa: BLE001
                pass
    return None


class Somlos(D.System):
    """Kedjan blandad med den rättade MEPS (se modulens text). var: blandningens val."""

    name = "somlos"
    var = Var()

    def __init__(self, var: Var | None = None):
        if var is not None:
            self.var = var
        self.meps_used = 0

    def reset(self):
        self.st = seamless.State()
        self.last = None       # senaste hela timmen som assimilerats
        self.runs = {}         # körning -> (Run, timsummor på domarens rutnät) eller None
        self.grid = None

    def _on(self, run_t: datetime, ctx):
        if run_t not in self.runs:
            p = meps_path(run_t)
            if not p.exists():
                self.runs[run_t] = None
            else:
                r = nwp.Run.load(p)
                on = r.on(self.grid)
                self.runs[run_t] = (r, np.stack([D.coarsen(x, ctx.f) for x in on]))
            while len(self.runs) > 3:
                self.runs.pop(next(iter(self.runs)))
        return self.runs[run_t]

    def _radar_hour(self, t, ctx):
        fs = [ctx.frame(t - k * D.STEP) for k in range(12)]
        fs = [f for f in fs if f is not None]
        return np.mean(fs, axis=0) if len(fs) >= 9 else None

    def _assimilate(self, t, ctx, p):
        d0 = datetime.fromisoformat(ctx.day).replace(tzinfo=UTC)
        h = d0 if self.last is None else self.last + timedelta(hours=1)
        while h <= t:
            got = self._on(nwp.available(h, CYCLE), ctx)
            if got is not None:
                run, on = got
                k = run.hour_ending(h)
                rh = self._radar_hour(h, ctx)
                if k is not None and rh is not None:
                    self.st = seamless.assimilate(self.st, run.run.isoformat(), on[k], rh, p)
            self.last = h
            h += timedelta(hours=1)

    def forecast(self, t, ctx):
        chain = load_chain(ctx, t)
        if chain is None:
            return None
        if self.grid is None:
            self.grid = day_grid(ctx.day)
        p = self.var.params(ctx.res)
        self._assimilate(t, ctx, p)
        got = self._on(nwp.available(t, CYCLE), ctx)
        if got is None or self.st.qm is None:
            return chain
        run, on = got
        out = np.empty_like(chain)
        for k in range(NQ):
            lead = 15 * (k + 1) - 7.5
            mq = seamless.meps_at(on, run.run, t + (k + 1) * D.Q - timedelta(minutes=5))
            out[k] = blend_v(chain[k], seamless.corrected(mq, lead, self.st, p), lead, p, self.var)
        self.meps_used += 1
        return out


def variant_system(var: Var) -> Somlos:
    s = Somlos(var)
    s.name = "somlos_" + var.tag()
    return s


# ---------- sökningen på träningsdagarna (läget snabb) ----------

SÖK = D.OUT / "snabb"
KONS = ["q99", "q99.9", "yta5", "yta10", "yta20", "volym", "blockmax_q50", "blockmax_q90"]
TRÄFF = ["fss5_10", "fss5_30", "fss10_10", "fss10_30", "csi5", "sedi5", "sedi10"]
SPÄRR = ["fss1_30", "csi1"]
FORM = ["form4_8", "form8_16"]
FROM_LEAD = [8, 12, 20]   # kvartar: 2, 3 och 5 h, där blandningen verkar (i SHOW)
ALL_LEAD = D.SHOW


def objective(sc: dict, base: dict) -> tuple[float, dict]:
    """Lägre är bättre. Medel av |log kvot| för konserveringen på 2, 3 och 5 h, plus straff för
    träff och spärrar som blir sämre än basen (mer än 0,002) på alla ledtider i SHOW, och för
    formen (|log kvot| mer än 0,02 sämre)."""
    li = [D.LEADS.index(k) for k in FROM_LEAD]
    ai = [D.LEADS.index(k) for k in ALL_LEAD]
    kons = float(np.nanmean([np.abs(sc[m][i]) for m in KONS for i in li]))
    pen = 0.0
    for m in TRÄFF + SPÄRR:
        for i in ai:
            d = base[m][i] - sc[m][i]
            if np.isfinite(d) and d > 0.002:
                pen += 5 * (d - 0.002)
    for m in FORM:
        for i in ai:
            d = abs(sc[m][i]) - abs(base[m][i])
            if np.isfinite(d) and d > 0.02:
                pen += 0.2 * (d - 0.02)
    return kons + pen, {"kons": kons, "straff": pen}


def run_variant(var: Var, days: list[str], procs: int = 2) -> str:
    name = "somlos_" + var.tag()
    from multiprocessing import get_context

    jobs = [(var, d, name) for d in days]
    with get_context("fork").Pool(procs, maxtasksperchild=4) as pool:
        list(pool.imap_unordered(_var_job, jobs))
    return name


def _var_job(args):
    var, day, name = args
    path = SÖK / name / f"{day}.npz"
    if path.exists():
        return
    D.SYSTEMS[name] = lambda var=var: Somlos(var)
    D.run_day("snabb", day, name)


def sample(rng) -> Var:
    """En slumpvariant: varje grupp av val är med med sannolikheten 0,5."""
    kw = {}
    if rng.random() < 0.5:
        kw |= dict(t50_small=float(rng.choice([45, 60, 90, 120, 180])), t50_large=float(rng.choice([120, 150, 240, 360])),
                   shape=float(rng.choice([1.5, 2.5, 4.0])))
    if rng.random() < 0.5:
        kw |= dict(t50_q=float(rng.choice([90, 120, 180, 300, 600])))
    if rng.random() < 0.5:
        kw |= dict(top_w=float(rng.choice([0.3, 0.5, 0.7, 1.0])), top_thr=float(rng.choice([2, 5, 10])))
    if rng.random() < 0.5:
        kw |= dict(fine_lam=float(rng.choice([0.25, 0.5, 1.0])), fine_km=float(rng.choice([8, 16])))
    elif rng.random() < 0.5:
        kw |= dict(t50_fine=float(rng.choice([30, 45, 120, 240])), fine_km=float(rng.choice([8, 16])))
    return Var(**kw)


def search(n: int, seed: int, procs: int, log: Path) -> None:
    rng = np.random.default_rng(seed)
    hand = [Var(), Var(t50_q=300.0), Var(top_w=1.0, top_thr=5.0), Var(top_w=0.5, top_thr=5.0),
            Var(fine_lam=0.5, fine_km=8.0), Var(t50_fine=240.0, fine_km=8.0), Var(t50_small=120.0, t50_large=240.0)]
    cands = list(dict.fromkeys(hand + [sample(rng) for _ in range(n)]))
    days_all = D.FAST_DAYS
    rounds = [(days_all[:3], None), (days_all, 6)]
    results = {}
    for r, (days, keep) in enumerate(rounds):
        if keep is not None:
            ranked = sorted(cands[1:], key=lambda v: results[v][0])
            cands = [Var()] + ranked[:keep]
        base_name = run_variant(Var(), days, procs)
        base = D.scores(D.load("snabb", base_name, days), days)
        for v in cands:
            s = time.monotonic()
            name = run_variant(v, days, procs)
            sc = D.scores(D.load("snabb", name, days), days)
            results[v] = objective(sc, base)
            with log.open("a") as fh:
                fh.write(json.dumps({"runda": r, "dygn": len(days), "var": v.tag(), "mål": results[v][0],
                                     **results[v][1], "s": round(time.monotonic() - s)}) + "\n")
            print(f"runda {r} {v.tag()}: {results[v][0]:.4f} {results[v][1]} ({time.monotonic() - s:.0f} s)", flush=True)
    best = sorted(cands[1:], key=lambda v: results[v][0])
    with log.open("a") as fh:
        fh.write(json.dumps({"bäst": [v.tag() for v in best]}) + "\n")


# ---------- körtiden på hela rutnätet ----------

def timing(day: str, hour: int) -> None:
    """Kedjan (model.Chain.run, 60 steg) och blandningen av alla 60 bilder med MEPS, som
    seamless.run_operational gör, på 2 km för en utgåva; utan hämtning och rendering."""
    from knep import model

    ctx = D.Ctx(day, 2)
    t = datetime.fromisoformat(day).replace(tzinfo=UTC) + timedelta(hours=hour)
    sysm = D.KedjaOm()
    sysm.reset()
    for k in range(18, 0, -1):
        sysm.observe(t - k * D.STEP, ctx)
    obs = ctx.history(t)
    s0 = time.monotonic()
    ctx.motions.pop(t, None)
    p_m = ctx.motion_dir / f"{t:%H%M}.npz"
    if p_m.exists():
        p_m.unlink()                        # rörelsen räknas om, som i drift
    motion = ctx.motion(t)
    s1 = time.monotonic()
    res = sysm.chain.run(obs, t, 60, sysm.state, motion=motion)
    s2 = time.monotonic()
    grid = day_grid(day)
    run_t = nwp.available(t, CYCLE)
    r = nwp.Run.load(meps_path(run_t))
    on = r.on(grid)
    s3 = time.monotonic()
    p = seamless.Params()
    st = seamless.assimilate(seamless.State(), run_t.isoformat(), seamless.meps_at(on, run_t, t),
                             np.nanmean(obs[-12:], axis=0), seamless._per_cycle(p))
    s4 = time.monotonic()
    out = [seamless.blend(f, seamless.corrected(seamless.meps_at(on, run_t, t + timedelta(minutes=5 * (k + 1))),
                                                5 * (k + 1) - 2.5, st, p), 5 * (k + 1) - 2.5, p)
           for k, f in enumerate(res.rain)]
    s5 = time.monotonic()
    print(json.dumps({"dag": day, "timme": hour, "rutnät": list(obs.shape[1:]), "rörelse_s": round(s1 - s0, 1),
                      "kedjan_s": round(s2 - s1, 1), "meps_omprojicering_s": round(s3 - s2, 1),
                      "assimilering_s": round(s4 - s3, 1), "blandning_60_s": round(s5 - s4, 1),
                      "summa_s": round(s5 - s0, 1), "bilder": len(out)}), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vad", choices=["spara", "sök", "tid"])
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--procs", type=int, default=2)
    ap.add_argument("--dag", default="2021-05-17")
    ap.add_argument("--timme", type=int, default=15)
    a = ap.parse_args()
    if a.vad == "spara":
        D.SYSTEMS["kedja_spar"] = KedjaSpar
        D.run("snabb", "kedja_spar", a.procs)
    elif a.vad == "sök":
        search(a.n, a.seed, a.procs, D.RESULTS / "somlos_sok.jsonl")
    else:
        timing(a.dag, a.timme)


if __name__ == "__main__":
    main()
