# Using DiaCausal with Claude Chat (claude.ai)

> Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

Goal: open claude.ai (web or phone app), ask "explain slide 17" or "how does AIPW work in our code?", and get an
answer from **our** files. Two parts: make the latest work visible on GitHub, then connect GitHub to a
claude.ai **Project**.

## 1. Put the latest work on `main`

The claude.ai GitHub integration reads files from a branch of the repository, not pull requests or history.
Our newest work (deck, datasets, briefing, interaction-sheet charts) is on the branch
`claude/diacausal-causal-engine-rers9e` until it is merged, so merge its pull request first, then use `main`.

## 2. Create a claude.ai Project and add the repository

1. On claude.ai: **Projects → Create project** → name it "DiaCausal (Group 28)". Keep it **private**. GitHub
   files can only be added to a private project; share answers with teammates by copying, or let each teammate
   make their own project the same way.
2. In the project, under **Project knowledge**, press **+ → GitHub**.
3. The first time, authorise the **Claude GitHub App**. The repository is public, so no extra permission is
   needed. For a private repository you would grant access to `Rhian-Roy/DiaCausal-CDSS` only.
4. Search for or paste `https://github.com/Rhian-Roy/DiaCausal-CDSS`. In the file browser, tick **only** the list
   below, then **Add files**. The whole repository (PDFs, notebooks, images, corpus) is too big for Claude's
   context window.
5. When the code changes, open the project and press **Sync** (or **Configure files** to change the list).

### Files to tick (about 60,000 words, fits comfortably)

| Tick | Why |
|---|---|
| `CLAUDE.md`, `README.md` | Rules, layout, how to run everything |
| `docs/midsem/TEAM_BRIEFING.md` | Every slide: what to say and what it means |
| `docs/midsem/EXPLAINING_DIACAUSAL.md` | The full handbook: components, 45 questions, numbers |
| `docs/midsem/DATASETS.md`, `INTERACTION_SHEET.md`, `PPT_CHANGES.md` | Data, the sheet, deck changes |
| `docs/CAUSAL_PLAN.md` | Why the causal engine is built the way it is |
| `diacausal_engine/` (all `.py`) | The causal engine code |
| `diacausal_rag/` (all `.py`, `config.yaml`, `prompt.v1.txt`; **not** `corpus/`) | The RAG code |
| `backend/app/pipeline/` | The chat app's six stages |
| `data/params.yaml`, `data/rules.csv`, `RAG/sources.csv` | Every number, rule and source |
| `results/benchmark_summary.csv`, `results/rag_eval_summary.csv`, `results/refutation.csv` | The real results |

Add more folders later (for example `web/` or `frontend/src/`) if you need them; remove some if claude.ai says
the knowledge is too large.

## 3. Project instructions (paste into "Set project instructions")

```
You are helping Group 28 (FCRIT Vashi, B.Tech Computer Engineering, guide Mr. Rahul Jadhav) understand and present
DiaCausal, a research prototype that helps a clinician choose an add-on drug to metformin (SGLT2i, DPP-4i,
sulfonylurea) using safety rules, causal inference (propensity, AIPW, DR-learner) with 95% intervals, and cited
evidence (RAG over WHO 2018 and FDA notices).
Answer only from the project files; name the file you used. If the files do not say, say so.
Quote numbers exactly as in results/*.csv, TEAM_BRIEFING.md or DATASETS.md; never invent results.
Explain in plain English first, then the technical detail, as if to our guide and a university panel.
Never give drug doses. Always keep: "Research prototype for clinician evaluation; not a marketed medical device;
not for unsupervised clinical use." The engine uses synthetic data only; NMB-2017 is a realism check.
```

## 4. Good questions to start with

- "Walk me through slides 19 to 21 as if I am presenting them."
- "Quiz me with 10 panel questions on the causal engine; wait for my answer each time."
- "Explain `aipw_scores` in diacausal_engine/estimators.py line by line."
- "Which interaction-sheet remarks did we address, and on which slide?"
- "What exactly is left for 100% implementation?"

Other ways, if needed: in any chat, **+ → Add from GitHub** attaches files for that one chat; or upload
`TEAM_BRIEFING.pdf` / `EXPLAINING_DIACAUSAL.pdf` as project files (works even without GitHub).
