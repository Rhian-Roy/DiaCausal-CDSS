"""The pipeline runs the layers only through registry.py, in the order of plan 8.3, and the stubs are exactly the ones
listed (P14's "list the stubs" is a test, not a promise)."""

import ast
import logging
from pathlib import Path

import pytest
from pipeline_helpers import PRESETS, body

from diacausal import registry
from diacausal.orchestrator import layers

ROOT = Path(__file__).resolve().parents[2]


def test_the_layers_are_in_the_order_of_plan_8_3():
    assert [e.name for e in registry.LAYERS] == [
        "input guards", "rules", "causal engine", "retrieval", "explanation", "output guards", "formatter"]


def test_exactly_these_layers_and_parts_are_stubs_and_each_names_the_prompt_that_replaces_it():
    """The input guards left this list when P15 built them, query processing when P16 did, the prompt builder when P22 did, the full output checks when P23 did, the evidence levels when P24 did, the shap drivers when P25 did."""
    assert {e.name: e.replaced_by for e in registry.stubs()} == {}
    assert all(e.replaced_by for e in registry.stubs()) and not any(e.replaced_by for e in (*registry.LAYERS, *registry.PARTS) if not e.stub)


@pytest.mark.parametrize("entry", [*registry.LAYERS, *registry.PARTS], ids=lambda e: e.name)
def test_every_registered_function_resolves_to_a_callable(entry):
    fn = registry.layer_function(entry.name) if entry in registry.LAYERS else registry.part_function(entry.name)
    assert callable(fn)


def test_an_unknown_layer_is_an_error():
    with pytest.raises(KeyError):
        registry.layer_function("telepathy")


def test_the_pipeline_does_not_import_a_layer_directly():
    tree = ast.parse((ROOT / "diacausal/orchestrator/pipeline.py").read_text())
    imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert not imported & {"diacausal.orchestrator.layers", "diacausal.orchestrator.stubs"}
    assert "diacausal.registry" in imported or any(isinstance(n, ast.ImportFrom) and n.module == "diacausal" and
                                                    any(a.name == "registry" for a in n.names) for n in ast.walk(tree))


def test_every_layer_runs_inside_a_trace_even_when_swapped_for_another_function(client, trace, monkeypatch):
    """A layer replaced in the registry (as P15 will do) is traced like any other: nothing is wired by hand."""
    seen = []
    monkeypatch.setattr(layers, "input_guards_layer", lambda ctx: seen.append(ctx.request_id))
    patient, question = PRESETS["typical"]
    client.post("/api/v1/ask", json=body(patient, question, "swap1"))
    assert seen == ["swap1"]
    text = " ".join(r.getMessage() for r in trace.records if r.name == "diacausal.trace")
    assert "[swap1] passed input guards layer" in text and "STUB" not in text.split("rules layer")[0]


def test_an_input_guard_abstain_stops_the_request_before_the_rules_run(client, trace, monkeypatch):
    from diacausal.tracing import AbstainSignal

    def blocked(ctx):
        raise AbstainSignal("OUT_OF_SCOPE")

    monkeypatch.setattr(layers, "input_guards_layer", blocked)
    patient, question = PRESETS["typical"]
    r = client.post("/api/v1/ask", json=body(patient, question, "stop1"))
    assert r.status_code == 422 and r.json()["message"]
    text = " ".join(r.getMessage() for r in trace.records if r.name == "diacausal.trace")
    assert "abstained input guards layer reason=OUT_OF_SCOPE" in text and "rules layer" not in text


def test_the_evidence_index_version_is_the_corpus_fingerprint_the_website_records():
    import json

    from diacausal.orchestrator.layers import _corpus_sha

    web = json.loads((ROOT / "web/evidence.json").read_text())
    assert _corpus_sha() == web["versions"]["corpus_sha"]


def test_every_passage_carries_a_chunk_id_that_the_card_cites(client):
    from diacausal.api.schemas import AnswerCardV1
    from diacausal.orchestrator.layers import get_retriever

    passages = get_retriever().search("Can SGLT2 inhibitors cause ketoacidosis?")["passages"]
    assert passages and all(p["chunk_id"] for p in passages)
    patient, question = PRESETS["typical"]
    card = AnswerCardV1.model_validate(client.post("/api/v1/ask", json=body(patient, question)).json())
    cited = {c.chunk_id for claim in card.claims for c in claim.citations}
    assert cited and cited <= {p["chunk_id"] for p in passages}
