"""The licence gate: only documents whose licence a team member has confirmed are ingested (split out of ingest.py).

Plain English: we only read documents whose licence lets us copy them into our index (bucket "cleared_ingest" in
knowledge_sources/sources.csv, and `checked_by` filled in by a person). Anything else raises LicenceError.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import TYPE_CHECKING

from diacausal.config import KNOWLEDGE_DIR, load_rag_config

if TYPE_CHECKING:
    from diacausal.rag.ingest.chunking import Chunk

SOURCES_CSV = KNOWLEDGE_DIR / "sources.csv"
CORPUS = KNOWLEDGE_DIR / "corpus"
CLEARED = "cleared_ingest"


class LicenceError(ValueError):
    """A document whose source is not licence-cleared for ingestion."""


def is_confirmed(source: dict) -> bool:
    """A licence counts only after a team member has checked it: "checked_by" filled, not a draft."""
    who = (source.get("checked_by") or "").strip().lower()
    return bool(who) and "draft" not in who and "to confirm" not in who


def load_sources(path: Path = SOURCES_CSV) -> dict[str, dict]:
    with Path(path).open(newline="", encoding="utf-8") as fh:
        return {row["id"]: row for row in csv.DictReader(fh)}


def ingest(corpus: Path = CORPUS, sources: dict[str, dict] | None = None, chunk_words: int | None = None) -> list[Chunk]:
    """Read corpus/manifest.csv (file,source_id) and chunk every listed file."""
    # chunking.py imports this module (for LicenceError and CLEARED), so it is imported here, when needed, not at the top
    from diacausal.rag.ingest.chunking import chunk_document

    sources = sources if sources is not None else load_sources()
    chunk_words = int(chunk_words or load_rag_config()["chunk_words"])
    manifest = Path(corpus) / "manifest.csv"
    if not manifest.exists():
        return []
    chunks: list[Chunk] = []
    parts: dict[str, int] = {}
    with manifest.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            source = sources.get(row["source_id"])
            if source is None:
                raise LicenceError(f"{row['file']}: unknown source id {row['source_id']!r}")
            if not is_confirmed(source):
                raise LicenceError(f"{row['file']}: the licence of {source['id']} is still a draft; "
                                   "a team member must confirm it and fill checked_by first")
            part = parts.get(source["id"], 0)
            parts[source["id"]] = part + 1
            chunks += chunk_document((Path(corpus) / row["file"]).read_text(encoding="utf-8"), source, chunk_words, part)
    return chunks
