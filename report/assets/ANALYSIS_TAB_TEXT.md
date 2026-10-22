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

## When confounding is stronger

With the drug choice depending 1.5 and 2 times as strongly on the patient's details, the share of patients with too few similar patients grows from 4.3% to 42.9%, B withholds 4.2% to 24.8% of the options, and B's intervals keep containing the true effect (91.2% to 98.1% of patients) while the naive comparison's fall to 21.1%; but B does not pull ahead of A: of 27 paired comparisons (3 multipliers x the measures with a paired interval, not counting the numbers B withholds), B is clearly better on 0, clearly worse on 2, and shows no improvement or no clear difference on the other 25.

| Measure | Drug choice x1 (today's data) | Drug choice x1.5 | Drug choice x2 |
|---|---|---|---|
| Patients with too few similar patients (smallest true propensity below 0.05) | 4.3% | 23.4% | 42.9% |
| Bias of the average effect (absolute), SGLT2i vs DPP-4i | Naive 0.1280 · A 0.0533 · B 0.0140; B minus A -0.0393 (95% interval -0.1013 to +0.0227): not a clear difference | Naive 0.1502 · A 0.0889 · B 0.1115; B minus A +0.0226 (95% interval -0.0886 to +0.1339): no improvement | Naive 0.1907 · A 0.0715 · B 0.0518; B minus A -0.0196 (95% interval -0.0886 to +0.0494): not a clear difference |
| Bias of the average effect (absolute), Sulfonylurea vs DPP-4i | Naive 0.0792 · A 0.0780 · B 0.0611; B minus A -0.0168 (95% interval -0.1663 to +0.1326): not a clear difference | Naive 0.0841 · A 0.1076 · B 0.0715; B minus A -0.0361 (95% interval -0.0838 to +0.0117): not a clear difference | Naive 0.1194 · A 0.0959 · B 0.0701; B minus A -0.0257 (95% interval -0.0762 to +0.0247): not a clear difference |
| Bias of the average effect (absolute), SGLT2i vs sulfonylurea | Naive 0.0546 · A 0.0247 · B 0.0592; B minus A +0.0345 (95% interval -0.0998 to +0.1688): no improvement | Naive 0.0661 · A 0.0212 · B 0.0610; B minus A +0.0397 (95% interval -0.0539 to +0.1333): no improvement | Naive 0.0712 · A 0.0244 · B 0.0191; B minus A -0.0053 (95% interval -0.0210 to +0.0104): not a clear difference |
| Error of each patient's effect (PEHE), SGLT2i vs DPP-4i | Naive 0.1906 · A 0.1204 · B 0.1972; B minus A +0.0768 (95% interval -0.0327 to +0.1864): no improvement | Naive 0.2051 · A 0.1411 · B 0.3965; B minus A +0.2554 (95% interval -0.3132 to +0.8239): no improvement | Naive 0.2366 · A 0.1566 · B 0.3564; B minus A +0.1999 (95% interval +0.0511 to +0.3487): no improvement (B clearly worse) |
| Error of each patient's effect (PEHE), Sulfonylurea vs DPP-4i | Naive 0.1899 · A 0.1498 · B 0.2981; B minus A +0.1483 (95% interval -0.0296 to +0.3263): no improvement | Naive 0.1881 · A 0.1606 · B 0.3985; B minus A +0.2379 (95% interval -0.2340 to +0.7099): no improvement | Naive 0.2049 · A 0.1648 · B 0.3701; B minus A +0.2052 (95% interval -0.1453 to +0.5557): no improvement |
| Error of each patient's effect (PEHE), SGLT2i vs sulfonylurea | Naive 0.1709 · A 0.1236 · B 0.2761; B minus A +0.1525 (95% interval -0.1775 to +0.4825): no improvement | Naive 0.1750 · A 0.1211 · B 0.2652; B minus A +0.1441 (95% interval -0.0768 to +0.3651): no improvement | Naive 0.1794 · A 0.1325 · B 0.2448; B minus A +0.1123 (95% interval -0.0291 to +0.2538): no improvement |
| Patients whose true effect lies in the 95% interval, SGLT2i vs DPP-4i | Naive 30.4% · B 96.6% | Naive 28.5% · B 91.2% | Naive 21.1% · B 96.0% |
| Patients whose true effect lies in the 95% interval, Sulfonylurea vs DPP-4i | Naive 36.7% · B 93.2% | Naive 37.1% · B 92.2% | Naive 30.0% · B 95.0% |
| Patients whose true effect lies in the 95% interval, SGLT2i vs sulfonylurea | Naive 41.1% · B 95.1% | Naive 39.6% · B 98.1% | Naive 38.1% · B 96.3% |
| Regret: extra HbA1c vs the truly best allowed drug | Naive 0.0669 · A 0.0200 · B 0.0369; B minus A +0.0169 (95% interval -0.0004 to +0.0343): no improvement | Naive 0.0669 · A 0.0121 · B 0.0456; B minus A +0.0334 (95% interval -0.0126 to +0.0795): no improvement | Naive 0.0669 · A 0.0411 · B 0.0343; B minus A -0.0069 (95% interval -0.0897 to +0.0760): not a clear difference |
| Error of the predicted HbA1c change (RMSE) | Naive 0.4137 · A 0.1527 · B 0.1556; B minus A +0.0029 (95% interval -0.0880 to +0.0937): no improvement | Naive 0.4145 · A 0.1551 · B 0.1878; B minus A +0.0327 (95% interval -0.0610 to +0.1264): no improvement | Naive 0.4137 · A 0.1513 · B 0.2122; B minus A +0.0608 (95% interval -0.0590 to +0.1806): no improvement |
| Picks the truly best allowed drug | Naive 47.6% · A 74.0% · B 65.2%; B minus A -8.8 points (95% interval -17.3 points to -0.3 points): no improvement (B clearly worse) | Naive 47.6% · A 80.4% · B 63.2%; B minus A -17.2 points (95% interval -50.6 points to +16.3 points): no improvement | Naive 47.6% · A 62.6% · B 65.6%; B minus A +3.0 points (95% interval -35.8 points to +41.8 points): not a clear difference |
| Numbers given where similar patients are too few | Naive 100.0% · A 100.0% · B 11.2%; B minus A -88.8 points (95% interval -93.2 points to -84.4 points): B clearly better | Naive 100.0% · A 100.0% · B 7.8%; B minus A -92.2 points (95% interval -104.8 points to -79.6 points): B clearly better | Naive 100.0% · A 100.0% · B 3.9%; B minus A -96.1 points (95% interval -103.0 points to -89.1 points): B clearly better |
| Options the engine withholds (B only) | Naive 0.0% · A 0.0% · B 4.2% | Naive 0.0% · A 0.0% · B 12.3% | Naive 0.0% · A 0.0% · B 24.8% |

Source: `results/xai_stress.csv`. Pre-registered before any run (docs/XAI_PLAN.md section 10): quick mode, 3 synthetic cohorts of 1,500 patients per multiplier (fewer and smaller than the 20 cohorts of 5,000 above), so every interval is wide and a single small cohort is a noisy judge; a multiplier raises confounding and removes overlap together. Naive = plain group averages; B minus A is paired on the same cohorts; absolute bias is the absolute value of each cohort's bias, averaged over the cohorts; every row of the results file is shown.
