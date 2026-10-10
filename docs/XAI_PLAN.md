# XAI plan: SHAP on the causal estimate, and the XAI-only baseline (P11)

> Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

**Status: written 4 October 2026. Version A built in P17 (`diacausal/xai/baseline.py`); version C built in P25 (`diacausal/xai/cate_shap.py`, `cate_shap_benchmark.py`, `web/engine.js` `explainEffect`) exactly as sections 3 and 4 say, plus an "all other details together" row with its own interval (joint HC3 covariance of the remaining coefficients) so the card's rows add up.** This is the plan P17 (version A), P25 (version C), P26 (version D) and P27 (Analysis tab) follow. Section 7 of [docs/PLAN_2026-10.md](PLAN_2026-10.md) says *what* to build; this file says *exactly how*, with every number below checked against the code on `main` (`4478d4b`). **VERIFIED** means I ran it or read it this session; **UNVERIFIED** means it is a plan, not a result.

## 0. What the investigation found (read this first)

1. **The final stage has no interactions and no polynomial terms.** Its design is `[1, standardised covariate 1 … 12]`: 13 columns, one per feature plus an intercept. So "basis terms summed back to their original feature" is the identity; each coefficient belongs to exactly one feature. (VERIFIED: `estimators.py:217-219`; `model.json` has `dr.beta` of shape 13 x 6.)
2. **Each comparison's coefficients are exactly the difference of the two options' coefficients** (largest gap 8e-15, checked for the HbA1c model and for the weight and hypoglycaemia models). The intercept of a comparison is the cohort's average effect (AIPW estimate).
3. **`model.json` and `engine.js` already hold everything SHAP needs** (`mean`, `scale`, `beta`, `cov` for each of the six targets). **No new number has to be exported.** Only a few display labels and display rules do.
4. **The formula is exact on the real model.** For the eGFR-40 example patient, base value + sum of contributions equals the engine's estimate to 1e-17, for all three comparisons.
5. **The generator's true effect modifiers are only `hba1c`, `egfr` and `duration_years`.** Every other feature has a true effect-modification of exactly zero. The fitted slopes recover the truth: all 7 true-modifier intervals contain the true slope, and all 29 non-modifier intervals include zero.
6. **A naive "top 3 by size" rule would show false drivers.** For the eGFR-40 patient the second-largest contribution to SGLT2i vs DPP-4i is `pancreatitis_history` (-0.159), a feature the generator gives **no** effect modification, and its interval (-0.609 to +0.290) crosses zero. **The card must show only drivers whose 95% interval excludes zero** (section 3.5). The plan's P25 text says "top 3 drivers"; it should say "up to 3 clear drivers".
7. **`shap.LinearExplainer` disagrees with the formula unless given the full cohort as background**: by default SHAP silently subsamples the background to 100 rows and the base value shifts (differences up to 0.025 HbA1c points). The P25 cross-check must pass `shap.maskers.Independent(X, max_samples=len(X))`.
8. **SHAP and LIME install with the engine's exact pins** (numpy 2.5.3, scikit-learn 1.9.1, pandas 3.0.6, scipy 1.18.1; shap 0.52.0, lime 0.2.0.1, numba 0.68.0) in a scratch environment. TreeSHAP works on the engine's own `HistGradientBoostingRegressor` (additivity error 2e-15), so version A can use the same model class as the benchmark's S-learner.
9. **The benchmark already has version A's model:** `estimators.s_learner` is a gradient-boosted model trained on factual data only, already scored for PEHE and regret (`benchmark.py:130-146`). Version A adds the explanations and the metrics that do not exist yet.

## 1. How the DR-learner's final stage is fitted (and how `model.json` and `engine.js` reproduce it)

### 1.1 The fit, step by step

| Step | What happens | Where |
|---|---|---|
| 1 | The covariate matrix `X` is the DAG's **adjustment set**: every node whose role is confounder, treatment predictor or outcome predictor, in the order of `data/params.yaml` `dag.nodes` (never the mediator `weight_change_6m`, never the derived `ckd`). **12 features:** `age, female, duration_years, hba1c, egfr, bmi, ascvd, hf, hypo_history, dka_history, pancreatitis_history, low_income` | `cohort.py:169-172`, `dag.py:39` |
| 2 | Cross-fitted propensities `e` (3 options) and cross-fitted outcome predictions `mu` (one `HistGradientBoostingRegressor` per option per fold) | `fitting.py:43-46`, `estimators.py:148-160` |
| 3 | AIPW score per patient and option: `phi_a = mu_a + 1{T=a}(Y - mu_a)/e_a` | `estimators.py:163-172` |
| 4 | **Six pseudo-outcomes:** the three scores, then the three differences `phi_SGLT2i - phi_DPP4i`, `phi_SU - phi_DPP4i`, `phi_SGLT2i - phi_SU` | `estimators.py:188-191`, `TARGETS` at `:185` |
| 5 | **Final stage:** ordinary least squares of each pseudo-outcome on `B = [1, (X - mean)/scale]`, where `mean` and `scale` are the training cohort's column means and standard deviations (scale 1 for a constant column). One `beta` of 13 numbers per target, all six at once (`beta_` has shape 13 x 6) | `DRLearner.fit`, `estimators.py:204-215` |
| 6 | **HC3 robust covariance** per target: `V_k = (B'B)^-1 B' diag(r_i^2/(1-h_i)^2) B (B'B)^-1`, with `h_i` the leverage clipped at 0.99 (`cov_` has shape 6 x 13 x 13) | `estimators.py:208-214` |
| 7 | **Prediction for a new patient `x`:** `value = b'beta_k` and a 95% interval `value ± z sqrt(b'V_k b)` with `b = [1, (x - mean)/scale]` and `z = 1.959964` | `DRLearner.predict`, `estimators.py:221-230` |

The weight (kg) and hypoglycaemia (probability) models are fitted the same way from their own scores and have the same structure (`fitting.py:48-54`).

### 1.2 Per comparison

| Target | Pseudo-outcome | Final-stage design | Interactions? |
|---|---|---|---|
| `SGLT2i`, `DPP4i`, `SU` (levels) | `phi_a` | `[1, 12 standardised features]` | none |
| `SGLT2i-DPP4i` | `phi_SGLT2i - phi_DPP4i` | the same 13 columns | none |
| `SU-DPP4i` | `phi_SU - phi_DPP4i` | the same 13 columns | none |
| `SGLT2i-SU` | `phi_SGLT2i - phi_SU` | the same 13 columns | none |

Because OLS is linear in its response and the design is shared, `beta(a-b) = beta(a) - beta(b)` **exactly** (VERIFIED to 8e-15), but `V(a-b)` is estimated from the contrast's own residuals, not as `V(a) + V(b)`.

### 1.3 Standardised coefficients (VERIFIED on `web/model.json`, HbA1c points per +1 SD of the feature)

| Feature | SD | Cohort mean | SGLT2i vs DPP-4i | SU vs DPP-4i | SGLT2i vs SU |
|---|---:|---:|---:|---:|---:|
| (intercept = cohort average effect) | | | -0.208 | -0.246 | +0.038 |
| `age` | 9.97 | 54.95 | -0.038 | -0.034 | -0.004 |
| `female` | 0.497 | 0.445 | +0.035 | +0.010 | +0.025 |
| `duration_years` | 4.895 | 6.944 | -0.016 | +0.077 | -0.092 |
| `hba1c` | 1.013 | 8.616 | -0.076 | -0.138 | +0.061 |
| `egfr` | 18.97 | 82.18 | -0.123 | -0.051 | -0.072 |
| `bmi` | 3.962 | 26.48 | -0.010 | -0.020 | +0.010 |
| `ascvd` | 0.365 | 0.159 | +0.011 | -0.003 | +0.014 |
| `hf` | 0.212 | 0.047 | +0.000 | +0.015 | -0.015 |
| `hypo_history` | 0.269 | 0.079 | +0.007 | +0.019 | -0.012 |
| `dka_history` | 0.106 | 0.011 | -0.041 | -0.006 | -0.035 |
| `pancreatitis_history` | 0.135 | 0.019 | -0.022 | -0.015 | -0.007 |
| `low_income` | 0.490 | 0.399 | -0.026 | -0.042 | +0.016 |

### 1.4 How `model.json` and `engine.js` reproduce it

- **Export:** `export_web._dr()` (`export_web.py:39-41`) writes `mean` (12), `scale` (12), `beta` (13 x 6) and `cov` (6 x 13 x 13) as plain floats; the same function exports the weight and hypoglycaemia models under `secondary`. `targets` lists the six targets in column order and `features` lists the 12 feature names in column order.
- **Reproduction:** `drPredict(model, x, d)` in `web/engine.js:106-122` builds `b = [1, (x_i - mean_i)/scale_i ...]`, takes `dot(b, beta[:,k])` for the value and `sqrt(b' cov_k b)` for the standard error: **the same arithmetic as Python, line for line.**
- **Existing proof it matches:** `tests/web/test_web.py::test_browser_engine_gives_the_same_answers_as_python` runs 155 patients (the presets plus 150 random) through `engine.js` (`run_engine.cjs`, `raw: true`) and compares `value`, `ci_low`, `ci_high` with the Python `DRLearner.predict` at **1e-9** (`_raw`), and the rounded outputs to the displayed precision. `test_model_json_is_fresh` compares a fresh export with the committed file to 1e-12.

## 2. Where the generator sets the true effect modifiers (`data/params.yaml`)

The truth is `cohort.true_expected_outcomes` (`cohort.py:89-111`): for each option `a`

`E[Y(a) | X] = drift + regression_to_mean*(hba1c-8.5) + female_term + base_a + per_hba1c_a*(hba1c-8.5) + per_10_egfr_a*(egfr-80)/10 + per_duration_year_a*(duration-7)`.

The drift, the regression-to-the-mean term and the sex term are **common to all options, so they cancel in every comparison.** What differs between options (all under `generator.outcome.effects`, `params.yaml:166-180`; centres at `:182`):

| Option | `base` (points) | `per_hba1c_pct` (per % above 8.5) | `per_10_egfr` (per 10 above 80) | `per_duration_year` (per year above 7) |
|---|---:|---:|---:|---:|
| SGLT2i | -0.75 (ASSUMED-DIRECTIONAL, TSAPAS_2020) | -0.20 (DENNIS_2022) | -0.06 (TRIMASTER_2023) | 0.00 (TEAM-SET) |
| DPP4i | -0.56 (TSAPAS_2020) | -0.12 (DENNIS_2022) | 0.00 (TRIMASTER_2023) | 0.00 (TEAM-SET) |
| SU | -0.80 (TSAPAS_2020) | -0.25 (DENNIS_2022) | 0.00 (TEAM-SET) | +0.02 (TEAM-SET) |

### 2.1 The true effect modifiers per comparison (derived by subtraction)

| Comparison | True base | `hba1c` slope (per %) | `egfr` slope (per unit) | `duration_years` slope (per year) | True modifiers |
|---|---:|---:|---:|---:|---|
| SGLT2i vs DPP-4i | -0.19 | -0.08 | -0.006 | 0 | `hba1c`, `egfr` |
| SU vs DPP-4i | -0.24 | -0.13 | 0 | +0.02 | `hba1c`, `duration_years` |
| SGLT2i vs SU | +0.05 | +0.05 | -0.006 | -0.02 | `hba1c`, `egfr`, `duration_years` |

**Every other feature (`age`, `female`, `bmi`, `ascvd`, `hf`, `hypo_history`, `dka_history`, `pancreatitis_history`, `low_income`) has a true modification of exactly 0 for every comparison.** Several of them affect *which drug a patient receives* (`generator.assignment`: for example `ascvd`, `hf` and `pancreatitis_history` raise the odds of SGLT2i; `hypo_history` lowers the odds of SU): that is confounding, which the engine corrects, not effect modification.

### 2.2 How well the fitted model recovers it (VERIFIED, committed `model.json`, estimate per original unit with 95% interval)

| Comparison | Feature | Fitted | 95% interval | Truth |
|---|---|---:|---|---:|
| SGLT2i vs DPP-4i | `hba1c` | -0.075 | -0.131 to -0.020 | -0.080 |
| | `egfr` | -0.0065 | -0.0099 to -0.0031 | -0.0060 |
| | `duration_years` | -0.0032 | -0.0138 to +0.0075 | 0 |
| SU vs DPP-4i | `hba1c` | -0.136 | -0.194 to -0.078 | -0.130 |
| | `duration_years` | +0.0156 | +0.0047 to +0.0266 | +0.0200 |
| | `egfr` | -0.0027 | -0.0057 to +0.0003 | 0 |
| SGLT2i vs SU | `hba1c` | +0.061 | +0.015 to +0.107 | +0.050 |
| | `egfr` | -0.0038 | -0.0072 to -0.0004 | -0.0060 |
| | `duration_years` | -0.0188 | -0.0286 to -0.0091 | -0.0200 |

All **7** true-modifier intervals (2 + 2 + 3) contain the truth, and **all 29 non-modifier intervals** (10 + 10 + 9) include zero. The table shows 9 of the 36 (12 features x 3 comparisons). Two cautions the paper must state: (a) this works because the generator's truth is **linear**, matching the final stage's form, so it shows the pipeline works, not that real effects are linear; (b) with 36 intervals at a nominal 95%, about 2 would exclude the truth by chance under a perfect model.

## 3. The proposed SHAP: exact, per comparison

### 3.1 Formula

For a comparison `c` (one of the three contrasts), a patient `x`, and the final-stage coefficients:

- `slope_cj = beta_c[j] / scale_j` (HbA1c points per **original unit** of feature `j`; `beta_c[j]` is the 13-vector entry for feature `j`, index `j+1` after the intercept).
- **Contribution** (SHAP value): `phi_cj(x) = slope_cj * (x_j - mean_j)` (HbA1c points).
- **Base value:** `base_c = beta_c[0]`, the estimate for a patient exactly at the cohort mean; it equals the cohort's average effect (AIPW).
- **Additivity (exact):** `estimate_c(x) = base_c + sum_j phi_cj(x)`.

This is coefficient x (value - cohort mean), as P11 asked. Basis terms are summed back to their original feature by the identity, because there is one basis column per feature. **If a later version adds an interaction column `c*(a - mean_a)(b - mean_b)`**, the Shapley split with the cohort mean as the reference point gives each of the two features half of that term, and the main effects stay as above; the test below would then need a case for it.

**Which targets get drivers.** Only the **three comparisons** (the doctor's question: "this drug versus that drug"). The level targets (`SGLT2i`, `DPP4i`, `SU`) are dominated by prognosis (everyone with a high starting HbA1c falls further, whatever the drug) and would show exactly what version A's SHAP shows; they are computed only for the Analysis tab's A-versus-C contrast (P26), never put on the answer card. For the card the comparator is DPP-4i (plan 8.11), so two comparisons are explained per patient: SGLT2i vs DPP-4i and SU vs DPP-4i.

### 3.2 Worked example with real numbers (60-year-old woman, HbA1c 8.2, eGFR 40, BMI 25.5, past pancreatitis; preset 2; VERIFIED)

**SGLT2i vs DPP-4i:** base -0.208, estimate **-0.024**. (The 95% interval printed with the estimate stays as the engine computes it.)

| Feature | Patient | Cohort mean | Slope per unit | Contribution | 95% interval of the contribution | Clear driver? |
|---|---:|---:|---:|---:|---|---|
| `egfr` | 40 | 82.2 | -0.0065 | **+0.274** | +0.131 to +0.417 | **yes** |
| `pancreatitis_history` | 1 | 0.02 | -0.162 | -0.159 | -0.609 to +0.290 | no |
| `female` | 1 | 0.44 | +0.071 | +0.039 | -0.017 to +0.096 | no |
| `hba1c` | 8.2 | 8.62 | -0.075 | **+0.031** | +0.008 to +0.055 | **yes** |
| `low_income` | 0 | 0.40 | -0.053 | +0.021 | -0.022 to +0.065 | no |
| `age` | 60 | 54.95 | -0.0038 | -0.019 | -0.051 to +0.012 | no |
| other 6 features | | | | -0.003 | | |

Check: -0.208 + 0.274 - 0.159 + 0.039 + 0.031 + 0.021 - 0.019 - 0.003 = **-0.024** (the sum of all 12 contributions is +0.184).

**Card sentence (templated, numbers from the table):** "For the average patient, SGLT2i lowers HbA1c 0.21 points more than DPP-4i. For this patient the estimate is -0.02. Lower kidney function (eGFR 40) takes 0.27 away; a lower HbA1c than average takes 0.03 away." Two clear drivers, both pushing the same way. **No sentence mentions pancreatitis**, correctly: the generator says it does not modify the effect (the safety rules, not the estimate, handle past pancreatitis for DPP-4i).

**SU vs DPP-4i for the same patient:** base -0.246, estimate -0.138; clear drivers `hba1c` (+0.057, +0.032 to +0.081) and `duration_years` (+0.017, +0.005 to +0.028). `egfr` (+0.114, -0.012 to +0.239) just misses and is **not** shown, which matches the truth (SU vs DPP-4i has no eGFR modification).

### 3.3 Interval of a contribution (no bootstrap)

`phi_cj = c_j * beta_cj` with `c_j = (x_j - mean_j)/scale_j` a fixed number for the patient, so its standard error is `|c_j| * sqrt(V_c[j+1][j+1])`, and the 95% interval is `phi_cj ± z * |c_j| * sqrt(V_c[j+1][j+1])` with the engine's `z = 1.959964`. This matches P25 and uses the same HC3 assumptions as the existing interval. **Stated limits:** it ignores the uncertainty of the cohort means and scales (treated as constants), the covariance between features' coefficients (each interval is marginal), and the uncertainty in the earlier cross-fitted models, exactly as the engine's own interval does.

### 3.4 Why the interval check is the same for every patient

Because `c_j` is a fixed number, "the interval of `phi_cj` excludes 0" is equivalent to "the coefficient `beta_cj` is clearly non-zero" (`|beta_cj| > z * SE_cj`), whatever the patient. So the **set of clear features per comparison is a property of the model, not of the patient**; the patient only decides which of those features have the largest contribution. With the committed model: SGLT2i vs DPP-4i `hba1c`, `egfr`; SU vs DPP-4i `hba1c`, `duration_years`; SGLT2i vs SU `hba1c`, `egfr`, `duration_years`. That is exactly the true-modifier set in every case (VERIFIED), which is why this rule is recommended.

### 3.5 Display rule for the answer card (P25)

1. Per displayed comparison, drivers are the features whose contribution interval **excludes 0**, sorted by `|phi|` descending; show **up to 3** (never pad with unclear ones). If none is clear, show "No single patient detail clearly drives this estimate."
2. Only for options with status `estimate`; never for an excluded or abstained option.
3. Always: 95% interval of the estimate next to the sentence; "drivers, not causes"; units in HbA1c points; direction in words ("the estimate is larger/smaller for patients with ...", plan rule 6).
4. Round contributions to 3 decimals; show a final row "all other details" equal to `estimate - base - (sum of rows shown)` so the displayed rows add up to the displayed estimate within 0.001.
5. Binary features: say "past pancreatitis: yes", not a number; the plain-words label table is exported (3.7).
6. **Multiple comparisons:** the nominal 95% rule is the product-wide standard; the Guide's caution says "with many details checked, an occasional driver can be a chance finding."

### 3.6 The Python reference and the JavaScript twin

- **Python (P25):** `diacausal/xai/cate_shap.py` (after the restructure; `diacausal_engine/` path before it) with `explain_effect(dr, x, target, z) -> EffectExplanation` holding `base`, `estimate`, and a list of `{feature, value, mean, slope_per_unit, phi, ci_low, ci_high, clear}`. Pure NumPy, no `shap` import (so the website export and CI stay light).
- **JavaScript (P25):** `explainEffect(model, x, target)` in `web/engine.js`, using only `model.dr.mean/scale/beta/cov`, `model.targets`, `model.features`, `model.thresholds.ci_z`; it returns the same fields; `recommend()` calls it for the comparisons that are displayed.

### 3.7 What to export to `model.json` (almost nothing)

**No new numeric field is needed**: `dr.mean`, `dr.scale`, `dr.beta`, `dr.cov`, `targets`, `features` and `thresholds.ci_z` already determine every contribution and interval (P25's "export coefficients and means" is already done). Add one small block, from `params.yaml` or a reviewed table, **not typed into `engine.js`**:

```json
"xai": {
  "method": "exact SHAP of the final linear stage: coefficient x (value - cohort mean); base value = cohort average effect",
  "max_drivers": 3,
  "driver_rule": "interval excludes zero, ranked by absolute contribution",
  "explained_targets": ["SGLT2i-DPP4i", "SU-DPP4i", "SGLT2i-SU"],
  "labels": { "egfr": {"text": "kidney function (eGFR)", "unit": "mL/min/1.73m2", "kind": "continuous"},
              "hba1c": {"text": "starting HbA1c", "unit": "%", "kind": "continuous"},
              "pancreatitis_history": {"text": "past pancreatitis", "kind": "yes_no"} }
}
```
`max_drivers` goes into `data/params.yaml` as a TEAM-SET number with a source note (the loader refuses a number without one); the labels get a doctor/Member D read-through (wording only). `test_model_json_is_fresh` then covers the block automatically.

## 4. Python-versus-JavaScript parity test

Extend the existing pattern, not a new mechanism: `tests/web/run_engine.cjs` (or a sibling `run_explain_effect.cjs`) prints `explainEffect` for every patient and comparison; the test compares against the Python reference.

| Test (in `tests/web/test_web.py` or `tests/xai/test_parity.py`) | What it asserts |
|---|---|
| `test_browser_shap_matches_python` | the 155 patients of the existing parity test, all 3 comparisons, all 12 features: `phi`, `ci_low`, `ci_high`, `base`, `estimate` equal Python at **1e-9**; `clear` flags and the order of the shown drivers are identical |
| `test_shap_adds_up_in_both` | `base + sum(phi)` equals the engine's `value` for that comparison to **1e-9**, in Python and in JavaScript |
| `test_shap_matches_shap_linearexplainer` (Python only, needs `shap`) | for 50 patients, `shap.LinearExplainer((slope, intercept), shap.maskers.Independent(X, max_samples=len(X)))` equals the formula to 1e-9 (with the default masker it would not: finding 7) |
| `test_driver_rules_on_the_card` | an excluded or abstained option has no drivers; at most 3 shown; every shown driver's interval excludes 0; none shown when none is clear; the "other details" row makes the rows add to the estimate within 0.001 |
| `test_shap_at_the_mean_is_zero_and_signs_follow_coefficients` | a patient exactly at the cohort mean has all `phi = 0`; changing one feature changes only that feature's `phi`, by `slope x delta` |
| `test_clear_set_equals_the_true_modifiers_on_the_committed_model` | for the committed `model.json`, the clear features of each comparison equal the modifier set derived from `params.yaml` (section 2.1). This is a regression check on this synthetic cohort, not a claim about the real world |

## 5. Version A: the gradient-boosted XAI-only baseline (P17)

**Purpose:** what a team would get by training a good predictor on routine data and explaining it with SHAP and LIME, *without* causal adjustment, intervals, abstention or the rules-first order. It never reaches a doctor, the API or `web/` (plan 7.5).

### 5.1 Model and data

- **Model:** `sklearn.ensemble.HistGradientBoostingRegressor`, the **same class and settings** as the engine's outcome model and the benchmark's S-learner (`params.yaml` `engine.outcome_model`: `max_iter`, `learning_rate`, `max_depth`, seeded). TreeSHAP supports it (VERIFIED: additivity error 2e-15; it is the same class the engine uses, so version A differs from B only in *how the effect is estimated*). `GradientBoostingRegressor` also works and is the fallback if a future `shap` drops support.
- **Inputs:** the 12 features plus 3 one-hot treatment columns (exactly `s_learner`, `estimators.py:239`). **Output:** the observed 6-month HbA1c change.
- **Training data: factual data only.** `observed_view(cohort)` columns `X`, `T`, `Y` (no `mu_true_*`, `e_true_*`, `y_true_*`, no propensity, no AIPW scores, no rules). Per benchmark replicate: train on that replicate's cohort (n = 5000), test on its fresh test cohort (n_test = 2000; 1000 in `--quick`) which carries the ground truth. No extra split is needed. The three presets are explained with the model fitted on the engine's own cohort (seed 2026).
- **Predictions per patient:** for each option `a` not excluded by `data/rules.csv`, `f(x, T=a)`; **pick = lowest predicted HbA1c**; the effect of a comparison is `f(x, a) - f(x, b)`. **Same exclusions as B** (plan 7.1: apply the same rule exclusions in all four), so the comparison measures only how the estimate is made. Version A does **not** apply the overlap abstention: that is the point of the "answers given where data are thin" metric.

### 5.2 Explanations

- **TreeSHAP** (`shap.TreeExplainer`, interventional, background = a fixed random 500-row sample of the training inputs). Global: mean |SHAP| per feature and a beeswarm; local: waterfalls for the 3 presets. SHAP is linear in the model output for a fixed background, so the explanation of a comparison is `phi_j(f(.,a)) - phi_j(f(.,b))` for the 12 features. The three treatment columns are reported separately: their SHAP is relative to the cohort's **prescribing mix**, not to a clinical alternative (plan 7.3).
- **LIME** (`LimeTabularExplainer`, mode regression, `discretize_continuous=False`, the binary features declared categorical so perturbations stay yes/no, `num_samples=5000`, seeded) applied to the **same scalar function** `g(x) = f(x,a) - f(x,b)`, so SHAP and LIME explain the same quantity. For the 3 presets: **10 seeds each** (P17).
- **Outputs:** `results/xai/baseline_metrics.csv`, `results/xai/shap_A.csv` (patient-level and global values), `results/xai/lime_stability.csv`, figures in `results/xai/`.

### 5.3 Dependencies

`shap==0.52.0` and `lime==0.2.0.1` in a **new `requirements-xai.txt`** (`-r requirements-engine.txt` plus the two pins), not in `requirements-engine.txt`: SHAP pulls `numba` and `llvmlite`, which the website export, the engine's CI job and the Streamlit demo do not need. A new CI job installs it and runs `tests/xai`; `pip-audit` covers the file. Licences: SHAP MIT, LIME BSD-2-Clause (UNVERIFIED here; check before the report's references). Version C needs **no** extra package (NumPy only); only its cross-check test does.

## 6. The A to D metrics (plan section 7.1), defined exactly

**Common set-up.** 20 benchmark replicates (cohort n = 5000, test n = 2000; the existing `benchmark.run`, same seeds), ground truth from the test cohort's `mu_true_*` (true expected HbA1c change per option) and `e_true_*` (true propensities). Every table cell is the **mean over replicates with a 95% t-interval** (t with 19 degrees of freedom). The same safety-rule exclusions apply to all versions. Comparisons are the three contrasts; "all patients" means test patients for whom the rules leave at least two options.

| Metric | Definition | A | B | C | D | Output column |
|---|---|:-:|:-:|:-:|:-:|---|
| **Prediction error** | RMSE of the predicted factual HbA1c change (on test patients, using their true expected outcome under the drug each would be given) | yes | (outcome model, cross-fitted) | = B | = B | `pred_rmse` |
| **Effect bias** | mean of (estimated effect - true effect) per comparison | yes | yes | = B | = B | `effect_bias_<comparison>` |
| **PEHE** | root-mean-square error of the patient-level effect, per comparison (`metrics.pehe`) | yes (exists for S-learner) | yes (exists) | = B | = B | `pehe_<comparison>` |
| **Picks the truly best drug** | share of patients where the lowest-estimate allowed drug equals the lowest-true-outcome allowed drug | yes, all patients | yes, on patients B answers; also reported on the same patients for A | = B | = B | `best_pick_rate`, `best_pick_rate_same_patients` |
| **Regret** | mean extra HbA1c versus the true best allowed drug (`metrics.policy_regret`) | yes | yes | = B | = B | `regret` |
| **Answers where data are thin** | thin = a patient whose smallest **true** propensity is below the engine's overlap threshold (0.05). Report the share of thin patients that receive an answer, and the error (PEHE) on thin patients versus the rest | answers all | abstains on thin | = B | = B | `answered_when_thin`, `pehe_thin`, `pehe_not_thin` |
| **Abstention rate** | `metrics.abstention_rate` | 0 by design | yes (exists) | = B | = B | `abstention_rate` |
| **Interval coverage** | share of test patients whose true effect lies inside the 95% interval | none | yes (exists) | = B | = B | `coverage_<comparison>` |
| **SHAP-LIME agreement** | per patient and comparison: Spearman rank correlation of the 12 absolute SHAP values with the 12 absolute LIME weights, and the Jaccard overlap of their top-3 sets; mean over 100 sampled test patients per replicate | yes | n/a | n/a | n/a | `shap_lime_spearman`, `shap_lime_top3_jaccard` |
| **LIME stability** | for each of the 3 presets and comparisons, 10 LIME runs with different seeds: mean pairwise Jaccard of the top-3 sets (1 = perfectly stable), and the coefficient of variation of the top feature's weight | yes (presets, replicate 0) | n/a | n/a (exact SHAP has no randomness; state as 1.0 by construction) | n/a | `lime_top3_jaccard`, `lime_top_weight_cv` |
| **Top features match the true modifiers** | per comparison, global importance `mean |phi_j|` over test patients; **precision at k = number of true modifiers** (the top-k features that are true modifiers, divided by k), and Spearman between `mean |phi_j|` and the true importance `|slope_j| x SD_j` over the 12 features | yes (SHAP; LIME optional) | n/a | yes | = C | `modifier_precision_at_k`, `modifier_spearman` |
| **False-driver rate** | share of displayed drivers (the card rule of 3.5) that are not true modifiers; and the share of true modifiers that appear among displayed drivers (recall) | n/a | n/a | yes | = C | `false_driver_rate`, `driver_recall` |
| **Contributions add up** | maximum absolute value of `base + sum(phi) - estimate` over all test patients and comparisons | n/a | n/a | yes (expect about 1e-15) | = C | `additivity_max_error` |
| **Driver interval coverage** | share of (replicate, comparison, feature) in which the 95% interval of the per-unit slope contains the true slope (modifiers and non-modifiers) | n/a | n/a | yes | = C | `slope_interval_coverage` |
| **Citation precision** | share of generated sentences whose cited passage supports them (the existing checker, `check_answer`), over the 20 golden questions of plan 8.8 plus the 60 gold questions | n/a | n/a | n/a | yes | `citation_precision` |
| **Number-match pass rate** | share of drafts whose every number appears in `CausalOutputV1` or the drivers (output guard 3) | n/a | n/a | n/a | yes | `number_match_pass` |
| **Fallback rate** | share of answers that fall back to the template | n/a | n/a | n/a | yes | `fallback_rate` |
| **Passage backs the top driver** | for each shown top driver, whether one of the retrieved passages is the one a reviewer listed for that driver and option (a small reviewed table, `eval/xai_driver_evidence.csv`, written by Members B and D: e.g. `egfr` x SGLT2i -> the FDA kidney communications and the WHO section on renal function); share of drivers backed | n/a | n/a | n/a | yes | `driver_passage_hit_rate` |

**Output files:** `results/xai_ablation.csv` (one row per version x metric x comparison: `version, metric, comparison, mean, ci_low, ci_high, n_reps`), `results/xai/*.csv`, and the figures P27 draws in the Analysis tab (version A vs C SHAP bars side by side; LIME stability chart), all labelled "synthetic benchmark".

**What to expect (hypotheses, not results; UNVERIFIED until run):** A predicts HbA1c well but picks worse and answers everywhere, including thin patients; A's SHAP ranks prognostic factors (`hba1c` first, because everyone with a high start falls further) while C's ranks only effect modifiers; the three treatment bars in A reflect the prescribing mix. **Runtime estimate (UNVERIFIED):** LIME at about 0.02 to 0.05 s per explanation means about 15 s per replicate for 100 patients x 3 comparisons, so about 5 minutes for 20 replicates; TreeSHAP on 2000 patients is seconds. Measure before committing to 100 LIME patients.

## 7. Files and tests to add

### 7.1 Files

| File | Prompt | Purpose |
|---|---|---|
| `docs/XAI_PLAN.md` | P11 | this plan |
| `requirements-xai.txt` | P17 | `-r requirements-engine.txt`, `shap==0.52.0`, `lime==0.2.0.1` |
| `diacausal/xai/__init__.py`, `diacausal/xai/baseline.py` | P17 | version A: model, predictions, TreeSHAP, LIME, metrics |
| `diacausal/xai/truth.py` | P17 | the true per-unit slopes and modifier set per comparison, **derived from `params.yaml`** (never typed) |
| `diacausal/xai/cate_shap.py` | P25 | `explain_effect`, the driver rule, the card-text numbers |
| `web/engine.js` (edit) | P25 | `explainEffect()`; `recommend()` returns drivers for displayed comparisons |
| `data/params.yaml` (edit) | P25 | `xai.max_drivers` (TEAM-SET, with a source note) |
| `diacausal/causal_inference/export_web.py` (edit) | P25 | add the `xai` block to `model.json`; re-export `web/model.json` |
| `diacausal/api/schemas/causal.py` (edit, optional) | P25 | `DriverV1.ci95` is already optional; fill it from the interval of the contribution |
| `web/app.js`, `web/styles/screens.css` (edit) | P25/P27 | the "What drives this estimate" expander (screen 17) |
| `diacausal/xai/ablation.py`, `scripts/xai_ablation.py` | P26 | versions A to D over the 20 replicates; writes `results/xai_ablation.csv` |
| `eval/xai_driver_evidence.csv` | P26 (Members B, D) | the reviewed driver-to-passage table (needs a doctor/Member B read) |
| `results/xai/*.csv`, `results/xai_ablation.csv`, figures | P17, P25, P26 | committed results (like `results/` today) |
| `tests/xai/` (new folder) | P17, P25, P26 | the tests below |
| `.github/workflows/check.yml` (edit) | P17 | a job that installs `requirements-xai.txt` and runs `tests/xai` |
| `docs/TESTING.md`, `CLAUDE.md`, `docs/WEBSITE.md` (edit) | P25 | requirement-to-test rows, the new commands, the card |

### 7.2 Tests

| Test file | Tests | Asserts |
|---|---|---|
| `tests/xai/test_truth.py` | `modifiers_come_from_params`, `common_terms_cancel` | the derived truth equals section 2.1 (3 comparisons); changing a value in a copy of `params.yaml` changes the truth |
| `tests/xai/test_cate_shap.py` | `adds_up`, `zero_at_the_mean`, `matches_formula_by_hand`, `matches_shap_linearexplainer`, `interval_matches_hc3_formula`, `clear_rule`, `no_drivers_for_abstained_or_excluded` | section 4's properties in Python (uses `shap` only for the cross-check) |
| `tests/web/test_web.py` | `test_browser_shap_matches_python`, `test_shap_adds_up_in_both`, `test_clear_set_equals_the_true_modifiers_on_the_committed_model` | section 4's parity; `test_model_json_is_fresh` also covers the `xai` block |
| `tests/xai/test_baseline.py` | `trains_on_factual_data_only` (the training frame has no truth, propensity or score columns), `same_rule_exclusions_as_the_engine`, `treatment_shap_is_relative_to_the_mix`, `shap_additivity_of_the_tree_model`, `lime_is_seeded_and_the_same_seed_repeats`, `baseline_never_imported_by_web_or_api` (a scan of `web/` and `diacausal/api/` for imports of `diacausal.xai.baseline`) | version A's guarantees |
| `tests/xai/test_metrics.py` | `metrics_on_a_tiny_cohort_match_hand_calculation`, `thin_patients_use_true_propensity`, `precision_at_k_and_spearman_definitions` | the formulas of section 6 on a small hand-checkable example |
| `tests/xai/test_ablation.py` | `all_four_versions_present`, `same_exclusions_in_every_version`, `csv_schema`, `saved_results_are_fresh` (a `--quick` re-run equals the committed quick file to 1e-9) | the A-D table |
| `tests/web/test_web.py` | `test_web_text_keeps_the_screens_content_rules` (exists) | the new copy never uses cause words about drivers; add a check that every driver sentence says "estimate is larger/smaller" and ends in the card's "The clinician decides." |

## 8. Changes this plan suggests to the other prompts (for you to approve)

1. **P25 step 3:** "top 3 drivers" becomes "up to 3 clear drivers (interval excludes zero)", and the empty case gets its own sentence (section 3.5).
2. **P25 step 1:** "cross-check with `shap.LinearExplainer`" must say "with `shap.maskers.Independent(X, max_samples=len(X))`" (finding 7).
3. **P25 step 2:** "export coefficients and means to `model.json`" is already done; replace with "add the small `xai` block and `max_drivers` in `params.yaml`".
4. **P17:** name the model `HistGradientBoostingRegressor` (same as the engine), put the pins in `requirements-xai.txt`, and reuse the benchmark's replicate loop and test cohort instead of a separate split.
5. **Plan 7.4:** the worked example's coefficients are "made up"; the real ones are in section 3.2 and show a patient where eGFR is the dominant, correct, driver.
6. **Plan 7.2:** "a confounder that does not change the drug difference should get little importance": with the committed model this holds exactly (all 9 non-modifiers are unclear), but state in the paper that it holds because the synthetic truth is linear.

## 9. Open questions and risks

| # | Item | Why it matters |
|---|---|---|
| 1 | **A real clinician's reading of "drivers".** The sentence "the estimate is larger/smaller for patients with ..." must be reviewed for plain-English clarity | the product safety wording; Member D |
| 2 | **Linear truth.** The generator is linear, the final stage is linear, so recovery is expected by construction | the paper must not claim SHAP finds real-world modifiers (plan 7.6) |
| 3 | **Multiple comparisons.** 36 nominal 95% intervals | a chance driver can appear; mention in Guide Cautions |
| 4 | **Rare binary features** (`dka_history` 1.1%, `pancreatitis_history` 1.9%, `hf` 4.7%) have very wide intervals, so they will almost never be clear drivers even if real | an honest limitation of 5000 synthetic patients |
| 5 | **LIME on binary features** creates off-distribution samples unless the features are declared categorical | handled in 5.2; stability still reported |
| 6 | **`numba` pulled in by SHAP** | kept out of the engine's core requirements (5.3) |
| 7 | **Secondary outcomes** (weight, hypoglycaemia) have the same linear structure, so the same function could explain them | out of scope for 30 Oct; list as FUTURE WORK |
| 8 | **Timing:** P17 is due by Sun 11 Oct (gate G1) and the restructure moves files the same week | write `diacausal/xai/` at its final path, as the restructure plan's rule 1 says |
| 9 | **UNVERIFIED:** the driver-to-passage gold table. (Run time measured: about 2.5 minutes for version A. Licences read from the installed packages on 10 Oct 2026: `shap` 0.52.0 is MIT, `lime` 0.2.0.1 is BSD, as their package metadata says; the licence text files were not read) | measure or check when built |
