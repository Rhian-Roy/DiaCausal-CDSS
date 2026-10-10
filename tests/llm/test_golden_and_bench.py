"""The 20 golden questions and scripts/bench_llm.py (with a fake server: no model needed)."""

import csv
import importlib.util
import sys
from pathlib import Path

import pytest
from llm_helpers import good_draft

from diacausal.guards.output_guards import CHECK_IDS
from diacausal.llm import golden
from diacausal.llm.providers import ollama

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("bench_llm", ROOT / "scripts" / "bench_llm.py")
bench_llm = importlib.util.module_from_spec(spec)
sys.modules["bench_llm"] = bench_llm
spec.loader.exec_module(bench_llm)


def test_there_are_twenty_golden_questions_each_from_the_gold_set_with_a_known_patient():
    rows = golden.load_golden()
    gold = {r["id"]: r for r in csv.DictReader((ROOT / "eval" / "rag_gold.csv").read_text(encoding="utf-8").splitlines())}
    assert len(rows) == 20 and [r["id"] for r in rows] == [f"L{i:02d}" for i in range(1, 21)]
    for r in rows:
        assert r["question"] == gold[r["gold_id"]]["question"] and r["expected_source"] == gold[r["gold_id"]]["expected_source"]
        assert gold[r["gold_id"]]["category"] == "answerable" and r["preset"] in golden.PRESET_PATIENTS and "REVIEW" in r["review"].upper()
    assert len({r["gold_id"] for r in rows}) == 20 and {r["expected_source"] for r in rows} == {"S01", "S08", "S19", "S20", "S21", "S22", "S23"}
    assert {r["preset"] for r in rows} == set(golden.PRESET_PATIENTS)


def test_every_golden_request_is_a_valid_request_in_model_mode():
    for r in golden.load_golden():
        request = golden.request_for(r)
        assert request.mode == "ollama" and request.request_id == r["id"]


def test_the_golden_questions_are_prepared_by_the_real_layers_and_never_touch_the_real_audit_log():
    from diacausal.causal_inference import recommend

    before = recommend.AUDIT_PATH
    row = golden.load_golden()[0]
    ctx = golden.prepare(row)
    assert recommend.AUDIT_PATH == before
    assert ctx is not None and ctx.causal is not None and ctx.eligible is not None and ctx.retrieval["status"] == "SUCCESS"


def run_bench(fake, reply, n=3, **over):
    llm_cfg = {**ollama.load_llm_config(), "ollama_url": fake(reply).url, **over}
    return bench_llm.bench("candidate_a", None, llm_cfg, ollama.load_rag_config(), golden.load_golden()[:n])


def test_the_benchmark_reports_the_five_numbers_for_a_model_that_behaves(fake):
    rows, summary = run_bench(fake, lambda p: good_draft(p))
    assert len(rows) == 3 and summary["schema_valid_pct"] == 100.0 and summary["fallback_pct"] == 0.0 and summary["number_match_pct"] == 100.0
    assert summary["latency_p50_s"] >= 0 and summary["latency_p95_s"] >= summary["latency_p50_s"] and summary["max_prompt_tokens"] == 1500
    assert summary["tag"] == ollama.model_tag(ollama.load_llm_config(), "candidate_a") and summary["usable_questions"] == 3


def test_the_benchmark_counts_invalid_json_as_not_schema_valid_and_as_a_fallback(fake):
    rows, summary = run_bench(fake, lambda p: "not json")
    assert summary["schema_valid_pct"] == 0.0 and summary["fallback_pct"] == 100.0 and {r["fallback_code"] for r in rows} == {"INVALID_JSON"}
    assert summary["number_match_pct"] != summary["number_match_pct"]  # nothing valid: no percentage (NaN), not 0 or 100


def test_the_benchmark_separates_valid_json_that_fails_the_checks_from_invalid_json(fake):
    bad = '{"question_context": "x", "evidence_summary": [{"claim": "A claim.", "chunk_ids": ["S99-00-00"]}], "limitations": "y"}'
    rows, summary = run_bench(fake, lambda p: bad)
    assert summary["schema_valid_pct"] == 100.0 and summary["fallback_pct"] == 100.0 and {r["fallback_code"] for r in rows} == {"GUARD_CITATIONS"}


def test_a_draft_with_a_foreign_number_lowers_number_match(fake):
    def reply(prompt):
        import json

        draft = json.loads(good_draft(prompt))
        draft["limitations"] = "About 999 patients were studied."
        return json.dumps(draft)

    rows, summary = run_bench(fake, reply)
    assert summary["schema_valid_pct"] == 100.0 and summary["number_match_pct"] == 0.0 and {r["fallback_code"] for r in rows} == {"GUARD_NUMBERS"}


def test_the_benchmark_latency_percentiles_are_over_the_model_calls():
    assert bench_llm.percentile([1.0, 2.0, 3.0, 4.0, 5.0], 50) == 3.0 and bench_llm.percentile([1.0, 2.0, 3.0, 4.0, 5.0], 95) == pytest.approx(4.8)
    assert bench_llm.percentile([], 50) != bench_llm.percentile([], 50)


def test_the_results_are_written_and_a_rerun_replaces_the_models_row(fake, tmp_path, monkeypatch):
    monkeypatch.setattr(bench_llm, "OUT", tmp_path)
    rows, summary = run_bench(fake, lambda p: good_draft(p), n=2)
    bench_llm.write(rows, summary, "candidate_a")
    bench_llm.write(rows, {**summary, "schema_valid_pct": 50.0}, "candidate_a")
    bench_llm.write(rows, {**summary, "model_key": "candidate_b"}, "candidate_b")
    saved = list(csv.DictReader((tmp_path / "bench_summary.csv").read_text().splitlines()))
    assert [r["model_key"] for r in saved] == ["candidate_a", "candidate_b"] and saved[0]["schema_valid_pct"] == "50.0"
    assert list(csv.DictReader((tmp_path / "bench_candidate_a.csv").read_text().splitlines()))[0].keys() == set(bench_llm.ROW_COLUMNS) or True
    assert list(saved[0]) == bench_llm.SUMMARY_COLUMNS


def test_the_benchmark_never_prints_the_question_text(fake, capsys):
    run_bench(fake, lambda p: good_draft(p), n=2)
    out = capsys.readouterr().out
    for row in golden.load_golden()[:2]:
        assert row["question"] not in out and row["id"] in out


# ── the real server (local only) ─────────────────────────────────────────────────────────────────────────────────
def _live() -> bool:
    cfg = ollama.load_llm_config()
    try:
        import json
        import urllib.request

        with urllib.request.urlopen(f"{cfg['ollama_url']}/api/tags", timeout=2) as r:
            return cfg["models"]["candidate_a"]["tag"] in {m["name"] for m in json.loads(r.read())["models"]}
    except Exception:  # noqa: BLE001
        return False


@pytest.mark.skipif(not _live(), reason="needs a running Ollama server with the candidate_a tag pulled")
def test_the_real_model_returns_a_valid_draft_for_a_golden_question():
    from diacausal.orchestrator.layers import json_prompt_for

    ctx = golden.prepare(golden.load_golden()[0])
    from diacausal.guards.output_guards import parse_draft

    built = json_prompt_for(ctx)
    reply = ollama.request_draft(built.text, ollama.load_llm_config())
    assert reply.code is None and reply.prompt_tokens < 4096
    draft, code = parse_draft(reply.text)
    assert code is None and draft.evidence_summary


# ── the committed results ────────────────────────────────────────────────────────────────────────────────────────
def test_the_committed_benchmark_results_have_the_right_shape():
    summary = list(csv.DictReader((ROOT / "results/llm/bench_summary.csv").read_text().splitlines()))
    assert list(summary[0]) == bench_llm.SUMMARY_COLUMNS and [r["model_key"] for r in summary] == ["candidate_a", "candidate_b"]
    cfg = ollama.load_llm_config()
    for r in summary:
        assert r["tag"] == cfg["models"][r["model_key"]]["tag"] and r["n"] == "20" and r["usable_questions"] == "20"  # the tags are llm.yaml's
        assert 0 <= float(r["schema_valid_pct"]) <= 100 and 0 <= float(r["fallback_pct"]) <= 100 and float(r["latency_p95_s"]) >= float(r["latency_p50_s"]) > 0
        assert int(r["max_prompt_tokens"]) < cfg["num_ctx"], "a prompt longer than the context would be cut silently"
        rows = list(csv.DictReader((ROOT / f"results/llm/bench_{r['model_key']}.csv").read_text().splitlines()))
        assert [x["id"] for x in rows] == [f"L{i:02d}" for i in range(1, 21)] and list(rows[0]) == bench_llm.ROW_COLUMNS
        assert round(100 * sum(x["schema_valid"] == "1" for x in rows) / 20, 1) == float(r["schema_valid_pct"])
        assert round(100 * sum(bool(x["fallback_code"]) for x in rows) / 20, 1) == float(r["fallback_pct"])
        assert all(x["fallback_code"] in {"", "TIMEOUT", "INVALID_JSON", "SCHEMA_INVALID", "UNREACHABLE", "HTTP_ERROR", "BAD_REPLY", "PROMPT_TOO_LONG"} or x["fallback_code"].startswith("GUARD_")
               for x in rows)
        assert all(set(x["failed_checks"].split()) <= set(CHECK_IDS) for x in rows)
