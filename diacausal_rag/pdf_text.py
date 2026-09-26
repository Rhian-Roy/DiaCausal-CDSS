"""PDF -> corpus text (RAG guide Step R2): page markers kept, section headings turned into '## '.

    python -m diacausal_rag.pdf_text IN.pdf diacausal_rag/corpus/OUT.txt --pages 7-26 \
        --heading '^(\\d+\\.\\d+(\\.\\d+)?\\.?\\s+[A-Z].*|\\d+\\.\\s+(Introduction|Recommendations))$'

Plain English: the licence gate still decides what may be ingested (only `cleared_ingest` rows
confirmed by a team member). This tool only turns an approved PDF into the plain-text format
ingest.py reads: "[page N]" before each page's text (N = the PDF page, as a PDF viewer shows it)
and "## Title" for each heading line the --heading pattern matches. Contents pages, reference
lists and appendices are left out with --pages. Check the output by eye before adding it to
corpus/manifest.csv.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from pypdf import PdfReader

LEADER_DOTS = re.compile(r"(\.{4,}|…{2,})")  # a contents-page line, never a heading


def pdf_to_corpus_text(pdf: Path | str, first: int, last: int, heading: str, header: str = "") -> str:
    """Text of PDF pages first..last (1-based, inclusive) in the corpus format."""
    head = re.compile(heading)
    reader = PdfReader(str(pdf))
    last = min(last, len(reader.pages))
    out: list[str] = [header.rstrip()] if header else []
    for n in range(first, last + 1):
        out.append(f"[page {n}]")
        lines = [ln.strip() for ln in (reader.pages[n - 1].extract_text() or "").splitlines()]
        para: list[str] = []
        for ln in lines:
            if not ln or re.fullmatch(r"\d{1,3}", ln):  # blank line or a printed page number
                continue
            if head.match(ln) and not LEADER_DOTS.search(ln) and len(ln) < 100:
                if para:
                    out.append(_join(para))
                    para = []
                out.append("## " + re.sub(r"\s+", " ", ln))
                continue
            para.append(ln)
        if para:
            out.append(_join(para))
    return "\n".join(out) + "\n"


def _join(lines: list[str]) -> str:
    """Join wrapped lines; a line ending in '-' joins without a space (sodium-\\nglucose -> sodium-glucose)."""
    text = ""
    for ln in lines:
        text += ln if text.endswith("-") or not text else " " + ln
    return re.sub(r"\s+", " ", text)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--pages", required=True, help="first-last PDF pages to keep, e.g. 7-26")
    ap.add_argument("--heading", required=True, help="regular expression for a heading line")
    a = ap.parse_args(argv)
    first, last = (int(x) for x in a.pages.split("-"))
    a.out.write_text(pdf_to_corpus_text(a.pdf, first, last, a.heading), encoding="utf-8")
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
