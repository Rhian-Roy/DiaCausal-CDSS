# Mid-sem kit — Major Project Progress Presentation-II (Wed 30 Sept 2026)

> Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

| File | What it is | Mentor item |
|---|---|---|
| **`PANEL_PREP.md` / `.pdf`** | **Start here if you are new.** From zero to ready: the story, exactly what the 25% covers and where it ends, every abbreviation expanded, the code file by file, the numbers card, 118 panel questions with answers, NotebookLM and Claude study prompts, the day-of checklist | all six |
| **`explainer/index.html`** + `DiaCausal_explainer.mp4` | The interactive narrated explainer (12 scenes, glossary, quiz; online at https://claude.ai/artifact/QQ3PmLQHZxrmmmi13tVFq9 once shared) and the same story as a 9-minute narrated video with captions (`scripts/make_explainer.py`, `scripts/record_explainer.cjs`) | all six |
| **`EXPLAINING_DIACAUSAL.md` / `.pdf`** | The handbook: pitches, every component, the guide-meeting script, the panel script (40-slide deck), the demo runbook, 45 questions, the numbers card | all six |
| **`TEAM_BRIEFING.md` / `.pdf`** | Every slide of the 40-slide deck: what to say, what it means, what may be asked; the code folder by folder | all six |
| `DiaCausal_MidSem_Presentation.pptx` | The first 22-slide draft (26 Sept), kept for reference; the team's deck below replaces it | — |
| `DiaCausal_MidSem_Report.pdf` | The report (52 pages): requirements, design, implementation status, real results, screenshots, code, evaluation matrix, timeline | all six |
| `DiaCausal_Report_Overleaf.zip` | The report's LaTeX source — Overleaf → New Project → Upload Project | — |
| `gantt.png`, `timeline.png` | Gantt chart and timeline chart with only the Project Interaction Sheet's rows and wording (`scripts/make_gantt.py`) | 3 |
| **`INTERACTION_SHEET.md`** | Every interaction-sheet entry: remark, status, where it is covered | all |
| **`Intelligent_Diabetes_CDSS_MidSem_updated.pptx`** (+ `.pdf` preview) + `PPT_CHANGES.md` | The team's deck, updated: 35 slides + 5 backup; slide 23 shows exactly what the 25% covers | all |
| `DiaCausal_demo.mp4` | 112-second captioned backup demo (presets, weight and low-sugar lines, option evidence, quoted explanation, abstention, dose refusal, print summary, Results) | 6 |
| **`DATASETS.md` / `.pdf`** | Every dataset (synthetic cohort, safety rules, parameters, evidence sources, test questions, real Indian NMB-2017): columns, how the synthetic cohort is made, why it is valid, the real Indian datasets that exist, the real-vs-synthetic check, the hospital path, and the progress estimate (≈75%) | 2, 3 |
| `data/` | First-rows pictures of each dataset (`01_…`–`07_…`) and `real_vs_synthetic.png` | 2 |
| `screens/ui/`, `screens/chat_app/`, `screens/all_screens_*.png` | Every screen of the website and the chat app, desktop and phone, plus one overview sheet each (28 Sept) | 4, 6 |
| `viva/viva_sheet.pdf` | One page: each item in one sentence, key words, ten likely questions | — |
| `screens/`, `diagrams/` | Screenshots and design diagrams for the slides and report; new on 28 Sept: `secondary_cards_desktop`, `option_evidence_desktop`, `explanation_card_desktop`, `abstain_desktop`, `dose_refused_desktop`, `print_summary`, `phone_secondary_card`, `phone_explanation` | 4, 6 |

Presenters (40-slide deck, as in its speaker notes): Pratham 1–3, 28, 32–33, 35 · Rhian 4–7, 22–24, 27, 29 ·
Advik 8–13, 25–26, 31, 34 · Graceton 14–21, 30.

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
