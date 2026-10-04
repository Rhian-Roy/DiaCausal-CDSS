# diacausal_rag/retrieve.py  (shim; removed in restructure step 9)
# This module was split into index/bm25.py, index/tfidf.py, retrieve/hybrid.py and retrieve/rerank.py, so the shim
# names what it re-exports.
from diacausal.rag.index.bm25 import BM25, TOKEN, tokens  # noqa: F401
from diacausal.rag.retrieve.hybrid import DOSE, WITHHELD, Retriever, index_text, rrf  # noqa: F401
