#!/usr/bin/env python3
"""Run the 25 synthetic vignettes through the pipeline and save a results table.

    cd backend && .venv/bin/python ../eval/run_vignettes.py
    (in the container:  docker compose exec app python ../eval/run_vignettes.py)

It runs the same pipeline the API runs — guards, clinical guardrails, and the stages
after them — without a web server or a sign-in, so the evaluation pack can be run by
anyone reviewing the project. Results go to eval/results/<date>.csv and a summary is
printed; it exits 1 if any vignette does not do what the table says it should.

NO REAL PATIENT DATA is involved: every vignette is synthetic (see vignettes.v1.json).
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "backend"))

from app.pipeline import run_pipeline  # noqa: E402
from app.schemas import ChatRequest  # noqa: E402


def ask(case: dict) -> dict:
    """One vignette through the pipeline, as a signed-in clinician's message."""
    request = ChatRequest.model_validate({
        "schema_version": "1.0",
        "client_trace_id": case["id"].lower() + "00",
        "parts": [{"type": "text", "text": case["question"]}, case["patient"]],
    })
    reply = run_pipeline(request)
    options = next((part for part in reply.parts if getattr(part, "type", "") == "options"), None)
    return {
        "outcome": reply.outcome.value,
        "reason_code": reply.reason_code.value if reply.reason_code else None,
        "scope_topic": reply.scope_topic,
        "options": {option.option: option.status.value for option in options.options} if options else {},
        "notes": {option.option: len(option.notes) for option in options.options} if options else {},
        "blocked_reason": reply.blocked_reason,
    }


def disagreements(expected: dict, got: dict) -> list[str]:
    problems = []
    for key in ("outcome", "reason_code", "scope_topic"):
        if key in expected and expected[key] != got[key]:
            problems.append(f"{key}: expected {expected[key]!r}, got {got[key]!r}")
    for option, status in expected.get("options", {}).items():
        if got["options"].get(option) != status:
            problems.append(f"{option}: expected {status!r}, got {got['options'].get(option)!r}")
    if (option := expected.get("notes_for")) and not got["notes"].get(option):
        problems.append(f"{option}: expected a note from an 'info' rule, got none")
    return problems


def main() -> int:
    vignettes = json.loads((HERE / "vignettes.v1.json").read_text(encoding="utf-8"))
    results_dir = HERE / "results"
    results_dir.mkdir(exist_ok=True)
    out_file = results_dir / f"{datetime.now(UTC):%Y-%m-%d}.csv"

    rows, failures = [], 0
    for case in vignettes["cases"]:
        got = ask(case)
        problems = disagreements(case["expect"], got)
        failures += bool(problems)
        rows.append({
            "id": case["id"],
            "description": case["description"],
            "outcome": got["outcome"],
            "reason_code": got["reason_code"] or "",
            "sglt2i": got["options"].get("sglt2i", ""),
            "dpp4i": got["options"].get("dpp4i", ""),
            "sulfonylurea": got["options"].get("sulfonylurea", ""),
            "as_expected": "no" if problems else "yes",
            "difference": "; ".join(problems),
        })
        mark = "  " if not problems else "X "
        print(f"{mark}{case['id']}  {case['description'][:58]:58} {got['outcome']:9} {got['reason_code'] or ''}")
        for problem in problems:
            print(f"      {problem}")

    with out_file.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n{len(rows) - failures} of {len(rows)} vignettes behaved as the table says.")
    print(f"Saved: {out_file.relative_to(HERE.parent)}")
    if failures:
        print("\nA difference is not automatically a bug: if a doctor changes a rule in "
              "backend/app/clinical/guardrails.v1.yaml, update the expectation here to match.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
