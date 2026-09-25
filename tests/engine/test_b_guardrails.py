"""Step (b): safety rules from data/rules.csv, each with its citation."""

import re
import shutil
from pathlib import Path

import pytest

from diacausal_engine.config import RULES_PATH
from diacausal_engine.guardrails import FIELDS, RulesError, load_rules

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


def test_ten_rules_each_with_a_source_and_section(table):
    assert [r.rule_id for r in table.rules] == [f"R{i:02d}" for i in range(1, 11)]
    for r in table.rules:
        assert r.source and r.section and r.message
        assert r.status in ("VERIFIED", "UNVERIFIED")


def test_nothing_fires_on_a_clear_patient(table):
    assert all(not v.fired for v in table.apply(CLEAR).values())


@pytest.mark.parametrize("rule_id", [f"R{i:02d}" for i in range(1, 11)])
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


def test_no_clinical_threshold_is_typed_into_the_engine_code():
    """Thresholds live only in data/rules.csv and data/params.yaml."""
    pattern = re.compile(r"\b(egfr|hba1c|age|bmi)\w*\"?\]?\s*(<=|>=|<|>|==)\s*\d", re.I)
    for f in (ROOT / "diacausal_engine").glob("*.py"):
        for n, line in enumerate(f.read_text().splitlines(), 1):
            assert not pattern.search(line), f"{f.name}:{n}: {line.strip()}"
    assert set(FIELDS) >= {"egfr", "age"}
