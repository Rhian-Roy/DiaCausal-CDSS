"""Stage 5 — llm_explanation (runs today).

Writes the answer the clinician reads. A language model explains; it never decides:

- The option summary is built from the structured results (guardrails + causal engine),
  word for word, so no number can be invented.
- The evidence explanation comes from diacausal_rag.explain. By default it quotes the
  passage sentences that best answer the question, each with its passage number (offline,
  nothing leaves this computer). With DIACAUSAL_EXPLAIN_BACKEND=gemini or ollama a model
  may rewrite them, but every sentence must pass the citation checker (cite a passage that
  was shown, mostly use its words, contain no dose) or the quoted sentences are shown instead.
- A dose question gets no explanation at all.
Sets ctx.reply_parts. Never logs the question or the answer.
"""

from __future__ import annotations

import os

from app import engines
from app.pipeline.context import PipelineContext, passed
from app.schemas import EvidencePart, Passage, Sentence, StageName, StageResult, TextPart
from app.tracing import log

NAME = StageName.LLM_EXPLANATION


def _fmt(r) -> str:
    return f"{r.value:+.2f} (95% range {r.ci_low:+.2f} to {r.ci_high:+.2f})"


def option_summary(ctx: PipelineContext) -> list[str]:
    part = ctx.estimates_part
    if part is None:
        return []
    lines = ["Estimated change in HbA1c at 6 months for this patient (percentage points; negative = better):"]
    for e in part.estimates:
        if e.status == "estimate":
            extra = []
            if e.weight_change_kg:
                extra.append(f"weight {e.weight_change_kg.value:+.1f} kg")
            if e.hypo_risk_pct:
                extra.append(f"low-sugar risk {e.hypo_risk_pct.value:.1f}%")
            lines.append(f"• {e.name}: {_fmt(e.hba1c_change)}" + (f"; {', '.join(extra)}" if extra else "") + ".")
        elif e.status == "excluded":
            lines.append(f"• {e.name}: excluded, no estimate. {e.reason}")
        else:
            lines.append(f"• {e.name}: insufficient evidence, no estimate. {e.reason or ''}".rstrip())
    for c in part.comparisons:
        overlap = c.difference.ci_low <= 0 <= c.difference.ci_high
        lines.append(f"{c.first} minus {c.second}: {_fmt(c.difference)}"
                     + (": the range includes 0, so neither is clearly better." if overlap else "."))
    lines.append(part.data_note + " " + part.decision)
    return lines


def _evidence_part(ctx: PipelineContext) -> EvidencePart | None:
    if ctx.evidence is None:
        return None
    from diacausal_rag.explain import explain

    question = ctx.text.strip()
    backend = os.environ.get("DIACAUSAL_EXPLAIN_BACKEND", "template")
    if backend not in ("template", "gemini", "ollama"):
        backend = "template"
    retriever = engines.retriever()
    reply = explain(question, ctx.evidence, backend=backend, idf=retriever.bm25.idf)
    dose = engines.dose_pattern()
    passages = []
    for n, p in enumerate(ctx.evidence.get("passages", []), start=1):
        c = p["citation"]
        text = p["text"] if not dose.search(p["text"]) else "[Passage withheld: it contains dosing text.]"
        passages.append(Passage(n=n, source_id=c["source_id"], title=c["title"], section=str(c.get("section") or ""),
                                page=None if c.get("page") in (None, "") else str(c["page"]), text=text))
    answered = reply["status"] == "SUCCESS"
    return EvidencePart(
        type="evidence",
        status="answered" if answered else "insufficient_evidence",
        sentences=[Sentence(text=s["text"], cites=s["cites"]) for s in reply["sentences"]] if answered else [],
        passages=passages if answered else [],
        backend=reply["backend"],
        note=reply.get("note") or (ctx.evidence.get("reason", "") if not answered else ""),
    )


def run(ctx: PipelineContext) -> StageResult:
    lines = option_summary(ctx)
    ctx.evidence_part = _evidence_part(ctx)
    ev = ctx.evidence_part
    if ev is not None:
        if ev.status == "answered":
            lines.append("From the approved sources (quoted, with passage numbers):" if ev.backend == "template"
                         else "From the approved sources (citations checked):")
            lines += [f"“{s.text}” " + "".join(f"[{n}]" for n in s.cites) if ev.backend == "template"
                      else s.text + " " + "".join(f"[{n}]" for n in s.cites) for s in ev.sentences]
        else:
            lines.append("Insufficient evidence: the approved sources do not answer this question"
                         + (f" ({ev.note})." if ev.note else "."))
    if not lines:
        lines = ["Add the patient's details in the panel to get estimates, or ask a question the approved "
                 "sources cover (WHO 2018 guideline, US FDA drug safety communications)."]
    parts = [p for p in (ctx.estimates_part, ev) if p is not None]
    ctx.reply_parts = [*parts, TextPart(type="text", text="\n\n".join(lines))]
    log.info("llm_explanation: %s, %d evidence sentences", ev.backend if ev else "no evidence",
             len(ev.sentences) if ev else 0)
    return passed(NAME, f"Answer written ({ev.backend if ev else 'summary only'}); every sentence cites its source.")
