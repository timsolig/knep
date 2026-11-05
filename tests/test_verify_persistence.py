"""Verifieringens persistens och urval med regn som rör sig, så att varje tidsförskjutning syns.

Testerna i test_verify.py har stillastående regn, där persistensen och en perfekt prognos blir rätt
oavsett vilken timme som används. Här flyttar sig ett band en ruta var femte minut, så att varje
timme har sin egen bild, och ett stillastående område ligger kvar (terrängbundet regn). Facit räknas
oberoende ur samma funktion och jämförs med tabellerna som score() sparar.
"""

from datetime import UTC, datetime, timedelta

import numpy as np
from rasterio.crs import CRS
from rasterio.transform import from_origin

from knep import composite, verify
from knep.radar import Grid

STEP = timedelta(minutes=5)
HOUR = timedelta(hours=1)
GRID = Grid(CRS.from_epsg(3006), from_origin(400000, 6600000, 2000, 2000), (40, 160))
HH = datetime(2026, 11, 4, 19, 0, tzinfo=UTC)  # utgåvans heltimme, som i drift
START = HH - HOUR
HOLE = (slice(0, 40), slice(40, 56))  # rutor som inte är uppmätta under timmen som slutar HH


def truth(t: datetime) -> np.ndarray:
    """Radarn vid t: ett band som flyttar sig österut en ruta per bild och ett stillastående område."""
    f = np.zeros(GRID.shape, np.float32)
    c = 4 + round((t - START) / STEP)
    f[6:30, c:c + 8] = 6.0
    f[32:38, 100:140] = 2.0
    return f


def outside(f: np.ndarray) -> np.ndarray:
    """Tim-KNEP saknar de östligaste rutorna (utanför prognosens område), där radarn har data."""
    f = f.copy()
    f[:, 150:] = np.nan
    return f


def covered() -> np.ndarray:
    m = np.ones(verify.vgrid(GRID).shape, bool)
    m[:, 75:] = False
    return m


def source_of(t: datetime) -> np.ndarray:
    src = np.full(GRID.shape, composite.SOURCE_SMHI, np.uint8)
    if HH - HOUR < t <= HH:
        src[HOLE] = composite.SOURCE_ADVECTED
    return src


def hour_mean(end: datetime) -> np.ndarray:
    """Facit räknat utan verify: medlet av timmens tolv bilder i block, NaN där någon bild saknar mätning."""
    st = []
    for j in range(12):
        t = end - j * STEP
        f = truth(t)
        f = np.where(np.isin(source_of(t), verify.MEASURED), f, np.nan)
        st.append(f.reshape(20, 2, 80, 2).mean(axis=(1, 3)).astype(np.float16).astype(np.float32))
    return np.mean(st, axis=0).astype(np.float16).astype(np.float32)


def table(f: np.ndarray, o: np.ndarray, mask: np.ndarray) -> np.ndarray:
    out = []
    for thr in verify.THRESHOLDS:
        fy, oy = f[mask] >= thr, o[mask] >= thr
        out.append([np.sum(fy & oy), np.sum(fy & ~oy), np.sum(~fy & oy), np.sum(~fy & ~oy)])
    return np.array(out)


def run(tmp_path, t0: datetime, met_field=None) -> verify.Day:
    """Radarn var femte minut, utgåvan t0 med en perfekt prognos, och räkningen när mätarna har kommit."""
    vdir = tmp_path / "verif"
    t = START - HOUR
    while t <= t0:
        verify.observe(vdir, [(t, truth(t))], source_of)
        t += STEP
    if met_field is not None:
        vg = verify.vgrid(GRID)
        verify.store_hours(verify.source_dir(vdir), "met_x", "2026-11-04T18:45:00Z", t0 - STEP,
                           [(HH + k * HOUR, met_field) for k in (1, 2)], vg)
    obs = [(t0 - k * STEP, "obs", truth(t0 - k * STEP)) for k in range(11, -1, -1)]
    fc = [(t0 + (k + 1) * STEP, "fc", outside(truth(t0 + (k + 1) * STEP)), None) for k in range(verify.LEADS * 12)]
    assert verify.due(vdir, t0)
    verify.issue(vdir, GRID, t0, obs + fc)
    pending = np.load(vdir / "pending" / f"{HH:%Y%m%dT%H}.npz")
    # persistensen är radarns timme som slutar HH, för alla ledtider
    for k in range(1, verify.LEADS + 1):
        np.testing.assert_array_equal(pending[f"persistens_{k}"].astype(np.float32), hour_mean(HH))
        # Tim-KNEP:s timme k slutar HH + k (prognosen är perfekt, så den är radarns timme utan hålet)
        ours = pending[f"ours_{k}"].astype(np.float32)
        o = hour_mean(HH + k * HOUR)
        assert np.isnan(ours[~covered()]).all() and np.allclose(ours[covered()], o[covered()], atol=1e-2), k
    while t <= HH + verify.LEADS * HOUR + 3 * STEP:
        verify.observe(vdir, [(t, truth(t))], source_of)
        t += STEP
    assert verify.score(vdir, GRID, HH + verify.LEADS * HOUR + verify.GAUGE_DELAY, None) == 1
    return verify.Day(vdir / "days" / f"{HH:%Y-%m-%d}.npz", verify.vgrid(GRID).shape)


def test_moving_rain_puts_every_hour_where_it_belongs(tmp_path):
    for t0 in (HH, HH + STEP, HH + 3 * STEP):  # utgåvan är första cykeln i timmen, upp till en kvart in
        day = run(tmp_path / f"{t0:%M}", t0)
        P = hour_mean(HH)
        for k in range(1, verify.LEADS + 1):
            O = hour_mean(HH + k * HOUR)
            base = np.isfinite(O) & covered()  # facit och Tim-KNEP
            ct = day.arrays["radar/ours/ct"][k - 1]
            # en perfekt prognos för rätt timme: inga falsklarm och inga missar
            assert ct[:, 1].sum() == 0 and ct[:, 2].sum() == 0 and ct[:, 0].sum() > 0, (t0, k)
            assert day.arrays["radar/ours/c"][k - 1][0] == base.sum()
            # persistensen: timmen som slutar HH mot timmen som slutar HH + k, på rutorna där båda finns
            mask = base & np.isfinite(P)
            np.testing.assert_array_equal(day.arrays["radar/persistens/ct"][k - 1], table(P, O, mask))
            assert day.arrays["radar/persistens/c"][k - 1][0] == mask.sum()
            # bandet har flyttat sig: persistensen missar det, men träffar det stillastående
            i1 = verify.THRESHOLDS.index(1.0)
            a, b, c, _ = day.arrays["radar/persistens/ct"][k - 1][i1]
            assert b > 0 and c > 0 and a > 0


def test_pairs_use_the_same_blocks(tmp_path):
    """Persistensen saknar blocken i hålet; Tim-KNEP jämförs parvis på exakt samma block."""
    day = run(tmp_path, HH + STEP)
    P = hour_mean(HH)
    assert np.isnan(P[HOLE[0], 20:28]).all()
    for k in range(1, verify.LEADS + 1):
        O = hour_mean(HH + k * HOUR)
        mask = np.isfinite(O) & np.isfinite(P) & covered()
        n_p = day.arrays["radar/persistens/c"][k - 1][0]
        n_pair = day.arrays["radar/ours@persistens/c"][k - 1][0]
        n_ours = day.arrays["radar/ours/c"][k - 1][0]
        assert n_p == n_pair == mask.sum() < n_ours
        # paret är Tim-KNEP på persistensens block: perfekt, och med lika många händelser som facit där
        ct = day.arrays["radar/ours@persistens/ct"][k - 1]
        np.testing.assert_array_equal(ct, table(O, O, mask))
        np.testing.assert_array_equal(ct[:, 0] + ct[:, 2], day.arrays["radar/persistens/ct"][k - 1][:, 0]
                                      + day.arrays["radar/persistens/ct"][k - 1][:, 2])


def test_tables_are_counted_the_same_for_every_model(tmp_path):
    """En jämförelsekälla med exakt persistensens fält får exakt persistensens tabeller och FSS."""
    day = run(tmp_path, HH + STEP, met_field=hour_mean(HH))
    for k in (1, 2):
        for name in ("ct", "c", "fss"):
            np.testing.assert_allclose(day.arrays[f"radar/met/{name}"][k - 1], day.arrays[f"radar/persistens/{name}"][k - 1])
    assert day.arrays["radar/met/hours"].tolist() == [1, 1, 0, 0, 0]
