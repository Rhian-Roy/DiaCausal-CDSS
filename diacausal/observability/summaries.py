"""What each pipeline layer and part produced, reduced to what a trace may keep: IDs, CODES, counts, statuses, versions and settings.

Each function reads the pipeline context AFTER its layer ran (also after an abstain or a failure: it then records what was left) and
returns a small dict. Never the patient's values, the question, a passage's text, the prompt or the model's text: the context holds all
of them, so every field below is chosen by name. Per-patient numbers (estimates, intervals, propensities, driver contributions) stay on
the answer card the clinician sees; the trace records which options got one and why the others did not.

Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.
"""

from __future__ import annotations

from typing import Any

# Which pipeline each registry entry belongs to (diacausal/registry.py names; the screen groups and filters by these).
LAYER_PIPELINE = {"input guards": "guards", "rules": "ci", "causal engine": "ci", "retrieval": "rag", "explanation": "llm",
                  "output guards": "output", "formatter": "output"}
PART_PIPELINE = {"query processing": "rag", "shap drivers": "ci", "evidence levels": "output", "prompt builder": "llm",
                 "full output checks": "output"}

# The retriever's fixed abstain sentences (diacausal/rag/retrieve/hybrid.py) as codes; anything else is OTHER.
RETRIEVAL_REASONS = {"the index is empty": "EMPTY_INDEX", "no approved passage matches": "NO_MATCH",
                     "the passages found cover too few": "LOW_COVERAGE"}
# The engine's fixed reasons for not giving an estimate (diacausal/causal_inference/recommend.py), as codes (the text holds numbers).
INSUFFICIENT_REASONS = {"Outside the cohort": "OUTSIDE_COHORT", "Too few similar patients": "LOW_OVERLAP", "Too uncertain": "TOO_UNCERTAIN"}


def _code(text: str | None, table: dict[str, str]) -> str | None:
    if not text:
        return None
    return next((code for start, code in table.items() if text.startswith(start)), "OTHER")


def input_guards(ctx) -> dict[str, Any]:
    g = ctx.guard
    return {
        "status": g.status if g else None,
        "checks": [{"check": c.id, "result": c.result} for c in g.checks] if g else [],
        "fields_received": sorted(ctx.request.patient.model_fields_set),  # which fields arrived, never their values
        "question_chars": len(ctx.request.question),  # a size, never the text
        "mode_requested": ctx.request.mode,
    }


def rules(ctx) -> dict[str, Any]:
    e = ctx.eligible
    if e is None:
        return {}
    return {"rules_version": e.rules_version, "eligible": list(e.eligible),
            "excluded": [{"option": h.option, "rule_id": h.rule_id} for h in e.excluded],
            "cautions": [{"option": h.option, "rule_id": h.rule_id} for h in e.caution]}


def causal_engine(ctx) -> dict[str, Any]:
    c = ctx.causal
    if c is None:
        return {}
    return {
        "applicable": c.applicable,
        "options": [{"option": o.arm, "status": o.status, "rule_ids": [s.rule_id for s in o.safety],
                     "why_no_estimate": _code(o.insufficient_reason, INSUFFICIENT_REASONS),
                     "method": o.confidence.method if o.confidence else None,
                     "secondary_outcomes": o.secondary is not None, "drivers_shown": len(o.drivers)} for o in c.options],
        "comparisons": [f"{x.first}-{x.second}" for x in c.comparisons],
        "assumptions": len(c.assumptions),
        "versions": {"engine": c.versions.engine, "params": c.versions.params, "params_sha": c.versions.params_sha,
                     "rules_sha": c.versions.rules_sha, "cohort": c.versions.cohort},
        "audit_line_written": True,  # write_audit runs before the drivers part in causal_layer; a failure there fails the layer
    }


def retrieval(ctx) -> dict[str, Any]:
    from diacausal.orchestrator.layers import get_retriever
    from diacausal.rag.retrieve.hybrid import WITHHELD

    r = get_retriever()
    raw, cfg = ctx.retrieval or {}, r.cfg  # the settings the retriever that answered was built with
    passages = raw.get("passages", [])
    return {
        "status": raw.get("status"),
        "reason": _code(raw.get("reason"), RETRIEVAL_REASONS),
        "index_version": ctx.evidence.index_version if ctx.evidence else None,
        "index": {"chunks": len(r.chunks), "built": "once per process, at server start (layers.warm_up)",
                  "searches": ["BM25 (expanded sub-queries)", "TF-IDF (the question as asked)"] + (["dense"] if r.dense is not None else []),
                  "fusion": "reciprocal rank fusion", "dense_enabled": r.dense is not None, "source_ranking_enabled": r.ranking is not None,
                  "reranker": "identity (slot only)"},
        "settings": {k: cfg.get(k) for k in ("top_k", "rrf_k", "bm25_k1", "bm25_b", "min_bm25_score", "min_query_coverage")},
        "passages": [{"rank": i, "chunk_id": p["chunk_id"], "source_id": p["citation"]["source_id"],
                      "licence_bucket": p["citation"].get("licence_bucket"), "withheld_dose_text": p["text"] == WITHHELD,
                      "scores": {k: v for k, v in p.get("scores", {}).items() if k in ("bm25", "vector", "rrf", "dense")}}
                     for i, p in enumerate(passages, start=1)],
    }


def _llm_config() -> dict:
    """llm.yaml as the explanation layer reads it, re-read only when the file or the DIACAUSAL_LLM_PROVIDER override changes."""
    import os

    from diacausal.llm.providers import ollama

    key = (ollama.CONFIG_PATH.stat().st_mtime_ns, os.environ.get(ollama.PROVIDER_ENV, ""))
    if _LLM_CACHE.get("key") != key:
        _LLM_CACHE.update(key=key, cfg=ollama.load_llm_config())
    return _LLM_CACHE["cfg"]


_LLM_CACHE: dict[str, Any] = {}


def explanation(ctx) -> dict[str, Any]:
    from diacausal.llm.providers import ollama

    cfg = _llm_config()
    out: dict[str, Any] = {"writer": "local model" if ctx.prompt is not None else "template", "model_asked": ctx.prompt is not None,
                           "provider_setting": cfg.get("provider"), "mode_requested": ctx.request.mode,
                           "prompt_problem": ctx.prompt_problem}
    if ctx.prompt is not None:
        p = ctx.prompt
        out["prompt"] = {"template": "prompt.v2.txt", "token_estimate": p.tokens, "budget": p.budget, "passages_shown": list(p.shown),
                         "passages_shortened": list(p.shortened), "passages_left_out": list(p.left_out),
                         "number_sources": len(p.number_sources)}
        out["model"] = {"key": cfg.get("model"), "tag": ollama.model_tag(cfg), "temperature": cfg.get("temperature"),
                        "num_ctx": cfg.get("num_ctx"), "timeout_seconds": cfg.get("timeout_seconds")}
    reply = ctx.model_reply
    if reply is not None:
        out["model_reply"] = {"received": reply.text is not None, "code": reply.code, "seconds": round(reply.seconds, 1),
                              "prompt_tokens": reply.prompt_tokens, "eval_tokens": reply.eval_tokens}
    if ctx.explanation is not None:
        out["answer"] = _answer(ctx.explanation)
    return out


def _answer(reply: dict) -> dict[str, Any]:
    sentences = reply.get("sentences", [])
    return {"status": reply.get("status"), "sentences": len(sentences), "cited_passages": sorted({n for s in sentences for n in s.get("cites", [])}),
            "fallback": reply.get("fallback"), "failed_checks": list(reply.get("failed_checks", [])),
            "dropped_claims": reply.get("dropped_claims", 0)}


def output_guards(ctx) -> dict[str, Any]:
    sentences = (ctx.explanation or {}).get("sentences", [])
    out: dict[str, Any] = {"checks_run": ["engine output check (no dose, no bare number, no estimated exclusion)",
                                          "no dose text in a sentence", "every sentence cites a passage that was shown"],
                           "sentences_checked": len(sentences)}
    if ctx.guarded is not None:
        out["model_draft"] = {"status": ctx.guarded.status, **_answer(ctx.explanation or {})}
    return out


def formatter(ctx) -> dict[str, Any]:
    card = ctx.card
    if card is None:
        return {}
    return {"mode": card.mode, "claims": len(card.claims), "effect_rows": len(card.effects),
            "evidence_levels": [{"option": lv.option, "level": lv.level} for lv in card.evidence_levels],
            "excluded": len(card.excluded), "cautions": len(card.cautions), "abstain_notices": len(card.abstain),
            "drivers": {k: len(v) for k, v in card.drivers.items()}, "fallback_used": card.fallback_used,
            "failed_checks": list(card.failed_checks), "fallback_reason": card.fallback_reason, "dropped_claims": card.dropped_claims}


LAYERS = {"input guards": input_guards, "rules": rules, "causal engine": causal_engine, "retrieval": retrieval,
          "explanation": explanation, "output guards": output_guards, "formatter": formatter}


# ── parts: (args, result) -> dict ────────────────────────────────────────────────────────────────────────────────

def _query_processing(args, plan) -> dict[str, Any]:
    return {"sub_queries": len(plan.sub_queries), "terms_added": len(plan.added), "driver_queries": len(plan.driver_queries),
            "tables": ["knowledge_sources/query_synonyms.csv", "knowledge_sources/brand_generic.csv (VERIFIED rows only)"],
            "note": "the expanded sub-queries feed BM25 only; TF-IDF gets the question as asked"}


def _shap_drivers(args, drivers) -> dict[str, Any]:
    ctx = args[0]
    return {"method": "exact SHAP of the DR-learner's linear final stage, HC3 95% interval per contribution",
            "comparator": "DPP4i", "max_drivers": int(ctx.engine.params.get("xai.max_drivers")),  # the engine's own params, already loaded
            "clear_drivers": {option: len(rows) for option, rows in (drivers or {}).items()}}


def _evidence_levels(args, levels) -> dict[str, Any]:
    return {"rule": "docs/PLAN_2026-10.md 8.11 (data/params.yaml evidence_level)", "levels": [{"option": lv.option, "level": lv.level} for lv in levels or []]}


def _prompt_builder(args, _) -> dict[str, Any]:
    ctx = args[0]
    return {"built": ctx.prompt is not None, "prompt_problem": ctx.prompt_problem,
            "why_not_built": None if ctx.prompt is not None or ctx.prompt_problem else "MODEL_NOT_ASKED"}


def _full_output_checks(args, _) -> dict[str, Any]:
    ctx = args[0]
    if ctx.guarded is None:
        return {"ran": False, "why": "MODEL_NOT_ASKED"}
    return {"ran": True, "status": ctx.guarded.status, **_answer(ctx.explanation or {})}


PARTS = {"query processing": _query_processing, "shap drivers": _shap_drivers, "evidence levels": _evidence_levels,
         "prompt builder": _prompt_builder, "full output checks": _full_output_checks}
