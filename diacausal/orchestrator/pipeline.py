"""The request pipeline (plan 8.3): one function, `ask`, that runs the layers in the order of `registry.LAYERS`,
each inside a trace (`diacausal.tracing.layer`), and returns the AnswerCardV1.

It reaches layers only through the registry, so replacing a stub with the real layer never touches this file.

Outcomes of a layer: it returns (passed); it raises AbstainSignal (the layer correctly could not answer: logged as
"abstained", the pipeline carries on with what it has, EXCEPT an abstain from "input guards", which stops the request
with RequestBlocked); any other exception is a failure and propagates (logged by class name only).

When the route has started an observability trace (diacausal/observability/recorder.py), each layer is also recorded as a span with
what it produced (diacausal/observability/summaries.py: IDs, codes, counts, never values), and the layers a stopped request never
reached are listed as "not run". Without a trace (the benchmark, the scripts) nothing extra happens.
"""

from __future__ import annotations

import time

from diacausal import registry
from diacausal.api.schemas import AnswerCardV1, AskRequestV1
from diacausal.api.schemas.patient import to_engine_patient
from diacausal.causal_inference.recommend import Engine, get_engine
from diacausal.observability import recorder, summaries
from diacausal.orchestrator.context import Context, RequestBlocked
from diacausal.tracing import AbstainSignal, layer

STOPS_THE_REQUEST = "input guards"


def _component(entry: registry.Layer) -> str:
    return entry.function


def ask(request: AskRequestV1, engine: Engine | None = None, timings: dict[str, float] | None = None) -> AnswerCardV1:
    """`timings`, when given, is filled with each layer's duration in milliseconds (layer name -> ms): the route sends them as a
    Server-Timing header, and scripts/measure_local.py reads them. Names and numbers only."""
    ctx = Context(request=request, engine=engine or get_engine(), patient=to_engine_patient(request.patient))
    reached = 0
    try:
        for entry in registry.LAYERS:
            function = registry.layer_function(entry.name)
            reached += 1
            t0 = time.perf_counter()
            pipeline = summaries.LAYER_PIPELINE.get(entry.name, "request")
            with recorder.span(entry.name, pipeline=pipeline, component=_component(entry), kind="layer") as s:
                try:
                    try:
                        with layer(entry.name, ctx.request_id):
                            function(ctx)
                    finally:
                        if s is not recorder.NULL and entry.name in summaries.LAYERS:  # only while a trace is recorded
                            recorder.describe_into(s, lambda: summaries.LAYERS[entry.name](ctx))
                except AbstainSignal as abstain:
                    ctx.abstained[entry.name] = abstain.code
                    if entry.name == STOPS_THE_REQUEST:
                        detail = abstain.result or {}
                        raise RequestBlocked(abstain.code, detail.get("message", ""), detail.get("problems")) from None
                    if s is not recorder.NULL:
                        s.status, s.code = "abstained", abstain.code  # recorded; the pipeline carries on
                finally:
                    if timings is not None:
                        timings[entry.name] = (time.perf_counter() - t0) * 1000
    except RequestBlocked as blocked:
        _mark_stopped(blocked.code)
        raise
    finally:
        for entry in registry.LAYERS[reached:]:
            recorder.not_run(entry.name, summaries.LAYER_PIPELINE.get(entry.name, "request"), _component(entry))
    assert ctx.card is not None, "the formatter layer did not produce a card"
    return ctx.card


def _mark_stopped(code: str) -> None:
    """The input guards' span ends as "abstained" with the guard's CODE (RequestBlocked replaced the AbstainSignal inside the span)."""
    trace = recorder.current()
    if trace is not None:
        for s in trace.spans:
            if s.kind == "layer" and s.name == STOPS_THE_REQUEST:
                s.status, s.code, s.error_type = "abstained", code, None
