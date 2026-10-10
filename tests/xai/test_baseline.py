"""Version A's guarantees (docs/XAI_PLAN.md section 5, plan 7.5): factual data only, the same rule exclusions as the
engine, exact TreeSHAP, seeded LIME, and never connected to the website or the API."""

import ast
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("shap", reason="needs requirements-xai.txt")
pytest.importorskip("lime", reason="needs requirements-xai.txt")

from diacausal.causal_inference.cohort import TRUTH_PREFIXES, features, observed_view, treatment_index  # noqa: E402
from diacausal.causal_inference.estimators import s_learner  # noqa: E402
from diacausal.causal_inference.metrics import pehe  # noqa: E402
from diacausal.config import ARMS, CONTRASTS  # noqa: E402
from diacausal.xai import baseline as b  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def model(params, cohorts):
    return b.VersionA(params, 7).fit(cohorts[0])


# ── factual data only ────────────────────────────────────────────────────────────────────────────────────────────
def test_the_training_table_has_only_what_a_real_dataset_would_have(params, cohorts):
    frame = b.training_frame(params, cohorts[0])
    assert list(frame.columns) == b.feature_names(params) + b.DRUG_COLUMNS + ["y"]
    assert len(b.feature_names(params)) == 12 and frame.shape == (1500, 16)
    assert not [c for c in frame.columns if c.startswith(TRUTH_PREFIXES) or "true" in c or "propensity" in c or "phi" in c]
    assert (frame[b.DRUG_COLUMNS].sum(axis=1) == 1).all()  # exactly one drug per patient: the one received


def test_the_hidden_truth_cannot_change_the_fitted_model(params, cohorts):
    """Scramble every truth column of the cohort: the model must be identical (it never sees them)."""
    train = cohorts[0].copy()
    for c in train.columns:
        if c.startswith(TRUTH_PREFIXES):
            train[c] = np.random.default_rng(0).permutation(train[c].to_numpy())
    a = b.VersionA(params, 7).fit(cohorts[0])
    z = b.VersionA(params, 7).fit(train)
    Xt = features(params, cohorts[1])
    assert np.array_equal(a.predict_options(Xt), z.predict_options(Xt))


def test_the_model_sees_fifteen_inputs_and_no_other(model):
    assert model.model.n_features_in_ == 15 and model.train_inputs.shape[1] == 15


def test_version_a_is_the_benchmarks_s_learner(params, cohorts, model):
    """Same class, same settings, same seed, same data: the predictions are identical, so the PEHE equals the benchmark's."""
    train, test = cohorts
    X, T, Y = features(params, train), treatment_index(train), observed_view(train)["y"].to_numpy(float)
    Xt = features(params, test)
    theirs = s_learner(X, T, Y, Xt, params.group("engine.outcome_model"), 7)
    assert np.allclose(model.predict_options(Xt), theirs, atol=1e-12)
    mu = test[[f"mu_true_{a}" for a in ARMS]].to_numpy(float)
    ours = b.evaluate_replicate(params, __import__("diacausal.guards.rules_loader", fromlist=["x"]).load_rules(), 7, 1500, 800, 0, with_lime=False)
    for (a, c), name in zip(CONTRASTS, b.COMPARISONS):
        i, j = ARMS.index(a), ARMS.index(c)
        assert ours["pehe", name] == pytest.approx(pehe(theirs[:, i] - theirs[:, j], mu[:, i] - mu[:, j]), abs=1e-12)


# ── the same rule exclusions as the engine ─────────────────────────────────────────────────────────────────────────
def test_the_exclusions_are_the_engines_rules_exactly(params, rules, cohorts):
    test = cohorts[1]
    allowed = b.rule_allowed(rules, test)
    for i, row in enumerate(test[list(b.FIELDS)].to_dict("records")[:300]):
        verdicts = rules.apply(row)
        assert [not verdicts[a].excluded for a in ARMS] == list(allowed[i])


def test_an_excluded_option_is_never_picked_and_a_patient_with_nothing_left_gets_no_pick(params, rules, cohorts, model):
    test = cohorts[1]
    Xt = features(params, test)
    allowed = b.rule_allowed(rules, test)
    choice = b.pick(model.predict_options(Xt), allowed)
    for i, c in enumerate(choice):
        assert c == -1 if not allowed[i].any() else allowed[i, c]
    # eGFR 25: R01, R10 and R11 leave no option at all (the merged rules)
    row = {f: 0.0 for f in b.FIELDS} | {"egfr": 25.0, "age": 60.0}
    assert not any(rules.apply(row)[a].excluded is False for a in ARMS)


def test_the_options_are_predicted_by_switching_only_the_drug_columns(model):
    x = np.arange(24, dtype=float).reshape(2, 12)
    for j in range(3):
        z = b.with_drug(x, j)
        assert np.array_equal(z[:, :12], x) and np.array_equal(z[:, 12:], np.tile(np.eye(3)[j], (2, 1)))
    manual = np.column_stack([model.model.predict(b.with_drug(x, j)) for j in range(3)])
    assert np.array_equal(model.predict_options(x), manual)


def test_the_effect_of_a_comparison_is_the_difference_of_two_predictions(model, params, cohorts):
    Xt = features(params, cohorts[1])[:50]
    levels = model.predict_options(Xt)
    assert np.allclose(model.predict_effect(Xt, "SGLT2i", "DPP4i"), levels[:, 0] - levels[:, 1])
    assert np.allclose(model.predict_effect(Xt, "SU", "DPP4i"), levels[:, 2] - levels[:, 1])


# ── TreeSHAP ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_shap_additivity_of_the_tree_model(model, params, cohorts):
    """expected value + the 15 SHAP values = the model's prediction, on rows the model has never seen."""
    explainer = b.tree_explainer(model.model)
    inputs = b.with_drug(features(params, cohorts[1])[:200], 1)
    values = explainer.shap_values(inputs)
    assert values.shape == (200, 15)
    assert np.abs(float(np.ravel(explainer.expected_value)[0]) + values.sum(axis=1) - model.model.predict(inputs)).max() < 1e-9


def test_the_shap_of_a_comparison_adds_up_to_the_estimated_effect(model, params, cohorts):
    Xt = features(params, cohorts[1])[:200]
    by_option = b.shap_by_option(b.tree_explainer(model.model), Xt)
    assert by_option.shape == (3, 200, 15)
    for a, c in CONTRASTS:
        assert np.abs(b.effect_shap(by_option, a, c).sum(axis=1) - model.predict_effect(Xt, a, c)).max() < 1e-9


def test_treatment_shap_is_relative_to_the_prescribing_mix_not_to_a_clinical_alternative(model, params, cohorts):
    """Averaged over the cohort that trained the model, each input's SHAP value is about zero: the drug columns say
    'more or less than the usual mix', which is why they are reported apart from the 12 patient features."""
    explainer = b.tree_explainer(model.model)
    mean = explainer.shap_values(model.train_inputs).mean(axis=0)
    assert np.abs(mean).max() < 0.02
    assert [n for n, v in zip(model.names + b.DRUG_COLUMNS, np.abs(model.train_inputs[:, 12:]).sum(axis=0)) if v == 0] == []


# ── LIME ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_lime_is_seeded_so_the_same_seed_gives_the_same_weights(model, params, cohorts):
    x = features(params, cohorts[1])[3]
    fn = b.effect_function(model, "SGLT2i", "DPP4i")
    first = b.lime_weights(fn, model.train_X, model.names, x, seed=5, samples=800)
    again = b.lime_weights(fn, model.train_X, model.names, x, seed=5, samples=800)
    other = b.lime_weights(fn, model.train_X, model.names, x, seed=6, samples=800)
    assert first.shape == (12,) and np.array_equal(first, again) and not np.array_equal(first, other)


def test_lime_and_shap_explain_the_same_function(model, params, cohorts):
    """LIME's local linear model approximates g(x) = f(x,a) - f(x,b) near x: at the instance it predicts about g(x)."""
    x = features(params, cohorts[1])[3]
    fn = b.effect_function(model, "SU", "DPP4i")
    assert fn(x[None, :]).shape == (1,) and fn(x[None, :])[0] == pytest.approx(model.predict_effect(x[None, :], "SU", "DPP4i")[0])


# ── the three presets ────────────────────────────────────────────────────────────────────────────────────────────
def test_the_presets_are_the_demos_presets():
    tree = ast.parse((ROOT / "demo" / "streamlit_app.py").read_text(encoding="utf-8"))
    demo = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "PRESETS":
            demo = {k.value: {kw.arg: ast.literal_eval(kw.value) for kw in v.keywords} for k, v in zip(n.value.keys, n.value.values)}
    assert list(demo.values()) == list(b.PRESETS.values())  # same three patients, same values, same order


def test_a_preset_becomes_the_twelve_model_features(params):
    row = b.preset_row(params, "egfr40_pancreatitis")
    assert row["female"] == 1.0 and row["pancreatitis_history"] == 1.0 and row["egfr"] == 40.0 and row["hypo_history"] == 0.0
    assert set(b.feature_names(params)) <= set(row) and set(b.FIELDS) <= set(row)


def test_presets_report_explains_only_the_options_the_rules_leave(params, rules, tmp_path):
    report = b.presets_report(params, rules, tmp_path, seeds=3, samples=300, draw_figures=False)
    picks = report["picks"]
    assert picks["typical"]["allowed"] == ["SGLT2i", "DPP4i", "SU"]
    assert "SGLT2i" not in picks["egfr40_pancreatitis"]["allowed"] and "SGLT2i" not in picks["older_hypo"]["allowed"]  # R01: eGFR below 45
    assert all(p["pick"] in p["allowed"] for p in picks.values())
    compared = {(r["preset"], r["comparison"]) for r in report["lime_rows"]}
    assert compared == {("typical", c) for c in b.COMPARISONS} | {("egfr40_pancreatitis", "SU-DPP4i"), ("older_hypo", "SU-DPP4i")}
    assert all(r["n_seeds"] == 3 and 0 <= r["lime_top3_jaccard"] <= 1 for r in report["lime_rows"])


def test_the_shap_of_each_preset_comparison_sums_to_its_estimate(params, rules, tmp_path):
    report = b.presets_report(params, rules, tmp_path, seeds=2, samples=300, draw_figures=False)
    frame = pd.DataFrame(report["shap_rows"])
    model = report["model"]
    for (preset, c), g in frame.groupby(["preset", "comparison"]):
        a, z = c.split("-")
        row = b.preset_row(params, preset)
        x = np.array([[row[f] for f in model.names]])
        assert g["phi"].astype(float).sum() == pytest.approx(float(model.predict_effect(x, a, z)[0]), abs=1e-6)


# ── never connected to the website or the API ────────────────────────────────────────────────────────────────────
def test_version_a_is_not_used_by_the_website_the_api_or_the_pipeline():
    banned = ("xai.baseline", "xai/baseline", "diacausal.xai", "import shap", "import lime", "from shap", "from lime")
    folders = [ROOT / "web", ROOT / "diacausal" / "api", ROOT / "diacausal" / "orchestrator", ROOT / "diacausal" / "output",
               ROOT / "diacausal" / "llm", ROOT / "diacausal" / "rag", ROOT / "diacausal" / "causal_inference", ROOT / "backend", ROOT / "supabase"]
    scanned = 0
    for folder in folders:
        for path in folder.rglob("*"):
            if path.suffix in {".py", ".js", ".html", ".json", ".ts", ".tsx", ".toml", ".yaml"} and "node_modules" not in path.parts and ".venv" not in path.parts and path.is_file():
                scanned += 1
                # version C (diacausal/xai/cate_shap.py: exact SHAP of the causal estimate, P25) is the one part of diacausal.xai the
                # pipeline may use; any other reference to diacausal.xai (version A, the benchmarks) still fails
                text = path.read_text(encoding="utf-8", errors="ignore").replace("diacausal.xai.cate_shap_benchmark", "BANNED-diacausal.xai")
                text = text.replace("from diacausal.xai import cate_shap", "").replace("diacausal.xai.cate_shap", "")
                assert not [w for w in banned if w in text], f"{path.relative_to(ROOT)} refers to version A"
    assert scanned > 100, f"the scan looked at only {scanned} files"


def test_version_c_which_the_pipeline_uses_never_loads_version_a_or_shap():
    import subprocess
    import sys

    code = ("import sys, diacausal.xai.cate_shap, diacausal.orchestrator.layers; "
            "bad=[m for m in ('diacausal.xai.baseline', 'diacausal.xai.cate_shap_benchmark', 'shap', 'lime') if m in sys.modules]; assert not bad, bad")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stderr[-500:]


def test_importing_version_a_does_not_load_shap_lime_or_matplotlib():
    """So the registry import test and the engine's CI job work without the XAI extras."""
    code = "import sys, diacausal.xai.baseline; bad=[m for m in ('shap','lime','matplotlib') if m in sys.modules]; assert not bad, bad"
    assert subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True).returncode == 0


def test_the_pins_are_in_the_xai_file_and_not_in_the_engine_file():
    xai = (ROOT / "requirements-xai.txt").read_text()
    engine = (ROOT / "requirements-engine.txt").read_text()
    assert "shap==0.52.0" in xai and "lime==0.2.0.1" in xai and "-r requirements-engine.txt" in xai
    assert "shap" not in engine.lower() and "lime" not in engine.lower()
    import lime
    import shap

    assert shap.__version__ == "0.52.0" and getattr(lime, "__version__", "0.2.0.1") == "0.2.0.1"
