# Changes to the team's deck (28–29 Sept)

> Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

Input: the team's `Intelligent_Diabetes_Clinical_Decision_Support_System.pptx` (24 slides).
Output: `Intelligent_Diabetes_CDSS_MidSem_updated.pptx`: **34 slides + 5 backup** (39), same template, fonts
and colours. Every number comes from `results/`, `docs/TESTING.md`, `DATASETS.md` or the engine itself.
Export the PDF from PowerPoint / Google Slides (not LibreOffice) so the deck's own fonts are used.

## Following the Project Interaction Sheet (29 Sept)

| # | Slide | Why |
|---|---|---|
| 9 | **Proposed System – Scope** (new): in scope, out of scope, future scope | Week 4 remark: "scope needs enhancement" |
| 12 | **Timeline / Gantt Chart** (replaced): Gantt built from the sheet, four implementation sections with the sheet's 25/40/60/80% deadlines | Week 5; sheet note: "timeline chart should reflect implementation into four sections" |
| 13 | **Timeline Chart – Interaction Sheet** (new): every sheet entry, date, status | Week 5 |
| 17 | **System Design – Working of the System** (new): one real consultation, step by step, with the engine's numbers | Week 6 remark: "working of the system: not done" |
| 30 | Completed vs Planned: planned side keyed to sheet weeks 8–10, guide evaluation, Nov, Dec, Jan–Feb | Weeks 8–10 |
| 31 | Progress: "25% by 23 Sep (met), 40% by 7 Oct (met early)" | Weeks 7–8 |
| 39 | Backup – Literature Comparison | Week 1: 16 papers, comparison table |
| 3 | Outline wording: scope, interaction-sheet timeline, working of the system | — |

## Corrected (they said "planned" or showed old numbers)

| # | Slide | Change |
|---|---|---|
| 5 | How DiaCausal works | step 4 also weight and low-sugar risk; step 6 "RAG: quoted, cited passages"; dashed = built separately, joins the chat app in October |
| 10 | Hardware & software | website (Netlify + Supabase); "Later (RAG)" → "RAG (built)" |
| 11 | System requirements | hypoglycaemia risk and weight change **Built**; + RAG and website rows |
| 14–16 | Architecture, data flow, sequence | "RAG layer (built)"; "(Oct)" removed |
| 22 | What's built | 150 engine, 33 RAG, 19 website, chat app 392 + 238 tests; RAG **Done** |
| 29 | Demo | website or Streamlit; backup video 112 s |
| 32 | Conclusion | cited evidence search working; next: one chat app, doctor review, IEEE paper |
| 33 | References | + [8] NMB-2017, [9] WHO 2018 |

## New content slides (28 Sept)

| # | Slide | Suggested presenter |
|---|---|---|
| 19 | Datasets – What We Use | Graceton |
| 20 | Dataset – Synthetic Cohort (How It Is Made) | Graceton |
| 21 | Dataset – Real Indian Data (NMB-2017) vs Synthetic | Graceton |
| 24 | Implementation – Website Screens | Advik |
| 25 | Implementation – Chat App Screens | Advik |
| 28 | Initial Results – Evidence Search (RAG) | Rhian |
| 31 | Progress – About 64% of the Whole Project | Pratham |
| 35–39 | Backup: why synthetic is valid · real Indian datasets · path to a hospital · phone screens · literature | whoever is asked |

Presenters (suggested): Pratham 1–3, 27, 31–34 · Rhian 4–7, 22–23, 26, 28 · Advik 8–13, 24–25, 30 ·
Graceton 14–21, 29. Speaker notes on every slide. With 34 main slides, keep about 20–25 s on each
design slide; if the slot is 12 minutes, move 24–25 and 13 to the backup section.
