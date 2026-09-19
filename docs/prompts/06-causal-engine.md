<!-- Owner: A | Model: Opus 5 | Effort: max while planning, then high | Branch: feat/causal-3arm | Start: Mon 28 Sep -->
# Prompt 6: 3-drug causal engine

**How to run:** in Claude Code type `/model`, choose **Opus 5**, set effort to **max while planning, then high**, then type:
`Do docs/prompts/06-causal-engine.md exactly. First create and switch to the branch feat/causal-3arm from an up-to-date main.`

---
Read CLAUDE.md, the research code in causal_engine/ (it compares SGLT2i vs metformin — two arms. That is NOT our question; reuse its structure and tests, not its data story) and docs/research/DiaCausal_parameter_extraction_worksheet.xlsx. Task: the v1.0 causal engine for "which drug to ADD to metformin: SGLT2i, DPP-4i or sulfonylurea", outcome = 6-month HbA1c change in percentage points. Plan first and wait for my OK.
1. Generator: causal_engine_v1/generator.py makes an India-calibrated synthetic cohort (age, sex, duration, HbA1c, eGFR, BMI, ASCVD, CKD, HF, past hypoglycaemia, socioeconomic proxy) with confounded 3-way treatment assignment and a planted individual effect per arm. EVERY distribution and effect size is read from causal_engine_v1/params.yaml, each with a source {title, year, table/figure}. A parameter with no source makes the generator refuse to run. Use only worksheet rows with status "verified"; everything else stays a TODO placeholder. Do NOT invent values. If Member A's existing params.yaml or validate_params.py exist anywhere in the repo, reuse them.
2. Estimator: multi-arm CATE for each option vs a reference (e.g. doubly robust learner, one model per contrast), with bootstrap 95% intervals. Choose the method in the plan and justify it in two sentences.
3. Overlap: multinomial propensity model; if the patient's propensity for any remaining option is below a threshold (in params.yaml with a reason), return "insufficient evidence" for that comparison (feeds design 19).
4. Validation on synthetic ground truth: PEHE, interval coverage (target ~95%), ranking accuracy; save plots to figures/v1/. Refutation: placebo treatment and random common cause.
5. Stage wiring: backend/app/pipeline/causal_engine.py receives only options that survived guardrails, fills each option's expected HbA1c change as {low, high} (never a bare point estimate), model version and cohort version. Load the fitted model once at startup; must answer in <2 s.
6. Secondary outcomes (hypoglycaemia risk, weight change, INR/month) come from a cited lookup table (causal_engine_v1/secondary.v1.yaml), not the model, and are labelled that way in the reply.
7. Tests: generator refuses uncited params; estimator recovers the planted effect within tolerance on a seeded cohort; overlap abstains outside support; stage never ranks a removed option.
8. Write docs/explain/07-causal-engine.md: DAG, why naive comparison is wrong, one worked numerical example of the doubly robust estimate for one patient, 8 viva questions.

---
When you are completely finished (all tests green):
1. Run `python3 scripts/check_all.py` and show me the last line.
2. Commit, push this branch, and open a pull request to main (use `gh pr create`; if `gh` is not logged in, walk me through `gh auth login` step by step).
3. Give me the pull-request link.
4. Write a 5-line plain-English summary of what changed that I can paste into our team WhatsApp.
Do NOT merge the pull request — I will get it reviewed first.
