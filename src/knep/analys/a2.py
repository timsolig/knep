"""A2T: analysen A1 rättad mot SMHI:s regnmätare, för en timme och dess fyra kvartar.

Avstängd: körs inte i cli.py. Metoden och parametrarna är A2T ur experiments/analys/a2.py
(system_params("A2T")), som slår A0 och A1 enligt analysens domare på valideringen; se
experiments/bakgrund/rapporter/2026-11-07/0001-a2-falska-ekon.md. Likheten med experimentet prövas i
tests/test_a2_src.py och experiments/analys/a2_src_likhet.py.

För varje period (timmen eller en kvart):

1. Kvoten i stor skala k(x) = (Σ w·g + α) / (Σ w·a + α) över timmätarna (g mätaren, a A1:s timsumma i
   mätarens ruta) i fönstret, de senaste WIN timmarna till och med timmen, med Gaussvikter med längden
   L_STOR. Klipps till [1/4, 4] och räknas på var 16:e ruta. För kvarten gäller k högst 1 där A1 är under
   K_SVAG (ingen uppskalning av svagt eko).
2. Optimal interpolation i kvadratrotsskala av d = √g − √(k·A1) vid periodens mätare, bakgrundens fel
   σ_b = SB·√(1 + C·(avstånd till närmaste radar / 100 km)²), korrelationen exp(−r/L) och mätarnas fel SO.
   Tillskottet räknas på var 4:e ruta och interpoleras bilinjärt; A2 = max(√(k·A1) + Δ, 0)².
3. Tak (kvarten): där 0 < A1 < K_SVAG blir A2 högst A1.
4. Torrmask: där A1 är under TORR och alla periodens mätare inom R_TORR km är torra (minst en) blir A2 0.

NaN i A1 (utanför täckningen) bevaras. Fälten är mm per period på radarns rutnät.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.distance import cdist

STEG = 4      # OI-tillskottet räknas på var 4:e ruta
STEG_K = 16   # kvoten i stor skala på var 16:e ruta
KMAX = 4.0    # kvoten klipps till [1/KMAX, KMAX]
# avstånden räknas med 2,0 km per ruta som i domaren och experimentet (RES_KM), där parametrarna valdes,
# fast SMHI:s rutnät har 2,015 km; längdskalorna nedan gäller alltså i den enheten
RES_KM = 2.0

# A2T, frysta värden ur system_params("A2T") i experiments/analys/a2.py (PARAMS och FRYSTA["A2T"]),
# valda på träningsdagarna; se rapporterna 2026-11-06/3-a2.md och 2026-11-07/0001-a2-falska-ekon.md.
# Ändra inte utan att domaren körs om.
TIMME = {"L_STOR": 75.0, "ALFA": 8.0, "WIN": 6, "L": 40.0, "SB": 1.6, "C": 1.0, "SO": 0.3,
         "TORR": 0.05, "R_TORR": 80.0, "K_SVAG": 0.0}
KVART = {"L_STOR": 75.0, "ALFA": 8.0, "WIN": 6, "L": 40.0, "SB": 0.8, "C": 1.0, "SO": 0.15,
         "TORR": 0.0125, "R_TORR": 80.0, "K_SVAG": 0.125}


@dataclass
class Matare:
    """Mätarvärden för en period (eller för fönstret): rad och kolumn på rutnätet och mm.

    a1 är A1 i mätarens ruta för samma period; behövs bara för fönstret (timmarna före den aktuella)."""

    rad: np.ndarray
    kol: np.ndarray
    mm: np.ndarray
    a1: np.ndarray | None = None

    def __post_init__(self):
        self.rad = np.asarray(self.rad, int)
        self.kol = np.asarray(self.kol, int)
        self.mm = np.asarray(self.mm, float)
        if self.a1 is not None:
            self.a1 = np.asarray(self.a1, float)

    def __len__(self):
        return len(self.mm)

    @staticmethod
    def tom() -> "Matare":
        return Matare(np.zeros(0, int), np.zeros(0, int), np.zeros(0), np.zeros(0))


def radaravstand_km(grid) -> np.ndarray:
    """Avståndet till närmaste radar i composite.RADARS, km per ruta (float32)."""
    from pyproj import Transformer

    from knep.analys.composite import RADARS
    tr = Transformer.from_crs("EPSG:4326", grid.crs, always_xy=True)
    h, w = grid.shape
    rr, cc = np.mgrid[0:h, 0:w]
    x, y = grid.transform * (cc + 0.5, rr + 0.5)
    best = np.full((h, w), np.inf, np.float32)
    for lat, lon, _, _ in RADARS.values():
        x0, y0 = tr.transform(lon, lat)
        best = np.minimum(best, (np.hypot(x - x0, y - y0) / 1000.0).astype(np.float32))
    return best


def _kvot(xy_t, xy_g, g, a, p):
    ok = np.isfinite(g) & np.isfinite(a)
    if not ok.any():
        return np.ones(len(xy_t))
    xy_g, g, a = xy_g[ok], g[ok], a[ok]
    w = np.exp(-0.5 * cdist(xy_t, xy_g, "sqeuclidean") / p["L_STOR"] ** 2)
    return np.clip((w @ g + p["ALFA"]) / (w @ a + p["ALFA"]), 1.0 / KMAX, KMAX)


def _sigma_b(rng_km, p):
    return p["SB"] * np.sqrt(1.0 + p["C"] * (rng_km / 100.0) ** 2)


def _svag(k, a1, p):
    """Ingen uppskalning där A1 är under K_SVAG."""
    return np.where(a1 < p["K_SVAG"], np.minimum(k, 1.0), k) if p["K_SVAG"] > 0 else k


def _upp(grov, shape, steg):
    """Bilinjärt från rutorna 0, steg, 2·steg, ... till hela rutnätet."""
    import cv2
    h, w = shape
    mx, my = np.meshgrid(np.arange(w, dtype=np.float32) / steg, np.arange(h, dtype=np.float32) / steg)
    return cv2.remap(np.ascontiguousarray(grov, dtype=np.float32), mx, my, cv2.INTER_LINEAR,
                     borderMode=cv2.BORDER_REPLICATE)


class A2T:
    """A2T på ett rutnät. rng_km är avståndet till närmaste radar (radaravstand_km), res_km rutans sida
    i avståndens enhet (se RES_KM)."""

    def __init__(self, rng_km: np.ndarray, res_km: float = RES_KM):
        self.shape = rng_km.shape
        self.rng = rng_km
        self.res = res_km
        h, w = self.shape
        rr, cc = np.mgrid[0:h:STEG, 0:w:STEG]
        self.cshape = rr.shape
        self.cxy = np.c_[cc.ravel(), rr.ravel()].astype(float) * res_km
        self.crng = rng_km[::STEG, ::STEG].ravel().astype(float)
        rr, cc = np.mgrid[0:h:STEG_K, 0:w:STEG_K]
        self.kshape = rr.shape
        self.kxy = np.c_[cc.ravel(), rr.ravel()].astype(float) * res_km

    @classmethod
    def fran_grid(cls, grid) -> "A2T":
        return cls(radaravstand_km(grid))

    def _xy(self, m: Matare):
        return np.c_[m.kol, m.rad].astype(float) * self.res

    def _period(self, a1, m: Matare, kvot_k, kvot_g, p):
        xy = self._xy(m)
        a = a1[m.rad, m.kol].astype(float)
        f0 = np.nan_to_num(a1, nan=0.0)
        kf = _svag(_upp(kvot_k, self.shape, STEG_K), f0, p)
        kvot_g = _svag(kvot_g, a, p)
        out = np.maximum(kf * f0, 0.0)
        ok = np.isfinite(a)
        if ok.any():
            bg = np.sqrt(np.maximum(kvot_g[ok] * a[ok], 0.0))
            d = np.sqrt(m.mm[ok]) - bg
            sbg = _sigma_b(self.rng[m.rad[ok], m.kol[ok]].astype(float), p)
            r = cdist(xy[ok], xy[ok])
            B = sbg[:, None] * sbg[None, :] * np.exp(-r / p["L"])
            B[np.diag_indices_from(B)] += p["SO"] ** 2
            v = np.linalg.solve(B, d)
            kk = np.exp(cdist(self.cxy, xy[ok]).astype(np.float32) * np.float32(-1.0 / p["L"]))
            inc = (_sigma_b(self.crng, p) * (kk @ (sbg * v).astype(np.float32))).reshape(self.cshape)
            out = np.maximum(np.sqrt(out) + _upp(inc, self.shape, STEG), 0.0) ** 2
        if p["K_SVAG"] > 0:  # taket över svagt eko
            out = np.where((f0 > 0) & (f0 < p["K_SVAG"]), np.minimum(out, f0), out)
        if len(m):
            # torrmasken på det glesa rutnätet (närmaste mätare och närmaste våta mätare), upp med närmaste
            R = p["R_TORR"]
            d_any = cKDTree(xy).query(self.cxy, distance_upper_bound=R + 1)[0]
            vat = m.mm > 0
            d_vat = cKDTree(xy[vat]).query(self.cxy, distance_upper_bound=R + 1)[0] if vat.any() \
                else np.full(len(self.cxy), np.inf)
            torr = ((d_any <= R) & (d_vat > R)).reshape(self.cshape)
            h, w = self.shape
            torr = np.repeat(np.repeat(torr, STEG, 0), STEG, 1)[:h, :w] & (f0 < p["TORR"])
            out[torr] = 0.0
        return np.where(np.isfinite(a1), out, np.nan).astype(np.float32)

    def timme(self, a1_timme: np.ndarray, a1_kvartar: np.ndarray, fonster: Matare, timmatare: Matare,
              kvartsmatare: list[Matare]) -> tuple[np.ndarray, np.ndarray]:
        """A2T:s timsumma (H, W) och fyra kvartssummor (4, H, W), mm per period.

        a1_timme, a1_kvartar: A1 för timmen och dess kvartar (NaN utanför täckningen).
        fonster: timmätarna för de WIN senaste timmarna till och med timmen, med A1:s timsumma i a1.
        timmatare: timmens mätare; kvartsmatare: en Matare per kvart. Mätare utan värde (NaN) tas bort."""
        rena = [_utan_nan(m) for m in (fonster, timmatare, *kvartsmatare)]
        fonster, timmatare, kvartsmatare = rena[0], rena[1], rena[2:]
        xy_f = self._xy(fonster)
        a_f = fonster.a1 if fonster.a1 is not None else np.full(len(fonster), np.nan)
        out_k = np.empty((len(kvartsmatare),) + self.shape, np.float32)
        out_t = None
        for p, perioder in ((TIMME, [(a1_timme, timmatare)]),
                            (KVART, list(zip(a1_kvartar, kvartsmatare)))):
            kvot_k = _kvot(self.kxy, xy_f, fonster.mm, a_f, p).reshape(self.kshape)
            for i, (f, m) in enumerate(perioder):
                kvot_g = _kvot(self._xy(m), xy_f, fonster.mm, a_f, p)
                res = self._period(np.asarray(f, np.float32), m, kvot_k, kvot_g, p)
                if p is TIMME:
                    out_t = res
                else:
                    out_k[i] = res
        return out_t, out_k


def _utan_nan(m: Matare) -> Matare:
    ok = np.isfinite(m.mm)
    if ok.all():
        return m
    return Matare(m.rad[ok], m.kol[ok], m.mm[ok], None if m.a1 is None else m.a1[ok])
