"""Fetch FDA Drug Safety Communications (US government work, public domain) into the RAG corpus.

    .venv/bin/python scripts/fetch_fda_dsc.py          # writes diacausal_rag/corpus/fda_*.txt

fda.gov refuses the build machine, so the text comes from the Internet Archive's copy of the
official fda.gov page (web.archive.org, unmodified HTML). Kept: the announcement and the
"Facts", "Additional Information" and "Data Summary" sections. Left out: brand-name tables,
reference lists and site navigation. Every file must also be listed in RAG/sources.csv
(bucket cleared_ingest, checked_by filled) and in diacausal_rag/corpus/manifest.csv.
"""

from __future__ import annotations

import gzip
import html
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "diacausal_rag" / "corpus"
BASE = "https://www.fda.gov/drugs/drug-safety-and-availability/"
ARCHIVE = "https://web.archive.org/web/2025id_/"  # "id_" = the page exactly as fda.gov served it

# (file, fda.gov slug)
PAGES = [
    ("fda_dsc_2016_saxagliptin_alogliptin_hf.txt",
     "fda-drug-safety-communication-fda-adds-warnings-about-heart-failure-risk-labels-type-2-diabetes"),
    ("fda_dsc_2015_dpp4_joint_pain.txt",
     "fda-drug-safety-communication-fda-warns-dpp-4-inhibitors-type-2-diabetes-may-cause-severe-joint-pain"),
    ("fda_dsc_2015_sglt2_ketoacidosis_uti.txt",
     "fda-revises-labels-sglt2-inhibitors-diabetes-include-warnings-about-too-much-acid-blood-and-serious"),
    ("fda_dsc_2018_sglt2_genital_infection.txt",
     "fda-warns-about-rare-occurrences-serious-infection-genital-area-sglt2-inhibitors-diabetes"),
    ("fda_dsc_2016_canagliflozin_dapagliflozin_kidney.txt",
     "fda-drug-safety-communication-fda-strengthens-kidney-warnings-diabetes-medicines-canagliflozin"),
    ("fda_dsc_2020_canagliflozin_amputation.txt",
     "fda-removes-boxed-warning-about-risk-leg-and-foot-amputations-diabetes-medicine-canagliflozin"),
]
SKIP = re.compile(r"^(list of|reference|references|related information)\b", re.I)


def fetch(slug: str, tries: int = 6) -> str:
    req = urllib.request.Request(ARCHIVE + BASE + slug, headers={"User-Agent": "DiaCausal research prototype"})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                raw = r.read()
            if raw[:2] == b"\x1f\x8b":  # the archive replays the original gzip body as-is
                raw = gzip.decompress(raw)
            return raw.decode("utf-8", errors="replace")
        except OSError:  # the archive often resets connections; wait and retry
            if attempt == tries - 1:
                raise
            time.sleep(2 ** (attempt + 1))
    raise RuntimeError("unreachable")


def plain(fragment: str) -> str:
    t = re.sub(r"<(script|style|table)\b.*?</\1>", " ", fragment, flags=re.S | re.I)
    t = re.sub(r"<sup\b.*?</sup>", "", t, flags=re.S | re.I)  # reference markers
    t = re.sub(r"<(br|/p|/li|/h\d|/div)[^>]*>", "\n", t, flags=re.I)
    t = re.sub(r"<li[^>]*>", "\n- ", t, flags=re.I)
    t = html.unescape(re.sub(r"<[^>]+>", "", t))
    lines = [re.sub(r"[ \t ]+", " ", ln).strip() for ln in t.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def to_corpus(page: str) -> tuple[str, str]:
    title = plain(re.search(r"<h1[^>]*content-title[^>]*>(.*?)</h1>", page, re.S).group(1))
    main = page[page.index('id="main-content"'):]
    main = main[:main.find("Related Information")] if "Related Information" in main else main
    parts = re.split(r'<h4 class="panel-title">(.*?)</h4>', main, flags=re.S)
    if len(parts) < 3:  # newer page layout (2020 on): plain <h2>/<h3> headings, no panels
        parts = re.split(r"<h[23][^>]*>(.*?)</h[23]>", main, flags=re.S)
    out = []
    for i in range(1, len(parts) - 1, 2):
        heading = plain(parts[i])
        if SKIP.match(heading):
            continue
        body = plain(parts[i + 1])
        body = re.split(r"\n(Contact FDA|Content current as of)", body)[0].strip()
        if body:
            out += [f"## {heading}", body]
    return title, "\n".join(out) + "\n"


def main() -> None:
    for file, slug in PAGES:
        title, text = to_corpus(fetch(slug))
        (CORPUS / file).write_text(text, encoding="utf-8")
        print(f"{file}: {title[:80]} ({len(text.split())} words)")


if __name__ == "__main__":
    sys.exit(main())
