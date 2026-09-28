# DiaCausal datasets: what we use, why synthetic, and what real Indian data exists

> Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

For the mid-sem slides and the viva. Every number below comes from a file in the repo or from a
script run on 28 Sept 2026; the pictures are in `docs/midsem/data/`.

## 1. The datasets in one table (slide-ready)

| # | Dataset | Real or synthetic | Size | What it is for | File | Picture |
|---|---|---|---|---|---|---|
| 1 | **DiaCausal synthetic cohort** | Synthetic (India-calibrated) | 5,000 patients per cohort, 20 cohorts in the benchmark | Train and **grade** the causal engine (the true answer is known) | made by `diacausal_engine/cohort.py` from `data/params.yaml` | `01_synthetic_cohort.png`, `02_synthetic_hidden_truth.png` |
| 2 | **Safety rules** | Real (drug labels, KDIGO) | 10 rules | Remove unsafe options **before** any estimate | `data/rules.csv` | `03_safety_rules.png` |
| 3 | **Generator parameters** | Each number labelled CITED / ASSUMED-DIRECTIONAL / TEAM-SET | 117 numbers | Say how the synthetic patients are made | `data/params.yaml` | `04_generator_parameters.png` |
| 4 | **Evidence sources** | Real documents (WHO 2018, 7 US FDA safety notices) | 26 sources listed, 8 texts in the search after the licence check | RAG evidence and explanations | `RAG/sources.csv`, `diacausal_rag/corpus/` | `05_rag_sources.png` |
| 5 | **Evidence test set** | Written by the team | 60 questions (45 answerable, 10 out of scope, 5 dose) | Measure the evidence search | `eval/rag_gold.csv` | `06_rag_gold_questions.png` |
| 6 | **NMB-2017** (new) | **Real Indian data** (CC0) | 7,496 adults, 1,986 with self-declared diabetes | Check that the synthetic patients look like real Indian patients | `data/reference/nmb2017.csv` | `07_real_indian_nmb2017.png`, `real_vs_synthetic.png` |

Regenerate everything: `python scripts/fetch_nmb2017.py`, `python scripts/compare_cohort.py`,
`python scripts/dataset_previews.py` (the last needs `CHROMIUM_PATH` or Playwright's own browser).

## 2. The synthetic cohort, column by column

One row is one adult with type 2 diabetes who is already on metformin and whose HbA1c is still at
or above 7%. The generator gives each one an add-on drug the way doctors tend to, then records
what happened by 6 months.

| Column | Meaning | Unit / values |
|---|---|---|
| `age` | Age | years (30–85) |
| `female` | Sex | 1 = female (45%) |
| `duration_years` | Years since diagnosis | years |
| `hba1c` | HbA1c at the start | % (7.0–13.0) |
| `egfr` | Kidney function; falls with age | mL/min/1.73m² (30–120) |
| `bmi` | Body-mass index; Asian-Indian cut-offs (overweight ≥ 23, obese ≥ 25) | kg/m² |
| `ascvd`, `hf` | Heart disease, heart failure | 1 = yes |
| `hypo_history`, `dka_history`, `pancreatitis_history` | Past low sugar, ketoacidosis, pancreatitis | 1 = yes |
| `low_income` | Cost matters | 1 = yes |
| `ckd` | eGFR < 60 (KDIGO) | 1 = yes |
| `treatment` | Add-on drug given | SGLT2i / DPP4i / SU |
| `y` | **Outcome:** HbA1c change at 6 months | percentage points |
| `weight_change_6m` | Weight change at 6 months | kg |
| `hypo_6m` | Any low-sugar episode by 6 months | 1 = yes |
| `y_true_*`, `e_true_*` … | **Hidden truth** (never shown to the estimators) | — |

### How it is generated (5 steps, `diacausal_engine/cohort.py`)
1. **Draw the patients.** Age, sex, years with diabetes, HbA1c, eGFR (lower in older patients),
   BMI and the history flags, from the distributions in `params.yaml`.
2. **Give each one a drug the way doctors tend to.** A formula makes the choice depend on the
   patient (for example higher HbA1c and BMI → more SGLT2i; low eGFR → less SGLT2i). This is
   *confounding by indication*, the same bias hospital records have, so a simple comparison of
   the three groups gives the wrong answer on purpose.
3. **Work out the 6-month HbA1c change under all three drugs** for every patient: a base effect
   per drug, adjusted for starting HbA1c, eGFR and years with diabetes, plus random noise. The
   directions come from published studies (Tsapas 2020 network meta-analysis, Dennis 2022,
   TRIMASTER 2023).
4. **Keep only the result for the drug each patient got** (`y`). The other two are hidden, just as
   in real life. Only these observed columns reach the estimators (`observed_view()`).
5. **Weight change and low-sugar risk** are made the same way from a separate random stream, so
   adding them did not change a single primary number.

### What the numbers in `params.yaml` rest on (honest count)
| Section | CITED | ASSUMED-DIRECTIONAL | TEAM-SET | Total |
|---|---|---|---|---|
| Generator (how patients are made) | 2 | 15 | 72 | 89 |
| Engine settings (folds, 0.05 overlap rule, …) | 2 | 0 | 16 | 18 |
| Display and context (BMI cut-offs, prevalence) | 5 | 0 | 5 | 10 |
| **All** | **9** | **15** | **93** | **117** |

ASSUMED-DIRECTIONAL means the direction and rough size come from the cited study but the exact
value is ours. TEAM-SET means our choice (many are plausibility limits or method settings). The
loader refuses any number without a source and a status.

## 3. Why synthetic data is valid here, and what it does NOT prove

- In real records you never see what would have happened under the drug a patient did **not** get,
  so no real dataset can tell you whether a causal method got the right answer.
- With a synthetic cohort we **know** the right answer, so we can grade each method. This is how
  causal-inference methods are normally tested (for example the ACIC data challenges and the
  semi-synthetic IHDP benchmark).
- Our result (`results/benchmark_summary.csv`, 20 cohorts × 5,000 patients): the true
  SGLT2i-vs-DPP-4i effect is **−0.211**; the naive comparison says **−0.370** (biased by the
  built-in confounding); AIPW says **−0.209** and its 95% interval contains the truth in 95% of
  cohorts; 9 of 9 refutation checks pass.
- **It does not prove** how much each drug lowers HbA1c in Indian patients. Those effect sizes are
  inputs we set from the literature, not findings.

**What is real today:** the safety rules (drug labels, KDIGO), the evidence and explanations (WHO,
FDA), and the method. **What is synthetic:** the effect numbers on the option cards.

## 4. Real Indian diabetes datasets (checked 28 Sept 2026)

The key fact for the panel: **no public Indian dataset records which add-on drug each patient got
together with their HbA1c months later.** That pairing is what a causal engine needs. The
datasets below are real and useful for other things.

| Dataset | Who / where | Size | Useful variables | Drug choice + follow-up HbA1c? | Access | How we use it |
|---|---|---|---|---|---|---|
| **NMB-2017** (Nagarathna et al., *Diabetes Res Clin Pract* 2020) | Nationwide Indian survey of adults at high risk of type 2 diabetes | 7,496 (1,986 self-declared diabetes) | age, sex, state, height, weight, waist, family history, activity, **HbA1c** | No | **Open, CC0 1.0**, Mendeley Data doi:10.17632/twp8xw6p25.1 | **In the repo** as a realism check (section 5) |
| **LASI Wave 1** (IIPS, 2017–18) | Nationally representative, adults 45+ | ~66,000 with dried-blood-spot biomarkers | **HbA1c** (dried blood spot), self-reported diabetes and treatment, BMI, BP | No (one wave, no drug class) | Free request form with ID at IIPS, academic use only | Next calibration step for age, BMI and HbA1c (needs the request) |
| **NFHS-5** (2019–21) | Nationally representative households | ~700,000 women and ~100,000 men | random blood glucose, self-reported diabetes and whether on medicine, BMI | No | Registration with the DHS Program | Prevalence and context only |
| **CARRS** (Chennai + Delhi cohort) | Urban adults 20+ | 12,271, followed every 2 years | HbA1c, glucose, risk factors | Some follow-up, but not add-on drug choice | By request to the investigators | Possible future collaboration |
| **ICMR-INDIAB** | National prevalence study | ~113,000 | glucose, HbA1c subset | No | Not public (published tables only) | Already cited in `params.yaml` for context |
| **Freedom from Diabetes clinic, Pune** (PMC11937334) | 18,950 T2D patients in a lifestyle programme | 18,950 | HbA1c, glucose-lowering medicines | Partly (medicines listed, not an add-on comparison) | "On reasonable request" to the authors | Candidate partner for real-data validation |

Not Indian, and so not used: the **Pima** dataset (Pima Native American women in Arizona, no drug
or outcome data); the Bangladesh and Iraq diabetes sets on Mendeley Data; the Turkish glycaemic-control set.

## 5. Real vs synthetic: the realism check

`python scripts/compare_cohort.py` → `docs/midsem/data/real_vs_synthetic.png` and `.csv`.
It compares our cohort with NMB-2017 adults who have diabetes and HbA1c ≥ 7% (n = 1,010), the
closest real match to "on metformin, not at target".

| | Synthetic (seed 0, n = 5,000) | NMB-2017, diabetes + HbA1c ≥ 7% (n = 1,010) |
|---|---|---|
| Age, mean (SD) | 55.0 (9.9) | 53.5 (9.8) |
| BMI, mean (SD) | 26.4 (4.1) | 26.6 (4.3) |
| BMI ≥ 25 (Asian-Indian obese) | 65% | 60% |
| Female | 45% | 41% |
| HbA1c, mean (SD) | 8.6 (1.0) | 9.2 (1.8) |

**What it shows:** age, BMI and sex match real Indian adults with diabetes closely. HbA1c is
**lower and narrower** in our cohort than in the real data (real patients have more very high
values, up to 14%). This is a concrete improvement we can make: widen the HbA1c distribution
(`generator.covariates.hba1c` in `params.yaml`) and rerun the benchmark, with NMB-2017 as the
cited source. Note that NMB-2017 did not ask about metformin, so it is a rough match, not an
exact one.

## 6. How it could be used in a real hospital

1. **Data:** an extract from a hospital's records of adults on metformin who started SGLT2i, DPP-4i
   or a sulfonylurea: baseline details plus HbA1c 3–9 months later. Needs the hospital ethics
   committee (IEC), de-identification and India's DPDP Act 2023 (guide's partner hospital).
2. **Same code:** the extract has the same columns as `observed_view()`, so it replaces the
   synthetic cohort with no change to the estimators.
3. **Checks without a known truth:** the overlap rule (propensity < 0.05 → "insufficient
   evidence"), refutation tests and E-values already built, plus agreement of the average effects
   with published trials ("target trial emulation").
4. **Silent pilot:** doctors see the suggestion but decide as usual; record agreement and safety flags.
5. **Regulation:** use in routine care would make it software as a medical device (CDSCO). Until
   then it stays a research prototype; the clinician decides.

**One line for the panel:** "We proved the method where the truth is known; the next step is the
same code on ethically approved hospital records, checked against trial results."

## 7. How much is implemented: about 64% of the final-year project

Weights are the team's judgement of each part's share of the whole year; each "% done" points to
a file or test.

| Part | Weight | Done | Evidence |
|---|---|---|---|
| Chat app: UI, guards, sign-in (CAPTCHA + MFA), patient panel, guardrails, voice, Docker | 20% | ~95% | 392 backend + 238 frontend tests; `check_all` 43 checks |
| Causal engine (cohort, safety rules, propensity, IPW / AIPW / matching, DR-learner, secondary outcomes, benchmark, refutation) | 25% | ~90% | 150 engine tests; `results/` (9 of 9 refutation checks). Missing: real-data validation |
| RAG (sources, hybrid search, abstention, explanations, citation checker, 60-question evaluation) | 20% | ~75% | 33 RAG tests; `results/rag_eval_summary.csv` (recall@5 0.933, abstention 0.800, citation precision 1.000, 0 dose leaks). Missing: medical embedding model, reranker, doctor review, RSSDI source |
| Joining engine + RAG + LLM into the chat app | 15% | ~10% | Stages and contract exist; 3 of 6 stages still return "skipped" |
| Clinician evaluation (25 vignettes, SUS) | 10% | ~20% | Pack ready in `eval/`; not yet run with doctors |
| Report and paper | 10% | ~40% | Mid-sem report done; paper not started |
| **Total** | 100% | **≈ 64%** | 0.20×95 + 0.25×90 + 0.20×75 + 0.15×10 + 0.10×20 + 0.10×40 |

Far past the 25% asked for mid-sem: every core part works and is tested on its own. What is left:
join them in the chat app, the doctor review and usability study, a better search model, the
real-data step above, and the paper.
