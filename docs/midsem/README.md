# Mid-sem kit — Major Project Progress Presentation-II (Wed 30 Sept 2026)

> Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

| File | What it is | Mentor item |
|---|---|---|
| **`EXPLAINING_DIACAUSAL.md` / `.pdf`** | **Start here.** The whole project from start to end: pitches, every component, the guide-meeting script, the panel script, the demo runbook, 45 questions with answers, the numbers card | all six |
| `DiaCausal_MidSem_Presentation.pptx` | 22 slides, 4:3, college format (made 26 Sept; the team is updating it for RAG and the secondary outcomes) | all six |
| `DiaCausal_MidSem_Report.pdf` | The report (49 pages): requirements, design, implementation status, real results, screenshots, code, evaluation matrix, timeline | all six |
| `DiaCausal_Report_Overleaf.zip` | The report's LaTeX source — Overleaf → New Project → Upload Project | — |
| `gantt.png` | Timeline chart (`scripts/make_gantt.py`) | 3 |
| `DiaCausal_demo.mp4` | 112-second captioned backup demo (presets, weight and low-sugar lines, option evidence, quoted explanation, abstention, dose refusal, print summary, Results) | 6 |
| **`DATASETS.md` / `.pdf`** | Every dataset (synthetic cohort, safety rules, parameters, evidence sources, test questions, real Indian NMB-2017): columns, how the synthetic cohort is made, why it is valid, the real Indian datasets that exist, the real-vs-synthetic check, the hospital path, and the progress estimate (≈64%) | 2, 3 |
| `data/` | First-rows pictures of each dataset (`01_…`–`07_…`) and `real_vs_synthetic.png` | 2 |
| `screens/ui/`, `screens/chat_app/`, `screens/all_screens_*.png` | Every screen of the website and the chat app, desktop and phone, plus one overview sheet each (28 Sept) | 4, 6 |
| `viva/viva_sheet.pdf` | One page: each item in one sentence, key words, ten likely questions | — |
| `screens/`, `diagrams/` | Screenshots and design diagrams for the slides and report; new on 28 Sept: `secondary_cards_desktop`, `option_evidence_desktop`, `explanation_card_desktop`, `abstain_desktop`, `dose_refused_desktop`, `print_summary`, `phone_secondary_card`, `phone_explanation` | 4, 6 |

Presenters (from docs/04): Pratham 1–3, 17, 20 · Rhian 4–5, 14–16 · Advik 6–9, 19, 21 · Graceton 10–13, 18.

Rebuild after a change:

```bash
.venv/bin/python scripts/make_gantt.py                         # Gantt chart
node scripts/make_midsem_deck.js                               # slides (needs: npm install pptxgenjs@3.12.0)
(cd report && pdflatex 0Synopsis && bibtex 0Synopsis && pdflatex 0Synopsis && pdflatex 0Synopsis)
python scripts/fetch_nmb2017.py && python scripts/compare_cohort.py   # real Indian reference data + comparison
CHROMIUM_PATH=/path/to/chromium .venv/bin/python scripts/dataset_previews.py   # first-rows pictures
```

Numbers come only from `results/` (synthetic data). Say it aloud: "Everything shown runs on synthetic data;
no real patient data has been used to train or grade the engine." (NMB-2017, a real public Indian survey, is used only to check that the synthetic patients look realistic.)
