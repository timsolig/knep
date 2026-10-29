"""Sömlös prognos 0 till 5 h: kedjan glider över i MEPS, rättad mot radarn löpande.

Kedjan (model.Chain) är bäst de första timmarna men vet inget om tillväxt och nya celler. MEPS
vet det men har fel i läge och mängd. Varje cykel assimileras den senaste radartimmen i en
rättning av MEPS:

  1. Läge: förskjutningen som bäst flyttar MEPS-timmen fram till nu på radarns senaste timme,
     med optiskt flöde (Farnebäck) på grova, utjämnade fält. Rättningen avtar med ledtiden.
  2. Mängd: kvantilavbildning från MEPS-timmen till radartimmen över de våta pixlarna.

Båda rättningarna utjämnas mellan cyklerna i ett tillstånd (exponentiellt glidande medel), så
att en enskild radarbild inte styr, och nollställs när MEPS byter körning.

Blandningen görs per skala: fälten delas i stora skalor (gaussiskt utjämnade) och resten, och
kedjans vikt avtar med ledtiden snabbare för de små skalorna än för de stora. Sist får det
blandade fältet en värdefördelning mellan kedjans och MEPS:s (kvantilerna viktade med samma
vikt), så att blandningen inte smetar ut topparna.

Allt räknas på radarns rutnät. Utanför radarns täckning finns bara MEPS.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np


from . import advect


def gaussian_filter(x, sigma):
    """Gaussisk utjämning med OpenCV (mångdubbelt snabbare än scipy på Pi:n), speglad rand."""
    x = np.asarray(x, np.float32)
    k = int(2 * round(3 * sigma) + 1)
    return cv2.GaussianBlur(x, (k, k), sigma, borderType=cv2.BORDER_REFLECT)


@dataclass
class Params:
    t50_small: float = 60.0     # min: ledtid där kedjans vikt för de små skalorna är 0,5
    t50_large: float = 150.0    # min: samma för de stora skalorna
    shape: float = 2.5          # brantheten i viktkurvan
    sigma_km: float = 30.0      # skalgränsen
    shift_tau: float = 240.0    # min: lägesrättningens avtagande med ledtiden
    shift_max_km: float = 80.0
    alpha: float = 0.3          # vikt för den nya skattningen i det glidande medlet
    res_km: float = 2.0
    correct_amount: bool = True
    correct_shift: bool = True
    match: bool = True


@dataclass
class State:
    run: str = ""
    dx: np.ndarray | None = None
    dy: np.ndarray | None = None
    qm: np.ndarray | None = None   # kvantilavbildningen: (MEPS-värden, radarvärden) på fasta sannolikheter


PROBS = np.linspace(0.0, 0.99, 41)  # inte högre: radarns högsta värden är ofta klotter eller hagel
FACTOR = (0.25, 4.0)                 # mängdrättningen ändrar ett värde högst så här mycket


def weight(lead_min: float, t50: float, shape: float) -> float:
    """Kedjans vikt: 1 vid ledtid 0, 0,5 vid t50, och mot 0 därefter."""
    return float(1.0 / (1.0 + (max(lead_min, 0.0) / t50) ** shape))


def _db(x):
    return 10 * np.log10(np.maximum(np.nan_to_num(x), 0.1))


def estimate_shift(meps_now: np.ndarray, radar_now: np.ndarray, p: Params) -> tuple[np.ndarray, np.ndarray]:
    """Förskjutning (dx, dy) i pixlar så att meps(x + d) liknar radarn(x), utjämnad och begränsad."""
    k = 4  # optiskt flöde på 8 km-rutor
    ok = np.isfinite(radar_now)
    a = gaussian_filter(np.where(ok, _db(meps_now), -10), 2)[::k, ::k]
    b = gaussian_filter(np.where(ok, _db(radar_now), -10), 2)[::k, ::k]
    to8 = lambda x: np.clip((x + 10) / 60 * 255, 0, 255).astype(np.uint8)
    flow = cv2.calcOpticalFlowFarneback(to8(b), to8(a), None, 0.5, 4, 15, 5, 7, 1.5, 0)  # b(x) ≈ a(x + flow)
    fx = cv2.resize(flow[..., 0], radar_now.shape[::-1], interpolation=cv2.INTER_LINEAR) * k
    fy = cv2.resize(flow[..., 1], radar_now.shape[::-1], interpolation=cv2.INTER_LINEAR) * k
    s = 25.0 / p.res_km
    fx, fy = gaussian_filter(fx, s), gaussian_filter(fy, s)
    mag = np.hypot(fx, fy)
    lim = p.shift_max_km / p.res_km
    f = np.where(mag > lim, lim / np.maximum(mag, 1e-6), 1.0)
    return (fx * f).astype(np.float32), (fy * f).astype(np.float32)


def shift(field_: np.ndarray, dx: np.ndarray, dy: np.ndarray, scale: float = 1.0) -> np.ndarray:
    h, w = field_.shape
    gx, gy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    scale = float(scale)  # Python-tal, så att kartorna förblir float32 som cv2.remap kräver
    mx, my = gx + dx * scale, gy + dy * scale
    out = advect.warp(np.nan_to_num(field_).astype(np.float32), mx, my, np.zeros(field_.shape, bool), 1)
    out[~np.isfinite(field_)] = np.nan
    return out


def estimate_amount(meps_now: np.ndarray, radar_now: np.ndarray) -> np.ndarray:
    """Kvantilerna för MEPS och radarn över pixlarna där någon av dem är våt."""
    ok = np.isfinite(radar_now) & np.isfinite(meps_now)
    wet = ok & ((meps_now > 0.1) | (radar_now > 0.1))
    if wet.sum() < 500:
        return np.stack([PROBS * 0, PROBS * 0])
    return np.stack([np.quantile(meps_now[wet], PROBS), np.quantile(radar_now[wet], PROBS)]).astype(np.float32)


def apply_amount(f: np.ndarray, qm: np.ndarray) -> np.ndarray:
    """Kvantilavbildningen som en faktor per värde, begränsad till FACTOR; över den högsta
    kvantilen gäller faktorn där, och under den lägsta våta kvantilen faktorn där."""
    src, dst = qm
    wet = src > 0.05
    if wet.sum() < 3:
        return f
    src, dst = src[wet], dst[wet]
    src = np.maximum.accumulate(src + np.arange(len(src)) * 1e-6)
    ratio = np.clip(dst / src, *FACTOR)
    x = np.nan_to_num(f)
    out = x * np.interp(x, src, ratio)  # np.interp håller kvoten konstant utanför kvantilerna
    out[~np.isfinite(f)] = np.nan
    return out.astype(np.float32)


def assimilate(state: State, run_id: str, meps_now: np.ndarray, radar_now: np.ndarray, p: Params) -> State:
    """Uppdatera rättningen av MEPS med senaste radartimmen."""
    if state.run != run_id:
        state = State(run=run_id)
    dx, dy = estimate_shift(meps_now, radar_now, p) if p.correct_shift else (None, None)
    qm = estimate_amount(meps_now, radar_now)
    a = p.alpha
    if state.dx is None or dx is None:
        state.dx, state.dy = dx, dy
    else:
        state.dx, state.dy = a * dx + (1 - a) * state.dx, a * dy + (1 - a) * state.dy
    state.qm = qm if state.qm is None else a * qm + (1 - a) * state.qm
    return state


def corrected(meps_f: np.ndarray, lead_min: float, state: State, p: Params) -> np.ndarray:
    f = meps_f
    if p.correct_shift and state.dx is not None:
        f = shift(f, state.dx, state.dy, np.exp(-lead_min / p.shift_tau))
    if p.correct_amount and state.qm is not None:
        f = apply_amount(f, state.qm)
    return f


def _quantiles(f: np.ndarray, n: int) -> np.ndarray:
    v = f[np.isfinite(f)]
    return np.quantile(v, np.linspace(0, 1, n)) if v.size else np.zeros(n)


def blend(chain_f: np.ndarray, meps_f: np.ndarray, lead_min: float, p: Params) -> np.ndarray:
    """En ledtids blandning av kedjan och den rättade MEPS-prognosen."""
    ws, wl = weight(lead_min, p.t50_small, p.shape), weight(lead_min, p.t50_large, p.shape)
    has_chain = np.isfinite(chain_f)
    c = np.where(has_chain, chain_f, meps_f)  # utanför radarn: bara MEPS
    m = np.nan_to_num(meps_f)
    s = p.sigma_km / p.res_km
    cl, ml = gaussian_filter(np.nan_to_num(c), s), gaussian_filter(m, s)
    out = wl * cl + (1 - wl) * ml + ws * (np.nan_to_num(c) - cl) + (1 - ws) * (m - ml)
    out = np.maximum(out, 0)
    if p.match:
        # fördelningen mellan kedjans och MEPS:s, med kedjans vikt för de små skalorna
        n = 2001
        target = ws * _quantiles(c, n) + (1 - ws) * _quantiles(m, n)
        ok = np.isfinite(out)
        order = np.argsort(out[ok] + 1e-3 * gaussian_filter(out, 2.0)[ok], kind="stable")
        vals = np.empty(order.size, np.float32)
        vals[order] = target[np.minimum((np.arange(order.size) + 0.5) / order.size * n, n - 1).astype(int)]
        out = out.astype(np.float32)
        out[ok] = vals
    out[~has_chain & ~np.isfinite(meps_f)] = np.nan
    return out.astype(np.float32)


# ---------- MEPS i tiden ----------

def meps_at(on: np.ndarray, run, t, interpolate: bool = True) -> np.ndarray:
    """MEPS-intensiteten (mm/h) för de 5 eller 15 minuterna före t.

    on: körningens timsummor på radarns rutnät, timme k = (run + k, run + k + 1]. Med interpolate
    tolkas timsumman som intensiteten mitt i timmen och interpoleras linjärt däremellan, så att
    prognosen inte hoppar vid hela timmar; annars gäller timsumman hela timmen.
    """
    hours = (t - run).total_seconds() / 3600
    if not interpolate:
        k = int(np.ceil(hours)) - 1
        return on[k] if 0 <= k < len(on) else np.full(on.shape[1:], np.nan, np.float32)
    x = hours - 0.5
    k = int(np.floor(x))
    if k < 0:
        return on[0]
    if k >= len(on) - 1:
        return on[-1] if k < len(on) else np.full(on.shape[1:], np.nan, np.float32)
    w = x - k
    return ((1 - w) * on[k] + w * on[k + 1]).astype(np.float32)


# ---------- drift ----------

def _per_cycle(p: Params, minutes: float = 5.0) -> Params:
    """Vikten i det glidande medlet är satt per timme (verifieringen assimilerar varje timme);
    i drift assimileras var 5:e minut, med samma minne."""
    from dataclasses import replace

    return replace(p, alpha=1 - (1 - p.alpha) ** (minutes / 60))


def save_state(st: State, path) -> None:
    arrays = {"run": np.array(st.run)}
    if st.dx is not None:
        arrays |= {"dx": st.dx.astype(np.float16), "dy": st.dy.astype(np.float16)}
    if st.qm is not None:
        arrays["qm"] = st.qm
    tmp = path.with_suffix(".tmp.npz")
    np.savez_compressed(tmp, **arrays)
    tmp.replace(path)


def load_state(path) -> State:
    if not path.exists():
        return State()
    d = np.load(path)
    return State(str(d["run"]), d["dx"].astype(np.float32) if "dx" in d else None,
                 d["dy"].astype(np.float32) if "dy" in d else None, d["qm"] if "qm" in d else None)


def run_operational(meps_dir, state_path, session, grid, now, obs: np.ndarray, fc: np.ndarray,
                    p: Params | None = None) -> tuple[np.ndarray, dict]:
    """Blanda kedjans 5-minutersprognos fc med senaste MEPS-körning, rättad mot radarn.

    Körningen hämtas en gång (cirka 2 MB) och sparas på radarns rutnät i meps_dir.
    """
    from datetime import timedelta

    from . import nwp

    p = p or Params()
    meps_dir.mkdir(parents=True, exist_ok=True)
    run_t = nwp.latest_run(session)
    path = meps_dir / f"meps_{run_t:%Y%m%dT%H}.npz"
    on_path = meps_dir / f"meps_{run_t:%Y%m%dT%H}.grid.npy"
    if not on_path.exists():
        rows, cols = nwp.box(grid)
        r = nwp.fetch(session, run_t, rows, cols)
        r.save(path)
        np.save(on_path, r.on(grid).astype(np.float16))
        for old in sorted(meps_dir.glob("meps_*"))[:-4]:  # förra körningen och den här
            old.unlink()
    on = np.load(on_path).astype(np.float32)
    radar_hour = np.nanmean(obs[-12:], axis=0) if len(obs) >= 9 else obs[-1]
    st = assimilate(load_state(state_path), run_t.isoformat(), meps_at(on, run_t, now), radar_hour, _per_cycle(p))
    save_state(st, state_path)
    out = np.empty_like(fc)
    for k, f in enumerate(fc):
        t = now + timedelta(minutes=5 * (k + 1))
        lead = 5 * (k + 1) - 2.5
        out[k] = blend(f, corrected(meps_at(on, run_t, t), lead, st, p), lead, p)
    return out, {"meps_run": run_t.strftime("%Y-%m-%dT%H:%M:%SZ"), "hours": round(len(fc) / 12, 2)}
