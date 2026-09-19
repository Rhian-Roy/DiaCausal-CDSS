<!-- Owner: B | Model: Opus 5 | Effort: high | Branch: feat/rag | Start: Mon 28 Sep -->
# Prompt 7: Licence-cleared RAG with citations

**How to run:** in Claude Code type `/model`, choose **Opus 5**, set effort to **high**, then type:
`Do docs/prompts/07-rag.md exactly. First create and switch to the branch feat/rag from an up-to-date main.`

---
Read CLAUDE.md, RAG/sources.csv and causal_engine/rag_lite.py (older TF-IDF research code). Task: make rag_retrieval real. Licence rule: ingest ONLY files whose row in RAG/sources.csv has bucket exactly "cleared_ingest" ("cleared_ingest_PENDING" is refused until Member B changes it); ADA Standards, National Formulary of India, Harrison's, Joslin's and the RSSDI textbook are never ingested; verbatim_only sources are quoted unaltered with attribution, never paraphrased. Plan first and wait for my OK.
1. Ingestion script: refuses any file without a cleared row; extracts text with page and section headings; chunks by section (~300–500 words); stores source, version, section, page, licence with every chunk.
2. Retrieval: hybrid BM25 + a small local embedding model (pinned; no patient data leaves the machine); retrieve top-k per option and per guardrail reason. Build the query from the structured patient and the options, not raw free text alone.
3. Abstain: if the best score is below a threshold set on the evaluation set, return "no supporting passage" rather than a weak one.
4. Output: citations attached to each option and guardrail reason as {source, version, section, page, passage}. The passage is shown verbatim in the evidence drawer (design 18).
5. Evaluation: tests/rag_eval.yaml with 30 questions and the expected source+section; report recall@5 and MRR; add to check_all with a minimum bar.
6. Tests: uncleared file rejected; every returned citation has all fields; abstain works.
7. Write docs/explain/08-rag.md: chunking, hybrid search, why citations, one worked retrieval example, 5 viva questions.

---
When you are completely finished (all tests green):
1. Run `python3 scripts/check_all.py` and show me the last line.
2. Commit, push this branch, and open a pull request to main (use `gh pr create`; if `gh` is not logged in, walk me through `gh auth login` step by step).
3. Give me the pull-request link.
4. Write a 5-line plain-English summary of what changed that I can paste into our team WhatsApp.
Do NOT merge the pull request — I will get it reviewed first.
