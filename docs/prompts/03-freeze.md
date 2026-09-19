<!-- Owner: C | Model: Sonnet 5 | Effort: default | Branch: chore/freeze | Start: Sat 26 Sep -->
# Prompt 3: Browser test and tidy-up

**How to run:** in Claude Code type `/model`, choose **Sonnet 5**, set effort to **default**, then type:
`Do docs/prompts/03-freeze.md exactly. First create and switch to the branch chore/freeze from an up-to-date main.`

---
Read CLAUDE.md. Task: close the known test gap and tidy up before the Sun 27 Sep chat-shell freeze. Plan first, wait for my OK, one commit per item.
1. Playwright end-to-end test in real Chromium against the real backend and page (the gap in docs/TESTING.md part 3): sign in with a test account + TOTP -> type -> Enter -> exactly the four console lines with one trace ID -> reply visible -> same ID in the backend log; empty message blocked; an Aadhaar-like number shows notice 09; "type 1 patient" shows notice 10; 8 messages -> thread scrolls and stays on the newest; mic disabled; 390x844 phone viewport. Add to scripts/check_all.py and CI.
2. Each pipeline stage reports duration_ms; the stage list shows it.
3. CI: pip-audit, npm audit --omit=dev, Dependabot for pip, npm and GitHub Actions.
4. Docs: README — remove ADA retrieval claims (not licence-cleared); label the Pima dataset as from the Akimel O'odham community in Arizona, USA, not Indian; fix the clone URL. SETUP.md — remove the branch-switch note. check_all — Node check label says "22.22+ or 24.15+". docs/explain/02-presenting-it.md Q27 — the three-drug add-on decision (SGLT2i / DPP-4i / sulfonylurea on top of metformin) is v1.0 scope due 30 Oct; only validation on real patients is future work. Update the test counts it quotes.
5. .devcontainer: GitHub Codespaces runs the chat app (Python 3.12, Node 24, scripts/setup.py on create, forward 5173 and 8000).
6. design/README.md: list design/v1/01–20 and say which component builds each.
Update docs/TESTING.md and the check count.

---
When you are completely finished (all tests green):
1. Run `python3 scripts/check_all.py` and show me the last line.
2. Commit, push this branch, and open a pull request to main (use `gh pr create`; if `gh` is not logged in, walk me through `gh auth login` step by step).
3. Give me the pull-request link.
4. Write a 5-line plain-English summary of what changed that I can paste into our team WhatsApp.
Do NOT merge the pull request — I will get it reviewed first.
