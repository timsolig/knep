"""A1: interpolationen längs rörelsen mellan radarbilderna, på syntetiska fält."""

from datetime import UTC, datetime, timedelta

import numpy as np

from knep.analys import a1

H, W = 40, 180


def _blob(x, y=20.0, r=2.0, peak=10.0):
    yy, xx = np.mgrid[0:H, 0:W]
    return (peak * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * r * r))).astype(np.float32)


def _motion(vx, vy=0.0):
    m = np.zeros((2, H, W), np.float32)
    m[0], m[1] = vx, vy
    return m


def test_cell_som_flyttar_sig_fyller_sparet():
    """En cell som flyttar sig 12 pixlar per bild: A0:s timmedel är ett pärlband, A1:s ett spår."""
    v = 12.0
    frames = [_blob(10 + v * k) for k in range(13)]
    a0 = np.mean(frames[1:], axis=0)  # A0: varje bild gäller fem minuter
    a1h = np.mean([a1.interval_mean(frames[k], frames[k + 1], _motion(v)) for k in range(12)], axis=0)
    track = slice(int(10 + v), int(10 + 12 * v))
    assert a0[20, track].min() < 0.05 * a0[20, track].max()  # glapp mellan pärlorna
    assert a1h[20, track].min() > 0.5 * a1h[20, track].max()  # sammanhängande
    # mängden bevaras: summan av A1 är densamma som A0:s inom några procent
    assert abs(a1h.sum() / a0.sum() - 1.0) < 0.05


def test_stillastående_och_tyngdpunkt():
    f = _blob(30)
    assert np.allclose(a1.interval_mean(f, f, _motion(0.0)), f, atol=1e-5)
    m = a1.interval_mean(_blob(30), _blob(34), _motion(4.0))
    x = (m.sum(axis=0) * np.arange(W)).sum() / m.sum()
    assert abs(x - 32.0) < 0.3  # mitt emellan de två bilderna


def test_saknade_data():
    f0, f1 = _blob(30), _blob(30)
    f0[:, :20] = np.nan  # första bilden vet inte till vänster
    f1[:, :10] = np.nan  # ingen av dem vet längst till vänster
    m = a1.interval_mean(f0, f1, _motion(0.0))
    assert np.isnan(m[:, :10]).all()
    assert np.allclose(m[:, 10:20], f1[:, 10:20], atol=1e-5)  # bara den andra bilden
    assert np.isfinite(m[:, 20:]).all() and (m >= 0)[np.isfinite(m)].all()


def test_update_sparar_hoppar_over_och_rensar(tmp_path):
    t = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)
    step = timedelta(minutes=5)
    times = [t, t + step, t + 3 * step, t + 4 * step]  # en bild saknas: inget intervall över luckan
    rain = np.stack([_blob(30 + 2 * k) for k in range(4)])
    out = a1.update(tmp_path, times, rain, _motion(2.0))
    assert [x[0] for x in out] == [t + step, t + 4 * step]
    # utan rörelse räknas inget nytt, men det sparade finns kvar
    assert len(a1.update(tmp_path, times, rain, None)) == 2
    # gamla intervall rensas
    later = [t + timedelta(hours=3)]
    assert a1.update(tmp_path, later, rain[:1], _motion(2.0)) == []
    assert not list(tmp_path.glob("a1_*.npz"))
