# Presentation Guide and Claude Design Prompts

**For:** Graceton (builds the slides) · everyone (presents)

## When to make it

- **Saturday 26:** slides 1–14 — nothing on them depends on results.
- **Monday 28:** slides 15–19 — results, demo and "completed vs planned", once the benchmark has run.
- **Tuesday 29:** rehearse twice, show the guide, freeze by 9 PM.

## The college format (from the department's sample deck)

- 4:3 slides, white background.
- Titles centred, Times New Roman, navy #002060, with a thin navy line under the title across the slide.
- The college logo (fcritlogo.jpg) in the top-right corner of every content slide.
- Body text in Calibri, black, 18–24 pt, key words in bold; sub-headings navy, bold and underlined.
- **Slide 1:** a header box with the logo on the left and, on the right: "Agnel Charities'" (italic), "Fr. C. Rodrigues Institute of Technology, Vashi" (bold, large), "(An Autonomous Institute & Permanently Affiliated to University of Mumbai)" (bold, red), "Computer Engineering Department" (bold). Below it, a large navy banner with white text "Major Project Progress Presentation-II" and "B.Tech (Computer) Sem - VII", then "2026-27" in large bold grey.
- **Slide 2:** a navy banner across the top with the project title in white and the logo at the right; below it the group number, the four names with roll numbers, and the guide.
- **Last slide:** "Thank You!" in large bold black, framed by four crossing navy lines.

## Slide plan (22 slides, following the mentor's six items)

| # | Title | What's on it | Visual | Presenter |
|---|---|---|---|---|
| 1 | Title | College title slide | — | Pratham |
| 2 | Project and team | Title, Group 28, names, roll numbers, guide | Banner | Pratham |
| 3 | Presentation Outline | The six items, then completed vs planned | List | Pratham |
| 4 | Proposed System — the problem | Second-line choice after metformin; why comparisons mislead | Worked-example table | Rhian |
| 5 | Proposed System — how it works | Guardrails → propensity/overlap → AIPW/DR-learner → cost → (RAG) → doctor | Flow diagram | Rhian |
| 6 | Proposed System — safety rules | Six safety rules and the intended-use statement | List | Advik |
| 7 | Hardware & Software Requirements | Development, demo and client tiers; software stack | Table | Advik |
| 8 | System Requirements | Key functional and non-functional requirements | Two columns | Advik |
| 9 | Timeline / Gantt Chart | Completed vs planned, with a marker at 30 Sept | Gantt | Advik |
| 10 | System Design — architecture | Layered block diagram | Diagram | Graceton |
| 11 | System Design — data flow | DFD level 0 and level 1 | Diagrams | Graceton |
| 12 | System Design — use case and sequence | Actors and one consultation | UML | Graceton |
| 13 | System Design — data and API | Rules table columns; POST /api/v1/recommend | Tables | Graceton |
| 14 | Implementation — what's built | Module status with evidence | Status table | Rhian |
| 15 | Implementation — how the code works | Walk-through with two short code snippets | Code | Rhian |
| 16 | Initial Results — accuracy | Naive vs IPW vs AIPW against the truth | Table + chart | Rhian |
| 17 | Initial Results — plots | Overlap, balance, patient-level effects | Three figures | Pratham |
| 18 | Demo | Three preset patients, then live | Screenshots | Graceton |
| 19 | Completed vs planned | Done so far vs the October plan | Two columns | Advik |
| 20 | Conclusion | Four points | List | Pratham |
| 21 | References | IEEE style | List | Advik |
| 22 | Thank You | Framed | — | Everyone |

## Claude Design prompt — slides 1–14 (Saturday)

Attach **fcritlogo.jpg** and the department's sample deck PDF, then paste:

```text
Create a 22-slide presentation for our college's mid-semester project review. It must match our college's slide format exactly (described below) — that matters more than style.

Project: DiaCausal — Intelligent Diabetes Clinical Decision Support System using Causal Inference and RAG. Group No. 28, Fr. C. Rodrigues Institute of Technology, Vashi. Members: Pratham Pawar (1023226), Graceton Santhmayor (1022246), Rhian Roy Kuttikadan (1023268), Advik Saxena (1023245). Guide: Mr. Rahul Jadhav. Event: Major Project Progress Presentation-II, B.Tech (Computer) Sem VII, 2026-27.

FORMAT (follow exactly):
- 4:3 slides (10 x 7.5 in), white background.
- Slide titles centred, Times New Roman, navy #002060, about 36 pt, with a thin navy horizontal line under the title across the slide.
- The attached college logo at the top-right corner of every content slide.
- Body text Calibri, black, 18-24 pt; key words bold; sub-headings navy, bold, underlined.
- Slide 1: a white header box with the logo on the left and, on the right, stacked and centred: "Agnel Charities'" (italic), "Fr. C. Rodrigues Institute of Technology, Vashi" (bold, large), "(An Autonomous Institute & Permanently Affiliated to University of Mumbai)" (bold, red), "Computer Engineering Department" (bold). Below it a large navy #002060 banner with white text on two lines: "Major Project Progress Presentation-II" and "B.Tech (Computer) Sem - VII". Below the banner, "2026-27" in large bold grey.
- Slide 2: a navy banner across the top with the project title in white and the logo at the right. Below it: "Group No. 28", the four names with roll numbers in two columns, and "Guide: Mr. Rahul Jadhav".
- Final slide: "Thank You!" in large bold black, framed by four long navy lines crossing like a # grid.
- At most 6 bullets per slide and 12 words per bullet. No stock photos, no emojis. Never use green to mean "recommended" (amber = caution, red = excluded, grey = insufficient evidence). Do not invent any numbers.

SLIDES — make 1-14 complete now. Make 15-19 as clean layouts with clearly marked placeholders that I will fill on Monday.
1. Title slide (format above).
2. Project and team (format above).
3. Presentation Outline: Proposed System; Hardware & Software Requirements; Timeline / Gantt Chart; System Design; Implementation; Initial Results / Demo; Work Completed vs Planned; Conclusion.
4. Proposed System - The Problem. Bullets: "After metformin, doctors choose between SGLT2 inhibitors, DPP-4 inhibitors and sulfonylureas"; "Old records mislead: different patients get different drugs". Table: High starting HbA1c - SGLT2i 300 patients -1.2, SU 100 patients -1.0; Lower starting HbA1c - SGLT2i 100 patients -0.6, SU 300 patients -0.5. Highlight: "Naive difference -0.425 vs fair difference -0.15 (about 3x too big)". Caption: "Illustrative synthetic numbers; HbA1c change in %".
5. Proposed System - How DiaCausal Works. Flow diagram: Patient details -> Safety rules (cited drug labels) -> Propensity and overlap check -> Each option's 6-month HbA1c change with a 95% range, or "insufficient evidence" -> Cost (INR/month) -> Evidence with citations (RAG, October) -> Doctor decides. Side note: "Every request is logged".
6. Proposed System - Safety Rules: The doctor always decides; Safety rules run before any estimate; Doses and thresholds only from cited tables, never from AI; Refuse to guess ("insufficient evidence"); Every estimate has a 95% range; Every request is logged. Footer box: "Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use."
7. Hardware & Software Requirements (table). Development: laptop with 8 GB+ RAM (MacBook Air, Apple silicon); Python 3.12, NumPy, pandas, scikit-learn, Matplotlib, pytest, Git/GitHub, Claude Code. Demo: same laptop offline, or Streamlit Community Cloud; Streamlit, FastAPI, Uvicorn. Client: any modern web browser. Later (RAG): PDF parser, BM25 search, vector store, language model (API or local via Ollama).
8. System Requirements. Functional: patient input with unit checks; safety rules with cited reasons; estimate with 95% range or "insufficient evidence"; hypoglycaemia risk and weight change; cost lookup (INR/month); audit log; REST API. Non-functional: under 3 s per request; 100% of requests logged; at least 80% test coverage; reproducible (fixed random seeds); intended-use statement on every screen; accessible (WCAG 2.1 AA).
9. Timeline / Gantt Chart, July-December 2026: Topic and proposal (July - mid-August, done); Literature and dataset research (August - 11 September, done); Dataset decision (12-14 September, done); Causal engine and mid-sem (15-30 September, in progress); RAG ingestion and engine fixes (1-9 October); Results frozen and doctor review (10-16 October); Integration, RAG evaluation, paper draft (17-23 October); Final report, paper, viva (24-30 October); Practical exams (31 October - 7 November); Theory exams (18-30 November); Final submission (December). Completed bars navy, planned bars grey, a vertical marker "Today: 30 Sept".
10. System Design - Architecture. Layered block diagram: User interface (Streamlit / web) -> FastAPI service -> Safety rules engine (rules.csv) -> Causal engine (propensity, overlap, AIPW, DR-learner) -> Cost lookup; FastAPI -> RAG layer -> approved guideline documents; FastAPI -> Audit log.
11. System Design - Data Flow. DFD level 0: Clinician <-> DiaCausal; guideline documents -> DiaCausal; DiaCausal -> audit store. DFD level 1: 1 Validate -> 2 Safety rules -> 3 Causal engine -> 4 Cost lookup -> 5 RAG explanation -> 6 Log and display.
12. System Design - Use Case and Sequence. Actors: Clinician (enter patient, view comparison, view evidence, export summary); Evaluator (review logs, run benchmark); Admin (manage rules and sources). Sequence for one consultation: Clinician -> UI -> API -> Safety rules -> Causal engine -> RAG -> Audit log -> UI -> Clinician.
13. System Design - Data and API. Rules table columns: rule id, drug class, condition, action, message, source, section, status. Prices table: drug, INR per month, as-of date, source. POST /api/v1/recommend - input: patient details; output: each option's estimate with 95% range or "insufficient evidence", exclusions with sources, versions, request id.
14. Implementation - What's Built. Table with columns Module | Status | Evidence. Rows: synthetic patient generator; safety rules; propensity and overlap check; naive / IPW / AIPW; DR-learner; metrics; benchmark; demo app; API; automated tests. Put "update Monday" in the Status column.
15. Implementation - How the Code Works (placeholder: two small code boxes).
16. Initial Results - Accuracy (placeholder: results table and one chart).
17. Initial Results - Plots (placeholder: three figures).
18. Demo (placeholder: three screenshots).
19. Work Completed vs Planned (placeholder: two columns).
20. Conclusion: causal engine working on India-calibrated synthetic data; safety rules before any estimate; honest uncertainty and refusal to guess; next: RAG with citations, doctor review, IEEE paper.
21. References (IEEE style):
[1] B. M. Shields et al., "Patient stratification for determining optimal second-line and third-line therapy for type 2 diabetes: the TriMaster study," Nat. Med., vol. 29, pp. 376-383, 2023.
[2] J. M. Dennis et al., "Development of a treatment selection algorithm for SGLT2 and DPP-4 inhibitor therapies in people with type 2 diabetes," Lancet Digit. Health, vol. 4, no. 12, pp. e873-e883, 2022.
[3] L. M. Gudemann et al., "Validation of an algorithm for selection of SGLT2 and DPP4 inhibitor therapies in people with type 2 diabetes across major UK ethnicity groups," Lancet Reg. Health Eur., vol. 61, 101547, 2026.
[4] R. M. Anjana et al., "Metabolic non-communicable disease health report of India: the ICMR-INDIAB national cross-sectional study (ICMR-INDIAB-17)," Lancet Diabetes Endocrinol., vol. 11, no. 7, pp. 474-489, 2023.
[5] E. H. Kennedy, "Towards optimal doubly robust estimation of heterogeneous causal effects," Electron. J. Stat., vol. 17, no. 2, pp. 3008-3049, 2023.
[6] P. Lewis et al., "Retrieval-augmented generation for knowledge-intensive NLP tasks," in Proc. NeurIPS, 2020.
[7] A. G. Cashin et al., "Transparent reporting of observational studies emulating a target trial - the TARGET statement," JAMA, vol. 334, no. 12, pp. 1084-1093, 2025.
22. Thank You (format above).

Add speaker notes to every slide: at most 80 words, plain English.
```

## Claude Design prompt — add results (Monday)

Attach `results_table.tex` (or the summary), the figures from `results/figures/`, and the three demo screenshots, then paste:

```text
Update slides 14-19 of this deck with the attached files. Slide 14: fill the Status and Evidence columns from the attached summary. Slide 15: show two short code excerpts I paste below. Slide 16: build the results table using only numbers from the attached results table, plus the ate_vs_truth chart. Slide 17: overlap.png, love_plot.png and cate_recovery.png, each with a one-line caption. Slide 18: the three demo screenshots with one-line captions. Slide 19: two columns, "Completed" and "Planned (October)". Keep the college format exactly, add speaker notes of at most 80 words, and do not invent any numbers.
```

## If Claude Design can't give you a .pptx file

- **Fallback A (uses the $100 cloud credit):** upload this document to the repo's `docs/` folder, then in a Claude Code cloud session paste:

```text
Create presentation/DiaCausal_MidSem.pptx with python-pptx, following docs/04_Presentation_PPT_Guide.md exactly: the college format, the 22-slide plan, and the slide contents in the Claude Design prompt. Insert figures from results/figures/ and screenshots from screens/. Add speaker notes. Commit the file.
```

- **Fallback B:** on Monday, send the results files in a chat and ask for the final .pptx in the college format.

## Live demo script (3 minutes — Graceton presents, Rhian drives)

1. The app is already open and warmed up.
2. Preset 1, a typical patient: read out one estimate and its 95% range.
3. Preset 2, eGFR 40 with a history of pancreatitis: point to the red exclusion and the amber caution, and read out the source.
4. Preset 3: show "insufficient evidence" and explain why refusing is safer than guessing.
5. Open "Why causal?" and walk through the worked example.
6. Show one line of the audit log.

If anything fails, play the recorded video without apologising at length: "Here is the same demo, recorded yesterday."

## Rehearsal checklist

- [ ] 12–15 minutes in total; about 3 minutes each
- [ ] Every number on a slide comes from the `results/` files
- [ ] Say "synthetic data" whenever you show results
- [ ] Practise the ten hardest questions in document 06
