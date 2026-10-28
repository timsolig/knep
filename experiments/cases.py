"""Inläsning av öppna radarfall från pysteps-data, omräknade till regnintensitet på 2 km.

Fallen används för att mäta designval som inte kräver träning:
kadens och fördröjning, rörelsefältets stabilitet och skaldämpning.
2 km väljs för att motsvara SMHI:s öppna komposit.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import numpy as np
from pysteps import io
from pysteps.utils import conversion

CASES = {
    # namn: (katalog, filmönster, läsare)
    "fmi_20160928": ("radar/fmi/pgm/20160928", r"(\d{12})_fmi", "fmi"),
    "fmi_20170509": ("radar/fmi/pgm/20170509", r"(\d{12})_fmi", "fmi"),
    "mch_20150515": ("radar/mch/20150515", r"AQC(\d{9})", "mch"),
    "mch_20170131": ("radar/mch/20170131", r"AQC(\d{9})", "mch"),
    # extremfall för träning och test av kraftig nederbörd
    "knmi_20100826": ("radar/KNMI/2010/08", r"5min_(\d{12})", "knmi"),
    "rmi_20210704": ("radar/rmi/radqpe/20210704", r"^(\d{12})00\.rad", "rmi"),
}


def _time(name: str, pattern: str, kind: str) -> datetime:
    s = re.search(pattern, name).group(1)
    if kind in ("fmi", "knmi", "rmi"):
        return datetime.strptime(s, "%Y%m%d%H%M")
    return datetime.strptime(s, "%y%j%H%M")  # MeteoSwiss: år, dag på året, tid


def load(root: Path, case: str, km: int = 2) -> tuple[np.ndarray, list[datetime], dict]:
    """Returnerar (T, H, W) i mm/h, NaN utanför täckning, tider och metadata."""
    sub, pattern, kind = CASES[case]
    files = sorted((root / sub).iterdir(), key=lambda p: _time(p.name, pattern, kind))
    fields, times, meta = [], [], None
    for f in files:
        if kind == "fmi":
            r, _, md = io.import_fmi_pgm(str(f), gzipped=True)
            r, md = conversion.to_rainrate(r, md, zr_a=223.0, zr_b=1.53)
        elif kind == "knmi":
            r, _, md = io.import_knmi_hdf5(str(f), qty="ACRR", accutime=5.0)
            r, md = conversion.to_rainrate(r, md)
        elif kind == "rmi":
            r, _, md = io.import_odim_hdf5(str(f), qty="RATE")
        else:
            r, _, md = io.import_mch_gif(str(f), product="AQC", unit="mm", accutime=5.0)
            r, md = conversion.to_rainrate(r, md)
        if md["xpixelsize"] < 100:  # KNMI anger pixelstorlek i km
            md = dict(md, xpixelsize=md["xpixelsize"] * 1000, ypixelsize=md["ypixelsize"] * 1000)
        fields.append(r)
        times.append(_time(f.name, pattern, kind))
        meta = md
    obs = np.stack(fields).astype(np.float32)
    k = int(round(km * 1000 / meta["xpixelsize"]))
    if k > 1:
        t, h, w = obs.shape
        h, w = h - h % k, w - w % k
        obs = obs[:, :h, :w].reshape(t, h // k, k, w // k, k).mean(axis=(2, 4))  # NaN smittar, som i en komposit
        meta = dict(meta, xpixelsize=meta["xpixelsize"] * k, ypixelsize=meta["ypixelsize"] * k)
    obs[obs < 0.1] = 0.0
    # beskär till den del som någon gång har täckning, så att stora tomma ytor inte kostar tid
    ok = np.isfinite(obs).any(axis=0)
    rows, cols = np.where(ok.any(axis=1))[0], np.where(ok.any(axis=0))[0]
    obs = obs[:, rows[0] : rows[-1] + 1, cols[0] : cols[-1] + 1]
    meta = dict(meta, crop=(int(rows[0]), int(cols[0])))
    return obs, times, meta


if __name__ == "__main__":
    import sys

    root = Path(sys.argv[1])
    for c in CASES:
        obs, times, meta = load(root, c)
        valid = np.isfinite(obs[0])
        wet = np.nanmean(obs >= 1.0, axis=(1, 2))
        print(
            f"{c}: {obs.shape}, {times[0]:%H:%M}..{times[-1]:%H:%M}, "
            f"pixel {meta['xpixelsize']:.0f} m, täckning {valid.mean():.0%}, "
            f"andel >=1 mm/h {wet.min():.1%}..{wet.max():.1%}, max {np.nanmax(obs):.0f} mm/h"
        )
