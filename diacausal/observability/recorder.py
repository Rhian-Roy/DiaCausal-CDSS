"""The trace of one request: spans recorded as the work happens, kept in a context variable so concurrent requests never mix.

    trace = recorder.start("ask", request_id)          # the route, before the pipeline
    with recorder.span("rules", pipeline="ci", component="diacausal.orchestrator.layers:rules_layer", kind="layer") as s:
        ...                                             # the real work
        s.note(eligible=["SGLT2i", "DPP4i"])            # what it produced, as IDs, codes, counts (never values)
    recorder.finish(trace, http_status=200)            # writes it to the store; a failure to write never touches the reply

Nothing is recorded unless a trace was started: the engine's `step()` calls are a no-op in the benchmark, the tests and the scripts.
A span's status is what happened, never what was planned: "completed", "abstained" (the layer correctly could not go on, with its
CODE), "failed" (the exception's CLASS name only), "skipped" (the code reached it and decided not to run it, with a CODE) or "not run"
(the request stopped before it). Durations come from time.perf_counter around the real call.

Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.
"""

from __future__ import annotations

import contextlib
import contextvars
import logging
import math
import os
import re
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

from diacausal.tracing import AbstainSignal

log = logging.getLogger("diacausal.trace")

STATUSES = ("completed", "abstained", "failed", "skipped", "not run")
PIPELINES = ("request", "guards", "ci", "rag", "llm", "output")
_CODE = re.compile(r"[A-Z][A-Z0-9_]{1,40}")
_KEY = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,40}")  # field names, and arm names used as keys (SGLT2i, DPP4i, SU)
# A summary string is a short label, an ID, a version or a setting; anything longer or with other characters is not kept.
_TEXT = re.compile(r"[A-Za-z0-9 _.:;@/#+,()=<>%§'*-]{0,120}")
REDACTED = "<not kept>"

_current: contextvars.ContextVar[Trace | None] = contextvars.ContextVar("diacausal_trace", default=None)
_running: dict[str, Trace] = {}
_running_lock = threading.Lock()


def enabled() -> bool:
    """Recording is on unless DIACAUSAL_OBSERVABILITY=off (then no trace is started, stored or served)."""
    return os.environ.get("DIACAUSAL_OBSERVABILITY", "on").strip().lower() not in ("off", "0", "false", "no")


def safe(value: Any, depth: int = 0) -> Any:
    """Keep only what a summary may hold: numbers (finite, rounded), booleans, None, short label strings, and lists / dicts of them."""
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return round(value, 4) if math.isfinite(value) else None
    if isinstance(value, str):
        return value if _TEXT.fullmatch(value) else REDACTED
    if depth >= 4:
        return REDACTED
    if isinstance(value, (list, tuple, set, frozenset)):
        items = sorted(value) if isinstance(value, (set, frozenset)) else list(value)
        return [safe(v, depth + 1) for v in items[:60]]
    if isinstance(value, dict):
        return {k: safe(v, depth + 1) for k, v in list(value.items())[:60] if isinstance(k, str) and _KEY.fullmatch(k)}
    return REDACTED


@dataclass
class Span:
    span_id: str
    parent_id: str | None
    name: str
    pipeline: str
    component: str
    kind: str  # "layer" (registry.LAYERS), "part" (registry.PARTS), "step" (inside a function), "request"
    start_ms: float | None = None  # from the start of the trace
    duration_ms: float | None = None
    status: str = "not run"
    code: str | None = None
    error_type: str | None = None
    summary: dict[str, Any] = field(default_factory=dict)

    def note(self, **items: Any) -> None:
        """Add to what this span produced (passed through `safe`)."""
        self.summary.update(safe(items))

    def skip(self, code: str) -> None:
        """The code reached this step and decided not to run it (e.g. no option left to estimate)."""
        self.status, self.code = "skipped", code if _CODE.fullmatch(code) else "SKIPPED"

    def as_dict(self) -> dict[str, Any]:
        return {"span_id": self.span_id, "parent_id": self.parent_id, "name": self.name, "pipeline": self.pipeline,
                "component": self.component, "kind": self.kind, "start_ms": self.start_ms, "duration_ms": self.duration_ms,
                "status": self.status, "code": self.code, "error_type": self.error_type, "summary": self.summary}


class _NullSpan:
    """What `span()` / `step()` hand out when nothing is being recorded: every call is a no-op."""

    def note(self, **items: Any) -> None:
        pass

    def skip(self, code: str) -> None:
        pass


NULL = _NullSpan()


@dataclass
class Trace:
    trace_id: str
    request_id: str
    workflow: str
    source: str = "server"
    started_at: float = field(default_factory=time.time)  # wall clock, seconds since 1970 (UTC)
    t0: float = field(default_factory=time.perf_counter)
    spans: list[Span] = field(default_factory=list)
    stack: list[str] = field(default_factory=list)
    status: str = "running"
    code: str | None = None
    http_status: int | None = None
    ended_at: float | None = None
    duration_ms: float | None = None
    context: dict[str, Any] = field(default_factory=dict)  # versions and settings that apply to the whole request
    _ids: int = 0

    def new_span(self, name: str, pipeline: str, component: str, kind: str) -> Span:
        self._ids += 1
        s = Span(span_id=f"{self._ids:03d}", parent_id=self.stack[-1] if self.stack else None, name=name,
                 pipeline=pipeline if pipeline in PIPELINES else "request", component=component, kind=kind)
        self.spans.append(s)
        return s

    def elapsed_ms(self) -> float:
        return (time.perf_counter() - self.t0) * 1000

    def as_dict(self) -> dict[str, Any]:
        spans = [s.as_dict() for s in self.spans]
        return {"trace_id": self.trace_id, "request_id": self.request_id, "workflow": self.workflow, "source": self.source,
                "started_at": self.started_at, "ended_at": self.ended_at, "duration_ms": self.duration_ms, "status": self.status,
                "code": self.code, "http_status": self.http_status, "context": self.context, "spans": spans,
                **rollup(spans)}


def _layer_status(spans: list[dict], names: tuple[str, ...]) -> str:
    """One status for a group of layers: failed > abstained > not run > completed (or "not run" when none of them is there)."""
    found = [s["status"] for s in spans if s["kind"] == "layer" and s["name"] in names]
    for status in ("failed", "abstained", "not run"):
        if status in found:
            return status
    return "completed" if found else "not run"


def rollup(spans: list[dict]) -> dict[str, Any]:
    """The per-pipeline statuses and counts the request list shows (computed from the spans, never stored separately)."""
    failed = [s for s in spans if s["status"] == "failed"]
    return {
        "ci_status": _layer_status(spans, ("rules", "causal engine")),
        "rag_status": _layer_status(spans, ("retrieval",)),
        "llm_status": _layer_status(spans, ("explanation",)),
        "output_status": _layer_status(spans, ("output guards", "formatter")),
        "n_spans": len(spans),
        "n_errors": len(failed),
        "n_warnings": sum(s["status"] == "abstained" for s in spans),
        "failed_stage": failed[0]["name"] if failed else None,
        "error_type": failed[0]["error_type"] if failed else None,
    }


def current() -> Trace | None:
    return _current.get()


def start(workflow: str, request_id: str, source: str = "server") -> Trace | None:
    """Begin the trace of one request (or None when recording is off). The trace ID is new for every request; the request ID is the
    client's (the one in the console trace, on the card and in X-Request-Id), so two requests that reuse an ID never overwrite each other."""
    if not enabled():
        return None
    rid = request_id if isinstance(request_id, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", request_id) else "-"
    trace = Trace(trace_id=uuid.uuid4().hex[:16], request_id=rid, workflow=workflow, source=source)
    _current.set(trace)
    with _running_lock:
        _running[trace.trace_id] = trace
    return trace


def running() -> list[dict[str, Any]]:
    """Requests that have started and not finished (this process only)."""
    with _running_lock:
        return [t.as_dict() for t in _running.values()]


@contextlib.contextmanager
def span(name: str, *, pipeline: str, component: str, kind: str = "step") -> Iterator[Span | _NullSpan]:
    """Record one piece of work in the current trace. AbstainSignal -> "abstained" with its CODE; any other exception -> "failed" with its
    class name; both are re-raised unchanged, so the work behaves exactly as without the trace."""
    trace = _current.get()
    if trace is None:
        yield NULL
        return
    s = trace.new_span(name, pipeline, component, kind)
    s.start_ms = round(trace.elapsed_ms(), 1)
    trace.stack.append(s.span_id)
    t0 = time.perf_counter()
    try:
        yield s
    except AbstainSignal as e:
        s.status, s.code = "abstained", e.code
        raise
    except Exception as e:  # noqa: BLE001 - recorded by class only, then re-raised
        s.status, s.error_type = "failed", type(e).__name__
        raise
    else:
        if s.status == "not run":  # the caller may already have said "skipped" or "abstained" (an abstain it caught and handled)
            s.status = "completed"
    finally:
        s.duration_ms = round((time.perf_counter() - t0) * 1000, 1)
        trace.stack.pop()


def step(name: str, pipeline: str, component: str):
    """A step inside a function (the engine's safety rules, overlap check, DR-learner, ...). A no-op when nothing is recorded."""
    return span(name, pipeline=pipeline, component=component, kind="step")


def not_run(name: str, pipeline: str, component: str, kind: str = "layer") -> None:
    """A layer the request never reached (it stopped earlier): listed, with no time, so the screen shows where it stopped."""
    trace = _current.get()
    if trace is not None:
        trace.new_span(name, pipeline, component, kind)


def describe_into(s: Span | _NullSpan, describe: Callable[[], dict]) -> None:
    """Add a summary to a span; a summary that cannot be built is recorded as its exception class, never allowed to break the work."""
    try:
        s.note(**describe())
    except Exception as e:  # noqa: BLE001
        s.note(summary_error=type(e).__name__)


def wrap_part(name: str, pipeline: str, fn: Callable, describe: Callable | None = None) -> Callable:
    """A part of a layer (registry.PARTS), recorded as a child span of its layer when a trace is running. `describe(args, result)`
    gives its summary (diacausal/observability/summaries.py)."""
    component = f"{fn.__module__}:{fn.__qualname__}"

    def part(*args, **kwargs):
        if _current.get() is None:
            return fn(*args, **kwargs)
        with span(name, pipeline=pipeline, component=component, kind="part") as s:
            result = fn(*args, **kwargs)
            if describe is not None:
                describe_into(s, lambda: describe(args, result))
            return result

    part.__wrapped__ = fn
    part.__name__ = getattr(fn, "__name__", "part")
    return part


def finish(trace: Trace | None, *, http_status: int, code: str | None = None, store=None) -> dict[str, Any] | None:
    """End the trace: its status from what the spans and the reply say, then (when a store is given) write it. Never raises: a trace
    that cannot be written is logged by exception class and the clinician's reply goes out unchanged."""
    if trace is None:
        return None
    try:
        trace.ended_at = time.time()
        trace.duration_ms = round(trace.elapsed_ms(), 1)
        trace.http_status = http_status
        trace.code = code if code and _CODE.fullmatch(code) else None
        statuses = {s.status for s in trace.spans if s.kind == "layer"}
        if http_status >= 500 or "failed" in statuses:
            trace.status = "failed"
        elif http_status == 422:
            trace.status = "blocked"
        elif "abstained" in statuses:
            trace.status = "partial"  # an answer was returned, but at least one layer could not give its part
        else:
            trace.status = "completed"
        record = trace.as_dict()
    except Exception as e:  # noqa: BLE001
        log.warning("[%s] observability: trace not finished error=%s", trace.request_id, type(e).__name__)
        record = None
    finally:
        with _running_lock:
            _running.pop(trace.trace_id, None)
        if _current.get() is trace:
            _current.set(None)
    if record is not None and store is not None:
        try:
            store.save(record)
        except Exception as e:  # noqa: BLE001
            log.warning("[%s] observability: trace not stored error=%s", trace.request_id, type(e).__name__)
    return record
