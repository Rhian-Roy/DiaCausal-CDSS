"""Loads the causal engine (diacausal_engine/) and the evidence search (diacausal_rag/) once.

Both live at the repository root, next to backend/, so the root is put on the import path
here and nowhere else. Loading is lazy: the first chat that needs the engine fits it on the
fixed synthetic reference cohort (a few seconds); every later message reuses it.
Nothing here ever sees patient values in a log line.
"""

from __future__ import annotations

import sys
import threading
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_lock = threading.Lock()


@lru_cache(maxsize=1)
def causal_engine():
    """diacausal_engine.recommend.Engine, fitted once."""
    with _lock:
        from diacausal_engine.recommend import get_engine

        return get_engine()


@lru_cache(maxsize=1)
def retriever():
    """diacausal_rag.retrieve.Retriever over the licence-cleared corpus."""
    with _lock:
        from diacausal_rag.ingest import ingest
        from diacausal_rag.retrieve import Retriever

        return Retriever(ingest())


def dose_pattern():
    from diacausal_engine.recommend import DOSE_PATTERN

    return DOSE_PATTERN
