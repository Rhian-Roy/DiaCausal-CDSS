"""Every module in diacausal/registry.py imports, and every module on disk is in the registry."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from diacausal.registry import REGISTRY, modules

ROOT = Path(__file__).resolve().parent.parent
PACKAGES = ("diacausal", "diacausal_engine", "diacausal_rag")


def _on_disk() -> set[str]:
    found = set()
    for pkg in PACKAGES:
        for path in (ROOT / pkg).rglob("*.py"):
            parts = list(path.relative_to(ROOT).with_suffix("").parts)
            if parts[-1] == "__init__":
                parts.pop()
            found.add(".".join(parts))
    return found


@pytest.mark.parametrize("entry", REGISTRY, ids=lambda e: e.module)
def test_every_registry_entry_imports(entry):
    assert importlib.import_module(entry.module) is not None


def test_the_registry_has_no_duplicates():
    assert len(modules()) == len(set(modules()))


def test_every_module_on_disk_is_in_the_registry():
    missing = sorted(_on_disk() - set(modules()))
    assert not missing, f"add these to diacausal/registry.py: {missing}"


def test_every_registry_entry_exists_on_disk():
    gone = sorted(set(modules()) - _on_disk())
    assert not gone, f"in the registry but no such file: {gone}"
