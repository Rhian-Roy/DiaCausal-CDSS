# Causal engine plan: 3 options added to metformin (v0.3, for the 30 Sep mid-sem)

> Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

**Question.** For one adult with type 2 diabetes already on metformin: what is the expected
6-month change in HbA1c (in percentage points) if we add an **SGLT2 inhibitor**, a **DPP-4
inhibitor**, or a **sulfonylurea**? Each answer comes with a 95% range, or "insufficient evidence"
when the data can't answer fairly. The clinician decides.

The reference tables come from `docs/02_Causal_Engine_Build_Guide.md` Part 6 and are used exactly.
What the repo already has is in `docs/REPO_INVENTORY.md`.

## 0. Status (27 Sep build) and how it maps onto our flow chart

**Built: steps a–j.** There are 130 tests in `tests/engine/`, and the full benchmark results are
committed in `results/`. The flow chart has two columns that run in parallel with no router: RAG
and the Causal Inference Pipeline. **v0.3 is the whole Causal Inference Pipeline column.** Its
last box (the structured Causal Output) is the hand-off to the Evidence Fusion layer, which we
build in October together with RAG and the LLM.

| Flow-chart box | Where it is |
|---|---|
| Causal dataset ingestion (observational data, preprocessing, variables; distinct from the RAG documents) | `cohort.py`: `generate_cohort` (synthetic), `load_dataset` (a real de-identified CSV later), `observed_view` (hides the truth) |
| Causal inference engine: DAG formulation, treatment and outcome identification | `dag.py` plus the `dag:` section of `data/params.yaml`: treatment, outcome, adjustment set; mediators are never adjusted for |
| Model selection and estimation: DML, propensity scores, CATE | `propensity.py` (cross-fitted multinomial propensity); `estimators.py` (naive, IPW, propensity-score matching, AIPW, which is the cross-fitted DML score; DR-learner CATE; T- and S-learners) |
| Causal analysis: counterfactual reasoning | `recommend.py`: the expected outcome under **each** option for this patient, plus the fair pairwise differences |
| Causal output: structured JSON (Applicable, Intervention, Outcome, Effect, Confidence, Assumptions) or NOT_APPLICABLE | `schemas.CausalOutput`, returned by `POST /api/v1/recommend` and shown in the demo |
| Safety + validation layer (disclaimer) | Already present on the causal side: the `data/rules.csv` guardrails run first; `check_output` refuses dose text and numbers without an interval; the intended-use statement is on every response |
| RAG pipeline, Evidence Fusion, prompt builder, diabetes-focused LLM | October (docs/03, prompts 07–09) |

## 1. The six rules we never break

1. Decision support only; the clinician decides. Every screen and API response shows the
   intended-use sentence above.
2. Safety rules run **before** any estimate. Contraindication and kidney-function thresholds for the
   engine live only in `data/rules.csv`, with a source for each rule. They are never hard-coded or
   invented. No drug doses are ever shown.
3. Every estimate has a 95% interval. If this patient's propensity for an option is below 0.05, we
   show "insufficient evidence" instead of a number.
4. Synthetic data only. Every generator parameter has a source and a status (CITED,
   ASSUMED-DIRECTIONAL or TEAM-SET) in `data/params.yaml`. The Pima dataset is not Indian data and is
   not used.
5. Units: HbA1c %, eGFR mL/min/1.73m², cost INR/month. Asian-Indian BMI cut-offs: overweight ≥ 23,
   obese ≥ 25.
6. We never weaken or delete a test to make it pass. No API keys or secrets go in this public repo.

## 2. Decisions and why

| # | Decision | Why (plain English) |
|---|---|---|
| D1 | A **new package, `diacausal_engine/`**. The old `causal_engine/` stays as it is. | The old code answers a different question (2 arms). Leaving it alone keeps its notebooks and tests working. The new file names (`guardrails.py`, `estimators.py`) match what the report guide copies into Overleaf. |
| D2 | **Keep both rules tables.** The engine reads only `data/rules.csv`; the chat app keeps its `guardrails.v1.yaml`. | You asked for "both … whatever suits best". Part 6 must be used exactly, and the chat app's tested behaviour shouldn't change five days before the demo. §4 lists every difference for Member D and the doctor. When the two are joined in October, **the stricter action wins** until the doctor decides, so no safety rule from either table is ever lost. |
| D3 | **The demo is Streamlit** (`demo/streamlit_app.py`), not the React chat page. | The React page needs sign-in with an authenticator app and a Node build. Showing estimates there means changing the tested contract in six or more files. Streamlit is one file and one command, and it runs offline on the MacBook. Our guides, viva answers and slides already describe a Streamlit demo. |
| D4 | **FastAPI:** a small separate app, `diacausal_engine/api.py`, with `POST /api/v1/recommend` on port 8001. | This is the endpoint slide 13 names. Port 8001 doesn't clash with the chat backend on 8000. The demo and the API call the same Python function, so they always agree. |
| D5 | **Its own pinned `requirements-engine.txt`**, a root `.venv`, and tests in `tests/engine/`. | Installing it is small and quick (no Whisper, no DoWhy/EconML). The old test file (2 known failures) stays out of the way. The fastapi, uvicorn and PyYAML pins match the backend's. |
| D6 | **The audit log** is `logs/audit.jsonl` (not committed). Each line holds the request ID, time, versions, **names** of the fields received, and each option's status and rule IDs. | CLAUDE.md says never to log patient values. That is stricter than viva answer 27, so say "we log what was decided and why, not the patient's numbers". |
| D7 | **Colours:** red = excluded, amber = caution, grey = insufficient evidence, pine (teal) = an estimate. **Never green for "recommended".** | This follows the PPT guide. The tokens come from `frontend/src/index.css`. |

## 3. Build plan for Step 2 (after you say "go")

For each step below: write the code and its tests, run `python -m pytest tests/engine -q`, explain
it in three plain sentences, commit, and push.

### a) Synthetic India-calibrated cohort
- **Files:** `data/params.yaml`, `diacausal_engine/config.py`, `diacausal_engine/cohort.py`.
- **What:** about 5,000 made-up patients.
  - Their details are age, sex, diabetes duration, HbA1c, eGFR, BMI, heart disease (ASCVD), CKD,
    heart failure, past hypoglycaemia, past DKA, past pancreatitis, and low income.
  - The drug each patient "received" depends on those details, the way real prescribing does. That
    creates **confounding by indication**. Sicker patients with high HbA1c or heart disease get
    SGLT2i more often. Low eGFR means less SGLT2i. Older age or past hypoglycaemia means less
    sulfonylurea. Low income means more sulfonylurea.
  - For every patient we store **all three true outcomes** (`y_true_sglt2i`, `y_true_dpp4i`,
    `y_true_su`). We only ever "observe" the one for the drug they got.
- **Safety net:** the loader **refuses to run** if any parameter has no source or no valid status.
- **Tests:**
  - the loader refuses an unsourced parameter;
  - the same seed gives the same cohort;
  - all three arms appear;
  - the observed outcome equals the stored true outcome for the drug received;
  - the naive comparison is clearly wrong, i.e. confounding exists;
  - eGFR is at least the metformin cut-off;
  - the BMI cut-offs match the backend's.

### b) Guardrails from `data/rules.csv`
- **Files:** `data/rules.csv` (the Part 6 table, character for character) and
  `diacausal_engine/guardrails.py`.
- **What:**
  - Read the csv and check every row. It needs a known operator (`lt le gt ge eq`), a known action
    (`EXCLUDE`, `CAUTION`), a known drug class, a known field, and a non-empty source and section.
    A bad row stops the program.
  - For one patient, return for each option: **excluded** or **caution**, with the message, the
    source, the section, and whether the rule is VERIFIED or UNVERIFIED.
  - UNVERIFIED rules still apply, because that is the safe direction, and they are labelled so the
    doctor can see it.
- **Tests:**
  - the csv equals the guide's block;
  - each rule fires at its boundary (eGFR 44.9 fires "below 45"; 45 does not);
  - a bad row is refused;
  - a scan of the engine's code finds no clinical thresholds written into it.

### c) Cross-fitted multinomial propensity model and overlap check
- **File:** `diacausal_engine/propensity.py`.
- **What:**
  - Multinomial logistic regression gives each patient's chance of getting each of the three drugs.
  - It is **cross-fitted** with 5 folds: every patient's score comes from a model that never saw
    that patient.
  - **Overlap check:** if this patient's chance for an option is below 0.05, that option gets
    "insufficient evidence".
  - **Support check:** a patient outside the range of the synthetic cohort gets "insufficient
    evidence — outside the cohort" for all options. Examples are type 1 diabetes, or an eGFR lower
    than anyone in the cohort.
- **Tests:**
  - each patient's three scores sum to 1;
  - out-of-fold scores differ from in-sample ones;
  - the viva example: scores 0.03, 0.55, 0.42 → the first option is "insufficient evidence";
  - out-of-range patients abstain.

### d) Average effects three ways: naive, IPW, AIPW, each with a 95% CI
- **File:** `diacausal_engine/estimators.py`. The formulas are written out in NumPy so each line can
  be explained.
  - **Naive:** the average outcome in each drug group. This is the unfair comparison.
  - **IPW:** re-weights patients by 1 ÷ (their chance of getting their drug), so each group looks
    like everyone. The standard error comes from the influence function.
  - **AIPW (doubly robust):** `φ_a = μ̂_a(X) + 1{A=a}·(Y − μ̂_a(X)) / ê_a(X)`. It combines an outcome
    model μ̂ (gradient boosting, cross-fitted, one per drug) with the propensity ê. SE = sd(φ)/√n.
  - The output is the average 6-month change for each drug, and the three pairwise differences
    (SGLT2i−DPP-4i, SU−DPP-4i, SGLT2i−SU), each with a 95% CI.
- **Tests:**
  - the guide's worked example: naive −0.425 vs fair −0.15;
  - the viva IPW example: weights 1.25 and 5 turn −0.70 into −0.52;
  - on a seeded cohort, IPW and AIPW land close to the truth and their CIs contain it, while naive
    is clearly off.

### e) DR-learner: this patient's effect, with an interval
- **File:** `diacausal_engine/estimators.py`.
- **What:**
  - Take the cross-fitted AIPW pseudo-outcomes φ and fit a **linear regression of φ on the
    patient's details** (the DR-learner, Kennedy 2023).
  - With robust (HC3) standard errors, this gives a 95% interval for **this** patient:
    `x*ᵀβ ± 1.96·√(x*ᵀVx*)`. We compute it for each option's expected change and for each pairwise
    difference.
  - T-learner and S-learner are built as simpler comparisons.
- **Tests:**
  - PEHE (the error per patient) is small, and smaller than naive;
  - the 95% intervals contain the true effect for most test patients (≥ 85% in the test;
    the benchmark reports the exact rate);
  - lower < estimate < upper, always.

### f) Metrics against the known truth
- **File:** `diacausal_engine/metrics.py`.
- **What:**
  - bias, RMSE, 95% interval coverage, PEHE;
  - **policy regret**: how much worse the option with the best estimate is than the truly best
    option, both chosen only among the options the safety rules and overlap allow;
  - how often the system abstains;
  - **covariate balance**: standardised mean differences before and after weighting.
- **Tests:** tiny made-up arrays with answers worked out by hand.

### g) Benchmark
- **Files:** `diacausal_engine/benchmark.py`, `diacausal_engine/figures.py`.
- **Commands:**
  - `python -m diacausal_engine.benchmark`: 20 repeats × 5,000 patients, plus 2,000 fresh test
    patients per repeat;
  - `--quick`: 3 repeats × 1,500 patients.
- **Saves:**

  | File | What it holds |
  |---|---|
  | `results/benchmark_summary.csv` | The summary numbers |
  | `results/results_table.tex` | A `tabular` for Overleaf `\input{}` |
  | `results/run_info.json` | Seeds, versions, file hashes, run time |
  | `results/figures/overlap.png` | Propensity for each drug, by the drug actually received, with the 0.05 line |
  | `results/figures/love_plot.png` | Balance (SMD) before and after weighting |
  | `results/figures/ate_vs_truth.png` | Naive, IPW and AIPW with 95% CIs against the true value |
  | `results/figures/cate_recovery.png` | DR-learner estimate vs true effect, per patient |
  | `results/figures/calibration.png` | Average predicted vs true effect, by decile |

- I run the full benchmark once and commit `results/`.

### h) Demo (Streamlit)
- **Files:** `diacausal_engine/recommend.py` (the one-patient pipeline) and `demo/streamlit_app.py`.
- **The order is fixed:**
  1. check the inputs;
  2. **apply the safety rules**. An excluded option is never estimated at all;
  3. run the support and overlap checks;
  4. make the DR-learner estimate with its 95% range;
  5. look up the cost. It says "price unavailable" until the Jan Aushadhi prices are confirmed;
  6. run a final check: no dose text, every number has a range, and excluded options have no
     number.
- **Screen:**
  - the intended-use banner at the top;
  - the patient form with units, and the Asian-Indian BMI category;
  - three preset buttons:
    1. a typical patient;
    2. eGFR 40 with past pancreatitis, which shows a red exclusion and amber cautions;
    3. a patient who triggers grey "insufficient evidence";
  - one card per option with its source and rule status;
  - a chart of the estimates with their 95% ranges;
  - a "Why causal?" box with the worked example;
  - the last audit-log line.
- The model is fitted once when the app starts; each answer takes well under a second.

### i) FastAPI endpoint
- **Files:** `diacausal_engine/api.py`, `diacausal_engine/schemas.py`.
- **Endpoints:** `POST /api/v1/recommend` (patient details in; each option's estimate with its 95%
  range, or "insufficient evidence", or excluded with sources; versions; request ID) and
  `GET /api/v1/health`.
- **Behaviour:**
  - Unknown fields are rejected (`extra="forbid"`), and so are values outside plausible ranges.
    Either gives HTTP 422 with a plain-English message.
  - **Every** response, errors included, carries the intended-use sentence.
- **Tests:** these use FastAPI's TestClient.

### j) Tests for everything above, plus CI
- There is a test file per step in `tests/engine/`. On top of those:
  - a sweep over many random patients: no dose text, and an interval on every estimate;
  - excluded options are never estimated;
  - the safety rules run before the estimate;
  - no secrets are in the repo.
- A new `engine` job in `.github/workflows/check.yml` (Linux and macOS, Python 3.12) runs the engine
  tests, the quick benchmark and `pip-audit`.
- `scripts/check_all.py` stays at 43 checks. `docs/TESTING.md` gets the new requirement → test rows.

### Step 3
- **`CLAUDE.md`:** add an "engine" section with the six rules and the commands. The existing
  content stays.
- **`README.md`:** a new top section with the exact MacBook commands. Also fix its outdated
  guardrail bullet list.
- **Pull request:** open one to `main` titled "Causal engine v0.3 for mid-sem", with a plain-English
  summary, what works, and known limitations.

## 4. The two rules tables side by side

`data/rules.csv` is Part 6. `guardrails.v1.yaml` is the chat app's table.

| Part 6 rule | Part 6 says | Chat app (yaml) says | Difference |
|---|---|---|---|
| R01 SGLT2i, eGFR < 45 | EXCLUDE (with a KDIGO note) | G01: do not use below **30**; G02: check first at 30–44; G15: KDIGO info note | Part 6 excludes from 45, the yaml from 30 |
| R02 SGLT2i, type 1 diabetes | EXCLUDE | No rule. The text guard refuses any type 1 question. | Same effect, different mechanism |
| R03 SGLT2i, past DKA | CAUTION | G03: **do not use** (the doctor is asked to decide) | The yaml is stricter |
| R04 DPP-4i, eGFR < 45 | CAUTION (no dose shown) | G09: check first | Same |
| R05 DPP-4i, past pancreatitis | CAUTION | G08: check first | Same |
| R06 DPP-4i, heart failure | CAUTION | G07: check first (saxagliptin/alogliptin notice) | Same action, different source |
| R07 SU, past hypoglycaemia | CAUTION | G10 (severe) and G11 (mild): check first | The yaml splits it by severity |
| R08 SU, age ≥ 65 | CAUTION (team-set cut-off) | G13: age TODO, **refused** | Active only in Part 6 |
| R09 SU, eGFR < 60 | CAUTION (team-set cut-off) | — | Only in Part 6 |
| R10 SU, eGFR < 30 | EXCLUDE (pending review) | G12: check first | Part 6 is stricter |
| — | — | G00: eGFR < 30 → the whole question is out of scope (metformin is contraindicated) | Only in the yaml. The engine's cohort starts at eGFR 30 (metformin label), so such patients get "outside the cohort". |
| — | — | G00b: eGFR missing → abstain | Only in the yaml. The engine makes eGFR a required field. |
| — | — | G04: SGLT2i with recurrent genital or urinary infection → check first | Only in the yaml |
| — | — | G16: SGLT2i info note for heart disease or heart failure | Only in the yaml |

**For Member D and the doctor:** choose one final table. Until then the engine uses Part 6 exactly.
When the chat app starts calling the engine, the stricter of the two actions will apply.

## 5. Where each generator number comes from (draft for `data/params.yaml`)

**What the statuses mean:**
- **CITED:** the value is taken from the source.
- **ASSUMED-DIRECTIONAL:** the direction and rough size follow the source, but the exact number is
  our choice. Say so openly in the viva.
- **TEAM-SET:** our own choice, labelled as such.

| Group | Examples | Source | Status |
|---|---|---|---|
| Prevalence and obesity anchors | diabetes 11.4%, generalised obesity 28.6% (context only) | Anjana et al., *Lancet Diabetes Endocrinol* 2023 (ICMR-INDIAB-17) | CITED |
| BMI and waist cut-offs | overweight ≥ 23, obese ≥ 25 kg/m² | Misra et al., *JAPI* 2009 | CITED |
| Cohort inclusion | eGFR ≥ 30 (metformin can be continued) | FDA Drug Safety Communication on metformin, 2016 | CITED |
| CKD definition | eGFR < 60 | KDIGO CKD definition | CITED |
| Drug effects added to metformin | SGLT2i, DPP-4i and SU each lower HbA1c by roughly 0.6–0.9 points at 6 months | Tsapas et al., *Ann Intern Med* 2020; Palmer et al., *JAMA* 2016 | ASSUMED-DIRECTIONAL |
| South Asian calibration | SGLT2i's average benefit over DPP-4i set to about 2.1 mmol/mol ≈ 0.19 points | Güdemann et al., *Lancet Reg Health Eur* 2026 | ASSUMED-DIRECTIONAL |
| Who benefits more | all three work better at higher starting HbA1c; SGLT2i works less well at lower eGFR | Dennis et al., *Lancet Digit Health* 2022; TriMaster (Shields et al., *Nat Med* 2023) | ASSUMED-DIRECTIONAL |
| Spread of 6-month change | total SD about 0.8 points | Worksheet row 20 (CANTATA-D placebo arm: 0.060 × √181 = 0.81) | ASSUMED-DIRECTIONAL |
| Everything else | age, sex, duration and HbA1c distributions; heart disease, heart failure, hypoglycaemia, DKA and pancreatitis rates; who gets which drug; SU working less well with longer duration; the 0.05 overlap cut-off; the 0.01 weight clip; SMD 0.1 (after Austin 2009) | Team choice; the note says which worksheet row would replace it | TEAM-SET |

Hypoglycaemia risk and weight change are **not** modelled in v0.3. The worksheet marks them "needs
decision".

## 6. How the demo connects to the current UI

- **Now (mid-sem):** the Streamlit demo calls the engine directly in Python. The FastAPI endpoint
  calls the same function. The chat app is untouched and still passes all its tests.
- **October:** wire the engine into the chat app's empty `causal_engine` stage.
  1. `backend/app/pipeline/causal_engine.py` translates the panel's fields: `egfr_ml_min_1_73m2`
     → `egfr`, `past_dka` → `dka_history`, `past_pancreatitis` → `pancreatitis_history`,
     `heart_failure` → `hf`, `past_hypoglycaemia ≠ "none"` → `hypo_history`, `age_years` → `age`.
     It then runs the engine **only on the options the guardrail stage kept** (`ctx.options`), so a
     removed option can never come back.
  2. Add `estimate {value, low, high}`, `evidence` and the model/cohort versions to `OptionResult`,
     in `backend/app/schemas.py` and `frontend/src/lib/contract.ts` together.
  3. AnswerCard and OptionsList draw designs 17 (options compared) and 19 (insufficient evidence).
  4. Pin numpy, pandas and scikit-learn in `backend/requirements.txt`, and copy the engine into the
     Docker image.
  5. Update the tests that today expect "causal_engine: skipped" (`backend/tests/test_chat.py`,
     `test_logging.py`, `scripts/check_all.py:337-342`, `StageList.tsx:31`). Their expectations
     change because the behaviour really changes; no test is weakened.

## 7. Known limitations (say these in the viva)

- **Synthetic data only.** The results show that the *method* recovers a known truth. They do not
  show real-world drug effects.
- **The effect sizes are assumed.** Their direction and rough size follow the cited trials; the
  exact numbers are our choice.
- There is one example drug per class, and all rule sources are US labels. The doctor must confirm
  them for Indian practice.
- We assume every confounder is measured. Nothing tests hidden confounding on real data yet.
- Prices are unconfirmed, so the app shows "price unavailable".
- The DR-learner's interval assumes the effect changes roughly in a straight line with each patient
  detail. The benchmark measures how often the intervals are right.
