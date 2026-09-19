<!-- Owner: C | Model: Sonnet 5 | Effort: default | Branch: feat/answer-card | Start: Mon 5 Oct -->
# Prompt 8: Answer card, evidence drawer, abstain and loading

**How to run:** in Claude Code type `/model`, choose **Sonnet 5**, set effort to **default**, then type:
`Do docs/prompts/08-answer-card.md exactly. First create and switch to the branch feat/answer-card from an up-to-date main.`

---
Read CLAUDE.md and design/v1/17–20. Task: show the real pipeline result. Plan first and wait for my OK.
1. Render the "options" reply part as design 17: three rows (SGLT2i, DPP-4i, sulfonylurea, all added to metformin); HbA1c change as a range with an interval bar — never a bare number; hypoglycaemia risk, weight, INR/month (labelled as from cited tables); safety chip; "Do not use" rows greyed and never first; "The clinician decides." under the table. No wording that tells the doctor what to prescribe.
2. Citation markers open the evidence drawer (design 18) with source, version, section, page and the verbatim passage.
3. Insufficient evidence (design 19) whenever guardrails or the causal stage abstain, with the reason.
4. Loading (design 20): the six stage names tick from waiting to done using the stage results; keep the trace ID visible.
5. Output check in api.ts: refuse to show an options part if any shown estimate lacks an interval, any claim lacks a citation, or a do_not_use option is ranked first.
6. Fonts from local @fontsource. Desktop and 390 px phone. Keyboard and screen-reader access for the drawer.
7. Extend the Playwright test: example patient -> options card with three rows and intervals -> open a citation -> drawer shows the passage. Update docs/TESTING.md and the count.
8. Write docs/explain/09-answer-card.md with 5 viva questions ("Why show a range, not a number?").

---
When you are completely finished (all tests green):
1. Run `python3 scripts/check_all.py` and show me the last line.
2. Commit, push this branch, and open a pull request to main (use `gh pr create`; if `gh` is not logged in, walk me through `gh auth login` step by step).
3. Give me the pull-request link.
4. Write a 5-line plain-English summary of what changed that I can paste into our team WhatsApp.
Do NOT merge the pull request — I will get it reviewed first.
