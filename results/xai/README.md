# results/xai: version A, the XAI-only baseline

> Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

**Synthetic benchmark. Version A is a baseline for the Analysis tab; it is never shown to a doctor and never connected to the
website or the API.** Made by `python -m diacausal.xai.baseline` (about 2.5 minutes; needs `requirements-xai.txt`). Details and
the design: `docs/XAI_PLAN.md` section 5; the metrics: section 6.

| File | What it holds |
|---|---|
| `baseline_metrics.csv` | one row per metric and comparison: `version, metric, comparison, mean, ci_low, ci_high, n_reps` (mean over 20 replicates of 5,000 patients with a 95% t-interval; same shape P26 uses for versions A to D) |
| `baseline_metrics_quick.csv` | the same for `--quick` (3 replicates of 1,500): a test re-runs it to catch any drift in the code |
| `shap_A.csv` | `global` rows: mean abs SHAP of each comparison per feature; `preset` rows: the SHAP of each preset and comparison (the 12 features plus the drug column; the rows add up to the estimated effect) |
| `lime_stability.csv` | 10 LIME seeds for each preset and comparison: top-3 overlap between runs and the spread of the top weight |
| `beeswarm_A.png`, `waterfall_A_*.png`, `lime_stability_A.png` | the figures |
| `run_info.json` | what was run (sizes, seeds, shap and lime versions, `params_sha`, `rules_sha`) and each preset's allowed options and pick |

How to read the metrics: `pehe_*` is the error of the patient-level effect (equal to the benchmark's S-learner, because it is the
same model); `pehe_thin` is the same on patients whose smallest TRUE propensity is below 0.05 (version A answers them; version B
abstains); `abstention_rate` is 0 by design, `excluded_by_rules_rate` is the share of (patient, option) pairs the safety rules remove;
`modifier_precision_at_k` is the share of the top-k SHAP features (k = number of true modifiers) that really modify the effect;
`shap_lime_*` is the agreement between the two explainers; `drug_columns_share` is the share of an effect's SHAP carried by the
drug columns, which only reflect the prescribing mix.

Options that the safety rules remove are neither predicted nor explained (as in version B): for the eGFR 40 and the older preset
only SU versus DPP-4i is shown.
