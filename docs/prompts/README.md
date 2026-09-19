# Claude Code prompts — run in this order

Each file says which model and effort to pick. To run one, open Claude Code in the repo folder, set the model with `/model`, and type:

`Do docs/prompts/NN-name.md exactly. First create and switch to the branch named in the file from an up-to-date main.`

Claude Code makes the branch, plans, waits for your OK, builds, tests, pushes and opens a pull request. You never type git commands. Do not merge until the pull request has been reviewed.

| # | File | What | Owner | Model | Effort | Start |
|---|---|---|---|---|---|---|
| 01 | `01-guards.md` | Guards and notices | C (D reviews) | Sonnet 5 | default | Mon 21 Sep |
| 02 | `02-auth.md` | Login, MFA, CAPTCHA, admin, audit log | C | Opus 5 | high | Tue 22 Sep |
| 03 | `03-freeze.md` | Browser test and tidy-up | C | Sonnet 5 | default | Sat 26 Sep |
| 04 | `04-patient-panel.md` | Patient panel and patient data type | C (A reviews fields) | Sonnet 5 | default | Mon 28 Sep |
| 05 | `05-guardrails.md` | Clinical guardrails from the cited table | D (A helps) | Opus 5 | high | Mon 28 Sep |
| 06 | `06-causal-engine.md` | 3-drug causal engine | A | Opus 5 | max while planning, then high | Mon 28 Sep |
| 07 | `07-rag.md` | Licence-cleared RAG with citations | B | Opus 5 | high | Mon 28 Sep |
| 08 | `08-answer-card.md` | Answer card, evidence drawer, abstain and loading | C | Sonnet 5 | default | Mon 5 Oct |
| 09 | `09-explanation.md` | Explanation stage and number-checking output guard | C (D reviews) | Opus 5 | high | Mon 12 Oct |
| 10 | `10-deploy.md` | Docker, deploy and evaluation pack | C + D | Sonnet 5 | default (switch to Opus 5 if stuck) | Mon 12 Oct |
| 11 | `11-voice.md` | Voice input — OPTIONAL, only if ahead by 12 Oct | C | Sonnet 5 | default | only if ahead |

Three things only the team can supply — the prompts fail loudly until they exist: the reviewed foul-word list (D), the doctor-reviewed guardrail table (D), the sourced params.yaml values (A).
