"""Source-aware ranking (P19): the five-key order, the source tiers, the latest-version rule, the top-20 fusion, the train /
held-out split, tuning on train only, and the before / after results. No model is downloaded: the dense part uses a stand-in."""

import csv
import hashlib
import re
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from diacausal.rag import evaluate as ev  # noqa: E402
from diacausal.rag.index import dense  # noqa: E402
from diacausal.rag.ingest.licence_gate import ingest, load_sources  # noqa: E402
from diacausal.rag.retrieve import query_processing as qp  # noqa: E402
from diacausal.rag.retrieve import ranking  # noqa: E402
from diacausal.rag.retrieve.hybrid import Retriever, index_text  # noqa: E402
from test_dense import GOLDEN, StandInEmbedder  # noqa: E402

CFG = ranking.load_ranking_config()
SOURCES_CSV = ROOT / "knowledge_sources" / "sources.csv"
TIERS = {"1", "2", "3", "4", "UNKNOWN"}
INDIA = {"india", "global", "other_country", "unknown"}


@pytest.fixture(scope="module")
def chunks():
    return ingest()


def info(tier, india, section=(), text=(), superseded=None):
    n = len(tier)
    return ranking.ChunkInfo(tier=list(tier), india=list(india), section_words=[set(s) for s in (section or [()] * n)],
                             text_lower=list(text or [""] * n), superseded=list(superseded or [False] * n))


def settings(**over):
    return {**CFG, "enabled": True, **over}


# ── the switch ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_ranking_is_off_by_default_and_the_retriever_has_no_ranking(chunks):
    assert CFG["enabled"] is False and ranking.for_retriever() is None and Retriever(chunks).ranking is None
    assert ranking.for_retriever({**CFG, "enabled": True})["top_n"] == 20


def test_every_entry_of_ranking_yaml_has_a_source_and_a_status():
    import yaml

    raw = yaml.safe_load((ROOT / "diacausal/rag/ranking.yaml").read_text(encoding="utf-8"))
    assert all(e.get("source") and e.get("status") in ("CITED", "ASSUMED-DIRECTIONAL", "TEAM-SET") for e in raw.values())
    assert CFG["top_n"] == 20 and CFG["latest_version_only"] is True and CFG["fusion_round_decimals"] in (None, 4, 3, 2)


def test_the_website_does_not_know_about_the_ranking():
    for js in (ROOT / "web").glob("*.js"):
        assert "ranking.yaml" not in js.read_text(encoding="utf-8") and "authority_tier" not in js.read_text(encoding="utf-8"), js.name
    assert "authority_tier" not in (ROOT / "web" / "evidence.json").read_text(encoding="utf-8")


# ── sources.csv: the two new columns ─────────────────────────────────────────────────────────────────────────────
def test_every_source_has_a_tier_and_an_india_value_from_the_allowed_lists():
    rows = list(csv.DictReader(SOURCES_CSV.read_text(encoding="utf-8").splitlines()))
    assert len(rows) == 31 and list(rows[0])[-2:] == ["authority_tier", "india_relevance"]
    assert {r["authority_tier"] for r in rows} <= TIERS and {r["india_relevance"] for r in rows} <= INDIA
    assert set(CFG["authority_tier_order"]) == TIERS and set(CFG["india_order"]) == INDIA


def test_the_new_columns_changed_no_existing_cell():
    import io
    import subprocess

    old = subprocess.run(["git", "show", "origin/main:knowledge_sources/sources.csv"], cwd=ROOT, capture_output=True, text=True)
    if old.returncode != 0:
        pytest.skip("origin/main is not available")
    before = list(csv.reader(io.StringIO(old.stdout, newline="")))
    after = list(csv.reader(io.StringIO(SOURCES_CSV.read_text(encoding="utf-8"), newline="")))
    if len(before[0]) == len(after[0]):
        pytest.skip("origin/main already has the columns")
    assert [r[:-2] for r in after] == before


def test_the_sources_that_can_be_returned_have_the_values_the_issuer_implies():
    s = load_sources()
    assert (s["S01"]["authority_tier"], s["S01"]["india_relevance"]) == ("1", "global")  # WHO guideline
    for sid in ("S08", "S19", "S20", "S21", "S22", "S23"):  # FDA drug safety communications
        assert (s[sid]["authority_tier"], s[sid]["india_relevance"]) == ("2", "other_country"), sid
    for sid in ("S02", "S03", "S04", "S05"):  # Indian guidelines
        assert (s[sid]["authority_tier"], s[sid]["india_relevance"]) == ("1", "india"), sid
    for sid in ("X03", "RP01", "RP05"):  # not known: marked, never guessed
        assert s[sid]["authority_tier"] == "UNKNOWN" and s[sid]["india_relevance"] == "unknown", sid
    assert {c.source_id for c in ingest()} <= {sid for sid, r in s.items() if r["authority_tier"] != "UNKNOWN"}


def test_the_generated_licence_table_shows_the_new_columns():
    text = (ROOT / "docs" / "SOURCES.md").read_text(encoding="utf-8")
    assert "Authority tier" in text and "India relevance" in text


# ── the latest version of each source ────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("text,key", [("2015-08-28", (2015, 8, 28)), ("2016", (2016, 0, 0)), ("2018 (ISBN 978-92-4-155028-4)", (2018, 0, 0)),
                                      ("2020; Indian J Endocrinol", (2020, 0, 0)), ("current", None), ("living", None), ("", None), ("—", None)])
def test_version_key_reads_the_date_or_year_at_the_start(text, key):
    assert ranking.version_key(text) == key


def src(issuer, title, version):
    return {"issuer": issuer, "title": title, "version": version}


def test_only_the_newest_version_of_a_document_stays():
    sources = {"A1": src("WHO", "Guideline X", "2018"), "A2": src("WHO", "Guideline X", "2022"), "A3": src("WHO", "Guideline X", "2020"),
               "B1": src("US FDA", "Communication Y", "2015-08-28"), "C1": src("RSSDI", "Recommendations", "2020"),
               "C2": src("RSSDI", "Other recommendations", "2022")}
    assert ranking.superseded_sources(sources) == {"A1", "A3"}  # A2 is newest; different titles are different documents


def test_a_family_whose_versions_cannot_be_compared_is_left_alone():
    assert ranking.superseded_sources({"A": src("WHO", "Same", "2018"), "B": src("WHO", "Same", "current")}) == set()
    assert ranking.superseded_sources({"A": src("WHO", "Same", "2018"), "B": src("WHO", "Same", "2018")}) == set()  # equal: nothing to drop


def test_the_family_is_found_whatever_the_case_and_spacing():
    assert ranking.superseded_sources({"A": src("US  FDA", "Drug  Safety", "2015"), "B": src("us fda", "drug safety", "2016")}) == {"A"}


def test_the_real_register_has_no_two_versions_of_a_document_so_nothing_is_dropped():
    assert ranking.superseded_sources(load_sources()) == set()


def test_a_superseded_source_is_not_returned_by_the_retriever(chunks):
    r = Retriever(chunks)
    r.ranking = settings()
    sources = load_sources()
    sources["S23"] = {**sources["S23"], "title": sources["S19"]["title"], "issuer": sources["S19"]["issuer"]}  # S19 (2015) is older than S23 (2020)
    r._info, r._info_for = ranking.build_info(chunks, sources, r.ranking, r._texts), r.ranking
    shown = {p["citation"]["source_id"] for g in GOLDEN for p in r.search(g["question"])["passages"]}
    assert "S19" not in shown, "an older version of the same document must never be returned"
    r2 = Retriever(chunks)
    r2.ranking = settings(latest_version_only=False)
    assert "S19" in {p["citation"]["source_id"] for g in GOLDEN for p in r2.search(g["question"])["passages"]}


# ── the five keys, one at a time ─────────────────────────────────────────────────────────────────────────────────
def test_the_fusion_score_decides_first():
    fused = {0: 0.030, 1: 0.020}
    i = info(tier=[3, 0], india=[3, 0], section=[{"a"}, {}], text=["", ""])
    assert ranking.order([0, 1], fused, i, {"a"}, [], settings(fusion_round_decimals=None)) == [0, 1]  # better score wins over every other key


def test_when_the_fusion_score_ties_the_authority_tier_decides():
    fused = {0: 0.02, 1: 0.02}
    assert ranking.order([0, 1], fused, info(tier=[1, 0], india=[0, 1]), set(), [], settings()) == [1, 0]


def test_when_fusion_and_tier_tie_the_india_relevance_decides():
    fused = {0: 0.02, 1: 0.02}
    assert ranking.order([0, 1], fused, info(tier=[1, 1], india=[2, 0], section=[{"a"}, set()]), {"a"}, [], settings()) == [1, 0]


def test_when_the_first_three_tie_the_section_match_decides():
    fused = {0: 0.02, 1: 0.02}
    i = info(tier=[1, 1], india=[0, 0], section=[{"kidney"}, {"kidney", "metformin"}], text=["pancreatitis", ""])
    assert ranking.order([0, 1], fused, i, {"kidney", "metformin"}, ["past_pancreatitis"], settings()) == [1, 0]


def test_when_the_first_four_tie_the_patient_condition_decides():
    fused = {0: 0.02, 1: 0.02}
    i = info(tier=[1, 1], india=[0, 0], section=[{"a"}, {"a"}], text=["nothing here", "a past pancreatitis case"])
    assert ranking.order([0, 1], fused, i, {"a"}, ["past_pancreatitis"], settings()) == [1, 0]
    assert ranking.order([0, 1], fused, i, {"a"}, [], settings()) == [0, 1]  # no condition given: the key is inert, position decides


def test_the_keys_are_compared_in_the_stated_order_not_added_up():
    """A better LATER key never beats a better EARLIER one."""
    fused = {0: 0.02, 1: 0.02}
    i = info(tier=[0, 1], india=[1, 0], section=[set(), {"a", "b", "c"}], text=["pancreatitis", ""])
    assert ranking.order([0, 1], fused, i, {"a", "b", "c"}, ["past_pancreatitis"], settings()) == [0, 1]


def test_rounding_makes_near_equal_fusion_scores_tie_so_the_other_keys_can_decide():
    fused = {0: 0.01639, 1: 0.01613}  # ranks 1 and 2 of one ranking: 1/61 and 1/62
    i = info(tier=[1, 0], india=[0, 0])
    assert ranking.order([0, 1], fused, i, set(), [], settings(fusion_round_decimals=None)) == [0, 1]
    assert ranking.order([0, 1], fused, i, set(), [], settings(fusion_round_decimals=4)) == [0, 1]
    assert ranking.order([0, 1], fused, i, set(), [], settings(fusion_round_decimals=3)) == [1, 0]  # both round to 0.016: the tier decides


def test_a_full_tie_is_broken_by_the_exact_score_then_the_position():
    i = info(tier=[0, 0, 0], india=[0, 0, 0])
    assert ranking.order([0, 1, 2], {0: 0.0200, 1: 0.0201, 2: 0.0200}, i, set(), [], settings(fusion_round_decimals=2)) == [1, 0, 2]


def test_an_unknown_value_ranks_after_every_known_one():
    s = {"A": {"authority_tier": "2", "india_relevance": "other_country"}, "B": {"authority_tier": "UNKNOWN", "india_relevance": "unknown"},
         "C": {"authority_tier": "weird", "india_relevance": "weird"}}
    chunk = lambda sid: type("C", (), {"source_id": sid, "section": "s"})()  # noqa: E731
    built = ranking.build_info([chunk("A"), chunk("B"), chunk("C"), chunk("Z")], s, CFG, ["", "", "", ""])
    assert built.tier[0] < built.tier[1] < built.tier[2] and built.india[0] < built.india[1] < built.india[2]
    assert built.tier[3] == built.tier[1] and built.india[3] == built.india[1]  # a source that is not in the register counts as unknown


def test_section_match_counts_the_question_words_in_the_section_title():
    assert ranking.section_match({"kidney", "function"}, {"kidney", "function", "tests"}) == 2
    assert ranking.section_match({"kidney"}, {"safety", "announcement"}) == 0 and ranking.section_match(set(), {"a"}) == 0


def test_condition_match_counts_the_patients_conditions_the_passage_mentions():
    kw = CFG["condition_keywords"]
    text = "reduced kidney function and a history of pancreatitis; heart failure was seen"
    assert ranking.condition_match(["ckd", "past_pancreatitis", "heart_failure", "past_dka"], text, kw) == 3
    assert ranking.condition_match(["ckd", "ckd"], text, kw) == 1 and ranking.condition_match([], text, kw) == 0
    assert ranking.condition_match(["not_a_condition"], text, kw) == 0


def test_patient_conditions_come_from_the_yes_no_fields_of_the_form():
    from diacausal.api.schemas import PatientV1

    base = dict(age=52, sex="M", duration_years=5.0, hba1c_pct=8.4, egfr=88.0, bmi=27.0, ascvd=False, heart_failure=False, ckd=False,
                past_hypo=False, past_dka=False, past_pancreatitis=False, type1=False, on_metformin=True)
    assert ranking.patient_conditions(PatientV1(**base)) == []
    assert ranking.patient_conditions(PatientV1(**{**base, "ckd": True, "past_pancreatitis": True})) == ["ckd", "past_pancreatitis"]
    assert set(CFG["condition_keywords"]) == {"ckd", "heart_failure", "ascvd", "past_pancreatitis", "past_hypo", "past_dka"}


# ── inside the retriever ─────────────────────────────────────────────────────────────────────────────────────────
def test_ranking_never_changes_whether_the_system_abstains_nor_adds_candidates(chunks):
    off, on = Retriever(chunks), Retriever(chunks)
    on.ranking = settings()
    for item in GOLDEN:
        for plan in (None, qp.process(item["question"])):
            a, b = off.search(item["question"], plan), on.search(item["question"], plan)
            assert (a["status"], a.get("reason")) == (b["status"], b.get("reason")), item["question"]
            for p in b["passages"]:
                assert p["scores"]["bm25"] > 0 or p["scores"]["vector"] > 0


def test_with_everything_tied_the_returned_order_follows_the_tuple(chunks):
    r = Retriever(chunks)
    r.ranking = settings(fusion_round_decimals=0)  # every fusion score rounds to 0: the other keys decide alone
    meta = ranking.build_info(chunks, load_sources(), r.ranking, r._texts)
    position = {c.chunk_id: i for i, c in enumerate(chunks)}
    q = "metformin kidney function eGFR"
    plan = qp.process(q)
    asked = set(__import__("diacausal.rag.index.bm25", fromlist=["x"]).tokens(q)) | set(__import__("diacausal.rag.index.bm25", fromlist=["x"]).tokens(" ".join(plan.added)))
    keys = [(meta.tier[position[p["chunk_id"]]], meta.india[position[p["chunk_id"]]], -ranking.section_match(asked, meta.section_words[position[p["chunk_id"]]]))
            for p in r.search(q, plan, ["ckd"])["passages"]]
    assert len(keys) == 5 and keys == sorted(keys)


def test_the_patients_conditions_reach_the_order_only_when_ranking_is_on(chunks):
    q = "Is a DPP-4 inhibitor safe?"
    off = Retriever(chunks)
    assert off.search(q, None, ["past_pancreatitis"]) == off.search(q)  # ranking off: conditions are ignored
    on = Retriever(chunks)
    on.ranking = settings(fusion_round_decimals=0)
    a, b = on.search(q, None, ["past_pancreatitis"])["passages"], on.search(q)["passages"]
    mentions = lambda ps: sum("pancreatitis" in p["text"].lower() for p in ps)  # noqa: E731
    assert mentions(a) >= mentions(b)


def test_only_the_top_twenty_of_each_keyword_ranking_enter_the_fusion(chunks, monkeypatch):
    from diacausal.rag.retrieve import hybrid

    seen = []
    real = hybrid.rrf
    monkeypatch.setattr(hybrid, "rrf", lambda rankings, k: (seen.append([len(r) for r in rankings]), real(rankings, k))[1])
    r = Retriever(chunks)
    r.ranking = settings()
    r.search("Can SGLT2 inhibitors cause ketoacidosis?")
    assert seen[-1] == [20, len(chunks)], "BM25 contributes its top 20, TF-IDF its full ranking"
    r.ranking = None
    r.search("Can SGLT2 inhibitors cause ketoacidosis?")
    assert seen[-1] == [len(chunks), len(chunks)]  # off: the old fusion, untouched


def test_dense_top_twenty_joins_the_fusion_when_dense_is_on(chunks, tmp_path, monkeypatch):
    from diacausal.rag.retrieve import hybrid

    cfg = dense.load_dense_config()
    ids, texts = [c.chunk_id for c in chunks], [index_text(c.text) for c in chunks]
    dense.build(ids, texts, cfg, "bge-small-en-v1.5", embedder=StandInEmbedder(), root=tmp_path)
    seen = []
    real = hybrid.rrf
    monkeypatch.setattr(hybrid, "rrf", lambda rankings, k: (seen.append([len(r) for r in rankings]), real(rankings, k))[1])
    r = Retriever(chunks)
    r.dense = dense.load(ids, texts, cfg, "bge-small-en-v1.5", embedder=StandInEmbedder(), root=tmp_path)
    r.ranking = settings()
    res = r.search("Can SGLT2 inhibitors cause ketoacidosis?")
    assert seen[-1] == [20, 20, len(chunks)] and all("dense" in p["scores"] for p in res["passages"])
    for item in GOLDEN:  # and abstention still does not move
        assert r.search(item["question"])["status"] == Retriever(chunks).search(item["question"])["status"]


def test_rrf_k_is_the_sixty_of_the_retrievers_settings(chunks):
    assert Retriever(chunks).cfg["rrf_k"] == 60


def test_the_pipeline_passes_the_patients_conditions_to_the_search(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    from diacausal.api.main import create_app
    from diacausal.causal_inference.recommend import get_engine
    from diacausal.rag.retrieve import hybrid

    seen = []
    real = hybrid.Retriever.search
    monkeypatch.setattr(hybrid.Retriever, "search", lambda self, q, plan=None, conditions=None: (seen.append(conditions), real(self, q, plan, conditions))[1])
    monkeypatch.setattr("diacausal.causal_inference.recommend.AUDIT_PATH", tmp_path / "a.jsonl")
    patient = dict(age=60, sex="F", duration_years=8.0, hba1c_pct=8.2, egfr=40.0, bmi=25.5, ascvd=False, heart_failure=False, ckd=True,
                   past_hypo=False, past_dka=False, past_pancreatitis=True, type1=False, on_metformin=True)
    with TestClient(create_app(get_engine())) as client:
        r = client.post("/api/v1/ask", json={"schema_version": "1.0", "request_id": "cond1", "patient": patient, "question": "Is a DPP-4 inhibitor safe?"})
    assert r.status_code == 200 and seen and seen[-1] == ["ckd", "past_pancreatitis"]


# ── the split, the tuning and the results ────────────────────────────────────────────────────────────────────────
def test_the_split_is_seeded_disjoint_complete_and_stratified():
    gold = ev.load_gold()
    train, held = ev.split_gold_full(gold, CFG["split_seed"], CFG["split_heldout_fraction"])
    assert len(train) + len(held) == 60 and not {g["id"] for g in train} & {g["id"] for g in held}
    assert (train, held) == ev.split_gold_full(gold, CFG["split_seed"], CFG["split_heldout_fraction"])
    assert held != ev.split_gold_full(gold, 7, CFG["split_heldout_fraction"])[1]
    for category in ("answerable", "out_of_scope", "dose"):
        assert any(g["category"] == category for g in held) and any(g["category"] == category for g in train)
    assert (len(held), sum(g["category"] == "answerable" for g in held)) == (20, 15)
    assert [g["id"] for g in train] == [g["id"] for g in gold if g["id"] in {t["id"] for t in train}]  # the file's order
    assert {g["expected_source"] for g in held if g["category"] == "answerable"} >= {"S01", "S08", "S20"}


def test_the_split_is_not_the_one_of_the_dense_evaluation():
    dev, held = ev.split_gold(ev.load_gold(), 2026, 0.34)
    train, held2 = ev.split_gold_full(ev.load_gold(), CFG["split_seed"], CFG["split_heldout_fraction"])
    assert {g["id"] for g in held} != {g["id"] for g in held2 if g["category"] == "answerable"}


def test_tuning_reads_the_train_questions_only(monkeypatch):
    gold = ev.load_gold()
    train, held = ev.split_gold_full(gold, CFG["split_seed"], CFG["split_heldout_fraction"])
    seen = []
    real = ev.ranking_question_rows
    monkeypatch.setattr(ev, "ranking_question_rows", lambda r, qs: (seen.extend(g["id"] for g in qs), real(r, qs))[1])
    ev.ranking_tune()
    assert seen and set(seen) == {g["id"] for g in train} and not set(seen) & {g["id"] for g in held}


def test_the_chosen_rounding_is_what_the_tuning_picks_on_train():
    rows, best = ev.ranking_tune()
    assert best == CFG["fusion_round_decimals"], "ranking.yaml must hold the value chosen on the train split"
    saved = list(csv.DictReader((ROOT / "results/rag_ranking_tuning.csv").read_text().splitlines()))
    assert [r["chosen"] for r in saved].count("1") == 1
    for mine, theirs in zip(rows, saved):
        assert str(mine["fusion_round_decimals"]) == theirs["fusion_round_decimals"] and mine["train_ndcg_at_5"] == pytest.approx(float(theirs["train_ndcg_at_5"]), abs=5e-5)


def test_the_committed_before_and_after_rows_are_reproduced_live_without_a_model():
    saved = list(csv.DictReader((ROOT / "results/rag_ranking_eval.csv").read_text().splitlines()))
    assert list(saved[0]) == ["split", "variant", "metric", "mean", "n"]
    assert {r["variant"] for r in saved} == {"before", "after", "after+dense:bge-small-en-v1.5", "after+dense:pubmedbert-base-embeddings"}
    chunks, rcfg = ingest(), ev.load_rag_config()
    train, held = ev.split_gold_full(ev.load_gold(), CFG["split_seed"], CFG["split_heldout_fraction"])
    for variant, rk in (("before", None), ("after", CFG)):
        r = ev.ranking_retriever(chunks, rcfg, rk)
        for split, qs in {"train": train, "heldout": held, "all": train + held}.items():
            rows = ev.ranking_question_rows(r, qs)
            for metric in ("recall_at_5", "mrr", "ndcg_at_5"):
                want = next(float(x["mean"]) for x in saved if (x["split"], x["variant"], x["metric"]) == (split, variant, metric))
                assert want == pytest.approx(ev._mean(rows, metric)[0], abs=5e-5), (variant, split, metric)


def test_before_and_after_agree_on_abstention_and_dose_leaks_and_the_paired_numbers_add_up():
    saved = list(csv.DictReader((ROOT / "results/rag_ranking_eval.csv").read_text().splitlines()))
    paired = list(csv.DictReader((ROOT / "results/rag_ranking_paired.csv").read_text().splitlines()))
    value = lambda split, variant, metric: float(next(r["mean"] for r in saved if (r["split"], r["variant"], r["metric"]) == (split, variant, metric)))  # noqa: E731
    for split in ("train", "heldout", "all"):
        for variant in {r["variant"] for r in saved} - {"before"}:
            assert value(split, variant, "abstention_accuracy") == value(split, "before", "abstention_accuracy")  # ranking never changes abstention
            assert value(split, variant, "dose_leaks") == 0 and value(split, "before", "dose_leaks") == 0
    for p in paired:
        assert int(p["wins"]) + int(p["losses"]) + int(p["ties"]) == int(p["n"])
        if p["metric"] in ("recall_at_5", "mrr", "ndcg_at_5"):
            assert float(p["diff"]) == pytest.approx(value(p["split"], p["variant"], p["metric"]) - value(p["split"], "before", p["metric"]), abs=1e-3)


def test_the_ablation_runs_end_to_end_with_stand_in_embedders(tmp_path, monkeypatch):
    cfg = dense.load_dense_config()
    chunks = ingest()
    ids, texts = [c.chunk_id for c in chunks], [index_text(c.text) for c in chunks]
    for key in cfg["models"]:
        dense.build(ids, texts, cfg, key, embedder=StandInEmbedder(), root=tmp_path)
    monkeypatch.setattr(dense, "INDEX_ROOT", tmp_path)
    rows, paired = ev.ranking_ablation(embedders={k: StandInEmbedder() for k in cfg["models"]})
    assert len(rows) == 3 * 4 * 5 and len(paired) == 3 * 3 * 4
    assert {r["split"] for r in rows} == {"train", "heldout", "all"} and all(0 <= r["mean"] <= max(1.0, r["n"]) for r in rows)
