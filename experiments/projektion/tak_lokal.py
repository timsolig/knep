"""Tak för lokal förskjutning: hur mycket av lägestaket är deformation, inte ny- och bortbildning (kön, spåret lokal-forskjutning).

Uppgift 0018 visade att två tredjedelar av taket för tillväxt i block om 32 km (CSI 1 mm +0,12 vid 2 h)
är massa som flyttas mellan block på 32 till 128 km, och 0022 att en rörelse som ändras med ledtiden
(ett fält per timme) bara tar 9 % av det. Det som är kvar är antingen en förskjutning som varierar i
rummet (deformation, rotation, en del av fältet som går fortare) eller ny- och bortbildning.

Här flyttas kedjans prognos för varje kvart mot facit med ett tätt rörelsefält (Farnebäck) mellan
prognosen och facit, med fönstret WIN_KM. Flyttningen kan inte skapa eller ta bort regn, bara flytta
det. Är taket nära tillväxttaket för 32 km är lägesfelet en lokal förskjutning och värt en kandidat (till
exempel en rörelse i flera skalor eller en ensemble av förskjutningar); är det litet är resten ny- och
bortbildning, och spåren för terrängen och satelliten är värda mer.

    uv run python experiments/projektion/domare.py kör --läge snabb --procs 2 --system tak_lokal:TakForskjutning32
    uv run python experiments/projektion/domare.py kör --läge snabb --procs 2 --system tak_lokal:TakForskjutning64
    uv run python experiments/projektion/domare.py kör --läge snabb --procs 2 --system tak_lokal:TakNybildning

Som de andra taken: ett fusk som ser facit, aldrig något som kan bli "bättre" i drift.
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import tak as T  # noqa: E402

NQ = T.NQ


def db(x: np.ndarray) -> np.ndarray:
    """Regnet i dB (10 log10(r + 0,1)), 0 där NaN, som bild för Farnebäck."""
    return (10.0 * np.log10(np.nan_to_num(x, nan=0.0) + 0.1)).astype(np.float32)


def flytta_mot(f: np.ndarray, o: np.ndarray, win_px: int) -> np.ndarray:
    """f flyttat så att det ligger som o: flödet o -> f ger för varje ruta var i f regnet kommer ifrån.
    NaN i f stannar NaN (täckningen ändras inte); utanför bilden räknas som 0."""
    flow = cv2.calcOpticalFlowFarneback(db(o), db(f), None, pyr_scale=0.5, levels=3, winsize=max(3, win_px | 1),
                                        iterations=3, poly_n=5, poly_sigma=1.1, flags=cv2.OPTFLOW_FARNEBACK_GAUSSIAN)
    h, w = f.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    src = np.nan_to_num(f, nan=0.0).astype(np.float32)
    out = cv2.remap(src, xx + flow[..., 0], yy + flow[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                    borderValue=0.0)
    return np.where(np.isfinite(f), out, np.nan).astype(np.float32)


class TakForskjutning32(T._Tak):
    """Kedjans prognos flyttad mot facit per kvart, fönster 32 km."""

    win_km = 32.0

    def cheat(self, fc, o, res, ctx, t):
        out = fc.copy()
        win = int(round(self.win_km / res))
        for k in range(NQ):
            if np.isfinite(o[k]).any():
                out[k] = flytta_mot(fc[k], o[k], win)
        return out


class TakForskjutning64(TakForskjutning32):
    """Som TakForskjutning32 med fönster 64 km (bara förskjutningar i större skala)."""

    win_km = 64.0


class TakNybildning(T._Tak):
    """Perfekt nybildning: där kedjan inte har regn (under 0,1 mm/h) inom NY_KM men facit har det, tas
    facit. Det kedjan redan har lämnas orört, så taket mäter bara regn som uppstår där inget fanns nära.
    Tillsammans med TakForskjutning32 och TakTillvaxt (0017) delar det lägestaket i förskjutning,
    nybildning och tillväxt."""

    ny_km = 16.0

    def cheat(self, fc, o, res, ctx, t):
        from scipy.ndimage import maximum_filter  # noqa: PLC0415

        size = int(round(2 * self.ny_km / res)) | 1
        out = fc.copy()
        for k in range(NQ):
            if not np.isfinite(o[k]).any():
                continue
            nara = maximum_filter(np.nan_to_num(fc[k]), size=size) >= 0.1
            ny = ~nara & np.isfinite(o[k]) & np.isfinite(fc[k])
            out[k] = np.where(ny, o[k], fc[k])
        return out
