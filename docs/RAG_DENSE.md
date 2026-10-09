# Dense search for the RAG (P18)

> Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

**Status: built, OFF.** `diacausal/rag/dense.yaml` has `enabled: false`. Nobody should switch it on until the team has read the numbers below and chosen a model.

## What it is
A local sentence-embedding model embeds every chunk once (`python -m diacausal.rag.index.dense build --model all`). At search time the
question is embedded and compared with every chunk by cosine similarity; that ranking is **one more ranking in the reciprocal rank
fusion** of `diacausal/rag/retrieve/hybrid.py`, next to BM25 and TF-IDF. Nothing else changes:

- **It only reorders.** The candidates are exactly those the keyword searches found (BM25 or TF-IDF score above 0), and the decision to abstain is taken from the keyword ranking alone, so dense search can never answer a question the system would otherwise refuse, nor refuse one it would answer. Tests prove both on 72 questions.
- **Dense gets the original question**, never the expanded sub-queries of `query_processing.py`.
- **No dose text is embedded**: the embedded text is `index_text(chunk.text)` (dose phrases removed), the same text BM25 indexes.
- **The website is unchanged** (BM25 + TF-IDF only; `web/evidence.json` is byte-identical; the flag lives in its own file so the evidence fingerprint of `config.yaml` does not move).
- **Retriever interface unchanged**: `Retriever(chunks, config)`, `search(question, plan)`. A passage gains a `dense` score only when the flag is on.

## The saved index (`knowledge_sources/index/dense/<model>/`)
`embeddings.npy` (windows x dimension, float32, normalised), `chunks.jsonl` (chunk id, window number, hash of the embedded text), `index_meta.json` (model, model revision, library version, date, chunk count 78, window count 111, dimension, window settings, longest window in tokens). Chunks reach 650 tokens, above the 512 of both models, so a chunk is cut into 250-word windows with 50 words of overlap (longest window 452 tokens) and scored by its best window. The index is verified against the corpus before every use; **a stale index is an error, never a silent fallback.** `python -m diacausal.rag.index.dense check` needs no model.

## The two models (from their model cards, read in October 2026)
| | `BAAI/bge-small-en-v1.5` | `NeuML/pubmedbert-base-embeddings` |
|---|---|---|
| Licence | MIT | Apache-2.0 |
| Size / vector | 33.4M parameters, 384 | 0.1B parameters, 768 |
| Max input | 512 tokens | 512 tokens |
| Query instruction | "Represent this sentence for searching relevant passages: " (queries only) | none stated, none used |
| Trained for | general retrieval | PubMed title-abstract pairs (base: PubMedBERT) |

Libraries: `requirements-dense.txt` (`sentence-transformers==6.1.0`, `transformers==5.18.0`, `torch==2.14.1`; pip-audit clean; not in the engine or website requirements). CI installs none of it; the tests use a stand-in embedder, and the one real-model test is skipped without the downloaded models.

## Evaluation (`python -m diacausal.rag.evaluate --dense-ablation`)
Relevant = a returned passage with the question's expected source and section. Ranking = the top 5 the retriever returns (an abstention scores 0). nDCG@5 uses binary gain over the number of relevant chunks in the index. The 45 answerable gold questions are split by a seeded, stratified split into **30 dev and 15 held-out** (`dense.yaml`: seed 2026); choose a model on dev and look at held-out once.

| split (n) | variant | recall@5 | MRR | nDCG@5 |
|---|---|---:|---:|---:|
| dev (30) | dense off | 0.933 | 0.637 | 0.642 |
| | bge-small-en-v1.5 | 0.933 | 0.662 | 0.648 |
| | pubmedbert-base-embeddings | 0.967 | 0.652 | 0.663 |
| held-out (15) | dense off | 1.000 | 0.758 | 0.727 |
| | bge-small-en-v1.5 | 1.000 | 0.802 | 0.743 |
| | pubmedbert-base-embeddings | 1.000 | 0.791 | 0.736 |
| all (45) | dense off | 0.956 | 0.677 | 0.670 |
| | bge-small-en-v1.5 | 0.956 | 0.709 | 0.680 |
| | pubmedbert-base-embeddings | 0.978 | 0.699 | 0.687 |

**Honest reading: no clear gain.** Both models move MRR up by about 0.02 to 0.03 and nDCG@5 by 0.01 to 0.02, but every paired 95% bootstrap interval (`results/rag_dense_paired.csv`) includes zero or touches it (the few intervals that start exactly at 0 come from one or two wins and no loss on a single split, which is a handful of questions). Over all 45 questions: bge-small, 5 wins / 2 losses on MRR; PubMedBERT, 5 wins / 4 losses. Recall@5 is already 0.956 without dense search, so there is little to gain, and 15 questions cannot show a small difference. **Recommendation: keep it off** for the 30 October demo; if the team wants it on, bge-small is the smaller model with the better held-out numbers, but that is a choice for the team and the doctor, not a result.

The gold set is small, written by the team, and its questions share words with the passages (they were written from them), which favours keyword search. A larger, independently written set could change the picture.

## To switch it on (after reading the above)
1. In `diacausal/rag/dense.yaml` set `enabled: true` and `model: <key>`.
2. `pip install -r requirements-dense.txt`; the first start downloads the model once (about 130 MB and 440 MB).
3. If the corpus changes, rebuild: `python -m diacausal.rag.index.dense build --model all`, then re-run the evaluation.
