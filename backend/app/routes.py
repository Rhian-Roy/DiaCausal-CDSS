"""The API's URLs."""

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.auth import audit
from app.auth.deps import Signed, client_ip, require_clinician
from app.auth.schemas import AuthError
from app.db import get_db
from app.pipeline import run_pipeline
from app.schemas import ChatRequest, ChatResponse, ErrorResponse, HealthResponse, PatientPart, TextPart
from app.tracing import log, trace_context

router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> HealthResponse:
    """Is the backend up? Used to check API connectivity."""
    return HealthResponse()


@router.post(
    "/v1/chat",
    responses={
        401: {"model": AuthError, "description": "Not signed in (or the session timed out)."},
        403: {"model": AuthError, "description": "Missing CSRF token, or intended use not acknowledged."},
        422: {"model": ErrorResponse, "description": "The request did not match the contract."},
    },
)
def chat(
    request: ChatRequest,
    response: Response,
    http: Request,
    signed: Signed = Depends(require_clinician),
    db: Session = Depends(get_db),
) -> ChatResponse:
    """Run one message through the pipeline and return the reply plus every stage's result.
    Signed-in clinicians only; every request is written to audit_log (never its text)."""
    with trace_context(request.client_trace_id):
        characters = sum(len(part.text) for part in request.parts if isinstance(part, TextPart))
        log.info("chat request received: %d part(s), %d characters", len(request.parts), characters)
        patient = next((part for part in request.parts if isinstance(part, PatientPart)), None)
        if patient is not None:
            # The names of the fields that were filled in — never the values themselves.
            log.info("patient details: %s", ", ".join(patient.filled_fields()) or "none filled in")
        result = run_pipeline(request)
        stages = ",".join(f"{stage.name}={stage.status}" for stage in result.stages)
        result.request_id = audit.record(
            db, "chat", result.outcome, user_id=signed.user.user_id,
            client_trace_id=request.client_trace_id, detail=stages, ip=client_ip(http),
        )
        log.info("reply sent: outcome=%s", result.outcome)

    response.headers["X-Trace-Id"] = request.client_trace_id
    return result
