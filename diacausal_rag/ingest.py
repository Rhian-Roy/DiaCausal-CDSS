"""Document ingestion: licence gate, section-aware chunking, metadata on every chunk.

Plain English: we only read documents whose licence lets us copy them into our index
(bucket "cleared_ingest" in RAG/sources.csv). Each document is a text file whose sections start
with a line "## Section name" (and optionally "[page N]" markers). We cut each section into
pieces of about 400 words — never mixing two sections — and label every piece with where it came
from, so every sentence we show later can be cited.
"""

from __future__ import annotations

import csv
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SOURCES_CSV = ROOT / "RAG" / "sources.csv"
CORPUS = Path(__file__).resolve().parent / "corpus"
CONFIG = Path(__file__).resolve().parent / "config.yaml"
CLEARED = "cleared_ingest"


class LicenceError(ValueError):
    """A document whose source is not licence-cleared for ingestion."""


def is_confirmed(source: dict) -> bool:
    """A licence counts only after a team member has checked it: "checked_by" filled, not a draft."""
    who = (source.get("checked_by") or "").strip().lower()
    return bool(who) and "draft" not in who and "to confirm" not in who


def load_config(path: Path = CONFIG) -> dict:
    raw = yaml.safe_load(Path(path).read_text())
    for key, entry in raw.items():
        if not entry.get("source") or entry.get("status") not in ("CITED", "ASSUMED-DIRECTIONAL", "TEAM-SET"):
            raise ValueError(f"diacausal_rag/config.yaml: {key} needs a source and a valid status")
    return {k: v["value"] for k, v in raw.items()}


def load_sources(path: Path = SOURCES_CSV) -> dict[str, dict]:
    with Path(path).open(newline="", encoding="utf-8") as fh:
        return {row["id"]: row for row in csv.DictReader(fh)}


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    text: str
    source_id: str
    title: str
    version: str
    section: str
    page: str
    licence_bucket: str


_PAGE = re.compile(r"\[page (\d+)\]")


def split_sections(text: str) -> list[tuple[str, str, str]]:
    """[(section title, page the section starts on, section text)] from '## Title' headings."""
    sections: list[tuple[str, str, str]] = []
    title, page, start_page, buf = "Untitled", "", "", []

    def flush() -> None:
        body = " ".join(buf).strip()
        if body:
            sections.append((title, start_page, body))

    for line in text.splitlines():
        marker = _PAGE.search(line)
        if line.startswith("## "):
            flush()
            buf, title, start_page = [], _PAGE.sub("", line[3:]).strip(), page
            if marker:
                page = start_page = marker.group(1)
            continue
        if marker:
            page = marker.group(1)
            if not buf:
                start_page = page
        buf.append(_PAGE.sub("", line))
    flush()
    return sections


def chunk_document(text: str, source: dict, chunk_words: int) -> list[Chunk]:
    if source.get("bucket") != CLEARED:
        raise LicenceError(f"{source.get('id')}: bucket {source.get('bucket')!r} is not {CLEARED!r}; do not ingest")
    chunks = []
    for s, (section, page, body) in enumerate(split_sections(text)):
        words = body.split()
        for start in range(0, len(words), chunk_words):
            piece = " ".join(words[start:start + chunk_words])
            chunks.append(Chunk(
                chunk_id=f"{source['id']}-{s:02d}-{start // chunk_words:02d}", text=piece,
                source_id=source["id"], title=source["title"], version=source["version"],
                section=section, page=page or "?", licence_bucket=source["bucket"],
            ))
    return chunks


def ingest(corpus: Path = CORPUS, sources: dict[str, dict] | None = None, chunk_words: int | None = None) -> list[Chunk]:
    """Read corpus/manifest.csv (file,source_id) and chunk every listed file."""
    sources = sources if sources is not None else load_sources()
    chunk_words = int(chunk_words or load_config()["chunk_words"])
    manifest = Path(corpus) / "manifest.csv"
    if not manifest.exists():
        return []
    chunks: list[Chunk] = []
    with manifest.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            source = sources.get(row["source_id"])
            if source is None:
                raise LicenceError(f"{row['file']}: unknown source id {row['source_id']!r}")
            if not is_confirmed(source):
                raise LicenceError(f"{row['file']}: the licence of {source['id']} is still a draft; "
                                   "a team member must confirm it and fill checked_by first")
            chunks += chunk_document((Path(corpus) / row["file"]).read_text(encoding="utf-8"), source, chunk_words)
    return chunks


def as_dicts(chunks: list[Chunk]) -> list[dict]:
    return [asdict(c) for c in chunks]
