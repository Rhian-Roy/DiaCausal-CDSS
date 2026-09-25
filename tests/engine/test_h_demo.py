"""Step (h): one patient -> structured Causal Output, and the Streamlit demo screen."""

import json
from pathlib import Path

import pytest
from conftest import EGFR40_PANCREATITIS, OLDER_HYPO, TYPICAL

from diacausal_engine import INTENDED_USE
from diacausal_engine.recommend import DOSE_PATTERN, OutputCheckError, bmi_category, check_output, load_prices
from diacausal_engine.schemas import PatientIn

ROOT = Path(__file__).resolve().parents[2]


def status(result):
    return {o.arm: o.status for o in result.options}


def test_typical_patient_gets_three_estimates_each_with_a_95_percent_range(engine, audit_file):
    r = engine.recommend(PatientIn(**TYPICAL))
    assert r.applicable == "APPLICABLE"
    assert status(r) == {"SGLT2i": "estimate", "DPP4i": "estimate", "SU": "estimate"}
    for o in r.options:
        assert o.effect.ci_low < o.effect.value < o.effect.ci_high
        assert o.effect.level == 0.95
    assert len(r.comparisons) == 3
    assert r.intended_use == INTENDED_USE


def test_egfr_40_with_pancreatitis_shows_exclusion_and_cautions_with_sources(engine, audit_file):
    r = engine.recommend(PatientIn(**EGFR40_PANCREATITIS))
    by = {o.arm: o for o in r.options}
    assert by["SGLT2i"].status == "excluded" and by["SGLT2i"].effect is None
    assert by["SGLT2i"].safety[0].rule_id == "R01" and "FARXIGA" in by["SGLT2i"].safety[0].source
    assert {s.rule_id for s in by["DPP4i"].safety} == {"R04", "R05"}
    assert {s.rule_id for s in by["SU"].safety} == {"R09"}
    assert all(s.action == "CAUTION" for s in by["DPP4i"].safety + by["SU"].safety)


def test_rare_patient_gets_insufficient_evidence_not_a_number(engine, audit_file):
    r = engine.recommend(PatientIn(**OLDER_HYPO))
    su = next(o for o in r.options if o.arm == "SU")
    assert su.status == "insufficient_evidence" and su.effect is None
    assert "below 0.05" in su.insufficient_reason


def test_type_1_diabetes_is_not_applicable(engine, audit_file):
    r = engine.recommend(PatientIn(**TYPICAL | {"t1d": True}))
    assert r.applicable == "NOT_APPLICABLE"
    assert not [o for o in r.options if o.effect is not None]
    assert any("type 1" in x for x in r.not_applicable_reasons)


def test_causal_output_has_every_flow_chart_field(engine, audit_file):
    out = engine.recommend(PatientIn(**TYPICAL)).model_dump()
    for key in ("applicable", "intervention", "outcome", "options", "comparisons", "assumptions", "versions", "intended_use"):
        assert key in out
    assert out["options"][0]["confidence"]["propensity"] > 0
    assert any("unmeasured confounding" in a for a in out["assumptions"])


def test_safety_rules_run_before_the_estimate_and_excluded_options_get_no_number(engine, audit_file, monkeypatch):
    """Call order is rules -> DR-learner, and an excluded option never carries an estimate."""
    from diacausal_engine.guardrails import RuleTable

    calls = []
    real_apply, real_predict = RuleTable.apply, engine.fitted.dr.predict
    monkeypatch.setattr(RuleTable, "apply", lambda self, p: calls.append("rules") or real_apply(self, p))
    monkeypatch.setattr(engine.fitted.dr, "predict", lambda x, z: calls.append("estimate") or real_predict(x, z))
    r = engine.recommend(PatientIn(**TYPICAL | {"egfr": 40}))  # R01 excludes SGLT2i
    assert calls == ["rules", "estimate"]
    assert status(r) == {"SGLT2i": "excluded", "DPP4i": "estimate", "SU": "estimate"}
    assert all(o.effect is None and o.confidence is None for o in r.options if o.status == "excluded")


def test_egfr_below_the_cohort_gets_no_number_at_all(engine, audit_file):
    """eGFR 25: R01 and R10 exclude SGLT2i and SU; DPP-4i is outside the cohort (which starts at 30)."""
    r = engine.recommend(PatientIn(**TYPICAL | {"egfr": 25}))
    assert status(r) == {"SGLT2i": "excluded", "DPP4i": "insufficient_evidence", "SU": "excluded"}
    assert r.applicable == "NOT_APPLICABLE"
    assert all(o.effect is None for o in r.options)


def test_output_check_refuses_doses_and_bare_numbers(engine, audit_file):
    r = engine.recommend(PatientIn(**TYPICAL))
    bad = r.model_copy(deep=True)
    bad.options[0].example_molecule = "dapagliflozin 10 mg"
    with pytest.raises(OutputCheckError, match="dose"):
        check_output(bad)
    bad = r.model_copy(deep=True)
    bad.options[0].status = "insufficient_evidence"
    with pytest.raises(OutputCheckError, match="must not carry a number"):
        check_output(bad)


@pytest.mark.parametrize("text", ["10 mg", "100 mg once daily", "twice daily", "max 8 mg/day", "2 tablets"])
def test_dose_pattern_catches_dose_text(text):
    assert DOSE_PATTERN.search(text)


def test_rule_messages_themselves_contain_no_doses():
    assert not DOSE_PATTERN.search((ROOT / "data/rules.csv").read_text())


def test_prices_stay_unavailable_until_confirmed():
    prices = load_prices()
    assert {c.label for c in prices.values()} == {"price unavailable"}
    assert all(c.inr_per_month is None for c in prices.values())


def test_bmi_uses_asian_indian_cutoffs(params):
    assert bmi_category(params, 22.9).startswith("Normal")
    assert bmi_category(params, 23.0).startswith("Overweight")
    assert bmi_category(params, 25.0).startswith("Obese")


def test_audit_log_records_decisions_but_never_patient_values(engine, audit_file):
    engine.recommend(PatientIn(**EGFR40_PANCREATITIS))
    line = json.loads(audit_file.read_text().strip().splitlines()[-1])
    assert line["options"]["SGLT2i"] == {"status": "excluded", "rules": ["R01"]}
    text = audit_file.read_text()
    for value in ('"egfr": 40', "25.5", "8.2", '"age": 60'):
        assert value not in text


def test_answers_quickly(engine, audit_file):
    import time

    t = time.perf_counter()
    engine.recommend(PatientIn(**TYPICAL))
    assert time.perf_counter() - t < 2.0


# ── the Streamlit screen ─────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    import os

    from streamlit.testing.v1 import AppTest

    os.environ["DIACAUSAL_AUDIT_LOG"] = str(tmp_path_factory.mktemp("audit") / "audit.jsonl")
    at = AppTest.from_file(str(ROOT / "demo/streamlit_app.py"), default_timeout=120)
    at.run()
    return at


def screen_text(at) -> str:
    return " ".join(str(m.value) for m in at.markdown) + " ".join(str(c.value) for c in at.caption)


def test_demo_shows_the_intended_use_statement_at_the_top(app):
    assert not app.exception
    assert INTENDED_USE in app.markdown[0].value


@pytest.mark.parametrize(
    "button,expected",
    [(0, ["ESTIMATE", "95% range"]), (1, ["EXCLUDED", "R01", "R05", "Source:"]), (2, ["INSUFFICIENT EVIDENCE", "below 0.05"])],
)
def test_each_preset_renders_its_story(app, button, expected):
    app.sidebar.button[button].click().run()
    assert not app.exception
    text = screen_text(app)
    for word in expected:
        assert word in text, word
    assert INTENDED_USE in text
    assert not DOSE_PATTERN.search(text)
    assert "The clinician decides" in text


def test_demo_never_uses_green_success_boxes():
    source = (ROOT / "demo/streamlit_app.py").read_text()
    assert "st.success" not in source and "green" not in source.lower().replace("never green", "")


def test_hosting_requirements_match_the_engine_pins():
    """demo/requirements.txt (Streamlit Community Cloud) must use exactly the engine's pins."""

    def pins(path):
        return {line.split("==")[0].lower(): line.strip() for line in path.read_text().splitlines()
                if line.strip() and not line.startswith("#")}

    engine, demo = pins(ROOT / "requirements-engine.txt"), pins(ROOT / "demo/requirements.txt")
    assert {"streamlit", "numpy", "scikit-learn", "pyyaml", "pydantic"} <= set(demo)
    for name, line in demo.items():
        assert engine.get(name) == line, name
