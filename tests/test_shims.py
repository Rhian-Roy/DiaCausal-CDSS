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
OLD_INGEST_API = (
    "ROOT Chunk _pieces as_dicts chunk_document split_sections CLEARED CORPUS SOURCES_CSV LicenceError ingest "
    "is_confirmed load_sources"
).split()
OLD_EXPLAIN_API = (
    "BACKENDS CALLERS DOSE_QUESTION NO_DOSE_NOTE PROMPT _ANSWER_SPLIT _BULLET _CITES _SPLIT _content _post _reply _usable "
    "_weighted_overlap build_prompt call_ollama check_answer explain main render sentences template"
).split()
OLD_RETRIEVE_API = "BM25 TOKEN tokens DOSE WITHHELD Retriever index_text rrf".split()
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


def test_the_split_shims_are_exactly_the_modules_that_were_split():
    assert sorted(e.module for e in SPLIT) == ["diacausal_engine.estimators", "diacausal_rag.explain", "diacausal_rag.ingest", "diacausal_rag.retrieve"]


def _offers(old_module: str, new_modules: list[str], names: list[str]):
    old = importlib.import_module(old_module)
    news = [importlib.import_module(m) for m in new_modules]
    for name in names:
        theirs = [getattr(m, name) for m in news if hasattr(m, name)]
        assert theirs, f"{name} is in none of {new_modules}"
        assert any(getattr(old, name) is t for t in theirs), f"{old_module}.{name} is not the real object"


def test_the_split_estimators_shim_offers_every_old_name_and_they_are_the_real_objects():
    import diacausal.causal_inference.estimators as es

    _offers("diacausal_engine.estimators", ["diacausal.causal_inference.estimators", "diacausal.causal_inference.dr_learner"], OLD_ESTIMATORS_API)
    assert not hasattr(es, "DRLearner") and not hasattr(es, "pseudo_outcomes"), "they moved to dr_learner.py"


def test_the_split_ingest_shim_offers_every_old_name_and_they_are_the_real_objects():
    import diacausal.config as cfg
    import diacausal_rag.ingest as old

    _offers("diacausal_rag.ingest", ["diacausal.rag.ingest.chunking", "diacausal.rag.ingest.licence_gate", "diacausal.config"], OLD_INGEST_API)
    assert old.load_config is cfg.load_rag_config and old.CONFIG == cfg.RAG_CONFIG_PATH  # renamed on the way


def test_the_split_explain_shim_offers_every_old_name_and_they_are_the_real_objects():
    _offers("diacausal_rag.explain", ["diacausal.llm.explain", "diacausal.llm.prompt_builder", "diacausal.llm.providers.template",
                                      "diacausal.llm.providers.ollama", "diacausal.guards.output_guards"], OLD_EXPLAIN_API)


def test_explain_modules_form_a_one_way_chain():
    """output_guards <- template <- explain; prompt_builder <- explain: no module imports one that imports it."""
    import ast

    def imported(path):
        tree = ast.parse((ROOT / path).read_text())
        return {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}

    assert not {m for m in imported("diacausal/guards/output_guards.py") if m.startswith("diacausal.llm")}
    assert "diacausal.llm.explain" not in imported("diacausal/llm/providers/template.py") | imported("diacausal/llm/prompt_builder.py") \
        | imported("diacausal/llm/providers/ollama.py")


def test_the_prompt_text_sits_next_to_its_builder():
    from diacausal.llm.prompt_builder import PROMPT

    assert (ROOT / "diacausal/llm/prompt.v1.txt").read_text(encoding="utf-8") == PROMPT
    assert not (ROOT / "diacausal_rag/prompt.v1.txt").exists()


def test_the_split_retrieve_shim_offers_every_old_name_and_they_are_the_real_objects():
    _offers("diacausal_rag.retrieve", ["diacausal.rag.index.bm25", "diacausal.rag.retrieve.hybrid"], OLD_RETRIEVE_API)


def test_the_rag_modules_that_would_form_a_cycle_do_not():
    """licence_gate is imported by chunking at the top; chunking is imported by licence_gate only inside ingest()."""
    import ast

    def top_level_imports(path):
        tree = ast.parse((ROOT / path).read_text())
        return {n.module for n in tree.body if isinstance(n, ast.ImportFrom) and n.module}

    assert "diacausal.rag.ingest.chunking" not in top_level_imports("diacausal/rag/ingest/licence_gate.py")
    assert "diacausal.rag.retrieve.hybrid" not in top_level_imports("diacausal/rag/index/bm25.py")
    assert "diacausal.rag.retrieve.hybrid" not in top_level_imports("diacausal/rag/index/tfidf.py")


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


def test_python_dash_m_on_the_old_explain_name_forwards_to_the_new_module():
    import subprocess
    import sys

    old = subprocess.run([sys.executable, "-m", "diacausal_rag.explain", "--help"], cwd=ROOT, capture_output=True, text=True)
    new = subprocess.run([sys.executable, "-m", "diacausal.llm.explain", "--help"], cwd=ROOT, capture_output=True, text=True)
    assert old.returncode == 0 and new.returncode == 0, old.stderr + new.stderr
    assert "--backend" in old.stdout and "diacausal.llm.explain" in new.stdout


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
