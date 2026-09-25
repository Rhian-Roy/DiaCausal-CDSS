"""Step (i): the causal engine as a web API.

    uvicorn diacausal_engine.api:app --port 8001      # docs at http://localhost:8001/docs

POST /api/v1/recommend   patient details in -> structured Causal Output out
GET  /api/v1/health      is the engine up?

Every response — including errors — carries the intended-use statement:
Research prototype for clinician evaluation; not a marketed medical device;
not for unsupervised clinical use.

Logs carry request IDs, option statuses and rule IDs only — never patient values.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from diacausal_engine import INTENDED_USE, __version__
from diacausal_engine.recommend import Engine, get_engine
from diacausal_engine.schemas import CausalOutput, ErrorOut, HealthOut, RecommendRequest

log = logging.getLogger("diacausal.engine")
if not log.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)


def _plain(error: dict) -> dict:
    """A validation problem in plain English, without echoing what the client sent."""
    field = ".".join(str(p) for p in error.get("loc", ()) if p != "body") or "body"
    kind = error.get("type", "")
    ctx = error.get("ctx") or {}
    if kind == "extra_forbidden":
        message = "this field is not part of the request; remove it"
    elif kind == "missing":
        message = "this field is required"
    elif kind in ("greater_than_equal", "less_than_equal"):
        message = f"out of the plausible range (allowed {ctx.get('ge', ctx.get('le'))} "
        message += "or more)" if kind == "greater_than_equal" else "or less)"
    elif kind == "literal_error":
        message = f"must be one of: {ctx.get('expected', '')}"
    else:
        message = "has the wrong type or format"
    return {"field": field, "message": message}


def create_app(engine: Engine | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.engine = engine or get_engine()  # fit once at startup, not on the first request
        log.info("[-] engine %s ready", __version__)
        yield

    app = FastAPI(
        title="DiaCausal causal engine",
        version=__version__,
        description=(
            f"**{INTENDED_USE}**\n\nFor one adult with type 2 diabetes already on metformin: the expected "
            "6-month HbA1c change under an SGLT2 inhibitor, a DPP-4 inhibitor or a sulfonylurea, each with a "
            "95% interval — after cited safety rules (data/rules.csv) have run. Synthetic data only. "
            "The clinician decides."
        ),
        lifespan=lifespan,
    )

    @app.exception_handler(RequestValidationError)
    async def invalid(request: Request, exc: RequestValidationError):
        problems = [_plain(e) for e in exc.errors()]
        log.warning("[-] recommend: rejected (%d problem(s))", len(problems))
        body = ErrorOut(message="The request was not accepted: " + "; ".join(
            f"{p['field']}: {p['message']}" for p in problems), problems=problems)
        return JSONResponse(status_code=422, content=body.model_dump())

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        return JSONResponse(status_code=exc.status_code,
                            content={"error": "http_error", "message": str(exc.detail), "intended_use": INTENDED_USE})

    @app.get("/api/v1/health", response_model=HealthOut)
    def health() -> HealthOut:
        return HealthOut(engine=__version__)

    @app.post("/api/v1/recommend", response_model=CausalOutput,
              responses={422: {"model": ErrorOut, "description": "Invalid request (plain-English message)"}})
    def recommend(body: RecommendRequest, request: Request) -> JSONResponse:
        result = request.app.state.engine.recommend(body.patient)
        log.info(
            "[%s] recommend: %s; %s", result.request_id, result.applicable,
            ", ".join(f"{o.arm}={o.status}" + (f"({'+'.join(s.rule_id for s in o.safety)})" if o.safety else "")
                      for o in result.options),
        )
        return JSONResponse(content=result.model_dump(), headers={"X-Request-Id": result.request_id})

    return app


app = create_app()
