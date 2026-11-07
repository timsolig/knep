"""A2T i cykeln (analys/a2_cykel.py och valet --a2 i cli.py), syntetiska data utan nätverk."""

import importlib.util
import json
import logging
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.crs import CRS
from rasterio.transform import from_origin

from knep import cli, render
from knep.analys import a2, a2_cykel, radar
from knep.analys.radar import Grid

ROOT = Path(__file__).resolve().parents[1]
if "analys_domare" not in sys.modules:
    spec = importlib.util.spec_from_file_location("analys_domare", ROOT / "experiments/analys/domare.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["analys_domare"] = mod
    spec.loader.exec_module(mod)
D = sys.modules["analys_domare"]

H, W = 60, 80
GRID = Grid(CRS.from_epsg(3006), from_origin(400000, 6600000, 2000, 2000), (H, W))
NOW = datetime(2026, 7, 14, 15, 7, tzinfo=UTC)
NEWEST = datetime(2026, 7, 14, 15, 0, tzinfo=UTC)
FIVE = timedelta(minutes=5)


def _latlon(grid, r, c):
    x, y = grid.transform * (np.asarray(c) + 0.5, np.asarray(r) + 0.5)
    lon, lat = Transformer.from_crs(grid.crs, "EPSG:4326", always_xy=True).transform(x, y)
    return np.asarray(lat), np.asarray(lon)


def _intervals(seed, hours=8):
    """A1:s intervall (slut, mm/h) för hours timmar till och med NEWEST, med en NaN-kant."""
    rng = np.random.default_rng(seed)
    out = []
    for k in range(12 * hours):
        t = NEWEST - (12 * hours - 1 - k) * FIVE
        f = (rng.gamma(0.6, 2.0, (H, W)) * (rng.random((H, W)) < 0.4)).astype(np.float16).astype(np.float32)
        f[:5] = np.nan
        out.append((t, f))
    return out


def _stations(seed, n=25):
    rng = np.random.default_rng(seed)
    r, c = rng.integers(0, H, n), rng.integers(0, W, n)
    lat, lon = _latlon(GRID, r, c)
    return r, c, {str(1000 + i): [float(lat[i]), float(lon[i]), f"st{i}"] for i in range(n)}


def _doc(seed, stations, hours_with=None):
    """gauges.json med timvärden och kvartsvärden; hours_with: vilka timslut som har mätare (alla om None)."""
    rng = np.random.default_rng(seed)
    doc = {"stations": stations, "60": {}, "15": {}}
    for h in range(10):
        end = NEWEST - h * timedelta(hours=1)
        if hours_with is not None and end not in hours_with:
            continue
        q = np.where(rng.random((len(stations), 4)) < 0.5, rng.gamma(0.7, 0.8, (len(stations), 4)), 0.0).round(1)
        doc["60"][a2_cykel._iso(end)] = {sid: float(q[i].sum()) for i, sid in enumerate(stations)}
        for j in range(4):
            tq = end - timedelta(hours=1) + (j + 1) * timedelta(minutes=15)
            doc["15"][a2_cykel._iso(tq)] = {sid: float(q[i, j]) for i, sid in enumerate(stations) if i % 3}
    return doc


def _direkt(ivs, r, c, doc, stations, end):
    """A2T.timme på samma indata, byggt utan a2_cykel: summorna som domaren och mätarna i given ruta."""
    by_t = dict(ivs)

    def a1(e):
        x = np.stack([by_t[e - timedelta(hours=1) + (k + 1) * FIVE] for k in range(12)])
        q, h = D.sums(x)
        return h[0].astype(np.float16).astype(np.float32), q.astype(np.float16).astype(np.float32)

    rc = dict(zip(stations, zip(r, c)))

    def mat(res, e):
        v = doc[res].get(a2_cykel._iso(e), {})
        ids = sorted(v)
        return a2.Matare([rc[s][0] for s in ids], [rc[s][1] for s in ids], [v[s] for s in ids])

    a1h, a1q = a1(end)
    rad, kol, mm, aa = [], [], [], []
    for k in range(5, -1, -1):
        e = end - timedelta(hours=k)
        m = mat("60", e)
        f = a1(e)[0] if e - timedelta(hours=1) >= min(by_t) - FIVE else None
        rad += list(m.rad); kol += list(m.kol); mm += list(m.mm)
        aa += list(f[m.rad, m.kol]) if f is not None else [np.nan] * len(m)
    fon = a2.Matare(rad, kol, mm, aa)
    kvm = [mat("15", end - timedelta(hours=1) + (j + 1) * timedelta(minutes=15)) for j in range(4)]
    model = a2.A2T.fran_grid(GRID)
    return model.timme(a1h, a1q, fon, mat("60", end), kvm)


def test_summor_som_domaren():
    rng = np.random.default_rng(1)
    x = (rng.gamma(0.6, 2.0, (12, 7, 9))).astype(np.float32)
    x[0:5, 0] = np.nan  # 7 av 12: timmen saknas, men kvartar med två av tre finns
    q, h = D.sums(x)
    tm, kv = a2_cykel.summor(list(x))
    assert np.array_equal(tm, h[0], equal_nan=True) and np.array_equal(kv, q, equal_nan=True)
    # ett intervall som inte finns är som NaN
    tm2, kv2 = a2_cykel.summor([None] + list(x[1:]))
    x[0] = np.nan
    q, h = D.sums(x)
    assert np.array_equal(tm2, h[0], equal_nan=True) and np.array_equal(kv2, q, equal_nan=True)


def test_spara_a1_en_gang_och_rensar(tmp_path):
    ivs = _intervals(0, hours=12)
    nya = a2_cykel.spara_a1(tmp_path, ivs, NOW)
    filer = sorted(p.name for p in tmp_path.glob("a1t_*.npz"))
    assert len(filer) == a2_cykel.BEHALL and filer[-1] == "a1t_20260714T1500.npz"
    assert nya == [NEWEST - timedelta(hours=k) for k in range(a2_cykel.BEHALL - 1, -1, -1)]  # bara de som behålls
    assert a2_cykel.spara_a1(tmp_path, ivs, NOW) == []  # sparas en gång
    # en ofullständig timme (bara sex intervall) sparas inte
    (tmp_path / "x").mkdir()
    assert a2_cykel.spara_a1(tmp_path / "x", ivs[-6:], NOW) == []
    tm, kv = a2_cykel.las_a1(tmp_path, NEWEST)
    assert tm.shape == (H, W) and kv.shape == (4, H, W) and tm.dtype == np.float32


def test_falten_lika_med_a2t_direkt(tmp_path):
    ivs = _intervals(2)
    r, c, stations = _stations(3)
    doc = _doc(4, stations)
    a2_cykel.spara_a1(tmp_path, ivs, NOW)
    res = a2_cykel.rakna(tmp_path, tmp_path, GRID, NOW, doc)
    assert [e for e, *_ in res] == [NEWEST - timedelta(hours=k) for k in range(a2_cykel.RAKNA, -1, -1)]
    for end, tm, kv, tag in res:
        th, tq = _direkt(ivs, r, c, doc, stations, end)
        assert np.array_equal(tm, th, equal_nan=True) and np.array_equal(kv, tq, equal_nan=True)
        assert tag.startswith("n") and int(tag[1:]) > 0
    # med mätarna ändrar A2T faktiskt fältet
    assert not np.array_equal(res[-1][1], a2_cykel.las_a1(tmp_path, NEWEST)[0], equal_nan=True)


def test_timmar_utan_matare_hoppas_over(tmp_path):
    ivs = _intervals(5)
    _, _, stations = _stations(6)
    med = {NEWEST - timedelta(hours=2), NEWEST - timedelta(hours=5)}
    doc = _doc(7, stations, hours_with=med)
    rend = render.Renderer(GRID)
    lst = a2_cykel.kor(tmp_path, tmp_path, rend, ivs, NOW, 12, doc)
    assert [f["time"] for f in lst["frames60"]] == [a2_cykel._iso(NEWEST - timedelta(hours=2))]
    assert len(lst["frames15"]) == 4 and lst["frames"] == []
    assert all(f["file"].startswith("a2/") and (tmp_path / f["file"]).exists() for f in lst["frames60"] + lst["frames15"])
    # utan mätare alls: A1:s timmar sparas, inget ritas
    lst = a2_cykel.kor(tmp_path / "tom", tmp_path / "tom", rend, ivs, NOW, 12, None)
    assert lst["frames60"] == [] and len(list((tmp_path / "tom").glob("a1t_*.npz"))) == 8  # åtta timmar intervall


def test_rakna_om_nar_fler_varden_kommer(tmp_path):
    ivs = _intervals(8)
    _, _, stations = _stations(9, n=30)
    full = _doc(10, stations, hours_with={NEWEST})
    rend = render.Renderer(GRID)
    halv = json.loads(json.dumps(full))
    t = a2_cykel._iso(NEWEST)
    halv["60"][t] = dict(list(full["60"][t].items())[:10])
    first = a2_cykel.kor(tmp_path, tmp_path, rend, ivs, NOW, 12, halv)["frames60"][0]["file"]
    assert a2_cykel.rakna(tmp_path, tmp_path, GRID, NOW, halv) == []  # samma mätare: räknas inte om
    second = a2_cykel.kor(tmp_path, tmp_path, rend, ivs, NOW, 12, full)["frames60"]
    assert len(second) == 1 and second[0]["file"] != first and not (tmp_path / first).exists()
    assert len(list((tmp_path / "a2").glob("q*.png"))) == 4  # kvartarna byttes också


# ---------------------------------------------------------------- hela cykeln

WEST, NORTH, RES, CW, CH = 126648, 7771252, 2000, 475, 894
T0 = datetime(2026, 7, 14, 15, 0, tzinfo=UTC)
CGRID = Grid(CRS.from_epsg(3006), from_origin(WEST, NORTH, RES, RES), (CH, CW))


def _rain(k):
    y, x = np.mgrid[0:CH, 0:CW]
    r = 25.0 * np.exp(-(((x - 150 - 2 * k) / 20.0) ** 2 + ((y - 600) / 12.0) ** 2))
    r[r < 0.05] = 0.0
    return r


def _encode(rain):
    with np.errstate(divide="ignore"):
        dbz = 10 * np.log10(radar.ZR_A * rain**radar.ZR_B)
    raw = np.clip(np.round((dbz - radar.OFFSET) / radar.GAIN), 1, 254)
    raw[rain == 0] = radar.NO_ECHO
    return raw.astype(np.uint8)


def _write_cache(cache, n=13):
    for k in range(n):
        t = T0 - k * radar.STEP
        with rasterio.open(cache / f"{t:%Y%m%d%H%M}.tif", "w", driver="GTiff", width=CW, height=CH, count=1,
                           dtype="uint8", crs="EPSG:3006", transform=from_origin(WEST, NORTH, RES, RES)) as dst:
            dst.write(_encode(_rain(-k)), 1)


def _arkiv(d):
    """p7.npz och p14.npz med sex stationer kring regncellen, värden för T0:s timme och kvartar."""
    d.mkdir()
    r = np.array([600, 600, 610, 590, 620, 400])
    c = np.array([140, 160, 150, 150, 120, 300])
    lat, lon = _latlon(CGRID, r, c)
    mm_h = np.array([3.0, 5.0, 1.0, 2.0, 0.0, 0.0])
    end = int(T0.timestamp())
    np.savez(d / "p7.npz", station=np.arange(6) + 1, lat=lat.astype(np.float32), lon=lon.astype(np.float32),
             time=np.full(6, end), mm=mm_h.astype(np.float32))
    q = np.repeat(np.arange(4), 6)
    np.savez(d / "p14.npz", station=np.tile(np.arange(6) + 1, 4), lat=np.tile(lat, 4).astype(np.float32),
             lon=np.tile(lon, 4).astype(np.float32), time=end - 3600 + (q + 1) * 900,
             mm=np.tile(mm_h / 4, 4).astype(np.float32))
    return r, c, mm_h


def _cli(tmp_path, *extra):
    cache, out = tmp_path / "cache", tmp_path / "out"
    cache.mkdir(exist_ok=True)
    _write_cache(cache)
    rc = cli.main(["--time", T0.isoformat(), "--cache", str(cache), "--out", str(out), "--hours", "0.5",
                   "--keep-cache", "--history", "13", "--no-bias", *extra])
    assert rc == 0
    return json.loads((out / "manifest.json").read_text()), cache, out


def test_cli_utan_valet_som_forut(tmp_path):
    m, cache, out = _cli(tmp_path, "--a2-matare", str(tmp_path / "finns-inte"))
    assert m["levels"]["a2"] is None and m["levels"]["a1"]["frames60"]
    assert not (out / "a2").exists() and not list((cache / "state").glob("a1t_*.npz"))


def test_cli_med_valet_fyller_a2(tmp_path):
    r, c, mm_h = _arkiv(tmp_path / "matare")
    m, cache, out = _cli(tmp_path, "--a2", "--a2-matare", str(tmp_path / "matare"))
    lst = m["levels"]["a2"]
    assert [f["time"] for f in lst["frames60"]] == ["2026-07-14T15:00:00Z"] and len(lst["frames15"]) == 4
    assert m["levels"]["a1"]["frames60"]  # A1 som förut
    # bilden är A2T.timme direkt på A1:s sparade summor och arkivets mätare
    a1h, a1q = a2_cykel.las_a1(cache / "state", T0)
    mat = a2.Matare(r, c, mm_h)
    tm, kv = a2.A2T.fran_grid(CGRID).timme(a1h, a1q, a2.Matare(r, c, mm_h, a1h[r, c]), mat,
                                           [a2.Matare(r, c, mm_h / 4) for _ in range(4)])
    rend = render.Renderer(CGRID)
    rend.png(tm, tmp_path / "h.png")
    rend.png(kv[2] * 4, tmp_path / "q.png")
    assert (tmp_path / "h.png").read_bytes() == (out / lst["frames60"][0]["file"]).read_bytes()
    assert (tmp_path / "q.png").read_bytes() == (out / lst["frames15"][2]["file"]).read_bytes()
    assert abs(np.nansum(tm) - np.nansum(a1h)) > 0.1  # mätarna ändrade fältet


def test_cli_fel_i_a2_bara_varning(tmp_path, monkeypatch, caplog):
    def boom(*a, **k):
        raise RuntimeError("trasig")
    monkeypatch.setattr(a2_cykel, "kor", boom)
    with caplog.at_level(logging.WARNING):
        m, _, out = _cli(tmp_path, "--a2")
    assert "A2: trasig" in caplog.text
    assert m["levels"]["a2"] is None and m["frames"] and m["levels"]["a1"]
