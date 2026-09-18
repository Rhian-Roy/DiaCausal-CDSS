"""Builds the FastAPI app. Run it with:

    .venv/bin/uvicorn app.main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from app.errors import validation_exception_handler
from app.routes import router
from app.settings import INTENDED_USE
from app.tracing import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="DiaCausal API", version="0.1.0", description=INTENDED_USE)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.include_router(router)
    return app


app = create_app()
