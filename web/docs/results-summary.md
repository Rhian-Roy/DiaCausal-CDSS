# Results summary: causal engine v0.3 (synthetic data)

> Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

**Where the numbers come from:** `results/benchmark_summary.csv`, `results/refutation.csv`,
`results/evalues.csv` and `results/run_info.json`. They were produced by
`python -m diacausal_engine.benchmark` from 20 synthetic India-calibrated cohorts of 5,000 patients each.
Each cohort also has 2,000 fresh test patients. The whole run took about 2.5 minutes.

**These are SYNTHETIC results.** They show that the *methods* recover a truth we planted. They are
not real-world drug effects. Do not quote any number that is not in the files above.

## 1. Which method is least biased? (average effects)

The true effects in the synthetic population are:

| Comparison | True effect |
|---|---|
| SGLT2i minus DPP-4i | **−0.211** percentage points (SGLT2i lowers HbA1c 0.21 more) |
| Sulfonylurea minus DPP-4i | **−0.256** |
| SGLT2i minus sulfonylurea | **+0.045** (almost no difference) |

| Method | Bias, SGLT2i vs DPP-4i | Bias, SU vs DPP-4i | Bias, SGLT2i vs SU |
|---|---|---|---|
| Naive | **−0.159** | −0.106 | −0.053 |
| IPW | +0.001 | −0.004 | +0.005 |
| Matching | −0.002 | −0.008 | +0.006 |
| AIPW | +0.002 | −0.003 | +0.005 |

**Plain English:** the naive comparison exaggerates SGLT2i's benefit over DPP-4i by about 75%
(−0.370 against the true −0.211), because sicker patients got SGLT2i more often. All three
corrected methods remove almost all of that bias. AIPW also has among the smallest typical errors
(RMSE 0.023–0.030).

## 2. Do the 95% intervals contain the truth about 95% of the time?

Coverage over the 20 repeats:

| Method | SGLT2i vs DPP-4i | SU vs DPP-4i | SGLT2i vs SU |
|---|---|---|---|
| Naive | **0%** | **0%** | 50% |
| IPW | 100% | 100% | 95% |
| Matching | 95% | 100% | 95% |
| AIPW | 95% | 95% | 90% |

**Plain English:** the naive intervals are confidently wrong. The corrected methods' intervals
contain the truth 90–100% of the time, close to the 95% target. With only 20 repeats, 18/20 (90%)
and 19/20 (95%) are both within normal chance.

## 3. Patient-level effects: how does the DR-learner compare with simpler learners?

PEHE is the typical error in *one patient's* effect, measured on fresh test patients (lower is
better):

| Learner | SGLT2i vs DPP-4i | SU vs DPP-4i | SGLT2i vs SU |
|---|---|---|---|
| **DR-learner** | 0.105 | 0.117 | 0.108 |
| S-learner | 0.103 | 0.104 | 0.110 |
| T-learner | 0.189 | 0.192 | 0.184 |
| Naive (same answer for everyone) | 0.214 | 0.197 | 0.169 |

**Plain English:** the DR-learner roughly halves the T-learner's error and is about as accurate as
the S-learner. Unlike either, it gives every patient a **95% interval**. Those intervals contained
the true patient effect for **94.4%, 94.7% and 92.7%** of test patients, and are on average
0.36–0.41 points wide.

## 4. Policy regret: how much would we lose by trusting the estimates?

For each test patient, we pick the option with the lowest predicted HbA1c among those the safety
rules and the overlap check allow. We then compare it with the truly best allowed option.

| Learner | Average regret (HbA1c points) |
|---|---|
| DR-learner | **0.011** |
| S-learner | 0.012 |
| T-learner | 0.029 |
| Naive | 0.062 |

**Plain English:** choosing by the DR-learner's estimates loses on average only about 0.01 points of
HbA1c compared with perfect knowledge. Choosing by the naive averages loses about six times more.
(This is an evaluation of accuracy. In the product, the clinician decides.)

## 5. How often does the system abstain?

**2.5%** of patient–option pairs in the test cohorts were answered with "insufficient evidence"
(propensity below 0.05) or "excluded" by a safety rule instead of a number.

## 6. Covariate balance before and after weighting

The largest standardised mean difference (SMD) across all patient details and all pairs of options
falls from **0.70** before weighting to **0.08** after IPW weighting, averaged over the 20 repeats.
Below 0.1 counts as balanced (Austin 2009). So after weighting, the three drug groups look alike.

## 7. Refutation tests and sensitivity (`results/refutation.csv`, `results/evalues.csv`)

These were run on the cohort from repeat 1. **All 9 checks passed.**

| Check | What should happen | What happened |
|---|---|---|
| Placebo treatment (20 random shuffles of who got which drug) | The effect vanishes | Average placebo effect 0.003–0.007; 90–100% of the placebo 95% intervals contained 0 |
| Random common cause (add pure noise as a fake confounder) | The estimate doesn't move | SGLT2i vs DPP-4i: −0.156 → −0.155 (all three within 2 SE) |
| Data subset (random 80% of patients) | The estimate stays about the same | SGLT2i vs DPP-4i: −0.156 → −0.153 (all three within 2 SE) |

**E-values**, for how strong a hidden confounder would need to be:

| Comparison | E-value (estimate) | E-value (CI bound nearest 0) |
|---|---|---|
| SGLT2i vs DPP-4i | 1.72 | 1.54 |
| SU vs DPP-4i | 2.15 | 1.95 |
| SGLT2i vs SU | 1.57 | 1.39 |

**Plain English:** to explain away the SGLT2i-vs-DPP-4i effect, an unmeasured factor would have to
be linked to both drug choice and HbA1c by a risk ratio of about 1.5–1.7. That is moderate:
possible, which is why real-data use needs care.

**Honest note:** in repeat 1's single cohort, AIPW estimated SGLT2i vs DPP-4i as −0.156, with an
interval from −0.207 to −0.106. That interval just misses the true −0.211. This is one of the
~5% of cohorts where a 95% interval is expected to miss. Across all 20 cohorts, AIPW's coverage
was 90–95% (section 2).

## 8. The five figures, and how to read each one

| Figure | How to read it |
|---|---|
| `results/figures/overlap.png` | For each drug, the chance each patient had of getting it, split by the drug they actually got. The dashed line at 0.05 marks where we refuse to estimate; overlapping curves mean fair comparisons are possible. |
| `results/figures/love_plot.png` | Each row is a patient detail: hollow grey = how different the drug groups were before weighting, blue = after. Blue dots left of the dashed 0.1 line mean the groups are balanced. |
| `results/figures/ate_vs_truth.png` | For each comparison, each method's average estimate with its 95% interval; the black vertical line is the truth. Naive (grey) misses it; IPW, matching and AIPW sit on it. |
| `results/figures/cate_recovery.png` | Each dot is one test patient: true effect (across) against the DR-learner's estimate (up). Dots near the dashed diagonal are accurate. The small off-diagonal cluster in the middle panel is the rare-patient limitation. |
| `results/figures/calibration.png` | Patients grouped into tenths by predicted effect: the average predicted vs the average true effect. Points on the diagonal mean the predictions are well calibrated. |

## 9. What this does *not* show

- **No real-world effect:** it says nothing about real-world drug effects, because the data is synthetic and the effect sizes are ASSUMED-DIRECTIONAL.
- **No proof of zero hidden confounding:** refutation tests can reveal problems, but they cannot prove there is no hidden confounding.
- **Rare patient types are weaker:** estimates for rare patient types (past DKA or pancreatitis) are less accurate than for typical patients.
