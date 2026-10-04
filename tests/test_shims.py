"""Shims (docs/RESTRUCTURE_PLAN.md, section 4): an old import path must give the very same module as the new one,
so a test that patches `old.X` reaches the real code, and the shim file stays tiny."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from diacausal.registry import REGISTRY

ROOT = Path(__file__).resolve().parent.parent
SHIMS = [e for e in REGISTRY if e.shim_for]
ALIASES = [e for e in SHIMS if e.alias]
SPLIT = [e for e in SHIMS if not e.alias]

# estimators.py before it was split: every name the old module offered, which the shim must still offer.
OLD_ESTIMATORS_API = (
    "IDX TARGETS Estimate _est _from_influence _matched_outcomes aipw aipw_scores by_target crossfit_outcomes DRLearner "
    "ipw ipw_mean levels_to_targets matching naive outcome_model pseudo_outcomes s_learner t_learner"
).split()


@pytest.mark.parametrize("entry", ALIASES, ids=lambda e: e.module)
def test_the_old_path_is_the_new_module(entry):
    assert importlib.import_module(entry.module) is importlib.import_module(entry.shim_for)


@pytest.mark.parametrize("entry", SHIMS, ids=lambda e: e.module)
def test_a_shim_file_is_tiny_and_names_the_new_module(entry):
    path = ROOT / (entry.module.replace(".", "/") + ".py")
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) <= 25, f"{path.name} is {len(lines)} lines: a shim must stay tiny"
    assert any(entry.shim_for in line for line in lines), f"{path.name} does not name {entry.shim_for}"


def test_the_split_estimators_shim_offers_every_old_name_and_they_are_the_real_objects():
    import diacausal.causal_inference.dr_learner as dr
    import diacausal.causal_inference.estimators as es
    import diacausal_engine.estimators as old

    assert [e.module for e in SPLIT] == ["diacausal_engine.estimators"]
    for name in OLD_ESTIMATORS_API:
        assert getattr(old, name) is getattr(es, name, None) or getattr(old, name) is getattr(dr, name, None), name
    assert not hasattr(es, "DRLearner") and not hasattr(es, "pseudo_outcomes"), "they moved to dr_learner.py"


def test_dr_learner_does_not_create_an_import_cycle():
    import ast
    from pathlib import Path as P

    tree = ast.parse((ROOT / "diacausal/causal_inference/estimators.py").read_text())
    imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert "diacausal.causal_inference.dr_learner" not in imported


def test_a_patch_through_a_shim_reaches_the_real_module(monkeypatch):
    import diacausal.config as real
    import diacausal_engine.config as old

    monkeypatch.setattr(old, "ROOT", Path("/nowhere"))
    assert real.ROOT == Path("/nowhere")


def test_the_old_package_still_exports_the_shared_constants():
    import diacausal
    import diacausal.config
    import diacausal_engine

    assert diacausal_engine.INTENDED_USE is diacausal.INTENDED_USE
    assert diacausal_engine.__version__ == diacausal.__version__ == "0.3.0"
    assert diacausal_engine.ARMS is diacausal.config.ARMS
    assert diacausal_engine.CONTRASTS is diacausal.config.CONTRASTS


def test_the_one_root_is_the_repository_root():
    from diacausal.config import DATA_DIR, KNOWLEDGE_DIR, RESULTS_DIR, ROOT as R, WEB_DIR

    assert R == ROOT and (R / "pytest.ini").exists()
    assert DATA_DIR.is_dir() and WEB_DIR.is_dir() and RESULTS_DIR.is_dir() and KNOWLEDGE_DIR.is_dir()


def test_python_dash_m_on_the_old_name_forwards_to_the_new_module():
    import subprocess
    import sys

    old = subprocess.run([sys.executable, "-m", "diacausal_engine.benchmark", "--help"], cwd=ROOT, capture_output=True, text=True)
    new = subprocess.run([sys.executable, "-m", "diacausal.causal_inference.benchmark", "--help"], cwd=ROOT, capture_output=True, text=True)
    assert old.returncode == 0 and new.returncode == 0, old.stderr + new.stderr
    assert old.stdout == new.stdout and "--quick" in old.stdout


def test_the_old_uvicorn_target_still_resolves():
    import diacausal.api.main as new
    import diacausal_engine.api as old

    assert old.app is new.app and old.create_app is new.create_app
