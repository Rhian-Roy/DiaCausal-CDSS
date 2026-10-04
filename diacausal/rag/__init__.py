"""DiaCausal RAG pipeline (diacausal.rag; moved from diacausal_rag in restructure step 6) (the "RAG Pipeline" column of the team flow chart).

Research prototype for clinician evaluation; not a marketed medical device;
not for unsupervised clinical use.

    ingest/       licence_gate.py (only confirmed "cleared_ingest" rows of knowledge_sources/sources.csv), section-aware,
                  sentence-aware chunks of about 400 words with source, version, section and page
                  (chunking.py); pdf_text.py: an approved PDF -> corpus text with page markers and headings
    index/        bm25.py (keywords) and tfidf.py (vectors)
    retrieve/     hybrid.py: BM25 + TF-IDF, reciprocal rank fusion, evidence JSON (or INSUFFICIENT_EVIDENCE: weak
                  match, or the question's words poorly covered); rerank.py: the reranker slot
    explain.py    cited explanation: template (offline, quotes) or Ollama (a local model),
                  every model answer checked sentence by sentence against the passages
    evaluate.py   recall@5, abstention, citation precision and dose leaks on eval/rag_gold.csv

Still to do: a medical embedding model in place of TF-IDF, a cross-encoder reranker, and the doctor's
review of the gold set. Dose text never enters the index and is never shown.
"""

from diacausal import INTENDED_USE  # noqa: E402,F401
