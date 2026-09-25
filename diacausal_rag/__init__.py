"""DiaCausal RAG pipeline — EARLY SKELETON (next phase, 1–16 October).

Research prototype for clinician evaluation; not a marketed medical device;
not for unsupervised clinical use.

Follows the "RAG Pipeline" column of the team flow chart:
    ingest.py    document ingestion: only licence-cleared sources (RAG/sources.csv bucket
                 "cleared_ingest"), section-aware chunks of about 400 words, metadata on each chunk
    retrieve.py  hybrid search (BM25 keywords + a vector retriever), reciprocal rank fusion,
                 a reranker slot, and structured evidence JSON — or INSUFFICIENT_EVIDENCE

Not built yet (October): a medical embedding model in place of the TF-IDF vector retriever, a
cross-encoder reranker, the evidence-fusion layer, and the LLM that writes cited explanations.
Passages that contain dose text are never shown (doses come only from the drug label).
"""

INTENDED_USE = (
    "Research prototype for clinician evaluation; not a marketed medical device; "
    "not for unsupervised clinical use."
)
