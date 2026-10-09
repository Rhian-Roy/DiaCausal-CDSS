"""Source-aware ranking (P19): after reciprocal rank fusion, passages are ordered by the tuple

    (fusion score, authority tier, India relevance, section match, patient-condition match)

best first, compared left to right: a later key only decides between passages that are tied on every earlier key. The fusion
score is compared after rounding to `fusion_round_decimals` places (diacausal/rag/ranking.yaml), so passages whose fused scores
differ by less than the rounding count as tied; with `null` only exact ties are broken by the other keys. After the five keys come
the exact fusion score and the chunk's position, so the order is always fully determined.

    authority tier     from knowledge_sources/sources.csv `authority_tier` (1 guideline, 2 regulator communication, 3 list, survey or
                       reference text, 4 not clinical evidence, UNKNOWN); a lower position in `authority_tier_order` is better
    India relevance    from `india_relevance` (india, global, other_country, unknown); a lower position in `india_order` is better;
                       a value that is not in the list ranks last
    section match      how many of the question's content words appear in the passage's SECTION TITLE (more is better)
    condition match    how many of the patient's yes/no conditions (kidney disease, heart failure, past pancreatitis, ...) the
                       passage mentions (more is better); 0 for every passage when no condition is given

`latest_version_only`: when two rows of sources.csv are versions of one document (same issuer and title, different version),
only the newest version's passages stay. A family whose versions cannot all be read as a date or year is left alone: nothing
is dropped on a guess.

Only ORDER changes. The candidates are the passages the keyword searches found, and abstention is still decided from the
plain keyword ranking (hybrid.py), so this never turns an answer into a refusal or the reverse.

Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from diacausal.config import load_rag_config
from diacausal.rag.index.bm25 import tokens

CONFIG_PATH = Path(__file__).resolve().parents[1] / "ranking.yaml"
_LAST = 10_000  # a value that is in no list ranks after every value that is


def load_ranking_config(path: Path = CONFIG_PATH) -> dict:
    return load_rag_config(path)


def for_retriever(cfg: dict | None = None) -> dict | None:
    """What the Retriever calls: None while `enabled` is false (the default), the settings otherwise."""
    cfg = cfg or load_ranking_config()
    return cfg if cfg["enabled"] else None


# ── versions of one document ─────────────────────────────────────────────────────────────────────────────────────

_DATE = re.compile(r"^\s*(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?")


def version_key(version: str) -> tuple[int, int, int] | None:
    """(year, month, day) from the start of a version text ("2015-08-28", "2016", "2018 (ISBN ...)"); None if it has none."""
    m = _DATE.match(version or "")
    return None if not m else (int(m.group(1)), int(m.group(2) or 0), int(m.group(3) or 0))


def superseded_sources(sources: dict[str, dict]) -> set[str]:
    """Ids of sources that are an older version of another row (same issuer and title, a newer version)."""
    families: dict[tuple[str, str], list[tuple[str, tuple | None]]] = {}
    for sid, row in sources.items():
        key = (" ".join((row.get("issuer") or "").lower().split()), " ".join((row.get("title") or "").lower().split()))
        families.setdefault(key, []).append((sid, version_key(row.get("version") or "")))
    old: set[str] = set()
    for members in families.values():
        if len(members) < 2 or any(v is None for _, v in members):
            continue  # one version, or one that cannot be compared: leave the family alone
        newest = max(v for _, v in members)
        old.update(sid for sid, v in members if v < newest)
    return old


# ── what the chunks are, as far as ranking cares ─────────────────────────────────────────────────────────────────

@dataclass
class ChunkInfo:
    tier: list[int]  # position of the chunk's source tier in authority_tier_order
    india: list[int]
    section_words: list[set[str]]
    text_lower: list[str]
    superseded: list[bool]


def build_info(chunks: Sequence, sources: dict[str, dict], cfg: dict, texts: Sequence[str]) -> ChunkInfo:
    tier_order, india_order = list(cfg["authority_tier_order"]), list(cfg["india_order"])
    old = superseded_sources(sources) if cfg["latest_version_only"] else set()

    def position(order: list[str], value: str) -> int:
        return order.index(value) if value in order else _LAST

    return ChunkInfo(
        tier=[position(tier_order, (sources.get(c.source_id, {}).get("authority_tier") or "UNKNOWN").strip()) for c in chunks],
        india=[position(india_order, (sources.get(c.source_id, {}).get("india_relevance") or "unknown").strip()) for c in chunks],
        section_words=[set(tokens(c.section)) for c in chunks],
        text_lower=[t.lower() for t in texts],
        superseded=[c.source_id in old for c in chunks],
    )


def patient_conditions(patient) -> list[str]:
    """The yes/no conditions of a PatientV1 that have search words in ranking.yaml."""
    flags = {"ckd": patient.ckd, "heart_failure": patient.heart_failure, "ascvd": patient.ascvd,
             "past_pancreatitis": patient.past_pancreatitis, "past_hypo": patient.past_hypo, "past_dka": patient.past_dka}
    return [name for name, yes in flags.items() if yes]


def section_match(question_words: set[str], section_words: set[str]) -> int:
    return len(question_words & section_words)


def condition_match(conditions: Iterable[str], text_lower: str, keywords: dict[str, list[str]]) -> int:
    return sum(any(w in text_lower for w in keywords.get(c, ())) for c in set(conditions))


def sort_key(i: int, fused: dict[int, float], info: ChunkInfo, question_words: set[str], conditions: Sequence[str], cfg: dict) -> tuple:
    decimals = cfg["fusion_round_decimals"]
    score = fused[i]
    return (-(round(score, int(decimals)) if decimals is not None else score), info.tier[i], info.india[i],
            -section_match(question_words, info.section_words[i]),
            -condition_match(conditions, info.text_lower[i], cfg["condition_keywords"]), -score, i)


def order(candidates: Iterable[int], fused: dict[int, float], info: ChunkInfo, question_words: set[str],
          conditions: Sequence[str], cfg: dict) -> list[int]:
    """The candidates, best first, by the five-key tuple (then exact score, then position)."""
    keep = [i for i in candidates if not info.superseded[i]]
    return sorted(keep, key=lambda i: sort_key(i, fused, info, question_words, conditions, cfg))
