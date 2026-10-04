"""GuardResultV1 (input guards, plan 8.6) and EligibleOptionsV1 (deterministic rules, run before estimation)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from diacausal.api.schemas.base import OptionName, V1

GuardId = Literal["scope", "identifier", "red_flag", "injection", "range", "length_language", "dose_request"]
GUARD_IDS = ("scope", "identifier", "red_flag", "injection", "range", "length_language", "dose_request")


class GuardCheckV1(V1):
    id: GuardId
    result: Literal["PASS", "BLOCK"]


class GuardResultV1(V1):
    """Seven input checks, in order. A BLOCK stops the request with a notice; the matched word is never shown."""

    status: Literal["PASS", "BLOCK"]
    checks: list[GuardCheckV1] = Field(min_length=1, max_length=len(GUARD_IDS))
    blocked_reason: str | None = Field(default=None, description="plain English; never repeats the matched word")


class RuleHitV1(V1):
    option: OptionName
    rule_id: str = Field(description="a rule id from data/rules.csv, e.g. R04")
    source: str = Field(description="label and section, e.g. 'JANUVIA US prescribing information, Sec 2.2'")


class EligibleOptionsV1(V1):
    """What the rules leave: removed options never reach the causal engine."""

    rules_version: str = Field(description="e.g. rules.csv@<git-sha>")
    excluded: list[RuleHitV1]
    caution: list[RuleHitV1]
    eligible: list[OptionName]
