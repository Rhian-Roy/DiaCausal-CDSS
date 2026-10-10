"""The registry: every importable module of the DiaCausal Python code, with what it is for.

`tests/test_imports.py` imports every entry and fails if a module exists on disk that is not listed
here, so this file cannot drift. Update it in every restructure step (docs/RESTRUCTURE_PLAN.md):
when a module moves, change its `module`; when a shim is left at the old path, keep both lines
(the old one with `shim_for` naming the new module) until the shim is removed (step 9).

Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised
clinical use.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import NamedTuple


class Entry(NamedTuple):
    module: str  # dotted import path
    role: str  # one line, plain English
    shim_for: str = ""  # set on a tiny file left at an old path: the new module it stands for
    alias: bool = True  # False for a split module: the shim re-exports names (several new modules) instead of aliasing one


REGISTRY: tuple[Entry, ...] = (
    Entry("diacausal", "the new single package (plan section 8.3)"),
    Entry("diacausal.causal_inference", "package: the 3-arm causal engine"),
    Entry("diacausal.guards", "package: safety rules and checkers"),
    Entry("diacausal.registry", "this list, and the ordered pipeline layers"),
    Entry("diacausal.xai", "package: explainable AI (version A baseline, ground truth); never used by the website or the API"),
    Entry("diacausal.xai.baseline", "version A: the XAI-only baseline (gradient boosting + TreeSHAP + LIME), scored against the truth"),
    Entry("diacausal.xai.truth", "the generator's true effect modifiers, derived from params.yaml"),
    Entry("diacausal.tracing", "console tracing: layer(), @traced, AbstainSignal (plan 8.5)"),
    Entry("diacausal.api.routes_v1", "POST /api/v1/ask"),
    Entry("diacausal.orchestrator", "package: the request pipeline"),
    Entry("diacausal.orchestrator.context", "what travels through the pipeline for one request"),
    Entry("diacausal.orchestrator.pipeline", "runs the layers in registry order, each in a trace"),
    Entry("diacausal.orchestrator.layers", "the layers that are built (rules, causal, retrieval, explanation, output guards, formatter)"),
    Entry("diacausal.orchestrator.stubs", "pass-through stubs for what is not built yet"),
    Entry("diacausal.guards.input_guards", "the seven input guards of plan 8.6 (scope, identifier, red flag, injection, range, length and language, dose request)"),
    Entry("diacausal.output", "package: assembling what the screen shows"),
    Entry("diacausal.output.formatter", "assemble AnswerCardV1 from the layers' results"),
    Entry("diacausal.output.parser", "what is kept of a draft that passed the output guards (P23)"),
    Entry("diacausal.api", "package"),
    Entry("diacausal.api.contract_app", "the v1 contract app"),
    Entry("diacausal.api.schemas", "v1 models (package)"),
    Entry("diacausal.api.schemas.base", "shared base model"),
    Entry("diacausal.api.schemas.card", "AnswerCardV1"),
    Entry("diacausal.api.schemas.causal", "CausalOutputV1, DriverV1"),
    Entry("diacausal.api.schemas.evidence", "EvidenceChunkV1, EvidenceBundleV1"),
    Entry("diacausal.api.schemas.guards", "GuardResultV1, EligibleOptionsV1"),
    Entry("diacausal.api.schemas.llm", "LLMRequestV1, AnswerDraftV1, GuardedDraftV1"),
    Entry("diacausal.api.schemas.patient", "PatientV1"),
    Entry("diacausal.api.schemas.service", "AskRequestV1 and service models"),
    Entry("diacausal.config", "params.yaml loader (data/params.yaml)"),
    Entry("diacausal.causal_inference.dag", "causal graph and adjustment sets"),
    Entry("diacausal.guards.rules_loader", "rules loader for data/rules.csv (runs before any estimate)"),
    Entry("diacausal.causal_inference.schemas", "engine models (PatientIn, CausalOutput, ...)"),
    Entry("diacausal.causal_inference.cohort", "synthetic India-calibrated cohort"),
    Entry("diacausal.causal_inference.propensity", "cross-fitted propensity model"),
    Entry("diacausal.causal_inference.estimators", "AIPW and DR-learner estimators"),
    Entry("diacausal.causal_inference.fitting", "shared model fitting"),
    Entry("diacausal.causal_inference.refute", "refutation tests and E-values"),
    Entry("diacausal.causal_inference.metrics", "benchmark metrics"),
    Entry("diacausal.causal_inference.dr_learner", "DR-learner: per-patient estimates with 95% intervals (split from estimators)"),
    Entry("diacausal.causal_inference.recommend", "Engine: the three-option recommendation"),
    Entry("diacausal.causal_inference.figures", "benchmark figures"),
    Entry("diacausal.causal_inference.benchmark", "benchmark runner (python -m entry point)"),
    Entry("diacausal.causal_inference.export_web", "writes web/model.json"),
    Entry("diacausal.api.main", "the engine's own FastAPI app (POST /api/v1/recommend)"),
    Entry("diacausal.rag", "package: RAG (moved from diacausal_rag)"),
    Entry("diacausal.rag.evaluate", "RAG evaluation (python -m entry point)"),
    Entry("diacausal.rag.export_web", "writes web/evidence.json"),
    Entry("diacausal.rag.sources_table", "writes docs/SOURCES.md"),
    Entry("diacausal.rag.ingest", "package: reading documents into chunks"),
    Entry("diacausal.rag.ingest.pdf_text", "PDF text extraction (python -m entry point)"),
    Entry("diacausal.rag.ingest.chunking", "section- and sentence-aware chunks (split from ingest)"),
    Entry("diacausal.rag.ingest.licence_gate", "the licence gate and ingest() (split from ingest)"),
    Entry("diacausal.rag.index", "package: the two search indexes"),
    Entry("diacausal.rag.index.bm25", "BM25 keyword search and tokens (split from retrieve)"),
    Entry("diacausal.rag.index.dense", "optional dense (sentence-embedding) index: build, save, check, score; off by default"),
    Entry("diacausal.rag.index.tfidf", "TF-IDF vector search (split from retrieve)"),
    Entry("diacausal.rag.retrieve", "package: hybrid retrieval"),
    Entry("diacausal.rag.retrieve.hybrid", "BM25 + TF-IDF + RRF and evidence JSON (split from retrieve)"),
    Entry("diacausal.rag.retrieve.ranking", "source-aware ranking: authority tier, India relevance, section and condition match, latest version only (off by default)"),
    Entry("diacausal.rag.retrieve.query_processing", "normalise, expand abbreviations and brands, split into at most 3 sub-queries (keyword search only)"),
    Entry("diacausal.rag.retrieve.rerank", "the reranker slot (split from retrieve)"),
    Entry("diacausal.llm", "package: the cited explanation"),
    Entry("diacausal.llm.explain", "the switch between providers: explain(), render(), command line"),
    Entry("diacausal.llm.prompt_builder", "the prompt sent to the local model"),
    Entry("diacausal.llm.providers", "package: the two answer writers"),
    Entry("diacausal.llm.providers.template", "offline answer that quotes passage sentences"),
    Entry("diacausal.llm.answer", "the model's reply -> the seven output checks -> the explanation, or the template (P23)"),
    Entry("diacausal.llm.golden", "the 20 golden questions and the pipeline inputs each one needs"),
    Entry("diacausal.llm.providers.ollama", "local model through Ollama"),
    Entry("diacausal.guards.output_guards", "the citation checker (sentences, check_answer) and the seven output checks of plan 8.10"),
    Entry("diacausal_engine", "the 3-arm causal engine (package)"),
    Entry("diacausal_engine.api", "old path of diacausal.api.main", shim_for="diacausal.api.main"),
    Entry("diacausal_engine.benchmark", "old path of diacausal.causal_inference.benchmark", shim_for="diacausal.causal_inference.benchmark"),
    Entry("diacausal_engine.cohort", "old path of diacausal.causal_inference.cohort", shim_for="diacausal.causal_inference.cohort"),
    Entry("diacausal_engine.config", "old path of diacausal.config", shim_for="diacausal.config"),
    Entry("diacausal_engine.dag", "old path of diacausal.causal_inference.dag", shim_for="diacausal.causal_inference.dag"),
    Entry("diacausal_engine.estimators", "old path of diacausal.causal_inference.estimators", shim_for="diacausal.causal_inference.estimators", alias=False),
    Entry("diacausal_engine.export_web", "old path of diacausal.causal_inference.export_web", shim_for="diacausal.causal_inference.export_web"),
    Entry("diacausal_engine.figures", "old path of diacausal.causal_inference.figures", shim_for="diacausal.causal_inference.figures"),
    Entry("diacausal_engine.fitting", "old path of diacausal.causal_inference.fitting", shim_for="diacausal.causal_inference.fitting"),
    Entry("diacausal_engine.guardrails", "old path of diacausal.guards.rules_loader", shim_for="diacausal.guards.rules_loader"),
    Entry("diacausal_engine.metrics", "old path of diacausal.causal_inference.metrics", shim_for="diacausal.causal_inference.metrics"),
    Entry("diacausal_engine.propensity", "old path of diacausal.causal_inference.propensity", shim_for="diacausal.causal_inference.propensity"),
    Entry("diacausal_engine.recommend", "old path of diacausal.causal_inference.recommend", shim_for="diacausal.causal_inference.recommend"),
    Entry("diacausal_engine.refute", "old path of diacausal.causal_inference.refute", shim_for="diacausal.causal_inference.refute"),
    Entry("diacausal_engine.schemas", "old path of diacausal.causal_inference.schemas", shim_for="diacausal.causal_inference.schemas"),
    Entry("diacausal_rag", "licence-gated RAG (package)"),
    Entry("diacausal_rag.evaluate", "old path of diacausal.rag.evaluate", shim_for="diacausal.rag.evaluate"),
    Entry("diacausal_rag.explain", "old path of diacausal.llm.explain (split into five modules)", shim_for="diacausal.llm.explain", alias=False),
    Entry("diacausal_rag.export_web", "old path of diacausal.rag.export_web", shim_for="diacausal.rag.export_web"),
    Entry("diacausal_rag.ingest", "old path of diacausal.rag.ingest.chunking", shim_for="diacausal.rag.ingest.chunking", alias=False),
    Entry("diacausal_rag.pdf_text", "old path of diacausal.rag.ingest.pdf_text", shim_for="diacausal.rag.ingest.pdf_text"),
    Entry("diacausal_rag.retrieve", "old path of diacausal.rag.retrieve.hybrid", shim_for="diacausal.rag.retrieve.hybrid", alias=False),
    Entry("diacausal_rag.sources_table", "old path of diacausal.rag.sources_table", shim_for="diacausal.rag.sources_table"),
)


def modules() -> list[str]:
    return [e.module for e in REGISTRY]


# ── the request pipeline (docs/PLAN_2026-10.md, section 8.3) ─────────────────────────────────────────────────────
# diacausal/orchestrator/pipeline.py reaches every layer ONLY through layer_function() below, in this order.
# `stub=True` marks a pass-through that is not built yet; `replaced_by` names the prompt that builds the real one
# (then change the one line here: nothing else needs to move). tests/orchestrator checks this list.


class Layer(NamedTuple):
    name: str  # as it appears in the trace: "[rid] passed input guards layer (3 ms)"
    function: str  # "module:attribute"
    stub: bool = False
    replaced_by: str = ""


_O = "diacausal.orchestrator"
LAYERS: tuple[Layer, ...] = (
    Layer("input guards", f"{_O}.layers:input_guards_layer"),
    Layer("rules", f"{_O}.layers:rules_layer"),
    Layer("causal engine", f"{_O}.layers:causal_layer"),
    Layer("retrieval", f"{_O}.layers:retrieval_layer"),
    Layer("explanation", f"{_O}.layers:explanation_layer"),
    Layer("output guards", f"{_O}.layers:output_guards_layer"),
    Layer("formatter", f"{_O}.layers:formatter_layer"),
)

# Parts inside a layer that are still stubs (each is called by its layer through part_function()).
PARTS: tuple[Layer, ...] = (
    Layer("query processing", f"{_O}.layers:query_processing_part"),
    Layer("shap drivers", f"{_O}.stubs:shap_drivers", stub=True, replaced_by="P25"),
    Layer("evidence levels", f"{_O}.stubs:evidence_levels", stub=True, replaced_by="P24"),
    Layer("prompt builder", f"{_O}.layers:prompt_builder_part"),
    Layer("full output checks", f"{_O}.layers:full_output_checks_part"),
)


def _resolve(entries: tuple[Layer, ...], name: str) -> Callable:
    for e in entries:
        if e.name == name:
            module, attr = e.function.split(":")
            return getattr(importlib.import_module(module), attr)
    raise KeyError(f"no layer or part called {name!r} in the registry")


def layer_function(name: str) -> Callable:
    """The function that runs one pipeline layer: fn(context) -> None."""
    return _resolve(LAYERS, name)


def part_function(name: str) -> Callable:
    """The function behind a part of a layer (a stub today for the parts in PARTS)."""
    return _resolve(PARTS, name)


def stubs() -> list[Layer]:
    """Every layer and part that is still a pass-through."""
    return [e for e in (*LAYERS, *PARTS) if e.stub]
