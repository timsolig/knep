"""Jämför viktning och regularisering för extremkalibreringen på tre utelämnade händelser.

    python experiments/tune_extremes.py rmi_20210704 mch_20150515 fmi_20160928
"""
import sys, time, numpy as np
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parents[1] / "src"))
from knep.extremes import FEATURES, MONO
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
F = sys.argv.pop(1) if len(sys.argv) > 1 and sys.argv[1].endswith("/") else "gen/ext/features/"
ALL = ["fmi_20160928", "fmi_20170509", "knmi_20100826", "mch_20150515", "mch_20170131", "rmi_20210704"]
rng = np.random.default_rng(0)
D = {}
for n in ALL:
    d = np.load(F + n + ".npz")
    s = rng.random(len(d["y"])) < 0.35
    D[n] = (d["X"][s], d["y"][s], d["w"][s])
DOM = [FEATURES.index(k) for k in ("q99", "q999", "wet")]
configs = {
    "A full vikt, utan händelsedrag": dict(wp=1.0, drop=DOM, leaf=200, l2=1.0),
    "B rotvikt, alla drag": dict(wp=0.5, drop=[], leaf=200, l2=1.0),
    "C rotvikt, utan händelsedrag": dict(wp=0.5, drop=DOM, leaf=200, l2=1.0),
    "D full vikt, grova löv": dict(wp=1.0, drop=[], leaf=3000, l2=10.0),
    "E rotvikt, grova löv": dict(wp=0.5, drop=[], leaf=3000, l2=10.0),
}
for held in sys.argv[1:]:
    tr = [n for n in ALL if n != held]
    X = np.concatenate([D[n][0] for n in tr]); y = np.concatenate([D[n][1] for n in tr]); w = np.concatenate([D[n][2] for n in tr])
    Xt, yt, wt = D[held]
    for cname, c in configs.items():
        keep = [i for i in range(len(FEATURES)) if i not in c["drop"]]
        mono = [1 if FEATURES[i] in MONO else 0 for i in keep]
        line = f"{held:14s} {cname:32s}"
        for thr in (5.0, 10.0, 20.0):
            o = (yt >= thr).astype(int)
            if o.sum() < 20:
                line += f" | {thr:.0f}: få fall"; continue
            m = HistGradientBoostingClassifier(learning_rate=0.08, max_iter=150, max_leaf_nodes=31, min_samples_leaf=c["leaf"],
                                               l2_regularization=c["l2"], monotonic_cst=mono, random_state=0, early_stopping=False)
            m.fit(X[:, keep], (y >= thr).astype(np.int8), sample_weight=w ** c["wp"])
            p = m.predict_proba(Xt[:, keep])[:, 1]
            base = np.average(o, weights=wt); bs = np.average((p - o) ** 2, weights=wt)
            line += f" | {thr:.0f}: AUC {roc_auc_score(o, p, sample_weight=wt):.3f} BSS {1 - bs / (base * (1 - base)):+.3f} kvot {np.average(p, weights=wt) / base:.2f}"
        print(line, flush=True)
