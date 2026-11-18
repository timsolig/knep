"""Uppgift 0028: ringarna vid Røst och Andøya i OPERA-delen av A0.

    uv run python experiments/riksgransen/ring_karta.py frekvens   andel bilder med eko per ruta, träningsdagar -> /dev/shm/opera_ring/frek_traning.npz
    uv run python experiments/riksgransen/ring_karta.py profil     radiell profil kring platserna och kartan

OPERA ur /data/riksgransen/opera15/ (var 15:e minut, kodning som SMHI). Bara dagar i träningen
väljs på; valideringsdagarna används en gång för den frysta kandidaten (ring_kand.py). Testdelen
läses aldrig: dagarna kommer ur domare.days('traning'/'validering'), som kontrollerar det.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
from scipy.ndimage import uniform_filter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import zon  # noqa: E402
from knep.analys import composite  # noqa: E402

_spec = importlib.util.spec_from_file_location("analys_domare", HERE.parent / "analys" / "domare.py")
domare = importlib.util.module_from_spec(_spec)
sys.modules["analys_domare"] = domare
_spec.loader.exec_module(domare)

TMP = Path("/dev/shm/opera_ring")
WET = 0.1  # mm/h
WIN = 21   # 42 km
# kodvärdet som svarar mot 0,1 mm/h
V_WET = int(np.ceil((10 * np.log10(composite.ZR_A * WET ** composite.ZR_B) + 30) / 0.4))


def dagar(del_: str) -> list[str]:
    """Dagar med OPERA-fil i delen (aldrig test)."""
    return [d for d in domare.days(del_) if (zon.OPERA_DIR / f"{d}.npz").exists()]


def eko_dag(day: str):
    """(eko bool (n,H,W), täckt bool (n,H,W)) för dagen, utan bilder där OPERA saknas helt."""
    z = np.load(zon.OPERA_DIR / f"{day}.npz")
    v = z["v"]
    cov = v != 255
    keep = cov.reshape(len(v), -1).mean(1) > 0.2
    return (v >= V_WET)[keep] & cov[keep], cov[keep]


def torra_grannar(eko, cov):
    """Per bild: ingen annan ruta inom 42 km (fyrkantigt fönster som i F4) har eko. Andelen
    eko i omgivningen utan rutan själv < 1/(WIN²) av de täckta rutorna, alltså noll eko."""
    out = np.empty(eko.shape, bool)
    n = WIN * WIN
    for i in range(len(eko)):
        e = uniform_filter(eko[i].astype(np.float32), WIN, mode="constant") * n
        c = uniform_filter(cov[i].astype(np.float32), WIN, mode="constant") * n
        # eko bland grannarna (utan rutan själv); torrt om under 0,5 ruta eko
        out[i] = (e - eko[i]) < 0.5
    return out


def frekvens() -> None:
    TMP.mkdir(exist_ok=True)
    g = None
    s = {"n": 0}
    for d in dagar("traning"):
        eko, cov = eko_dag(d)
        tg = torra_grannar(eko, cov)
        if g is None:
            g = {"eko": np.zeros(eko.shape[1:], np.float64), "cov": np.zeros(eko.shape[1:], np.float64),
                 "torr": np.zeros(eko.shape[1:], np.float64)}
        g["eko"] += eko.sum(0)
        g["cov"] += cov.sum(0)
        g["torr"] += (eko & tg).sum(0)
        s["n"] += len(eko)
        print(d, len(eko), flush=True)
    np.savez_compressed(TMP / "frek_traning.npz", **g, n=s["n"])


def main():
    {"frekvens": frekvens}[sys.argv[1]]()


if __name__ == "__main__":
    main()
