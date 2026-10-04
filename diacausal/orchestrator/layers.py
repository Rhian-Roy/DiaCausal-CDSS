"""The layers that are built. Each is `fn(context) -> None`: it reads what earlier layers left in the context and adds
its own result. A layer that cannot go on raises `AbstainSignal(CODE)` AFTER storing what it still has, so the pipeline
logs "abstained ... reason=CODE" and carries on; any other exception is a failure.

Never log here (the trace does it, by layer, from the pipeline) and never put patient values or text in an exception
message: only the class name reaches the log, but uvicorn would print a message.
"""

from __future__ import annotations

import hashlib
import re
from functools import lru_cache

from diacausal import registry
from diacausal.api.schemas import (CausalOutputV1, EligibleOptionsV1, EvidenceBundleV1, EvidenceChunkV1, RuleHitV1,
                                   ScoresV1)
from diacausal.causal_inference.recommend import DOSE_PATTERN, OutputCheckError, check_output, write_audit
from diacausal.guards.output_guards import _usable
from diacausal.guards import input_guards
from diacausal.llm.explain import DOSE_QUESTION, explain
from diacausal.orchestrator.context import Context
from diacausal.output.formatter import build_card
from diacausal.rag.ingest.licence_gate import CORPUS, ingest, load_sources
from diacausal.rag.retrieve import query_processing
from diacausal.rag.retrieve.hybrid import Retriever
from diacausal.tracing import AbstainSignal


class RuleOrderViolation(RuntimeError):
    """The causal engine returned a number for an option the rules had already removed. Never allowed (invariant 2)."""


@lru_cache(maxsize=1)
def get_retriever() -> Retriever:
    """Built once per process from the licence-cleared corpus (a fraction of a second)."""
    return Retriever(ingest())


def warm_up() -> None:
    """Build the search index at startup so the first request is not slower than the rest."""
    get_retriever()


def _corpus_sha() -> str:
    """The same fingerprint web/evidence.json records (file names and bytes of the corpus)."""
    h = hashlib.sha256()
    for p in sorted(p for p in CORPUS.iterdir() if p.suffix in (".txt", ".csv")):
        h.update(p.name.encode() + b"\0" + p.read_bytes())
    return h.hexdigest()[:10]


# ── layer 1: input guards ────────────────────────────────────────────────────────────────────────────────────────

def input_guards_layer(ctx: Context) -> None:
    """The seven deterministic input checks of plan 8.6. All run; if any blocks, the request stops here with the
    plain-language reason (the one that matters most first: an emergency before everything else)."""
    results = input_guards.evaluate(ctx.request)
    ctx.guard = input_guards.combine(results)
    if ctx.guard.status == "BLOCK":
        by_id = {r.checks[0].id: r for r in results}
        order = [cid for cid in input_guards.SHOW_FIRST if by_id[cid].status == "BLOCK"]
        problems = [{"check": cid, "code": input_guards.CODES[cid], "message": by_id[cid].blocked_reason} for cid in order]
        raise AbstainSignal(input_guards.CODES[order[0]], result={"message": ctx.guard.blocked_reason, "problems": problems})


# ── layer 2: rules ───────────────────────────────────────────────────────────────────────────────────────────────

def rules_layer(ctx: Context) -> None:
    """data/rules.csv runs BEFORE any estimate and removes options."""
    verdicts = ctx.engine.rule_verdicts(ctx.patient)

    def hits(arm: str, rules) -> list[RuleHitV1]:
        return [RuleHitV1(option=arm, rule_id=r.rule_id, source=f"{r.source}, {r.section}") for r in rules]

    excluded = [h for arm, v in verdicts.items() for h in hits(arm, v.exclusions)]
    caution = [h for arm, v in verdicts.items() for h in hits(arm, v.cautions)]
    ctx.eligible = EligibleOptionsV1(
        rules_version=f"rules.csv@{ctx.engine.rules.version}", excluded=excluded, caution=caution,
        eligible=[arm for arm, v in verdicts.items() if not v.excluded])
    if not ctx.eligible.eligible:
        raise AbstainSignal("ALL_OPTIONS_EXCLUDED")


# ── layer 3: causal engine ───────────────────────────────────────────────────────────────────────────────────────

def causal_layer(ctx: Context) -> None:
    """Estimates, with 95% intervals, for the options the rules left (the engine re-applies the same rules itself;
    this layer verifies that a removed option never comes back)."""
    result = ctx.engine.recommend(ctx.patient, audit=False)
    result = result.model_copy(update={"request_id": ctx.request_id})  # one ID for the trace, the audit line and the card
    removed = {h.option for h in ctx.eligible.excluded}
    for option in result.options:
        if option.arm in removed and option.status != "excluded":
            raise RuleOrderViolation("an option removed by the rules was estimated")
    write_audit(result, ctx.patient)  # IDs, versions, statuses and rule IDs only; no patient values
    ctx.causal = CausalOutputV1.model_validate({
        **result.model_dump(), "options": [{**o.model_dump(), "drivers": []} for o in result.options]})
    ctx.drivers = registry.part_function("shap drivers")(ctx)
    ctx.evidence_levels = registry.part_function("evidence levels")(ctx)
    if result.applicable == "NOT_APPLICABLE":
        raise AbstainSignal("NOT_APPLICABLE")


# ── layer 4: retrieval ───────────────────────────────────────────────────────────────────────────────────────────

def _label(source: dict, page: str) -> str:
    year = re.search(r"\b(?:19|20)\d{2}\b", source.get("version", ""))
    name = f"{source.get('issuer', '').strip() or source.get('id', '')} {year.group(0) if year else ''}".strip()
    return f"{name}, p.{page}" if page not in ("", "?") else name


def retrieval_layer(ctx: Context) -> None:
    plan = registry.part_function("query processing")(ctx, ctx.request.question)
    retriever = get_retriever()
    ctx.idf = retriever.bm25.idf if retriever.chunks else None
    raw = retriever.search(ctx.request.question, plan)  # BM25 gets the expanded sub-queries, the vector search the question
    ctx.retrieval = raw
    sources = load_sources()
    chunks = []
    for p in raw["passages"]:
        c, s = p["citation"], sources.get(p["citation"]["source_id"], {})
        ctx.labels[p["chunk_id"]] = _label({"id": c["source_id"], **s}, c["page"])
        chunks.append(EvidenceChunkV1(
            chunk_id=p["chunk_id"], source=c["title"], version=c["version"], section=c["section"],
            page=int(c["page"]) if str(c["page"]).isdigit() else None, licence=s.get("licence_as_found", "unknown"),
            text=p["text"], scores=ScoresV1(bm25=p["scores"]["bm25"], dense=None, rrf=p["scores"]["rrf"])))
    ok = raw["status"] == "SUCCESS"
    ctx.evidence = EvidenceBundleV1(status="OK" if ok else "INSUFFICIENT_EVIDENCE", index_version=f"kb@{_corpus_sha()}",
                                    chunks=chunks, reason=None if ok else raw.get("reason"))
    if not ok:
        raise AbstainSignal("NO_EVIDENCE")


def query_processing_part(ctx: Context, question: str):
    """Part of the retrieval layer (P16): the question as a QueryPlan. Nothing about it is logged."""
    return query_processing.process(question)


# ── layer 5: explanation ─────────────────────────────────────────────────────────────────────────────────────────

def explanation_layer(ctx: Context) -> None:
    """Template wording today (or the local model, which falls back to the template on any problem)."""
    registry.part_function("prompt builder")(ctx)
    question = ctx.request.question
    ctx.explanation = explain(question, ctx.retrieval, backend=ctx.request.mode, idf=ctx.idf)
    if ctx.explanation["status"] != "SUCCESS":
        raise AbstainSignal("DOSE_REQUEST" if DOSE_QUESTION.search(question) else "NO_SUPPORTED_CLAIM")


# ── layer 6: output guards ───────────────────────────────────────────────────────────────────────────────────────

def output_guards_layer(ctx: Context) -> None:
    """Checks that already exist: the engine's reply never carries a dose, a bare number or an estimated exclusion;
    every sentence of the explanation cites a passage that was shown and holds no dose text. The remaining checks of
    plan 8.10 are the stub `full output checks` (P23)."""
    check_output(ctx.causal)
    shown = {n for n, _ in _usable(ctx.retrieval["passages"])} if ctx.retrieval else set()
    for item in (ctx.explanation or {}).get("sentences", []):
        if DOSE_PATTERN.search(item["text"]):
            raise OutputCheckError("an explanation sentence contains dose-like text")
        if not item["cites"] or not set(item["cites"]) <= shown:
            raise OutputCheckError("an explanation sentence cites a passage that was not shown")
    registry.part_function("full output checks")(ctx)


# ── layer 7: formatter ───────────────────────────────────────────────────────────────────────────────────────────

def formatter_layer(ctx: Context) -> None:
    ctx.card = build_card(request=ctx.request, causal=ctx.causal, eligible=ctx.eligible, evidence=ctx.evidence,
                          reply=ctx.explanation, labels=ctx.labels, drivers=ctx.drivers, levels=ctx.evidence_levels)
