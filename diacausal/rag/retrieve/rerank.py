"""The reranker slot (split out of retrieve.py in restructure step 6). Identity today; a cross-encoder goes here in October."""

from __future__ import annotations


def rerank(question: str, candidates: list[int]) -> list[int]:
    """Candidate passage indices, best first. Today: unchanged."""
    return candidates
