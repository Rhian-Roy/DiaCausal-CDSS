"""DiaCausal RAG pipeline (the "RAG Pipeline" column of the team flow chart).

Research prototype for clinician evaluation; not a marketed medical device;
not for unsupervised clinical use.

    ingest.py     licence gate (only confirmed "cleared_ingest" rows of RAG/sources.csv), section-aware,
                  sentence-aware chunks of about 400 words with source, version, section and page
    pdf_text.py   an approved PDF -> corpus text with page markers and headings
    retrieve.py   BM25 + TF-IDF vector search, reciprocal rank fusion, a reranker slot, and evidence
                  JSON — or INSUFFICIENT_EVIDENCE (weak match, or the question's words poorly covered)
    explain.py    cited explanation: template (offline, quotes), Gemini (free, online) or Ollama (local),
                  every model answer checked sentence by sentence against the passages
    evaluate.py   recall@5, abstention, citation precision and dose leaks on eval/rag_gold.csv

Still to do: a medical embedding model in place of TF-IDF, a cross-encoder reranker, and the doctor's
review of the gold set. Dose text never enters the index and is never shown.
"""

INTENDED_USE = (
    "Research prototype for clinician evaluation; not a marketed medical device; "
    "not for unsupervised clinical use."
)
