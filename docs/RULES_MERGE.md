# Merging the three rule sources into `data/rules.csv`

> Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

Written 4 October 2026 (Member D's area; the doctor still has to review every row). **Rule used:** where two sources
disagree, the **stricter action wins until the doctor decides** (`EXCLUDE` or "do not use" or "abstain" beats `CAUTION` or
"check first", which beats information only). Nothing was relaxed anywhere.

## 1. The three sources

| Source | What it is | Rules | Used by |
|---|---|---:|---|
| **A** `data/rules.csv` | The engine's table (Part 6 of `docs/02_Causal_Engine_Build_Guide.md`). One test per row. Each row: one option, one patient field, one comparison, `EXCLUDE` or `CAUTION`, a source. | R01 to R10 (now R01 to R11) | the engine, the website (`web/model.json`), the benchmark |
| **B** `backend/app/clinical/guardrails.v1.yaml` | The chat app's draft table (v1.0.0-draft, "not reviewed"). Richer: compound conditions, patient-level abstain, information-only rules, severity grades. | 15 | the chat app only (`backend/`, unchanged) |
| **C** `legacy/causal_engine/guardrails.py` | The older 2-arm research code, numbers typed in code, cited to ADA Standards and IDF 2025 (neither is licence-cleared). Frozen. | 7 | nothing active |

## 2. What changed in `data/rules.csv`

Only two things, the only places where another source was stricter than A **and** the CSV format can hold the rule:

| Row | Before | After | Why |
|---|---|---|---|
| **R03** SGLT2i, history of ketoacidosis | `CAUTION` | **`EXCLUDE`** | B (G03) says do not use; A said caution. The stricter wins. B itself asks the doctor: "is do_not_use right, or check_first?" Status stays UNVERIFIED (label section to confirm). |
| **R11** (new) DPP-4i, eGFR below 30 | none | **`EXCLUDE`**, VERIFIED | B (G00) and C (`metformin_egfr_30`) both say that below eGFR 30 metformin is contraindicated, so "adding to metformin" does not apply (FDA Drug Safety Communication, 8 Apr 2016). SGLT2i is already excluded at that eGFR by R01 and SU by R10; the DPP-4i was the only option left (it said "insufficient evidence" because the cohort starts at 30). Now all three are excluded and the engine answers NOT_APPLICABLE with the reason. |

Everything else in A is unchanged, byte for byte (`R01`, `R02`, `R04` to `R10`).

## 3. Every rule of B and C, and what happened to it

`=` same strength as A; `A stricter` means A already has the stricter action, nothing to do.

### Source B (chat app), 15 rules

| B rule | Meaning | Counterpart in A | Difference | Resolution |
|---|---|---|---|---|
| G00 metformin eGFR < 30 | abstain (whole question) | R01 + R10 + **R11** | A had no rule for DPP-4i | **merged**: R11 added; all options excluded = abstain |
| G00b missing eGFR | abstain | engine rule check | `applies()` raises "needs egfr" (fails closed); the patient form requires eGFR | already covered, no row |
| G01 SGLT2i eGFR < 30 | do not use | R01 (eGFR < 45, exclude) | A stricter (wider) | A stays |
| G02 SGLT2i 30 <= eGFR < 45 | check first | R01 (exclude) | A stricter | A stays |
| G03 SGLT2i past ketoacidosis | do not use | R03 (was caution) | **B stricter** | **merged**: R03 now `EXCLUDE` |
| G04 SGLT2i recurrent genital/urinary infection | check first | none | needs a patient field the engine does not have (`recurrent_genital_or_urinary_infection`) | **not merged** (needs a new field in the patient form, `PatientIn`, `PatientV1`, the website and `FIELDS`); stays in B |
| G07 DPP-4i heart failure | check first | R06 (caution) | = | A stays (B's text also says avoid saxagliptin/alogliptin) |
| G08 DPP-4i past pancreatitis | check first | R05 (caution) | = | A stays |
| G09 DPP-4i eGFR < 45 | check first | R04 (caution) | = | A stays |
| G10 SU past severe hypoglycaemia | check first | R07 (caution, any past hypoglycaemia) | = (A has no severe/mild grading) | A stays; B asks the doctor whether severe should become do-not-use |
| G11 SU past mild hypoglycaemia | check first | R07 | = | A stays |
| G12 SU eGFR < 30 | check first | R10 (exclude) | A stricter | A stays |
| G13 SU older adult | check first, age `TODO_AGE` | R08 (age >= 65, caution) | B is unfinished (the loader refuses it) | A stays |
| G15 SGLT2i with CKD, eGFR >= 20 | information only (kidney/heart protection) | none (R01's message mentions it) | action INFO and fields `ckd` are not in the CSV | **not merged**: information, not an eligibility rule |
| G16 SGLT2i with ASCVD or heart failure | information only | none | action INFO, field `established_ascvd` not in the CSV | **not merged**: information, not an eligibility rule |

### Source C (legacy research code), 7 rules

| C rule | Meaning | Counterpart | Resolution |
|---|---|---|---|
| `metformin_egfr_30` | VETO below eGFR 30 | R11 (+ R01, R10) | **merged** (same as G00) |
| `sglt2i_egfr_45` | WARNING at 30 <= eGFR < 45 | R01 (exclude) | A stricter, A stays |
| `out_of_distribution` | warning if a patient is outside the training ranges | the engine's overlap and support check (`support_check`, `insufficient_evidence`) | not a drug rule; **not merged** |
| `effect_too_small` | caution if the estimated effect is under 0.3 points | none | depends on the estimate, so it cannot run before it; **not merged** |
| `predicted_harm` | warning if the estimated effect is -0.3 or worse | none | depends on the estimate; the engine already shows the 95% interval and abstains when too wide; **not merged** |
| `severe_hyperglycaemia` | caution at baseline HbA1c >= 10 | none | field `hba1c` is not one of the rule fields, and the cited sources (IDF 2025, ADA Standards) are not licence-cleared; **not merged** |
| `cvd_indication` | information only | G16 | information only; **not merged** |

## 4. What this does *not* do

- **`backend/app/clinical/guardrails.v1.yaml` is still the chat app's own table.** The chat app (`backend/`) is unchanged: it
  does not read `data/rules.csv`. Making the chat app read the CSV means a loader change and a new test set; it is only worth
  doing if the chat app stays in the project (restructure step 10 may move it to `legacy/`). Until then
  `tests/engine/test_b_guardrails.py` fails if the CSV ever becomes weaker than B for any rule listed above, and fails if a
  new rule is added to B without being merged or listed here with a reason.
- **Five rules need a schema change** to be merged properly: compound conditions (G02 as a range, G15, G16), the information
  action, severity grades (G10, G11), and the new patient fields (G04, G15, G16). Each is a decision for the team and the
  doctor, not something to add silently.

## 5. For the doctor to decide (not Claude)

1. R03: keep **exclude** for a history of ketoacidosis, or go back to **caution**?
2. R11: confirm that the engine should treat eGFR below 30 as "adding to metformin does not apply".
3. R10 and R09 (SU, eGFR below 30 and below 60) and R08 (age 65): still team-set cut-offs, as before.
4. Whether G04, G15 and G16 should get their own fields and rows.

## 6. What this change regenerated

`web/model.json` (the website's copy of the rules), `web/results.json` and `results/` (the benchmark chooses among the options
the rules allow, so its policy numbers can move), and the numbers that quote them. The site needs a redeploy to show them
(docs/DEPLOY.md section 9).
