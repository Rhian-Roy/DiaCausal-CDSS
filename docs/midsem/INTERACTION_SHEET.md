# Project Interaction Sheet: where each entry is covered

> Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

Group 28 · Domain AI/ML · Guide: Mr. Rahul Jadhav · Title: Intelligent Diabetes Clinical Decision Support System ·
Type: In-house. Coordinator: Dr. Rakhi Kalantri · HOD: Dr. M. Kiruthika.
Charts: `docs/midsem/timeline.png` and `gantt.png` (`python scripts/make_gantt.py`), also in the deck
(slides 12–13) and the report (Appendix A).

## Second half of 2026

| Week, date | Task on the sheet | Guide's remark | Status | Where it is |
|---|---|---|---|---|
| 0 (vacation) | Topic finalisation, feasibility | met guide, topic finalised | Signed | Report Ch 1 |
| 1 · 22 Jul | Topic selection presentation | 16 papers; comparison table; relevant papers; gaps identified | Signed | Report Ch 2, Table 2.1; deck slide 39 (backup) |
| 2 · 29 Jul | Abstract, introduction | abstract needs revision: yes | Signed; revised | Report Abstract, Ch 1 |
| 3 · 05 Aug | Review of literature | changes suggested | Signed; made | Report Ch 2 |
| SP-I · 12 Aug | Synopsis Presentation-I | — | Done | — |
| 4 · 19 Aug | Proposed system: problem, approach, scope | proposed system ok; **scope needs enhancement** | Signed | Report Ch 3; **deck slide 9 "Scope"** (in scope / out of scope / future scope) |
| 5 · 02 Sep | H/W, S/W requirements, timeline chart | requirement study done | Signed | Deck slides 10–13; report Ch 4, Appendix A |
| 6 · 09 Sep | Design: block, flow diagrams | block and flow ok; **working of the system: not done** | Signed | Deck slides 6–7, 14–16; **deck slide 17 "Working of the System"** (one real consultation, step by step) |
| 7 · 23 Sep | Implementation 25% | coding details; 25% done (refer timeline) | Signed | Deck slides 22–23; report Ch 5 |
| SP-II · 30 Sep | Synopsis Presentation-II | — | Today | This deck (39 slides) |
| 8 · 07 Oct | Implementation 40% + feedback | — | **Already met** (Sections 1–2) | Deck slides 22–31 |
| 9 · 14 Oct | Implementation 60% | — | Our target 3 Oct (Section 3) | Engine + RAG inside the chat app |
| 10 · 21 Oct | Implementation 80% | — | Our target 6 Oct (Section 4) | Better search, real-data adapter, evaluation tools |
| 26–31 Oct | Guide evaluation | — | Planned | Doctor review and SUS study run in October |
| Nov | Final synopsis presentation (tentative) | — | Planned | — |
| Dec | 100% implementation; research paper (format, plagiarism, grammar, flow) | — | Planned | Paper draft starts once results are frozen |

## First half of 2027

| When | Task on the sheet | Plan |
|---|---|---|
| January | Project evaluation: complete project presentation | Full demo: chat app with engine + RAG, website, results |
| February | PCUBE (poster, presentation, model) | Poster from the report figures; the website is the model |
| February | Research paper revision (plagiarism count, format, flow, diagram clarity, language, journal/conference) | Venue decided with the guide |
| February | Black book (soft copy for plagiarism check), paper submission, guide evaluation, final black book with the interaction sheet | Report LaTeX becomes the black book |

## The four implementation sections (the sheet asks for four)

| Section | Contents | Status |
|---|---|---|
| 1 | Causal engine core (cohort, safety rules, propensity, IPW/AIPW/matching, DR-learner, benchmark) + chat app base (UI, guards, sign-in, patient panel, guardrails, voice) | Done by 25 Sep |
| 2 | Evidence search (RAG: WHO + FDA, hybrid search, cited explanations, 60-question evaluation), weight and low-sugar outcomes, website with accounts | Done by 28 Sep |
| 3 | Causal engine and RAG inside the chat app (the three "skipped" stages) | In progress; target 3 Oct |
| 4 | Dense medical embeddings + reranker, real-data adapter, evaluation tools | Target 6 Oct |
