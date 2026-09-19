<!-- Owner: C + D | Model: Sonnet 5 | Effort: default (switch to Opus 5 if stuck) | Branch: feat/deploy | Start: Mon 12 Oct -->
# Prompt 10: Docker, deploy and evaluation pack

**How to run:** in Claude Code type `/model`, choose **Sonnet 5**, set effort to **default (switch to Opus 5 if stuck)**, then type:
`Do docs/prompts/10-deploy.md exactly. First create and switch to the branch feat/deploy from an up-to-date main.`

---
Read CLAUDE.md and docker/README.md. Task: one image the doctor's evaluation PC can run, plus the evaluation kit. Plan first and wait for my OK.
1. One Dockerfile (multi-stage): build the frontend, FastAPI serves the built files and /api from one origin; python:3.12-slim; non-root user; no secrets in the image; healthcheck. compose.yaml with a volume for the SQLite database and model files. Update docker/README.md.
2. Security headers: CSP, HSTS (when behind HTTPS), frame-ancestors 'none', nosniff; /docs disabled in production; request body size limit.
3. docs/DEPLOY.md: run on a clean Windows/Linux PC with Docker Desktop; create the admin; HTTPS option (reverse proxy) for a network deployment; database backup.
4. Evaluation pack in eval/: 25 synthetic patient vignettes (JSON) covering each guardrail, each option winning, abstain, emergency, identifier, out of scope; a script that runs them and saves a results table; a System Usability Scale form and a short doctor feedback sheet. No real patient data.
5. Deploy checklist in docs/DEPLOY.md, checked off.
6. Write docs/explain/11-deploy.md with 5 viva questions.

---
When you are completely finished (all tests green):
1. Run `python3 scripts/check_all.py` and show me the last line.
2. Commit, push this branch, and open a pull request to main (use `gh pr create`; if `gh` is not logged in, walk me through `gh auth login` step by step).
3. Give me the pull-request link.
4. Write a 5-line plain-English summary of what changed that I can paste into our team WhatsApp.
Do NOT merge the pull request — I will get it reviewed first.
