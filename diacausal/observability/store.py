"""Where finished traces are kept: one SQLite file on this computer (Python's own sqlite3, no new dependency).

    logs/observability.sqlite3        (DIACAUSAL_TRACE_DB=<path> to put it elsewhere; logs/ is not in git, like logs/audit.jsonl)

One row per request: the columns the request list filters and sorts on, plus the whole trace as JSON. One write per request, after it
finished. Retention: the newest KEEP_TRACES rows, none older than KEEP_DAYS (both TEAM-SET, here because they are not clinical numbers).
A trace holds no patient values, question, prompt, passage or model text (recorder.py, summaries.py), so the file holds none either.

Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from diacausal.config import ROOT

KEEP_TRACES = 1000  # TEAM-SET: enough for an evaluation session; the oldest go first
KEEP_DAYS = 30  # TEAM-SET
SORTS = {"time": "started_at", "duration": "duration_ms"}
STATUSES = ("running", "completed", "partial", "blocked", "failed")
PIPELINE_COLUMNS = {"ci": "ci_status", "rag": "rag_status", "llm": "llm_status", "output": "output_status"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS traces (
    trace_id TEXT PRIMARY KEY, request_id TEXT NOT NULL, source TEXT NOT NULL, workflow TEXT NOT NULL,
    started_at REAL NOT NULL, ended_at REAL, duration_ms REAL, status TEXT NOT NULL, http_status INTEGER, code TEXT,
    ci_status TEXT, rag_status TEXT, llm_status TEXT, output_status TEXT,
    n_spans INTEGER, n_errors INTEGER, n_warnings INTEGER, failed_stage TEXT, error_type TEXT, doc TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS traces_started ON traces (started_at);
CREATE INDEX IF NOT EXISTS traces_request ON traces (request_id);
"""
_COLUMNS = ("trace_id", "request_id", "source", "workflow", "started_at", "ended_at", "duration_ms", "status", "http_status", "code",
            "ci_status", "rag_status", "llm_status", "output_status", "n_spans", "n_errors", "n_warnings", "failed_stage", "error_type")


def default_path() -> Path:
    return Path(os.environ.get("DIACAUSAL_TRACE_DB", ROOT / "logs" / "observability.sqlite3"))


class TraceStore:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else default_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        with self._lock:
            self._db.executescript(_SCHEMA)

    def save(self, trace: dict[str, Any]) -> None:
        row = [trace.get(c) for c in _COLUMNS] + [json.dumps(trace, separators=(",", ":"))]
        cutoff = time.time() - KEEP_DAYS * 86400
        with self._lock, self._db:
            self._db.execute(f"INSERT OR REPLACE INTO traces ({', '.join(_COLUMNS)}, doc) VALUES ({', '.join('?' * (len(_COLUMNS) + 1))})", row)
            self._db.execute("DELETE FROM traces WHERE started_at < ?", (cutoff,))
            self._db.execute("DELETE FROM traces WHERE trace_id NOT IN (SELECT trace_id FROM traces ORDER BY started_at DESC LIMIT ?)",
                             (KEEP_TRACES,))

    def get(self, trace_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._db.execute("SELECT doc FROM traces WHERE trace_id = ?", (trace_id,)).fetchone()
        return json.loads(row["doc"]) if row else None

    def query(self, *, q: str | None = None, status: str | None = None, pipeline: str | None = None, pipeline_status: str | None = None,
              since: float | None = None, until: float | None = None, problems: bool = False, sort: str = "time", order: str = "desc",
              limit: int = 50, offset: int = 0) -> tuple[int, list[dict[str, Any]]]:
        """(how many match, one page of them), newest first by default. Only the list columns, never the spans."""
        where, args = [], []
        if q:
            where.append("(trace_id LIKE ? OR request_id LIKE ?)")
            args += [f"{q}%", f"{q}%"]
        if status:
            where.append("status = ?")
            args.append(status)
        if pipeline in PIPELINE_COLUMNS:
            column = PIPELINE_COLUMNS[pipeline]
            where.append(f"{column} = ?" if pipeline_status else f"{column} != 'not run'")
            if pipeline_status:
                args.append(pipeline_status)
        if since is not None:
            where.append("started_at >= ?")
            args.append(since)
        if until is not None:
            where.append("started_at <= ?")
            args.append(until)
        if problems:
            where.append("(n_errors > 0 OR n_warnings > 0 OR status IN ('failed', 'blocked'))")
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        direction = "ASC" if order == "asc" else "DESC"
        with self._lock:
            total = self._db.execute(f"SELECT COUNT(*) FROM traces {clause}", args).fetchone()[0]
            rows = self._db.execute(f"SELECT {', '.join(_COLUMNS)} FROM traces {clause} ORDER BY {SORTS.get(sort, 'started_at')} {direction}, "
                                    f"started_at DESC LIMIT ? OFFSET ?", [*args, limit, offset]).fetchall()
        return total, [dict(r) for r in rows]

    def summary(self, recent: int = 10) -> dict[str, Any]:
        """Counts and durations over every stored trace (the persisted history, not just this session)."""
        with self._lock:
            by_status = dict(self._db.execute("SELECT status, COUNT(*) FROM traces GROUP BY status").fetchall())
            durations = [r[0] for r in self._db.execute(
                "SELECT duration_ms FROM traces WHERE duration_ms IS NOT NULL ORDER BY duration_ms").fetchall()]
            first_last = self._db.execute("SELECT MIN(started_at), MAX(started_at) FROM traces").fetchone()
            failures = {name: self._db.execute(f"SELECT COUNT(*) FROM traces WHERE {column} = 'failed'").fetchone()[0]
                        for name, column in PIPELINE_COLUMNS.items()}
            abstentions = {name: self._db.execute(f"SELECT COUNT(*) FROM traces WHERE {column} = 'abstained'").fetchone()[0]
                           for name, column in PIPELINE_COLUMNS.items()}
            problems = self._db.execute(
                "SELECT trace_id, request_id, started_at, status, http_status, code, failed_stage, error_type, n_errors, n_warnings FROM traces "
                "WHERE n_errors > 0 OR n_warnings > 0 OR status IN ('failed', 'blocked') ORDER BY started_at DESC LIMIT ?", (recent,)).fetchall()
        total = sum(by_status.values())

        def pct(p: float) -> float | None:
            return round(durations[min(len(durations) - 1, int(p * (len(durations) - 1) + 0.5))], 1) if durations else None

        answered = by_status.get("completed", 0) + by_status.get("partial", 0)
        return {
            "total": total, "by_status": {s: by_status.get(s, 0) for s in STATUSES if s != "running"},
            "answered_share": round(answered / total, 4) if total else None,
            "duration_ms": {"mean": round(sum(durations) / len(durations), 1) if durations else None, "p50": pct(0.5), "p95": pct(0.95),
                            "n": len(durations)},
            "failures": failures, "abstentions": abstentions,
            "first_at": first_last[0], "last_at": first_last[1],
            "recent_problems": [dict(r) for r in problems],
            "retention": {"keep_traces": KEEP_TRACES, "keep_days": KEEP_DAYS},
        }

    def close(self) -> None:
        with self._lock:
            self._db.close()
