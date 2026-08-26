"""
Zero-dependency PDF text extraction.
====================================

Why this file exists at all: no PDF library is installed in this environment,
and `pip install` is not available. Rather than let that block the RAG half of
the project, we read the PDFs ourselves.

This is less mad than it sounds. A PDF is not a mysterious binary format — it is
a text file with compressed islands in it. Stripped to essentials:

    1. The file is a list of numbered OBJECTS:   `12 0 obj ... endobj`
    2. Some objects are STREAMS — a dictionary, then `stream`, then bytes, then
       `endstream`. Page content is a stream, usually zlib-compressed
       (`/Filter /FlateDecode`).
    3. Decompressed, a content stream is a tiny stack language. Only two of its
       operators actually put glyphs on the page:

           (Hello) Tj                        show one string
           [(Hel) -20 (lo world)] TJ         show several, with kerning numbers

    4. So: find the streams, decompress them, pull the parenthesised strings out
       of `Tj` and `TJ`, and you have the text.

Validated on the project's four guideline PDFs:

    IDF_Rec_2025.pdf                          271,055 letters   works well
    BTN_D1_Diabetes Management guidelines.pdf  383,534 letters   works well
    dc252383.pdf (ADA Diabetes Care)            14,818 letters   mostly watermark
    Diabetes handbooks, ency....pdf                   0 letters   unreadable

--------------------------------------------------------------------------------
WHAT THIS DELIBERATELY DOES NOT DO — and why the honesty matters
--------------------------------------------------------------------------------
This is a pragmatic 250-line reader, not a PDF engine. It cannot handle:

    CID / Identity-H fonts     The bytes in the stream are glyph indexes, not
                               characters. Recovering text needs the font's
                               ToUnicode CMap, which we do not parse. This is
                               why the ADA paper comes back as mostly watermark:
                               the body text is there, just encoded through a
                               font table we cannot read.

    Scanned pages              Some PDFs contain no text at all, only images of
                               text. No amount of parsing helps; that needs OCR.

    Reading order              We emit strings in content-stream order, which is
                               usually but not always the order a human reads.
                               Multi-column layouts can interleave.

Which is exactly why `rag_lite.py` has a three-tier loader and
`guideline_fallback.py` exists. A retrieval system that silently returns nothing
for two of its four sources is worse than one that says so and falls back to
curated text — because the first kind fails invisibly.

If `pypdf` is ever installed, :func:`extract_pdf` will use it automatically and
this whole module becomes a fallback. It is written to be replaceable.
"""

from __future__ import annotations

import re
import zlib
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Page:
    """One page's worth of extracted text."""

    number: int          #: 1-indexed, for citations
    text: str
    n_letters: int = 0

    def __post_init__(self):
        self.n_letters = sum(c.isalpha() for c in self.text)


@dataclass
class Document:
    """An extracted PDF, plus an honest account of how well it worked."""

    path: str
    pages: list[Page]
    backend: str                       #: which of the three tiers produced this
    notes: dict = field(default_factory=dict)

    @property
    def name(self) -> str:
        return Path(self.path).name

    @property
    def n_letters(self) -> int:
        return sum(p.n_letters for p in self.pages)

    @property
    def usable(self) -> bool:
        """Enough real text to retrieve over?

        Two conditions, and the second is the one that earns its place:

            total letters >= 2000        We got something at all.
            letters per page >= 250      What we got is spread across the
                                         document, not concentrated in a
                                         header.

        Without the per-page test, a 19-page paper yielding one repeated footer
        line looks "usable" on the total and floods the index with 44 chunks of
        `Downloaded from diabetesjournals.org by guest`. Those chunks then win
        searches, because a phrase repeated 19 times is a phrase TF-IDF is happy
        to match. One bad threshold is all it takes to make a retriever
        confidently cite a watermark.
        """
        if not self.pages:
            return False
        per_page = self.n_letters / len(self.pages)
        return self.n_letters >= 2000 and per_page >= 250


    @property
    def quality(self) -> str:
        """A blunt verdict, so a demo can say what happened out loud."""
        letters_per_page = self.n_letters / max(len(self.pages), 1)
        if self.n_letters == 0:
            return "UNREADABLE — no extractable text (scanned images, or a font we cannot decode)"
        if letters_per_page < 200:
            return "POOR — only fragments recovered, probably CID-encoded fonts"
        if letters_per_page < 800:
            return "PARTIAL — usable but incomplete"
        return "GOOD"

    def summary(self) -> str:
        return (
            f"{self.name:<46s} {len(self.pages):>4d} pages  "
            f"{self.n_letters:>8,d} letters  via {self.backend:<12s} {self.quality}"
        )


# ═════════════════════════════════════════════════════════════════════════════
# TIER 1 — our own parser
# ═════════════════════════════════════════════════════════════════════════════

#: Matches `... stream\r\n <bytes> \r\n endstream`, non-greedy, bytes mode.
_STREAM_RE = re.compile(rb"stream\r?\n?(.*?)\r?\n?endstream", re.DOTALL)

#: `(text) Tj`  — a single show-string operator.
_TJ_RE = re.compile(rb"\((?:\\.|[^\\()])*\)\s*Tj")

#: `[ (a) -20 (b) ] TJ`  — the array form, which is what real PDFs mostly use.
_TJ_ARRAY_RE = re.compile(rb"\[((?:\\.|[^\\\[\]])*)\]\s*TJ", re.DOTALL)

#: Any parenthesised literal string inside a TJ array.
_STRING_RE = re.compile(rb"\((?:\\.|[^\\()])*\)")

#: `BT ... ET` — a text object. Used only to spot page breaks heuristically.
_PDF_ESCAPES = {
    rb"\n": b"\n", rb"\r": b"\r", rb"\t": b"\t", rb"\b": b"\b",
    rb"\f": b"\f", rb"\(": b"(", rb"\)": b")", rb"\\": b"\\",
}


def _unescape(raw: bytes) -> bytes:
    """Turn a PDF literal string's escape sequences into real bytes.

    PDF strings use C-style escapes plus three-digit OCTAL codes (`\\251` is
    the copyright sign). Octal is easy to forget and shows up constantly in
    real documents, hence the explicit pass.
    """
    for esc, real in _PDF_ESCAPES.items():
        raw = raw.replace(esc, real)
    # Octal escapes: \ddd
    def _octal(m):
        try:
            return bytes([int(m.group(1), 8) & 0xFF])
        except ValueError:  # pragma: no cover
            return b""
    return re.sub(rb"\\([0-7]{1,3})", _octal, raw)


def _decode(raw: bytes) -> str:
    """Bytes to text. PDF literal strings are usually Latin-1 or WinAnsi.

    We try Latin-1 (which never fails and covers the WinAnsi range for our
    documents) and drop control characters other than whitespace.
    """
    s = raw.decode("latin-1", errors="replace")
    return "".join(ch if ch.isprintable() or ch in " \t\n" else " " for ch in s)


def _text_from_content_stream(data: bytes) -> str:
    """Pull the shown strings out of one decompressed content stream.

    The two operators are handled slightly differently, and the difference
    matters for readability:

        Tj  ->  one string, emit it.

        TJ  ->  an array of strings interleaved with kerning numbers. The
                numbers are horizontal adjustments in thousandths of an em. A
                large NEGATIVE number means "move right a lot", which is how
                PDFs encode an inter-word space without wasting a byte on ' '.
                So we insert a space when the adjustment is big enough. Skip
                that and you get `theriskofhypoglycaemia`, which no tokeniser
                can recover from.
    """
    out: list[str] = []

    # Walk the stream in order, handling whichever operator comes next, so the
    # output preserves layout order rather than grouping by operator type.
    #
    # The third alternative catches the POSITIONING operators. Td/TD/T* move to
    # a new line and Tm sets the text matrix outright (which is how PDFs jump
    # from a heading to a body paragraph). All four mean "the pen moved", so we
    # emit a newline. Without Tm in that list, a heading and the paragraph under
    # it get concatenated — `Lente InsulinLente insulin is...` — and the
    # heading's last word is lost to the tokeniser.
    pattern = re.compile(
        rb"\[((?:\\.|[^\\\[\]])*)\]\s*TJ|(\((?:\\.|[^\\()])*\))\s*Tj|(T\*|Td|TD|Tm|ET)",
        re.DOTALL,
    )
    for m in pattern.finditer(data):
        if m.group(1) is not None:                      # TJ array
            body = m.group(1)
            frag: list[str] = []
            for piece in re.finditer(rb"\((?:\\.|[^\\()])*\)|-?\d+(?:\.\d+)?", body):
                tok = piece.group(0)
                if tok.startswith(b"("):
                    frag.append(_decode(_unescape(tok[1:-1])))
                else:
                    # A kerning adjustment. Below about -100 thousandths of an
                    # em is a real word gap in every font we have looked at.
                    try:
                        if float(tok) <= -100:
                            frag.append(" ")
                    except ValueError:  # pragma: no cover
                        pass
            out.append("".join(frag))
        elif m.group(2) is not None:                    # (string) Tj
            out.append(_decode(_unescape(m.group(2)[1:-1])))
        else:                                            # T* / Td / TD / Tm / ET
            # The pen moved to a new position: a new line, or a jump from a
            # heading to a paragraph. Emit a newline so sentences do not run
            # together across visual lines.
            out.append("\n")

    return "".join(out)


def extract_pdf_builtin(path: str | Path) -> Document:
    """Tier 1: extract with our own parser. No third-party code involved.

    Page attribution is approximate. Properly, you walk the page tree
    (`/Type /Pages` -> `/Kids`) and map each `/Contents` reference to a page.
    We take the simpler route: each successfully decompressed content stream is
    treated as one page. For our documents this lines up closely enough that
    citations point at the right place, and where it slips it slips by one — a
    limitation worth stating rather than hiding, since a citation the reader
    cannot find is worse than no citation.
    """
    raw = Path(path).read_bytes()
    pages: list[Page] = []
    n_streams = n_decompressed = 0

    for m in _STREAM_RE.finditer(raw):
        n_streams += 1
        blob = m.group(1)
        try:
            data = zlib.decompress(blob)
        except zlib.error:
            # Not Flate-compressed, or compressed with a filter we do not
            # support (DCTDecode = a JPEG, CCITTFaxDecode = a fax image, and so
            # on). Try it raw in case it is an uncompressed content stream.
            data = blob
        n_decompressed += 1

        # Content streams contain `BT` (begin text). Streams without it are
        # images, fonts, or metadata — skip them cheaply.
        if b"BT" not in data and b"Tj" not in data and b"TJ" not in data:
            continue

        text = _text_from_content_stream(data)
        if sum(c.isalpha() for c in text) > 0:
            pages.append(Page(number=len(pages) + 1, text=text))

    doc = Document(
        path=str(path),
        pages=pages,
        backend="builtin",
        notes={
            "streams_found": n_streams,
            "streams_with_text": len(pages),
            "limitation": (
                "CID/Identity-H fonts and scanned images cannot be decoded by "
                "this parser; page numbers are stream-order approximations."
            ),
        },
    )
    return doc


# ═════════════════════════════════════════════════════════════════════════════
# TIER 2 — pypdf, if it ever appears
# ═════════════════════════════════════════════════════════════════════════════

def extract_pdf_pypdf(path: str | Path) -> Document | None:
    """Tier 2: use `pypdf` if it is installed. Returns None if it is not.

    Not currently available here, but written and wired in anyway: the moment
    someone runs this project on a machine with `pypdf`, extraction silently
    gets better — real page numbers, proper font decoding, correct reading
    order — and no other file has to change.
    """
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        return None

    reader = PdfReader(str(path))
    pages = [
        Page(number=i + 1, text=(p.extract_text() or ""))
        for i, p in enumerate(reader.pages)
    ]
    return Document(path=str(path), pages=pages, backend="pypdf")


def extract_pdf(path: str | Path, prefer_library: bool = True) -> Document:
    """Extract a PDF using the best backend available.

    Order: `pypdf` if present (better), otherwise our own parser (always
    present). The caller does not need to know which ran — `Document.backend`
    records it for the demo to print.
    """
    if prefer_library:
        doc = extract_pdf_pypdf(path)
        if doc is not None and doc.n_letters > 0:
            return doc
    return extract_pdf_builtin(path)


# ═════════════════════════════════════════════════════════════════════════════
# CLEANUP — the difference between "text" and "text worth indexing"
# ═════════════════════════════════════════════════════════════════════════════

def clean_text(text: str) -> str:
    """Normalise whitespace and repair line-break hyphenation.

    Two fixes that matter more than they look:

        DE-HYPHENATION   PDFs break words across lines: "hypo-\\nglycaemia".
                         Left alone, TF-IDF sees the tokens `hypo` and
                         `glycaemia` and a search for "hypoglycaemia" misses the
                         one chunk that discusses it.

                         The cost, stated plainly: we cannot tell a line-break
                         hyphen from a real one, so genuine compounds that
                         happen to break at the hyphen come out joined —
                         "follow-up" becomes "followup", "well-recognised"
                         becomes "wellrecognised". That trade is worth taking.
                         A joined compound is still one findable token; a split
                         word is two useless ones.

        WHITESPACE       Collapse runs of spaces and blank lines, so chunk
                         boundaries fall in sensible places rather than inside a
                         column of padding.
    """
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)   # de-hyphenate
    # A line holding a single letter is almost always a drop-cap or a glyph the
    # layout engine positioned separately: `M\nost widely available`. Rejoin it,
    # or the tokeniser sees `ost` and the word is lost.
    text = re.sub(r"\n([A-Za-z])\n(?=[a-z])", r"\n\1", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def drop_boilerplate(doc: Document, threshold: float = 0.5, min_len: int = 12) -> Document:
    """Remove lines that appear on more than `threshold` of the pages.

    Running headers, footers, journal names, DOI stamps and watermarks repeat on
    every page. They are the single biggest source of retrieval noise, because
    a phrase appearing 90 times is a phrase TF-IDF will happily match on — and
    "Downloaded from diabetesjournals.org by guest" is never the answer to a
    clinical question.

    The rule is purely statistical: no keyword list, no per-document tuning.
    A line on over half the pages is furniture, not content.
    """
    if len(doc.pages) < 4:
        # Too few pages for the statistic to mean anything. Leave it alone
        # rather than deleting content on the strength of two observations.
        return doc

    counts: Counter[str] = Counter()
    for page in doc.pages:
        for line in {ln.strip() for ln in page.text.splitlines() if len(ln.strip()) >= min_len}:
            counts[line] += 1

    cutoff = threshold * len(doc.pages)
    boilerplate = {line for line, c in counts.items() if c > cutoff}

    cleaned = [
        Page(
            number=p.number,
            text="\n".join(
                ln for ln in p.text.splitlines() if ln.strip() not in boilerplate
            ),
        )
        for p in doc.pages
    ]
    notes = dict(doc.notes)
    notes["boilerplate_lines_removed"] = len(boilerplate)
    notes["boilerplate_examples"] = sorted(boilerplate, key=len, reverse=True)[:3]
    return Document(path=doc.path, pages=cleaned, backend=doc.backend, notes=notes)


def load_clean(path: str | Path) -> Document:
    """Extract, normalise, then strip boilerplate. The one function to call.

    The ORDER matters, and getting it wrong is a subtle bug worth recording.
    Boilerplate detection works by counting identical lines across pages, so the
    lines have to be identical *as strings* before you count them. Raw extraction
    leaves the same running footer with slightly different internal whitespace on
    different pages, depending on where the layout engine happened to emit a
    positioning operator — so counting first and cleaning second finds nothing,
    and every page keeps its watermark.

    Normalise first, count second: the ADA paper's "Downloaded from
    diabetesjournals.org..." footer then correctly registers on 19 of 19 pages
    and is removed, leaving that document with no text at all — which is the
    honest answer, and the signal that sends it to the fallback tier.
    """
    doc = extract_pdf(path)
    for p in doc.pages:
        p.text = clean_text(p.text)
        p.n_letters = sum(c.isalpha() for c in p.text)
    doc = drop_boilerplate(doc)
    for p in doc.pages:
        p.text = clean_text(p.text)
        p.n_letters = sum(c.isalpha() for c in p.text)
    return doc



def extraction_report(folder: str | Path = "RAG") -> str:
    """Try every PDF in a folder and print an honest per-file verdict.

    This is a good first cell in a demo: it shows that two of four guidelines
    read cleanly, one reads partially, one not at all — and that the system was
    built knowing that, rather than discovering it live.
    """
    folder = Path(folder)
    pdfs = sorted(folder.glob("*.pdf"))
    lines = [
        f"PDF EXTRACTION REPORT — {folder}/",
        "=" * 100,
        f"{'file':<46s} {'pages':>5s}  {'letters':>8s}  backend       verdict",
        "-" * 100,
    ]
    for p in pdfs:
        try:
            lines.append("  " + load_clean(p).summary())
        except Exception as exc:  # pragma: no cover
            lines.append(f"  {p.name:<46s} FAILED: {type(exc).__name__}: {exc}")
    lines += [
        "-" * 100,
        "Anything below GOOD is handled by the fallback tier in "
        "`guideline_fallback.py`,",
        "so every citation the CDSS shows still resolves to real guideline text.",
    ]
    return "\n".join(lines)
