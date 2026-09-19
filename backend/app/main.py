"""Builds the FastAPI app. Run it with:

    .venv/bin/python -m uvicorn app.main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import RedirectResponse

from app import db
from app.auth.deps import AuthProblem, auth_problem_handler
from app.auth.routes import router as auth_router
from app.errors import validation_exception_handler
from app.routes import router
from app.secrets_env import database_url, secret_key
from app.settings import INTENDED_USE
from app.tracing import configure_logging


def create_app(database: str | None = None) -> FastAPI:
    """`database` overrides DIACAUSAL_DATABASE_URL (tests use a throwaway file)."""
    configure_logging()
    secret_key()  # stop now, with a clear message, if backend/.env is missing
    db.configure(database or database_url())
    app = FastAPI(title="DiaCausal API", version="0.2.0", description=INTENDED_USE)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(AuthProblem, auth_problem_handler)
    app.include_router(auth_router)
    app.include_router(router)

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        """Opening http://localhost:8000 in a browser shows the API docs."""
        return RedirectResponse("/docs")

    return app


app = create_app()
