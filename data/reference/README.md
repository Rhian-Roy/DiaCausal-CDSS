# Real reference data (not used by the engine)

> Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

## nmb2017.csv

- **What:** NMB-2017, a nationwide Indian cross-sectional survey of adults at high risk of type 2
  diabetes. 7,496 rows; 1,986 said they have diabetes. Columns: patient_id (the survey's own
  number, not an identifier), zone, state, district, age, gender, waist_cm, height_cm, weight_kg,
  diabetes_self_declared, diabetes_father, diabetes_mother, moderate_activity, vigorous_activity,
  daily_physical, hba1c (%).
- **Source:** Nagarathna R, Patil SS, Nagendra H, Rajesh SK, Venkatrao M, Singh A. "A composite of
  BMI and waist circumference may be a better obesity metric in Indians with high risk for type 2
  diabetes: an analysis of NMB-2017, a nationwide cross-sectional study." *Diabetes Research and
  Clinical Practice* 2020; doi:10.1016/j.diabres.2020.108037.
- **Data:** Mendeley Data, doi:10.17632/twp8xw6p25.1, published 24 Feb 2020, licence **CC0 1.0**
  (public domain; we cite it anyway). The data are published as a 640-page PDF;
  `scripts/fetch_nmb2017.py` downloads it (SHA-256 checked), extracts both column blocks and
  checks they line up page by page. Checked 28 Sept 2026.
- **Limits:** self-declared diabetes; no drug, no metformin status, no follow-up HbA1c; a few rows
  have implausible heights or weights (BMI is left blank for those in `scripts/compare_cohort.py`).
- **Use in DiaCausal:** only `scripts/compare_cohort.py`, to check that the synthetic cohort's
  age, BMI, sex and HbA1c look like real Indian adults with diabetes (docs/midsem/DATASETS.md §5).
  The causal engine never reads this folder (tests/engine/test_a_cohort.py checks this): it
  trains and is graded on the synthetic cohort, whose true effects are known.
