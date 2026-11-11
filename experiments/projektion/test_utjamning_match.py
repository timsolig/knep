"""Tester för utjamning_match.py på syntetiska fält."""

import sys
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import domare as D  # noqa: E402
import utjamning_match as M  # noqa: E402
import utjamning_snabb as S  # noqa: E402
from test_utjamning_snabb import field  # noqa: E402


def smooth_of(f):
    return S.blend_fast(f, np.full_like(f, 8.0), 2.0)


def test_hel_ger_kedjans_vaerdemaengd():
    f = field(3)
    g = smooth_of(f)
    m = M.match_hel(f, g)
    ok = np.isfinite(f)
    assert np.array_equal(np.isfinite(m), ok)
    assert np.array_equal(np.sort(m[ok]), np.sort(f[ok]))


def test_hel_foljer_g_rang():
    f = field(4)
    g = smooth_of(f)
    m = M.match_hel(f, g)
    ok = np.isfinite(f)
    a, b = g[ok], m[ok]
    o = np.argsort(a, kind="stable")
    assert (np.diff(b[o]) >= -1e-6).all()


def test_svans_lamnar_under_troeskeln():
    f = field(5)
    g = smooth_of(f)
    tr = float(np.nanquantile(g, 0.9))
    m = M.match_svans(f, g, tr)
    ok = np.isfinite(f)
    low = ok & (g < tr)
    assert np.array_equal(m[low], g[low])
    assert (g >= tr)[ok].any()
    assert m[ok].max() == f[ok].max()


def test_block_ger_blockets_vaerdemaengd():
    f = field(6, (64, 64))
    f[0, 0] = 1.0
    g = smooth_of(f)
    m = M.match_block(f, g, 16, mjuk=False)
    for y in range(0, 64, 16):
        for x in range(0, 64, 16):
            fb, mb = f[y:y + 16, x:x + 16], m[y:y + 16, x:x + 16]
            if (fb > 0).any():
                ok = np.isfinite(fb)
                assert np.array_equal(np.sort(mb[ok]), np.sort(fb[ok]))


def test_sigma_noll_ger_kedjans_faelt(monkeypatch):
    fc = np.stack([field(k) for k in range(D.NQ)])
    monkeypatch.setattr(D.KedjaOm, "forecast", lambda self, t, ctx: fc)

    class Ctx:
        res = 2

        def motion(self, t):
            return np.zeros((2,) + fc.shape[1:], np.float32)

        def history(self, t, n=12):
            return None

        def frame(self, t):
            return None

    for name in ("M_hel", "M_svans2", "M_blk64"):
        s = getattr(M, name)()
        assert np.array_equal(s.forecast(datetime(2020, 1, 1, 12), Ctx()), fc, equal_nan=True)
