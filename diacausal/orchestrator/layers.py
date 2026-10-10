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
from diacausal.config import load_rag_config
from diacausal.api.schemas import (CausalOutputV1, EligibleOptionsV1, EvidenceBundleV1, EvidenceChunkV1, RuleHitV1,
                                   ScoresV1)
from diacausal.causal_inference.recommend import DOSE_PATTERN, OutputCheckError, check_output, write_audit
from diacausal.guards.output_guards import _usable
from diacausal.guards import input_guards
from diacausal.llm import prompt_builder
from diacausal.llm.answer import GuardInputs, template_instead
from diacausal.llm.answer import resolve as resolve_answer
from diacausal.llm.explain import DOSE_QUESTION, explain
from diacausal.llm.providers import ollama
from diacausal.orchestrator.context import Context
from diacausal.output.formatter import build_card, evidence_levels
from diacausal.rag.ingest.licence_gate import CORPUS, ingest, load_sources
from diacausal.rag.retrieve import query_processing, ranking
from diacausal.rag.retrieve.hybrid import Retriever
from diacausal.tracing import AbstainSignal, guard_notice


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
    # BM25 gets the expanded sub-queries, the vector search the question; the patient's conditions only matter when ranking.yaml is on
    raw = retriever.search(ctx.request.question, plan, ranking.patient_conditions(ctx.request.patient))
    ctx.retrieval = raw
    sources = load_sources()
    chunks = []
    for p in raw["passages"]:
        c, s = p["citation"], sources.get(p["citation"]["source_id"], {})
        ctx.labels[p["chunk_id"]] = _label({"id": c["source_id"], **s}, c["page"])
        chunks.append(EvidenceChunkV1(
            chunk_id=p["chunk_id"], source=c["title"], version=c["version"], section=c["section"],
            page=int(c["page"]) if str(c["page"]).isdigit() else None, licence=s.get("licence_as_found", "unknown"),
            text=p["text"], scores=ScoresV1(bm25=p["scores"]["bm25"], dense=p["scores"].get("dense"), rrf=p["scores"]["rrf"])))
    ok = raw["status"] == "SUCCESS"
    ctx.evidence = EvidenceBundleV1(status="OK" if ok else "INSUFFICIENT_EVIDENCE", index_version=f"kb@{_corpus_sha()}",
                                    chunks=chunks, reason=None if ok else raw.get("reason"))
    if not ok:
        raise AbstainSignal("NO_EVIDENCE")


def query_processing_part(ctx: Context, question: str):
    """Part of the retrieval layer (P16): the question as a QueryPlan. Nothing about it is logged."""
    return query_processing.process(question)


# ── layer 5: explanation ─────────────────────────────────────────────────────────────────────────────────────────

def json_prompt_for(ctx: Context) -> prompt_builder.BuiltPrompt:
    """The section 8.9 prompt for this request, within the token budget (diacausal/llm/prompt_builder.py). Raises PromptError."""
    return prompt_builder.build_llm_prompt(ctx.request, ctx.eligible, ctx.causal, ctx.drivers, ctx.evidence,
                                           max_claims=int(ollama.load_llm_config()["max_claims"]))


def model_will_answer(ctx: Context, llm_cfg: dict | None = None) -> bool:
    """True when the local model is asked: switched on in BOTH places, evidence to quote, and not a dose question."""
    llm_cfg = llm_cfg or ollama.load_llm_config()
    usable = ctx.retrieval is not None and ctx.retrieval.get("status") == "SUCCESS" and bool(_usable(ctx.retrieval["passages"]))
    return ollama.is_enabled(llm_cfg, ctx.request.mode) and usable and not DOSE_QUESTION.search(ctx.request.question)


def prompt_builder_part(ctx: Context) -> None:
    """Part of the explanation layer (P22): build the model's prompt, only when the model will be asked. A prompt that cannot be
    built safely leaves `ctx.prompt_problem` (a CODE) and the template writes the answer."""
    ctx.prompt = ctx.prompt_problem = ctx.model_reply = ctx.guarded = None
    if not model_will_answer(ctx):
        return
    try:
        ctx.prompt = json_prompt_for(ctx)
    except prompt_builder.PromptError as error:
        ctx.prompt_problem = error.code


def explanation_layer(ctx: Context) -> None:
    """The template writes the answer, unless the local model is switched on in BOTH places (llm.yaml `provider: ollama` and the
    request's `mode: ollama`). Then the model is asked here, but what it returns is NOT used yet: the output guards layer checks it
    (plan 8.10) and uses the template instead of anything that fails."""
    registry.part_function("prompt builder")(ctx)
    question = ctx.request.question
    if ctx.prompt is not None:
        ctx.model_reply = ollama.request_draft(ctx.prompt.text, ollama.load_llm_config())
        return
    if ctx.prompt_problem is not None:
        ctx.explanation = template_instead(question, ctx.retrieval, load_rag_config(), ctx.idf, ctx.prompt_problem)
    else:
        ctx.explanation = explain(question, ctx.retrieval, backend="template", idf=ctx.idf)
    if ctx.explanation["status"] != "SUCCESS":
        raise AbstainSignal("DOSE_REQUEST" if DOSE_QUESTION.search(question) else "NO_SUPPORTED_CLAIM")


# ── layer 6: output guards ───────────────────────────────────────────────────────────────────────────────────────

def full_output_checks_part(ctx: Context) -> None:
    """Part of the output guards layer (P23): the seven checks of plan 8.10 on the model's draft. Anything but a PASS means the template
    answers; the card then says `fallback_used` with the failed check IDs. Nothing to do when the model was not asked."""
    if ctx.model_reply is None:
        return
    inputs = GuardInputs(eligible=ctx.eligible, causal=ctx.causal, drivers=ctx.drivers or {}, number_sources=tuple(ctx.prompt.number_sources))
    ctx.explanation, ctx.guarded = resolve_answer(ctx.request.question, ctx.model_reply, evidence=ctx.retrieval, rag_cfg=load_rag_config(),
                                                  llm_cfg=ollama.load_llm_config(), idf=ctx.idf, inputs=inputs)
    reply = ctx.explanation
    if ctx.guarded is not None:
        guard_notice(ctx.request_id, ctx.guarded.status, reply.get("failed_checks", []), reply.get("fallback"), reply.get("dropped_claims", 0))
    if reply["status"] != "SUCCESS":
        raise AbstainSignal("NO_SUPPORTED_CLAIM")


def output_guards_layer(ctx: Context) -> None:
    """The engine's reply never carries a dose, a bare number or an estimated exclusion; a model's draft passes the seven checks of
    plan 8.10 (or the template is used); and every sentence of the explanation cites a passage that was shown and holds no dose text."""
    check_output(ctx.causal)
    registry.part_function("full output checks")(ctx)
    shown = {n for n, _ in _usable(ctx.retrieval["passages"])} if ctx.retrieval else set()
    for item in (ctx.explanation or {}).get("sentences", []):
        if DOSE_PATTERN.search(item["text"]):
            raise OutputCheckError("an explanation sentence contains dose-like text")
        if not item["cites"] or not set(item["cites"]) <= shown:
            raise OutputCheckError("an explanation sentence cites a passage that was not shown")


# ── layer 7: formatter ───────────────────────────────────────────────────────────────────────────────────────────

def evidence_levels_part(ctx: Context) -> list:
    """Part of the formatter layer (P24): the evidence level of each option the rules left (plan 8.11), now that the retrieval has
    run (its citations count, and an abstained retrieval makes every level Insufficient)."""
    return evidence_levels(ctx.causal, ctx.evidence) if ctx.causal is not None else []


def formatter_layer(ctx: Context) -> None:
    ctx.evidence_levels = registry.part_function("evidence levels")(ctx)
    ctx.card = build_card(request=ctx.request, causal=ctx.causal, eligible=ctx.eligible, evidence=ctx.evidence,
                          reply=ctx.explanation, labels=ctx.labels, drivers=ctx.drivers, levels=ctx.evidence_levels)
