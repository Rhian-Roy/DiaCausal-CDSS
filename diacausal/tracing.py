"""Console tracing of the request pipeline (docs/PLAN_2026-10.md, section 8.5).

Every layer of a request logs, under the logger `diacausal.trace`:

    [c2f1] entered input guards layer
    [c2f1] executing input guards layer
    [c2f1] passed input guards layer (3 ms)                    or
    [c2f1] abstained retrieval layer reason=NO_EVIDENCE (4 ms) or
    [c2f1] failed explanation layer error=ValueError (2 ms)

Two ways to trace: the context manager `layer(name, request_id)` and the decorator `@traced("name")`.

WHAT IS NEVER LOGGED: patient values, the question, prompts, passages, keys. A log line holds only the request ID,
the layer name, the status, a reason CODE (upper case letters, digits and underscores: free text is refused so a
question cannot slip in as a "reason"), the duration and the exception CLASS name (never its message, which may
contain the input).

Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.
"""

from __future__ import annotations

import contextlib
import functools
import logging
import os
import re
import time
from collections.abc import Callable, Iterator
from typing import Any

log = logging.getLogger("diacausal.trace")

_CODE = re.compile(r"[A-Z][A-Z0-9_]{1,40}")
_SAFE_NAME = re.compile(r"[a-z][a-z ]{1,40}")
_SAFE_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")


class AbstainSignal(Exception):
    """A layer decided, correctly, that it cannot answer (not an error): it logs "abstained ... reason=CODE".
    `result` optionally carries what the layer still produced, so the pipeline can carry on."""

    def __init__(self, code: str, result: Any = None):
        if not _CODE.fullmatch(code):
            raise ValueError("an abstain reason is a CODE such as NO_EVIDENCE, never free text")
        super().__init__(code)
        self.code = code
        self.result = result


def _clean_id(request_id: str) -> str:
    """The request ID the client gave (already limited to A-Z a-z 0-9 - _); anything else is logged as '-'."""
    return request_id if isinstance(request_id, str) and _SAFE_ID.fullmatch(request_id) else "-"


@contextlib.contextmanager
def layer(name: str, request_id: str) -> Iterator[None]:
    if not _SAFE_NAME.fullmatch(name):
        raise ValueError("a layer name is lower-case words, e.g. 'input guards'")
    rid = _clean_id(request_id)
    t0 = time.perf_counter()

    def ms() -> float:
        return (time.perf_counter() - t0) * 1000

    log.info("[%s] entered %s layer", rid, name)
    log.info("[%s] executing %s layer", rid, name)
    try:
        yield
    except AbstainSignal as e:
        log.info("[%s] abstained %s layer reason=%s (%.0f ms)", rid, name, e.code, ms())
        raise
    except Exception as e:  # noqa: BLE001 - logged by class only, then re-raised
        log.warning("[%s] failed %s layer error=%s (%.0f ms)", rid, name, type(e).__name__, ms())
        raise
    else:
        log.info("[%s] passed %s layer (%.0f ms)", rid, name, ms())


def stub_notice(name: str, request_id: str) -> None:
    """A layer that is not built yet says so, so a pass-through is never mistaken for a check that ran."""
    log.info("[%s] %s layer is a STUB: nothing was checked, passing through", _clean_id(request_id), name)


def _find_request_id(args: tuple, kwargs: dict) -> str:
    if "request_id" in kwargs:
        return kwargs["request_id"]
    for a in args:
        rid = getattr(a, "request_id", None)
        if isinstance(rid, str):
            return rid
    return "-"


def traced(name: str) -> Callable:
    """Decorator form of `layer`. The request ID is the `request_id` keyword argument, or the `request_id`
    attribute of the first argument that has one (the pipeline's context object)."""

    def wrap(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def inner(*args, **kwargs):
            with layer(name, _find_request_id(args, kwargs)):
                return fn(*args, **kwargs)

        return inner

    return wrap


_HANDLER_NAME = "diacausal-trace-console"


def configure_console(environment: str | None = None) -> None:
    """Show the trace in the console while developing (set DIACAUSAL_ENV=production to switch it off).
    Safe to call twice. In production the lines still go to whatever handlers the host configures."""
    env = (environment if environment is not None else os.environ.get("DIACAUSAL_ENV", "development")).lower()
    log.setLevel(logging.INFO)
    present = [h for h in log.handlers if h.get_name() == _HANDLER_NAME]
    if env == "production":
        for h in present:
            log.removeHandler(h)
        return
    if present:
        return
    handler = logging.StreamHandler()
    handler.set_name(_HANDLER_NAME)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S"))
    log.addHandler(handler)
