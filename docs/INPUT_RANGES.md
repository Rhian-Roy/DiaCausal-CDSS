# Patient input ranges (API v1)

> Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

Source: section 8.2 of [docs/PLAN_2026-10.md](PLAN_2026-10.md). **Status: TEAM-SET plausibility bounds.**
They only catch typing errors (an HbA1c of 45, an age of 5). They are **not clinical thresholds**: those live
only in `data/rules.csv`. `diacausal/api/schemas/patient.py` (`PatientV1`) uses exactly these bounds, and
`tests/contract/test_ranges.py` fails if this table and the code ever differ.

| Field in `PatientV1` | Meaning | Unit | Required | Allowed range | Used by |
| --- | --- | --- | --- | --- | --- |
| `age` | Age | years (whole number) | Yes | 18–100 | Model; scope guard (adults only) |
| `sex` | Sex | `F` or `M` | Yes | — | Model |
| `duration_years` | Diabetes duration | years | Yes | 0–60 | Model |
| `hba1c_pct` | HbA1c | % | Yes | 4.0–20.0 | Model |
| `egfr` | eGFR | mL/min/1.73m² | Yes | 5–150 | Rules and model |
| `bmi` | BMI | kg/m² | Yes | 12–60 | Model; Asian-Indian classes: normal 18.5–22.9, overweight 23–24.9, obesity 25 or more |
| `waist_cm` | Waist | cm | No | 50–200 | Display only; abdominal obesity at 90 cm or more (men), 80 cm or more (women) |
| `ascvd` | Established heart disease | yes/no | Yes | — | Rules and explanation |
| `heart_failure` | Heart failure | yes/no | Yes | — | Rules and explanation |
| `ckd` | Kidney disease | yes/no | Yes | — | Rules and explanation (the engine has no CKD input; the API carries it for the explanation) |
| `past_hypo` | Past hypoglycaemia | yes/no | Yes | — | Rules |
| `past_dka` | Past diabetic ketoacidosis | yes/no | Yes | — | Rules |
| `past_pancreatitis` | Past pancreatitis | yes/no | Yes | — | Rules |
| `type1` | Type 1 diabetes | yes/no | Yes | — | Rules (type 1 is out of scope) |
| `on_metformin` | Currently on metformin | yes/no | Yes | must be yes | Scope guard (the API accepts either answer; the guard blocks "no") |
| `cost_concern` | Cost a major concern | yes/no | No | — | Shows ₹/month prominently |
| `glucose_mg_dl` | Fasting or post-meal glucose | mg/dL | No | 40–600 | **Not used in the estimate** |

No dataset upload: a single-patient form fits the frozen decision, and bulk upload is future work.

## Today's engine and website ranges (for comparison)

`data/params.yaml` (`display.input_ranges`) is what `diacausal_engine/schemas.py` and the website enforce today.
Every bound above sits **inside** the engine's, so a `PatientV1` is never rejected later by the engine
(`tests/contract/test_ranges.py` checks this). Aligning `params.yaml` and the website to this table is a
separate, small task.

| Field | This table | Engine today |
| --- | --- | --- |
| age | 18–100 | 18–110 |
| duration_years | 0–60 | 0–80 |
| hba1c | 4–20 | 4–20 |
| egfr | 5–150 | 0–150 |
| bmi | 12–60 | 12–70 |

## Field names

`PatientV1` uses the names in section 8.4 (`hba1c_pct`, `heart_failure`, `past_hypo`, `type1`, `cost_concern`,
sex `F`/`M`). The engine keeps its own names (`hba1c`, `hf`, `hypo_history`, `t1d`, `low_income`, sex
`female`/`male`); `to_engine_patient()` in `patient.py` converts, and a test checks that every valid `PatientV1`
becomes a valid engine `PatientIn`.
