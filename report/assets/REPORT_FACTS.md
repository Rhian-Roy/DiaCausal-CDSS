# Report facts (18 Oct 2026, repository commit 9f9f3c9 plus the re-run language-model benchmark)

> Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

Every number below is **copied** from the file named next to it; nothing is computed or estimated here. All data are
**synthetic** (an India-calibrated cohort); no real patient data are used.

## Dataset and generator (`data/params.yaml`, `results/run_info.json`)

| Fact | Value | Source |
|---|---|---|
| Patients per synthetic cohort | 5000 | `params.yaml` `n_patients`; `run_info.json` `n_patients` |
| Benchmark replicates | 20 (test patients per replicate: 2000) | `run_info.json` `reps`, `n_test_patients` |
| Base seed; reference-cohort seed | 7; 2026 | `run_info.json` `base_seed`; `params.yaml` `engine.reference_cohort_seed` |
| Inclusion | eGFR ≥ 30 mL/min/1.73m² (CITED: FDA metformin 2016); HbA1c ≥ 7.0 % (TEAM-SET) | `params.yaml` `inclusion` |
| Population draw for the true effects | 200000 patients | `params.yaml` `population_truth_n` |
| True average 6-month HbA1c change (points) | SGLT2i −0.96146283; DPP-4i −0.75046544; SU −1.0069405150000001 | `run_info.json` `true_population_effects` |
| Engine settings | 5 cross-fit folds; overlap minimum propensity 0.05; maximum interval width 1.5 points; 95% interval (z 1.959964) | `params.yaml` `engine` |
| Refutation checks | 9 of 9 passed | `run_info.json` `refutation_checks_passed` |
| Evidence passages (licence-cleared, confirmed sources) | 78 passages from 7 sources | `web/evidence.json` (chunks; sources with bucket cleared_ingest and confirmed) |
| Gold questions | 60 (RAG), 20 (local model) | `eval/rag_gold.csv`, `eval/llm_golden.csv` (data rows) |

## Causal engine accuracy (`results/benchmark_summary.csv`; 20 replicates)

| Row | Value |
|---|---|
| Naive, SGLT2i vs DPP-4i | truth −0.2110, mean estimate −0.3697, bias −0.1587, 95% coverage 0.0000 |
| AIPW, SGLT2i vs DPP-4i | truth −0.2110, mean estimate −0.2091, bias 0.0019, RMSE 0.0226, 95% coverage 0.9500 |
| DR-learner, per patient, SGLT2i vs DPP-4i | 95% coverage 0.9441, mean interval width 0.3701, PEHE 0.1048 |
| DR-learner policy | regret 0.0110, abstention rate 0.0274 |

## A–D ablation (`results/xai_ablation.csv`; mean [95% CI] n = replicates; n = 0 rows come from fixed question sets)

| Metric (comparison) | A (XAI only) | B (causal) | C (causal + XAI) | D (causal + XAI + RAG) |
|---|---|---|---|---|
| Regret (all) | 0.0126418 [0.00835571, 0.0169279] | 0.0106256 [0.00829738, 0.0129539] | same as B | same as B |
| PEHE (SGLT2i–DPP4i) | 0.103316 [0.0965404, 0.110092] | 0.104791 [0.0933624, 0.11622] | same as B | same as B |
| 95% coverage (SGLT2i–DPP4i) | — (no interval) | 0.944075 [0.917786, 0.970364] | same as B | same as B |
| Numbers given where data are thin (all) | 1 [1, 1] | 0.127891 [0.0932814, 0.1625] | same as B | same as B |
| Top features are true modifiers (SGLT2i–DPP4i) | 0.95 [0.877974, 1.02203] | — | 0.875 [0.77104, 0.97896] | 0.875 [0.77104, 0.97896] |
| Shown drivers not true modifiers (SGLT2i–DPP4i) | — | — | 0.180513 [0.0565631, 0.304462] n=19 | same as C |
| Quoted sentences supported (all) | — | — | — | 1 (n=0, 60 gold questions) |
| Local-model drafts with only engine numbers (all) | — | — | — | 0.3 (n=0, 20 golden questions; re-run 18 Oct) |
| Abstention rate (all) | 0 [0, 0] | 0.0156381 [0.0139409, 0.0173352] | same as B | same as B |

## Evidence search (`results/rag_eval_summary.csv`, template backend, 60 questions)

Recall@5 0.956; answered 1.000; abstention accuracy 0.800; citation precision 1.000; dose leaks 0.

## Latency

| Measurement | Value | Source |
|---|---|---|
| Whole pipeline, template, 20 golden questions (Mac, Apple silicon) | median 52.0 ms; 95th percentile 73.5 ms; fallback rate 0.0; start-up 8.2 s | `results/local_llm_mac-m-series_summary.csv` |
| Local model call, qwen3:4b-instruct-2507-q4_K_M (Mac) | p50 24.31 s; p95 43.16 s; schema-valid 100.0 %; number-match 30.0 %; fallback 75.0 % (re-run 18 Oct 2026) | `results/llm/bench_summary.csv` |
| Local model call, medgemma1.5:4b-it-q4_K_M (Mac) | p50 52.91 s; p95 60.01 s; schema-valid 60.0 %; number-match 75.0 % (of the valid ones); fallback 55.0 % (8 of 20 timed out at 60 s) (re-run 18 Oct 2026) | `results/llm/bench_summary.csv` |
| RTX 2050 laptop | not measured yet (`scripts/measure_local.py --machine rtx2050`) | — |

## Tests (`assets/results/test_counts.csv`; `python3 scripts/check_all.py` on 18 Oct 2026: ALL 64 CHECKS PASSED)

- **Chat app (legacy):** backend 392, frontend 238, vignettes 25, real-browser 10.
- **Submitted system:**

| Test group | Passed |
|---|---|
| engine | 194 |
| RAG | 199 (1 skipped) |
| guards | 381 |
| contract | 71 |
| imports | 79 |
| no legacy use | 2 |
| CI workflows | 8 |
| pipeline and local-model provider | 185 |
| log privacy | 25 |
| clinic laptop | 12 |
| demo script | 5 |
| web parity | 30 |
| XAI | 68 |

- **Do not add these up.** The log-privacy group's 25 tests are also inside the pipeline group.

## Documents (`assets/results/doc_sizes.csv`)

Words and lines of every `docs/*.md` and `report/*.tex`. **Page counts are not measured:** the docs are Markdown (no pages),
and the LaTeX report was not compiled (no LaTeX on this machine). Some examples:

| Document | Words |
|---|---|
| `docs/PLAN_2026-10.md` | 17144 |
| `docs/TESTING.md` | 8277 |
| `docs/XAI_PLAN.md` | 5736 |
| `docs/DEPLOY.md` | 2743 |
| `report/` chapters 1–6, together | 7033 |

## Other files in this pack

- `assets/screens/`: 12 screens of the current `web/` build, at 1280 px and 390 px.
  - Taken with the repository's screenshot runner (`tests/web/screens_check.cjs`) on a local copy with sign-in off.
  - Synthetic presets only. The 19 screen uses the Typical preset with age 88, which is outside the cohort.
  - About (26) shows the team's and the guide's names.
- `assets/results/`: the copied CSV and JSON files, unchanged from `results/`.
