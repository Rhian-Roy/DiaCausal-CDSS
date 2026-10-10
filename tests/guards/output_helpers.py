"""Inputs for the output guard tests (P23): contract examples as models, two synthetic passages, and a draft builder."""

import json
from pathlib import Path

from diacausal.api import schemas
from diacausal.api.schemas import DriverV1, RuleHitV1
from diacausal.guards.output_guards import run_output_guards

EXAMPLES = Path(__file__).resolve().parents[1] / "contract" / "examples"
MIN_SUPPORT = 0.6

# SGLT2i's estimate is -0.882 (-0.974 to -0.791): the numbers a draft may copy.
SOURCES = ('{"value":-0.882,"ci95":[-0.974,-0.791]}', "{}")

PASSAGES = [
    {"chunk_id": "S20-00-00", "text": "SGLT2 inhibitors can cause ketoacidosis, a serious condition that needs hospital treatment.",
     "citation": {"source_id": "S20", "title": "FDA", "version": "2015-12-04", "section": "Safety Announcement", "page": "2", "licence_bucket": "x"}},
    {"chunk_id": "S01-12-00", "text": "Metformin remains the first medicine in the guideline for most adults with type 2 diabetes.",
     "citation": {"source_id": "S01", "title": "WHO", "version": "2018", "section": "Recommendations", "page": "12", "licence_bucket": "x"}},
]
GOOD = ("SGLT2 inhibitors can cause ketoacidosis, a serious condition.", ["S20-00-00"])
GOOD2 = ("Metformin remains the first medicine for most adults.", ["S01-12-00"])


def example(name: str):
    data = json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))
    data.pop("_note", None)
    return getattr(schemas, name).model_validate(data)


def causal(**status):
    """The contract example's causal output; `status={"DPP4i": "insufficient_evidence"}` changes an option's status."""
    out = example("CausalOutputV1")
    for option in out.options:
        if option.arm in status:
            option.status = status[option.arm]
    return out


def eligible(*removed):
    """EligibleOptionsV1 with these options removed by a rule."""
    return example("EligibleOptionsV1").model_copy(update={"excluded": [RuleHitV1(option=o, rule_id="R01", source="test") for o in removed]})


def drivers(*features):
    return {"SGLT2i": [DriverV1(feature=f, value=1.0, contribution=0.05) for f in features]} if features else {}


def draft(*claims, context="The question is about the passages.", limitations="Only the retrieved passages were used.", **extra):
    return json.dumps({"question_context": context, "limitations": limitations,
                       "evidence_summary": [{"claim": c, "chunk_ids": ids} for c, ids in (claims or [GOOD])], **extra})


def run(text, *, removed=(), status=None, features=(), sources=SOURCES, passages=PASSAGES, max_claims=4):
    return run_output_guards(text, passages=passages, number_sources=sources, eligible=eligible(*removed), causal=causal(**(status or {})),
                             drivers=drivers(*features), min_support=MIN_SUPPORT, max_claims=max_claims)


def failed(guarded):
    return [c.id for c in guarded.checks if c.result == "FAIL"]
