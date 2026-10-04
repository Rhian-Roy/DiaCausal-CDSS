"""Query processing (P16): normalise, expand abbreviations and brand names, split into at most 3 sub-queries; the
expansion feeds the keyword search only."""

import csv
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from diacausal.rag.index.bm25 import TOKEN  # noqa: E402
from diacausal.rag.ingest.licence_gate import CORPUS, ingest  # noqa: E402
from diacausal.rag.retrieve import query_processing as qp  # noqa: E402
from diacausal.rag.retrieve.hybrid import Retriever  # noqa: E402

KNOWLEDGE = ROOT / "knowledge_sources"


def rows(path):
    return list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))


def write(tmp_path, name, header, lines):
    path = tmp_path / name
    path.write_text(",".join(header) + "\n" + "\n".join(lines) + "\n", encoding="utf-8")
    return path


# ── normalise ────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("raw,expected", [
    ("  Can   SGLT2   inhibitors\tcause\nDKA? ", "can sglt2 inhibitors cause dka?"),
    ("SGLT‑2 and DPP–4", "sglt-2 and dpp-4"),  # non-breaking hyphen
    ("DPP–4–inhibitor", "dpp-4-inhibitor"),  # en dash
    ("ｅＧＦＲ ４５", "egfr 45"),  # full-width letters
    ("keto​acidosis", "ketoacidosis"),  # zero-width space
    ("", ""),
])
def test_normalise(raw, expected):
    assert qp.normalise(raw) == expected


# ── deterministic ────────────────────────────────────────────────────────────────────────────────────────────────
QUESTIONS = ["Can DKA happen with SGLT2i and what about UTI risk?", "Is eGFR 45 ok for DPP4i? Also hypoglycemia in SU users.",
             "zebra-test", "What is Fournier's gangrene and which diabetes medicines is it linked to?", "", "HbA1c a1c ASCVD CKD"]


@pytest.mark.parametrize("q", QUESTIONS)
def test_the_same_question_always_gives_the_same_plan(q):
    first = qp.process(q)
    assert all(qp.process(q) == first for _ in range(25))


def test_the_plan_does_not_depend_on_a_cached_table():
    q = "Can DKA happen with SGLT2i and what about UTI risk?"
    before = qp.process(q)
    qp.load_synonyms.cache_clear()
    qp.load_brands.cache_clear()
    assert qp.process(q) == before


def test_expansions_are_added_in_the_order_the_words_appear_in_the_question():
    plan = qp.process("uti and dka")
    assert plan.added.index("urinary tract infection") < plan.added.index("diabetic ketoacidosis")
    assert qp.process("dka and uti").added.index("diabetic ketoacidosis") < qp.process("dka and uti").added.index("urinary tract infection")


# ── unknown words pass through unchanged ─────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("q", ["zebra-test", "xylophone quartz", "Métformine rénale", "मधुमेह", "plain words only"])
def test_a_question_with_no_known_word_is_searched_exactly_as_written(q):
    plan = qp.process(q)
    assert plan.added == () and plan.equivalents == {}
    assert plan.sub_queries == (qp.normalise(q),) and plan.original == q


def test_unknown_words_stay_exactly_where_they_were_when_a_known_word_is_expanded():
    plan = qp.process("Does zebraword affect DKA in quartzland?")
    assert plan.sub_queries[0].startswith("does zebraword affect dka in quartzland?")  # nothing removed or reordered
    assert plan.added == ("diabetic ketoacidosis", "ketoacidosis")


def test_no_content_word_of_the_question_is_lost_by_expansion_or_splitting():
    """Splitting at "and" consumes the connective itself (a stop word the keyword search ignores anyway)."""
    from diacausal.rag.index.bm25 import tokens

    for q in QUESTIONS:
        assert set(tokens(qp.normalise(q))) <= set(tokens(" ".join(qp.process(q).sub_queries)))


# ── expansion ────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("q,must_add", [
    ("DKA", {"diabetic ketoacidosis", "ketoacidosis"}), ("eGFR 45", {"estimated glomerular filtration rate"}),
    ("SGLT2i", {"sglt2", "sglt-2", "inhibitors"}), ("DPP4i", {"dpp-4", "inhibitors"}),
    ("UTI", {"urinary tract infection", "urinary tract infections"}), ("hypoglycemia", {"hypoglycaemia"}),
    ("HF", {"heart failure"}), ("gliptin", {"dpp-4", "inhibitors"}), ("SGLT2", {"sglt-2"}), ("SGLT-2", {"sglt2"}),
])
def test_abbreviations_and_spelling_variants_are_expanded(q, must_add):
    assert must_add <= set(qp.process(q).added)


def test_a_term_that_is_already_in_the_question_is_not_added_again():
    assert qp.process("DKA diabetic ketoacidosis").added == ()  # both long forms are already there
    plan = qp.process("DKA and ketoacidosis")
    assert plan.added == ("diabetic ketoacidosis",)  # "ketoacidosis" is already there, the full phrase is not
    assert len(set(qp.process("DKA DKA dka").added)) == len(qp.process("DKA DKA dka").added)


def test_the_equivalents_say_which_question_word_each_expansion_belongs_to():
    plan = qp.process("DKA and SGLT2i")
    assert "ketoacidosis" in plan.equivalents["dka"] and "inhibitors" in plan.equivalents["sglt2i"]


def test_the_shipped_files_are_the_default_tables():
    assert qp.load_synonyms() == qp.load_synonyms(KNOWLEDGE / "query_synonyms.csv") and "dka" in qp.load_synonyms()


# ── the CSV files ────────────────────────────────────────────────────────────────────────────────────────────────
def test_both_files_have_a_source_column_filled_on_every_row():
    for name, columns in (("query_synonyms.csv", ["abbreviation", "expansion", "source", "status"]), ("brand_generic.csv", ["brand", "generic", "source", "status"])):
        data = rows(KNOWLEDGE / name)
        assert list(data[0]) == columns and data
        assert all(r["source"].strip() for r in data), name


def test_no_brand_name_is_written_in_the_brand_file_and_every_row_says_to_verify():
    data = rows(KNOWLEDGE / "brand_generic.csv")
    assert all(r["brand"] == "" and r["status"] == "TODO-VERIFY" and r["source"].startswith("TODO-VERIFY") for r in data)
    assert qp.load_brands(KNOWLEDGE / "brand_generic.csv") == {}  # so no brand is ever mapped today


def test_every_generic_in_the_brand_file_already_appears_in_the_repository():
    """A generic name is never invented either: each one is in the corpus, params.yaml or rules.csv."""
    known = " ".join(p.read_text(encoding="utf-8").lower() for p in [*CORPUS.glob("*.txt"), ROOT / "data/params.yaml", ROOT / "data/rules.csv"])
    for r in rows(KNOWLEDGE / "brand_generic.csv"):
        assert r["generic"] in known, r["generic"]


def test_each_synonym_status_tells_the_truth_about_the_corpus():
    vocab = {w for p in CORPUS.glob("*.txt") for w in TOKEN.findall(p.read_text(encoding="utf-8").lower())}
    for r in rows(KNOWLEDGE / "query_synonyms.csv"):
        needed = {t for term in r["expansion"].split(";") for t in TOKEN.findall(term.lower())}
        assert r["status"] in ("IN-CORPUS", "TEAM-SET"), r
        if r["status"] == "IN-CORPUS":
            assert needed <= vocab, f"{r['abbreviation']}: {sorted(needed - vocab)} is not in the corpus"
            assert all((ROOT / f.strip().removeprefix("knowledge_sources/corpus: ")).exists() or (CORPUS / f.strip()).exists()
                       for f in re.findall(r"[\w.]+\.txt", r["source"]) for _ in [0]) and ".txt" in r["source"]
        else:
            assert needed - vocab, f"{r['abbreviation']} is marked TEAM-SET but the corpus has all its words"


def test_synonym_keys_are_lower_case_and_unique_per_expansion():
    data = rows(KNOWLEDGE / "query_synonyms.csv")
    assert all(r["abbreviation"] == r["abbreviation"].lower() == r["abbreviation"].strip() for r in data)
    assert len({r["abbreviation"] for r in data}) == len(data)


# ── brand names: only checked rows ever apply (synthetic names only: no real brand is written anywhere) ─────────
def test_a_verified_brand_row_maps_the_brand_to_its_generic(tmp_path):
    path = write(tmp_path, "b.csv", ["brand", "generic", "source", "status"], ["examplebrandx,examplegeneric,TEST,VERIFIED"])
    brands = qp.load_brands(path)
    plan = qp.process("Is ExampleBrandX safe in CKD?", brands=brands)
    assert "examplegeneric" in plan.added and plan.sub_queries[0].startswith("is examplebrandx safe in ckd?")


def test_unverified_or_brandless_rows_are_ignored(tmp_path):
    path = write(tmp_path, "b.csv", ["brand", "generic", "source", "status"],
                 ["examplebrandy,examplegeneric,TEST,TODO-VERIFY", ",examplegeneric,TEST,VERIFIED", "examplebrandz,,TEST,VERIFIED",
                  "examplebrandw,examplegeneric,TEST,"])
    assert qp.load_brands(path) == {}
    assert qp.process("examplebrandy examplebrandz examplebrandw", brands={}).added == ()


def test_a_brand_with_two_generics_adds_both_in_file_order(tmp_path):
    path = write(tmp_path, "b.csv", ["brand", "generic", "source", "status"],
                 ["comboone,genericaa,TEST,VERIFIED", "comboone,genericbb,TEST,VERIFIED"])
    assert qp.process("comboone", brands=qp.load_brands(path)).added == ("genericaa", "genericbb")


def test_a_todo_verify_synonym_row_is_ignored_too(tmp_path):
    path = write(tmp_path, "s.csv", ["abbreviation", "expansion", "source", "status"], ["abc,alphabetical order,TEST,TODO-VERIFY", "xyz,last letters,TEST,TEAM-SET"])
    table = qp.load_synonyms(path)
    assert "abc" not in table and table["xyz"] == ("last letters",)


# ── splitting ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_two_independent_questions_become_two_sub_queries():
    plan = qp.process("Can SGLT2 inhibitors cause ketoacidosis? Is sitagliptin safe in heart failure?")
    assert len(plan.sub_queries) == 2 and plan.sub_queries[0].startswith("can sglt2 inhibitors cause ketoacidosis?")


def test_and_splits_only_when_both_halves_can_stand_alone():
    assert len(qp.process("Can SGLT2 inhibitors cause ketoacidosis and is sitagliptin safe in heart failure?").sub_queries) == 2
    assert len(qp.process("Can SGLT2 inhibitors cause ketoacidosis and UTI?").sub_queries) == 1  # "UTI" is too short to stand alone


def test_a_part_that_points_back_stays_with_the_part_before_it():
    """Found with the gold set (G40): split alone, "which medicines is it linked to?" lost Fournier's gangrene."""
    plan = qp.process("What is Fournier's gangrene and which diabetes medicines is it linked to?")
    assert len(plan.sub_queries) == 1
    plan = qp.process("What is Fournier's gangrene? Which diabetes medicines is it linked to?")
    assert len(plan.sub_queries) == 1


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 8, 20])
def test_there_are_never_more_than_three_sub_queries_and_nothing_is_dropped(n):
    text = " ".join(f"Question number {i} about metformin dosing? " for i in range(n)).replace("dosing", "kidneys")
    plan = qp.process(text)
    assert 1 <= len(plan.sub_queries) <= qp.MAX_SUB_QUERIES
    assert plan.sub_queries[-1].count("question number") == max(1, n - 2) if n > 3 else True
    words = TOKEN.findall(qp.normalise(text))
    assert set(words) <= set(TOKEN.findall(" ".join(plan.sub_queries)))
    assert sum(w == "number" for w in TOKEN.findall(" ".join(plan.sub_queries))) == n  # every question is in some part


def test_an_empty_question_gives_one_empty_sub_query():
    assert qp.process("   ").sub_queries == ("",)


# ── keyword search gets the expansion, vector search the original ───────────────────────────────────────────────
@pytest.fixture(scope="module")
def retriever():
    return Retriever(ingest())


def test_the_vector_search_gets_the_original_question_and_bm25_the_expanded_sub_queries(retriever, monkeypatch):
    from diacausal.rag.index import tfidf

    q = "Can DKA happen with SGLT2i? Is sitagliptin safe in heart failure?"
    plan = qp.process(q)
    seen_vector, seen_bm25 = [], []
    real_sim, real_scores = tfidf.similarities, retriever.bm25.scores
    monkeypatch.setattr(tfidf, "similarities", lambda v, m, question: (seen_vector.append(question), real_sim(v, m, question))[1])
    monkeypatch.setattr(retriever.bm25, "scores", lambda query: (seen_bm25.append(query), real_scores(query))[1])
    retriever.search(q, plan)
    assert seen_vector == [q]  # exactly as asked: not normalised, not expanded
    assert seen_bm25 == list(plan.sub_queries) and "diabetic ketoacidosis" in seen_bm25[0]
    assert all("diabetic" not in v for v in seen_vector)


def test_without_a_plan_or_with_a_plan_that_adds_nothing_the_search_is_the_one_it_always_was(retriever):
    q = "kidney function measure"  # nothing to expand and nothing to split
    plan = qp.process(q)
    assert plan.added == () and plan.sub_queries == (q,)
    assert retriever.search(q, plan) == retriever.search(q)
    assert retriever.search(q)["status"] == "SUCCESS"


def test_a_spelling_variant_only_adds_a_keyword_it_never_changes_the_question(retriever):
    q = "Can SGLT2 inhibitors cause ketoacidosis?"
    plan = qp.process(q)
    assert plan.added == ("sglt-2",) and plan.original == q
    assert retriever.search(q, plan)["question"] == q  # the reply is about the question as asked


def test_expansion_rescues_a_question_that_used_to_abstain(retriever):
    """Gold G29: "the gliptin" is not a word of the corpus; "dpp-4 inhibitors" is."""
    q = "What happened when patients with joint pain stopped the gliptin?"
    assert retriever.search(q)["status"] == "INSUFFICIENT_EVIDENCE"
    after = retriever.search(q, qp.process(q))
    assert after["status"] == "SUCCESS" and after["passages"][0]["citation"]["source_id"] == "S19"


def test_a_question_that_was_found_before_is_still_found_after(retriever):
    """Gold G40: splitting it would have lost the subject; it must still reach S22."""
    q = "What is Fournier's gangrene and which diabetes medicines is it linked to?"
    assert {p["citation"]["source_id"] for p in retriever.search(q, qp.process(q))["passages"]} == {p["citation"]["source_id"] for p in retriever.search(q)["passages"]}


def test_an_unknown_question_still_abstains(retriever):
    q = "zebra-test"
    assert retriever.search(q, qp.process(q))["status"] == "INSUFFICIENT_EVIDENCE"


def test_the_passage_scores_with_a_plan_still_have_the_same_fields(retriever):
    q = "Can DKA happen with SGLT2i?"
    p = retriever.search(q, qp.process(q))["passages"][0]
    assert set(p) == {"chunk_id", "text", "citation", "scores"} and set(p["scores"]) == {"bm25", "vector", "rrf"}


def test_every_gold_question_gets_a_plan_without_error():
    from diacausal.rag.evaluate import load_gold

    for g in load_gold():
        plan = qp.process(g["question"])
        assert 1 <= len(plan.sub_queries) <= 3 and plan.original == g["question"]
