"""The registry: every importable module of the DiaCausal Python code, with what it is for.

`tests/test_imports.py` imports every entry and fails if a module exists on disk that is not listed
here, so this file cannot drift. Update it in every restructure step (docs/RESTRUCTURE_PLAN.md):
when a module moves, change its `module`; when a shim is left at the old path, keep both lines
(the old one with `shim_for` naming the new module) until the shim is removed (step 9).

Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised
clinical use.
"""

from __future__ import annotations

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
    Entry("diacausal.registry", "this list"),
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
    Entry("diacausal_rag.evaluate", "RAG evaluation (python -m entry point)"),
    Entry("diacausal_rag.explain", "template/Ollama explanations and the citation checker"),
    Entry("diacausal_rag.export_web", "writes web/evidence.json"),
    Entry("diacausal_rag.ingest", "licence gate and chunking"),
    Entry("diacausal_rag.pdf_text", "PDF text extraction (python -m entry point)"),
    Entry("diacausal_rag.retrieve", "BM25 + TF-IDF + RRF retrieval"),
    Entry("diacausal_rag.sources_table", "writes docs/SOURCES.md"),
)


def modules() -> list[str]:
    return [e.module for e in REGISTRY]
