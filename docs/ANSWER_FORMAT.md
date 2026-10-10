# The answer card (AnswerCardV1), evidence levels and the abstain card

> Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

P24. The format of every answer DiaCausal shows, from `POST /api/v1/ask` (`diacausal/output/formatter.py`) and from the website
(`web/card.js` builds the same object, `web/app.js` draws it). Source: docs/PLAN_2026-10.md section 8.11 and
design/screens-v2/handoff/HANDOFF.md section 7. The contract is `AnswerCardV1` in `diacausal/api/schemas/card.py`
(`openapi.json`, `web/types.d.ts`); tests/web checks that every card the website builds validates against it.

## What the card shows, in order

| # | Part | Field(s) | Comes from | Rule |
|---|---|---|---|---|
| 1 | Question and patient | `question`, `patient_summary` ("52 y, M, HbA1c 8.4%, eGFR 88, BMI 27 (category)") | the request | Age, sex, HbA1c, eGFR, BMI and its Asian-Indian category only; no identifier |
| 2 | Safety checks | `excluded`, `cautions` (each with `rule_id` and `source`) | `data/rules.csv`, applied **before** any estimate | One card per option: Safe to consider · Check first · Do not use |
| 3 | Finding | (computed from `effects`) | the causal engine | A **leader** only when its 95% interval of the difference vs DPP-4i excludes 0, and only "on HbA1c". Otherwise "No clear difference in HbA1c for this patient" |
| 4 | Effects table | `effects[]`: `hba1c_change` (with 95% interval), `vs_comparator`, `hypo_risk_pct` (any hypoglycaemia by 6 months, %), `weight_change_kg`, `cost_label` (₹/month or "price unavailable"), `status`, `caution` | the causal engine (`CausalOutputV1`), **never the language model** | An option removed by a rule: "Not estimated — removed by rule R.. before estimation". An Insufficient option: no number at all |
| 5 | Evidence level | `evidence_levels[]`: `level` and its one-line `reason` | `diacausal/causal_inference/evidence_level.py` | Moderate · Low · Insufficient; never High (below) |
| 6 | Trade-offs | (from `effects`) | the engine | Weight, any hypoglycaemia and cost side by side, never a ranking. With no leader they come **before** the table (screen 21) |
| 7 | What drives this estimate | `drivers`: per option, its comparison against DPP-4i, up to 3 `DriverV1` (`feature`, `value`, `contribution` in HbA1c points, `ci95`) | exact SHAP of the causal engine's own estimate (P25, `diacausal/xai/cate_shap.py`; `web/engine.js` `explainEffect`) | Only for options shown with an estimate (and only when DPP-4i has one). A driver is shown only when the 95% interval of its contribution excludes zero, largest first; none clear -> "No single patient detail clearly drives this estimate." An "all other details together" row (with its own interval) makes the rows add up to the estimate. "The estimate is larger or smaller for patients with these details ... They are not causes." |
| 8 | Abstain card | `abstain[]`: `option`, `why`, `propensity`, `threshold` | evidence level Insufficient | Exactly the text below |
| 9 | Cited evidence | `claims[]` (at most 4, each with `citations`: chunk ID and label) and the sources list | retrieval (licence-cleared passages, shown verbatim on request) | Quoted sentences, not advice |
| 10 | Model record | `mode`, `question_context`, `limitations`, `fallback_used`, `failed_checks`, `fallback_reason`, `dropped_claims` | P21–P23 | The website never runs a model: always `template`, no fallback |
| 11 | The end | `intended_use`, `decision` | fixed | The intended-use sentence, verbatim, then "The clinician decides." as the very last line (P27) |

The comparator is DPP-4 inhibitor (`comparator`). Hypoglycaemia is the engine's own secondary outcome (% with its 95% interval), not a
category from a table.

## The three screens

| Screen | When | Headline |
|---|---|---|
| 17 — options compared, leader shown | at least one difference vs DPP-4i has a 95% interval that excludes 0 | "Three options compared for this patient"; the finding names the option that lowers HbA1c more and says "This is a difference on HbA1c only." |
| 21 — no clear difference | every difference vs DPP-4i includes 0 (or DPP-4i itself has no estimate) | "Three options compared for this patient"; "No clear difference in HbA1c for this patient"; trade-offs first |
| 19 — insufficient evidence | no option has an estimate (outside the cohort, type 1 diabetes, every option without overlap, or the search for the question found nothing) | "Insufficient evidence — no comparison shown"; why, what to do instead, then the abstain card for each option |

## Evidence level (plan 8.11)

The cut-offs are in `data/params.yaml`, group `evidence_level`, all **TEAM-SET** (Members A and D and the collaborating doctor to
review). Nothing is typed in the code; `web/engine.js` reads the same numbers from `web/model.json`.

| Level | When (checked in this order) |
|---|---|
| Insufficient | propensity **below** 0.05 (`insufficient_propensity_below`, the same number as `engine.overlap_min_propensity`), or the 95% interval **wider than** 1.5 points (`insufficient_width_above` = `engine.max_interval_width`), or the retrieval abstained |
| Low | interval wider than 1.0 (`low_width_above`), or propensity below 0.10 (`low_propensity_below`), or fewer than 2 cited passages (`low_citations_below`) |
| Moderate | everything else |
| High | **never**: every estimate comes from a synthetic cohort. `high_enabled: false`; the code refuses to run if it is switched on |

- **Width** = `ci_high − ci_low` of the 6-month HbA1c change, as the engine prints it (3 decimals). "Below" and "wider than" are strict:
  propensity exactly 0.05 is Low, exactly 0.10 is Moderate; width exactly 1.0 is Moderate, exactly 1.5 is Low.
- **Cited passages** of an option = the passages on the card that name it (its class word, e.g. "sglt2", or its example molecule).
  For a question: the passages retrieved for it. For "Compare the three options" (no question, website only): each option's own search
  (at most 2 passages). The benchmark runs no search, so it leaves this part of the rule out.
- **Worked example:** SGLT2i from −1.2 to −0.6 (width 0.6), propensity 0.31, 2 cited passages → **Moderate**: "Moderate: the 95% interval
  is 0.60 points wide, propensity 0.31, 2 cited passages." The same option with propensity 0.07 → **Low**: "Low: propensity 0.07 (below 0.1)."
- An option the rules removed has **no** level: the table says "Not assessed".
- An Insufficient option shows **no estimate**, even if the engine made one (that happens only when the retrieval abstained).

## The abstain card (exactly as in section 8.11)

```
Insufficient evidence for: DPP-4i
Why: too few similar patients received this option in the reference data (propensity 0.03; threshold 0.05).
What you can still see: cited guideline passages (Investigate tab).
The clinician decides. Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.
```

The "Why" line names the part of the rule that applied:

| Cause | Why |
|---|---|
| no overlap | too few similar patients received this option in the reference data (propensity P; threshold 0.05) |
| interval too wide | this patient's 95% interval is wider than 1.5 points, so no useful estimate can be shown |
| outside the cohort | this patient is outside the range of the reference data (age = 88 is outside the cohort's range (30 to 85)) |
| the search found nothing | no licence-cleared passage answers this question |

So that the card can quote the propensity, the engine now puts it on an option it abstained on for overlap (`confidence.propensity`,
with `method` saying no estimate was made). It never adds an estimate to such an option.

## Does the level mean anything? (benchmark, `results/evidence_level_coverage.csv`)

`python -m diacausal.causal_inference.benchmark` (20 synthetic cohorts × 5,000 patients, 2,000 test patients each): for every test
patient and every option the rules leave, the level of the DR-learner's estimate and whether its 95% interval contains the **true**
6-month change.

| Level | Patient-option pairs | Share | Interval contains the truth | Mean interval width |
|---|---:|---:|---:|---:|
| Moderate | 109,612 | 92.6% | 94.5% | 0.25 points |
| Low | 6,955 | 5.9% | 93.8% | 0.40 points |
| Insufficient (withheld; never shown) | 1,852 | 1.6% | 93.0% | 0.69 points |

Coverage is higher for Moderate than for Low, and lowest for what is withheld, as plan 8.11 asks; but the differences are small (about
one percentage point), and every level is close to the nominal 95%. On this synthetic cohort the level mostly tracks the propensity and
the width of the interval, not a large loss of accuracy. That is an honest result for the report: the level is a caution about how
much data stand behind an estimate, not a promise about its accuracy.

## Where it lives

| What | Python | Website |
|---|---|---|
| The rule, the reason, the abstain card | `diacausal/causal_inference/evidence_level.py` | `web/engine.js` (`evidenceLevel`, `abstainWhy`, `abstainCard`, `countCitations`), same text (tests/web compares them) |
| The card | `diacausal/output/formatter.py` (`build_card`, `evidence_levels`, `abstain_notices`) | `web/card.js` (`build`, `leaders`) |
| Drawing it | — | `web/app.js` (`renderCard`): Patient Details (Compare, and a question with the patient filled in) and Investigate (with the patient filled in) |
| Tests | `tests/engine/test_m_evidence_level.py`, `tests/orchestrator/test_evidence_levels_in_the_card.py`, `tests/engine/test_g_benchmark.py` | `tests/web/test_web.py` (parity, contract, screens 17, 21 and 19 at 1280 and 390 px) |
