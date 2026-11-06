"""Semi-Lagrangesk extrapolering med OpenCV, samma schema som pysteps men mångdubbelt snabbare.

pysteps.extrapolation.semilagrangian gör fem interpolationer per steg med scipy (rörelsen i två
komponenter två gånger, för mittpunkten och slutpunkten, och fältet en gång). Här görs samma
steg med cv2.remap, och förflyttningen räknas en gång och delas av alla fält som flyttas med
samma rörelse. På SMHI:s rutnät tar 60 steg en bråkdel av en sekund i stället för en halv minut.

Randvillkoren är pysteps: rörelsen förlängs med kantvärdet, och fältet får outval utanför
rutnätet.
"""

from __future__ import annotations

import cv2
import numpy as np


def displacements(velocity: np.ndarray, steps: int | list[float]):
    """Förflyttningen bakåt (dx, dy) i pixlar för varje steg, som pysteps med n_iter = 1.

    velocity: (2, H, W) i pixlar per steg. steps: antal steg eller stigande tider i steg.
    """
    times = np.arange(1, steps + 1, dtype=float) if isinstance(steps, (int, np.integer)) else np.asarray(steps, float)
    diffs = np.diff(np.concatenate([[0.0], times])).tolist()  # Python-tal, så att allt förblir float32
    h, w = velocity.shape[1:]
    gx, gy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    vx, vy = velocity[0].astype(np.float32), velocity[1].astype(np.float32)
    dx, dy = np.zeros((h, w), np.float32), np.zeros((h, w), np.float32)

    def at(px, py):
        mx, my = gx + px, gy + py
        return (cv2.remap(vx, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE),
                cv2.remap(vy, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE))

    ix, iy = vx * diffs[0], vy * diffs[0]
    for td in diffs:
        ix, iy = (v * td for v in at(dx - ix / 2, dy - iy / 2))  # mittpunkten
        dx, dy = dx - ix, dy - iy
        ix, iy = (v * td for v in at(dx, dy))
        mx, my = gx + dx, gy + dy
        yield mx, my, (mx < 0) | (mx > w - 1) | (my < 0) | (my > h - 1)


def warp(field: np.ndarray, mx: np.ndarray, my: np.ndarray, outside: np.ndarray, order: int = 1, outval=np.nan) -> np.ndarray:
    """Fältet i punkterna (mx, my); outval där punkten ligger utanför rutnätet."""
    out = cv2.remap(field, mx, my, cv2.INTER_LINEAR if order else cv2.INTER_NEAREST,
                    borderMode=cv2.BORDER_CONSTANT, borderValue=0.0)
    out[outside] = outval
    return out


def extrapolate(fields, velocity: np.ndarray, steps, orders=1, outval=np.nan):
    """Flytta ett eller flera fält med samma rörelse: (steg, H, W) per fält.

    fields: ett fält (H, W) eller en lista; orders: 1 bilinjärt, 0 närmaste granne, per fält.
    """
    single = isinstance(fields, np.ndarray)
    fields = [np.asarray(f, np.float32) for f in ([fields] if single else fields)]
    orders = [orders] * len(fields) if isinstance(orders, int) else list(orders)
    out = [[] for _ in fields]
    for mx, my, outside in displacements(velocity, steps):
        for f, o, acc in zip(fields, orders, out):
            acc.append(warp(f, mx, my, outside, o, outval))
    out = [np.stack(a) for a in out]
    return out[0] if single else out
