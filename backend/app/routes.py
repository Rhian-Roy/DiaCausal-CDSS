"""The API's URLs."""

from fastapi import APIRouter, Response

from app.pipeline import run_pipeline
from app.schemas import ChatRequest, ChatResponse, ErrorResponse, HealthResponse
from app.tracing import log, trace_context

router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> HealthResponse:
    """Is the backend up? Used to check API connectivity."""
    return HealthResponse()


@router.post(
    "/v1/chat",
    responses={422: {"model": ErrorResponse, "description": "The request did not match the contract."}},
)
def chat(request: ChatRequest, response: Response) -> ChatResponse:
    """Run one message through the pipeline and return the reply plus every stage's result.

    LOGIN: once sign-in exists, add a parameter here such as
    `clinician: Clinician = Depends(require_clinician)` — see app/auth/README.md.
    """
    with trace_context(request.client_trace_id):
        characters = sum(len(part.text) for part in request.parts)
        log.info("chat request received: %d part(s), %d characters", len(request.parts), characters)
        result = run_pipeline(request)
        log.info("reply sent: outcome=%s", result.outcome)

    response.headers["X-Trace-Id"] = request.client_trace_id
    return result
