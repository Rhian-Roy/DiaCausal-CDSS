<!-- Owner: D (A helps) | Model: Opus 5 | Effort: high | Branch: feat/guardrails | Start: Mon 28 Sep -->
# Prompt 5: Clinical guardrails from the cited table

**How to run:** in Claude Code type `/model`, choose **Opus 5**, set effort to **high**, then type:
`Do docs/prompts/05-guardrails.md exactly. First create and switch to the branch feat/guardrails from an up-to-date main.`

---
Read CLAUDE.md, backend/app/pipeline/clinical_guardrails.py, causal_engine/guardrails.py (older research code — reuse ideas, not thresholds) and backend/app/clinical/guardrails.v1.yaml. Task: make the clinical_guardrails stage real. Safety invariants: guardrails run BEFORE causal ranking; thresholds and contraindications come only from the structured, cited table, never from free text or a model. Plan first and wait for my OK.
1. The table ALREADY EXISTS as a DRAFT (15 rules). Keep its format. Do NOT add, remove or change any clinical content, threshold or source — only Member D and the doctor do that. Write a loader + schema validation: a rule containing TODO or with no source makes the loader fail with a clear error; rules with verified "recheck" load but are logged as needing recheck; while reviewed_by is empty, every result carries "draft — not clinically reviewed".
2. Stage output: for each of the three options (sglt2i, dpp4i, sulfonylurea), status Safe to consider / Check first / Do not use with reasons and sources. A do_not_use option is removed before the causal stage and can never be shown first. Patient-scope "abstain" rules stop the pipeline with the reason.
3. If every option is do_not_use, or a required field is missing, the stage abstains with a plain reason (feeds design 19).
4. Add a structured reply part "options" (schemas.py + contract.ts) carrying each option's guardrail status; later stages fill in more fields.
5. Tests: one test per rule with a patient that triggers it and one that doesn't; loader rejects uncited/TODO rules; removed options never reach causal_engine.
6. Write docs/explain/06-guardrails.md with a worked example patient and 5 viva questions ("Why can't the model override a contraindication?").

---
When you are completely finished (all tests green):
1. Run `python3 scripts/check_all.py` and show me the last line.
2. Commit, push this branch, and open a pull request to main (use `gh pr create`; if `gh` is not logged in, walk me through `gh auth login` step by step).
3. Give me the pull-request link.
4. Write a 5-line plain-English summary of what changed that I can paste into our team WhatsApp.
Do NOT merge the pull request — I will get it reviewed first.
