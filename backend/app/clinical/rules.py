"""Loading and applying the cited clinical rules in guardrails.v1.yaml.

Two safety rules decide the whole design of this file:

1. **Every threshold comes from the table, with a source.** Nothing here invents a number,
   and no language model is involved. A rule with a `TODO` or without a source is refused:
   it never fires, and it is reported loudly (see `RuleProblem` and `load`).
2. **A condition is data, not code.** The `when:` line is a tiny expression language —
   comparisons, `and`/`or`, and "is missing" — parsed and checked against a whitelist.
   Nothing can be called, imported or assigned, so a bad line in the file cannot run code.

While `reviewed_by` is empty the table is a DRAFT, and every answer must say so.
"""

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

RULES_FILE = Path(__file__).resolve().parent / "guardrails.v1.yaml"

OPTIONS = ("sglt2i", "dpp4i", "sulfonylurea")
OPTION_NAMES = {
    "sglt2i": "SGLT2 inhibitor",
    "dpp4i": "DPP-4 inhibitor",
    "sulfonylurea": "Sulfonylurea",
}
ACTIONS = ("abstain", "do_not_use", "check_first", "info")
DRAFT_WARNING = "draft — not clinically reviewed"

Action = Literal["abstain", "do_not_use", "check_first", "info"]


class RuleProblem(Exception):
    """A rule that must not be used: no source, a TODO left in, or a condition we cannot read."""


@dataclass(frozen=True)
class Rule:
    id: str
    scope: Literal["patient", "option"]
    option: str | None
    when: str
    action: Action
    reason: str
    sources: tuple[str, ...]
    requires_field: str | None
    needs_recheck: bool
    reviewed_by: str | None

    @property
    def is_draft(self) -> bool:
        return not self.reviewed_by


@dataclass
class RuleSet:
    version: str
    rules: list[Rule] = field(default_factory=list)
    refused: list[str] = field(default_factory=list)  # "id: why", reported on every reply

    @property
    def is_draft(self) -> bool:
        return any(rule.is_draft for rule in self.rules)

    def for_option(self, option: str) -> list[Rule]:
        return [rule for rule in self.rules if rule.scope == "option" and rule.option == option]

    @property
    def patient_rules(self) -> list[Rule]:
        return [rule for rule in self.rules if rule.scope == "patient"]


# ── the tiny expression language ─────────────────────────────────────────────

_ALLOWED_NODES = (
    ast.Expression, ast.BoolOp, ast.And, ast.Or, ast.UnaryOp, ast.Not,
    ast.Compare, ast.Name, ast.Load, ast.Constant,
    ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq, ast.Is, ast.IsNot,
)

MISSING = " is missing"


def _readable(when: str) -> str:
    """The rule's condition as Python we can parse:
    "x is missing" -> "x is None", and YAML's true/false -> True/False."""
    readable = when.replace(MISSING, " is None")
    return re.sub(r"\b(true|false)\b", lambda match: match[1].capitalize(), readable)


def compile_condition(when: str) -> ast.Expression:
    """Check the condition uses only what we allow, and hand back the parsed tree."""
    try:
        tree = ast.parse(_readable(when), mode="eval")
    except SyntaxError as problem:
        raise RuleProblem(f"the condition {when!r} could not be read: {problem}") from problem
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise RuleProblem(
                f"the condition {when!r} uses {type(node).__name__}, which is not allowed here "
                "(only comparisons, and/or/not, and 'is missing')"
            )
        if isinstance(node, ast.Name) and node.id.isupper():
            raise RuleProblem(f"the condition {when!r} still has a placeholder ({node.id})")
    return tree


def _values_in(tree: ast.Expression) -> set[str]:
    return {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}


def applies(rule: Rule, patient: dict[str, Any]) -> bool:
    """Does this rule fire for this patient? Unknown values mean "cannot tell" -> no."""
    tree = compile_condition(rule.when)
    asks_missing = MISSING in rule.when
    for name in _values_in(tree):
        if name not in patient:
            raise RuleProblem(f"rule {rule.id} asks for {name!r}, which the patient panel does not collect")
        if patient[name] is None and not asks_missing:
            return False  # a rule about eGFR cannot fire when eGFR was not entered
    return bool(eval(compile(tree, "<rule>", "eval"), {"__builtins__": {}}, dict(patient)))  # noqa: S307


# ── loading ──────────────────────────────────────────────────────────────────


def _sources_of(raw: dict) -> tuple[str, ...]:
    source = raw.get("source")
    entries = source if isinstance(source, list) else [source]
    described = []
    for entry in entries:
        if not isinstance(entry, dict) or not entry.get("title"):
            raise RuleProblem("no source")
        parts = [str(entry["title"])]
        for key in ("version", "section"):
            if entry.get(key):
                parts.append(str(entry[key]))
        if entry.get("url"):
            parts.append(str(entry["url"]))
        described.append(" — ".join(parts))
    return tuple(described)


def _rule_from(raw: dict) -> Rule:
    if not isinstance(raw, dict) or not raw.get("id"):
        raise RuleProblem("a rule without an id")
    for key in ("scope", "when", "action", "reason"):
        if not raw.get(key):
            raise RuleProblem(f"no {key}")
    if raw["scope"] not in ("patient", "option"):
        raise RuleProblem(f"unknown scope {raw['scope']!r}")
    if raw["action"] not in ACTIONS:
        raise RuleProblem(f"unknown action {raw['action']!r}")
    if raw["scope"] == "option" and raw.get("option") not in OPTIONS:
        raise RuleProblem(f"unknown option {raw.get('option')!r}")
    if "TODO" in yaml.safe_dump(raw):
        raise RuleProblem("it still contains TODO")

    rule = Rule(
        id=str(raw["id"]),
        scope=raw["scope"],
        option=raw.get("option"),
        when=str(raw["when"]),
        action=raw["action"],
        reason=str(raw["reason"]),
        sources=_sources_of(raw),
        requires_field=raw.get("requires_field"),
        needs_recheck=str(raw.get("verified", "")).startswith("recheck"),
        reviewed_by=raw.get("reviewed_by"),
    )
    compile_condition(rule.when)  # refuse a condition we cannot read, before it is ever used
    return rule


def load(path: Path | None = None, *, strict: bool = False) -> RuleSet:
    """Read the table.

    `strict=True` raises on the first unusable rule — used by the tests and by
    `python -m app.clinical.check`, so a bad table cannot pass review unnoticed.
    `strict=False` (what the running app uses) leaves the unusable rule OUT and records
    why in `refused`, which every reply then carries: dropping one incomplete rule is
    safer than dropping all fifteen by refusing to start.
    """
    path = path or RULES_FILE  # looked up when called, so tests can point at their own file
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    rule_set = RuleSet(version=str(raw.get("version", "unknown")))
    for entry in raw.get("rules", []):
        try:
            rule_set.rules.append(_rule_from(entry))
        except RuleProblem as problem:
            name = entry.get("id", "a rule with no id") if isinstance(entry, dict) else "a rule"
            if strict:
                raise RuleProblem(f"{name}: {problem}") from problem
            rule_set.refused.append(f"{name}: {problem}")
    if not rule_set.rules:
        raise RuleProblem(f"{path} has no usable rules")
    return rule_set
