"""Tränad extremkalibrering ovanpå kedjan (lk30, matchning, platskarta).

En gradient boosting-modell per tröskel (1, 5, 10, 20 mm/h) lär sig sannolikheten att
radarn överskrider tröskeln i en pixel, givet lagrangeska särdrag från kedjan:

  prognosen och dess grannskap   värde, max och medel i 6 till 62 km, andel över 1, 5, 10 mm/h
  trend längs banan              intensitetsändring de senaste 15 och 30 min, flyttad med rörelsen
  platskartan                    online-korrektionen och dess ramp med ledtid
  läget i händelsen              ledtid, fart, analysens 99- och 99,9-percentil och regnandel

Sannolikheterna används på två sätt:
  1. som sannolikhetskartor för kraftig nederbörd
  2. för att kalibrera kartan: den förväntade ytan över varje tröskel (summan av
     sannolikheterna) bestämmer hur kedjans värden skalas om, monotont, så att läge och
     struktur behålls men frekvensen av extremer blir rätt per situation och ledtid ("ext").

Validering: lämna en händelse utanför (träna på de andra, förutsäg den utelämnade).

    python experiments/extremes.py features <gen>
    python experiments/extremes.py train <gen>
    python experiments/extremes.py predict <gen>
    python experiments/extremes.py evalprob <gen> --out prob.json
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np
from scipy.ndimage import uniform_filter

sys.path.insert(0, str(Path(__file__).parent))
import verify  # noqa: E402
from generate import NS, encode, quiet  # noqa: E402

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from nowcast.extremes import FEATURES, MONO, THR, USE_THR, calibrate_tail, db, features, predict_proba, recalibrate  # noqa: E402

TRAIN_LEADS = [1, 2, 3, 4, 6, 8, 10, 12]
RNG = np.random.default_rng(0)


def load_case(path: Path):
    verify.OURS[:] = ["lk30", "oro_cdf"]
    cs = verify.Case(path)
    cs.motion = np.load(path)["motion"].astype(np.float32)
    return cs


def tendencies(cs, j):
    from pysteps.extrapolation.semilagrangian import extrapolate
    from nowcast.extremes import tendencies as _tend
    i = cs.issues[j]
    v = cs.motion[j]
    adv = lambda f, n: quiet(extrapolate, f, v, n)
    past15 = cs.obs[i - 3] if i >= 3 else None
    past30 = cs.obs[i - 6] if i >= 6 else None
    return _tend(cs.obs[i], past15, past30, v, NS, adv)


def lead_features(cs, j, k, tend15, tend30, speed, dom):
    """Särdrag för körning j och ledtid k på hela rutnätet, samt kedjans fält."""
    i = cs.issues[j]
    c = cs.inst("oro_cdf", i, i + k)
    return features(c, k, tend15, tend30, cs.corr_cdf[i], speed, dom), c


def build_features(gen: Path, out: Path, only=None):
    out.mkdir(parents=True, exist_ok=True)
    for path in sorted(p for p in gen.glob("*.npz") if not p.stem.endswith("_ext")):
        if (only and path.stem not in only) or (out / path.name).exists():
            continue
        t0 = time.time()
        cs = load_case(path)
        X, Y, W, K, I = [], [], [], [], []
        for j, i in enumerate(cs.issues):
            t15, t30, speed, dom = tendencies(cs, j)
            for k in TRAIN_LEADS:
                if i + k >= cs.n:
                    continue
                f, c = lead_features(cs, j, k, t15, t30, speed, dom)
                y = cs.obs[i + k]
                ok = np.isfinite(c) & np.isfinite(y)
                near = (f[3] >= db(0.3)) | (y >= 0.3)
                strong = (f[2] >= db(3.0)) | (y >= 3.0)
                extreme = (f[2] >= db(8.0)) | (y >= 8.0)
                # alla rader nära kraftig nederbörd, färre ju vanligare raden är; vikten återställer fördelningen
                p = np.where(extreme, 1.0, np.where(strong, 0.25, np.where(near, 0.04, 0.002)))
                keep = ok & (RNG.random(y.shape) < p)
                X.append(f[:, keep].T)
                Y.append(y[keep])
                W.append(1.0 / p[keep])
                K.append(np.full(keep.sum(), k, np.int8))
                I.append(np.full(keep.sum(), i, np.int16))
        np.savez_compressed(out / f"{cs.name}.npz", X=np.concatenate(X), y=np.concatenate(Y).astype(np.float32),
                            w=np.concatenate(W).astype(np.float32), k=np.concatenate(K), i=np.concatenate(I))
        n = sum(len(y) for y in Y)
        print(f"{cs.name}: {n} rader, {sum((y >= 10).sum() for y in Y)} med >= 10 mm/h, {time.time() - t0:.0f} s", flush=True)


def fit(X, y, w):
    """En klassificerare per tröskel.

    Valt i tune-jämförelsen (results/extremer.md): roten ur urvalsvikterna och grova löv.
    Fulla inversvikter låter de många torra raderna styra och ger dåliga modeller för
    10 och 20 mm/h på en ny händelse; rotvikter ger ROC-yta runt 0,96 vid 10 mm/h.
    """
    from sklearn.ensemble import HistGradientBoostingClassifier
    models = {}
    mono = [1 if n in MONO else 0 for n in FEATURES]
    for t in THR:
        m = HistGradientBoostingClassifier(learning_rate=0.08, max_iter=150, max_leaf_nodes=31, min_samples_leaf=3000,
                                           l2_regularization=10.0, monotonic_cst=mono, early_stopping=False, random_state=0)
        m.fit(X, (y >= t).astype(np.int8), sample_weight=np.sqrt(w))
        models[t] = m
    return models


def train(feat: Path, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    data = {p.stem: dict(np.load(p)) for p in sorted(feat.glob("*.npz"))}
    names = list(data)
    for held in names + ["alla"]:
        t0 = time.time()
        use = [n for n in names if n != held]
        X, y, w = [], [], []
        for n in use:
            d = data[n]
            # halva de vanliga raderna räcker; rader nära kraftig nederbörd behålls alla
            keep_all = (d["y"] >= 5) | (d["X"][:, FEATURES.index("max7")] >= db(5.0))
            pick = keep_all | (RNG.random(len(d["y"])) < 0.5)
            X.append(d["X"][pick])
            y.append(d["y"][pick])
            w.append(d["w"][pick] * np.where(keep_all[pick], 1.0, 2.0))
        X, y, w = np.concatenate(X), np.concatenate(y), np.concatenate(w)
        models = fit(X, y, w)
        with open(out / f"model_utan_{held}.pkl", "wb") as fh:
            import sklearn

            pickle.dump({"thr": THR, "features": FEATURES, "models": models, "sklearn": sklearn.__version__}, fh)
        its = {t: models[t].n_iter_ for t in THR}
        print(f"utan {held}: {len(y)} rader, iterationer {its}, {time.time() - t0:.0f} s", flush=True)


def predict(gen: Path, models_dir: Path):
    for path in sorted(p for p in gen.glob("*.npz") if not p.stem.endswith("_ext")):
        t0 = time.time()
        with open(models_dir / f"model_utan_{path.stem}.pkl", "rb") as fh:
            models = pickle.load(fh)["models"]
        cs = load_case(path)
        shape = (len(cs.issues), NS) + cs.obs.shape[1:]
        ext = np.zeros(shape, np.uint8)
        exth = np.zeros(shape, np.uint8)
        prob = np.zeros((len(THR),) + shape, np.uint8)
        for j, i in enumerate(cs.issues):
            t15, t30, speed, dom = tendencies(cs, j)
            for k in range(1, NS + 1):
                f, c = lead_features(cs, j, k, t15, t30, speed, dom)
                mask = np.isfinite(c) & (f[3] >= db(1.0))  # samma genväg som i driften
                P = predict_proba(models, f, mask)
                expected = P.reshape(len(THR), -1).sum(axis=1)
                ext[j, k - 1] = encode(calibrate_tail(c, expected))
                exth[j, k - 1] = encode(calibrate_tail(c, expected, weight=0.5))
                prob[:, j, k - 1] = np.round(P * 250).astype(np.uint8)
        np.savez_compressed(path.with_name(path.stem + "_ext.npz"), ext=ext, exth=exth, prob=prob)
        print(f"{cs.name}: förutsagt utanför urvalet på {time.time() - t0:.0f} s", flush=True)


def recal(gen: Path, models_dir: Path, final_model: Path | None):
    """Isoton omkalibrering av sannolikheterna, lärd på de andra fallens prognoser utanför urvalet.

    Skriver om ext, exth och prob i <fall>_ext.npz (råa sannolikheter sparas som prob_raw) och
    lägger tabellen för alla fall i den slutliga modellen.
    """
    from sklearn.isotonic import IsotonicRegression
    from nowcast.extremes import LEAD_BUCKETS, bucket
    paths = sorted(p for p in gen.glob("*.npz") if not p.stem.endswith("_ext"))
    samples = {}  # fall -> (tröskel, intervall) -> (p, y, w)
    for path in paths:
        cs = load_case(path)
        e = np.load(path.with_name(path.stem + "_ext.npz"))
        prob = e["prob_raw"] if "prob_raw" in e.files else e["prob"]
        acc = {}
        for j, i in enumerate(cs.issues):
            for k in range(1, NS + 1):
                if i + k >= cs.n:
                    continue
                y = cs.obs[i + k]
                ok = np.isfinite(y)
                for t in USE_THR:
                    p = prob[THR.index(t), j, k - 1][ok] / 250.0
                    o = (y[ok] >= t)
                    keep = (p >= 0.005) | o
                    rest = ~keep & (RNG.random(p.size) < 0.02)
                    a = acc.setdefault((t, bucket(k)), ([], [], []))
                    a[0].append(np.concatenate([p[keep], p[rest]]))
                    a[1].append(np.concatenate([o[keep], o[rest]]).astype(np.float32))
                    a[2].append(np.concatenate([np.ones(keep.sum()), np.full(rest.sum(), 50.0)]))
        samples[path.stem] = {key: tuple(np.concatenate(v) for v in val) for key, val in acc.items()}
        print(f"{path.stem}: prov för omkalibreringen insamlade", flush=True)

    def fit_tables(names):
        tables = {}
        for key in samples[names[0]]:
            p = np.concatenate([samples[n][key][0] for n in names])
            y = np.concatenate([samples[n][key][1] for n in names])
            w = np.concatenate([samples[n][key][2] for n in names])
            iso = IsotonicRegression(y_min=0.0, y_max=1.0, increasing=True, out_of_bounds="clip").fit(p, y, sample_weight=w)
            x = np.linspace(0, 1, 101)
            tables[key] = (x.astype(np.float32), iso.predict(x).astype(np.float32))
        return tables

    for path in paths:
        others = [n for n in samples if n != path.stem]
        tables = fit_tables(others)
        fold = models_dir / f"model_utan_{path.stem}.pkl"
        if fold.exists():  # tabellen följer med fallets modell, så att demoflikarna också är utanför urvalet
            with open(fold, "rb") as fh:
                d = pickle.load(fh)
            d["recal"] = tables
            with open(fold, "wb") as fh:
                pickle.dump(d, fh)
        cs = load_case(path)
        e = dict(np.load(path.with_name(path.stem + "_ext.npz")))
        raw = e.get("prob_raw", e["prob"])
        prob = np.zeros_like(raw)
        for j, i in enumerate(cs.issues):
            for k in range(1, NS + 1):
                P = recalibrate(raw[:, j, k - 1].astype(np.float32) / 250.0, k, tables)
                prob[:, j, k - 1] = np.round(P * 250).astype(np.uint8)
                c = cs.inst("oro_cdf", i, i + k)
                expected = P.reshape(len(THR), -1).sum(axis=1)
                e["ext"][j, k - 1] = encode(calibrate_tail(c, expected))
                e["exth"][j, k - 1] = encode(calibrate_tail(c, expected, weight=0.5))
        e["prob_raw"], e["prob"] = raw, prob
        np.savez_compressed(path.with_name(path.stem + "_ext.npz"), **e)
        print(f"{path.stem}: omkalibrerad utanför urvalet", flush=True)
    if final_model is not None and final_model.exists():
        with open(final_model, "rb") as fh:
            d = pickle.load(fh)
        d["recal"] = fit_tables(list(samples))
        with open(final_model, "wb") as fh:
            pickle.dump(d, fh)
        print(f"omkalibrering för alla fall sparad i {final_model}")


def evalprob(gen: Path, out: Path, leads=(3, 6, 9, 12)):
    """Brier skill score, tillförlitlighet och ROC-yta för sannolikheter mot momentan radar."""
    from sklearn.metrics import roc_auc_score
    res = {}
    acc = {}
    for path in sorted(p for p in gen.glob("*.npz") if not p.stem.endswith("_ext")):
        cs = load_case(path)
        e = np.load(path.with_name(path.stem + "_ext.npz"))
        prob = e["prob"]
        prob_raw = e["prob_raw"] if "prob_raw" in e.files else None
        for j, i in enumerate(cs.issues):
            for k in leads:
                if i + k >= cs.n:
                    continue
                y = cs.obs[i + k]
                c = cs.inst("oro_cdf", i, i + k)
                ok = np.isfinite(y) & np.isfinite(c)
                cz = np.nan_to_num(c)
                for n, t in enumerate(THR):
                    if t not in USE_THR:
                        continue
                    o = (y[ok] >= t).astype(np.float32)
                    sysp = {
                        "tränad": prob[n, j, k - 1][ok] / 250.0,
                        **({"tränad, rå": prob_raw[n, j, k - 1][ok] / 250.0} if prob_raw is not None else {}),
                        "grannskap 30 km": uniform_filter((cz >= t).astype(np.float32), 15)[ok],
                        "grannskap 14 km": uniform_filter((cz >= t).astype(np.float32), 7)[ok],
                        "kedjan ja/nej": (cz >= t).astype(np.float32)[ok],
                    }
                    for s, p in sysp.items():
                        a = acc.setdefault((s, k * 5, t), {"bs": 0.0, "n": 0, "o": 0.0, "p": 0.0, "rel": np.zeros((10, 3)), "samp": []})
                        a["bs"] += float(np.sum((p - o) ** 2))
                        a["n"] += o.size
                        a["o"] += float(o.sum())
                        a["p"] += float(p.sum())
                        b = np.minimum((p * 10).astype(int), 9)
                        np.add.at(a["rel"], b, np.stack([np.ones_like(p), p, o], axis=1))
                        if o.sum() > 0:
                            pick = RNG.random(o.size) < min(1.0, 3000 / o.size)
                            a["samp"].append((p[pick], o[pick]))
        print(f"{cs.name}: klar", flush=True)
    for (s, lead, t), a in acc.items():
        base = a["o"] / a["n"]
        bs_clim = base * (1 - base)
        p = np.concatenate([x for x, _ in a["samp"]]) if a["samp"] else np.array([])
        o = np.concatenate([y for _, y in a["samp"]]) if a["samp"] else np.array([])
        auc = float(roc_auc_score(o, p)) if o.size and 0 < o.sum() < o.size else None
        rel = a["rel"]
        rows = [[float(r[1] / r[0]), float(r[2] / r[0]), int(r[0])] for r in rel if r[0] > 0]
        res.setdefault(s, {}).setdefault(str(lead), {})[str(t)] = {
            "BSS": 1 - (a["bs"] / a["n"]) / bs_clim if bs_clim > 0 else None,
            "AUC": auc, "bas": base, "kvot": a["p"] / a["o"] if a["o"] else None, "tillforlitlighet": rows,
        }
    out.write_text(json.dumps(res, indent=1))
    print(f"skrev {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["features", "train", "predict", "recal", "evalprob"])
    ap.add_argument("--final-model", type=Path, default=Path("models/extremes.pkl"))
    ap.add_argument("gen", type=Path)
    ap.add_argument("--work", type=Path, default=None, help="katalog för särdrag och modeller (standard: <gen>/ext)")
    ap.add_argument("--out", type=Path, default=Path("prob.json"))
    ap.add_argument("--cases", nargs="*", default=None, help="bara de här fallen (särdrag)")
    a = ap.parse_args()
    work = a.work or a.gen / "ext"
    if a.step == "features":
        build_features(a.gen, work / "features", a.cases)
    elif a.step == "train":
        train(work / "features", work / "models")
    elif a.step == "predict":
        predict(a.gen, work / "models")
    elif a.step == "recal":
        recal(a.gen, work / "models", a.final_model)
    else:
        evalprob(a.gen, a.out)
