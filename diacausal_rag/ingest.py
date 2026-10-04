# diacausal_rag/ingest.py  (shim; removed in restructure step 9)
# This module was split into chunking.py and licence_gate.py, so the shim names what it re-exports.
from diacausal.config import RAG_CONFIG_PATH as CONFIG  # noqa: F401
from diacausal.config import ROOT, load_rag_config as load_config  # noqa: F401
from diacausal.rag.ingest.chunking import Chunk, _pieces, as_dicts, chunk_document, split_sections  # noqa: F401
from diacausal.rag.ingest.licence_gate import (  # noqa: F401
    CLEARED, CORPUS, SOURCES_CSV, LicenceError, ingest, is_confirmed, load_sources,
)
