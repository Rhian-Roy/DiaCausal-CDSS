"""providers/ollama.py (P21): the exact request, and a fallback to the template on EVERY kind of failure."""

import json
import logging
import time

import pytest
from llm_helpers import evidence_lines, good_draft

from diacausal.api.schemas import AnswerDraftV1
from diacausal.llm.prompt_builder import number_sources
from diacausal.llm.providers import ollama
from diacausal.llm.providers.template import template
from diacausal.rag.ingest.licence_gate import ingest
from diacausal.rag.retrieve.hybrid import Retriever

QUESTION = "Can SGLT2 inhibitors cause ketoacidosis?"
CANARY = "ZEBRA-CANARY-7731"


@pytest.fixture(scope="module")
def evidence():
    return Retriever(ingest()).search(QUESTION)


def prompt_for(evidence, question=QUESTION):
    """A stand-in for the real prompt (tests/llm/test_prompt_budget.py covers that one): the provider only sends text."""
    lines = [f'[{p["chunk_id"]}] {p["citation"]["title"]}, {p["citation"]["version"]}, {p["citation"]["section"]}, p.{p["citation"]["page"]}: "{p["text"]}"'
             for p in evidence["passages"]]
    return "\n".join([f"QUESTION: {question}", "<evidence>", *lines, "</evidence>"])


def with_url(cfg, server, **over):
    return {**cfg, "ollama_url": server.url, "provider": "ollama", **over}


def run(evidence, cfg, rag_cfg, number_sources=None):
    return ollama.explain_structured(QUESTION, evidence, prompt_for(evidence), rag_cfg, cfg, number_sources=number_sources)


def assert_template_fallback(reply, evidence, rag_cfg, code):
    expected = template(QUESTION, evidence, rag_cfg)
    assert reply["fallback"] == code and reply["backend"] == "template" and reply["status"] == expected["status"]
    assert reply["sentences"] == expected["sentences"] and code in reply["note"]


# ── the request ──────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_request_has_exactly_what_the_task_asks_for(fake, llm_cfg, evidence, rag_cfg):
    server = fake(lambda prompt: good_draft(prompt))
    run(evidence, with_url(llm_cfg, server), rag_cfg)
    (body,) = server.requests
    assert server.paths == ["/api/generate"]
    assert body["model"] == llm_cfg["models"][llm_cfg["model"]]["tag"]  # the tag comes from llm.yaml
    assert body["stream"] is False and body["format"] == AnswerDraftV1.model_json_schema()  # structured output: the JSON schema in `format`
    assert body["options"] == {"temperature": 0, "num_ctx": 4096} and body["keep_alive"] == llm_cfg["keep_alive"]
    assert "think" not in body  # only when llm.yaml sets it
    assert body["prompt"] == prompt_for(evidence)


def test_think_is_sent_only_when_the_config_sets_it(llm_cfg):
    assert "think" not in ollama.request_body("p", llm_cfg) and ollama.request_body("p", {**llm_cfg, "think": False})["think"] is False


def test_the_settings_are_the_ones_of_the_task_and_every_entry_has_a_source():
    import yaml

    raw = yaml.safe_load(ollama.CONFIG_PATH.read_text(encoding="utf-8"))
    assert all(e.get("source") and e.get("status") in ("CITED", "ASSUMED-DIRECTIONAL", "TEAM-SET") for e in raw.values())
    cfg = ollama.load_llm_config()
    assert (cfg["provider"], cfg["timeout_seconds"], cfg["temperature"], cfg["num_ctx"]) == ("template", 60, 0, 4096)
    assert set(cfg["models"]) == {"candidate_a", "candidate_b"} and cfg["ollama_url"].startswith("http://localhost")


def test_model_tags_live_in_llm_yaml_only():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    for path in [root / "scripts/bench_llm.py", *(root / "diacausal/llm").rglob("*.py"), *(root / "diacausal/orchestrator").rglob("*.py")]:
        text = path.read_text(encoding="utf-8").lower()
        assert "qwen3" not in text and "medgemma" not in text and "q4_k_m" not in text, f"{path.name} hard-codes a model tag"
    assert "qwen3" in ollama.model_tag(ollama.load_llm_config(), "candidate_a") and "medgemma" in ollama.model_tag(ollama.load_llm_config(), "candidate_b")


def test_an_unknown_model_key_is_an_error_not_a_guess(llm_cfg):
    with pytest.raises(ollama.OllamaError) as e:
        ollama.model_tag(llm_cfg, "candidate_z")
    assert e.value.code == "UNKNOWN_MODEL_KEY"


def test_the_template_is_the_default_and_the_model_needs_the_config_and_the_request():
    cfg = ollama.load_llm_config()
    assert cfg["provider"] == "template"
    assert not ollama.is_enabled(cfg, "ollama") and not ollama.is_enabled(cfg, "template")
    assert not ollama.is_enabled({**cfg, "provider": "ollama"}, "template")
    assert ollama.is_enabled({**cfg, "provider": "ollama"}, "ollama")


# ── a good answer ────────────────────────────────────────────────────────────────────────────────────────────────
def test_a_good_draft_becomes_cited_sentences_written_by_the_model(fake, llm_cfg, evidence, rag_cfg):
    server = fake(lambda prompt: good_draft(prompt, claims=2))
    reply = run(evidence, with_url(llm_cfg, server), rag_cfg)
    assert reply["status"] == "SUCCESS" and reply["backend"] == "ollama" and reply["fallback"] is None and len(reply["sentences"]) == 2
    assert all(s["cites"] and all(1 <= n <= len(evidence["passages"]) for n in s["cites"]) for s in reply["sentences"])
    assert "intended_use" in reply


def test_a_model_that_says_there_is_not_enough_evidence_is_respected_without_echoing_it(fake, llm_cfg, evidence, rag_cfg):
    text = json.dumps({"question_context": "x", "evidence_summary": [], "limitations": CANARY, "insufficient": True, "insufficient_reason": CANARY})
    reply = run(evidence, with_url(llm_cfg, fake(lambda p: text)), rag_cfg)
    assert reply["status"] == "INSUFFICIENT_EVIDENCE" and reply["sentences"] == [] and CANARY not in json.dumps(reply)


def test_at_most_max_claims_are_kept(fake, llm_cfg, evidence, rag_cfg):
    reply = run(evidence, with_url(llm_cfg, fake(lambda p: good_draft(p, claims=5)), max_claims=2), rag_cfg)
    assert reply["status"] == "SUCCESS" and len(reply["sentences"]) == 2


# ── every failure falls back to the template ─────────────────────────────────────────────────────────────────────
def test_a_server_that_is_not_running_falls_back(llm_cfg, evidence, rag_cfg):
    reply = run(evidence, {**llm_cfg, "ollama_url": "http://127.0.0.1:9", "timeout_seconds": 2}, rag_cfg)
    assert_template_fallback(reply, evidence, rag_cfg, "UNREACHABLE")


def test_a_slow_model_falls_back_at_the_timeout(fake, llm_cfg, evidence, rag_cfg):
    server = fake({"sleep": 2.0, "then": good_draft})
    started = time.perf_counter()
    reply = run(evidence, with_url(llm_cfg, server, timeout_seconds=0.4), rag_cfg)
    assert time.perf_counter() - started < 1.8, "the call must give up at the timeout, not wait for the model"
    assert_template_fallback(reply, evidence, rag_cfg, "TIMEOUT")


def test_the_timeout_in_the_config_is_sixty_seconds_and_is_what_the_request_uses(llm_cfg, monkeypatch):
    seen = []
    monkeypatch.setattr(ollama.urllib.request, "urlopen", lambda req, timeout=None: (seen.append(timeout), (_ for _ in ()).throw(TimeoutError()))[1])
    with pytest.raises(ollama.OllamaError) as e:
        ollama.post_generate({"model": "m"}, llm_cfg)
    assert seen == [60.0] and e.value.code == "TIMEOUT"


@pytest.mark.parametrize("spec,code", [({"status": 500}, "HTTP_ERROR"), ({"status": 404}, "HTTP_ERROR"), ({"raw": b"not json at all"}, "BAD_REPLY"),
                                       ({"raw": b'{"no_response_field": 1}'}, "BAD_REPLY"), ({"raw": b'["a list"]'}, "BAD_REPLY"),
                                       ({"text": "this is not json"}, "INVALID_JSON"), ({"text": '{"question_context": "x"'}, "INVALID_JSON"),
                                       ({"text": '{"question_context": "x"}'}, "SCHEMA_INVALID"),
                                       ({"text": json.dumps({"question_context": "x", "evidence_summary": [], "limitations": "y", "extra": 1})}, "SCHEMA_INVALID"),
                                       ({"text": json.dumps({"question_context": 1, "evidence_summary": [], "limitations": "y"})}, "SCHEMA_INVALID"),
                                       ({"text": "[]"}, "SCHEMA_INVALID")])
def test_every_kind_of_bad_reply_falls_back_with_its_own_code(fake, llm_cfg, evidence, rag_cfg, spec, code):
    reply = run(evidence, with_url(llm_cfg, fake(spec)), rag_cfg)
    assert_template_fallback(reply, evidence, rag_cfg, code)


def test_a_claim_citing_a_passage_that_was_never_retrieved_falls_back(fake, llm_cfg, evidence, rag_cfg):
    bad = json.dumps({"question_context": "x", "evidence_summary": [{"claim": "SGLT2 inhibitors can cause ketoacidosis.", "chunk_ids": ["S99-00-00"]}], "limitations": "y"})
    assert_template_fallback(run(evidence, with_url(llm_cfg, fake(lambda p: bad)), rag_cfg), evidence, rag_cfg, "CITATION_CHECK")


def test_a_claim_without_a_citation_falls_back(fake, llm_cfg, evidence, rag_cfg):
    bad = json.dumps({"question_context": "x", "evidence_summary": [{"claim": "SGLT2 inhibitors can cause ketoacidosis.", "chunk_ids": []}], "limitations": "y"})
    assert_template_fallback(run(evidence, with_url(llm_cfg, fake(lambda p: bad)), rag_cfg), evidence, rag_cfg, "CITATION_CHECK")


def test_a_claim_the_cited_passage_does_not_support_falls_back(fake, llm_cfg, evidence, rag_cfg):
    cid = evidence["passages"][0]["chunk_id"]
    bad = json.dumps({"question_context": "x", "evidence_summary": [{"claim": "Oranges cure everything in a dark quiet room tonight.", "chunk_ids": [cid]}], "limitations": "y"})
    assert_template_fallback(run(evidence, with_url(llm_cfg, fake(lambda p: bad)), rag_cfg), evidence, rag_cfg, "CITATION_CHECK")


def test_a_claim_with_a_dose_falls_back(fake, llm_cfg, evidence, rag_cfg):
    cid, text = evidence_lines(prompt_for(evidence))[0]
    bad = json.dumps({"question_context": "x", "evidence_summary": [{"claim": " ".join(text.split()[:10]) + " Take 10 mg once daily.", "chunk_ids": [cid]}], "limitations": "y"})
    assert_template_fallback(run(evidence, with_url(llm_cfg, fake(lambda p: bad)), rag_cfg), evidence, rag_cfg, "CITATION_CHECK")


def test_a_number_that_is_not_in_the_causal_output_falls_back(fake, llm_cfg, evidence, rag_cfg):
    cid, text = evidence_lines(prompt_for(evidence))[0]
    words = " ".join(w for w in text.split() if not any(c.isdigit() for c in w))
    draft = json.dumps({"question_context": "x", "evidence_summary": [{"claim": " ".join(words.split()[:12]), "chunk_ids": [cid]}],
                        "limitations": "The estimate is -0.9 points."})  # -0.9 is not in the causal output below
    sources = number_sources({"options": [{"value": -0.5}]}, {})
    assert_template_fallback(run(evidence, with_url(llm_cfg, fake(lambda p: draft)), rag_cfg, sources), evidence, rag_cfg, "NUMBER_MISMATCH")
    ok = run(evidence, with_url(llm_cfg, fake(lambda p: draft)), rag_cfg, number_sources({"options": [{"value": -0.9}]}, {}))
    assert ok["status"] == "SUCCESS" and ok["fallback"] is None  # the same draft passes when the number IS in the causal output


def test_an_unexpected_error_inside_the_provider_still_falls_back(monkeypatch, llm_cfg, evidence, rag_cfg):
    monkeypatch.setattr(ollama, "generate_draft", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert_template_fallback(run(evidence, llm_cfg, rag_cfg), evidence, rag_cfg, "UNEXPECTED_RUNTIMEERROR")


def test_a_fallback_never_contains_what_the_model_wrote_or_the_question(fake, llm_cfg, evidence, rag_cfg, caplog):
    caplog.set_level(logging.DEBUG)
    bad = json.dumps({"question_context": CANARY, "evidence_summary": [{"claim": CANARY, "chunk_ids": ["S99-00-00"]}], "limitations": CANARY})
    reply = run(evidence, with_url(llm_cfg, fake(lambda p: bad)), rag_cfg)
    reply2 = run(evidence, with_url(llm_cfg, fake(lambda p: CANARY + " not json")), rag_cfg)
    logged = " ".join(f"{r.getMessage()} {r.args}" for r in caplog.records)
    for text in (json.dumps(reply), json.dumps(reply2), logged):
        assert CANARY not in text  # nothing the model wrote is kept
    assert QUESTION not in logged  # (a template reply names the question it answers, as it always has; the log never does)


def test_the_fallback_is_the_same_template_that_the_tests_of_the_template_use(evidence, rag_cfg):
    from diacausal.llm.explain import explain

    assert template(QUESTION, evidence, rag_cfg)["sentences"] == explain(QUESTION, evidence, "template", rag_cfg)["sentences"]
