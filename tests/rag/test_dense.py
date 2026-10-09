"""Dense search (P18): off by default and then identical to before; one more ranking in the fusion when on; a saved,
checked index; no dose text embedded; the website untouched; and the retrieval metrics of the with / without comparison.

CI downloads no model: these tests use a small deterministic stand-in embedder (hashed bag of words). The tests that need the
real models are skipped unless sentence-transformers and the downloaded models are present."""

import hashlib
import inspect
import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from diacausal.rag import evaluate as ev  # noqa: E402
from diacausal.rag.index import dense  # noqa: E402
from diacausal.rag.ingest.licence_gate import ingest  # noqa: E402
from diacausal.rag.retrieve import query_processing as qp  # noqa: E402
from diacausal.rag.retrieve.hybrid import DOSE, Retriever, index_text  # noqa: E402

GOLDEN = json.loads((Path(__file__).parent / "golden_search.json").read_text(encoding="utf-8"))
DIM = 64


class StandInEmbedder:
    """A hashed bag of words, L2-normalised: deterministic, no model. Records every text it is asked to embed."""

    def __init__(self, dim: int = DIM):
        self.dim, self.seen = dim, []

    def _vector(self, text: str) -> np.ndarray:
        v = np.zeros(self.dim, dtype=np.float32)
        for word in re.findall(r"[a-z0-9]+", text.lower()):
            v[int(hashlib.sha256(word.encode()).hexdigest(), 16) % self.dim] += 1.0
        n = np.linalg.norm(v)
        return v / n if n else v

    def embed_passages(self, texts):
        self.seen.extend(texts)
        return np.stack([self._vector(t) for t in texts])

    def embed_query(self, text):
        return self._vector(text)


@pytest.fixture(scope="module")
def chunks():
    return ingest()


@pytest.fixture(scope="module")
def ids_texts(chunks):
    return [c.chunk_id for c in chunks], [index_text(c.text) for c in chunks]


@pytest.fixture(scope="module")
def cfg():
    return dense.load_dense_config()


@pytest.fixture(scope="module")
def built(tmp_path_factory, ids_texts, cfg):
    """A stand-in index per model key in a temporary folder."""
    root = tmp_path_factory.mktemp("dense")
    ids, texts = ids_texts
    for key in cfg["models"]:
        dense.build(ids, texts, cfg, key, embedder=StandInEmbedder(), root=root, today="2026-10-09")
    return root


def retriever_on(chunks, ids_texts, cfg, root, key="bge-small-en-v1.5", embedder=None):
    r = Retriever(chunks)
    ids, texts = ids_texts
    r.dense = dense.load(ids, texts, cfg, key, embedder=embedder or StandInEmbedder(), root=root)
    return r


def compact(res):
    return {"status": res["status"], "reason": res.get("reason"), "passages": [
        {"chunk_id": p["chunk_id"], "text_sha": hashlib.sha256(p["text"].encode()).hexdigest()[:16], "citation": p["citation"],
         "scores": p["scores"]} for p in res["passages"]]}


def first_difference(a, b, path=""):
    """Where two JSON trees differ: the same keys, lengths and strings; numbers equal to 1e-12 (relative), because the last
    digit of a float differs between platforms (the same rule as tests/web)."""
    import math

    if isinstance(a, dict) and isinstance(b, dict):
        if a.keys() != b.keys():
            return f"{path}: keys differ"
        return next((d for k in a if (d := first_difference(a[k], b[k], f"{path}.{k}"))), None)
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return f"{path}: {len(a)} vs {len(b)} items"
        return next((d for i, (x, y) in enumerate(zip(a, b)) if (d := first_difference(x, y, f"{path}[{i}]"))), None)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        return None if math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12) else f"{path}: {a!r} vs {b!r}"
    return None if a == b else f"{path}: {str(a)[:50]!r} vs {str(b)[:50]!r}"


def same(a, b, tol=5e-4):
    assert (a["status"], a["reason"]) == (b["status"], b["reason"])
    assert [(p["chunk_id"], p["text_sha"], p["citation"]) for p in a["passages"]] == [(p["chunk_id"], p["text_sha"], p["citation"]) for p in b["passages"]]
    for p, q in zip(a["passages"], b["passages"]):
        assert p["scores"].keys() == q["scores"].keys()
        for k in p["scores"]:
            assert p["scores"][k] == pytest.approx(q["scores"][k], abs=tol)


# ── dense OFF: identical to before ───────────────────────────────────────────────────────────────────────────────
def test_the_flag_is_off_by_default_and_the_retriever_has_no_dense_index(cfg, chunks):
    assert cfg["enabled"] is False
    assert dense.for_retriever([c.chunk_id for c in chunks], [index_text(c.text) for c in chunks]) is None
    assert Retriever(chunks).dense is None


def test_with_dense_off_every_answer_equals_the_answer_before_this_change():
    """tests/rag/golden_search.json was taken from the code BEFORE dense search existed: 72 questions, searched plain and
    with a query plan. Status, reason, passage order, text, citations and scores must be unchanged."""
    r = Retriever(ingest())
    assert len(GOLDEN) == 72
    for item in GOLDEN:
        q = item["question"]
        same(compact(r.search(q)), item["plain"])
        same(compact(r.search(q, qp.process(q))), item["planned"])


def test_with_dense_off_no_passage_carries_a_dense_score():
    r = Retriever(ingest())
    for item in GOLDEN[:20]:
        for p in r.search(item["question"])["passages"]:
            assert set(p["scores"]) == {"bm25", "vector", "rrf"} and set(p) == {"chunk_id", "text", "citation", "scores"}


def test_the_retrievers_public_interface_is_unchanged():
    assert str(inspect.signature(Retriever.__init__)) == "(self, chunks: 'list[Chunk]', config: 'dict | None' = None)"
    assert str(inspect.signature(Retriever.search)) == (
        "(self, question: 'str', plan: 'QueryPlan | None' = None, conditions: 'Sequence[str] | None' = None) -> 'dict'")  # P19 added the optional `conditions`
    assert str(inspect.signature(Retriever.rerank)) == "(self, question: 'str', candidates: 'list[int]') -> 'list[int]'"


def test_the_website_and_its_evidence_file_do_not_know_about_dense_search():
    from diacausal.rag.export_web import evidence_dict

    committed = json.loads((ROOT / "web" / "evidence.json").read_text(encoding="utf-8"))
    assert first_difference(json.loads(json.dumps(evidence_dict())), committed) is None, "web/evidence.json must not change"
    assert not [k for k in committed if "dense" in k.lower()] and "dense" not in json.dumps(committed["config"])
    for js in (ROOT / "web").glob("*.js"):
        assert "dense" not in js.read_text(encoding="utf-8").lower(), js.name
    import hashlib as h

    assert committed["versions"]["config_sha"] == h.sha256(b"config.yaml\0" + (ROOT / "diacausal/rag/config.yaml").read_bytes()).hexdigest()[:10]


# ── dense ON ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_dense_search_never_changes_whether_the_system_abstains(chunks, ids_texts, cfg, built):
    off, on = Retriever(chunks), retriever_on(chunks, ids_texts, cfg, built)
    for item in GOLDEN:
        for plan in (None, qp.process(item["question"])):
            a, b = off.search(item["question"], plan), on.search(item["question"], plan)
            assert (a["status"], a.get("reason")) == (b["status"], b.get("reason")), item["question"]


def test_dense_search_only_reorders_the_passages_the_keyword_searches_found(chunks, ids_texts, cfg, built):
    off, on = Retriever(chunks), retriever_on(chunks, ids_texts, cfg, built)
    for item in GOLDEN:
        res = on.search(item["question"])
        for p in res["passages"]:
            assert p["scores"]["bm25"] > 0 or p["scores"]["vector"] > 0  # a candidate the keyword searches already had
            assert set(p["scores"]) == {"bm25", "vector", "dense", "rrf"} and -1.0001 <= p["scores"]["dense"] <= 1.0001
    q = "Can SGLT2 inhibitors cause ketoacidosis?"
    by_off = {p["chunk_id"]: p["scores"] for p in off.search(q)["passages"]}
    for p in on.search(q)["passages"]:  # the keyword scores of a passage do not depend on dense search
        if p["chunk_id"] in by_off:
            assert (p["scores"]["bm25"], p["scores"]["vector"]) == (by_off[p["chunk_id"]]["bm25"], by_off[p["chunk_id"]]["vector"])


def test_the_dense_ranking_really_enters_the_fusion(chunks, ids_texts, cfg, built):
    """Make one passage the dense winner for a question: it must not move down, and for some question it moves up."""
    off = Retriever(chunks)
    moved_up = 0
    for question in ("Can SGLT2 inhibitors cause ketoacidosis?", "metformin kidney function eGFR", "What happened with joint pain and the gliptin?",
                     "side effects of metformin diarrhea nausea", "heart failure saxagliptin", "lactic acidosis risk"):
        base = off.search(question)
        if base["status"] != "SUCCESS" or len(base["passages"]) < 3:
            continue
        target = base["passages"][-1]["chunk_id"]  # the last of the top five
        target_text = index_text(next(c.text for c in chunks if c.chunk_id == target))

        class Pull(StandInEmbedder):
            def embed_query(self, text):  # the question "looks like" the target passage
                return self._vector(target_text)

        on = retriever_on(chunks, ids_texts, cfg, built, embedder=Pull())
        after = [p["chunk_id"] for p in on.search(question)["passages"]]
        assert target in after and after.index(target) <= len(base["passages"]) - 1
        moved_up += after.index(target) < len(base["passages"]) - 1
    assert moved_up >= 1, "dense search never changed a ranking"


def test_dense_scores_are_the_cosine_of_the_question_and_the_best_window(chunks, ids_texts, cfg, built):
    index = dense.load(*ids_texts, cfg, "bge-small-en-v1.5", embedder=StandInEmbedder(), root=built)
    scores = index.scores("kidney function and metformin")
    assert scores.shape == (len(chunks),) and np.isfinite(scores).all() and scores.max() <= 1.0001
    q = index.embedder.embed_query("kidney function and metformin")
    for i in (0, 10, 40, 77):
        rows = [k for k, r in enumerate(index.rows) if r["chunk_id"] == ids_texts[0][i]]
        assert scores[i] == pytest.approx(max(float(index.embeddings[k] @ q) for k in rows), abs=1e-6)


def test_the_question_given_to_dense_search_is_the_original_not_the_expansion(chunks, ids_texts, cfg, built):
    seen = []

    class Spy(StandInEmbedder):
        def embed_query(self, text):
            seen.append(text)
            return super().embed_query(text)

    on = retriever_on(chunks, ids_texts, cfg, built, embedder=Spy())
    q = "Can DKA happen with SGLT2i?"
    on.search(q, qp.process(q))
    assert seen == [q] and "diabetic" not in seen[0]


# ── the saved index ──────────────────────────────────────────────────────────────────────────────────────────────
def test_windows_cut_long_text_with_overlap_and_keep_short_text_whole():
    short = "one two three"
    assert dense.windows(short, 250, 50) == [short]
    words = [f"w{i}" for i in range(400)]
    parts = dense.windows(" ".join(words), 250, 50)
    assert [len(p.split()) for p in parts] == [250, 200] and parts[0].split()[200:] == parts[1].split()[:50]
    assert parts[-1].split()[-1] == "w399" and all(len(p.split()) <= 250 for p in parts)
    assert len(dense.windows(" ".join(words[:250]), 250, 50)) == 1 and len(dense.windows(" ".join(words[:251]), 250, 50)) == 2
    with pytest.raises(ValueError):
        dense.windows("a b c", 5, 5)


def test_the_saved_files_hold_what_the_plan_says(built, cfg, ids_texts):
    for key in cfg["models"]:
        folder = built / key
        assert sorted(p.name for p in folder.iterdir()) == ["chunks.jsonl", "embeddings.npy", "index_meta.json"]
        meta = json.loads((folder / "index_meta.json").read_text())
        embeddings = np.load(folder / "embeddings.npy")
        rows = [json.loads(line) for line in (folder / "chunks.jsonl").read_text().splitlines()]
        assert meta["model"] == cfg["models"][key]["hf_name"] and meta["date"] == "2026-10-09" and meta["chunk_count"] == 78
        assert {"model_revision", "library", "window_count", "dimension", "query_prefix", "licence"} <= set(meta)
        assert embeddings.shape == (len(rows), DIM) == (meta["window_count"], meta["dimension"]) and embeddings.dtype == np.float32
        assert {r["chunk_id"] for r in rows} == set(ids_texts[0]) and all(set(r) == {"chunk_id", "window", "text_sha"} for r in rows)
        assert np.allclose(np.linalg.norm(embeddings, axis=1), 1.0, atol=1e-5)


def test_a_stale_or_missing_index_is_an_error_never_a_silent_fallback(built, cfg, ids_texts, tmp_path):
    ids, texts = ids_texts
    key = "bge-small-en-v1.5"
    changed = list(texts)
    changed[3] = changed[3] + " one more sentence"
    with pytest.raises(dense.DenseIndexError, match="stale"):
        dense.load(ids, changed, cfg, key, embedder=StandInEmbedder(), root=built)
    with pytest.raises(dense.DenseIndexError, match="stale"):
        dense.load(ids[:-1], texts[:-1], cfg, key, embedder=StandInEmbedder(), root=built)
    with pytest.raises(dense.DenseIndexError, match="stale"):
        dense.load(ids, texts, {**cfg, "window_words": 120}, key, embedder=StandInEmbedder(), root=built)
    with pytest.raises(dense.DenseIndexError, match="build --model"):
        dense.load(ids, texts, cfg, key, embedder=StandInEmbedder(), root=tmp_path)
    with pytest.raises(dense.DenseIndexError, match="unknown dense model"):
        dense.load(ids, texts, cfg, "no-such-model", embedder=StandInEmbedder(), root=built)
    other = {**cfg, "models": {**cfg["models"], key: {**cfg["models"][key], "hf_name": "someone/else"}}}
    with pytest.raises(dense.DenseIndexError, match="rebuild"):
        dense.load(ids, texts, other, key, embedder=StandInEmbedder(), root=built)


def test_a_retriever_with_the_flag_on_and_a_stale_index_refuses_to_start(chunks, cfg, tmp_path):
    on = {**cfg, "enabled": True}
    with pytest.raises(dense.DenseIndexError):
        dense.for_retriever([c.chunk_id for c in chunks], [index_text(c.text) for c in chunks], on, root=tmp_path)


def test_dose_text_is_never_embedded(chunks, ids_texts, cfg, tmp_path):
    assert sum(bool(DOSE.search(c.text)) for c in chunks) >= 5, "the corpus has dose-like text, so this test checks something"
    spy = StandInEmbedder()
    dense.build(*ids_texts, cfg, "bge-small-en-v1.5", embedder=spy, root=tmp_path)
    assert spy.seen and not [t for t in spy.seen if DOSE.search(t)]
    raw = {c.chunk_id: c.text for c in chunks if DOSE.search(c.text)}
    assert all(any(DOSE.search(raw[cid]) for cid in raw) for _ in [0])  # the raw texts do contain it; only the index text is clean


def test_the_committed_indexes_are_current_for_every_model_and_say_which_model_made_them(cfg, ids_texts):
    ids, texts = ids_texts
    for key, model in cfg["models"].items():
        index = dense.load(ids, texts, cfg, key, embedder=object())  # no model needed: only the hashes are checked
        meta = index.meta
        assert meta["model"] == model["hf_name"] and meta["licence"] == model["licence"] and meta["dimension"] == model["dimension"]
        assert meta["chunk_count"] == 78 and meta["window_count"] == 111 and re.fullmatch(r"\d{4}-\d\d-\d\d", meta["date"])
        assert meta["longest_window_tokens"] <= model["max_tokens"] and re.fullmatch(r"[0-9a-f]{40}", meta["model_revision"])
        assert meta["library"].startswith("sentence-transformers ") and index.embeddings.dtype == np.float32


def test_the_check_command_reports_current_without_a_model(capsys):
    with pytest.raises(SystemExit) as stop:
        dense.main(["check"])
    assert stop.value.code == 0
    assert capsys.readouterr().out.count(": current") == 2


# ── the configuration ────────────────────────────────────────────────────────────────────────────────────────────
def test_dense_yaml_has_a_source_and_a_status_on_every_entry_and_the_model_facts_of_the_cards():
    import yaml

    raw = yaml.safe_load((ROOT / "diacausal/rag/dense.yaml").read_text(encoding="utf-8"))
    assert all(e.get("source") and e.get("status") in ("CITED", "ASSUMED-DIRECTIONAL", "TEAM-SET") for e in raw.values())
    models = raw["models"]["value"]
    assert models["bge-small-en-v1.5"]["licence"] == "MIT" and models["bge-small-en-v1.5"]["dimension"] == 384
    assert models["pubmedbert-base-embeddings"]["licence"] == "Apache-2.0" and models["pubmedbert-base-embeddings"]["dimension"] == 768
    assert models["bge-small-en-v1.5"]["query_prefix"] == "Represent this sentence for searching relevant passages: "
    assert models["pubmedbert-base-embeddings"]["query_prefix"] == "" and raw["model"]["value"] in models and raw["enabled"]["value"] is False


def test_the_dense_libraries_are_pinned_in_their_own_file_and_not_in_the_engine_or_website_files():
    dense_req = (ROOT / "requirements-dense.txt").read_text()
    assert re.search(r"^sentence-transformers==\d", dense_req, re.M) and re.search(r"^torch==\d", dense_req, re.M) and "-r requirements-engine.txt" in dense_req
    for other in ("requirements-engine.txt", "requirements-xai.txt"):
        assert not re.search(r"torch|sentence-transformers", (ROOT / other).read_text())


def test_importing_the_retriever_loads_neither_torch_nor_sentence_transformers():
    import subprocess

    code = ("import sys, diacausal.rag.retrieve.hybrid, diacausal.rag.index.dense as d, diacausal.rag.evaluate; "
            "bad=[m for m in ('torch','sentence_transformers','transformers') if m in sys.modules]; assert not bad, bad")
    done = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr


# ── the retrieval metrics ────────────────────────────────────────────────────────────────────────────────────────
def test_recall_mrr_and_ndcg_match_hand_calculations():
    assert ev.recall_at_k([0, 0, 1, 0, 0]) == 1.0 and ev.recall_at_k([0, 0, 0, 0, 0]) == 0.0 and ev.recall_at_k([]) == 0.0
    assert ev.recall_at_k([0, 0, 0, 0, 0, 1]) == 0.0  # the sixth is outside the top five
    assert ev.reciprocal_rank([0, 0, 1, 1, 0]) == pytest.approx(1 / 3) and ev.reciprocal_rank([1]) == 1.0 and ev.reciprocal_rank([0, 0]) == 0.0
    assert ev.ndcg_at_k([1, 0, 0, 0, 0], 1) == pytest.approx(1.0)
    assert ev.ndcg_at_k([0, 1, 0, 0, 0], 1) == pytest.approx(1 / np.log2(3))  # relevant passage at rank 2, one exists
    assert ev.ndcg_at_k([1, 0, 1, 0, 0], 2) == pytest.approx((1 + 1 / np.log2(4)) / (1 + 1 / np.log2(3)))
    assert ev.ndcg_at_k([1, 1, 1, 1, 1], 9) == pytest.approx(1.0) and ev.ndcg_at_k([1, 0], 0) == 0.0 and ev.ndcg_at_k([], 3) == 0.0


def test_relevance_means_the_expected_source_and_section():
    passages = [{"citation": {"source_id": "S08", "section": "Safety Announcement"}}, {"citation": {"source_id": "S19", "section": "Safety Announcement"}},
                {"citation": {"source_id": "S08", "section": "Data Summary"}}]
    assert ev.relevance_flags(passages, "S08", "safety announcement") == [1, 0, 0] and ev.relevance_flags(passages, "S08", "data") == [0, 0, 1]


def test_the_split_is_seeded_stratified_disjoint_and_covers_every_answerable_question():
    gold = ev.load_gold()
    dev, held = ev.split_gold(gold, 2026, 0.34)
    answerable = [g for g in gold if g["category"] == "answerable"]
    assert len(dev) + len(held) == len(answerable) == 45 and not {g["id"] for g in dev} & {g["id"] for g in held}
    assert (dev, held) == ev.split_gold(gold, 2026, 0.34) and held != ev.split_gold(gold, 7, 0.34)[1]
    assert [g["id"] for g in dev] == [g["id"] for g in answerable if g["id"] in {d["id"] for d in dev}]  # the file's order
    sources = {g["expected_source"] for g in answerable}
    assert {g["expected_source"] for g in held} == sources - set() or len({g["expected_source"] for g in held}) >= 6
    assert 12 <= len(held) <= 18 and all(g["category"] == "answerable" for g in dev + held)


def test_the_paired_comparison_counts_wins_losses_and_ties_and_is_seeded():
    on, off = [1.0, 0.5, 0.0, 0.25, 1.0], [0.5, 0.5, 0.25, 0.25, 1.0]
    a = ev.paired_difference(on, off, 500, 1)
    assert (a["wins"], a["losses"], a["ties"], a["n"]) == (1, 1, 3, 5) and a["diff"] == pytest.approx(0.25 / 5)
    assert a == ev.paired_difference(on, off, 500, 1) and a["ci_low"] <= a["ci_high"]
    same_all = ev.paired_difference([0.5] * 4, [0.5] * 4, 100, 1)
    assert (same_all["diff"], same_all["ci_low"], same_all["ci_high"], same_all["ties"]) == (0.0, 0.0, 0.0, 4)


def test_the_ablation_runs_end_to_end_with_stand_in_embedders(monkeypatch, built, cfg):
    monkeypatch.setattr(dense, "INDEX_ROOT", built)
    rows, paired = ev.dense_ablation(embedders={k: StandInEmbedder() for k in cfg["models"]})
    keys = {(r["split"], r["model"], r["dense"], r["metric"]) for r in rows}
    assert len(rows) == 3 * 3 * (1 + len(cfg["models"])) and ("heldout", "bge-small-en-v1.5", "on", "mrr") in keys and ("dev", "none", "off", "recall_at_5") in keys
    assert len(paired) == 3 * 3 * len(cfg["models"])
    for r in rows:
        assert 0.0 <= r["mean"] <= 1.0 and r["n"] in (30, 15, 45)
    for r in paired:
        on = next(x["mean"] for x in rows if (x["split"], x["model"], x["dense"], x["metric"]) == (r["split"], r["model"], "on", r["metric"]))
        off = next(x["mean"] for x in rows if (x["split"], x["model"], x["dense"], x["metric"]) == (r["split"], "none", "off", r["metric"]))
        assert r["diff"] == pytest.approx(on - off, abs=1e-9) and r["wins"] + r["losses"] + r["ties"] == r["n"]


def test_the_baseline_without_dense_equals_the_committed_retrieval_evaluation():
    """The 'off' rows use the same hit test and the same questions as results/rag_eval.csv, so recall@5 is the same number."""
    rows = [r for r in __import__("csv").DictReader((ROOT / "results/rag_dense_eval.csv").read_text().splitlines())]
    summary = {r["metric"]: r["value"] for r in __import__("csv").DictReader((ROOT / "results/rag_eval_summary.csv").read_text().splitlines())}
    off_all = next(float(r["mean"]) for r in rows if r["split"] == "all" and r["dense"] == "off" and r["metric"] == "recall_at_5")
    assert off_all == pytest.approx(float(summary["recall_at_5"]), abs=5e-4)


# ── the committed results ────────────────────────────────────────────────────────────────────────────────────────
def test_the_committed_results_have_the_expected_shape_and_the_off_rows_are_reproducible_without_a_model():
    import csv

    rows = list(csv.DictReader((ROOT / "results/rag_dense_eval.csv").read_text().splitlines()))
    paired = list(csv.DictReader((ROOT / "results/rag_dense_paired.csv").read_text().splitlines()))
    assert list(rows[0]) == ["split", "model", "dense", "metric", "mean", "n"]
    assert list(paired[0]) == ["split", "model", "metric", "diff", "ci_low", "ci_high", "wins", "losses", "ties", "n"]
    assert {r["model"] for r in rows} == {"none", "bge-small-en-v1.5", "pubmedbert-base-embeddings"} and {r["metric"] for r in rows} == {"recall_at_5", "mrr", "ndcg_at_5"}
    assert all(0 <= float(r["mean"]) <= 1 for r in rows) and all(int(p["wins"]) + int(p["losses"]) + int(p["ties"]) == int(p["n"]) for p in paired)
    cfg = dense.load_dense_config()
    dev, held = ev.split_gold(ev.load_gold(), int(cfg["eval_split_seed"]), float(cfg["eval_heldout_fraction"]))
    off = Retriever(ingest())
    for name, qs in {"dev": dev, "heldout": held, "all": dev + held}.items():
        live = ev.per_question_metrics(off, qs)
        for metric, values in live.items():
            saved = next(float(r["mean"]) for r in rows if (r["split"], r["dense"], r["metric"]) == (name, "off", metric))
            assert saved == pytest.approx(float(np.mean(values)), abs=5e-5), (name, metric)


# ── the real models (local only: skipped in CI and wherever the models are not downloaded) ──────────────────────
def _real_models_available() -> bool:
    try:
        from huggingface_hub import try_to_load_from_cache
        import sentence_transformers  # noqa: F401
    except ImportError:
        return False
    names = [m["hf_name"] for m in dense.load_dense_config()["models"].values()]
    return all(isinstance(try_to_load_from_cache(n, "config.json"), str) for n in names)


@pytest.mark.skipif(not _real_models_available(), reason="needs requirements-dense.txt and the two downloaded models")
def test_the_real_models_reproduce_the_saved_embeddings_and_the_saved_results(cfg, ids_texts, chunks):
    ids, texts = ids_texts
    for key, model in cfg["models"].items():
        embedder = dense.SentenceEmbedder(model["hf_name"], model["query_prefix"], cfg["batch_size"])
        index = dense.load(ids, texts, cfg, key, embedder=embedder)
        fresh = embedder.embed_passages(dense.window_rows(ids[:5], texts[:5], cfg["window_words"], cfg["window_overlap_words"])[1])
        assert np.abs(np.sum(fresh * index.embeddings[: len(fresh)], axis=1) - 1.0).max() < 1e-3  # same vectors on this machine
        assert embedder.revision() == index.meta["model_revision"]
        assert index.scores("Can SGLT2 inhibitors cause ketoacidosis?").argmax() in range(len(chunks))
    import csv

    rows, _ = ev.dense_ablation()
    saved = {(r["split"], r["model"], r["dense"], r["metric"]): float(r["mean"]) for r in csv.DictReader((ROOT / "results/rag_dense_eval.csv").read_text().splitlines())}
    for r in rows:
        assert r["mean"] == pytest.approx(saved[(r["split"], r["model"], r["dense"], r["metric"])], abs=0.02)
