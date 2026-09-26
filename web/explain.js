/*
 * DiaCausal explanations, in the browser — a mirror of the template writer and the citation
 * checker in diacausal_rag/explain.py.
 *
 * Research prototype for clinician evaluation; not a marketed medical device;
 * not for unsupervised clinical use.
 *
 * template(): quotes the passage sentences that share the most words with the question, each with
 * its passage number; it cannot invent anything. fromModel(): runs a model's answer (Gemini, via
 * the DiaCausal server) through checkAnswer(); if any sentence fails, the template answer is shown
 * instead and the reply says why. Every setting comes from evidence.json. tests/web/test_web.py
 * checks this file gives the same answers as Python.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory(require("./evidence.js"));
  else root.DiaCausalExplain = factory(root.DiaCausalEvidence);
})(typeof self !== "undefined" ? self : this, function (Evidence) {
  "use strict";

  const SPLIT = /(?:(?<=[.!?])|(?<=\]))\s+(?=[A-Z0-9"“(•-])/;
  const ANSWER_SPLIT = /(?<=\])\s+|(?<=[.!?])\s+(?=[A-Z0-9"“(•-])/;
  const CITES = /\s*((?:\[\d+\]\s*)+)[.!?]?\s*$/;
  const BULLET = /^[-•]\s*/;
  const STARTS = /^[A-Z0-9"“(\[]/;
  const ENDS = /[.!?:)\]”"]$/;

  const content = (index, text) => new Set(Evidence._internals.bm25Tokens(index, text));

  /** explain.sentences(): passage text -> sentences, bullet marks removed. */
  function sentences(text) {
    const parts = [];
    for (const line of text.split(/\s+(?=[•]\s)|\s+-\s(?=[A-Z])/)) {
      for (let s of line.trim().split(SPLIT)) {
        s = s.replace(BULLET, "").trim();
        if (s.length > 1) parts.push(s);
      }
    }
    return parts;
  }

  /** explain._weighted_overlap(): IDF-weighted share of the question's words in a sentence (sorted sums). */
  function weightedOverlap(index, q, words) {
    const idf = index.bm25.idf;
    const vals = Object.values(idf);
    const top = vals.length ? Math.max(...vals) : 1;
    const w = (t) => (Object.prototype.hasOwnProperty.call(idf, t) ? idf[t] : top);
    const sorted = [...q].sort();
    let total = 0, got = 0;
    for (const t of sorted) total += w(t);
    for (const t of sorted) if (words.has(t)) got += w(t);
    return total ? got / total : 0;
  }

  function usable(index, passages) {
    return passages.map((p, i) => [i + 1, p]).filter(([, p]) => p.text !== index.withheld_text);
  }

  function reply(index, question, backend, status, items, note = "") {
    return { status, question, backend, sentences: items, note, intended_use: index.intended_use };
  }

  function template(index, question, evidence) {
    const cfg = index.config;
    if (evidence.status !== "SUCCESS") return reply(index, question, "template", "INSUFFICIENT_EVIDENCE", [], evidence.reason || "");
    const dose = new RegExp(index.strict_dose_pattern, "i");
    const q = content(index, question);
    const scored = [];
    for (const [n, p] of usable(index, evidence.passages)) {
      sentences(p.text).forEach((s, k) => {
        if (dose.test(s) || !q.size || !STARTS.test(s) || !ENDS.test(s)) return;
        const overlap = weightedOverlap(index, q, content(index, s));
        if (overlap > 0) scored.push([-overlap, n, k, s]);
      });
    }
    scored.sort((a, b) => a[0] - b[0] || a[1] - b[1] || a[2] - b[2]);
    const items = [];
    const per = {};
    for (const [, n, , s] of scored) {
      if ((per[n] || 0) >= 2) continue;
      per[n] = (per[n] || 0) + 1;
      items.push({ text: s, cites: [n] });
      if (items.length >= cfg.explain_max_sentences) break;
    }
    if (!items.length) {
      return reply(index, question, "template", "INSUFFICIENT_EVIDENCE", [], "the passages found do not contain a sentence about this question");
    }
    return reply(index, question, "template", "SUCCESS", items);
  }

  /** explain.check_answer(): [items, problems]; problems empty = the answer passes. */
  function checkAnswer(index, text, passages) {
    const problems = [];
    if (new RegExp(index.strict_dose_pattern, "i").test(text)) problems.push("the answer contains dose-like text");
    const shown = new Map(usable(index, passages));
    const items = [];
    for (let s of text.trim().split(ANSWER_SPLIT)) {
      s = s.trim();
      if (!s) continue;
      const m = s.match(CITES);
      if (!m) { problems.push(`a sentence has no citation: '${s.slice(0, 60)}'`); continue; }
      const cites = [...new Set((m[1].match(/\d+/g) || []).map(Number))].sort((a, b) => a - b);
      const body = s.slice(0, m.index).replace(/[ .]+$/, "") + ".";
      const missing = cites.filter((c) => !shown.has(c));
      if (missing.length) { problems.push(`cites passage(s) [${missing.join(", ")}] that were not shown`); continue; }
      const words = content(index, body);
      const support = new Set();
      for (const c of cites) for (const t of content(index, shown.get(c).text)) support.add(t);
      let common = 0;
      for (const t of words) if (support.has(t)) common++;
      const share = words.size ? common / words.size : 0;
      if (share < index.config.explain_min_support) {
        problems.push(`only ${Math.round(share * 100)}% of a sentence's words are in the passages it cites: '${body.slice(0, 60)}'`);
        continue;
      }
      items.push({ text: body, cites });
    }
    if (!items.length && !problems.length) problems.push("empty answer");
    return [items, problems];
  }

  function doseQuestion(index, question) {
    return new RegExp(index.dose_question_pattern, "i").test(question);
  }

  /** The offline answer: always available, never leaves the device. */
  function explain(index, question, evidence) {
    if (doseQuestion(index, question)) return reply(index, question, "template", "INSUFFICIENT_EVIDENCE", [], index.no_dose_note);
    return template(index, question, evidence);
  }

  /** A model's answer (text) -> checked reply, or the template with a note saying why not. */
  function fromModel(index, question, evidence, backend, text) {
    if (doseQuestion(index, question)) return reply(index, question, backend, "INSUFFICIENT_EVIDENCE", [], index.no_dose_note);
    if (text.trim() === "INSUFFICIENT_EVIDENCE") {
      return reply(index, question, backend, "INSUFFICIENT_EVIDENCE", [], "the model found no answer in the passages");
    }
    const [items, problems] = checkAnswer(index, text, evidence.passages);
    if (problems.length) {
      const fallback = template(index, question, evidence);
      fallback.note = `${backend} answer failed the citation check (${problems[0]}); showing quoted sentences instead`;
      return fallback;
    }
    return reply(index, question, backend, "SUCCESS", items.slice(0, index.config.explain_max_sentences));
  }

  return { explain, fromModel, template, checkAnswer, sentences, doseQuestion };
});
