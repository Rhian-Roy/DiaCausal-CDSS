"""The v1 endpoints as a schema-only FastAPI app (no logic): it exists so the Pydantic models generate
openapi.json (scripts/export_openapi.py). P14 builds the real orchestrator behind the same signatures.

Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised
clinical use.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic.json_schema import models_json_schema

from diacausal.api.schemas import (MODELS, AnswerCardV1, AskRequestV1, CausalOutputV1, ErrorV1, HealthV1,
                                   RecommendRequestV1)
from diacausal import INTENDED_USE

DESCRIPTION = (
    "Version 1 of the DiaCausal API contract. Every payload carries `schema_version: \"1.0\"` and unknown fields "
    f"are rejected. {INTENDED_USE}"
)


def create_contract_app() -> FastAPI:
    app = FastAPI(title="DiaCausal API", version="1.0", description=DESCRIPTION)
    errors = {422: {"model": ErrorV1, "description": "The request did not match the contract."}}

    @app.get("/api/v1/health", response_model=HealthV1, operation_id="health")
    def health() -> HealthV1:
        raise HTTPException(501, "contract only")

    @app.post("/api/v1/recommend", response_model=CausalOutputV1, responses=errors, operation_id="recommend")
    def recommend(request: RecommendRequestV1) -> CausalOutputV1:
        raise HTTPException(501, "contract only")

    @app.post("/api/v1/ask", response_model=AnswerCardV1, responses=errors, operation_id="ask")
    def ask(request: AskRequestV1) -> AnswerCardV1:
        raise HTTPException(501, "contract only")

    def openapi() -> dict:
        """The endpoints' schema, plus every model of plan 8.4 as a component (some are only used inside others
        or by later layers, such as the guards and the LLM request), so web/types.d.ts has them all."""
        if app.openapi_schema is None:
            spec = FastAPI.openapi(app)
            _, defs = models_json_schema([(m, "validation") for m in MODELS.values()], ref_template="#/components/schemas/{model}")
            schemas = spec.setdefault("components", {}).setdefault("schemas", {})
            for name, schema in defs.get("$defs", {}).items():
                schemas.setdefault(name, schema)
            app.openapi_schema = spec
        return app.openapi_schema

    app.openapi = openapi
    return app
