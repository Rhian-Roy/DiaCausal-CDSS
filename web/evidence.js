/*
 * DiaCausal evidence search (RAG retrieval), in the browser — a line-by-line mirror of
 * diacausal_rag/retrieve.py.
 *
 * Research prototype for clinician evaluation; not a marketed medical device;
 * not for unsupervised clinical use.
 *
 * The index (word counts, TF-IDF vectors, citations) comes from evidence.json, which Python
 * writes (python -m diacausal_rag.export_web). Only licence-cleared, team-confirmed sources are
 * in it; passages with dose-like text were withheld before export. The question never leaves the
 * device. tests/web/test_web.py checks this file gives exactly the same passages and scores as
 * the Python retriever.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.DiaCausalEvidence = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // Python round(x, n): round half to even on the exact binary value.
  function roundN(x, n) {
    const f = 10 ** n;
    const scaled = x * f;
    const r = Math.round(scaled);
    const tie = Math.abs(scaled - Math.trunc(scaled)) === 0.5;
    const v = tie && r % 2 !== 0 ? r - 1 : r;
    return v / f === 0 ? 0 : v / f;
  }

  /** retrieve.tokens(): lower-case words (with inner hyphens), stop words removed — for BM25. */
  function bm25Tokens(index, text) {
    const stop = index._stop || (index._stop = new Set(index.stop_words));
    const re = new RegExp(index.bm25_token_pattern, "g");
    return (text.toLowerCase().match(re) || []).filter((t) => !stop.has(t));
  }

  /** sklearn TfidfVectorizer's analyzer: \b\w\w+\b words, stop words removed, then 1- and 2-grams. */
  function tfidfTerms(index, text) {
    const stop = index._stop || (index._stop = new Set(index.stop_words));
    const words = (text.toLowerCase().match(/[\p{L}\p{N}\p{M}_]{2,}/gu) || []).filter((t) => !stop.has(t));
    const [lo, hi] = index.tfidf.ngram_range;
    const terms = [];
    for (let n = lo; n <= hi; n++) {
      for (let i = 0; i + n <= words.length; i++) terms.push(words.slice(i, i + n).join(" "));
    }
    return terms;
  }

  function bm25Scores(index, question) {
    const q = bm25Tokens(index, question);
    const { bm25_k1: k1, bm25_b: b } = index.config;
    const { idf, avgdl } = index.bm25;
    return index.chunks.map((c) => {
      let s = 0;
      for (const t of q) {
        const f = c.bm25.tf[t];
        if (f) s += idf[t] * f * (k1 + 1) / (f + k1 * (1 - b + b * c.bm25.len / avgdl));
      }
      return s;
    });
  }

  function vectorScores(index, question) {
    const counts = new Map();
    for (const t of tfidfTerms(index, question)) {
      const j = index.tfidf.vocabulary[t];
      if (j !== undefined) counts.set(j, (counts.get(j) || 0) + 1);
    }
    const q = new Map();
    let norm = 0;
    for (const [j, tf] of counts) {
      const v = (index.tfidf.sublinear_tf ? 1 + Math.log(tf) : tf) * index.tfidf.idf[j];
      q.set(j, v);
      norm += v * v;
    }
    norm = Math.sqrt(norm);
    return index.chunks.map((c) => {
      if (!norm) return 0;
      let s = 0;
      for (const [j, v] of q) s += (v / norm) * (c.tfidf[j] || 0);
      return s;
    });
  }

  function argsortDesc(scores) {
    return scores.map((_, i) => i).sort((a, b) => scores[b] - scores[a]); // stable, like Python's sorted
  }

  /** Reciprocal rank fusion: score = sum over retrievers of 1 / (k + rank). Keeps first-seen order on ties. */
  function rrf(rankings, k) {
    const fused = new Map();
    for (const ranking of rankings) {
      ranking.forEach((idx, r) => fused.set(idx, (fused.get(idx) || 0) + 1 / (k + r + 1)));
    }
    return fused;
  }

  function abstain(index, question, reason) {
    return { status: "INSUFFICIENT_EVIDENCE", question, reason, passages: [], intended_use: index.intended_use };
  }

  /** One question -> the same evidence JSON as Retriever.search(). */
  function search(index, question, opts = {}) {
    const k = index.config.top_k;
    if (!index.chunks.length) return abstain(index, question, "the index is empty (no licence-cleared documents ingested yet)");
    const bm = bm25Scores(index, question);
    const vec = vectorScores(index, question);
    const fused = rrf([argsortDesc(bm), argsortDesc(vec)], index.config.rrf_k);
    const order = [...fused.keys()].sort((a, b) => fused.get(b) - fused.get(a)).slice(0, k); // reranker slot: identity
    if (Math.max(...bm) < index.config.min_bm25_score) {
      return abstain(index, question, "no approved passage matches this question well enough");
    }
    const q = new Set(bm25Tokens(index, question));
    let found = 0;
    for (const t of q) if (order.some((i) => index.chunks[i].bm25.tf[t])) found++;
    if (q.size && found / q.size < (index.config.min_query_coverage || 0)) {
      return abstain(index, question, "the passages found cover too few of the question's words");
    }
    const dose = new RegExp(index.dose_pattern, "i");
    const passages = order.map((i) => {
      const c = index.chunks[i];
      const p = {
        text: c.withheld || dose.test(c.text) ? index.withheld_text : c.text,
        citation: c.citation,
        scores: { bm25: roundN(bm[i], 4), vector: roundN(vec[i], 4), rrf: roundN(fused.get(i), 5) },
      };
      if (opts.raw) p._raw = { chunk_id: c.chunk_id, bm25: bm[i], vector: vec[i], rrf: fused.get(i) };
      return p;
    });
    return { status: "SUCCESS", question, passages, intended_use: index.intended_use };
  }

  return { search, _internals: { bm25Tokens, tfidfTerms, bm25Scores, vectorScores, rrf, roundN } };
});
