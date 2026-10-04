"""POST /api/v1/ask end to end: each demo preset returns a schema-valid AnswerCardV1, in the order of plan 8.3."""

import pytest
from pipeline_helpers import PRESETS, body

from diacausal import INTENDED_USE
from diacausal.api.schemas import AnswerCardV1

LAYERS = ["input guards", "rules", "causal engine", "retrieval", "explanation", "output guards", "formatter"]


def layer_lines(caplog, rid):
    return [r.getMessage() for r in caplog.records if r.name == "diacausal.trace" and r.getMessage().startswith(f"[{rid}]")]


@pytest.mark.parametrize("name", list(PRESETS))
def test_each_preset_returns_a_schema_valid_card(client, trace, name):
    patient, question = PRESETS[name]
    r = client.post("/api/v1/ask", json=body(patient, question, f"p-{name[:6]}"))
    assert r.status_code == 200, r.text
    card = AnswerCardV1.model_validate(r.json())  # every rule of the card model holds
    assert card.request_id == f"p-{name[:6]}" == r.headers["X-Request-Id"]
    assert card.intended_use == INTENDED_USE and card.decision.endswith("The clinician decides.")
    assert [e.option for e in card.effects] == ["SGLT2i", "DPP4i", "SU"]
    assert card.mode == "template" and card.comparator == "DPP4i"
    for e in card.effects:  # an excluded or insufficient option never carries a number
        if e.status != "ESTIMATED":
            assert e.hba1c_change is None and e.weight_change_kg is None and e.hypo_risk_pct is None
        else:
            assert e.hba1c_change.ci_low <= e.hba1c_change.value <= e.hba1c_change.ci_high  # always an interval
    assert card.claims == [] or all(c.citations for c in card.claims)
    assert len(card.claims) <= 4


def test_the_typical_patient_has_every_option_and_cited_claims(client):
    patient, question = PRESETS["typical"]
    card = AnswerCardV1.model_validate(client.post("/api/v1/ask", json=body(patient, question)).json())
    assert [e.status for e in card.effects] == ["ESTIMATED"] * 3 and card.excluded == []
    assert card.claims, "the retrieval has passages about ketoacidosis"
    labels = {c.label for claim in card.claims for c in claim.citations}
    assert all(any(w in label for w in ("FDA", "WHO")) for label in labels), labels


def test_egfr_40_removes_the_sglt2i_by_rule_r01_and_never_estimates_it(client):
    patient, question = PRESETS["egfr40_pancreatitis"]
    card = AnswerCardV1.model_validate(client.post("/api/v1/ask", json=body(patient, question)).json())
    sglt2 = next(e for e in card.effects if e.option == "SGLT2i")
    assert sglt2.status == "EXCLUDED" and sglt2.hba1c_change is None
    assert [(h.option, h.rule_id) for h in card.excluded] == [("SGLT2i", "R01")]
    assert all(h.source for h in card.excluded)
    assert next(e for e in card.effects if e.option == "DPP4i").caution  # R04 and R05


def test_the_older_patient_gets_the_sulfonylurea_cautions(client):
    patient, question = PRESETS["older_hypo"]
    card = AnswerCardV1.model_validate(client.post("/api/v1/ask", json=body(patient, question)).json())
    assert next(e for e in card.effects if e.option == "SGLT2i").status == "EXCLUDED"
    assert next(e for e in card.effects if e.option == "SU").caution  # R07, R08, R09


@pytest.mark.parametrize("name", list(PRESETS))
def test_the_layers_run_in_the_order_of_plan_8_3(client, trace, name):
    patient, question = PRESETS[name]
    client.post("/api/v1/ask", json=body(patient, question, "order1"))
    lines = layer_lines(trace, "order1")
    entered = [ln.split(" entered ")[1].removesuffix(" layer") for ln in lines if " entered " in ln]
    assert entered == LAYERS
    for layer_name in LAYERS:  # each layer: entered, executing, then exactly one of passed / abstained / failed
        mine = [ln for ln in lines if f" {layer_name} layer" in ln and "STUB" not in ln]
        assert mine[0].endswith(f"entered {layer_name} layer") and mine[1].endswith(f"executing {layer_name} layer")
        assert len(mine) == 3 and any(w in mine[2] for w in (" passed ", " abstained "))


def test_every_option_excluded_still_answers_and_says_why(client, trace):
    r = client.post("/api/v1/ask", json=body(dict(age=60, sex="F", duration_years=8.0, hba1c_pct=8.2, egfr=25.0, bmi=25.5,
                                                  ckd=True), "Can SGLT2 inhibitors cause ketoacidosis?", "allout"))
    card = AnswerCardV1.model_validate(r.json())
    assert [e.status for e in card.effects] == ["EXCLUDED"] * 3
    text = " ".join(layer_lines(trace, "allout"))
    assert "abstained rules layer reason=ALL_OPTIONS_EXCLUDED" in text
    assert "abstained causal engine layer reason=NOT_APPLICABLE" in text


def test_a_question_nothing_matches_abstains_at_retrieval_and_the_card_has_no_claims(client, trace):
    patient, _ = PRESETS["typical"]
    card = AnswerCardV1.model_validate(client.post("/api/v1/ask", json=body(patient, "zebra-test", "noev")).json())
    assert card.claims == []
    assert "abstained retrieval layer reason=NO_EVIDENCE" in " ".join(layer_lines(trace, "noev"))
    assert "abstained explanation layer" in " ".join(layer_lines(trace, "noev"))


def test_a_dose_question_is_stopped_by_the_input_guards_before_anything_runs(client, trace):
    patient, _ = PRESETS["typical"]
    r = client.post("/api/v1/ask", json=body(patient, "What dose of sitagliptin should I use?", "dose"))
    assert r.status_code == 422 and "never gives doses" in r.json()["message"]
    assert [p["check"] for p in r.json()["problems"]] == ["dose_request"]
    text = " ".join(layer_lines(trace, "dose"))
    assert "abstained input guards layer reason=DOSE_REQUEST" in text and "rules layer" not in text


def test_the_local_model_mode_falls_back_to_the_template_when_there_is_no_model(client):
    patient, question = PRESETS["typical"]
    r = client.post("/api/v1/ask", json={**body(patient, question), "mode": "ollama"})
    card = AnswerCardV1.model_validate(r.json())
    assert card.mode in ("template", "ollama")  # "template" when no local model answers, "ollama" if one does
    assert all(c.citations for c in card.claims)


def test_recommend_still_works_next_to_ask(client):
    r = client.post("/api/v1/recommend", json={"schema_version": "1.0", "patient": {
        "age": 52, "sex": "male", "duration_years": 5.0, "hba1c": 8.4, "egfr": 88.0, "bmi": 27.0}})
    assert r.status_code == 200 and r.json()["applicable"] == "APPLICABLE" and r.json()["intended_use"] == INTENDED_USE


def test_a_bad_request_is_refused_in_plain_english_without_echoing_it(client):
    patient, question = PRESETS["typical"]
    r = client.post("/api/v1/ask", json=body({**patient, "hba1c_pct": 99.123}, question))
    assert r.status_code == 422 and "99.123" not in r.text and "out of the plausible range" in r.json()["message"]
    r = client.post("/api/v1/ask", json={**body(patient, question), "surprise": 1})
    assert r.status_code == 422 and r.json()["intended_use"] == INTENDED_USE


def test_the_live_endpoint_matches_the_published_contract(client):
    from diacausal.api.contract_app import create_contract_app

    live = client.get("/openapi.json").json()["paths"]["/api/v1/ask"]["post"]
    contract = create_contract_app().openapi()["paths"]["/api/v1/ask"]["post"]
    assert live["requestBody"] == contract["requestBody"]
    assert live["responses"]["200"] == contract["responses"]["200"]
    assert live["responses"]["422"]["content"] == contract["responses"]["422"]["content"]
