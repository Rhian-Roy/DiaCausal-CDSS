# Changes to the team's deck (28–29 Sept)

> Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

Input: the team's `Intelligent_Diabetes_Clinical_Decision_Support_System.pptx` (24 slides).
Output: `Intelligent_Diabetes_CDSS_MidSem_updated.pptx` (+ a `.pdf` preview): **35 slides + 5 backup** (40), same
template, fonts and colours. Every number comes from `results/`, `docs/TESTING.md`, `DATASETS.md` or the engine
itself. For the final PDF, export from PowerPoint / Google Slides (not LibreOffice) so the deck's own fonts are used.

## Following the Project Interaction Sheet (29 Sept)

| # | Slide | Why |
|---|---|---|
| 9 | **Proposed System – Scope** (new): in scope, out of scope, future scope | Week 4 remark: "scope needs enhancement" |
| 12 | **Timeline / Gantt Chart** (replaced): only the sheet's own rows and words (weeks 0–10, the two synopsis presentations, guide evaluation, Nov, Dec, Jan, Feb); nothing that is not on the sheet | Week 5; sheet note: "timeline chart should reflect implementation into four sections" |
| 13 | **Timeline Chart – Interaction Sheet** (new): every sheet entry, its date and status | Week 5 |
| 17 | **System Design – Working of the System** (new): one real consultation, step by step, with the engine's numbers | Week 6 remark: "working of the system: not done" |
| 23 | **Implementation – Exactly What the 25% Covers** (new): the six steps our guide signed on 23 Sep, where each lives in the code, and where the 25% ends | Week 7: "coding details; 25% done" |
| 31 | Completed vs Planned: planned side keyed to sheet weeks 8–10, guide evaluation, Nov, Dec, Jan–Feb | Weeks 8–10 |
| 32 | Progress: "about 75%": 25% by 23 Sep (signed), 40% met 28 Sep, 60% met 29 Sep | Weeks 7–9 |
| 40 | Backup – Literature Comparison | Week 1: 16 papers, comparison table |
| 3 | Outline wording: scope, interaction-sheet timeline, working of the system | — |

## Corrected (they said "planned" or showed old numbers)

| # | Slide | Change |
|---|---|---|
| 5 | How DiaCausal works | step 4 also weight and low-sugar risk; step 6 "RAG: quoted, cited passages"; all arrows solid: "all seven steps run in the chat app (29 Sep)" |
| 10 | Hardware & software | website (Netlify + Supabase); "Later (RAG)" → "RAG (built)" |
| 11 | System requirements | hypoglycaemia risk and weight change **Built**; + RAG and website rows |
| 14–15 | Architecture, data flow | "RAG layer (built)", "(Oct)" removed, dashed (planned) arrows made solid |
| 16 | Use case and sequence | "RAG (Oct)" → "RAG"; the "cite evidence" call is solid. The remaining dashed arrows are UML return messages and lifelines, which are dashed by convention |
| 22 | What's built | 150 engine, 33 RAG, 19 website tests; chat app 401 + 246; RAG **Done** |
| 26 | Chat app screens | the reply now shows the engine's estimates with 95% ranges and the quoted, cited evidence |
| 30 | Demo | website or Streamlit; backup video 112 s |
| 33 | Conclusion | engine and cited evidence in one chat app; next: better search model, doctor review, IEEE paper |
| 34 | References | + [8] NMB-2017, [9] WHO 2018 |

## New content slides (28–29 Sept)

| # | Slide | Suggested presenter |
|---|---|---|
| 19 | Datasets – What We Use | Graceton |
| 20 | Dataset – Synthetic Cohort (How It Is Made) | Graceton |
| 21 | Dataset – Real Indian Data (NMB-2017) vs Synthetic | Graceton |
| 23 | Implementation – Exactly What the 25% Covers | Rhian |
| 25 | Implementation – Website Screens | Advik |
| 26 | Implementation – Chat App Screens | Advik |
| 29 | Initial Results – Evidence Search (RAG) | Rhian |
| 32 | Progress – About 75% of the Whole Project | Pratham |
| 36–40 | Backup: why synthetic is valid · real Indian datasets · path to a hospital · phone screens · literature | whoever is asked |

Presenters (as in the speaker notes): Pratham 1–3, 28, 32–33, 35 · Rhian 4–7, 22–24, 27, 29 ·
Advik 8–13, 25–26, 31, 34 · Graceton 14–21, 30 (Rhian at the laptop). Speaker notes on every slide. With 35 main slides, keep about 20–25 s on each
design slide; if the slot is 12 minutes, move 25, 13 and 16 to the backup section.
