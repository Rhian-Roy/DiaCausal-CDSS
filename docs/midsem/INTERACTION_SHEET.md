# Project Interaction Sheet: where each entry is covered

> Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

Group 28 · Domain AI/ML · Guide: Mr. Rahul Jadhav · Title: Intelligent Diabetes Clinical Decision Support System ·
Type: In-house. Coordinator: Dr. Rakhi Kalantri · HOD: Dr. M. Kiruthika.
Charts: `docs/midsem/timeline.png` and `gantt.png` (`python scripts/make_gantt.py`), also in the deck
(slides 12–13) and the report (Appendix A). The charts use only the sheet's own rows and wording.

## Second half of 2026

| Week, date | Task on the sheet | Guide's remark | Status | Where it is |
|---|---|---|---|---|
| 0 | Topic finalisation, feasibility | met guide, topic finalised | Signed | Report Ch 1 |
| 1 · 22 Jul | Topic selection presentation | 16 papers; comparison table; relevant papers; gaps identified | Signed | Report Ch 2, Table 2.1; deck slide 39 (backup) |
| 2 · 29 Jul | Abstract, introduction | abstract needs revision: yes | Signed; revised | Report Abstract, Ch 1 |
| 3 · 05 Aug | Review of literature | changes suggested | Signed; made | Report Ch 2 |
| SP-I · 12 Aug | Synopsis Presentation-I | — | Done | — |
| 4 · 19 Aug | Proposed system: problem, approach, scope | proposed system ok; **scope needs enhancement** | Signed | Report Ch 3; **deck slide 9 "Scope"** (in scope / out of scope / future scope) |
| 5 · 02 Sep | H/W, S/W requirements, timeline chart | requirement study done | Signed | Deck slides 10–13; report Ch 4, Appendix A |
| 6 · 09 Sep | Design: block, flow diagrams | block and flow ok; **working of the system: not done** | Signed | Deck slides 6–7, 14–16; **deck slide 17 "Working of the System"** (one real consultation, step by step) |
| 7 · 23 Sep | Implementation 25% | coding details; 25% done (refer timeline) | Signed | Deck slide 23 "Exactly What the 25% Covers", slides 22, 24; report Ch 5 |
| SP-II · 30 Sep | Synopsis Presentation-II | — | Today | This deck (35 slides + 5 backup) |
| 8 · 07 Oct | Implementation 40% + progress feedback | — | **Met 28 Sep** (Section 2) | Deck slides 25, 29 |
| 9 · 14 Oct | Implementation 60% + overall progress | — | **Met 29 Sep** (Section 3) | Deck slide 26: engine + RAG inside the chat app, all six stages run |
| 10 · 21 Oct | Implementation 80% + overall progress | — | Our target 3 Oct (Section 4a) | Better search: medical embeddings + reranker |
| 26–31 Oct | Guide evaluation | — | Planned | Doctor review and SUS study run in October |
| Nov | Final synopsis presentation (tentative) | — | Planned | — |
| Dec | 100% implementation; research paper (format, plagiarism, grammar, flow) | — | Our target 6 Oct for 100% (Section 4) | Real-data adapter, evaluation tools; paper draft once results are frozen |

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
| 1 | **The 25%** (deck slide 23): causal engine core (synthetic cohort, safety rules first, propensity + overlap, IPW/matching/AIPW, DR-learner with a 95% range) + chat app base (sign-in with CAPTCHA and authenticator, guards, patient panel, guardrails, voice) | Signed 23 Sep |
| 2 | Benchmark (20 cohorts) + 9 refutation checks, weight and low-sugar outcomes, evidence search (RAG: WHO + FDA, hybrid search, cited explanations, 60-question evaluation), website with accounts | Done 28 Sep (40%) |
| 3 | Causal engine and RAG inside the chat app (the three stages that used to say "skipped") | Done 29 Sep (60%) |
| 4 | (a) dense medical embeddings + reranker, target 3 Oct; (b) real-data adapter and evaluation tools, target 6 Oct | Planned |
