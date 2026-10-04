"""Version A: the XAI-only baseline (docs/XAI_PLAN.md section 5; plan section 7).

What a team would get by training a good predictor on routine data and explaining it with SHAP and LIME, WITHOUT causal
adjustment, intervals, abstention or the rules-first order. It exists to be compared with the causal engine (version B)
and with SHAP on the causal estimate (version C) in the Analysis tab.

    NEVER CONNECTED TO web/ OR THE API. A test scans web/, diacausal/api/ and diacausal/orchestrator/ for any use of it.
    A doctor never sees a number from this file. SHAP and LIME explain a MODEL, not a cause.

The model: scikit-learn's HistGradientBoostingRegressor with the engine's own settings (params.yaml engine.outcome_model),
trained on FACTUAL data only: the 12 patient features plus one column per drug (one-hot) -> the observed 6-month HbA1c
change. This is exactly the benchmark's S-learner (diacausal.causal_inference.estimators.s_learner), so version A and the
engine differ only in HOW THE EFFECT IS ESTIMATED; a test checks that the predictions are identical.

A patient's prediction for a drug is the model with the drug columns switched to that drug. The options are those the
SAME safety rules (data/rules.csv) leave for that patient (as in version B); the lowest prediction is version A's pick.
Version A does NOT apply the overlap abstention: it answers every patient, thin data or not.

TreeSHAP: shap.TreeExplainer in its default (tree_path_dependent) mode. Interventional TreeSHAP was tried first (plan 5.2)
and rejected: with shap 0.52.0 and scikit-learn 1.9.1 it is off by a constant of about 0.002 HbA1c points on this model
class, while the path-dependent mode is exact (about 1e-14). The explanation of a comparison "A versus B" is the SHAP of
g(x) = f(x, A) - f(x, B): the difference of the two SHAP vectors, whose expected values cancel, so the contributions add
up to the estimated effect. The drug columns are relative to the training cohort's PRESCRIBING MIX, not to a clinical
alternative. LIME explains the same g(x), so both explain the same quantity.

Run:  python -m diacausal.xai.baseline [--quick]      (needs requirements-xai.txt: shap, lime)
Writes results/xai/: baseline_metrics.csv, shap_A.csv, lime_stability.csv, run_info.json and figures.

Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pandas as pd

from diacausal.causal_inference.cohort import features, generate_cohort, observed_view, treatment_index
from diacausal.causal_inference.dag import load_dag
from diacausal.causal_inference.estimators import outcome_model
from diacausal.causal_inference.metrics import pehe, policy_regret
from diacausal.config import ARMS, CONTRASTS, RESULTS_DIR, load_params
from diacausal.guards.rules_loader import FIELDS, RuleTable, load_rules
from diacausal.xai import truth

COMPARISONS = truth.COMPARISONS
OUT_DIR = RESULTS_DIR / "xai"
DRUG_COLUMNS = [f"drug_{a}" for a in ARMS]
TOP_K = 3  # the "top 3" of the agreement and stability metrics
LIME_SAMPLES = 5000
LIME_SEEDS = 10
SHAP_BACKGROUND_ROWS = 500  # rows of the beeswarm
METRIC_COLUMNS = ["version", "metric", "comparison", "mean", "ci_low", "ci_high", "n_reps"]

# The three demo presets (demo/streamlit_app.py; a test keeps the two in step).
PRESETS = {
    "typical": dict(age=52, sex="male", duration_years=5.0, hba1c=8.4, egfr=88.0, bmi=27.0),
    "egfr40_pancreatitis": dict(age=60, sex="female", duration_years=8.0, hba1c=8.2, egfr=40.0, bmi=25.5, pancreatitis_history=True),
    "older_hypo": dict(age=80, sex="male", duration_years=15.0, hba1c=8.0, egfr=38.0, bmi=24.0, hypo_history=True, ascvd=True),
}


# ── the data and the model ───────────────────────────────────────────────────────────────────────────────────────

def feature_names(params) -> list[str]:
    return list(load_dag(params).adjustment_set)


def training_frame(params, cohort: pd.DataFrame) -> pd.DataFrame:
    """The factual training table: the 12 patient features, the drug as three 0/1 columns, and the observed outcome `y`.
    Built from `observed_view(cohort)`: no true outcomes, no true propensities, no scores."""
    observed = observed_view(cohort)
    frame = observed[feature_names(params)].astype(float).copy()
    for arm in ARMS:
        frame[f"drug_{arm}"] = (observed["treatment"] == arm).astype(float)
    frame["y"] = observed["y"].to_numpy(float)
    return frame


def with_drug(X: np.ndarray, j: int) -> np.ndarray:
    """The 12 features with the drug columns switched to option number j (rows x 15)."""
    drug = np.zeros((len(X), len(ARMS)))
    drug[:, j] = 1.0
    return np.column_stack([X, drug])


class VersionA:
    """The model of version A: fitted once, then asked 'what if this patient got drug a?' for every drug."""

    def __init__(self, params, seed: int):
        self.params, self.seed = params, int(seed)
        self.names = feature_names(params)
        self.model = outcome_model(params.group("engine.outcome_model"), self.seed)

    def fit(self, cohort: pd.DataFrame) -> "VersionA":
        frame = training_frame(self.params, cohort)
        self.train_X = frame[self.names].to_numpy(float)
        self.train_inputs = frame[self.names + DRUG_COLUMNS].to_numpy(float)
        self.model.fit(self.train_inputs, frame["y"].to_numpy(float))
        return self

    def predict_options(self, X: np.ndarray) -> np.ndarray:
        """(n, 3): the predicted HbA1c change under each drug."""
        return np.column_stack([self.model.predict(with_drug(X, j)) for j in range(len(ARMS))])

    def predict_effect(self, X: np.ndarray, a: str, b: str) -> np.ndarray:
        return self.model.predict(with_drug(X, ARMS.index(a))) - self.model.predict(with_drug(X, ARMS.index(b)))


def rule_allowed(rules: RuleTable, df: pd.DataFrame) -> np.ndarray:
    """(n, 3): the option is not excluded by data/rules.csv. The same rules as the engine, and nothing else: no overlap
    abstention (version A answers every patient)."""
    return np.array([[not v.excluded for v in rules.apply(row).values()] for row in df[list(FIELDS)].to_dict("records")])


def pick(levels: np.ndarray, allowed: np.ndarray) -> np.ndarray:
    """Index of the lowest prediction among the allowed options (-1 where none is allowed)."""
    chosen = np.where(allowed, levels, np.inf).argmin(axis=1)
    return np.where(allowed.any(axis=1), chosen, -1)


# ── explanations ─────────────────────────────────────────────────────────────────────────────────────────────────

def tree_explainer(model):
    import shap

    return shap.TreeExplainer(model)  # default mode: exact on this model class (see the module docstring)


def shap_by_option(explainer, X: np.ndarray) -> np.ndarray:
    """(3, n, 15): TreeSHAP of the model with the drug switched to each option."""
    return np.stack([explainer.shap_values(with_drug(X, j)) for j in range(len(ARMS))])


def effect_shap(by_option: np.ndarray, a: str, b: str) -> np.ndarray:
    """(n, 15): the SHAP of g = f(x,a) - f(x,b). The expected values cancel, so each row sums to the estimated effect."""
    return by_option[ARMS.index(a)] - by_option[ARMS.index(b)]


def lime_weights(model_fn, X_train: np.ndarray, names: list[str], x: np.ndarray, seed: int, samples: int = LIME_SAMPLES) -> np.ndarray:
    """LIME (tabular, regression, no discretisation, binary features declared categorical, seeded) of model_fn at x:
    the 12 weights in feature order."""
    from lime.lime_tabular import LimeTabularExplainer

    binary = [j for j in range(X_train.shape[1]) if set(np.unique(X_train[:, j])) <= {0.0, 1.0}]
    explainer = LimeTabularExplainer(X_train, feature_names=names, categorical_features=binary, mode="regression",
                                     discretize_continuous=False, random_state=int(seed))
    explanation = explainer.explain_instance(x, model_fn, num_features=len(names), num_samples=samples)
    weights = np.zeros(len(names))
    for j, w in explanation.local_exp[1]:
        weights[j] = w
    return weights


def effect_function(model: VersionA, a: str, b: str):
    return lambda Z: model.predict_effect(np.asarray(Z, float), a, b)


# ── the metric helpers (pure NumPy / SciPy, tested by hand in tests/xai/test_metrics.py) ───────────────────────

def top_k(values: Sequence[float], k: int = TOP_K) -> set[int]:
    """Indices of the k largest values; ties are broken by position, so the result never depends on hash order."""
    order = sorted(range(len(values)), key=lambda i: (-values[i], i))
    return set(order[:k])


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if (a | b) else 1.0


def spearman(x: Sequence[float], y: Sequence[float]) -> float:
    from scipy.stats import spearmanr

    x, y = np.asarray(x, float), np.asarray(y, float)
    if np.ptp(x) == 0 or np.ptp(y) == 0:
        return float("nan")  # a constant ranking has no correlation
    return float(spearmanr(x, y).statistic)


def precision_at_k(importance: dict[str, float], true_set: Sequence[str]) -> float:
    """Of the k most important features (k = how many true modifiers there are), the share that are true modifiers."""
    k = len(true_set)
    if k == 0:
        return float("nan")
    names = list(importance)
    chosen = top_k([importance[n] for n in names], k)
    return len({names[i] for i in chosen} & set(true_set)) / k


def mean_ci(values: Sequence[float]) -> tuple[float, float, float, int]:
    """Mean over replicates and its 95% t-interval (NaN replicates are left out; one replicate gives no interval)."""
    from scipy.stats import t

    v = np.asarray([x for x in values if not np.isnan(x)], float)
    if len(v) == 0:
        return float("nan"), float("nan"), float("nan"), 0
    if len(v) == 1:
        return float(v[0]), float("nan"), float("nan"), 1
    half = t.ppf(0.975, len(v) - 1) * v.std(ddof=1) / np.sqrt(len(v))
    return float(v.mean()), float(v.mean() - half), float(v.mean() + half), len(v)


# ── one replicate: fit on a cohort, score on a fresh test cohort with the truth ────────────────────────────────────

def evaluate_replicate(params, rules: RuleTable, seed: int, n: int, n_test: int, n_agree: int, with_lime: bool = True) -> dict:
    """Same cohorts as the benchmark's replicate `seed` (train: generate_cohort(seed); test: seed + 100000)."""
    cohort = generate_cohort(params, n=n, seed=seed)
    test = generate_cohort(params, n=n_test, seed=seed + 100_000)
    model = VersionA(params, seed).fit(cohort)
    Xt = features(params, test)
    names = model.names
    levels = model.predict_options(Xt)
    mu = test[[f"mu_true_{a}" for a in ARMS]].to_numpy(float)
    e_true = test[[f"e_true_{a}" for a in ARMS]].to_numpy(float)
    allowed = rule_allowed(rules, test)
    thin = e_true.min(axis=1) < params.get("engine.overlap_min_propensity")
    m: dict[tuple[str, str], float] = {}

    # prediction error: of the factual outcome (the drug each test patient received) and of all three
    received = treatment_index(test)
    rows = np.arange(len(test))
    m["pred_rmse", "all"] = float(np.sqrt(np.mean((levels[rows, received] - mu[rows, received]) ** 2)))
    m["pred_rmse_all_options", "all"] = float(np.sqrt(np.mean((levels - mu) ** 2)))

    # effect bias and PEHE per comparison (all test patients, as in the benchmark), also on thin and non-thin patients
    true_effects = truth.true_effect(params, mu)
    for (a, b), c in zip(CONTRASTS, COMPARISONS):
        est = levels[:, ARMS.index(a)] - levels[:, ARMS.index(b)]
        m["effect_bias", c] = float(np.mean(est - true_effects[c]))
        m["pehe", c] = pehe(est, true_effects[c])
        m["pehe_thin", c] = pehe(est[thin], true_effects[c][thin]) if thin.any() else float("nan")
        m["pehe_not_thin", c] = pehe(est[~thin], true_effects[c][~thin])

    # picks, regret and who is answered
    regret, decided = policy_regret(levels, mu, allowed)
    m["regret", "all"] = regret
    choice = pick(levels, allowed)
    best = pick(mu, allowed)
    has_choice = allowed.sum(axis=1) >= 2
    m["best_pick_rate", "all"] = float(np.mean(choice[has_choice] == best[has_choice])) if has_choice.any() else float("nan")
    m["abstention_rate", "all"] = 0.0  # version A never abstains
    m["excluded_by_rules_rate", "all"] = float(1.0 - allowed.mean())
    m["thin_share", "all"] = float(thin.mean())
    m["answered_when_thin", "all"] = float(allowed.any(axis=1)[thin].mean()) if thin.any() else float("nan")

    # TreeSHAP of every comparison on every test patient: global importance and the modifier check
    explainer = tree_explainer(model.model)
    by_option = shap_by_option(explainer, Xt)
    sd = {f: float(Xt[:, j].std()) for j, f in enumerate(names)}
    importance_truth = truth.true_importance(params, sd)
    modifiers = truth.modifiers(params)
    effect_phi = {}
    for (a, b), c in zip(CONTRASTS, COMPARISONS):
        phi = effect_shap(by_option, a, b)
        effect_phi[c] = phi
        mean_abs = {f: float(np.abs(phi[:, j]).mean()) for j, f in enumerate(names)}
        m["modifier_precision_at_k", c] = precision_at_k(mean_abs, modifiers[c])
        m["modifier_spearman", c] = spearman([mean_abs[f] for f in names], [importance_truth[c][f] for f in names])
        m["drug_columns_share", c] = float(np.abs(phi[:, len(names):]).sum() / np.abs(phi).sum())

    # SHAP-LIME agreement on a sample of test patients, for each comparison
    if with_lime and n_agree > 0:
        rng = np.random.default_rng(seed + 7)
        sample = rng.choice(len(test), size=min(n_agree, len(test)), replace=False)
        for (a, b), c in zip(CONTRASTS, COMPARISONS):
            fn = effect_function(model, a, b)
            rho, jac = [], []
            for i in sample:
                w = lime_weights(fn, model.train_X, names, Xt[i], seed=seed * 10_000 + int(i))
                s = np.abs(effect_phi[c][i, :len(names)])
                rho.append(spearman(s, np.abs(w)))
                jac.append(jaccard(top_k(list(s)), top_k(list(np.abs(w)))))
            m["shap_lime_spearman", c] = float(np.nanmean(rho))
            m["shap_lime_top3_jaccard", c] = float(np.mean(jac))
    return m


# ── the three presets: waterfalls, LIME stability ───────────────────────────────────────────────────────────────────

def preset_row(params, name: str) -> dict[str, float]:
    """A preset as the 12 model features (plus the rule fields), every missing yes/no detail = 0."""
    raw = PRESETS[name]
    row = {f: 0.0 for f in feature_names(params)} | {f: 0.0 for f in FIELDS}
    for key, value in raw.items():
        if key == "sex":
            row["female"] = 1.0 if value == "female" else 0.0
        else:
            row[key] = float(value)
    return row


def presets_report(params, rules: RuleTable, out: Path, seeds: int = LIME_SEEDS, samples: int = LIME_SAMPLES, draw_figures: bool = True) -> dict:
    """Fit version A on the engine's own reference cohort and explain the three presets: TreeSHAP waterfalls and LIME with
    `seeds` seeds each. Options excluded by the safety rules are not predicted or explained."""
    seed = int(params.get("engine.reference_cohort_seed"))
    cohort = generate_cohort(params, n=int(params.get("generator.n_patients")), seed=seed)
    model = VersionA(params, int(params.get("engine.random_seed"))).fit(cohort)
    names = model.names
    explainer = tree_explainer(model.model)
    shap_rows, lime_rows, picks = [], [], {}
    for preset in PRESETS:
        row = preset_row(params, preset)
        x = np.array([[row[f] for f in names]])
        verdicts = rules.apply({f: row[f] for f in FIELDS})
        options = [a for a in ARMS if not verdicts[a].excluded]
        levels = model.predict_options(x)[0]
        picks[preset] = {"allowed": options, "pick": min(options, key=lambda a: levels[ARMS.index(a)]) if options else None,
                         "predictions": {a: float(levels[ARMS.index(a)]) for a in options}}
        by_option = shap_by_option(explainer, x)
        for a, b in [(a, b) for a, b in CONTRASTS if a in options and b in options]:
            c = f"{a}-{b}"
            phi = effect_shap(by_option, a, b)[0]
            effect = float(model.predict_effect(x, a, b)[0])
            for j, f in enumerate(names):
                shap_rows.append(dict(scope="preset", preset=preset, comparison=c, feature=f, patient_value=row[f], phi=float(phi[j]), mean_abs_phi=""))
            shap_rows.append(dict(scope="preset", preset=preset, comparison=c, feature="drug (prescribing mix)", patient_value="",
                                  phi=float(phi[len(names):].sum()), mean_abs_phi=""))
            assert abs(phi.sum() - effect) < 1e-6, "the SHAP values of a comparison must add up to the estimated effect"
            if draw_figures:
                waterfall_figure(names, row, phi, effect, a, b, preset, out / f"waterfall_A_{preset}_{c}.png")
            fn = effect_function(model, a, b)
            weights = np.array([lime_weights(fn, model.train_X, names, x[0], seed=s, samples=samples) for s in range(seeds)])
            tops = [top_k(list(np.abs(w))) for w in weights]
            pairs = [jaccard(tops[i], tops[j]) for i in range(seeds) for j in range(i + 1, seeds)]
            lead = int(np.abs(weights).mean(axis=0).argmax())
            cv = float(weights[:, lead].std(ddof=1) / abs(weights[:, lead].mean())) if seeds > 1 and weights[:, lead].mean() else float("nan")
            lime_rows.append(dict(preset=preset, comparison=c, option_a=a, option_b=b, n_seeds=seeds, lime_top3_jaccard=float(np.mean(pairs)),
                                  lime_top_weight_cv=cv, top_feature=names[lead], mean_abs_weight_top=float(np.abs(weights[:, lead]).mean())))
    return {"shap_rows": shap_rows, "lime_rows": lime_rows, "picks": picks, "model": model, "explainer": explainer}


def global_shap(params, model: VersionA, explainer, out: Path, n_rows: int = SHAP_BACKGROUND_ROWS, draw_figures: bool = True) -> list[dict]:
    """Global importance on a fresh test cohort: mean |SHAP| of the model per input, and of each comparison per feature."""
    seed = int(params.get("engine.reference_cohort_seed")) + 100_000
    test = generate_cohort(params, n=2000, seed=seed)
    names = model.names
    Xt = features(params, test)
    by_option = shap_by_option(explainer, Xt)
    rows = [dict(scope="global", preset="", comparison=c, feature=f, patient_value="", phi="",
                 mean_abs_phi=float(np.abs(effect_shap(by_option, a, b)[:, j]).mean()))
            for (a, b), c in zip(CONTRASTS, COMPARISONS) for j, f in enumerate(names)]
    if draw_figures:
        received = treatment_index(test)[:n_rows]
        inputs = np.column_stack([Xt[:n_rows], np.eye(len(ARMS))[received]])
        beeswarm_figure(explainer, inputs, names + DRUG_COLUMNS, out / "beeswarm_A.png")
    return rows


# ── figures (matplotlib / shap are imported here so that importing this module needs neither) ───────────────────

def _plt():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def beeswarm_figure(explainer, inputs: np.ndarray, columns: list[str], path: Path) -> None:
    import shap

    plt = _plt()
    values = explainer.shap_values(inputs)
    shap.summary_plot(values, inputs, feature_names=columns, show=False, max_display=len(columns))
    plt.title("Version A (XAI only): TreeSHAP of the HbA1c-change model\nsynthetic benchmark; a model explanation, not a causal one", fontsize=10)
    plt.tight_layout()
    plt.savefig(path, dpi=130)
    plt.close("all")


def waterfall_figure(names: list[str], row: dict, phi: np.ndarray, effect: float, a: str, b: str, preset: str, path: Path) -> None:
    import shap

    plt = _plt()
    labels = [f"{f} = {row[f]:g}" for f in names] + ["drug column (prescribing mix)"]
    values = np.append(phi[:len(names)], phi[len(names):].sum())
    explanation = shap.Explanation(values=values, base_values=0.0, data=None, feature_names=labels)
    shap.plots.waterfall(explanation, max_display=14, show=False)
    plt.title(f"Version A: {a} minus {b} for preset '{preset}': {effect:+.2f} HbA1c points (a model's estimate, no interval)", fontsize=9)
    plt.tight_layout()
    plt.savefig(path, dpi=130, bbox_inches="tight")
    plt.close("all")


def stability_figure(lime_rows: list[dict], path: Path) -> None:
    plt = _plt()
    labels = [f"{r['preset']}\n{r['comparison']}" for r in lime_rows]
    fig, ax = plt.subplots(figsize=(max(6, 1.1 * len(labels)), 4))
    ax.bar(range(len(labels)), [r["lime_top3_jaccard"] for r in lime_rows], color="#52514E")
    ax.axhline(1.0, color="#0E5049", linestyle="--", linewidth=1)
    ax.set_xticks(range(len(labels)), labels, fontsize=7)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("top-3 overlap between LIME runs\n(1 = every seed agrees)")
    ax.set_title("Version A: LIME stability, 10 seeds per preset (synthetic benchmark)", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close("all")


# ── the whole run ───────────────────────────────────────────────────────────────────────────────────────────────────

def write_csv(rows: list[dict], columns: list[str], path: Path) -> None:
    with Path(path).open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow({k: (f"{v:.6g}" if isinstance(v, float) else v) for k, v in r.items()})


def aggregate(replicates: list[dict], preset_stability: list[dict]) -> list[dict]:
    keys = sorted({k for r in replicates for k in r})
    rows = []
    for metric, comparison in keys:
        mean, lo, hi, n = mean_ci([r.get((metric, comparison), float("nan")) for r in replicates])
        rows.append(dict(version="A", metric=metric, comparison=comparison, mean=mean, ci_low=lo, ci_high=hi, n_reps=n))
    for comparison in COMPARISONS:
        mine = [r for r in preset_stability if r["comparison"] == comparison]
        if mine:
            for metric, col in (("lime_top3_jaccard", "lime_top3_jaccard"), ("lime_top_weight_cv", "lime_top_weight_cv")):
                values = [r[col] for r in mine]
                rows.append(dict(version="A", metric=metric, comparison=comparison, mean=float(np.nanmean(values)), ci_low="", ci_high="", n_reps=1))
    return rows


def run(reps: int, n: int, n_test: int, n_agree: int, out: Path = OUT_DIR, seeds: int = LIME_SEEDS, samples: int = LIME_SAMPLES,
        draw_figures: bool = True, with_lime: bool = True, seed: int | None = None) -> dict:
    started = time.time()
    params, rules = load_params(), load_rules()
    seed = int(params.get("engine.random_seed") if seed is None else seed)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    replicates = []
    for r in range(reps):
        replicates.append(evaluate_replicate(params, rules, seed + r, n, n_test, n_agree, with_lime=with_lime))
        print(f"  replicate {r + 1}/{reps} done ({time.time() - started:.0f} s)", flush=True)
    report = presets_report(params, rules, out, seeds=seeds, samples=samples, draw_figures=draw_figures)
    glob = global_shap(params, report["model"], report["explainer"], out, draw_figures=draw_figures)
    metrics = aggregate(replicates, report["lime_rows"])
    write_csv(metrics, METRIC_COLUMNS, out / "baseline_metrics.csv")
    write_csv(report["shap_rows"] + glob, ["scope", "preset", "comparison", "feature", "patient_value", "phi", "mean_abs_phi"], out / "shap_A.csv")
    write_csv(report["lime_rows"], ["preset", "comparison", "option_a", "option_b", "n_seeds", "lime_top3_jaccard", "lime_top_weight_cv",
                                    "top_feature", "mean_abs_weight_top"], out / "lime_stability.csv")
    if draw_figures:
        stability_figure(report["lime_rows"], out / "lime_stability_A.png")
    import lime
    import shap
    (out / "run_info.json").write_text(json.dumps({
        "version": "A (XAI-only baseline)", "reps": reps, "n": n, "n_test": n_test, "shap_lime_patients_per_replicate": n_agree,
        "lime_seeds_per_preset": seeds, "lime_samples": samples, "seed": seed, "params_sha": params.fingerprint, "rules_sha": rules.version,
        "shap": shap.__version__, "lime": getattr(lime, "__version__", "0.2.0.1"), "shap_mode": "tree_path_dependent",
        "presets": report["picks"], "seconds": round(time.time() - started, 1),
        "note": "synthetic benchmark; version A is a baseline, never shown to a doctor"}, indent=1), encoding="utf-8")
    return {"metrics": metrics, "replicates": replicates, "report": report}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quick", action="store_true", help="3 replicates x 1,500 patients, 20 SHAP-LIME patients, 2,000 LIME samples")
    ap.add_argument("--reps", type=int)
    ap.add_argument("--n", type=int)
    ap.add_argument("--n-test", type=int)
    ap.add_argument("--agree", type=int, help="patients per replicate for the SHAP-LIME agreement")
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    a = ap.parse_args(argv)
    reps, n, n_test, agree, samples = (3, 1500, 1000, 20, 2000) if a.quick else (20, 5000, 2000, 100, LIME_SAMPLES)
    run(a.reps or reps, a.n or n, a.n_test or n_test, a.agree if a.agree is not None else agree, a.out, samples=samples)
    print(f"Saved results to {a.out}")


if __name__ == "__main__":
    main()
