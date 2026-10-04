"""Section-aware, sentence-aware chunking with metadata on every chunk (split out of ingest.py in restructure step 6).

Plain English: each document is a text file whose sections start with a line "## Section name" (and optionally
"[page N]" markers). We cut each section into pieces of about 400 words, never mixing two sections, and label
every piece with where it came from (source, version, section, page), so every sentence we show later can be cited.
`chunk_document` refuses a source that is not licence-cleared; the gate itself is in licence_gate.py.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from diacausal.rag.ingest.licence_gate import CLEARED, LicenceError


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


_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def _pieces(body: str, chunk_words: int) -> list[str]:
    """Cut a section into pieces of at most chunk_words words, ending at a sentence end where possible
    (a single sentence longer than chunk_words is cut by words)."""
    out: list[list[str]] = []
    cur: list[str] = []
    for sentence in _SENTENCE_END.split(body):
        w = sentence.split()
        if len(cur) + len(w) > chunk_words and cur:
            out.append(cur)
            cur = []
        while len(w) > chunk_words:
            out.append(w[:chunk_words])
            w = w[chunk_words:]
        cur += w
    if cur:
        out.append(cur)
    return [" ".join(p) for p in out]


def chunk_document(text: str, source: dict, chunk_words: int, part: int = 0) -> list[Chunk]:
    """part: 0 for a source's first file in the manifest, 1, 2, ... for its further files
    (their chunk IDs become S08.1-..., so two files of one source never share an ID)."""
    if source.get("bucket") != CLEARED:
        raise LicenceError(f"{source.get('id')}: bucket {source.get('bucket')!r} is not {CLEARED!r}; do not ingest")
    chunks = []
    for s, (section, page, body) in enumerate(split_sections(text)):
        for k, piece in enumerate(_pieces(body, chunk_words)):
            chunks.append(Chunk(
                chunk_id=f"{source['id']}{f'.{part}' if part else ''}-{s:02d}-{k:02d}", text=piece,
                source_id=source["id"], title=source["title"], version=source["version"],
                section=section, page=page or "?", licence_bucket=source["bucket"],
            ))
    return chunks


def as_dicts(chunks: list[Chunk]) -> list[dict]:
    return [asdict(c) for c in chunks]
