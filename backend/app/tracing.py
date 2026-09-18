"""Trace IDs in the backend log.

The browser makes a short trace ID for every message and sends it as
`client_trace_id`. While a request is handled we keep that ID in a context
variable (think: a sticky note attached to the current request), and a logging
filter copies it onto every log line. So one ID links the browser console and
the backend log for the same message.

Privacy rule: never log the message text itself — only sizes, stage results and IDs.
"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

NO_TRACE = "-"

_current_trace_id: ContextVar[str] = ContextVar("trace_id", default=NO_TRACE)


class TraceIdFilter(logging.Filter):
    """Adds `record.trace_id` so the log format can print it."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = _current_trace_id.get()
        return True


# The one logger the whole app writes to.
log = logging.getLogger("diacausal")
log.addFilter(TraceIdFilter())

LOG_FORMAT = "%(asctime)s %(levelname)-7s [%(trace_id)s] %(message)s"


def configure_logging() -> None:
    """Print app logs to the terminal. Safe to call more than once."""
    if any(isinstance(f, TraceIdFilter) for h in log.handlers for f in h.filters):
        return
    handler = logging.StreamHandler()
    handler.addFilter(TraceIdFilter())
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt="%H:%M:%S"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)


@contextmanager
def trace_context(trace_id: str) -> Iterator[None]:
    """Every log line written inside this block carries `trace_id`."""
    token = _current_trace_id.set(trace_id)
    try:
        yield
    finally:
        _current_trace_id.reset(token)
