"""Turn Pydantic's validation errors into messages a person can act on.

FastAPI already rejects a request that does not match schemas.py with HTTP 422,
but its default wording ("Input should be 'text'") is written for programmers.
This handler keeps the 422 and rewrites each problem as a clear sentence, e.g.
    Part 1 has type "image", which this API does not accept. Supported part types: text.

Anything the client sent is echoed back only in short, escaped form (every
non-ASCII or control character becomes a \\uXXXX escape), so a hostile value
cannot flood the response, inject fake lines into the log, or crash the reply.
"""

import json
import re
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas import ErrorResponse, Problem
from app.settings import (
    MAX_PARTS,
    MAX_TEXT_CHARS,
    SCHEMA_VERSION,
    SUPPORTED_PART_TYPES,
    TRACE_ID_PATTERN,
)
from app.tracing import NO_TRACE, log, trace_context

_SUPPORTED = ", ".join(SUPPORTED_PART_TYPES)
_TRACE_ID = re.compile(TRACE_ID_PATTERN)
_PLAIN_KEY = re.compile(r"[A-Za-z0-9_]{1,40}")
_PART_EXAMPLE = '{"type": "text", "text": "..."}'


def _show(value: Any, limit: int = 40) -> str:
    """A short, escaped copy of a client-supplied value."""
    shown = json.dumps(value, default=str)  # ASCII-only: also safe for broken "\ud800"-style input
    return shown if len(shown) <= limit else shown[: limit - 1] + "…"


def _field_name(path: tuple) -> str:
    """("parts", 0, "text") -> "parts[0].text"."""
    name = ""
    for item in path:
        if isinstance(item, int):
            name += f"[{item}]"
        else:
            key = item if _PLAIN_KEY.fullmatch(str(item)) else _show(str(item), 20)
            name += f".{key}" if name else key
    return name or "body"


def _describe(err: dict) -> Problem:
    """One Pydantic error -> one plain-English Problem."""
    loc = tuple(err.get("loc", ()))
    path = loc[1:] if loc[:1] == ("body",) else loc
    kind = err.get("type", "")
    value = err.get("input")
    field = _field_name(path)

    def problem(message: str) -> Problem:
        return Problem(field=field, message=message)

    if kind == "json_invalid":
        return Problem(field="body", message="The request body is not valid JSON.")
    if not path and isinstance(value, bytes):
        # FastAPI only parses JSON when the request says it is JSON.
        return problem('Send the body as JSON with the header "Content-Type: application/json".')
    if not path:
        return problem('The request body must be a JSON object like {"schema_version": "1.0", ...}.')

    if path[0] == "parts" and len(path) >= 2 and isinstance(path[1], int):
        n, rest = path[1] + 1, path[2:]
        if rest == ("type",):
            if kind == "missing":
                return problem(f'Part {n} has no "type". Supported part types: {_SUPPORTED}.')
            return problem(
                f"Part {n} has type {_show(value)}, which this API does not accept. "
                f"Supported part types: {_SUPPORTED}."
            )
        if rest == ("text",):
            if kind == "string_too_long":
                return problem(
                    f"Part {n} text is {len(value):,} characters long; "
                    f"the limit is {MAX_TEXT_CHARS:,}."
                )
            if kind == "missing":
                return problem(f'Part {n} has no "text".')
            return problem(f"Part {n} text must be a string.")
        if not rest:
            return problem(f"Part {n} must be an object like {_PART_EXAMPLE}.")

    if path == ("parts",):
        if kind == "too_short":
            return problem("parts must contain at least one part.")
        if kind == "too_long":
            return problem(f"parts may contain at most {MAX_PARTS} parts.")
        return problem(f"parts is required: a list like [{_PART_EXAMPLE}].")

    if path == ("schema_version",):
        got = "" if kind == "missing" else f" (got {_show(value)})"
        return problem(f'schema_version must be "{SCHEMA_VERSION}"{got}.')

    if path == ("client_trace_id",):
        rule = '1-64 letters, digits, "-" or "_"'
        if kind == "missing":
            return problem(f"client_trace_id is required: {rule}.")
        return problem(f"client_trace_id must be {rule} (got {_show(value)}).")

    if kind == "extra_forbidden":
        return problem(f'"{field}" is not a field this API accepts.')

    return problem(f"{field}: {err.get('msg', 'invalid value')}.")


def _problems(errors: list[dict]) -> list[Problem]:
    """Describe every error, but if a part has the wrong type, report only that
    (its missing or extra fields are just a side effect of the wrong type)."""
    bad_type_parts = {
        loc[2]
        for e in errors
        if len(loc := tuple(e.get("loc", ()))) == 4 and loc[:2] == ("body", "parts") and loc[3] == "type"
    }
    problems: list[Problem] = []
    for e in errors:
        loc = tuple(e.get("loc", ()))
        if len(loc) >= 4 and loc[:2] == ("body", "parts") and loc[2] in bad_type_parts and loc[3] != "type":
            continue
        described = _describe(e)
        if described not in problems:
            problems.append(described)
    return problems


def _trace_id_from(body: Any) -> str | None:
    """The client's trace ID, if the body had a valid one."""
    if isinstance(body, dict):
        candidate = body.get("client_trace_id")
        if isinstance(candidate, str) and _TRACE_ID.fullmatch(candidate):
            return candidate
    return None


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    problems = _problems(list(exc.errors())) or [Problem(field="body", message="The request is not valid.")]
    message = problems[0].message
    if len(problems) > 1:
        more = len(problems) - 1
        message += f' ({more} more problem{"s" if more > 1 else ""} listed in "problems".)'

    trace_id = _trace_id_from(exc.body)
    with trace_context(trace_id or NO_TRACE):
        log.warning("request rejected (422): %s", message)

    body = ErrorResponse(message=message, problems=problems, trace_id=trace_id)
    headers = {"X-Trace-Id": trace_id} if trace_id else None
    return JSONResponse(status_code=422, content=body.model_dump(), headers=headers)
