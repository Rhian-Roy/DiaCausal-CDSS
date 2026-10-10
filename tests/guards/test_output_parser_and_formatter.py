"""diacausal/output/parser.py and formatter.py (P23): the parser keeps only the question context, at most 4 claims and the limitations;
the card takes every number of the effects table from CausalOutputV1, never from the model."""

import json

from output_helpers import example, GOOD, GOOD2, PASSAGES, draft, run

from diacausal.api.schemas import AnswerCardV1, AnswerDraftV1
from diacausal.output.formatter import build_card
from diacausal.output.parser import parse, to_sentences


def parsed_draft(**over):
    base = {"question_context": " Context. ", "limitations": " Limits. ", "insufficient": False,
            "evidence_summary": [{"claim": f" Claim {n}. ", "chunk_ids": ["S20-00-00"]} for n in range(6)]}
    return AnswerDraftV1.model_validate(base | over)


# ── the parser ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_parser_keeps_only_the_context_at_most_four_claims_and_the_limitations():
    p = parse(parsed_draft(insufficient_reason="THIS TEXT IS NOT KEPT"))
    assert p.question_context == "Context." and p.limitations == "Limits." and len(p.claims) == 4 and p.claims[0].text == "Claim 0."
    assert "NOT KEPT" not in repr(p) and set(vars(p)) == {"question_context", "claims", "limitations", "insufficient"}
    assert len(parse(parsed_draft(), max_claims=2).claims) == 2


def test_the_parser_notes_that_the_model_found_no_answer_without_keeping_its_reason():
    p = parse(parsed_draft(evidence_summary=[], insufficient=True, insufficient_reason="no passage"))
    assert p.insufficient and p.claims == () and "no passage" not in repr(p)


def test_the_claims_become_sentences_citing_the_position_of_the_passage():
    g = run(draft(GOOD, GOOD2))
    sentences = to_sentences(parse(g.draft), PASSAGES)
    assert [s["cites"] for s in sentences] == [[1], [2]] and all(s["text"].endswith(".") and not s["text"].endswith("..") for s in sentences)


def test_a_claim_citing_two_passages_cites_both_and_an_unknown_id_is_left_out_by_the_parser_too():
    p = parse(parsed_draft(evidence_summary=[{"claim": "Both.", "chunk_ids": ["S01-12-00", "S20-00-00"]}, {"claim": "None.", "chunk_ids": ["S99-00-00"]}]))
    assert to_sentences(p, PASSAGES) == [{"text": "Both.", "cites": [1, 2]}]


# ── the card ─────────────────────────────────────────────────────────────────────────────────────────────────────
def card(reply):
    return build_card(request=example("AskRequestV1"), causal=example("CausalOutputV1"), eligible=example("EligibleOptionsV1"),
                      evidence=example("EvidenceBundleV1"), reply=reply, labels={"S01-p12-c3": "WHO 2018, p.12"}, drivers={}, levels=[])


def test_every_number_of_the_effects_table_comes_from_the_causal_output_whatever_the_reply_says():
    causal = example("CausalOutputV1")
    lying = {"status": "SUCCESS", "backend": "ollama", "sentences": [{"text": "The effect is -9.99 points, the best of all.", "cites": [1]}],
             "question_context": "The change is -8.88.", "limitations": "Maybe -7.77.", "fallback": None, "failed_checks": [], "dropped_claims": 0}
    c = card(lying)
    by = {row.option: row for row in c.effects}
    for option in causal.options:
        assert by[option.arm].hba1c_change == option.effect and by[option.arm].weight_change_kg == option.secondary.weight_change_kg
        assert by[option.arm].hypo_risk_pct == option.secondary.hypo_risk_pct
    table = json.dumps([row.model_dump() for row in c.effects])
    assert "9.99" not in table and "8.88" not in table and "7.77" not in table


def test_a_model_answer_puts_its_words_on_the_card_and_says_no_fallback_was_used():
    reply = {"status": "SUCCESS", "backend": "ollama", "sentences": [{"text": "Metformin is first.", "cites": [1]}], "question_context": "About metformin.",
             "limitations": "Passages only.", "fallback": None, "failed_checks": [], "dropped_claims": 1}
    c = AnswerCardV1.model_validate(card(reply).model_dump())
    assert c.mode == "ollama" and c.question_context == "About metformin." and c.limitations == "Passages only." and c.dropped_claims == 1
    assert c.fallback_used is False and c.failed_checks == [] and c.fallback_reason is None and c.claims[0].citations[0].label == "WHO 2018, p.12"


def test_a_fallback_is_recorded_with_its_failed_checks_and_the_model_text_is_not_on_the_card():
    reply = {"status": "SUCCESS", "backend": "template", "sentences": [{"text": "A quoted sentence.", "cites": [1]}], "note": "x",
             "fallback": "GUARD_NUMBERS", "failed_checks": ["numbers", "dose_threshold"], "dropped_claims": 0}
    c = card(reply)
    assert c.mode == "template" and c.fallback_used and c.failed_checks == ["numbers", "dose_threshold"] and c.fallback_reason == "GUARD_NUMBERS"
    assert c.question_context is None and c.limitations is None


def test_a_card_that_never_asked_the_model_has_no_fallback():
    c = card({"status": "SUCCESS", "backend": "template", "sentences": [{"text": "A quoted sentence.", "cites": [1]}]})
    assert c.fallback_used is False and c.failed_checks == [] and c.fallback_reason is None and c.dropped_claims == 0
