"""Builds the FastAPI app. Run it with:

    .venv/bin/python -m uvicorn app.main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import RedirectResponse

from app.errors import validation_exception_handler
from app.routes import router
from app.settings import INTENDED_USE
from app.tracing import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="DiaCausal API", version="0.1.0", description=INTENDED_USE)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.include_router(router)

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        """Opening http://localhost:8000 in a browser shows the API docs."""
        return RedirectResponse("/docs")

    return app


app = create_app()
