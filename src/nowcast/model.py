"""Prognosmodellen.

Referens: optiskt flöde (Lucas-Kanade) på de senaste radarbilderna och
semi-Lagrangesk extrapolering av den senaste bilden, med pysteps. Ingen träning.
Antar att nederbörden bevaras längs banorna, så terrängbunden nederbörd
(uppglidning, regnskugga) flyttas med vinden i stället för att stå kvar.
En ny modell ska ha samma signatur och slå den här i verifieringen.
"""

import numpy as np
from pysteps.extrapolation.semilagrangian import extrapolate
from pysteps.motion.lucaskanade import dense_lucaskanade
from pysteps.utils.transformation import dB_transform


def nowcast(obs: np.ndarray, steps: int) -> np.ndarray:
    """obs: (T, H, W) i mm/h med 5 min mellan bilderna, äldst först, NaN utanför täckning.

    Returnerar (steps, H, W) i mm/h, ett fält per 5 min. NaN där det saknas underlag.
    """
    filled = np.nan_to_num(obs, nan=0.0)
    db, _ = dB_transform(filled, threshold=0.1, zerovalue=-15.0)
    velocity = dense_lucaskanade(db)
    forecast = extrapolate(filled[-1], velocity, steps)
    forecast[:, np.isnan(obs[-1])] = np.nan
    return forecast
