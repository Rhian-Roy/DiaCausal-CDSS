"""Dense (sentence-embedding) index for the RAG: one local model embeds every chunk once; a question is embedded at search
time and compared with the chunks by cosine similarity. Its ranking is ONE MORE ranking in the reciprocal rank fusion of
diacausal/rag/retrieve/hybrid.py, next to BM25 and TF-IDF. Written from scratch for this project (no code from other RAG projects).

    OFF BY DEFAULT: diacausal/rag/dense.yaml  enabled: false.  The website never uses it (it keeps BM25 + TF-IDF).
    Dense search only REORDERS: it never adds a passage the keyword searches did not find and never changes whether the
    system abstains (hybrid.py decides abstention from the keyword ranking alone).

What is embedded: `index_text(chunk.text)`, the text with dose-like phrases removed (the same text BM25 indexes), so no dose
text ever enters an embedding. A chunk longer than the window (`window_words`, default 250 words; the chunks reach 399 words,
650 tokens, above the 512-token limit of both models) is cut into overlapping windows; a chunk's dense score is its BEST window.

Saved per model under knowledge_sources/index/dense/<model key>/:
    embeddings.npy     (windows x dimension) float32, L2-normalised
    chunks.jsonl       one line per window: chunk_id, window number, sha of the embedded text of that window
    index_meta.json    model name and revision, library version, date, chunk count, window count, dimension, window settings
The index is checked against the current corpus before every use (a hash of each embedded text): a stale index is an error
(DenseIndexError), never a silent fallback, so results never come from text that is no longer in the corpus.

    python -m diacausal.rag.index.dense build --model all      # (needs requirements-dense.txt) embed and save
    python -m diacausal.rag.index.dense check                  # is every saved index current? (no model needed)

`sentence_transformers` is imported only when a model is really used, so importing this module needs nothing but NumPy.

Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np

from diacausal.config import KNOWLEDGE_DIR, load_rag_config

CONFIG_PATH = Path(__file__).resolve().parents[1] / "dense.yaml"
INDEX_ROOT = KNOWLEDGE_DIR / "index" / "dense"
FILES = ("embeddings.npy", "chunks.jsonl", "index_meta.json")


class DenseIndexError(RuntimeError):
    """The dense index is missing, stale or does not match the model asked for."""


def load_dense_config(path: Path = CONFIG_PATH) -> dict:
    """The values of dense.yaml (every entry must have a source and a valid status: same loader as config.yaml)."""
    return load_rag_config(path)


def model_settings(cfg: dict, key: str | None = None) -> tuple[str, dict]:
    key = key or cfg["model"]
    if key not in cfg["models"]:
        raise DenseIndexError(f"unknown dense model {key!r}; choose one of {sorted(cfg['models'])}")
    return key, cfg["models"][key]


# ── windows and hashes ───────────────────────────────────────────────────────────────────────────────────────────

def windows(text: str, size: int, overlap: int) -> list[str]:
    """The text cut into windows of at most `size` words that overlap by `overlap` words; the last window always ends at
    the last word. A text of at most `size` words is one window, unchanged."""
    if overlap >= size:
        raise ValueError("the overlap must be smaller than the window")
    words = text.split()
    if len(words) <= size:
        return [text]
    step, out, start = size - overlap, [], 0
    while True:
        out.append(" ".join(words[start:start + size]))
        if start + size >= len(words):
            return out
        start += step


def text_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def window_rows(chunk_ids: Sequence[str], texts: Sequence[str], size: int, overlap: int) -> tuple[list[dict], list[str]]:
    """One row per window ({chunk_id, window, text_sha}) and the window texts, in chunk order."""
    rows, pieces = [], []
    for cid, text in zip(chunk_ids, texts):
        for number, piece in enumerate(windows(text, size, overlap)):
            rows.append({"chunk_id": cid, "window": number, "text_sha": text_sha(piece)})
            pieces.append(piece)
    return rows, pieces


# ── the embedder ─────────────────────────────────────────────────────────────────────────────────────────────────

class SentenceEmbedder:
    """A sentence-transformers model, loaded on first use (CPU). Vectors are L2-normalised, so a dot product is the cosine."""

    def __init__(self, hf_name: str, query_prefix: str = "", batch_size: int = 16):
        self.hf_name, self.query_prefix, self.batch_size = hf_name, query_prefix, int(batch_size)
        self._model = None

    @property
    def model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:  # pragma: no cover - only without requirements-dense.txt
                raise DenseIndexError("dense search needs the optional libraries: pip install -r requirements-dense.txt") from exc
            self._model = SentenceTransformer(self.hf_name, device="cpu")
        return self._model

    def embed_passages(self, texts: Sequence[str]) -> np.ndarray:
        return np.asarray(self.model.encode(list(texts), batch_size=self.batch_size, normalize_embeddings=True,
                                            show_progress_bar=False), dtype=np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        return self.embed_passages([self.query_prefix + text])[0]

    def max_tokens_of(self, texts: Sequence[str]) -> int:
        tokenizer = self.model.tokenizer
        return max(len(tokenizer(t, add_special_tokens=True)["input_ids"]) for t in texts)

    def revision(self) -> str:
        """The commit of the downloaded model files (the folder name in the local cache), or 'unknown'."""
        try:
            from huggingface_hub import try_to_load_from_cache

            path = try_to_load_from_cache(self.hf_name, "config.json")
            return Path(path).parent.name if path else "unknown"
        except Exception:  # noqa: BLE001 - provenance only
            return "unknown"

    def library_version(self) -> str:
        import sentence_transformers

        return f"sentence-transformers {sentence_transformers.__version__}"


# ── the index ────────────────────────────────────────────────────────────────────────────────────────────────────

@dataclass
class DenseIndex:
    """Embeddings of every window of every chunk, ready to score a question."""

    embeddings: np.ndarray  # (windows, dimension), normalised
    rows: list[dict]
    chunk_ids: list[str]  # the retriever's chunk order
    embedder: object
    meta: dict

    def __post_init__(self):
        position = {cid: i for i, cid in enumerate(self.chunk_ids)}
        self._chunk_of_row = np.array([position[r["chunk_id"]] for r in self.rows], dtype=int)

    def scores(self, question: str) -> np.ndarray:
        """(n_chunks,) cosine similarity of the question to each chunk: the best of its windows."""
        q = self.embedder.embed_query(question)
        sims = self.embeddings @ q
        best = np.full(len(self.chunk_ids), -np.inf)
        np.maximum.at(best, self._chunk_of_row, sims)
        return best


def index_dir(model_key: str, root: Path | None = None) -> Path:
    return Path(root or INDEX_ROOT) / model_key


def build(chunk_ids: Sequence[str], texts: Sequence[str], cfg: dict, model_key: str | None = None, embedder=None,
          root: Path | None = None, today: str | None = None) -> Path:
    """Embed every window once and save the three files. `texts` are the dose-free texts of the chunks."""
    key, model = model_settings(cfg, model_key)
    rows, pieces = window_rows(chunk_ids, texts, int(cfg["window_words"]), int(cfg["window_overlap_words"]))
    embedder = embedder or SentenceEmbedder(model["hf_name"], model["query_prefix"], cfg["batch_size"])
    longest = embedder.max_tokens_of(pieces) if hasattr(embedder, "max_tokens_of") else None
    if longest is not None and longest > int(model["max_tokens"]):
        raise DenseIndexError(f"a window has {longest} tokens, above the model's {model['max_tokens']}: lower window_words")
    embeddings = embedder.embed_passages(pieces)
    out = index_dir(key, root)
    out.mkdir(parents=True, exist_ok=True)
    np.save(out / "embeddings.npy", embeddings.astype(np.float32))
    (out / "chunks.jsonl").write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8")
    meta = {"model_key": key, "model": model["hf_name"], "model_revision": getattr(embedder, "revision", lambda: "unknown")(),
            "library": getattr(embedder, "library_version", lambda: "stand-in")(), "date": today or date.today().isoformat(),
            "chunk_count": len(chunk_ids), "window_count": len(rows), "dimension": int(embeddings.shape[1]),
            "window_words": int(cfg["window_words"]), "window_overlap_words": int(cfg["window_overlap_words"]),
            "longest_window_tokens": longest, "query_prefix": model["query_prefix"], "normalised": True,
            "licence": model["licence"]}
    (out / "index_meta.json").write_text(json.dumps(meta, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return out


def load(chunk_ids: Sequence[str], texts: Sequence[str], cfg: dict, model_key: str | None = None, embedder=None,
         root: Path | None = None) -> DenseIndex:
    """Read the saved index and prove it is current: the same windows, with the same embedded text, for the same chunks."""
    key, model = model_settings(cfg, model_key)
    folder = index_dir(key, root)
    missing = [f for f in FILES if not (folder / f).exists()]
    if missing:
        raise DenseIndexError(f"no dense index for {key} ({', '.join(missing)} missing): run "
                              f"python -m diacausal.rag.index.dense build --model {key}")
    meta = json.loads((folder / "index_meta.json").read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in (folder / "chunks.jsonl").read_text(encoding="utf-8").splitlines() if line]
    embeddings = np.load(folder / "embeddings.npy")
    expected, _ = window_rows(chunk_ids, texts, int(cfg["window_words"]), int(cfg["window_overlap_words"]))
    if meta["model"] != model["hf_name"] or meta["query_prefix"] != model["query_prefix"]:
        raise DenseIndexError(f"the saved index was made with {meta['model']}, not {model['hf_name']}: rebuild it")
    if rows != expected or meta["chunk_count"] != len(chunk_ids) or embeddings.shape != (len(rows), meta["dimension"]):
        raise DenseIndexError(f"the dense index for {key} is stale (the corpus or the window settings changed): rebuild it")
    embedder = embedder or SentenceEmbedder(model["hf_name"], model["query_prefix"], cfg["batch_size"])
    return DenseIndex(embeddings=embeddings, rows=rows, chunk_ids=list(chunk_ids), embedder=embedder, meta=meta)


def for_retriever(chunk_ids: Sequence[str], texts: Sequence[str], cfg: dict | None = None, embedder=None,
                  root: Path | None = None) -> DenseIndex | None:
    """What the Retriever calls: None while `enabled` is false (the default), the checked index when it is true."""
    cfg = cfg or load_dense_config()
    if not cfg["enabled"] or not chunk_ids:
        return None
    return load(chunk_ids, texts, cfg, embedder=embedder, root=root)


# ── command line ─────────────────────────────────────────────────────────────────────────────────────────────────

def _chunk_texts() -> tuple[list[str], list[str]]:
    from diacausal.rag.ingest.licence_gate import ingest
    from diacausal.rag.retrieve.hybrid import index_text

    chunks = ingest()
    return [c.chunk_id for c in chunks], [index_text(c.text) for c in chunks]


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build", help="embed every chunk once and save the index")
    b.add_argument("--model", default="all", help="a key of dense.yaml `models`, or all")
    sub.add_parser("check", help="is every saved index current? (needs no model)")
    a = ap.parse_args(argv)
    cfg = load_dense_config()
    ids, texts = _chunk_texts()
    keys = sorted(cfg["models"]) if getattr(a, "model", "all") == "all" else [a.model]
    if a.command == "build":
        for key in keys:
            out = build(ids, texts, cfg, key)
            print(f"{key}: saved {out.relative_to(KNOWLEDGE_DIR.parent)} ({json.loads((out / 'index_meta.json').read_text())['window_count']} windows)")
        return
    bad = 0
    for key in sorted(cfg["models"]):
        try:
            load(ids, texts, cfg, key, embedder=object())
            print(f"{key}: current")
        except DenseIndexError as exc:
            bad += 1
            print(f"{key}: {exc}")
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
