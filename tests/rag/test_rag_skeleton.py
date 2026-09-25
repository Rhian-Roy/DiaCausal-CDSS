"""RAG early skeleton: licence gate, chunking, hybrid retrieval, abstention, no doses.

The corpus below is MADE-UP TEST TEXT, not a real guideline.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from diacausal_rag import INTENDED_USE  # noqa: E402
from diacausal_rag.ingest import CLEARED, LicenceError, chunk_document, ingest, load_config, load_sources, split_sections  # noqa: E402
from diacausal_rag.retrieve import WITHHELD, Retriever, rrf  # noqa: E402

DOC = """[page 1]
## Choosing a second medicine
Test text. When metformin alone does not control glucose, a second oral medicine can be added.
Sulfonylureas, DPP-4 inhibitors and SGLT2 inhibitors are options discussed with the patient.
[page 2]
## Kidney function
Test text. Kidney function measured as eGFR affects how well SGLT2 inhibitors lower glucose.
## Hypoglycaemia
Test text. Sulfonylureas carry a higher risk of hypoglycaemia than DPP-4 inhibitors.
## Dosing
Test text. Start at 1 mg once daily.
"""
SRC = {"id": "T1", "title": "Made-up test guideline", "version": "test", "bucket": CLEARED}


@pytest.fixture(scope="module")
def retriever():
    return Retriever(chunk_document(DOC, SRC, chunk_words=400))


def test_only_licence_cleared_sources_are_ingested():
    with pytest.raises(LicenceError, match="not 'cleared_ingest'"):
        chunk_document(DOC, SRC | {"id": "T2", "bucket": "cite_only"}, 400)


def test_the_real_licence_table_refuses_idf_and_admits_who():
    sources = load_sources()
    assert sources["S01"]["bucket"] == CLEARED  # WHO 2018
    for sid in ("S11", "S12", "S10", "X02"):  # IDF 2025, ADA, NICE, excluded article
        with pytest.raises(LicenceError):
            chunk_document(DOC, sources[sid], 400)


def test_sections_are_never_mixed_and_carry_their_page():
    secs = split_sections(DOC)
    assert [s[0] for s in secs] == ["Choosing a second medicine", "Kidney function", "Hypoglycaemia", "Dosing"]
    assert [s[1] for s in secs] == ["1", "2", "2", "2"]


def test_long_sections_are_cut_to_the_chunk_size():
    long_doc = "## A\n" + " ".join(["word"] * 900)
    chunks = chunk_document(long_doc, SRC, chunk_words=400)
    assert [len(c.text.split()) for c in chunks] == [400, 400, 100]
    assert all(c.section == "A" and c.source_id == "T1" for c in chunks)


def test_hybrid_search_finds_the_right_section_with_a_citation(retriever):
    out = retriever.search("How does eGFR affect SGLT2 inhibitors?")
    assert out["status"] == "SUCCESS" and out["intended_use"] == INTENDED_USE
    top = out["passages"][0]
    assert top["citation"]["section"] == "Kidney function" and top["citation"]["page"] == "2"
    assert set(top["scores"]) == {"bm25", "vector", "rrf"}


def test_unsupported_questions_get_insufficient_evidence(retriever):
    out = retriever.search("What is the capital of France?")
    assert out["status"] == "INSUFFICIENT_EVIDENCE" and out["passages"] == []


def test_passages_with_dose_text_are_withheld(retriever):
    out = retriever.search("dosing start once daily")
    texts = [p["text"] for p in out["passages"]]
    assert WITHHELD in texts and not any("mg" in t for t in texts)


def test_empty_index_abstains():
    assert Retriever([]).search("anything")["status"] == "INSUFFICIENT_EVIDENCE"


def test_reciprocal_rank_fusion_rewards_agreement():
    fused = rrf([[0, 1, 2], [1, 0, 2]], k=60)
    assert fused[0] == fused[1] > fused[2]


def test_config_numbers_are_sourced():
    cfg = load_config()
    assert cfg["chunk_words"] == 400 and cfg["top_k"] == 5 and cfg["rrf_k"] == 60


def test_the_committed_corpus_is_empty_until_licences_are_confirmed():
    assert ingest() == []


def test_sources_md_is_in_sync_with_the_licence_csv():
    from diacausal_rag.sources_table import OUT, render

    assert OUT.read_text(encoding="utf-8") == render(), "run: python -m diacausal_rag.sources_table"
