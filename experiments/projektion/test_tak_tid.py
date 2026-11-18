"""Test av tak_tid.shift_forecast med syntetiska fält (uppgift 0022)."""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import tak_tid as T  # noqa: E402
from knep.prognos import advect  # noqa: E402

H, W, N = 64, 200, 60


def blob(cx, cy=32.0, s=3.0):
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    return (5.0 * np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2 * s * s))).astype(np.float32)


def com(f):
    y, x = np.mgrid[0:H, 0:W]
    return (f * x).sum() / f.sum(), (f * y).sum() / f.sum()


def uniform(vx, vy=0.0):
    v = np.zeros((2, H, W), np.float32)
    v[0], v[1] = vx, vy
    return v


def test_konstant_rorelse_ger_kedjans_prognos():
    v = uniform(0.5, 0.2)
    rain = advect.extrapolate(blob(40.0), v, N, outval=0.0)
    out = T.shift_forecast(rain, [v] * N, [v] * N)
    assert np.abs(out - rain).max() < 1e-4


def test_riktningsbyte_efter_en_timme():
    # kedjan flyttar ekot 0,5 px per steg åt höger; facit rör sig åt höger första timmen och sedan åt vänster
    vc, vr = uniform(0.5), uniform(-0.5)
    rain = advect.extrapolate(blob(100.0), vc, N, outval=0.0)
    out = T.shift_forecast(rain, [vc] * N, [vc] * 12 + [vr] * (N - 12))
    # efter 24 steg (mittsteg i kvart 8, bild index 23): 12 steg höger, 12 vänster: tillbaka vid start
    x, y = com(out[23])
    # (skiftet räknas vid kvartens mittsteg, så toleransen är en bildruta om 0,5 px per steg plus lite)
    assert abs(x - 100.0) < 1.2 and abs(y - 32.0) < 0.3
    # efter 12 steg: 6 px åt höger
    x, _ = com(out[11])
    assert abs(x - 106.0) < 1.2
    # efter 36 steg: 6 px åt vänster om start
    x, _ = com(out[35])
    assert abs(x - 94.0) < 1.2


def test_nan_stannar_nan():
    v = uniform(0.5)
    rain = advect.extrapolate(blob(40.0), v, N, outval=0.0)
    rain[:, :5, :] = np.nan
    out = T.shift_forecast(rain, [v] * N, [uniform(0.3)] * N)
    assert np.isnan(out[:, :5, :]).all() and np.isfinite(out[:, 5:, :]).all()
