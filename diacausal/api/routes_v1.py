"""POST /api/v1/ask: patient details and a question in -> AnswerCardV1 out (plan 8.4), through the pipeline.

Any problem inside the pipeline is answered with a plain 500 that carries only the request ID. The exception is logged
by CLASS NAME only: its message could contain what the client sent (a pydantic error repeats the input), and
uvicorn would print it with the traceback.

Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from diacausal import INTENDED_USE
from diacausal.api.schemas import AnswerCardV1, AskRequestV1, ErrorV1
from diacausal.orchestrator.context import RequestBlocked
from diacausal.orchestrator.pipeline import ask as run_pipeline

log = logging.getLogger("diacausal.engine")
router = APIRouter()


@router.post("/api/v1/ask", response_model=AnswerCardV1, operation_id="ask",
             responses={422: {"model": ErrorV1, "description": "Invalid request, or stopped by an input check"},
                        500: {"description": "The request could not be completed (only the request ID is returned)"}})
def ask(body: AskRequestV1, request: Request) -> JSONResponse:
    headers = {"X-Request-Id": body.request_id}
    try:
        card = run_pipeline(body, request.app.state.engine)
    except RequestBlocked as blocked:
        log.warning("[%s] ask: stopped by an input check reason=%s", body.request_id, blocked.code)
        return JSONResponse(status_code=422, headers=headers, content=ErrorV1(
            message=blocked.message or "This request was stopped by an input check.", problems=blocked.problems).model_dump())
    except Exception as exc:  # noqa: BLE001 - answered below; the class name is all that is logged
        log.error("[%s] ask: failed error=%s", body.request_id, type(exc).__name__)
        return JSONResponse(status_code=500, headers=headers, content={
            "error": "internal", "request_id": body.request_id, "intended_use": INTENDED_USE,
            "message": "The request could not be completed and nothing was shown. Try again, or tell the team the request ID."})
    return JSONResponse(content=card.model_dump(mode="json"), headers=headers)
