"""The clinical guardrails: the cited table, one test per rule, and the safety invariants.

Every threshold here is read from app/clinical/guardrails.v1.yaml — the tests never repeat
a clinical number, so a doctor changing the table changes the tests with it.
"""

import textwrap

import pytest
import yaml

from app.clinical import rules as clinical_rules
from app.clinical.rules import DRAFT_WARNING, RuleProblem, load
from app.pipeline import clinical_guardrails
from app.schemas import OptionStatus
from conftest import PATIENT

TABLE = load()
BY_ID = {rule.id: rule for rule in TABLE.rules}

# A patient every option is fine for: good kidneys, no history of anything.
WELL = {**PATIENT, "egfr_ml_min_1_73m2": 62, "age_years": 58}

# What makes each rule in the table fire. The thresholds come from the rules themselves.
TRIGGERS = {
    "G00_metformin_egfr_lt30": {"egfr_ml_min_1_73m2": 25},
    "G00b_missing_egfr": {"egfr_ml_min_1_73m2": None},
    "G01_sglt2i_egfr_lt30": {"egfr_ml_min_1_73m2": 25},
    "G02_sglt2i_egfr_30_to_45": {"egfr_ml_min_1_73m2": 40},
    "G03_sglt2i_past_dka": {"past_dka": True},
    "G04_sglt2i_recurrent_genital_infection": {"recurrent_genital_or_urinary_infection": True},
    "G07_dpp4i_heart_failure": {"heart_failure": True},
    "G08_dpp4i_past_pancreatitis": {"past_pancreatitis": True},
    "G09_dpp4i_egfr_lt45": {"egfr_ml_min_1_73m2": 40},
    "G10_su_past_severe_hypo": {"past_hypoglycaemia": "severe"},
    "G11_su_past_mild_hypo": {"past_hypoglycaemia": "mild"},
    "G12_su_egfr_lt30": {"egfr_ml_min_1_73m2": 25},
    "G15_sglt2i_ckd_info": {"ckd": True, "egfr_ml_min_1_73m2": 40},
    "G16_sglt2i_ascvd_hf_info": {"established_ascvd": True},
}


def patient(**changes) -> dict:
    values = {key: value for key, value in WELL.items() if key != "type"}
    values.setdefault("budget_inr_per_month", None)
    values.update(changes)
    return values


def ask(client, text="What should I add?", **changes):
    part = {"type": "patient", **{k: v for k, v in patient(**changes).items() if v is not None}}
    body = {"schema_version": "1.0", "client_trace_id": "abc12345",
            "parts": [{"type": "text", "text": text}, part]}
    return client.post("/api/v1/chat", json=body).json()


def options_of(reply) -> dict[str, dict]:
    part = next(part for part in reply["parts"] if part["type"] == "options")
    return {option["option"]: option for option in part["options"]}


# ── the table ────────────────────────────────────────────────────────────────


def test_every_rule_in_the_table_is_covered_by_a_test():
    """If someone adds a rule, this fails until it has a trigger here."""
    assert set(BY_ID) == set(TRIGGERS)


def test_the_incomplete_rule_is_refused_and_never_fires():
    assert TABLE.refused == ["G13_su_older_adult: it still contains TODO"]
    assert "G13_su_older_adult" not in BY_ID


def test_strict_loading_raises_so_review_cannot_miss_it():
    with pytest.raises(RuleProblem, match="G13_su_older_adult: it still contains TODO"):
        load(strict=True)


def test_every_rule_in_use_has_a_source():
    for rule in TABLE.rules:
        assert rule.sources and all(source.strip() for source in rule.sources), rule.id


def test_the_table_is_still_a_draft_until_a_doctor_reviews_it():
    assert TABLE.is_draft and all(rule.reviewed_by is None for rule in TABLE.rules)


@pytest.mark.parametrize("rule_id", sorted(TRIGGERS))
def test_each_rule_fires_for_its_patient_and_not_for_a_well_one(rule_id):
    rule = BY_ID[rule_id]
    assert clinical_rules.applies(rule, patient(**TRIGGERS[rule_id])), f"{rule_id} should fire"
    assert not clinical_rules.applies(rule, patient()), f"{rule_id} should not fire for a well patient"


def test_a_rule_cannot_fire_on_a_value_that_was_not_entered():
    assert not clinical_rules.applies(BY_ID["G01_sglt2i_egfr_lt30"], patient(egfr_ml_min_1_73m2=None))


# ── conditions are data, not code ────────────────────────────────────────────


@pytest.mark.parametrize(
    "when",
    ["__import__('os').system('ls')", "open('/etc/passwd').read()", "egfr_ml_min_1_73m2.__class__",
     "[x for x in (1, 2)]", "age_years >= TODO_AGE"],
)
def test_a_condition_that_is_not_a_plain_comparison_is_refused(when):
    with pytest.raises(RuleProblem):
        clinical_rules.compile_condition(when)


def test_a_rule_that_asks_for_a_field_we_do_not_collect_is_caught():
    rule = BY_ID["G01_sglt2i_egfr_lt30"]
    with pytest.raises(RuleProblem, match="does not collect"):
        clinical_rules.applies(rule, {"something_else": 1})


def test_a_rule_without_a_source_is_refused(tmp_path):
    table = tmp_path / "rules.yaml"
    table.write_text(textwrap.dedent("""
        version: test
        rules:
          - id: R1
            scope: option
            option: sglt2i
            when: "egfr_ml_min_1_73m2 < 30"
            action: do_not_use
            reason: "because"
            source: null
    """), encoding="utf-8")
    with pytest.raises(RuleProblem, match="no source"):
        load(table, strict=True)


def test_a_table_with_no_usable_rules_refuses_to_load(tmp_path):
    table = tmp_path / "rules.yaml"
    table.write_text("version: test\nrules:\n  - id: R1\n    scope: patient\n    when: TODO\n", encoding="utf-8")
    with pytest.raises(RuleProblem, match="no usable rules"):
        load(table)


# ── through the API ──────────────────────────────────────────────────────────


def test_a_well_patient_gets_all_three_options(client):
    options = options_of(ask(client))
    assert [option["status"] for option in options.values()] == ["safe_to_consider"] * 3
    assert set(options) == {"sglt2i", "dpp4i", "sulfonylurea"}


def test_every_reply_says_the_table_is_a_draft(client):
    part = next(part for part in ask(client)["parts"] if part["type"] == "options")
    assert part["draft_warning"] == DRAFT_WARNING and part["rules_version"] == TABLE.version


def test_a_contraindicated_option_is_do_not_use_with_its_reason_and_source(client):
    sglt2i = options_of(ask(client, past_dka=True))["sglt2i"]
    rule = BY_ID["G03_sglt2i_past_dka"]
    assert sglt2i["status"] == "do_not_use"
    assert rule.reason in sglt2i["reasons"] and rule.sources[0] in sglt2i["sources"]
    assert rule.id in sglt2i["rule_ids"]


def test_check_first_is_reported_with_its_reason(client):
    dpp4i = options_of(ask(client, heart_failure=True))["dpp4i"]
    assert dpp4i["status"] == "check_first"
    assert BY_ID["G07_dpp4i_heart_failure"].reason in dpp4i["reasons"]


def test_do_not_use_beats_check_first_for_the_same_option(client):
    """eGFR 40 makes SGLT2i "check first"; past DKA makes it "do not use"."""
    sglt2i = options_of(ask(client, egfr_ml_min_1_73m2=40, past_dka=True))["sglt2i"]
    assert sglt2i["status"] == "do_not_use"
    assert len(sglt2i["reasons"]) == 2  # both reasons are still shown


def test_an_info_rule_is_a_note_not_a_restriction(client):
    sglt2i = options_of(ask(client, established_ascvd=True))["sglt2i"]
    assert sglt2i["status"] == "safe_to_consider" and sglt2i["notes"]


def test_a_patient_rule_stops_the_whole_question(client):
    reply = ask(client, egfr_ml_min_1_73m2=25)
    assert reply["outcome"] == "blocked"
    assert reply["reason_code"] == "insufficient_evidence"
    assert reply["blocked_reason"] == BY_ID["G00_metformin_egfr_lt30"].reason
    assert reply["parts"] == []


def test_without_egfr_the_stage_abstains_instead_of_guessing(client):
    reply = ask(client, egfr_ml_min_1_73m2=None)
    assert reply["outcome"] == "blocked" and reply["reason_code"] == "insufficient_evidence"
    assert reply["blocked_reason"] == BY_ID["G00b_missing_egfr"].reason


def test_guardrails_run_before_the_causal_engine(client, chat_body):
    stages = [stage["name"] for stage in client.post("/api/v1/chat", json=chat_body()).json()["stages"]]
    assert stages.index("clinical_guardrails") < stages.index("causal_engine")


def test_a_removed_option_never_reaches_the_causal_engine(client, monkeypatch):
    from app.pipeline import causal_engine
    from app.pipeline.context import not_built_yet

    seen = {}

    def remember(ctx):
        seen["options"] = [option.option for option in ctx.options]
        seen["removed"] = [option.option for option in ctx.removed_options]
        return not_built_yet(causal_engine.NAME)

    monkeypatch.setattr(causal_engine, "run", remember)
    ask(client, past_dka=True)

    assert seen["removed"] == ["sglt2i"] and "sglt2i" not in seen["options"]
    assert seen["options"] == ["dpp4i", "sulfonylurea"]


def test_when_nothing_may_be_used_the_stage_abstains(client, tmp_path, monkeypatch):
    """Every option removed -> say so, never rank the unusable."""
    table = tmp_path / "all-blocked.yaml"
    table.write_text(
        "version: test-all-blocked\nrules:\n"
        + "".join(
            textwrap.dedent(f"""\
              - id: X_{option}
                scope: option
                option: {option}
                when: "egfr_ml_min_1_73m2 > 0"
                action: do_not_use
                reason: "Not usable in this made-up table ({option})."
                source: {{title: "test", version: "1", section: "1", url: null}}
            """)
            for option in ("sglt2i", "dpp4i", "sulfonylurea")
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(clinical_rules, "RULES_FILE", table)
    clinical_guardrails.reset()
    try:
        reply = ask(client)
        assert reply["outcome"] == "blocked" and reply["reason_code"] == "insufficient_evidence"
        assert "None of the three add-on options can be used" in reply["blocked_reason"]
        assert "Not usable in this made-up table (dpp4i)." in reply["blocked_reason"]
    finally:
        clinical_guardrails.reset()  # the real table again for the next test


def test_the_stage_says_what_it_did(client):
    reply = ask(client, past_dka=True)
    stage = next(s for s in reply["stages"] if s["name"] == "clinical_guardrails")
    assert stage["status"] == "passed" and stage["detail"] == "2 of 3 options may be used; removed: sglt2i"


def test_patient_values_are_not_in_the_stage_detail(client):
    reply = ask(client, egfr_ml_min_1_73m2=40)
    assert "40" not in yaml.safe_dump([stage["detail"] for stage in reply["stages"]])
