# Changes to the team's deck (28 Sept)

> Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

Input: the team's `Intelligent_Diabetes_Clinical_Decision_Support_System.pptx` (24 slides).
Output: `Intelligent_Diabetes_CDSS_MidSem_updated.pptx` (**30 main slides + 5 backup**), same template, fonts and
colours. Every number comes from `results/`, `docs/TESTING.md` or `DATASETS.md`. Export the PDF from
PowerPoint / Google Slides, not LibreOffice, so the deck's own fonts are used.

## Corrected (they said "planned" or showed old numbers)

| New # | Slide | Change |
|---|---|---|
| 3 | Outline | + "Datasets (synthetic and real Indian data)", "Implementation and screens", "…, progress" |
| 5 | How DiaCausal works | step 4 now also weight and low-sugar risk; step 6 "RAG: quoted, cited passages"; legend "Dashed = built separately; joins the chat app in October" |
| 9 | Hardware & software | website (Netlify + Supabase) in Demo; "Later (RAG)" → "RAG (built)" with what it uses |
| 10 | System requirements | Hypoglycaemia risk and weight change: Planned → **Built**; + "Evidence with citations (RAG)" and "Website with accounts (MFA)": Built |
| 11 | Gantt | row labels: "Causal engine, RAG core, mid-sem"; "RAG upgrades and engine fixes"; "Chat-app integration, paper draft" (dates unchanged) |
| 12–14 | Architecture, data flow, sequence | "RAG layer (built)", "(Oct)" removed; dashed now means "built separately; joins the chat app/API in October" |
| 19 | What's built | 139 → **150 engine, 33 RAG, 19 website; chat app 392 + 238** tests; RAG pipeline Started → **Done**; weight/low-sugar and website rows |
| 26 | Demo | live demo: website or Streamlit; backup video 112 s |
| 27 | Completed vs planned | weight/low-sugar and RAG moved to Completed; October: embeddings + reranker, doctor review, chat-app integration, paper, SUS study, real-data step |
| 29 | Conclusion | "Causal engine and cited evidence search working"; "Next: one chat app, doctor review, IEEE paper" |
| 30 | References | + [8] NMB-2017 (Nagarathna 2020), [9] WHO 2018 guideline |

Speaker notes updated on every changed slide.

## New slides (with speaker notes; suggested presenter)

| # | Slide | Presenter |
|---|---|---|
| 16 | Datasets – What We Use (6 datasets: real or synthetic, size, purpose) | Graceton |
| 17 | Dataset – Synthetic Cohort (5 generation steps + first 8 rows) | Graceton |
| 18 | Dataset – Real Indian Data (NMB-2017 first rows + real-vs-synthetic chart) | Graceton |
| 21 | Implementation – Website Screens (4 screens) | Advik |
| 22 | Implementation – Chat App Screens (sign-in, authenticator, reply, guard) | Advik |
| 25 | Initial Results – Evidence Search (RAG): recall@5 0.933, precision 1.000, 0 dose leaks, abstention 0.800 (target 0.9), answered 0.978 | Rhian |
| 28 | Progress – About 64% of the Whole Project (weighted table) | Pratham |
| 32–35 | Backup (after Thank You, for questions): why synthetic data is valid · real Indian datasets · path to a real hospital · phone screens | whoever is asked |

Time: the seven new slides add about 3–4 minutes; if the slot is 12 minutes, show 21/22 quickly or move them to backup.
