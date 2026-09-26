# Mid-sem kit — Major Project Progress Presentation-II (Wed 30 Sept 2026)

> Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

| File | What it is | Mentor item |
|---|---|---|
| `DiaCausal_MidSem_Presentation.pptx` | 22 slides, 4:3, college format, speaker notes and presenter per slide | all six |
| `DiaCausal_MidSem_Report.pdf` | The report (49 pages): requirements, design, implementation status, real results, screenshots, code, evaluation matrix, timeline | all six |
| `DiaCausal_Report_Overleaf.zip` | The report's LaTeX source — Overleaf → New Project → Upload Project | — |
| `gantt.png` | Timeline chart (`scripts/make_gantt.py`) | 3 |
| `DiaCausal_demo.mp4` | 98-second backup demo video (three presets, Evidence, Results) | 6 |
| `viva/viva_sheet.pdf` | One page: each item in one sentence, key words, ten likely questions | — |
| `screens/`, `diagrams/` | Screenshots and design diagrams used in the slides and report | 4, 6 |

Presenters (from docs/04): Pratham 1–3, 17, 20 · Rhian 4–5, 14–16 · Advik 6–9, 19, 21 · Graceton 10–13, 18.

Rebuild after a change:

```bash
.venv/bin/python scripts/make_gantt.py                         # Gantt chart
node scripts/make_midsem_deck.js                               # slides (needs: npm install pptxgenjs@3.12.0)
(cd report && pdflatex 0Synopsis && bibtex 0Synopsis && pdflatex 0Synopsis && pdflatex 0Synopsis)
```

Numbers come only from `results/` (synthetic data). Say it aloud: "Everything shown runs on synthetic data;
no real patient data has been used."
