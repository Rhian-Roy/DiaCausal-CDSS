"""Load data/params.yaml and refuse to run if any number has no source or status.

Plain English: every number the generator or the engine uses must say where it came from
(`source`) and how much we trust it (`status`: CITED, ASSUMED-DIRECTIONAL or TEAM-SET).
If one is missing, we stop with an error instead of quietly using an unsourced number.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
PARAMS_PATH = DATA_DIR / "params.yaml"
RULES_PATH = DATA_DIR / "rules.csv"
PRICES_PATH = DATA_DIR / "prices.csv"

STATUSES = ("CITED", "ASSUMED-DIRECTIONAL", "TEAM-SET")
# Sections that may only contain sourced entries (never a bare number).
SOURCED_SECTIONS = ("generator", "engine", "display", "context")
ENTRY_KEYS = {"value", "unit", "source", "status", "note"}


class ParamsError(ValueError):
    """params.yaml is missing a source or status, or has a bare number."""


def file_hash(path: Path) -> str:
    """Short fingerprint of a file, used as its version in every reply."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:10]


def _is_entry(node: Any) -> bool:
    return isinstance(node, dict) and "value" in node


def _check(node: Any, where: str, sources: dict[str, str], problems: list[str]) -> None:
    if _is_entry(node):
        extra = set(node) - ENTRY_KEYS
        if extra:
            problems.append(f"{where}: unknown keys {sorted(extra)}")
        source = node.get("source")
        if not isinstance(source, str) or not source.strip():
            problems.append(f"{where}: no source")
        status = node.get("status")
        if status not in STATUSES:
            problems.append(f"{where}: status must be one of {STATUSES}, got {status!r}")
        return
    if isinstance(node, dict):
        for key, child in node.items():
            _check(child, f"{where}.{key}", sources, problems)
        return
    problems.append(f"{where}: a bare value ({node!r}) — wrap it as {{value, unit, source, status}}")


@dataclass(frozen=True)
class Params:
    """The validated contents of params.yaml, plus its fingerprint."""

    raw: dict
    version: str
    fingerprint: str

    def get(self, dotted: str) -> Any:
        """Value of one entry, e.g. params.get("engine.overlap_min_propensity") -> 0.05."""
        node: Any = self.raw
        for part in dotted.split("."):
            node = node[part]
        if not _is_entry(node):
            raise KeyError(f"{dotted} is a group, not a single value")
        return node["value"]

    def entry(self, dotted: str) -> dict:
        node: Any = self.raw
        for part in dotted.split("."):
            node = node[part]
        return node

    def group(self, dotted: str) -> dict[str, Any]:
        """{key: value} for every entry directly inside a group."""
        node: Any = self.raw
        for part in dotted.split("."):
            node = node[part]
        return {k: v["value"] for k, v in node.items() if _is_entry(v)}

    @property
    def arms(self) -> list[str]:
        return list(self.raw["arms"])

    def arm_name(self, arm: str) -> str:
        return self.raw["arms"][arm]["name"]

    def source_text(self, key: str) -> str:
        """The full citation for a source key (free text is returned as it is)."""
        return self.raw["sources"].get(key, key)

    def entries(self) -> list[tuple[str, dict]]:
        """Every sourced entry as (dotted path, entry) — for the params table in the docs."""
        out: list[tuple[str, dict]] = []

        def walk(node: Any, where: str) -> None:
            if _is_entry(node):
                out.append((where, node))
            elif isinstance(node, dict):
                for k, v in node.items():
                    walk(v, f"{where}.{k}" if where else k)

        for section in SOURCED_SECTIONS:
            walk(self.raw.get(section, {}), section)
        return out


def validate(raw: dict) -> None:
    """Raise ParamsError listing every problem, or return quietly."""
    problems: list[str] = []
    sources = raw.get("sources") or {}
    if not isinstance(sources, dict) or not sources:
        problems.append("sources: missing")
    for section in SOURCED_SECTIONS:
        if section not in raw:
            problems.append(f"{section}: missing section")
            continue
        _check(raw[section], section, sources, problems)
    if set(raw.get("arms", {})) != {"SGLT2i", "DPP4i", "SU"}:
        problems.append("arms: must be exactly SGLT2i, DPP4i, SU")
    if problems:
        raise ParamsError("params.yaml refused:\n  " + "\n  ".join(problems))


def load_params(path: Path | str = PARAMS_PATH) -> Params:
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ParamsError("params.yaml refused: not a mapping")
    validate(raw)
    return Params(raw=raw, version=str(raw.get("version", "?")), fingerprint=file_hash(path))
