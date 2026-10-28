"""Genererar prognoser för en KNEP-proxy och våra varianter på ett radarfall.

KNEP-proxy: analyser var 15:e minut på 15-minuters medelintensitet (som
cheddar-obs prec15min), rörelse med Lucas-Kanade på 15-minutersbilder och
semi-Lagrangesk extrapolering i 15-minuterssteg.

Våra varianter: analyser var 5:e minut på momentana bilder.
  lk      Lucas-Kanade på 4 bilder (15 min), extrapolering
  lk30    Lucas-Kanade på 7 bilder (30 min), extrapolering
  ema     rörelsefält utjämnat mellan körningar (alfa 0,3), extrapolering
  filt    lagrangeskt filtrerad analys (vikt 0,6 på ny bild), lk30-rörelse
  sprog   S-PROG (skaldämpning), lk30-rörelse
  steps   STEPS-ensemble med 8 medlemmar, lk30-rörelse; PMM som deterministisk produkt

Prognoserna sparas kvantiserade (0,5 dB) så att verifieringen kan köras om med andra mått.
"""

from __future__ import annotations

import argparse
import contextlib
import io as _io
import sys
import time
from pathlib import Path

import numpy as np
from pysteps import motion, nowcasts
from pysteps.extrapolation.semilagrangian import extrapolate
from pysteps.utils import transformation

sys.path.insert(0, str(Path(__file__).parent))
from cases import load  # noqa: E402

NS = 14          # 5-minuterssteg som sparas för våra varianter (70 min)
NK = 7           # 15-minuterssteg för KNEP-proxyn (105 min)
NENS = 8
ALPHA = 0.3      # utjämning av rörelsefältet mellan körningar
W_FILT = 0.6     # vikt på ny radarbild i det lagrangeska filtret
LK = motion.get_method("LK")
FRAMES = 0


def encode(r: np.ndarray) -> np.ndarray:
    """mm/h → uint8: 0 = torrt, 255 = saknas, annars 0,5 dB-steg från 0,1 mm/h."""
    q = np.zeros(r.shape, np.uint8)
    wet = np.isfinite(r) & (r >= 0.1)
    q[wet] = np.clip(np.round((10 * np.log10(r[wet]) + 10.0) / 0.5) + 1, 1, 254).astype(np.uint8)
    q[~np.isfinite(r)] = 255
    return q


def decode(q: np.ndarray) -> np.ndarray:
    r = np.where(q == 0, 0.0, 10 ** (((q.astype(np.float32) - 1) * 0.5 - 10.0) / 10)).astype(np.float32)
    r[q == 255] = np.nan
    return r


def db(r: np.ndarray) -> np.ndarray:
    out, _ = transformation.dB_transform(np.nan_to_num(r, nan=0.0), threshold=0.1, zerovalue=-15.0)
    return out


def undb(x: np.ndarray) -> np.ndarray:
    out, _ = transformation.dB_transform(x, threshold=-10.0, inverse=True)
    out[out < 0.1] = 0.0
    return out


def quiet(fn, *a, **k):
    with contextlib.redirect_stdout(_io.StringIO()):
        return fn(*a, **k)


def mask_outside(fc: np.ndarray, last: np.ndarray) -> np.ndarray:
    fc = fc.astype(np.float32)
    fc[:, ~np.isfinite(last)] = np.nan
    return fc


def run(root: Path, case: str, out: Path, with_steps: bool) -> None:
    obs, times, meta = load(root, case)
    if FRAMES:
        obs, times = obs[:FRAMES], times[:FRAMES]
    n = len(times)
    acc15 = np.full_like(obs, np.nan)
    for i in range(2, n):
        acc15[i] = obs[i - 2 : i + 1].mean(axis=0)

    filled = np.nan_to_num(obs, nan=0.0)
    first = 6  # 30 min historik för lk30
    issues = list(range(first, n - 1))
    prods = {k: np.zeros((len(issues), NS) + obs.shape[1:], np.uint8) for k in ["lk", "lk30", "ema", "filt", "sprog", "steps"]}
    members = {}  # (issue, valid) → (NENS, H, W) uint8, 15-min medel per medlem
    vel_store = np.zeros((len(issues), 2) + obs.shape[1:], np.float16)  # lk30 per körning, pixlar per 5 min
    v_ema = None
    a_filt = None
    t0 = time.time()

    # lagrangeskt filter körs från början av fallet
    for i in range(1, n):
        v = quiet(LK, db(obs[max(0, i - 6) : i + 1]))
        prev = filled[0] if a_filt is None else a_filt
        adv = extrapolate(prev, v, 1)[0]
        adv = np.where(np.isfinite(adv), adv, filled[i])
        new = np.where(np.isfinite(obs[i]), W_FILT * filled[i] + (1 - W_FILT) * adv, adv)
        a_filt = new.astype(np.float32)
        if i in issues:
            j = issues.index(i)
            v4 = quiet(LK, db(obs[i - 3 : i + 1]))
            v30 = v
            vel_store[j] = v30.astype(np.float16)
            v_ema = v4 if v_ema is None else ALPHA * v4 + (1 - ALPHA) * v_ema
            last = obs[i]
            prods["lk"][j] = encode(mask_outside(extrapolate(filled[i], v4, NS), last))
            prods["lk30"][j] = encode(mask_outside(extrapolate(filled[i], v30, NS), last))
            prods["ema"][j] = encode(mask_outside(extrapolate(filled[i], v_ema, NS), last))
            prods["filt"][j] = encode(mask_outside(extrapolate(a_filt, v30, NS), last))
            sp = quiet(nowcasts.get_method("sprog"), db(obs[i - 2 : i + 1]), v30, NS, precip_thr=-10.0, n_cascade_levels=6, ar_order=2)
            prods["sprog"][j] = encode(mask_outside(undb(sp), last))
            if with_steps:
                ens = quiet(
                    nowcasts.get_method("steps"), db(obs[i - 2 : i + 1]), v30, NS,
                    n_ens_members=NENS, n_cascade_levels=6, precip_thr=-10.0,
                    kmperpixel=meta["xpixelsize"] / 1000, timestep=5, seed=1000 + i, num_workers=1,
                )
                ens = undb(ens)  # (NENS, NS, H, W)
                ens[:, :, ~np.isfinite(last)] = np.nan
                prods["steps"][j] = encode(pmm(ens))
                for k in range(1, NS + 1):
                    vi = i + k
                    if vi < n and times[vi].minute % 15 == 0 and k >= 3:
                        members[(i, vi)] = encode(ens[:, k - 3 : k].mean(axis=1))
                    elif vi < n and times[vi].minute % 15 == 0:
                        # medelvärdet når tillbaka till observerade bilder
                        parts = [obs[i - (2 - k) + m] if m < 3 - k else ens[:, m - (3 - k)] for m in range(3)]
                        stack = np.stack([np.broadcast_to(p, ens.shape[:1] + p.shape[-2:]) for p in parts])
                        members[(i, vi)] = encode(stack.mean(axis=0))
            print(f"{case}: körning {j + 1}/{len(issues)} klar efter {time.time() - t0:.0f} s", flush=True)

    # KNEP-proxy: kvartsanalyser på 15-minuters medel, tre bilder med 15 min mellanrum
    kissues = [i for i in range(6, n) if times[i].minute % 15 == 0]
    knep = np.zeros((len(kissues), NK) + obs.shape[1:], np.uint8)
    knep_inst = np.zeros_like(knep)
    for j, i in enumerate(kissues):
        a = acc15[[i - 6, i - 3, i]]
        v15 = quiet(LK, db(a))
        knep[j] = encode(mask_outside(extrapolate(np.nan_to_num(a[-1], nan=0.0), v15, NK), a[-1]))
        b = obs[[i - 6, i - 3, i]]
        v15b = quiet(LK, db(b))
        knep_inst[j] = encode(mask_outside(extrapolate(filled[i], v15b, NK), b[-1]))

    np.savez_compressed(
        out / f"{case}.npz",
        obs=encode(obs), times=np.array([t.isoformat() for t in times]),
        issues=np.array(issues), kissues=np.array(kissues),
        knep=knep, knep_inst=knep_inst, motion=vel_store,
        member_keys=np.array(list(members.keys())) if members else np.zeros((0, 2), int),
        member_vals=np.stack(list(members.values())) if members else np.zeros((0,), np.uint8),
        **prods,
    )
    print(f"{case}: klart på {time.time() - t0:.0f} s", flush=True)


def pmm(ens: np.ndarray) -> np.ndarray:
    """Sannolikhetsmatchat ensemblemedel per ledtid: medelvärdets läge, medlemmarnas fördelning."""
    out = np.full(ens.shape[1:], np.nan, np.float32)
    for k in range(ens.shape[1]):
        ok = np.all(np.isfinite(ens[:, k]), axis=0)
        m = ens[:, k].mean(axis=0)
        # bara pixlar där alla medlemmar finns, annars hamnar saknade värden sist i
        # poolen och läggs på pixlarna med högst medel (de kraftigaste kärnorna)
        pool = np.sort(ens[:, k][:, ok].ravel())[:: ens.shape[0]]
        order = np.argsort(m[ok], kind="stable")
        vals = np.empty(ok.sum(), np.float32)
        vals[order] = pool[: ok.sum()]
        out[k][ok] = vals
    return out


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("root", type=Path)
    p.add_argument("case")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--no-steps", action="store_true")
    p.add_argument("--frames", type=int, default=0, help="använd bara de första N bilderna (för snabbtest)")
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    FRAMES = a.frames
    run(a.root, a.case, a.out, not a.no_steps)
