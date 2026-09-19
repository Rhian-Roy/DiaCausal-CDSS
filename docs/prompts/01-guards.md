<!-- Owner: C (D reviews) | Model: Sonnet 5 | Effort: default | Branch: feat/guards | Start: Mon 21 Sep -->
# Prompt 1: Guards and notices

**How to run:** in Claude Code type `/model`, choose **Sonnet 5**, set effort to **default**, then type:
`Do docs/prompts/01-guards.md exactly. First create and switch to the branch feat/guards from an up-to-date main.`

---
Read CLAUDE.md, docs/TESTING.md and design/v1/09–12. Task: replace the empty blocklist and the medical-UI-guard stub with real guards shared by browser and server, and show the four notices from the designs. Plan first (files, test list) and wait for my OK; then small verified steps, one commit each.

1. The shared rules file ALREADY EXISTS: shared/guard_rules/rules.v1.json, with examples.v1.json and reference_guard.py (47/47 cases pass). Do not rewrite its contents. Make frontend/src/lib/guards.ts and backend/app/pipeline/blocklist.py both load it (Vite JSON import; Python json at startup) and give exactly the same result as reference_guard.py on every case. Delete both hard-coded BLOCKED_TERMS. Log the rules version with the trace ID per request, never the text.
2. Whole-word matching must keep Devanagari words whole ("मधुमेह" is one word). Frontend [\p{L}\p{M}\p{N}]; backend the `regex` package with the same class (pin it).
3. The medical allowlist always wins over the blocklist. Never echo the matched word to the user or the log.
4. Run every check in the browser AND in backend_guard (the server is the authority): identifiers -> notice 09; out of scope -> notice 10 naming the reason; emergency -> notice 11 only, no treatment content; blocked language -> notice 12. The backend returns outcome "blocked" plus reason_code (identifier | out_of_scope | emergency | language); add reason_code to schemas.py and contract.ts together. Negation and history cues in rules.v1.json must work exactly as in reference_guard.py.
5. Console honesty: any check still stubbed prints "(stub)". Blocks use console.warn with the trace ID.
6. Build notices 09–12 as React components with the existing tokens in src/index.css. Fonts stay on the local @fontsource packages — do not add the Google Fonts links from the designs.
7. Tests: pytest and vitest both run every case in examples.v1.json. Add a line to scripts/check_all.py; update docs/TESTING.md and the check count.
8. Write docs/explain/03-guards.md: each guard, one worked example each, 5 viva questions with answers.
Do not touch clinical_guardrails, causal_engine, rag_retrieval or llm_explanation. Never loosen request validation.

---
When you are completely finished (all tests green):
1. Run `python3 scripts/check_all.py` and show me the last line.
2. Commit, push this branch, and open a pull request to main (use `gh pr create`; if `gh` is not logged in, walk me through `gh auth login` step by step).
3. Give me the pull-request link.
4. Write a 5-line plain-English summary of what changed that I can paste into our team WhatsApp.
Do NOT merge the pull request — I will get it reviewed first.
