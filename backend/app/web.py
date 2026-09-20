"""Serving the built page, and the headers a browser needs to be strict with it.

In development the page is served by Vite on :5173 and talks to this API on :8000.
In a container there is **one** origin: FastAPI serves the built files from
`frontend/dist` and `/api/...` itself. That is simpler to deploy, removes CORS
entirely, and makes the `__Host-` session cookie behave exactly as intended.
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app.settings import MAX_REQUEST_BYTES

# Where `npm run build` puts the page (the Dockerfile copies it here).
BUILT_PAGE = Path(__file__).resolve().parents[2] / "frontend" / "dist"

# What the page is allowed to do. It loads nothing from anywhere else: no CDN, no
# analytics, no Google Fonts (the fonts are bundled). 'unsafe-inline' is needed for the
# style attribute Vite emits; scripts have no such exception.
CONTENT_SECURITY_POLICY = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",  # the CAPTCHA image and the QR code are data: URLs
    "media-src 'self'",  # the spoken CAPTCHA
    "font-src 'self'",
    "connect-src 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",  # nobody may put DiaCausal in an iframe
    "base-uri 'none'",
    "object-src 'none'",
])


def add_security_headers(app: FastAPI, *, production: bool) -> None:
    @app.middleware("http")
    async def security_headers(request: Request, call_next) -> Response:
        # Refuse a body that is too large before reading it (uvicorn streams it otherwise).
        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > MAX_REQUEST_BYTES:
            return Response(status_code=413, content="Request too large.", media_type="text/plain")

        response = await call_next(request)
        response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        # The microphone is used by the page itself (voice input); nothing else is allowed.
        response.headers.setdefault("Permissions-Policy", "microphone=(self), camera=(), geolocation=()")
        if production and request.url.scheme == "https":
            # Only over HTTPS, and only in production: telling a browser to refuse http
            # for a year is not something to do from a development machine.
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response


def serve_built_page(app: FastAPI) -> bool:
    """Serve frontend/dist at / if it has been built. Returns whether it is there."""
    index = BUILT_PAGE / "index.html"
    if not index.is_file():
        return False

    app.mount("/assets", StaticFiles(directory=BUILT_PAGE / "assets"), name="assets")

    # Addresses that belong to the API, not the page: they must never quietly serve
    # the page instead (in production the API documentation is off, so they are 404).
    reserved = ("api", "docs", "redoc", "openapi.json")

    @app.get("/{path:path}", include_in_schema=False)
    def page(path: str) -> Response:
        """Any other address serves the page (it is a single-page app)."""
        if path.split("/")[0] in reserved:
            raise HTTPException(status_code=404, detail="Not found.")
        candidate = (BUILT_PAGE / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(BUILT_PAGE.resolve()):
            return FileResponse(candidate)
        return FileResponse(index, headers={"Cache-Control": "no-store"})

    return True
