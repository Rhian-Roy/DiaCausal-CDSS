"""Evidence levels (plan 8.11, P24): the rule on its boundaries, High never shown, the abstain card exactly as written."""

import pytest
from conftest import OLDER_HYPO, TYPICAL

from diacausal import INTENDED_USE
from diacausal.causal_inference import evidence_level as ev
from diacausal.causal_inference.schemas import PatientIn
from diacausal.config import load_params

RULE = ev.load_rule()


def option(lo=-1.2, hi=-0.6, propensity=0.31, status="estimate", reason=None, arm="DPP4i"):
    """An option of the engine's output, as a dict (the same shape web/engine.js uses)."""
    names = {"SGLT2i": ("SGLT2 inhibitor", "dapagliflozin"), "DPP4i": ("DPP-4 inhibitor", "sitagliptin"), "SU": ("Sulfonylurea", "glimepiride")}
    o = {"arm": arm, "name": names[arm][0], "example_molecule": names[arm][1], "status": status, "safety": [],
         "insufficient_reason": reason, "effect": None, "confidence": None}
    if status == "estimate":
        o["effect"] = {"value": (lo + hi) / 2, "ci_low": lo, "ci_high": hi}
    if propensity is not None and status != "excluded":
        o["confidence"] = {"propensity": propensity, "overlap_threshold": 0.05}
    return o


def level(**kw):
    citations = kw.pop("citations", 2)
    return ev.assess(option(**kw), citations=citations).level


# ── the cut-offs ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_cut_offs_come_from_params_yaml_and_are_team_set():
    p = load_params()
    assert RULE == ev.Rule(0.05, 1.5, 1.0, 0.10, 2)
    for key in ("insufficient_propensity_below", "insufficient_width_above", "low_width_above", "low_propensity_below", "low_citations_below", "high_enabled"):
        entry = p.entry(f"evidence_level.{key}")
        assert entry["status"] == "TEAM-SET" and entry["source"] == "PLAN_8_11", key


def test_the_insufficient_cut_offs_are_the_engines_own_so_the_two_can_never_disagree():
    p = load_params()
    assert RULE.insufficient_propensity_below == p.get("engine.overlap_min_propensity")
    assert RULE.insufficient_width_above == p.get("engine.max_interval_width")


def test_high_cannot_be_switched_on_for_synthetic_data(monkeypatch):
    p = load_params()
    real = p.group

    monkeypatch.setattr(type(p), "group", lambda self, name: {**real(name), "high_enabled": True} if name == "evidence_level" else real(name))
    with pytest.raises(ValueError, match="never shown on synthetic data"):
        ev.load_rule(p)


def test_high_is_never_a_level():
    import itertools

    for lo, p, c in itertools.product([-2.0, -1.5, -1.2, -0.9, -0.7], [0.01, 0.049, 0.05, 0.09, 0.1, 0.5, 0.99], [None, 0, 1, 2, 9]):
        assert level(lo=lo, hi=-0.6, propensity=p, citations=c) in ev.LEVELS
    assert "High" not in ev.LEVELS


# ── the boundaries ───────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("propensity,expected", [(0.0499, "Insufficient"), (0.05, "Low"), (0.0999, "Low"), (0.10, "Moderate"), (0.9, "Moderate")])
def test_propensity_boundaries(propensity, expected):
    """'below 0.05' and 'below 0.10': the cut-off itself belongs to the better level."""
    assert level(propensity=propensity) == expected


@pytest.mark.parametrize("lo,expected", [(-1.6, "Moderate"), (-1.601, "Low"), (-2.1, "Low"), (-2.101, "Insufficient")])
def test_width_boundaries(lo, expected):
    """Width = ci_high - ci_low (hi = -0.6): exactly 1.0 is not "above 1.0"; exactly 1.5 is not "above 1.5". The engine prints intervals to 3 decimals, so the width is too."""
    assert level(lo=lo, hi=-0.6) == expected


@pytest.mark.parametrize("citations,expected", [(None, "Moderate"), (0, "Low"), (1, "Low"), (2, "Moderate"), (5, "Moderate")])
def test_citation_boundaries(citations, expected):
    """Fewer than 2 cited passages is Low; None means no search ran (the benchmark) and the rule is not used."""
    assert level(citations=citations) == expected


def test_retrieval_that_abstained_makes_every_estimate_insufficient():
    a = ev.assess(option(), citations=3, retrieval_abstained=True)
    assert a.level == "Insufficient" and a.reason == "Insufficient: no licence-cleared passage answers this question."


def test_the_plans_worked_example():
    """SGLT2i -1.2 to -0.6 (width 0.6), propensity 0.31, 2 citations -> Moderate; with propensity 0.07 -> Low."""
    assert ev.assess(option(arm="SGLT2i"), citations=2) == ev.Assessment(
        "Moderate", "Moderate: the 95% interval is 0.60 points wide, propensity 0.31, 2 cited passages.")
    assert ev.assess(option(propensity=0.07, arm="SU"), citations=2) == ev.Assessment("Low", "Low: propensity 0.07 (below 0.1).")


def test_every_low_reason_that_applies_is_listed():
    a = ev.assess(option(lo=-1.9, hi=-0.6, propensity=0.08), citations=1)
    assert a == ev.Assessment("Low", "Low: the 95% interval is 1.30 points wide (more than 1); propensity 0.08 (below 0.1); 1 cited passage (fewer than 2).")


# ── options the engine did not estimate ──────────────────────────────────────────────────────────────────────────
def test_an_excluded_option_is_not_assessed_and_names_its_rule():
    o = {**option(status="excluded", propensity=None), "safety": [{"rule_id": "R01", "action": "EXCLUDE"}, {"rule_id": "R04", "action": "CAUTION"}]}
    assert ev.assess(o, citations=2) == ev.Assessment(None, "Not assessed: removed by rule R01 before estimation.")


def test_the_abstain_card_is_exactly_the_plans():
    o = option(status="insufficient_evidence", propensity=0.03, reason="Too few similar patients received this option (propensity 0.030, below 0.05). A fair comparison is not possible.")
    assert ev.abstain_card(o) == [
        "Insufficient evidence for: DPP-4i",
        "Why: too few similar patients received this option in the reference data (propensity 0.03; threshold 0.05).",
        "What you can still see: cited guideline passages (Investigate tab).",
        f"The clinician decides. {INTENDED_USE}"]
    assert ev.assess(o, citations=2).reason == "Insufficient: too few similar patients received this option in the reference data (propensity 0.03; threshold 0.05)."


@pytest.mark.parametrize("reason,why", [
    ("Too uncertain: this patient's 95% range is 1.62 points wide (limit 1.5). A useful estimate is not possible.",
     "this patient's 95% interval is wider than 1.5 points, so no useful estimate can be shown"),
    ("Outside the cohort: age = 88 is outside the cohort's range (30 to 85)",
     "this patient is outside the range of the reference data (age = 88 is outside the cohort's range (30 to 85))"),
    ("Something else happened.", "something else happened")])
def test_the_why_line_names_the_part_of_the_rule_that_applied(reason, why):
    assert ev.abstain_why(option(status="insufficient_evidence", propensity=None, reason=reason)) == why


# ── formatting the same way as the browser ───────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("x,text", [(0.125, "0.13"), (0.135, "0.14"), (0.005, "0.01"), (0.004999, "0.00"), (1.0, "1.00"), (0.3, "0.30")])
def test_numbers_are_rounded_half_away_from_zero(x, text):
    assert ev.fmt2(x) == text


def test_citations_count_the_passages_that_name_the_option():
    texts = ["SGLT2 inhibitors can cause ketoacidosis.", "Dapagliflozin and kidney function.", "Metformin first.", "sglt2 again"]
    assert ev.count_citations(texts, option(arm="SGLT2i")) == 3 and ev.count_citations(texts, option(arm="SU")) == 0


# ── with the real engine ─────────────────────────────────────────────────────────────────────────────────────────
def test_real_engine_options_get_a_level_each_and_excluded_ones_none(engine, audit_file):
    r = engine.recommend(PatientIn(**TYPICAL))
    for o in r.options:
        a = ev.assess(o, citations=2)
        assert a.level in ev.LEVELS and a.reason.startswith(a.level + ":")


def test_an_option_without_overlap_now_carries_its_propensity_but_still_no_estimate(engine, audit_file):
    r = engine.recommend(PatientIn(**OLDER_HYPO))
    low = [o for o in r.options if o.status == "insufficient_evidence" and o.insufficient_reason.startswith("Too few")]
    for o in low:
        assert o.effect is None and o.secondary is None and o.confidence.propensity < o.confidence.overlap_threshold
        assert ev.abstain_card(o)[1].startswith("Why: too few similar patients received this option in the reference data (propensity ")
