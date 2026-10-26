"""GET /api/v1/observability/...: the recorded traces, for the Observability screen (docs/OBSERVABILITY.md).

    GET /api/v1/observability/summary            counts, durations and recent problems over every stored trace
    GET /api/v1/observability/traces             one page of traces (filters: q, status, pipeline, pipeline_status, since, until,
                                                 problems; sort time|duration; order desc|asc; limit 1-200; offset)
    GET /api/v1/observability/traces/{trace_id}  one trace with all its spans
    GET /api/v1/observability/engine             what the engine was fitted on, and the pipeline as registry.py lists it

Who may read them: only a client on THIS computer (127.0.0.1 or ::1). The clinic server listens on 127.0.0.1 only (a test checks), so
this is the same boundary as the rest of the API; a request that arrives from anywhere else (a proxy, a mis-set --host) gets 403. A
trace holds no patient values, question, prompt, passage or model text (diacausal/observability/summaries.py).

Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.
"""

from __future__ import annotations

import re
from typing import Literal

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from diacausal import INTENDED_USE, registry
from diacausal.observability import recorder, summaries
from diacausal.observability.store import STATUSES

router = APIRouter(prefix="/api/v1/observability", include_in_schema=True, tags=["observability"])
LOCAL = {"127.0.0.1", "::1"}
TRACE_ID = re.compile(r"[0-9a-f]{16}")
SEARCH = re.compile(r"[A-Za-z0-9_-]{1,64}")
NO_STORE = {"Cache-Control": "no-store"}


def _refuse(request: Request) -> JSONResponse | None:
    if not recorder.enabled():
        return JSONResponse(status_code=404, headers=NO_STORE, content={
            "error": "off", "message": "Observability is switched off on this computer (DIACAUSAL_OBSERVABILITY=off).", "intended_use": INTENDED_USE})
    host = request.client.host if request.client else ""
    if host not in LOCAL:
        return JSONResponse(status_code=403, headers=NO_STORE, content={
            "error": "forbidden", "message": "Traces can be read only on the computer that runs the DiaCausal server.", "intended_use": INTENDED_USE})
    if getattr(request.app.state, "trace_store", None) is None:
        return JSONResponse(status_code=503, headers=NO_STORE, content={
            "error": "not_ready", "message": "The trace store is not open yet: the server is still starting.", "intended_use": INTENDED_USE})
    return None


def _reply(content: dict) -> JSONResponse:
    return JSONResponse(content={**content, "intended_use": INTENDED_USE}, headers=NO_STORE)


@router.get("/summary")
def summary(request: Request) -> JSONResponse:
    if (refused := _refuse(request)) is not None:
        return refused
    return _reply({"scope": "every trace stored on this computer", "stored": request.app.state.trace_store.summary(),
                   "running": len(recorder.running()), "recording": True})


@router.get("/traces")
def traces(request: Request,
           q: str | None = Query(None, max_length=64), status: str | None = Query(None),
           pipeline: Literal["ci", "rag", "llm", "output"] | None = None,
           pipeline_status: Literal["completed", "abstained", "failed", "not run"] | None = None,
           since: float | None = Query(None, ge=0), until: float | None = Query(None, ge=0), problems: bool = False,
           sort: Literal["time", "duration"] = "time", order: Literal["desc", "asc"] = "desc",
           limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)) -> JSONResponse:
    if (refused := _refuse(request)) is not None:
        return refused
    if q is not None and not SEARCH.fullmatch(q):
        return JSONResponse(status_code=422, headers=NO_STORE, content={
            "error": "invalid", "message": "Search by a trace ID or request ID: letters, digits, - and _ only.", "intended_use": INTENDED_USE})
    running = [] if status not in (None, "running") or offset else [
        {k: t[k] for k in ("trace_id", "request_id", "source", "workflow", "started_at", "status")} for t in recorder.running()]
    if status == "running":
        return _reply({"total": len(running), "traces": running, "running": running})
    if status is not None and status not in STATUSES:
        return JSONResponse(status_code=422, headers=NO_STORE, content={
            "error": "invalid", "message": f"status must be one of: {', '.join(STATUSES)}", "intended_use": INTENDED_USE})
    total, rows = request.app.state.trace_store.query(q=q, status=status, pipeline=pipeline, pipeline_status=pipeline_status, since=since,
                                                      until=until, problems=problems, sort=sort, order=order, limit=limit, offset=offset)
    return _reply({"total": total, "traces": rows, "running": running, "limit": limit, "offset": offset})


@router.get("/traces/{trace_id}")
def trace(trace_id: str, request: Request) -> JSONResponse:
    if (refused := _refuse(request)) is not None:
        return refused
    if not TRACE_ID.fullmatch(trace_id):
        return JSONResponse(status_code=422, headers=NO_STORE, content={
            "error": "invalid", "message": "A trace ID is 16 lower-case hexadecimal characters.", "intended_use": INTENDED_USE})
    found = request.app.state.trace_store.get(trace_id) or next((t for t in recorder.running() if t["trace_id"] == trace_id), None)
    if found is None:
        return JSONResponse(status_code=404, headers=NO_STORE, content={
            "error": "not_found", "message": "No trace with this ID is stored on this computer (it may have passed the retention limit).",
            "intended_use": INTENDED_USE})
    return _reply({"trace": found})


@router.get("/engine")
def engine(request: Request) -> JSONResponse:
    if (refused := _refuse(request)) is not None:
        return refused
    layers = [{"name": e.name, "component": e.function, "pipeline": summaries.LAYER_PIPELINE.get(e.name), "stub": e.stub}
              for e in registry.LAYERS]
    parts = [{"name": e.name, "component": e.function, "pipeline": summaries.PART_PIPELINE.get(e.name), "stub": e.stub}
             for e in registry.PARTS]
    return _reply({"engine": request.app.state.engine_facts, "layers": layers, "parts": parts,
                   "order": "sequential: each layer runs after the previous one returns (diacausal/orchestrator/pipeline.py); no branch runs in parallel"})
