# Analysis tab: the three panels (for the report and the slides)

> Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

Written by `python -m diacausal.causal_inference.analysis_panels` from `results/xai_ablation.csv`, `results/rag_eval_summary.csv` and `results/llm/bench_summary.csv`. Do not edit by hand: a test rebuilds it. **Synthetic benchmark**: it tests whether the methods recover a planted truth, not real-world drug effects.

## From records to causal estimates

B adjusts for why each patient received their drug instead of only learning from the records as A does: compared with A, its regret is 16% lower (not a clear difference), the average effect has 88% smaller bias, and it gives numbers for 12.8% of the patient-option pairs where similar patients are too few instead of 100.0%; its error on each patient's effect (PEHE) shows no clear improvement on 3 of 3 comparisons. The naive comparison of group averages has a regret of 0.0633 (A 0.0126, B 0.0106) and its interval contains the true SGLT2i vs DPP-4i effect for 13.9% of patients (B 94.4%).

| Measure | A → B |
|---|---|
| Bias of the average effect, SGLT2i vs DPP-4i | 88% smaller bias; 95% interval A excludes 0, B includes 0 |
| Patients whose true effect lies in the 95% interval, SGLT2i vs DPP-4i | A gives no interval, so only B and the naive comparison can be checked against 95% |
| Regret: extra HbA1c vs the truly best allowed drug | 16% lower: not a clear difference; paired 95% interval of B minus A -0.0064 to +0.0024 |
| Error of the predicted HbA1c change (RMSE) | 22% lower; paired 95% interval of B minus A -0.0255 to -0.0161 |
| Picks the truly best allowed drug | 1.6 points higher (2% more): not a clear difference; paired 95% interval of B minus A -1.8 points to +5.0 points |
| Numbers given where similar patients are too few | 87.2 points lower (87% fewer) |
| Error of each patient's effect (PEHE), SGLT2i vs DPP-4i | 1% higher: no improvement; paired 95% interval of B minus A -0.0090 to +0.0119 |
| Error of each patient's effect (PEHE), Sulfonylurea vs DPP-4i | 13% higher: no improvement; paired 95% interval of B minus A +0.0011 to +0.0261 |
| Error of each patient's effect (PEHE), SGLT2i vs sulfonylurea | 2% lower: not a clear difference; paired 95% interval of B minus A -0.0150 to +0.0097 |

Source: `results/xai_ablation.csv`, `results/benchmark_summary.csv`. Mean over 20 synthetic cohorts with its 95% interval. The naive comparison uses the plain average HbA1c change in each drug group of the records for every patient. C and D do not change B's estimate, so they are not repeated here.

## What C adds

C splits B's estimate into one contribution per patient detail that adds up to the estimate (largest error 2.7e-16) and shows only the details whose 95% interval excludes zero; 11% to 18% of the drivers it shows are not true effect modifiers, and A's top features match the true modifiers more often than C's on 2 of 3 comparisons.

| Measure | A · XAI only | C · B + exact SHAP |
|---|---|---|
| Contributions add up to the estimate (largest error), SGLT2i vs DPP-4i | not applicable | 2.1e-16 |
| Contributions add up to the estimate (largest error), Sulfonylurea vs DPP-4i | not applicable | 2.7e-16 |
| Contributions add up to the estimate (largest error), SGLT2i vs sulfonylurea | not applicable | 1.9e-16 |
| Top features that are true effect modifiers, SGLT2i vs DPP-4i | 95.0% (95% CI 87.8% to 102.2%) | 87.5% (95% CI 77.1% to 97.9%) |
| Top features that are true effect modifiers, Sulfonylurea vs DPP-4i | 92.5% (95% CI 83.9% to 101.1%) | 97.5% (95% CI 92.3% to 102.7%) |
| Top features that are true effect modifiers, SGLT2i vs sulfonylurea | 98.3% (95% CI 94.8% to 101.8%) | 78.3% (95% CI 69.2% to 87.5%) |
| Shown drivers that are not true effect modifiers, SGLT2i vs DPP-4i | A shows no drivers | 18.1% (95% CI 5.7% to 30.4%) |
| Shown drivers that are not true effect modifiers, Sulfonylurea vs DPP-4i | A shows no drivers | 10.9% (95% CI 2.8% to 19.0%) |
| Shown drivers that are not true effect modifiers, SGLT2i vs sulfonylurea | A shows no drivers | 16.8% (95% CI 9.1% to 24.6%) |

Source: `results/xai_ablation.csv`. Drivers describe the estimate, never a cause. A's SHAP explains a prediction model, not an effect. An interval past 100% is the t-interval of the 20 cohorts as the ablation wrote it (most cohorts score 100%), not a value above 100%.

## What D adds

D finds cited passages and writes the explanation, and checks every draft before it is shown: on the 60 gold questions 100% of the quoted sentences were supported by their cited passage and 0 answers contained dose text; the local model's drafts failed a check on 75% of the 20 golden questions, so the template answered instead.

| Measure | Value | Measured on | Source |
|---|---|---|---|
| Quoted sentences supported by their cited passage (citation precision) | 100.0% | 60 gold questions, template writer | results/rag_eval_summary.csv |
| Answers that contained dose text (dose leaks) | 0 of 60 | 60 gold questions, template writer | results/rag_eval_summary.csv |
| Local-model drafts whose every number is in the causal output | 30.0% | 20 golden questions, local model (candidate_a) | results/llm/bench_summary.csv |
| Local-model drafts replaced by the template after a failed check | 75.0% | 20 golden questions, local model (candidate_a) | results/llm/bench_summary.csv |

Source: `results/rag_eval_summary.csv`, `results/llm/bench_summary.csv`. Fixed question sets, not synthetic cohorts, so these values have no interval.
