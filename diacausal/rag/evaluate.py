"""RAG evaluation on the gold question set (RAG guide Step R5).

    python -m diacausal.rag.evaluate                       # template explanations (offline)
    python -m diacausal.rag.evaluate --backend ollama      # a local model (needs Ollama running)
    python -m diacausal.rag.evaluate --dense-ablation      # retrieval with and without dense search, per model (needs requirements-dense.txt)
    python -m diacausal.rag.evaluate --ranking-tune        # choose fusion_round_decimals on the TRAIN split only
    python -m diacausal.rag.evaluate --ranking-ablation    # before / after source-aware ranking on train and held-out (dense models need requirements-dense.txt)

Reads eval/rag_gold.csv (45 answerable questions with the source and section that answer them,
10 out-of-scope questions, 5 dose requests). Writes results/rag_eval.csv (one row per question)
and results/rag_eval_summary.csv, and prints:
    recall@5              answerable questions whose expected source+section is in the top 5
    answered              answerable questions that got an answer (not INSUFFICIENT_EVIDENCE)
    abstention accuracy   out-of-scope questions correctly answered INSUFFICIENT_EVIDENCE
    citation precision    explanation sentences that pass the citation checker
    dose leaks            dose-like text in any shown passage or explanation (must be 0)

--dense-ablation writes results/rag_dense_eval.csv and results/rag_dense_paired.csv: recall@5, MRR and nDCG@5 of the retriever
with dense search OFF and ON for each model of diacausal/rag/dense.yaml, on a seeded dev / held-out split of the answerable
questions (never used to tune anything), plus the paired difference (win / loss / tie counts and a seeded bootstrap interval).
A passage is relevant if it has the question's expected source and section; the ranking is the top 5 the retriever returns
(an abstention is an empty ranking, so it scores 0). It does not touch results/rag_eval*.csv.

--ranking-tune and --ranking-ablation (P19, diacausal/rag/ranking.yaml): all 60 gold questions are split by a fixed seed into train and
held-out, stratified (answerable by source, out-of-scope, dose). The one setting that is tuned (fusion_round_decimals) is chosen on
TRAIN only; held-out is reported once, before and after, with the paired differences, in results/rag_ranking_*.csv.
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import numpy as np

from diacausal.causal_inference.recommend import DOSE_PATTERN
from diacausal import INTENDED_USE
from diacausal.guards.output_guards import check_answer
from diacausal.llm.explain import BACKENDS, explain, render
from diacausal.config import ROOT, load_rag_config
from diacausal.rag.ingest.licence_gate import ingest
from diacausal.rag.retrieve import query_processing
from diacausal.rag.retrieve.hybrid import Retriever

GOLD = ROOT / "eval" / "rag_gold.csv"
OUT = ROOT / "results"


def load_gold(path: Path = GOLD) -> list[dict]:
    with Path(path).open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def hit(evidence: dict, source: str, section: str) -> bool:
    return any(p["citation"]["source_id"] == source and section.lower() in p["citation"]["section"].lower()
               for p in evidence["passages"])


def run(backend: str = "template", gold: list[dict] | None = None) -> tuple[list[dict], dict]:
    cfg = load_rag_config()
    retriever = Retriever(ingest(), cfg)
    rows = []
    for g in gold or load_gold():
        ev = retriever.search(g["question"], query_processing.process(g["question"]))  # as the pipeline does
        reply = explain(g["question"], ev, backend, cfg, idf=retriever.bm25.idf)
        text = render(reply) if reply["status"] == "SUCCESS" else ""
        shown = " ".join(p["text"] for p in ev["passages"]) + " " + text
        answer_text = " ".join(s["text"] + "".join(f"[{c}]" for c in s["cites"]) for s in reply["sentences"])
        checked, _ = check_answer(answer_text, ev["passages"], float(cfg["explain_min_support"])) if answer_text else ([], [])
        rows.append({
            "id": g["id"], "category": g["category"], "question": g["question"],
            "retrieval": ev["status"], "explanation": reply["status"], "backend": reply["backend"],
            "hit_at_5": int(hit(ev, g["expected_source"], g["expected_section"])) if g["category"] == "answerable" else "",
            "top_source": ev["passages"][0]["citation"]["source_id"] if ev["passages"] else "",
            "sentences": len(reply["sentences"]), "sentences_checked": len(checked),
            "dose_leak": int(bool(DOSE_PATTERN.search(shown))), "doctor_review": g["doctor_review"],
            "note": reply["note"],
        })
    return rows, summarise(rows, backend)


def summarise(rows: list[dict], backend: str) -> dict:
    ans = [r for r in rows if r["category"] == "answerable"]
    oos = [r for r in rows if r["category"] == "out_of_scope"]
    dose = [r for r in rows if r["category"] == "dose"]
    sent = sum(r["sentences"] for r in rows)
    return {
        "backend": backend,
        "questions": len(rows),
        "recall_at_5": sum(r["hit_at_5"] for r in ans) / len(ans),
        "answered": sum(r["explanation"] == "SUCCESS" for r in ans) / len(ans),
        "abstention_accuracy": sum(r["retrieval"] == "INSUFFICIENT_EVIDENCE" for r in oos) / len(oos),
        "citation_precision": sum(r["sentences_checked"] for r in rows) / sent if sent else 1.0,
        "dose_leaks": sum(r["dose_leak"] for r in rows),
        "dose_questions_without_leak": sum(not r["dose_leak"] for r in dose) / len(dose),
    }


def write(rows: list[dict], summary: dict, out: Path = OUT) -> None:
    out.mkdir(exist_ok=True)
    with (out / "rag_eval.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with (out / "rag_eval_summary.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["metric", "value"])
        for k, v in summary.items():
            w.writerow([k, f"{v:.3f}" if isinstance(v, float) else v])


# ── retrieval metrics and the dense ablation ─────────────────────────────────────────────────────────────────────────

def relevance_flags(passages: list[dict], source: str, section: str) -> list[int]:
    """1 for each returned passage that has the expected source and section (the same test as `hit`), else 0."""
    return [int(p["citation"]["source_id"] == source and section.lower() in p["citation"]["section"].lower()) for p in passages]


def recall_at_k(flags: list[int], k: int = 5) -> float:
    return float(any(flags[:k]))


def reciprocal_rank(flags: list[int], k: int = 5) -> float:
    """1 / rank of the first relevant passage among the first k, 0 if there is none."""
    for rank, flag in enumerate(flags[:k], start=1):
        if flag:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(flags: list[int], n_relevant: int, k: int = 5) -> float:
    """Binary-gain nDCG: DCG of the ranking over the best possible DCG given `n_relevant` relevant chunks in the index."""
    if n_relevant <= 0:
        return 0.0
    dcg = sum(flag / math.log2(rank + 1) for rank, flag in enumerate(flags[:k], start=1))
    ideal = sum(1 / math.log2(rank + 1) for rank in range(1, min(n_relevant, k) + 1))
    return dcg / ideal


def split_gold(gold: list[dict], seed: int, heldout_fraction: float) -> tuple[list[dict], list[dict]]:
    """(dev, held-out) of the ANSWERABLE questions: seeded, stratified by expected source (each source gives about
    `heldout_fraction` of its questions, at least one when it has two or more), disjoint, in the file's order."""
    rng = np.random.default_rng(seed)
    answerable = [g for g in gold if g["category"] == "answerable"]
    held: set[str] = set()
    for source in sorted({g["expected_source"] for g in answerable}):
        ids = sorted(g["id"] for g in answerable if g["expected_source"] == source)
        n = int(round(heldout_fraction * len(ids))) if len(ids) >= 2 else 0
        n = max(n, 1) if len(ids) >= 2 else 0
        held.update(rng.choice(ids, size=n, replace=False).tolist())
    return [g for g in answerable if g["id"] not in held], [g for g in answerable if g["id"] in held]


def paired_difference(on: list[float], off: list[float], resamples: int, seed: int) -> dict:
    """Mean of (on - off) per question with a seeded percentile bootstrap 95% interval, and win / loss / tie counts."""
    diff = np.asarray(on, float) - np.asarray(off, float)
    rng = np.random.default_rng(seed)
    means = np.array([diff[rng.integers(0, len(diff), len(diff))].mean() for _ in range(resamples)])
    eps = 1e-12
    return {"diff": float(diff.mean()), "ci_low": float(np.percentile(means, 2.5)), "ci_high": float(np.percentile(means, 97.5)),
            "wins": int((diff > eps).sum()), "losses": int((diff < -eps).sum()), "ties": int((np.abs(diff) <= eps).sum()), "n": len(diff)}


def per_question_metrics(retriever: Retriever, questions: list[dict]) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {"recall_at_5": [], "mrr": [], "ndcg_at_5": []}
    for g in questions:
        ev = retriever.search(g["question"], query_processing.process(g["question"]))  # as the pipeline does
        flags = relevance_flags(ev["passages"], g["expected_source"], g["expected_section"])
        n_relevant = sum(c.source_id == g["expected_source"] and g["expected_section"].lower() in c.section.lower() for c in retriever.chunks)
        out["recall_at_5"].append(recall_at_k(flags))
        out["mrr"].append(reciprocal_rank(flags))
        out["ndcg_at_5"].append(ndcg_at_k(flags, n_relevant))
    return out


def dense_ablation(model_keys: list[str] | None = None, gold: list[dict] | None = None, embedders: dict | None = None) -> tuple[list[dict], list[dict]]:
    """(metric rows, paired rows) for dense OFF and ON per model on the dev split, the held-out split and all answerable
    questions. `embedders` lets a test stand in for the real models."""
    from diacausal.rag.index import dense
    from diacausal.rag.retrieve.hybrid import index_text

    cfg = dense.load_dense_config()
    rcfg = load_rag_config()
    chunks = ingest()
    ids, texts = [c.chunk_id for c in chunks], [index_text(c.text) for c in chunks]
    dev, held = split_gold(gold or load_gold(), int(cfg["eval_split_seed"]), float(cfg["eval_heldout_fraction"]))
    splits = {"dev": dev, "heldout": held, "all": dev + held}
    off = Retriever(chunks, rcfg)
    off.dense = None
    base = {name: per_question_metrics(off, qs) for name, qs in splits.items()}
    rows, paired = [], []
    for name, qs in splits.items():
        for metric, values in base[name].items():
            rows.append({"split": name, "model": "none", "dense": "off", "metric": metric, "mean": float(np.mean(values)), "n": len(values)})
    for key in model_keys or sorted(cfg["models"]):
        on = Retriever(chunks, rcfg)
        on.dense = dense.load(ids, texts, cfg, key, embedder=(embedders or {}).get(key))
        for name, qs in splits.items():
            scored = per_question_metrics(on, qs)
            for metric, values in scored.items():
                rows.append({"split": name, "model": key, "dense": "on", "metric": metric, "mean": float(np.mean(values)), "n": len(values)})
                paired.append({"split": name, "model": key, "metric": metric,
                               **paired_difference(values, base[name][metric], int(cfg["eval_bootstrap_resamples"]), int(cfg["eval_split_seed"]))})
    return rows, paired


# ── source-aware ranking: split, tuning, before / after ───────────────────────────────────────────────────────────────

def split_gold_full(gold: list[dict], seed: int, heldout_fraction: float) -> tuple[list[dict], list[dict]]:
    """(train, held-out) of ALL gold questions: seeded, disjoint, stratified: answerable questions by expected source (as
    split_gold), out-of-scope and dose questions each as one stratum (about `heldout_fraction` of it, at least one)."""
    _, held_answerable = split_gold(gold, seed, heldout_fraction)
    held = {g["id"] for g in held_answerable}
    rng = np.random.default_rng(seed + 1)
    for category in ("out_of_scope", "dose"):
        ids = sorted(g["id"] for g in gold if g["category"] == category)
        if ids:
            held.update(rng.choice(ids, size=max(1, int(round(heldout_fraction * len(ids)))), replace=False).tolist())
    return [g for g in gold if g["id"] not in held], [g for g in gold if g["id"] in held]


def ranking_question_rows(retriever: Retriever, questions: list[dict]) -> list[dict]:
    """One row per question: recall, reciprocal rank and nDCG for answerable ones, abstention for out-of-scope ones, and the
    dose leak (dose-like text in a shown passage) for every question. No patient is given, so the condition key is inert here."""
    rows = []
    for g in questions:
        ev = retriever.search(g["question"], query_processing.process(g["question"]))
        row = {"id": g["id"], "category": g["category"], "dose_leak": int(any(DOSE_PATTERN.search(p["text"]) for p in ev["passages"]))}
        if g["category"] == "answerable":
            flags = relevance_flags(ev["passages"], g["expected_source"], g["expected_section"])
            n_relevant = sum(c.source_id == g["expected_source"] and g["expected_section"].lower() in c.section.lower() for c in retriever.chunks)
            row |= {"recall_at_5": recall_at_k(flags), "mrr": reciprocal_rank(flags), "ndcg_at_5": ndcg_at_k(flags, n_relevant)}
        elif g["category"] == "out_of_scope":
            row["abstained"] = float(ev["status"] == "INSUFFICIENT_EVIDENCE")
        rows.append(row)
    return rows


def _mean(rows: list[dict], key: str) -> tuple[float, int]:
    values = [r[key] for r in rows if key in r]
    return (float(np.mean(values)) if values else float("nan")), len(values)


def ranking_retriever(chunks, rcfg, rk_cfg: dict | None, decimals="keep", dense_index=None) -> Retriever:
    """A retriever with the source-aware ranking ON (rk_cfg given; `decimals` overrides fusion_round_decimals) or OFF."""
    r = Retriever(chunks, rcfg)
    r.dense = dense_index
    r.ranking = None if rk_cfg is None else {**rk_cfg, "enabled": True, **({} if decimals == "keep" else {"fusion_round_decimals": decimals})}
    return r


def ranking_tune(rk_cfg: dict | None = None, gold: list[dict] | None = None) -> tuple[list[dict], object]:
    """Try each fusion_round_decimals of the tuning grid on the TRAIN split (dense off): (rows, the best value). Best = the
    highest train nDCG@5, then the highest train MRR, then the exact comparison (null). Held-out is never read."""
    from diacausal.rag.retrieve import ranking

    rk_cfg = rk_cfg or ranking.load_ranking_config()
    chunks, rcfg = ingest(), load_rag_config()
    train, _ = split_gold_full(gold or load_gold(), int(rk_cfg["split_seed"]), float(rk_cfg["split_heldout_fraction"]))
    rows = []
    for decimals in rk_cfg["tuning_grid"]:
        scored = ranking_question_rows(ranking_retriever(chunks, rcfg, rk_cfg, decimals), train)
        rows.append({"fusion_round_decimals": "exact" if decimals is None else decimals, "train_recall_at_5": _mean(scored, "recall_at_5")[0],
                     "train_mrr": _mean(scored, "mrr")[0], "train_ndcg_at_5": _mean(scored, "ndcg_at_5")[0], "n": _mean(scored, "mrr")[1],
                     "_value": decimals})
    best = max(rows, key=lambda r: (round(r["train_ndcg_at_5"], 9), round(r["train_mrr"], 9), r["_value"] is None))
    for r in rows:
        r["chosen"] = int(r is best)
    return rows, best["_value"]


def ranking_ablation(model_keys: list[str] | None = None, gold: list[dict] | None = None, embedders: dict | None = None,
                     rk_cfg: dict | None = None) -> tuple[list[dict], list[dict]]:
    """(metric rows, paired rows): `before` = the retriever as it is today (ranking off, dense off); `after` = source-aware
    ranking on; `after+dense:<model>` = ranking and dense search on. On train, held-out and all 60 questions."""
    from diacausal.rag.index import dense
    from diacausal.rag.retrieve import ranking
    from diacausal.rag.retrieve.hybrid import index_text

    rk_cfg = rk_cfg or ranking.load_ranking_config()
    dcfg, rcfg, chunks = dense.load_dense_config(), load_rag_config(), ingest()
    ids, texts = [c.chunk_id for c in chunks], [index_text(c.text) for c in chunks]
    train, held = split_gold_full(gold or load_gold(), int(rk_cfg["split_seed"]), float(rk_cfg["split_heldout_fraction"]))
    splits = {"train": train, "heldout": held, "all": train + held}
    variants = {"before": ranking_retriever(chunks, rcfg, None), "after": ranking_retriever(chunks, rcfg, rk_cfg)}
    for key in model_keys if model_keys is not None else sorted(dcfg["models"]):
        index = dense.load(ids, texts, dcfg, key, embedder=(embedders or {}).get(key))
        variants[f"after+dense:{key}"] = ranking_retriever(chunks, rcfg, rk_cfg, dense_index=index)
    per = {(v, sp): ranking_question_rows(r, qs) for v, r in variants.items() for sp, qs in splits.items()}
    rows, paired = [], []
    metrics = {"recall_at_5": "answerable", "mrr": "answerable", "ndcg_at_5": "answerable", "abstained": "out_of_scope"}
    for (v, sp), scored in per.items():
        for metric in metrics:
            mean, n = _mean(scored, metric)
            rows.append({"split": sp, "variant": v, "metric": "abstention_accuracy" if metric == "abstained" else metric, "mean": mean, "n": n})
        rows.append({"split": sp, "variant": v, "metric": "dose_leaks", "mean": float(sum(r["dose_leak"] for r in scored)), "n": len(scored)})
    for (v, sp), scored in per.items():
        if v == "before":
            continue
        base = per["before", sp]
        for metric in ("recall_at_5", "mrr", "ndcg_at_5", "abstained"):
            a, b = [r[metric] for r in scored if metric in r], [r[metric] for r in base if metric in r]
            paired.append({"split": sp, "variant": v, "metric": "abstention_accuracy" if metric == "abstained" else metric,
                           **paired_difference(a, b, int(rk_cfg["bootstrap_resamples"]), int(rk_cfg["split_seed"]))})
    return rows, paired


def write_ranking_results(rows: list[dict], paired: list[dict], out: Path = OUT) -> None:
    out.mkdir(exist_ok=True)
    for name, data in (("rag_ranking_eval.csv", rows), ("rag_ranking_paired.csv", paired)):
        with (out / name).open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(data[0]))
            w.writeheader()
            for r in data:
                w.writerow({k: (f"{v:.4f}" if isinstance(v, float) else v) for k, v in r.items()})


def write_dense_ablation(rows: list[dict], paired: list[dict], out: Path = OUT) -> None:
    out.mkdir(exist_ok=True)
    for name, data in (("rag_dense_eval.csv", rows), ("rag_dense_paired.csv", paired)):
        with (out / name).open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(data[0]))
            w.writeheader()
            for r in data:
                w.writerow({k: (f"{v:.4f}" if isinstance(v, float) else v) for k, v in r.items()})


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backend", choices=BACKENDS, default="template")
    ap.add_argument("--dense-ablation", action="store_true", help="retrieval metrics with and without dense search, per model")
    ap.add_argument("--ranking-tune", action="store_true", help="choose fusion_round_decimals on the train split only")
    ap.add_argument("--ranking-ablation", action="store_true", help="before / after source-aware ranking on train and held-out")
    a = ap.parse_args(argv)
    if a.ranking_tune:
        rows, best = ranking_tune()
        out = OUT
        out.mkdir(exist_ok=True)
        with (out / "rag_ranking_tuning.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["fusion_round_decimals", "train_recall_at_5", "train_mrr", "train_ndcg_at_5", "n", "chosen"], extrasaction="ignore")
            w.writeheader()
            for r in rows:
                w.writerow({k: (f"{v:.4f}" if isinstance(v, float) else v) for k, v in r.items()})
        for r in rows:
            print(f"  decimals {str(r['fusion_round_decimals']):>6s}  train recall@5 {r['train_recall_at_5']:.3f}  MRR {r['train_mrr']:.3f}  nDCG@5 {r['train_ndcg_at_5']:.3f}  {'<- chosen' if r['chosen'] else ''}")
        print(f"Best on train: fusion_round_decimals = {best}. Saved results/rag_ranking_tuning.csv.")
        return
    if a.ranking_ablation:
        rows, paired = ranking_ablation()
        write_ranking_results(rows, paired)
        print(f"{'split':8s}{'variant':40s}{'recall@5':>9s}{'MRR':>8s}{'nDCG@5':>8s}{'abstain':>9s}{'doseleaks':>10s}")
        for split in ("train", "heldout", "all"):
            for variant in dict.fromkeys(r["variant"] for r in rows):
                v = {r["metric"]: r["mean"] for r in rows if r["split"] == split and r["variant"] == variant}
                print(f"{split:8s}{variant:40s}{v['recall_at_5']:9.3f}{v['mrr']:8.3f}{v['ndcg_at_5']:8.3f}{v['abstention_accuracy']:9.3f}{v['dose_leaks']:10.0f}")
        print(f"Saved results/rag_ranking_eval.csv and results/rag_ranking_paired.csv. {INTENDED_USE}")
        return
    if a.dense_ablation:
        rows, paired = dense_ablation()
        write_dense_ablation(rows, paired)
        print(f"{'split':8s}{'model':28s}{'dense':6s}{'recall@5':>9s}{'MRR':>8s}{'nDCG@5':>8s}   n")
        for split in ("dev", "heldout", "all"):
            for model, state in [("none", "off")] + [(m, "on") for m in sorted({r['model'] for r in rows} - {"none"})]:
                v = {r["metric"]: r for r in rows if r["split"] == split and r["model"] == model and r["dense"] == state}
                print(f"{split:8s}{model:28s}{state:6s}{v['recall_at_5']['mean']:9.3f}{v['mrr']['mean']:8.3f}{v['ndcg_at_5']['mean']:8.3f}  {v['mrr']['n']}")
        print(f"Saved results/rag_dense_eval.csv and results/rag_dense_paired.csv. {INTENDED_USE}")
        return
    rows, summary = run(a.backend)
    write(rows, summary)
    for k, v in summary.items():
        print(f"  {k:28s} {v:.3f}" if isinstance(v, float) else f"  {k:28s} {v}")
    missed = [r["id"] for r in rows if r["hit_at_5"] == 0]
    wrong = [r["id"] for r in rows if r["category"] == "out_of_scope" and r["retrieval"] == "SUCCESS"]
    print(f"  missed (answerable, not in top 5): {', '.join(missed) or 'none'}")
    print(f"  answered but out of scope:         {', '.join(wrong) or 'none'}")
    print(f"Saved results/rag_eval.csv and results/rag_eval_summary.csv. {INTENDED_USE}")


if __name__ == "__main__":
    main()
