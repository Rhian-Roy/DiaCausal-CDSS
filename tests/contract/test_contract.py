"""API v1 contract (P09): every example validates; every model forbids extra fields and a wrong schema_version;
the ranges match docs/INPUT_RANGES.md; the engine's real output fits CausalOutputV1; openapi.json and
web/types.d.ts are fresh. `_note` is a comment key allowed ONLY in the example files (stripped before checking)."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Literal

import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from diacausal.api.schemas import (MODELS, RANGES, AnswerCardV1, AskRequestV1, CausalOutputV1, GuardedDraftV1,  # noqa: E402
                                   LLMRequestV1, PatientV1, to_engine_patient)
from diacausal_engine import INTENDED_USE  # noqa: E402
from diacausal_engine.recommend import Engine  # noqa: E402

EXAMPLES = ROOT / "tests" / "contract" / "examples"
NAMES = sorted(MODELS)


def load(name: str) -> dict:
    data = json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))
    data.pop("_note", None)
    return data


def test_the_twelve_models_named_in_p09_exist():
    assert NAMES == sorted(["PatientV1", "AskRequestV1", "GuardResultV1", "EligibleOptionsV1", "CausalOutputV1", "DriverV1",
                            "EvidenceChunkV1", "EvidenceBundleV1", "LLMRequestV1", "AnswerDraftV1", "GuardedDraftV1", "AnswerCardV1"])


@pytest.mark.parametrize("name", NAMES)
def test_every_example_validates_and_round_trips(name):
    model = MODELS[name].model_validate(load(name))
    assert model.schema_version == "1.0"
    again = MODELS[name].model_validate(json.loads(model.model_dump_json()))
    assert again == model


def test_there_is_an_example_for_every_model_and_no_stray_files():
    assert sorted(p.stem for p in EXAMPLES.glob("*.json")) == NAMES


@pytest.mark.parametrize("name", NAMES)
def test_unknown_fields_are_rejected(name):
    data = load(name)
    data["surprise_field"] = 1
    with pytest.raises(ValidationError) as e:
        MODELS[name].model_validate(data)
    assert "surprise_field" in str(e.value)


def _nested_models(model_cls, seen=None):
    seen = seen if seen is not None else set()
    for field in model_cls.model_fields.values():
        for t in _walk(field.annotation):
            if hasattr(t, "model_fields") and t not in seen:
                seen.add(t)
                _nested_models(t, seen)
    return seen


def _walk(annotation):
    args = getattr(annotation, "__args__", None)
    if args:
        for a in args:
            yield from _walk(a)
    else:
        yield annotation


def test_every_v1_model_forbids_extra_fields_and_carries_schema_version():
    models = set(MODELS.values())
    for m in list(models):
        models |= {n for n in _nested_models(m) if n.__module__.startswith("diacausal.api.schemas")}
    for m in models:
        assert m.model_config.get("extra") == "forbid", m.__name__
        field = m.model_fields["schema_version"]
        assert field.annotation == Literal["1.0"], m.__name__  # only "1.0" is accepted
        assert field.default == "1.0" or m.__name__ in ("AskRequestV1", "RecommendRequestV1"), m.__name__  # requests must send it


@pytest.mark.parametrize("name", NAMES)
def test_a_wrong_schema_version_is_rejected(name):
    data = load(name)
    data["schema_version"] = "2.0"
    with pytest.raises(ValidationError):
        MODELS[name].model_validate(data)


def test_ask_request_requires_schema_version_and_a_valid_request_id():
    data = load("AskRequestV1")
    del data["schema_version"]
    with pytest.raises(ValidationError):
        AskRequestV1.model_validate(data)
    for bad in ("", "a b", "x" * 65, "résumé"):
        data = load("AskRequestV1")
        data["request_id"] = bad
        with pytest.raises(ValidationError):
            AskRequestV1.model_validate(data)
    data = load("AskRequestV1")
    data["mode"] = "gemini"  # only template and ollama exist
    with pytest.raises(ValidationError):
        AskRequestV1.model_validate(data)


# ── ranges (docs/INPUT_RANGES.md) ───────────────────────────────────────────────────────────────
def _table_ranges() -> dict[str, tuple[float, float]]:
    out = {}
    for line in (ROOT / "docs/INPUT_RANGES.md").read_text(encoding="utf-8").split("## Today's engine")[0].splitlines():
        m = re.match(r"\| `(\w+)` \|.*\| (\d+(?:\.\d+)?)–(\d+(?:\.\d+)?) \|", line)
        if m:
            out[m.group(1)] = (float(m.group(2)), float(m.group(3)))
    return out


def test_ranges_in_code_match_the_table_in_docs_input_ranges():
    table = _table_ranges()
    assert set(table) == set(RANGES)
    for field, (lo, hi) in RANGES.items():
        assert table[field] == (float(lo), float(hi)), field
    assert "TEAM-SET" in (ROOT / "docs/INPUT_RANGES.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("field", ["age", "duration_years", "hba1c_pct", "egfr", "bmi", "waist_cm", "glucose_mg_dl"])
def test_patient_ranges_are_enforced_at_both_edges(field):
    lo, hi = RANGES[field]
    for ok in (lo, hi):
        data = load("PatientV1")
        data[field] = ok
        PatientV1.model_validate(data)
    for bad in (lo - 0.5 if field != "age" else lo - 1, hi + 0.5 if field != "age" else hi + 1):
        data = load("PatientV1")
        data[field] = bad
        with pytest.raises(ValidationError):
            PatientV1.model_validate(data)


def test_age_must_be_a_whole_number_and_sex_is_f_or_m():
    data = load("PatientV1")
    data["age"] = 52.5
    with pytest.raises(ValidationError):
        PatientV1.model_validate(data)
    data = load("PatientV1")
    data["sex"] = "female"
    with pytest.raises(ValidationError):
        PatientV1.model_validate(data)


def test_every_required_yes_no_question_must_be_answered():
    for field in ("ascvd", "heart_failure", "ckd", "past_hypo", "past_dka", "past_pancreatitis", "type1", "on_metformin"):
        data = load("PatientV1")
        del data[field]
        with pytest.raises(ValidationError):
            PatientV1.model_validate(data)


def test_every_8_2_range_sits_inside_the_engines_range_so_the_engine_never_rejects_a_valid_patient():
    from diacausal_engine.schemas import PatientIn

    eng = {"age": "age", "duration_years": "duration_years", "hba1c_pct": "hba1c", "egfr": "egfr", "bmi": "bmi"}
    for field, engine_field in eng.items():
        lo, hi = RANGES[field]
        meta = {type(m).__name__: m for m in PatientIn.model_fields[engine_field].metadata}
        assert meta["Ge"].ge <= lo and hi <= meta["Le"].le, field


@pytest.mark.parametrize("corner", ["low", "high"])
def test_corner_patients_convert_to_valid_engine_patients(corner):
    data = load("PatientV1")
    for field, (lo, hi) in RANGES.items():
        if field in ("waist_cm", "glucose_mg_dl"):
            continue
        data[field] = int(lo if corner == "low" else hi) if field == "age" else (lo if corner == "low" else hi)
    engine_patient = to_engine_patient(PatientV1.model_validate(data))
    assert engine_patient.age == data["age"] and engine_patient.hba1c == data["hba1c_pct"]


def test_conversion_maps_every_field_the_engine_uses():
    p = PatientV1.model_validate({**load("PatientV1"), "sex": "F", "heart_failure": True, "past_hypo": True, "past_dka": True,
                                  "past_pancreatitis": True, "type1": False, "ascvd": True, "cost_concern": False})
    e = to_engine_patient(p)
    assert (e.sex, e.hf, e.hypo_history, e.dka_history, e.pancreatitis_history, e.ascvd, e.t1d, e.low_income) == \
        ("female", True, True, True, True, True, False, False)


# ── CausalOutputV1 reuses the engine's CausalOutput ─────────────────────────────────────────────
def test_the_engines_real_output_is_a_valid_causal_output_v1():
    engine = Engine()
    for patient in (load("PatientV1"), {**load("PatientV1"), "egfr": 40, "past_pancreatitis": True}, {**load("PatientV1"), "age": 80, "hba1c_pct": 8.0, "past_hypo": True}):
        out = engine.recommend(to_engine_patient(PatientV1.model_validate(patient)), audit=False)
        v1 = CausalOutputV1.model_validate(json.loads(out.model_dump_json()))
        assert v1.model_dump(exclude={"options": {"__all__": {"drivers", "schema_version"}}}) == json.loads(out.model_dump_json())


def test_causal_output_v1_keeps_every_existing_engine_field_name():
    from diacausal_engine.schemas import CausalOutput, OptionOut

    assert set(CausalOutput.model_fields) <= set(CausalOutputV1.model_fields)
    assert set(OptionOut.model_fields) | {"drivers", "schema_version"} == set(CausalOutputV1.model_fields["options"].annotation.__args__[0].model_fields)


# ── safety invariants encoded in the contract ───────────────────────────────────────────────────
def test_an_option_a_rule_removed_never_carries_an_estimate():
    card = load("AnswerCardV1")
    card["effects"][0]["status"] = "EXCLUDED"  # an excluded row that still has numbers
    with pytest.raises(ValidationError, match="never shows an estimate"):
        AnswerCardV1.model_validate(card)
    card = load("AnswerCardV1")
    card["excluded"] = [{"option": card["effects"][0]["option"], "rule_id": "R01", "source": "label"}]
    with pytest.raises(ValidationError, match="must be EXCLUDED"):
        AnswerCardV1.model_validate(card)


def test_the_card_keeps_the_intended_use_sentence_and_the_clinician_decides():
    assert AnswerCardV1.model_validate(load("AnswerCardV1")).intended_use == INTENDED_USE
    card = load("AnswerCardV1")
    card["intended_use"] = "Research prototype."
    with pytest.raises(ValidationError):
        AnswerCardV1.model_validate(card)
    card = load("AnswerCardV1")
    card["decision"] = "You should add an SGLT2 inhibitor."
    with pytest.raises(ValidationError):
        AnswerCardV1.model_validate(card)


def test_evidence_level_is_never_high_and_a_card_shows_at_most_four_cited_claims():
    card = load("AnswerCardV1")
    card["evidence_levels"][0]["level"] = "High"
    with pytest.raises(ValidationError):
        AnswerCardV1.model_validate(card)
    card = load("AnswerCardV1")
    card["claims"] = card["claims"] * 5
    with pytest.raises(ValidationError):
        AnswerCardV1.model_validate(card)
    card = load("AnswerCardV1")
    card["claims"][0]["citations"] = []
    with pytest.raises(ValidationError):
        AnswerCardV1.model_validate(card)


def test_drivers_are_not_allowed_for_an_option_the_rules_removed():
    req = load("LLMRequestV1")
    req["excluded_by_rules"] = [{"option": "SGLT2i", "rule_id": "R01", "source": "label"}]
    with pytest.raises(ValidationError, match="removed"):
        LLMRequestV1.model_validate(req)


def test_a_guarded_draft_carries_a_draft_only_when_it_passed():
    g = load("GuardedDraftV1")
    g["status"] = "FALLBACK"
    with pytest.raises(ValidationError):
        GuardedDraftV1.model_validate(g)
    g = load("GuardedDraftV1")
    g["draft"] = None
    with pytest.raises(ValidationError):
        GuardedDraftV1.model_validate(g)
    g["status"] = "FALLBACK"
    GuardedDraftV1.model_validate(g)


# ── openapi.json and web/types.d.ts are generated, and must be fresh ───────────────────────────
def test_openapi_json_is_fresh():
    import subprocess

    r = subprocess.run([sys.executable, str(ROOT / "scripts/export_openapi.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_openapi_has_the_three_endpoints_and_all_twelve_models():
    spec = json.loads((ROOT / "openapi.json").read_text(encoding="utf-8"))
    assert sorted(spec["paths"]) == ["/api/v1/ask", "/api/v1/health", "/api/v1/recommend"]
    assert set(MODELS) <= set(spec["components"]["schemas"])
    for name, schema in spec["components"]["schemas"].items():
        if name.endswith("V1"):
            assert schema.get("additionalProperties") is False, name
    assert INTENDED_USE in spec["info"]["description"]


def test_types_d_ts_matches_openapi_json():
    ts = (ROOT / "web/types.d.ts").read_text(encoding="utf-8")
    sha = hashlib.sha256((ROOT / "openapi.json").read_bytes()).hexdigest()
    assert f"openapi.json sha256: {sha}" in ts, "run: bash scripts/make_types.sh"
    for name in MODELS:
        assert re.search(rf"\b{name}\b", ts), name
    assert "openapi-typescript@" in ts.splitlines()[0]
