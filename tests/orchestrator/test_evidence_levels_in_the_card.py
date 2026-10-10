"""P24 through /api/v1/ask: every option the rules left has an evidence level with its reason, an Insufficient option shows no estimate
and carries the abstain notice of plan 8.11, excluded and 'check first' rules are on the card with rule ID and source."""

import pytest
from pipeline_helpers import PRESETS, body

from diacausal.api.schemas import AnswerCardV1
from diacausal.causal_inference.evidence_level import LEVELS


def card(client, preset, question=None, rid="ev1"):
    patient, q = PRESETS[preset]
    r = client.post("/api/v1/ask", json=body(patient, question or q, rid))
    assert r.status_code == 200, r.text
    return AnswerCardV1.model_validate(r.json())


@pytest.mark.parametrize("preset", list(PRESETS))
def test_every_option_the_rules_left_has_a_level_and_a_one_line_reason(client, preset):
    c = card(client, preset)
    removed = {h.option for h in c.excluded}
    assert {lv.option for lv in c.evidence_levels} == {row.option for row in c.effects} - removed
    for lv in c.evidence_levels:
        assert lv.level in LEVELS and lv.reason.startswith(lv.level + ":") and "\n" not in lv.reason
    assert all(lv.level != "High" for lv in c.evidence_levels)


def test_an_option_without_overlap_shows_no_estimate_and_the_plans_abstain_notice(client):
    c = card(client, "older_hypo")
    rows = {row.option: row for row in c.effects}
    notices = {n.option: n for n in c.abstain}
    insufficient = [lv.option for lv in c.evidence_levels if lv.level == "Insufficient"]
    assert insufficient, "the older patient with past hypoglycaemia has an option without overlap"
    for option in insufficient:
        assert rows[option].status == "INSUFFICIENT_EVIDENCE" and rows[option].hba1c_change is None
        n = notices[option]
        if n.propensity is not None:
            assert n.threshold == 0.05 and n.propensity < 0.05
            assert n.why.startswith("too few similar patients received this option in the reference data (propensity ")
            assert n.why.endswith("; threshold 0.05)")


def test_excluded_and_check_first_rules_are_on_the_card_with_rule_id_and_source(client):
    c = card(client, "egfr40_pancreatitis")
    assert [h.option for h in c.excluded] == ["SGLT2i"] and all(h.rule_id.startswith("R") and h.source for h in c.excluded)
    assert c.cautions and all(h.rule_id.startswith("R") and h.source for h in c.cautions)
    assert "SGLT2i" not in {lv.option for lv in c.evidence_levels}


def test_when_the_retrieval_abstains_every_level_is_insufficient_and_no_estimate_is_shown(client):
    c = card(client, "typical", question="zebra-test")
    assert c.evidence_levels and all(lv.level == "Insufficient" for lv in c.evidence_levels)
    assert all(row.hba1c_change is None and row.vs_comparator is None for row in c.effects)
    assert {n.why for n in c.abstain} == {"no licence-cleared passage answers this question"}


def test_the_level_counts_the_retrieved_passages_that_name_the_option(client):
    c = card(client, "typical")  # "Can SGLT2 inhibitors cause ketoacidosis?": the passages name SGLT2 inhibitors
    by = {lv.option: lv for lv in c.evidence_levels}
    assert "cited passage" in by["SGLT2i"].reason
