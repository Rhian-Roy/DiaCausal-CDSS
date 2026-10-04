"""EvidenceChunkV1 and EvidenceBundleV1 (retrieval, plan 8.4 and 8.7). Passages are shown as stored."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from diacausal.api.schemas.base import V1


class ScoresV1(V1):
    bm25: float
    dense: float | None = Field(default=None, description="null until the dense index exists (P18)")
    rrf: float


class EvidenceChunkV1(V1):
    chunk_id: str
    source: str
    version: str
    section: str
    page: int | None = Field(default=None, description="null for a web page")
    licence: str
    text: str
    scores: ScoresV1


class EvidenceBundleV1(V1):
    status: Literal["OK", "INSUFFICIENT_EVIDENCE"]
    index_version: str
    chunks: list[EvidenceChunkV1]
    reason: str | None = Field(default=None, description="why, when status is INSUFFICIENT_EVIDENCE")
