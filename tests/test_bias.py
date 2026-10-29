"""Volymkorrektionen på syntetiska mätare och radar: årsvolymen ska stämma efter korrektionen."""

from datetime import UTC, date, datetime, timedelta

import numpy as np

from knep import bias, composite

# 8 km över Sverige räcker för testet och går fort
GRID = composite.TargetGrid(200000.0, 7700000.0, 8000.0, (165, 90))


def _stations(n=160, seed=1):
    rng = np.random.default_rng(seed)
    beam = bias.beam_height(GRID)
    X, Y = GRID.centres()
    ok = np.argwhere(np.isfinite(beam))
    pick = ok[rng.choice(len(ok), n, replace=False)]
    from pyproj import Transformer

    lon, lat = Transformer.from_crs("EPSG:3006", "EPSG:4326", always_xy=True).transform(X[pick[:, 0], pick[:, 1]], Y[pick[:, 0], pick[:, 1]])
    return bias.Stations(np.arange(1000, 1000 + n, dtype=np.int64), np.asarray(lat), np.asarray(lon)), beam


def _true_logk(h, month, blocked):
    winter = month in (11, 12, 1, 2, 3)
    return (0.05 + 0.08 * h + 0.03 * h**2) * (1.6 if winter else 1.0) + np.where(blocked, 0.5, 0.0)


def _fill(store, stations, beam, start, days, seed=2):
    """Mätare = sanning; radar = sanning delat med den sanna faktorn, med brus per timme."""
    rng = np.random.default_rng(seed)
    row, col, inside = stations.pixels(GRID)
    h = beam[row, col]
    blocked = (stations.lat > 64) & (stations.lon < 17)
    for k in range(days):
        d = start + timedelta(days=k)
        wet = rng.random((24, len(h))) < 0.12
        g = np.where(wet, rng.gamma(0.6, 2.0, (24, len(h))), 0.0).astype(np.float32)
        lk = _true_logk(h, d.month, blocked)
        r = (g * np.exp(-lk)[None, :] * np.exp(rng.normal(0, 0.2, g.shape))).astype(np.float32)
        # radarns svans är för låg (som vid dämpning i skurar): över 4 mm dämpas timsumman som (g/4)^-0.3
        r = (r * (np.maximum(g, 4.0) / 4.0) ** -0.3).astype(np.float32)
        store._save("gauge", d, stations.ids, {"val": g})
        store._save("radar", d, stations.ids, {"sum": r, "cnt": np.full(g.shape, 12, np.uint8), "last": np.int64(0)})
    return blocked


def test_beam_height_grows_with_range():
    beam = bias.beam_height(GRID)
    lat, lon, height, _ = composite.RADARS["seatv"]
    st = bias.Stations(np.array([1, 2]), np.array([lat, lat + 1.8]), np.array([lon, lon]))
    row, col, _ = st.pixels(GRID)
    assert beam[row[0], col[0]] < 0.5 < beam[row[1], col[1]] < 4.0


def test_store_counts_each_frame_once(tmp_path):
    store = bias.Store(tmp_path)
    st = bias.Stations(np.array([7]), np.array([58.5]), np.array([16.2]))
    rain = np.full(GRID.shape, 6.0, np.float32)
    t = datetime(2024, 7, 1, 12, 5, tzinfo=UTC)
    assert store.add_radar(t, rain, None, st, GRID)
    assert not store.add_radar(t, rain, None, st, GRID)
    for k in range(1, 12):
        store.add_radar(t + timedelta(minutes=5 * k), rain, None, st, GRID)
    store.add_gauges([(7, datetime(2024, 7, 1, 13, tzinfo=UTC), 5.5)])
    G, R, T = store.pairs(date(2024, 7, 1), date(2024, 7, 1), st.ids)
    i = T.index(datetime(2024, 7, 1, 13, tzinfo=UTC))
    assert abs(R[i, 0] - 6.0) < 1e-4 and G[i, 0] == 5.5  # 12 bilder à 6 mm/h = 6 mm på timmen som slutar 13
    assert bias.hour_end(datetime(2024, 7, 1, 13, 0, tzinfo=UTC)) == datetime(2024, 7, 1, 13, tzinfo=UTC)


def test_fit_makes_annual_volume_match(tmp_path):
    stations, beam = _stations()
    store = bias.Store(tmp_path)
    start = date(2023, 1, 1)
    blocked = _fill(store, stations, beam, start, 365)
    corr, rep = bias.fit(store, stations, GRID, start, date(2023, 12, 31), beam=beam)
    # före: radarn har klart för lite; efter: inom några procent totalt och de flesta stationer inom 20 %
    assert rep["volym_före"] < 0.75
    assert abs(rep["volym_efter"] - 1.0) < 0.05
    assert rep["inom_20_proc_efter"] > 0.85 > rep["inom_20_proc_före"]
    # vintern korrigeras mer än sommaren, och den blockerade sektorn mer än sin omgivning
    row, col, _ = stations.pixels(GRID)
    jan, jul = corr.factor(datetime(2023, 1, 15, tzinfo=UTC)), corr.factor(datetime(2023, 7, 15, tzinfo=UTC))
    assert np.median(jan[row, col]) > np.median(jul[row, col])
    far = beam[row, col] > 2
    assert np.median(jul[row[blocked], col[blocked]]) > np.median(jul[row[~blocked & far], col[~blocked & far]])
    # svansen: radarns 99,9-percentil av våta timmar låg för lågt och hamnar närmare mätarna,
    # utan att volymen ovan blev fel
    assert rep["gamma"] > 0.03
    assert abs(np.log(rep["kvantil_99.9_efter"])) < abs(np.log(rep["kvantil_99.9_före"]))
    assert abs(rep["kvantil_99.9_efter"] - 1.0) < 0.12
    # korsvaliderat på stationer som inte var med i skattningen
    cv = bias.cross_validate(store, stations, GRID, start, date(2023, 12, 31), beam=beam)
    assert abs(cv["volym_efter"] - 1.0) < 0.08 and cv["inom_20_proc_efter"] > cv["inom_20_proc_före"]


def test_factor_is_continuous_between_months(tmp_path):
    coef = np.zeros((12, 3))
    coef[0, 0], coef[1, 0] = 0.4, 0.0
    c = bias.Correction(coef, np.zeros(GRID.shape, np.float32), bias.beam_height(GRID))
    a = c.logk(datetime(2024, 1, 31, 23, tzinfo=UTC))
    b = c.logk(datetime(2024, 2, 1, 1, tzinfo=UTC))
    assert np.nanmax(np.abs(a - b)) < 0.02
    path = tmp_path / "bias.npz"
    c.save(path)
    assert np.allclose(bias.Correction.load(path).coef, coef)


def test_parse_archive_csv():
    text = ("Stationsnamn;Klimatnummer\nNorrköping;86340\n\nDatum;Tid (UTC);Nederbördsmängd;Kvalitet;;Tidsutsnitt:\n"
            "2023-08-08;12:00:00;3.4;G;;Kvalitetskontrollerade\n2023-08-08;13:00:00;0.0;Y;;\n2023-08-08;14:00:00;9.9;R;;\n")
    recs = bias.parse_archive_csv(text, 86340)
    assert recs == [(86340, datetime(2023, 8, 8, 12, tzinfo=UTC), 3.4), (86340, datetime(2023, 8, 8, 13, tzinfo=UTC), 0.0)]


def test_backfill_keeps_day_in_memory(tmp_path):
    store = bias.Store(tmp_path)
    st = bias.Stations(np.array([7]), np.array([58.5]), np.array([16.2]))
    rain = np.full(GRID.shape, 3.0, np.float32)
    t = datetime(2024, 7, 1, 23, 5, tzinfo=UTC)
    for k in range(24):  # 23:05 till 01:00: två dygnsfiler
        store.add_radar(t + timedelta(minutes=5 * k), rain, None, st, GRID, keep=True)
    store.flush()
    store.add_gauges([(7, datetime(2024, 7, 2, 0, tzinfo=UTC), 3.0), (7, datetime(2024, 7, 2, 1, tzinfo=UTC), 3.0)])
    G, R, T = store.pairs(date(2024, 7, 1), date(2024, 7, 2), st.ids)
    i0, i1 = T.index(datetime(2024, 7, 2, 0, tzinfo=UTC)), T.index(datetime(2024, 7, 2, 1, tzinfo=UTC))
    assert abs(R[i0, 0] - 3.0) < 1e-4 and abs(R[i1, 0] - 3.0) < 1e-4
