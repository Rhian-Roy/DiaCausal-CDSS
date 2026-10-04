"""Step (b): safety rules from data/rules.csv, each with its citation."""

import re
import shutil
from pathlib import Path

import pytest

from diacausal.config import RULES_PATH
from diacausal.guards.rules_loader import FIELDS, load_rules, RulesError

ROOT = Path(__file__).resolve().parents[2]

# A patient no rule fires on (every field the rules need, at a harmless value).
CLEAR = {"age": 50, "egfr": 90, "t1d": 0, "dka_history": 0, "pancreatitis_history": 0, "hf": 0, "hypo_history": 0}


@pytest.fixture(scope="module")
def table():
    return load_rules()


def test_rules_csv_is_exactly_part_6_of_the_build_guide():
    guide = (ROOT / "docs/02_Causal_Engine_Build_Guide.md").read_text()
    block = re.search(r"\*\*data/rules\.csv\*\*\s*```text\n(.*?)```", guide, re.S).group(1)
    assert RULES_PATH.read_text() == block


def test_eleven_rules_each_with_a_source_and_section(table):
    """R01 to R10 are Part 6 as first written; R11 was added by the merge of the rule sources (docs/RULES_MERGE.md)."""
    assert [r.rule_id for r in table.rules] == [f"R{i:02d}" for i in range(1, 12)]
    for r in table.rules:
        assert r.source and r.section and r.message
        assert r.status in ("VERIFIED", "UNVERIFIED")


def test_nothing_fires_on_a_clear_patient(table):
    assert all(not v.fired for v in table.apply(CLEAR).values())


@pytest.mark.parametrize("rule_id", [f"R{i:02d}" for i in range(1, 12)])
def test_each_rule_fires_just_inside_its_boundary_and_not_outside(table, rule_id):
    rule = next(r for r in table.rules if r.rule_id == rule_id)
    inside = {"lt": rule.value - 0.1, "le": rule.value, "ge": rule.value, "gt": rule.value + 0.1, "eq": rule.value}[rule.op]
    outside = {"lt": rule.value, "le": rule.value + 0.1, "ge": rule.value - 0.1, "gt": rule.value, "eq": 1 - rule.value}[rule.op]
    fired = table.apply({**CLEAR, rule.field: inside})[rule.arm].fired
    assert rule in fired
    assert rule not in table.apply({**CLEAR, rule.field: outside})[rule.arm].fired


def test_egfr_40_excludes_sglt2i_and_cautions_the_others(table):
    v = table.apply({**CLEAR, "egfr": 40})
    assert v["SGLT2i"].excluded and v["SGLT2i"].exclusions[0].rule_id == "R01"
    assert not v["DPP4i"].excluded and [r.rule_id for r in v["DPP4i"].cautions] == ["R04"]
    assert not v["SU"].excluded and [r.rule_id for r in v["SU"].cautions] == ["R09"]


def test_egfr_below_30_excludes_sulfonylurea(table):
    v = table.apply({**CLEAR, "egfr": 25})
    assert v["SU"].excluded and "R10" in [r.rule_id for r in v["SU"].exclusions]


def test_egfr_below_30_excludes_all_three_options_because_metformin_is_contraindicated(table):
    v = table.apply({**CLEAR, "egfr": 25})
    assert all(x.excluded for x in v.values())
    assert "R11" in [r.rule_id for r in v["DPP4i"].exclusions]  # the merge added this one; R01 and R10 cover the other two


def test_a_history_of_ketoacidosis_now_excludes_sglt2i(table):
    v = table.apply({**CLEAR, "dka_history": 1})
    assert v["SGLT2i"].excluded and [r.rule_id for r in v["SGLT2i"].exclusions] == ["R03"]
    assert not v["DPP4i"].fired and not v["SU"].fired


# ── the merge of the rule sources (docs/RULES_MERGE.md): the engine table is never weaker than the chat-app table ──

# chat-app rule id -> the rows of data/rules.csv that cover it (the engine arm and condition must be the same or wider)
YAML_TO_CSV = {
    "G00_metformin_egfr_lt30": ["R01", "R10", "R11"],  # abstain for the patient = every option excluded
    "G01_sglt2i_egfr_lt30": ["R01"], "G02_sglt2i_egfr_30_to_45": ["R01"], "G03_sglt2i_past_dka": ["R03"],
    "G07_dpp4i_heart_failure": ["R06"], "G08_dpp4i_past_pancreatitis": ["R05"], "G09_dpp4i_egfr_lt45": ["R04"],
    "G10_su_past_severe_hypo": ["R07"], "G11_su_past_mild_hypo": ["R07"], "G12_su_egfr_lt30": ["R10"],
}
# chat-app rules the CSV format cannot hold, each with the reason (listed in docs/RULES_MERGE.md)
NOT_MERGED = {
    "G00b_missing_egfr": "the engine already refuses a patient without eGFR (a rule that cannot be checked fails closed)",
    "G04_sglt2i_recurrent_genital_infection": "needs a patient field the engine does not have",
    "G13_su_older_adult": "the chat table has no age yet (TODO_AGE), so it cannot fire; R08 has 65",
    "G15_sglt2i_ckd_info": "information only (action INFO), needs fields ckd and eGFR 20",
    "G16_sglt2i_ascvd_hf_info": "information only (action INFO), needs field established_ascvd",
}
STRENGTH = {"info": 0, "check_first": 1, "CAUTION": 1, "do_not_use": 2, "abstain": 2, "EXCLUDE": 2}


def test_every_chat_app_rule_is_merged_or_listed_with_a_reason(table):
    import yaml

    yml = yaml.safe_load((ROOT / "backend/app/clinical/guardrails.v1.yaml").read_text())
    ids = {r["id"] for r in yml["rules"]}
    assert ids == set(YAML_TO_CSV) | set(NOT_MERGED), "a rule of the chat-app table is neither merged nor explained"
    csv_ids = {r.rule_id for r in table.rules}
    assert all(set(v) <= csv_ids for v in YAML_TO_CSV.values())


def test_the_engine_table_is_never_weaker_than_the_chat_app_table(table):
    import yaml

    yml = yaml.safe_load((ROOT / "backend/app/clinical/guardrails.v1.yaml").read_text())
    by_id = {r.rule_id: r for r in table.rules}
    for rule in yml["rules"]:
        if rule["id"] not in YAML_TO_CSV:
            continue
        strongest = max(STRENGTH[by_id[c].action] for c in YAML_TO_CSV[rule["id"]])
        assert strongest >= STRENGTH[rule["action"]], f"{rule['id']} is stricter in the chat-app table than in rules.csv"


def test_a_missing_field_fails_closed(table):
    patient = dict(CLEAR)
    del patient["egfr"]
    with pytest.raises(RulesError, match="needs 'egfr'"):
        table.apply(patient)


def _broken(tmp_path, old, new):
    path = tmp_path / "rules.csv"
    text = RULES_PATH.read_text()
    assert old in text
    path.write_text(text.replace(old, new, 1))
    return path


@pytest.mark.parametrize(
    "old,new,why",
    [
        (',"FARXIGA (dapagliflozin) US prescribing information (DailyMed); KDIGO 2022 Diabetes in CKD",', ',"",', "'source' is empty"),
        ("R01,SGLT2i,dapagliflozin,egfr,lt,", "R01,SGLT2i,dapagliflozin,egfr,below,", "unknown op"),
        ("R01,SGLT2i,dapagliflozin,egfr,lt,45,EXCLUDE", "R01,SGLT2i,dapagliflozin,egfr,lt,45,MAYBE", "unknown action"),
        ("R02,SGLT2i,dapagliflozin,t1d,", "R02,GLP1RA,dapagliflozin,t1d,", "unknown arm"),
        ("R02,SGLT2i,dapagliflozin,t1d,", "R02,SGLT2i,dapagliflozin,weight,", "unknown field"),
        ("R01,SGLT2i,dapagliflozin,egfr,lt,45,", "R01,SGLT2i,dapagliflozin,egfr,lt,forty-five,", "not a number"),
    ],
)
def test_a_bad_row_is_refused(tmp_path, old, new, why):
    with pytest.raises(RulesError, match=why):
        load_rules(_broken(tmp_path, old, new))


def test_duplicate_rule_ids_are_refused(tmp_path):
    with pytest.raises(RulesError, match="duplicate"):
        load_rules(_broken(tmp_path, "R02,SGLT2i", "R01,SGLT2i"))


def test_no_clinical_threshold_is_typed_into_the_engine_code(engine_code_files):
    """Thresholds live only in data/rules.csv and data/params.yaml."""
    pattern = re.compile(r"\b(egfr|hba1c|age|bmi)\w*\"?\]?\s*(<=|>=|<|>|==)\s*\d", re.I)
    for f in engine_code_files:
        for n, line in enumerate(f.read_text().splitlines(), 1):
            assert not pattern.search(line), f"{f.name}:{n}: {line.strip()}"
    assert set(FIELDS) >= {"egfr", "age"}
