"""Step (i): the causal engine as a web API.

    uvicorn diacausal.api.main:app --port 8001      # docs at http://localhost:8001/docs

POST /api/v1/recommend   patient details in -> structured Causal Output out (the engine alone)
POST /api/v1/ask         patient details + a question -> AnswerCardV1 (the whole pipeline: routes_v1.py)
GET  /api/v1/health      is the engine up?
GET  /api/v1/llm         which writer answers questions here: the template, or a local Ollama model (and is it running?)
GET  /api/v1/observability/...   the recorded trace of each /ask request (routes_observability.py; this computer only)
GET  /                   the website (web/), with the same security headers as on Netlify (web/netlify.toml): the clinic
                         laptop (scripts/start_clinic.*, docs/OFFLINE_INSTALL.md) opens this, on 127.0.0.1 only

Every response — including errors — carries the intended-use statement:
Research prototype for clinician evaluation; not a marketed medical device;
not for unsupervised clinical use.

Logs carry request IDs, option statuses and rule IDs only — never patient values.
"""

from __future__ import annotations

import logging
import time
import tomllib
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from diacausal import INTENDED_USE, __version__
from diacausal.config import WEB_DIR
from diacausal.causal_inference.recommend import Engine, get_engine
from diacausal.api.routes_observability import router as observability_router
from diacausal.api.routes_v1 import router as v1_router
from diacausal.causal_inference.schemas import CausalOutput, ErrorOut, HealthOut, RecommendRequest
from diacausal.observability import engine_facts
from diacausal.observability.recorder import enabled as observability_enabled
from diacausal.observability.store import TraceStore
from diacausal.tracing import configure_console

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


NOT_THE_PAGE = ("/api/", "/docs", "/redoc", "/openapi.json")  # these keep FastAPI's own headers (/docs loads its own scripts)


def site_headers(toml_path=WEB_DIR / "netlify.toml") -> dict[str, dict[str, str]]:
    """The security headers of the public site, read from web/netlify.toml so the laptop and Netlify can never differ:
    {path pattern: {header: value}} ("/*" for every file, "/sw.js" for the service worker)."""
    data = tomllib.loads(toml_path.read_text(encoding="utf-8"))
    return {h["for"]: dict(h["values"]) for h in data.get("headers", [])}


def create_app(engine: Engine | None = None, trace_store: TraceStore | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configure_console()  # the pipeline trace in the console while developing (DIACAUSAL_ENV=production: off)
        fit_ms = None
        if engine is None and get_engine.cache_info().currsize == 0:  # timed only when it is really fitted here
            t0 = time.perf_counter()
            app.state.engine = get_engine()
            fit_ms = (time.perf_counter() - t0) * 1000
        else:
            app.state.engine = engine or get_engine()  # fit once at startup, not on the first request
        from diacausal.orchestrator.layers import warm_up

        warm_up()  # build the search index now, not on the first /ask
        # observability (docs/OBSERVABILITY.md): the trace store on this computer and what the engine was fitted on
        app.state.trace_store = trace_store or (TraceStore() if observability_enabled() else None)
        app.state.engine_facts = engine_facts.describe(app.state.engine, fit_ms)
        log.info("[-] engine %s ready", __version__)
        yield
        if trace_store is None and app.state.trace_store is not None:
            app.state.trace_store.close()

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
        log.warning("[-] %s: rejected (%d problem(s))", request.url.path.rsplit("/", 1)[-1], len(problems))
        body = ErrorOut(message="The request was not accepted: " + "; ".join(
            f"{p['field']}: {p['message']}" for p in problems), problems=problems)
        return JSONResponse(status_code=422, content=body.model_dump())

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        return JSONResponse(status_code=exc.status_code,
                            content={"error": "http_error", "message": str(exc.detail), "intended_use": INTENDED_USE})

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception):
        """Any other crash: a plain JSON reply with the intended-use statement, never the exception's text (it could repeat the input)."""
        log.error("[-] %s: failed error=%s", request.url.path.rsplit("/", 1)[-1], type(exc).__name__)
        return JSONResponse(status_code=500, content={"error": "internal", "intended_use": INTENDED_USE,
                            "message": "The request could not be completed and nothing was shown. Try again, or tell the team."})

    @app.get("/api/v1/health", response_model=HealthOut)
    def health() -> HealthOut:
        return HealthOut(engine=__version__)

    @app.get("/config.json", include_in_schema=False)
    def page_config() -> JSONResponse:
        """The website's committed settings (accounts off, never a key) plus "clinic": true, so the page knows it is served by this
        server and asks /api/v1/llm. On Netlify config.json has no "clinic", so the public page makes no extra request."""
        import json

        base = json.loads((WEB_DIR / "config.json").read_text(encoding="utf-8"))
        return JSONResponse(content={**base, "clinic": True}, headers={"Cache-Control": "no-cache"})

    @app.get("/api/v1/llm")
    def llm_status() -> JSONResponse:
        """Which writer answers questions on this computer (for the page's banner). Asked fresh each time, with a 2 s limit."""
        from diacausal.llm.providers import ollama

        return JSONResponse(content={**ollama.status(ollama.load_llm_config()), "intended_use": INTENDED_USE})

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

    app.include_router(v1_router)
    app.include_router(observability_router)

    headers = site_headers()

    @app.middleware("http")
    async def page_headers(request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        if not path.startswith(NOT_THE_PAGE):
            for pattern, values in headers.items():
                if pattern == "/*" or pattern == path:
                    response.headers.update(values)
        return response

    # The website itself, last, so every /api route above wins. html=True serves index.html for "/".
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
    return app


app = create_app()
