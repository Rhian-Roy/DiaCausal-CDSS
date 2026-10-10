"""Query processing (P16): turn the question into what the keyword search should look for.

    normalise      Unicode NFKC, one kind of dash, case folded, spaces collapsed
    expand         abbreviations and spelling variants from knowledge_sources/query_synonyms.csv ("DKA" also searches
                   "diabetic ketoacidosis"), brand names to generics from knowledge_sources/brand_generic.csv
    split          at most 3 sub-queries, only where a question clearly holds more than one question

WHAT USES WHAT: the expanded sub-queries go to BM25 ONLY. The vector search (TF-IDF today, the dense model later) always
gets the ORIGINAL question: an expansion is a keyword aid, and it would distort a meaning-based comparison.

Rules that keep it safe and testable:
  * deterministic: the same question always gives the same plan (no model, no randomness, rows applied in file order);
  * nothing is removed or rewritten: expansions are APPENDED, so an unknown word passes through unchanged and a question
    with no match is searched exactly as written;
  * a brand name is never invented: brand_generic.csv is empty of brands until Member B verifies them (status
    TODO-VERIFY rows and rows without a brand are ignored); only status VERIFIED rows ever apply;
  * the text of the question is never logged here (this module does not log).

Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.
"""

from __future__ import annotations

import csv
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from functools import lru_cache
from pathlib import Path

from diacausal.config import KNOWLEDGE_DIR
from diacausal.rag.index.bm25 import TOKEN, tokens

SYNONYMS_CSV = KNOWLEDGE_DIR / "query_synonyms.csv"
BRAND_CSV = KNOWLEDGE_DIR / "brand_generic.csv"
DRIVER_TERMS_CSV = KNOWLEDGE_DIR / "driver_terms.csv"  # P26: a driver feature -> words the corpus uses for it
MAX_SUB_QUERIES = 3  # plan P16
MIN_WORDS_EACH_SIDE = 3  # a question is split at "and" only if both halves are at least this long
MAX_PHRASE_WORDS = 3  # an abbreviation or brand may be up to three words ("type 2 diabetes")
INACTIVE = "TODO-VERIFY"
VERIFIED = "VERIFIED"

_DASHES = dict.fromkeys(map(ord, "‐‑‒–—−﹘﹣－"), "-")
_INVISIBLE = dict.fromkeys(map(ord, "​‌‍⁠﻿"), None)
_SENTENCES = re.compile(r"(?<=[.?!;])\s+")
_AND = re.compile(r"\s+(?:and|also|as well as)\s+")
# A part that points back at the one before it ("... and which medicines is IT linked to?") cannot be searched alone:
# without its subject it matches generic passages. Such a part is kept with the part before it.
_POINTS_BACK = re.compile(r"\b(?:it|its|they|them|their|this|that|these|those|he|she|him|her|his|such|same)\b")


def normalise(text: str) -> str:
    """NFKC, one kind of dash, no zero-width characters, lower case, single spaces."""
    text = unicodedata.normalize("NFKC", text).translate(_DASHES).translate(_INVISIBLE)
    return " ".join(text.casefold().split())


# ── the two tables ───────────────────────────────────────────────────────────────────────────────────────────────

def _rows(path: Path) -> list[dict]:
    with Path(path).open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


@lru_cache(maxsize=8)
def load_synonyms(path: Path = SYNONYMS_CSV) -> dict[str, tuple[str, ...]]:
    """{abbreviation or variant (lower case): the terms to ADD}. A row with no abbreviation or no expansion, or marked
    TODO-VERIFY, is ignored. Several rows for one key add their terms in file order."""
    table: dict[str, list[str]] = {}
    for row in _rows(path):
        key, expansion = normalise(row.get("abbreviation") or ""), (row.get("expansion") or "").strip()
        if not key or not expansion or (row.get("status") or "").strip() == INACTIVE:
            continue
        table.setdefault(key, []).extend(normalise(t) for t in expansion.split(";") if t.strip())
    return {k: tuple(v) for k, v in table.items()}


@lru_cache(maxsize=8)
def load_brands(path: Path = BRAND_CSV) -> dict[str, tuple[str, ...]]:
    """{brand name (lower case): generic names}. ONLY rows with a brand AND status VERIFIED apply: an empty brand or a
    TODO-VERIFY row is a reminder, never a mapping."""
    table: dict[str, list[str]] = {}
    for row in _rows(path):
        brand, generic = normalise(row.get("brand") or ""), normalise(row.get("generic") or "")
        if brand and generic and (row.get("status") or "").strip() == VERIFIED:
            table.setdefault(brand, []).append(generic)
    return {k: tuple(v) for k, v in table.items()}


# ── expand and split ─────────────────────────────────────────────────────────────────────────────────────────────

def _matches(words: list[str], table: dict[str, tuple[str, ...]]):
    """(first word index, number of words, added terms) for every key found, longest phrase first at each position."""
    i = 0
    while i < len(words):
        for n in range(min(MAX_PHRASE_WORDS, len(words) - i), 0, -1):
            added = table.get(" ".join(words[i:i + n]))
            if added:
                yield i, n, added
                i += n
                break
        else:
            i += 1


def expand(text: str, synonyms: dict[str, tuple[str, ...]], brands: dict[str, tuple[str, ...]]) -> tuple[str, tuple[str, ...], dict[str, tuple[str, ...]]]:
    """The text with extra terms appended; the extra terms; and {question word: the words of what was added for it}.
    Nothing already in the text is added again."""
    text = normalise(text)
    words = TOKEN.findall(text)
    added: list[str] = []
    equivalents: dict[str, set[str]] = {}
    for table in (synonyms, brands):
        for start, n, terms in _matches(words, table):
            for term in terms:
                if term in added or (" " + term + " ") in (" " + " ".join(words) + " "):
                    continue
                added.append(term)
                for w in words[start:start + n]:
                    equivalents.setdefault(w, set()).update(tokens(term))
    expanded = text if not added else text + " " + " ".join(added)
    return expanded, tuple(added), {k: tuple(sorted(v)) for k, v in equivalents.items()}


def split_sub_queries(text: str) -> list[str]:
    """At most MAX_SUB_QUERIES parts of a normalised question: at sentence ends, and at "and" / "also" / "as well as"
    when BOTH halves have at least MIN_WORDS_EACH_SIDE words (so "ketoacidosis and UTI" stays whole) and the second
    half does not point back at the first ("it", "they", "this"...). Parts beyond the limit are joined onto the last
    one: nothing is dropped."""
    parts: list[str] = []
    for sentence in (s.strip() for s in _SENTENCES.split(text) if s.strip()):
        pieces = [p.strip() for p in _AND.split(sentence)]
        merged = [pieces[0]]
        for piece in pieces[1:]:
            if len(merged[-1].split()) >= MIN_WORDS_EACH_SIDE and len(piece.split()) >= MIN_WORDS_EACH_SIDE and not _POINTS_BACK.search(piece):
                merged.append(piece)
            else:
                merged[-1] = merged[-1] + " and " + piece  # too short or not self-contained: keep it with its neighbour
        # a whole sentence that points back at the previous one stays with it too
        if parts and _POINTS_BACK.search(merged[0]):
            parts[-1] = parts[-1] + " " + merged[0]
            merged = merged[1:]
        parts.extend(merged)
    if len(parts) > MAX_SUB_QUERIES:
        parts = parts[:MAX_SUB_QUERIES - 1] + [" ".join(parts[MAX_SUB_QUERIES - 1:])]
    return parts or [text]


@dataclass(frozen=True)
class QueryPlan:
    original: str  # exactly what was asked: the vector search uses this
    normalised: str
    sub_queries: tuple[str, ...]  # expanded; the keyword search (BM25) uses these
    added: tuple[str, ...] = ()  # the terms the tables added (for tests; never logged)
    equivalents: dict[str, tuple[str, ...]] = field(default_factory=dict)  # question word -> words of its expansions
    driver_queries: tuple[str, ...] = ()  # P26: one keyword query per comparison's top driver; they only REORDER (hybrid.py)


def process(question: str, synonyms: dict[str, tuple[str, ...]] | None = None,
            brands: dict[str, tuple[str, ...]] | None = None) -> QueryPlan:
    synonyms = load_synonyms() if synonyms is None else synonyms
    brands = load_brands() if brands is None else brands
    normalised = normalise(question)
    subs, added, equivalents = [], [], {}
    for part in split_sub_queries(normalised):
        text, extra, eq = expand(part, synonyms, brands)
        subs.append(text)
        added.extend(t for t in extra if t not in added)
        for word, words in eq.items():
            equivalents[word] = tuple(sorted(set(equivalents.get(word, ())) | set(words)))
    return QueryPlan(original=question, normalised=normalised, sub_queries=tuple(subs), added=tuple(added), equivalents=equivalents)


# ── drivers of the estimate (P26) ────────────────────────────────────────────────────────────────────────────────────

def load_driver_terms(path: Path = DRIVER_TERMS_CSV) -> dict[str, tuple[str, ...]]:
    """{feature: the words the licence-cleared corpus uses for it} ("egfr" -> kidney function, renal impairment, egfr). Every word of a
    row marked IN-CORPUS is in the corpus (a test checks), so a term can always match something."""
    return {r["feature"]: tuple(t.strip() for t in r["terms"].split(";") if t.strip()) for r in _rows(path)}


def add_drivers(plan: QueryPlan, features: Sequence[str], terms: dict[str, tuple[str, ...]] | None = None) -> QueryPlan:
    """The plan plus one keyword query per top driver (one per comparison, duplicates once): "egfr" -> "kidney function renal
    impairment egfr". These queries never decide whether to abstain and never bring in a passage the question did not find: in
    hybrid.py they only add a ranking to the fusion, so passages about the driver move up among the question's own candidates."""
    terms = load_driver_terms() if terms is None else terms
    queries = tuple(dict.fromkeys(normalise(" ".join(terms[f])) for f in features if f in terms))
    return replace(plan, driver_queries=queries)
