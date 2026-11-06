"""Filter mot fast klotter i A0, ett val som är av som standard (`bygg(..., klotter_path=...)`,
`knep --klotter KARTA`). Kartdelen av F4 i experiments/analys/filter.py; domaren bedömde den på
valideringen natten 2026-11-06 (experiments/natt/rapporter/2026-11-06/4-filter.md). Kartan för F4
är den utan utvidgning (`filter.py karta_drift` skriver den med nyckeln `klotter`).

En karta över misstänkta klotterrutor räknas en gång utanför driften (experiments/analys/filter.py,
ur eko under torra mätartimmar, textur och isolering, inte ur hur ofta rutan är våt). I varje bild
tas ekot på en misstänkt ruta bort bara om omgivningen inom 42 km (utan de misstänkta rutorna)
nästan saknar eko. Regn på en misstänkt ruta när det regnar omkring, som orografisk nederbörd,
står kvar.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy.ndimage import uniform_filter

ECHO = 0.1      # mm/h
WIN = 21        # rutor om 2 km, 42 km
KONTEXT = 0.03  # andel eko i omgivningen under vilken ekot på en misstänkt ruta tas bort


def load(path: Path | None, shape: tuple[int, int]) -> np.ndarray | None:
    """Kartan (bool, rutnätets form) eller None om den saknas eller har fel form."""
    if path is None or not Path(path).exists():
        return None
    m = np.load(path)["klotter"].astype(bool)
    return m if m.shape == shape else None


def rensa(rain: np.ndarray, klotter: np.ndarray | None, kontext: float = KONTEXT) -> np.ndarray:
    """rain (mm/h, NaN utanför täckningen) utan klotter: eko på misstänkta rutor sätts till 0 där
    omgivningen har eko i mindre än andelen `kontext` av de täckta rutorna."""
    if klotter is None:
        return rain
    cov = np.isfinite(rain)
    echo = cov & (np.nan_to_num(rain, nan=0.0) >= ECHO)
    if not (echo & klotter).any():
        return rain
    e = uniform_filter((echo & ~klotter).astype(np.float32), WIN)
    c = uniform_filter((cov & ~klotter).astype(np.float32), WIN)
    kill = klotter & echo & (e < kontext * np.maximum(c, 1e-3))
    if not kill.any():
        return rain
    out = rain.copy()
    out[kill] = 0.0
    return out
