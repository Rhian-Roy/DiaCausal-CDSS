"""The request pipeline (plan 8.3): one function, `ask`, that runs the layers in the order of `registry.LAYERS`,
each inside a trace (`diacausal.tracing.layer`), and returns the AnswerCardV1.

It reaches layers only through the registry, so replacing a stub with the real layer never touches this file.

Outcomes of a layer: it returns (passed); it raises AbstainSignal (the layer correctly could not answer: logged as
"abstained", the pipeline carries on with what it has, EXCEPT an abstain from "input guards", which stops the request
with RequestBlocked); any other exception is a failure and propagates (logged by class name only).
"""

from __future__ import annotations

from diacausal import registry
from diacausal.api.schemas import AnswerCardV1, AskRequestV1
from diacausal.api.schemas.patient import to_engine_patient
from diacausal.causal_inference.recommend import Engine, get_engine
from diacausal.orchestrator.context import Context, RequestBlocked
from diacausal.tracing import AbstainSignal, layer

STOPS_THE_REQUEST = "input guards"


def ask(request: AskRequestV1, engine: Engine | None = None) -> AnswerCardV1:
    ctx = Context(request=request, engine=engine or get_engine(), patient=to_engine_patient(request.patient))
    for entry in registry.LAYERS:
        function = registry.layer_function(entry.name)
        try:
            with layer(entry.name, ctx.request_id):
                function(ctx)
        except AbstainSignal as abstain:
            ctx.abstained[entry.name] = abstain.code
            if entry.name == STOPS_THE_REQUEST:
                detail = abstain.result or {}
                raise RequestBlocked(abstain.code, detail.get("message", ""), detail.get("problems")) from None
    assert ctx.card is not None, "the formatter layer did not produce a card"
    return ctx.card
