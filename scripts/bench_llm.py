"""Benchmark a local model on the 20 golden questions (eval/llm_golden.csv; docs/PLAN_2026-10.md section 8.8).

    .venv/bin/python scripts/bench_llm.py --model candidate_a        # a key of diacausal/llm/llm.yaml `models`
    .venv/bin/python scripts/bench_llm.py --all                      # every candidate in llm.yaml
    .venv/bin/python scripts/bench_llm.py --tag <ollama tag>         # any other pulled tag, for a one-off try (read it from your shell, not from here)

Model tags are read from diacausal/llm/llm.yaml and nowhere else. Needs a running Ollama server with the tag pulled.

For each question the REAL pipeline layers run (rules, causal engine, retrieval), the section 8.9 prompt is built, and the model is
asked once through the same code the pipeline uses (providers/ollama.py: JSON schema in `format`, temperature 0, num_ctx 4096,
60 s timeout). One warm-up call (not counted) loads the model first. Reported:

    schema-valid %   replies that were valid JSON and parsed as AnswerDraftV1                      (of all questions)
    number-match %   schema-valid drafts whose every number is in the causal output or the drivers,
                     or is a page or version number of a passage it cites (plan 8.10 check 3)      (of the schema-valid drafts)
    fallback %       questions that the pipeline would have answered with the template instead: any error or timeout, or a
                     draft that fails one of the seven output checks of plan 8.10 (P23). A claim that only the citation check
                     drops does NOT count: the rest of the draft is used (`dropped_claims` in the per-question file)   (of all questions)
    latency p50/p95  seconds of the model call, over all questions (an error counts at the time it took)

Writes results/llm/bench_<key>.csv (one row per question) and results/llm/bench_summary.csv (one row per model, replaced on re-run).
The question text is never printed: only ids.

Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.
"""

from __future__ import annotations

import argparse
import csv
import json
import platform
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from diacausal.llm.answer import GuardInputs, resolve  # noqa: E402
from diacausal.llm.golden import load_golden, prepare  # noqa: E402
from diacausal.llm.providers import ollama  # noqa: E402

OUT = ROOT / "results" / "llm"
SUMMARY_COLUMNS = ["model_key", "tag", "n", "usable_questions", "schema_valid_pct", "number_match_pct", "fallback_pct", "latency_p50_s",
                   "latency_p95_s", "max_prompt_estimate", "max_prompt_tokens", "warmup_s", "ollama_version", "date", "machine"]
ROW_COLUMNS = ["id", "preset", "schema_valid", "number_match", "fallback_code", "seconds", "prompt_estimate", "prompt_tokens", "eval_tokens", "claims", "dropped_claims", "failed_checks"]


def server_version(cfg: dict) -> str:
    try:
        with urllib.request.urlopen(f"{cfg['ollama_url'].rstrip('/')}/api/version", timeout=5) as r:
            return json.loads(r.read()).get("version", "unknown")
    except Exception:  # noqa: BLE001
        return "unreachable"


def percentile(values: list[float], q: float) -> float:
    return float(np.percentile(values, q)) if values else float("nan")


def bench(key: str | None, tag: str | None, llm_cfg: dict, rag_cfg: dict, golden: list[dict]) -> tuple[list[dict], dict]:
    from diacausal.api.schemas import AnswerDraftV1  # noqa: F401

    tag = tag or ollama.model_tag(llm_cfg, key)
    from diacausal.llm.prompt_builder import PromptError
    from diacausal.orchestrator.layers import json_prompt_for

    contexts = [(row, prepare(row)) for row in golden]
    usable = [(row, ctx) for row, ctx in contexts if ctx is not None]
    print(f"{tag}: {len(usable)} of {len(golden)} golden questions have evidence", flush=True)
    warm = 0.0
    if usable:
        row, ctx = usable[0]
        warm = ollama.request_draft(json_prompt_for(ctx).text, llm_cfg, tag).seconds
        print(f"  warm-up (not counted): {warm:.1f} s", flush=True)
    rows = []
    for row, ctx in usable:
        try:
            built = json_prompt_for(ctx)
        except PromptError as error:  # no model call: the pipeline would use the template here
            rows.append({"id": row["id"], "preset": row["preset"], "schema_valid": 0, "number_match": "", "fallback_code": error.code, "seconds": 0,
                         "prompt_estimate": "", "prompt_tokens": "", "eval_tokens": "", "claims": "", "dropped_claims": "", "failed_checks": ""})
            print(f"  {row['id']}  no prompt: {error.code}", flush=True)
            continue
        reply = ollama.request_draft(built.text, llm_cfg, tag)
        inputs = GuardInputs(eligible=ctx.eligible, causal=ctx.causal, drivers=ctx.drivers or {}, number_sources=tuple(built.number_sources))
        explanation, guarded = resolve(ctx.request.question, reply, evidence=ctx.retrieval, rag_cfg=rag_cfg,
                                       llm_cfg=llm_cfg, idf=ctx.idf, inputs=inputs)
        verdict = {c.id: c.result for c in guarded.checks} if guarded else {}
        parsed = verdict.get("parse") == "PASS"
        failed = [i for i, r in verdict.items() if r == "FAIL"]
        rows.append({"id": row["id"], "preset": row["preset"], "schema_valid": int(parsed), "number_match": int(verdict["numbers"] == "PASS") if parsed else "",
                     "fallback_code": explanation["fallback"] or "", "seconds": round(reply.seconds, 2), "prompt_estimate": built.tokens,
                     "prompt_tokens": reply.prompt_tokens or "", "eval_tokens": reply.eval_tokens or "",
                     "claims": len(explanation["sentences"]) if explanation["fallback"] is None else "", "dropped_claims": explanation.get("dropped_claims", 0),
                     "failed_checks": " ".join(failed)})
        print(f"  {row['id']}  {'valid ' if parsed else 'INVALID'}  fallback={explanation['fallback'] or '-':20s} {reply.seconds:5.1f} s", flush=True)
    n = len(rows)
    valid = [r for r in rows if r["schema_valid"]]
    summary = {"model_key": key or "(tag given)", "tag": tag, "n": len(golden), "usable_questions": n,
               "schema_valid_pct": round(100 * len(valid) / n, 1) if n else float("nan"),
               "number_match_pct": round(100 * sum(r["number_match"] == 1 for r in valid) / len(valid), 1) if valid else float("nan"),
               "fallback_pct": round(100 * sum(bool(r["fallback_code"]) for r in rows) / n, 1) if n else float("nan"),
               "latency_p50_s": round(percentile([r["seconds"] for r in rows], 50), 2), "latency_p95_s": round(percentile([r["seconds"] for r in rows], 95), 2),
               "max_prompt_estimate": max([r["prompt_estimate"] for r in rows if r["prompt_estimate"] != ""] or [0]),
               "max_prompt_tokens": max([r["prompt_tokens"] for r in rows if r["prompt_tokens"] != ""] or [0]), "warmup_s": round(warm, 1),
               "ollama_version": server_version(llm_cfg), "date": date.today().isoformat(), "machine": f"{platform.machine()} {platform.system()}"}
    return rows, summary


def write(rows: list[dict], summary: dict, key: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / f"bench_{key}.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=ROW_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    path = OUT / "bench_summary.csv"
    old = [r for r in csv.DictReader(path.read_text(encoding="utf-8").splitlines())] if path.exists() else []
    merged = [r for r in old if r["model_key"] != summary["model_key"]] + [summary]
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=SUMMARY_COLUMNS)
        w.writeheader()
        w.writerows(merged)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    which = ap.add_mutually_exclusive_group(required=True)
    which.add_argument("--model", help="a key of llm.yaml `models`")
    which.add_argument("--all", action="store_true", help="every candidate in llm.yaml")
    which.add_argument("--tag", help="an Ollama tag not in llm.yaml (one-off)")
    ap.add_argument("--limit", type=int, help="only the first N golden questions (a quick try)")
    a = ap.parse_args(argv)
    llm_cfg, rag_cfg = ollama.load_llm_config(), ollama.load_rag_config()
    golden = load_golden()[: a.limit] if a.limit else load_golden()
    keys = sorted(llm_cfg["models"]) if a.all else [a.model] if a.model else [None]
    for key in keys:
        rows, summary = bench(key, a.tag, llm_cfg, rag_cfg, golden)
        write(rows, summary, key or "tag")
        print(f"  {summary['tag']}: schema-valid {summary['schema_valid_pct']}%  number-match {summary['number_match_pct']}% (of valid)  "
              f"fallback {summary['fallback_pct']}%  p50 {summary['latency_p50_s']} s  p95 {summary['latency_p95_s']} s  "
              f"max prompt {summary['max_prompt_tokens']} tokens")
    print("Saved results/llm/. Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
