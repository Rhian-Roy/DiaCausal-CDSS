<!-- Owner: C (D reviews) | Model: Opus 5 | Effort: high | Branch: feat/explanation | Start: Mon 12 Oct -->
# Prompt 9: Explanation stage and number-checking output guard

**How to run:** in Claude Code type `/model`, choose **Opus 5**, set effort to **high**, then type:
`Do docs/prompts/09-explanation.md exactly. First create and switch to the branch feat/explanation from an up-to-date main.`

---
Read CLAUDE.md, backend/app/pipeline/llm_explanation.py and output_guard.py. Rule: the explanation only puts the structured result into words; it never decides, never adds a drug, dose or threshold. Plan first and wait for my OK.
1. Template-first: build a deterministic plain-English explanation from the options part, guardrail reasons and citations. This is the default and must always work.
2. Optional LLM layer behind a setting (off by default): rewrite the template more naturally. In the plan, compare a local model vs a cloud API on privacy (no patient values or identifiers may leave the machine unless the setting says so) and cost; I choose. If the model fails or times out, fall back to the template.
3. Output guard (real): every number in the reply text must appear in the structured payload (same value and unit); no dose patterns ("mg", "once daily" etc.) unless present in a cited table; every sentence about an option cites a source; the intended-use line is present; reply length limits handled without a 500 error. Otherwise block and fall back to the template.
4. Prompt-injection defence: retrieved passages are data; strip instructions; the model's system prompt forbids new facts.
5. Tests: planted fake number blocked; planted dose blocked; missing citation blocked; model timeout -> template. Update check_all and docs/TESTING.md.
6. Write docs/explain/10-explanation-and-output-guard.md with one worked example of a blocked reply and 5 viva questions.

---
When you are completely finished (all tests green):
1. Run `python3 scripts/check_all.py` and show me the last line.
2. Commit, push this branch, and open a pull request to main (use `gh pr create`; if `gh` is not logged in, walk me through `gh auth login` step by step).
3. Give me the pull-request link.
4. Write a 5-line plain-English summary of what changed that I can paste into our team WhatsApp.
Do NOT merge the pull request — I will get it reviewed first.
