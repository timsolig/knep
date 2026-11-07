"""Sammanställning av artefaktinventeringen: kartor, ekrar, vindkraft, typning och terrängen.

    uv run python experiments/analys/karta.py

Läser /data/analys/artefakter/dag/*.npz (från artefakter.py) och skriver
/data/analys/artefakter/kartor.npz, tabell.json och bilder under /data/analys/artefakter/bild/.
Kandidaterna väljs på träningsdagarna; valideringsdagarna visar om de står kvar.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
from scipy.ndimage import median_filter, uniform_filter

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "src"))
from artefakter import HOJD, OUT, RADAR, days, grid_xy  # noqa: E402
from knep.analys import composite, radar  # noqa: E402

SUMS = ("sd", "sd2", "tex", "d5", "se", "sl")


def load(part: str | None):
    tot, per_day = {}, {}
    for d, p in days():
        if part and p != part:
            continue
        f = OUT / "dag" / f"{d}.npz"
        if not f.exists():
            continue
        z = np.load(f)
        for k in z.files:
            if k.startswith("uv_") or k in ("mean_uv", "missing"):
                continue
            tot[k] = tot.get(k, 0) + z[k].astype(np.float64)
        per_day[d] = (z["ne"].astype(np.float32), z["nv"].astype(np.float32), z["nde"].astype(np.float32),
                      z["ndv"].astype(np.float32), z["mean_uv"])
    return tot, per_day


def ratio(a, b, min_b=1):
    return np.where(b >= min_b, a / np.maximum(b, 1), np.nan)


def derived(T):
    D = {}
    D["f_eko"] = ratio(T["ne"], T["nv"], 50)
    D["f_eko5"] = ratio(T["ne5"], T["nv"], 50)
    D["f_torr"] = ratio(T["nde"], T["ndv"], 50)       # eko när alla mätare inom 25 km är torra
    D["f_vat"] = ratio(T["nwe"], T["nwv"], 50)
    D["f_still"] = ratio(T["still"], T["nm"], 10)     # andel stillastående när rörelsen är tydlig
    D["euler_lagr"] = ratio(T["se"], T["sl"] + 1e-3, 1)  # medelfel på platsen / längs rörelsen, < 1 = står still
    D["euler_lagr"][T["nm"] < 10] = np.nan
    D["tex"] = ratio(T["tex"], T["ne"], 20)
    mu = ratio(T["sd"], T["ne"], 20)
    D["dbz_medel"] = mu
    D["dbz_sd"] = np.sqrt(np.maximum(ratio(T["sd2"], T["ne"], 20) - mu ** 2, 0))
    D["d5"] = ratio(T["d5"], T["n5"], 20)
    D["flip"] = ratio(T["flip"], T["nv"], 50)
    D["f_iso"] = ratio(T["iso"], T["ne"], 20)
    up, dn = ratio(T["neu"], T["nup"], 30), ratio(T["ned"], T["ndn"], 30)
    D["lyft"] = (up + 0.005) / (dn + 0.005)          # P(eko | vind mot sluttningen) / P(eko | vind nedför)
    f = np.nan_to_num(D["f_eko"])
    D["overskott"] = f - median_filter(f, 15)        # ekofrekvens över omgivningen (30 km)
    ft = np.nan_to_num(D["f_torr"])
    D["overskott_torr"] = ft - median_filter(ft, 15)
    return D


def days_with(per_day, thr=0.3, dry=False):
    n = None
    for ne, nv, nde, ndv, _ in per_day.values():
        a = (nde / np.maximum(ndv, 1) > thr) & (ndv >= 24) if dry else (ne / np.maximum(nv, 1) > thr) & (nv >= 100)
        n = a.astype(np.int16) if n is None else n + a
    return n


def radar_px(grid):
    to_rc = grid_xy(grid)
    out = {}
    for code, (lat, lon, alt, rng) in composite.RADARS.items():
        r, c = to_rc(np.array([lat]), np.array([lon]))
        out[code] = (float(r[0]), float(c[0]))
    return out


def spokes(field, rpx, shape, rmin=20, rmax=100, bins=360, z_thr=6.0):
    """Ekrar: smala toppar i azimutprofilen av fältet (medel över avståndet rmin..rmax rutor)
    jämfört med löpande median över ±10°. Ger (radar, azimut, styrka, z) för toppar över z_thr."""
    h, w = shape
    yy, xx = np.mgrid[0:h, 0:w]
    res = []
    prof_out = {}
    for code, (r0, c0) in rpx.items():
        if not (0 <= r0 < h and 0 <= c0 < w):
            continue
        dy, dx = yy - r0, xx - c0
        d = np.hypot(dy, dx)
        az = (np.degrees(np.arctan2(dx, -dy)) + 360) % 360  # 0 = norr, medurs
        m = (d >= rmin) & (d <= rmax) & np.isfinite(field)
        if m.sum() < 1000:
            continue
        b = (az[m] / (360 / bins)).astype(int) % bins
        s = np.bincount(b, field[m], bins)
        n = np.bincount(b, None, bins)
        prof = np.where(n > 5, s / np.maximum(n, 1), np.nan)
        ext = np.concatenate([prof[-10:], prof, prof[:10]])
        med = np.array([np.nanmedian(ext[i:i + 21]) for i in range(bins)])
        dev = prof - med
        mad = np.nanmedian(np.abs(dev)) * 1.4826 + 1e-4
        z = dev / mad
        prof_out[code] = prof
        for i in np.where((z > z_thr) & (dev >= 0.01))[0]:
            res.append({"radar": code, "azimut": float(i * 360 / bins), "overskott": float(dev[i]), "z": float(z[i]),
                        "andel_rutor": int(n[i])})
    return res, prof_out


def sun_azimuths(day: str, lat: float):
    """Ungefärlig azimut för soluppgång och solnedgång (grader från norr)."""
    dd = date.fromisoformat(day).timetuple().tm_yday
    dec = np.radians(-23.44 * np.cos(2 * np.pi / 365 * (dd + 10)))
    c = np.sin(dec) / np.cos(np.radians(lat))
    if abs(c) >= 1:
        return None
    a = np.degrees(np.arccos(c))
    return a, 360 - a


def main() -> None:
    _, grid = radar.read_rain(next((RADAR / "2020/02/10").glob("*.tif")))
    h, w = grid.shape
    hz = np.load(HOJD)["h"].astype(np.float32)
    rpx = radar_px(grid)
    to_rc = grid_xy(grid)
    from pyproj import Transformer
    inv = Transformer.from_crs(grid.crs, "EPSG:4326", always_xy=True)

    def latlon(r, c):
        x, y = grid.transform * (c + 0.5, r + 0.5)
        lon, lat = inv.transform(x, y)
        return round(lat, 3), round(lon, 3)

    T_all, pd_all = load(None)
    T_tr, pd_tr = load("traning")
    T_va, pd_va = load("validering")
    D = derived(T_all)
    Dtr, Dva = derived(T_tr), derived(T_va)
    D["dagar_eko30"] = days_with(pd_all).astype(np.float32)
    D["dagar_torr30"] = days_with(pd_all, dry=True).astype(np.float32)
    ndays = len(pd_all)

    # avstånd till närmaste radar (km) och närmaste vindkraftverk
    yy, xx = np.mgrid[0:h, 0:w]
    drad = np.full((h, w), 1e9)
    near_code = np.empty((h, w), "<U5")
    for code, (r0, c0) in rpx.items():
        d = np.hypot(yy - r0, xx - c0) * 2.015
        better = d < drad
        drad[better] = d[better]
        near_code[better] = code
    wind = np.zeros((h, w), bool)
    vf = OUT / "vind" / "osm_vindkraft.json"
    nturb = 0
    if vf.exists():
        ll = np.array(json.loads(vf.read_text()))
        r, c = to_rc(ll[:, 0], ll[:, 1])
        ok = (r >= 0) & (r < h) & (c >= 0) & (c < w)
        wind[r[ok].astype(int), c[ok].astype(int)] = True
        nturb = int(ok.sum())
    from scipy.ndimage import binary_dilation, distance_transform_edt
    wind_near = binary_dilation(wind, iterations=1)  # inom en ruta (2 km)
    sea = hz <= 0.5
    coast_km = distance_transform_edt(sea) * 2.015  # avstånd in i havet från land
    dhdy, dhdx = np.gradient(hz)
    slope = np.hypot(dhdx, dhdy) / 2015.0

    # ekrar i ekofrekvensens överskott, per radar
    sp, prof = spokes(D["overskott"], rpx, (h, w))
    sp_tr, _ = spokes(Dtr["overskott"], rpx, (h, w))
    sp_va, _ = spokes(Dva["overskott"], rpx, (h, w))
    # ekrar per dag (solen och tillfälliga störningar)
    day_spokes = []
    for d, (ne, nv, *_rest) in pd_all.items():
        f = ne / np.maximum(nv, 1)
        f[nv < 100] = np.nan
        ex = f - uniform_filter(np.nan_to_num(f), 15)  # medel i stället för median per dag, för tidens skull
        ex[nv < 100] = np.nan
        res, _ = spokes(ex, rpx, (h, w), z_thr=6.0)
        for s in res:
            if s["overskott"] < 0.03:
                continue
            lat = composite.RADARS[s["radar"]][0]
            sa = sun_azimuths(d, lat)
            s["dag"] = d
            s["solen"] = bool(sa and min(abs(s["azimut"] - a) for a in sa) <= 8)
            day_spokes.append(s)

    # kandidater: valda på träningsdagarna
    cov = np.nan_to_num(T_tr["nv"]) >= 2000
    cand = cov & ((np.nan_to_num(Dtr["overskott"]) >= 0.05) |
                  ((np.nan_to_num(Dtr["f_torr"]) >= 0.10) & (T_tr["ndv"] >= 300)))
    spoke_px = np.zeros((h, w), bool)
    for s in sp:
        r0, c0 = rpx[s["radar"]]
        a = np.radians(s["azimut"] + 0.5)
        for rr in np.arange(10, 120, 0.5):
            r_, c_ = int(r0 - rr * np.cos(a)), int(c0 + rr * np.sin(a))
            if 0 <= r_ < h and 0 <= c_ < w:
                spoke_px[r_, c_] = True
    spoke_px = binary_dilation(spoke_px, iterations=1)

    typ = np.zeros((h, w), np.uint8)
    TYPER = {1: "närklotter vid radar", 2: "havsklotter", 3: "vindkraft", 4: "eker", 5: "fast klotter (land)",
             6: "möjlig orografi", 7: "övrigt"}
    still = np.nan_to_num(D["euler_lagr"], nan=1.0)
    fdry = np.nan_to_num(D["f_torr"])
    lyft = np.nan_to_num(D["lyft"], nan=1.0)
    typ[cand] = 7
    oro = cand & (hz >= 300) & (lyft >= 1.3) & (fdry < 0.05)
    typ[oro] = 6
    fast = cand & ((still < 0.6) | (fdry >= 0.10)) & ~sea
    typ[fast] = 5
    typ[cand & spoke_px] = 4
    typ[cand & wind_near] = 3
    typ[cand & sea] = 2
    typ[cand & (drad <= 15)] = 1

    # tabell över de värsta rutorna: poäng = överskott + torr-andel, en per 10 km-block
    score = np.nan_to_num(D["overskott"]) + np.nan_to_num(D["f_torr"])
    score[~cand] = -1
    worst = []
    used = np.zeros((h, w), bool)
    for idx in np.argsort(score.ravel())[::-1]:
        r, c = divmod(int(idx), w)
        if score[r, c] <= 0 or len(worst) >= 40:
            break
        if used[r, c]:
            continue
        used[max(0, r - 5):r + 6, max(0, c - 5):c + 6] = True
        lat, lon = latlon(r, c)
        worst.append({
            "rad": r, "kol": c, "lat": lat, "lon": lon, "typ": TYPER.get(int(typ[r, c]), "-"),
            "f_eko": round(float(D["f_eko"][r, c]), 3), "overskott": round(float(D["overskott"][r, c]), 3),
            "f_torr": round(float(np.nan_to_num(D["f_torr"][r, c])), 3),
            "f_torr_val": round(float(np.nan_to_num(Dva["f_torr"][r, c])), 3),
            "overskott_val": round(float(np.nan_to_num(Dva["overskott"][r, c])), 3),
            "euler_lagr": round(float(np.nan_to_num(D["euler_lagr"][r, c], nan=-1)), 2),
            "f_still": round(float(np.nan_to_num(D["f_still"][r, c])), 3),
            "tex": round(float(np.nan_to_num(D["tex"][r, c])), 1), "d5": round(float(np.nan_to_num(D["d5"][r, c])), 1),
            "dbz": round(float(np.nan_to_num(D["dbz_medel"][r, c])), 1),
            "f_iso": round(float(np.nan_to_num(D["f_iso"][r, c])), 3),
            "lyft": round(float(lyft[r, c]), 2), "dagar_eko30": int(D["dagar_eko30"][r, c]),
            "hojd": int(hz[r, c]), "radar": str(near_code[r, c]), "radar_km": int(drad[r, c]),
        })

    # klasser: medianer av kännetecknen
    feats = ["f_eko", "overskott", "f_torr", "f_vat", "euler_lagr", "f_still", "tex", "dbz_medel", "dbz_sd", "d5",
             "flip", "f_iso", "lyft", "dagar_eko30", "dagar_torr30"]
    klasser = {}
    groups = {TYPER[k]: typ == k for k in TYPER}
    groups["alla täckta (referens)"] = cov
    groups["fjäll/höjd > 400 m, ej kandidat"] = cov & (hz > 400) & ~cand
    groups["låglandet < 100 m, ej kandidat"] = cov & (hz < 100) & ~cand & ~sea
    groups["vindkraftsrutor (alla)"] = cov & wind
    groups["ring 4 till 10 km kring vindkraft"] = cov & binary_dilation(wind, iterations=5) & ~binary_dilation(wind, iterations=2)
    for name, m in groups.items():
        n = int(m.sum())
        klasser[name] = {"rutor": n}
        if n:
            for f in feats:
                v = D[f][m]
                v = v[np.isfinite(v)]
                klasser[name][f] = round(float(np.median(v)), 3) if v.size else None
                if f in ("overskott", "f_torr"):
                    klasser[name][f + "_p90"] = round(float(np.percentile(v, 90)), 3) if v.size else None

    # stabilitet: står kandidaterna kvar på valideringsdagarna?
    cand_va = cov & ((np.nan_to_num(Dva["overskott"]) >= 0.05) |
                     ((np.nan_to_num(Dva["f_torr"]) >= 0.10) & (T_va["ndv"] >= 150)))
    stab = {"kandidater_traning": int(cand.sum()), "kandidater_validering": int(cand_va.sum()),
            "bada": int((cand & cand_va).sum()),
            "per_typ_kvar_i_validering": {TYPER[k]: [int((typ == k).sum()), int(((typ == k) & cand_va).sum())] for k in TYPER}}
    terr = {}
    for name, m in {"över 400 m": cov & (hz > 400), "300 till 400 m": cov & (hz > 300) & (hz <= 400),
                    "lutning > 2 %": cov & (slope > 0.02), "lyft > 1,3 och > 300 m": cov & (hz > 300) & (lyft > 1.3)}.items():
        terr[name] = {"rutor": int(m.sum()), "kandidater": int((m & cand).sum()),
                      "per_typ": {TYPER[k]: int((m & (typ == k)).sum()) for k in TYPER if (m & (typ == k)).any()}}

    tab = {"dagar": ndays, "dagar_traning": len(pd_tr), "dagar_validering": len(pd_va), "vindkraftverk": nturb,
           "klasser": klasser, "stabilitet": stab, "terrang": terr, "varst": worst,
           "ekrar": sorted(sp, key=lambda s: -s["z"]),
           "ekrar_traning": len(sp_tr), "ekrar_validering": len(sp_va),
           "ekrar_bada": sum(1 for s in sp_tr if any(t["radar"] == s["radar"] and abs(t["azimut"] - s["azimut"]) <= 1 for t in sp_va)),
           "ekrar_per_dag": sorted(day_spokes, key=lambda s: -s["z"])[:60],
           "ekrar_per_dag_antal": len(day_spokes), "ekrar_per_dag_solen": sum(s["solen"] for s in day_spokes)}
    (OUT / "tabell.json").write_text(json.dumps(tab, indent=1, ensure_ascii=False))
    np.savez_compressed(OUT / "kartor.npz", **{k: v.astype(np.float16) for k, v in D.items()}, typ=typ,
                        kandidat=cand, kandidat_val=cand_va, vind=wind, hojd=hz.astype(np.float16),
                        transform=np.array(grid.transform)[:6], crs=str(grid.crs))
    bilder(D, typ, hz, rpx, wind, TYPER)
    print(json.dumps({k: tab[k] for k in ("dagar", "vindkraftverk", "stabilitet", "ekrar_traning", "ekrar_validering", "ekrar_bada",
                                          "ekrar_per_dag_antal", "ekrar_per_dag_solen")}, ensure_ascii=False, indent=1))


def bilder(D, typ, hz, rpx, wind, TYPER):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    out = OUT / "bild"
    out.mkdir(exist_ok=True)
    for name, vmax, cmap in [("f_eko", 0.3, "viridis"), ("overskott", 0.15, "magma"), ("f_torr", 0.2, "magma"),
                             ("euler_lagr", 1.2, "RdBu"), ("lyft", 3.0, "PuOr"), ("tex", 15, "viridis"),
                             ("dagar_eko30", 20, "viridis")]:
        fig, ax = plt.subplots(figsize=(5, 9), dpi=110)
        im = ax.imshow(D[name], vmin=0, vmax=vmax, cmap=cmap, interpolation="nearest")
        ax.contour(hz, [400], colors="w", linewidths=0.3)
        for code, (r, c) in rpx.items():
            ax.plot(c, r, "r+", ms=5)
        ax.set_title(name)
        ax.set_xlim(0, hz.shape[1]); ax.set_ylim(hz.shape[0], 0)
        fig.colorbar(im, ax=ax, shrink=0.6)
        fig.savefig(out / f"{name}.png", bbox_inches="tight")
        plt.close(fig)
    cols = ["#00000000", "red", "blue", "orange", "magenta", "black", "green", "grey"]
    fig, ax = plt.subplots(figsize=(5, 9), dpi=110)
    ax.imshow(hz, cmap="Greys", vmin=0, vmax=1500, alpha=0.5)
    t = np.ma.masked_equal(typ, 0)
    ax.imshow(t, cmap=ListedColormap(cols[1:]), vmin=1, vmax=7, interpolation="nearest")
    for code, (r, c) in rpx.items():
        ax.plot(c, r, "c+", ms=6)
    ax.set_xlim(0, hz.shape[1]); ax.set_ylim(hz.shape[0], 0)
    ax.set_title(" ".join(f"{k}={v}" for k, v in TYPER.items()), fontsize=5)
    fig.savefig(out / "typ.png", bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
