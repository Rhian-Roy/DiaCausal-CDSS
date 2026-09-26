"""RAG early skeleton: licence gate, chunking, hybrid retrieval, abstention, no doses.

The corpus below is MADE-UP TEST TEXT, not a real guideline.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from diacausal_rag import INTENDED_USE  # noqa: E402
from diacausal_rag.ingest import CLEARED, CORPUS, LicenceError, chunk_document, ingest, load_config, load_sources, split_sections  # noqa: E402
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
    # with the default settings a dose question finds too little to answer: nothing is shown
    assert not any("mg" in p["text"] for p in retriever.search("dosing start once daily")["passages"])
    # and even when a dose passage is retrieved (coverage check off), its text is withheld
    loose = Retriever(retriever.chunks, {**retriever.cfg, "min_query_coverage": 0.0})
    out = loose.search("dosing start once daily")
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


def test_the_committed_corpus_holds_only_confirmed_licence_cleared_sources():
    """Every committed document maps to a cleared_ingest source whose licence a team member confirmed."""
    from diacausal_rag.ingest import is_confirmed

    sources = load_sources()
    chunks = ingest()
    assert chunks, "the corpus should hold the confirmed FDA communication (S08)"
    for c in chunks:
        assert c.licence_bucket == CLEARED and is_confirmed(sources[c.source_id]), c.chunk_id
    assert {c.source_id for c in chunks} <= {k for k, r in sources.items() if r["bucket"] == CLEARED and is_confirmed(r)}
    # WHO 2018 (S01) is in only because a team member confirmed its CC BY-NC-SA 3.0 IGO licence
    assert "S01" in {c.source_id for c in chunks} and is_confirmed(sources["S01"])
    assert "CC BY-NC-SA 3.0 IGO" in sources["S01"]["licence_as_found"]
    # every text file in the corpus folder is listed in the manifest (nothing slips in unlisted)
    listed = {row.split(",")[0] for row in (CORPUS / "manifest.csv").read_text().splitlines()[1:] if row}
    assert {f.name for f in CORPUS.glob("*.txt")} == listed
    # never ingested: IDF, ADA, NICE, KDIGO, RSSDI 2022 (cite only / excluded)
    assert not {c.source_id for c in chunks} & {"S03", "S09", "S10", "S11", "S12"}


def test_a_draft_licence_is_refused_even_in_the_cleared_bucket(tmp_path):
    (tmp_path / "doc.txt").write_text(DOC)
    (tmp_path / "manifest.csv").write_text("file,source_id\ndoc.txt,T1\n")
    with pytest.raises(LicenceError, match="still a draft"):
        ingest(tmp_path, sources={"T1": SRC | {"checked_by": "Claude (draft) — Member B to confirm"}})
    assert ingest(tmp_path, sources={"T1": SRC | {"checked_by": "Team member"}})


def test_sources_md_is_in_sync_with_the_licence_csv():
    from diacausal_rag.sources_table import OUT, render

    assert OUT.read_text(encoding="utf-8") == render(), "run: python -m diacausal_rag.sources_table"


def test_pdf_pages_become_corpus_text_with_page_markers_and_headings(tmp_path):
    """RAG step R2: an approved PDF becomes '[page N]' + '## heading' text that ingest.py reads."""
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib.backends.backend_pdf import PdfPages
    import matplotlib.pyplot as plt

    from diacausal_rag.pdf_text import pdf_to_corpus_text

    pdf = tmp_path / "doc.pdf"
    with PdfPages(pdf) as out:
        for lines in (["Contents", "1.1 Scope ........ 3"], ["1.1 Scope of the guideline", "Adults with type 2 diabetes-", "mellitus on metformin."],
                      ["3.1 Second-line treatment", "Add a sulfonylurea when metformin alone", "is not enough.", "7"]):
            fig = plt.figure()
            for i, ln in enumerate(lines):
                fig.text(0.1, 0.9 - 0.08 * i, ln)
            out.savefig(fig)
            plt.close(fig)
    text = pdf_to_corpus_text(pdf, 2, 3, r"^\d+\.\d+\s+[A-Z].*$")
    assert "Contents" not in text  # page 1 left out
    assert text.splitlines()[:2] == ["[page 2]", "## 1.1 Scope of the guideline"]
    assert "diabetes-mellitus" in text and "\n7\n" not in text  # hyphen joined; page number dropped
    sections = split_sections(text)
    assert [(s, p) for s, p, _ in sections] == [("1.1 Scope of the guideline", "2"), ("3.1 Second-line treatment", "3")]


def test_chunk_ids_are_unique_even_when_one_source_has_several_files():
    ids = [c.chunk_id for c in ingest()]
    assert len(ids) == len(set(ids))
