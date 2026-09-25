"""Step (b): safety rules loaded from data/rules.csv — they run BEFORE any estimate.

Plain English: a table written by the team from cited drug labels says, for each drug
class, which patient condition means "exclude" or "caution". This file only READS that
table and applies it; no threshold is typed into the code. An excluded option is removed
before the causal engine sees it, so it never gets a number. A caution keeps the option
but shows the reason and its source to the clinician.

Rules marked UNVERIFIED still apply (excluding or cautioning is the safe direction) and
are labelled so the doctor can see that the cut-off is a team choice awaiting review.
"""

from __future__ import annotations

import csv
import operator
from dataclasses import dataclass, field
from pathlib import Path

from diacausal_engine import ARMS
from diacausal_engine.config import RULES_PATH, file_hash

COLUMNS = [
    "rule_id", "arm", "representative_molecule", "field", "op", "value",
    "action", "message", "source", "section", "status",
]
OPS = {"lt": operator.lt, "le": operator.le, "gt": operator.gt, "ge": operator.ge, "eq": operator.eq}
OP_WORDS = {"lt": "<", "le": "<=", "gt": ">", "ge": ">=", "eq": "="}
ACTIONS = ("EXCLUDE", "CAUTION")
RULE_STATUSES = ("VERIFIED", "UNVERIFIED")
# The patient fields a rule may test (the engine's patient schema uses the same names).
FIELDS = ("age", "egfr", "t1d", "dka_history", "pancreatitis_history", "hf", "hypo_history")


class RulesError(ValueError):
    """data/rules.csv has a row the engine cannot trust."""


@dataclass(frozen=True)
class Rule:
    rule_id: str
    arm: str
    representative_molecule: str
    field: str
    op: str
    value: float
    action: str
    message: str
    source: str
    section: str
    status: str

    def applies(self, patient: dict) -> bool:
        if self.field not in patient or patient[self.field] is None:
            # Fail closed: a rule we cannot check is a reason to stop, never to pass.
            raise RulesError(f"{self.rule_id} needs '{self.field}', which was not given")
        return OPS[self.op](float(patient[self.field]), self.value)

    @property
    def condition(self) -> str:
        return f"{self.field} {OP_WORDS[self.op]} {self.value:g}"


@dataclass
class ArmVerdict:
    """What the rules say about one option for one patient."""

    arm: str
    excluded: bool = False
    fired: list[Rule] = field(default_factory=list)

    @property
    def cautions(self) -> list[Rule]:
        return [r for r in self.fired if r.action == "CAUTION"]

    @property
    def exclusions(self) -> list[Rule]:
        return [r for r in self.fired if r.action == "EXCLUDE"]

    @property
    def status(self) -> str:
        if self.excluded:
            return "excluded"
        return "caution" if self.cautions else "no_rule_fired"


@dataclass(frozen=True)
class RuleTable:
    rules: tuple[Rule, ...]
    version: str

    def apply(self, patient: dict) -> dict[str, ArmVerdict]:
        verdicts = {arm: ArmVerdict(arm) for arm in ARMS}
        for rule in self.rules:
            if rule.applies(patient):
                v = verdicts[rule.arm]
                v.fired.append(rule)
                if rule.action == "EXCLUDE":
                    v.excluded = True
        return verdicts


def _parse_row(row: dict, line: int) -> Rule:
    where = f"rules.csv line {line} ({row.get('rule_id') or '?'})"
    for col in COLUMNS:
        if not (row.get(col) or "").strip():
            raise RulesError(f"{where}: '{col}' is empty")
    if row["arm"] not in ARMS:
        raise RulesError(f"{where}: unknown arm {row['arm']!r}")
    if row["field"] not in FIELDS:
        raise RulesError(f"{where}: unknown field {row['field']!r}")
    if row["op"] not in OPS:
        raise RulesError(f"{where}: unknown op {row['op']!r}")
    if row["action"] not in ACTIONS:
        raise RulesError(f"{where}: unknown action {row['action']!r}")
    if row["status"] not in RULE_STATUSES:
        raise RulesError(f"{where}: unknown status {row['status']!r}")
    try:
        value = float(row["value"])
    except ValueError as exc:
        raise RulesError(f"{where}: value {row['value']!r} is not a number") from exc
    return Rule(**{**{c: row[c].strip() for c in COLUMNS}, "value": value})


def load_rules(path: Path | str = RULES_PATH) -> RuleTable:
    path = Path(path)
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames != COLUMNS:
            raise RulesError(f"rules.csv columns must be exactly {COLUMNS}, got {reader.fieldnames}")
        rules = tuple(_parse_row(row, i + 2) for i, row in enumerate(reader))
    ids = [r.rule_id for r in rules]
    if len(set(ids)) != len(ids):
        raise RulesError("rules.csv has duplicate rule_id values")
    if not rules:
        raise RulesError("rules.csv has no rules")
    return RuleTable(rules=rules, version=file_hash(path))
