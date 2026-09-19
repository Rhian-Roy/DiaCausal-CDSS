<!-- Owner: C (A reviews fields) | Model: Sonnet 5 | Effort: default | Branch: feat/patient-panel | Start: Mon 28 Sep -->
# Prompt 4: Patient panel and patient data type

**How to run:** in Claude Code type `/model`, choose **Sonnet 5**, set effort to **default**, then type:
`Do docs/prompts/04-patient-panel.md exactly. First create and switch to the branch feat/patient-panel from an up-to-date main.`

---
Read CLAUDE.md, backend/app/schemas.py, frontend/src/lib/contract.ts and design/v1/13–16. Task: replace the hard-coded PatientStrip with the patient details panel, and send its values to the backend as a new structured part. Plan first and wait for my OK.
1. Contract: add PatientPart (type "patient") and make Part a tagged union on "type", as the comment in schemas.py describes; add "patient" to SUPPORTED_PART_TYPES; mirror in contract.ts. Keep extra="forbid". Fields with units in the name: age_years (18–110), diabetes_duration_years, hba1c_percent (4–20), egfr_ml_min_1_73m2 (0–150), bmi_kg_m2 (12–70), established_ascvd, ckd, heart_failure, past_dka, recurrent_genital_or_urinary_infection, past_pancreatitis (booleans), past_hypoglycaemia (none | mild | severe), budget_inr_per_month (optional). The last three booleans are needed by rules in backend/app/clinical/guardrails.v1.yaml. Out-of-range -> 422 with a plain-English message naming the expected range. Range limits live in one file with a comment saying they are plausibility limits, not clinical thresholds.
2. A request carries at most one patient part plus the text part. The six stages receive it via PipelineContext.patient.
3. Panel UI per designs 13–16: empty, filled, out-of-range inline message, "Example data" badge when prefilled; BMI category uses Asian-Indian cut-offs (normal <23, overweight 23–24.9, obese >=25; source Misra et al. JAPI 2009); desktop side panel, phone collapsible sheet; "New patient" clears the panel AND the conversation and starts a fresh trace. Browser-side range check for instant feedback; the backend check is the authority.
4. Never log patient values; log only which fields were present.
5. Tests: every field's boundaries both sides; unknown field rejected; two patient parts rejected; New patient clears everything. Update scripts/check_all.py, docs/TESTING.md and the check count.
6. Write docs/explain/05-patient-panel.md: why structured input beats free text for safety, one worked request JSON, 5 viva questions.

---
When you are completely finished (all tests green):
1. Run `python3 scripts/check_all.py` and show me the last line.
2. Commit, push this branch, and open a pull request to main (use `gh pr create`; if `gh` is not logged in, walk me through `gh auth login` step by step).
3. Give me the pull-request link.
4. Write a 5-line plain-English summary of what changed that I can paste into our team WhatsApp.
Do NOT merge the pull request — I will get it reviewed first.
