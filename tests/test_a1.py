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


def test_stay_standard_av_och_stillastaende_regn_ligger_kvar():
    """Valet stay: av (None) är exakt som förut; en stillastående topp smetas ut utan det men inte med."""
    f = _blob(60, r=1.5)
    mot = _motion(6.0)
    old = a1.interval_mean(f, f, mot)
    assert np.array_equal(old, a1.interpolate(f, f, a1.paths(mot), None))
    assert old.max() < 0.8 * f.max()  # utan valet: toppen sjunker när rörelsen säger att allt flyttar sig
    kept = a1.interval_mean(f, f, mot, stay=1.0)
    assert np.allclose(kept, f, atol=1e-5)  # hela den gemensamma delen står still


def test_stay_cell_som_flyttar_sig_flyttas_som_forut():
    """En liten cell som flyttar sig långt har ingen gemensam del: stay ändrar nästan inget."""
    v = 12.0
    f0, f1 = _blob(30), _blob(30 + v)
    a = a1.interval_mean(f0, f1, _motion(v))
    b = a1.interval_mean(f0, f1, _motion(v), stay=1.0)
    assert np.abs(a - b).max() < 0.03 * a.max()  # bara svansarna överlappar
    # NaN och täckningen som förut
    f0[:, :20] = np.nan
    c = a1.interval_mean(f0, f1, _motion(v), stay=1.0)
    assert np.array_equal(np.isnan(c), np.isnan(a1.interval_mean(f0, f1, _motion(v))))


def test_stay_fraction_bara_uppfor():
    terr = np.tile(np.arange(W, dtype=np.float32) * 10.0, (H, 1))  # 10 m per pixel österut
    up = a1.stay_fraction(_motion(1.0), terr, 1.0)
    down = a1.stay_fraction(_motion(-1.0), terr, 1.0)
    assert np.allclose(up[:, 10:-10], 1 - np.exp(-10.0), atol=1e-4)
    assert np.allclose(down, 0.0)


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
