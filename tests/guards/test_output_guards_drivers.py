"""P26: the output guards know the drivers. A number a draft copies from DRIVERS passes (88 and 88.0 are one number); an invented
driver number fails; causal wording about any driver, by its feature name, alias or card label, fails; the phrasing the XAI rule asks
for passes."""

import json

import pytest
from output_helpers import GOOD, draft, failed, run

from diacausal.api.schemas import DriverV1
from diacausal.guards.output_guards import numbers_in, numbers_match, parse_draft

DRIVERS = {"SGLT2i": [DriverV1(feature="egfr", value=88.0, contribution=-0.038, ci95=(-0.058, -0.018))]}
SOURCES = ('{"value":-0.882,"ci95":[-0.974,-0.791]}', json.dumps({k: [d.model_dump(mode="json", exclude={"schema_version"}) for d in v] for k, v in DRIVERS.items()}, separators=(",", ":")))


@pytest.mark.parametrize("text", ["Kidney function (eGFR 88) moves the estimate by 0.038 points.", "The interval is -0.058 to -0.018.",
                                  "eGFR 88.0 is this patient's value."])
def test_a_number_copied_from_drivers_passes(text):
    g = run(draft(GOOD, limitations=text), sources=SOURCES)
    assert "numbers" not in failed(g), text


@pytest.mark.parametrize("text", ["Kidney function moves the estimate by 0.04 points.", "eGFR 87 is this patient's value.", "The driver adds 0.05."])
def test_an_invented_or_rounded_driver_number_fails(text):
    g = run(draft(GOOD, limitations=text), sources=SOURCES)
    assert "numbers" in failed(g), text


def test_eighty_eight_and_eighty_eight_point_zero_are_one_number_but_digits_never_change():
    d = parse_draft(draft(GOOD, limitations="Values 88 and 0.50 and 0.038."))[0]
    assert numbers_match(d, ["88.0 0.5 0.038"], [])[0] and not numbers_match(d, ["88.0 0.5 0.04"], [])[0]
    assert numbers_in("88.0") == ["88.0"]


@pytest.mark.parametrize("feature,text", [("ascvd", "Established heart disease causes the larger effect."),
                                          ("duration_years", "A longer diabetes duration leads to less lowering."),
                                          ("hba1c_pct", "The effect is driven by starting HbA1c."),
                                          ("egfr", "Kidney function is responsible for the difference.")])
def test_causal_wording_about_a_driver_by_its_card_label_fails(feature, text):
    drivers = {"SGLT2i": [DriverV1(feature=feature, value=1.0, contribution=0.05, ci95=(0.01, 0.09))]}
    assert "identifier_causal" in failed(run(draft(GOOD, limitations=text), features=[feature]))
    from diacausal.guards.output_guards import run_output_guards
    from output_helpers import PASSAGES, causal, eligible

    g = run_output_guards(draft(GOOD, limitations=text), passages=PASSAGES, number_sources=("{}", "{}"), eligible=eligible(), causal=causal(),
                          drivers=drivers, min_support=0.6)
    assert "identifier_causal" in failed(g)


def test_the_label_of_a_feature_that_is_not_a_driver_is_not_checked():
    assert "identifier_causal" not in failed(run(draft(GOOD, limitations="Established heart disease causes the larger effect.")))


@pytest.mark.parametrize("text", ["The estimate is larger for patients with lower kidney function.",
                                  "The estimate is smaller for patients with a lower starting HbA1c."])
def test_the_phrasing_the_xai_rule_asks_for_passes(text):
    assert "identifier_causal" not in failed(run(draft(GOOD, limitations=text), features=["egfr", "hba1c_pct"]))
