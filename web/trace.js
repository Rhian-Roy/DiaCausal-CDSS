/* DiaCausal — the trace of each request run in THIS browser tab, for the Observability screen (docs/OBSERVABILITY.md).
 *
 * The website runs the whole pipeline on this device (guards.js, engine.js, evidence.js, explain.js, card.js); app.js records each
 * step here as it runs: name, component, start, duration, status, and a summary of IDs, codes, counts and settings. Never a patient
 * value, the question or a passage: the same rule as the server's traces (diacausal/observability/). Kept in memory for this tab only
 * (newest 50), never stored or sent; a reload or a sign-out clears them.
 *
 * Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.
 */
(function () {
  "use strict";
  const MAX = 50;
  const KEY = /^[A-Za-z][A-Za-z0-9_-]{0,40}$/;
  const TEXT = /^[A-Za-z0-9 _.:;@/#+,()=<>%§'*-]{0,120}$/;
  const REDACTED = "<not kept>";
  const PIPELINES = ["request", "guards", "ci", "rag", "llm", "output"];
  const traces = []; // newest first
  const listeners = new Set();
  const opened = Date.now() / 1000;

  function hex(n) {
    const bytes = new Uint8Array(n / 2);
    (window.crypto || globalThis.crypto).getRandomValues(bytes);
    return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
  }

  /** What a summary may hold: numbers, booleans, null, short label strings, and arrays / objects of them (the server's safe()). */
  function safe(v, depth = 0) {
    if (v === null || v === undefined) return null;
    if (typeof v === "boolean") return v;
    if (typeof v === "number") return Number.isFinite(v) ? Math.round(v * 1e4) / 1e4 : null;
    if (typeof v === "string") return TEXT.test(v) ? v : REDACTED;
    if (depth >= 4) return REDACTED;
    if (Array.isArray(v)) return v.slice(0, 60).map((x) => safe(x, depth + 1));
    if (typeof v === "object") {
      const out = {};
      for (const [k, x] of Object.entries(v).slice(0, 60)) if (KEY.test(k)) out[k] = safe(x, depth + 1);
      return out;
    }
    return REDACTED;
  }

  function layerStatus(spans, pipeline) {
    const found = spans.filter((s) => s.kind === "layer" && s.pipeline === pipeline).map((s) => s.status);
    for (const st of ["failed", "abstained", "not run"]) if (found.includes(st)) return st;
    return found.length ? "completed" : "not run";
  }

  /** The per-pipeline statuses and counts the request list shows (the server's rollup(), by pipeline). */
  function rollup(spans) {
    const failed = spans.filter((s) => s.status === "failed");
    return {
      ci_status: layerStatus(spans, "ci"), rag_status: layerStatus(spans, "rag"), llm_status: layerStatus(spans, "llm"),
      output_status: layerStatus(spans, "output"), n_spans: spans.length, n_errors: failed.length,
      n_warnings: spans.filter((s) => s.status === "abstained").length,
      failed_stage: failed.length ? failed[0].name : null, error_type: failed.length ? failed[0].error_type : null,
    };
  }

  function makeSpan(t, name, pipeline, component, kind) {
    const s = {
      span_id: String(++t._ids).padStart(3, "0"), parent_id: t._stack.length ? t._stack[t._stack.length - 1] : null, name,
      pipeline: PIPELINES.includes(pipeline) ? pipeline : "request", component, kind, start_ms: null, duration_ms: null,
      status: "not run", code: null, error_type: null, summary: {},
    };
    t.spans.push(s);
    return s;
  }

  const handle = (s) => ({
    note(obj) { Object.assign(s.summary, safe(obj || {})); },
    skip(code) { s.status = "skipped"; s.code = /^[A-Z][A-Z0-9_]{1,40}$/.test(code) ? code : "SKIPPED"; },
    abstain(code) { s.status = "abstained"; s.code = /^[A-Z][A-Z0-9_]{1,40}$/.test(code) ? code : "ABSTAINED"; },
  });

  function start(workflow, requestId) {
    const t = {
      trace_id: hex(16), request_id: /^[A-Za-z0-9_-]{1,64}$/.test(requestId || "") ? requestId : "-", workflow, source: "browser",
      started_at: Date.now() / 1000, ended_at: null, duration_ms: null, status: "running", code: null, http_status: null, context: {},
      spans: [], _t0: performance.now(), _ids: 0, _stack: [],
    };
    traces.unshift(t);
    if (traces.length > MAX) traces.length = MAX;
    t.span = (name, opts, fn) => span(t, name, opts, fn);
    t.notRun = (name, pipeline, component) => makeSpan(t, name, pipeline, component, "layer");
    t.step = (parentName, report) => { // a step engine.js reported (opts.step), as a child of the span that is open now
      const s = makeSpan(t, report.name, "ci", report.component, "step");
      s.start_ms = Math.round((report.start - t._t0) * 10) / 10;
      s.duration_ms = Math.round(report.duration_ms * 10) / 10;
      s.status = report.status;
      s.code = report.code || null;
      s.summary = safe(report.summary || {});
    };
    emit();
    return t;
  }

  /** Run fn(spanHandle) as one span of trace t (fn may be async). An exception is recorded by its NAME only and re-thrown. */
  function span(t, name, { pipeline = "request", component = "", kind = "layer" } = {}, fn) {
    const s = makeSpan(t, name, pipeline, component, kind);
    const t0 = performance.now();
    s.start_ms = Math.round((t0 - t._t0) * 10) / 10;
    t._stack.push(s.span_id);
    const done = (failed) => {
      s.duration_ms = Math.round((performance.now() - t0) * 10) / 10;
      if (failed) { s.status = "failed"; s.error_type = failed.name || "Error"; } else if (s.status === "not run") s.status = "completed";
      const i = t._stack.lastIndexOf(s.span_id);
      if (i >= 0) t._stack.splice(i, 1);
    };
    let out;
    try {
      out = fn(handle(s));
    } catch (e) {
      done(e);
      throw e;
    }
    if (out && typeof out.then === "function") {
      return out.then((v) => { done(null); return v; }, (e) => { done(e); throw e; });
    }
    done(null);
    return out;
  }

  /** End trace t: "blocked" (stopped by a check), "failed", "cancelled" (newer details replaced it before it was shown), "partial"
   *  (a layer abstained) or "completed". */
  function finish(t, { blocked = null, failed = false, cancelled = false, context = null } = {}) {
    if (!t || t.status !== "running") return;
    t.ended_at = Date.now() / 1000;
    t.duration_ms = Math.round((performance.now() - t._t0) * 10) / 10;
    const statuses = new Set(t.spans.filter((s) => s.kind === "layer").map((s) => s.status));
    t.status = failed || statuses.has("failed") ? "failed" : blocked ? "blocked" : cancelled ? "cancelled"
      : statuses.has("abstained") ? "partial" : "completed";
    t.code = blocked && /^[A-Z][A-Z0-9_]{1,40}$/.test(blocked) ? blocked : null;
    if (context) t.context = safe(context);
    emit();
  }

  // What each browser step produced, reduced to IDs, codes, counts and settings (the server's summaries.py, for the same objects).
  const INSUFFICIENT = { "Outside the cohort": "OUTSIDE_COHORT", "Too few similar patients": "LOW_OVERLAP", "Too uncertain": "TOO_UNCERTAIN" };
  const RETRIEVAL = { "the index is empty": "EMPTY_INDEX", "no approved passage matches": "NO_MATCH", "the passages found cover too few": "LOW_COVERAGE" };
  const code = (text, table) => (text ? Object.entries(table).find(([k]) => text.startsWith(k))?.[1] || "OTHER" : null);
  const describe = {
    guards: (c) => ({ status: c.status, checks: (c.checks || []).map((x) => ({ check: x.id, result: x.result })), code: c.code || null,
      shown_first: c.shown || null }),
    engine: (r) => ({
      applicable: r.applicable,
      options: (r.options || []).map((o) => ({ option: o.arm, status: o.status, rule_ids: (o.safety || []).map((s) => s.rule_id),
        why_no_estimate: code(o.insufficient_reason, INSUFFICIENT), method: o.confidence ? o.confidence.method : null,
        secondary_outcomes: Boolean(o.secondary) })),
      comparisons: (r.comparisons || []).map((c) => `${c.first}-${c.second}`), versions: r.versions, computed_on: "this device" }),
    retrieval: (raw, index) => ({
      status: raw.status, reason: code(raw.reason, RETRIEVAL), index_versions: index && index.versions,
      index: { chunks: index ? index.chunks.length : null, built: "web/evidence.json, made by python -m diacausal.rag.export_web",
        searches: ["BM25", "TF-IDF"], fusion: "reciprocal rank fusion", source_ranking_enabled: false },
      settings: index ? { top_k: index.config.top_k, rrf_k: index.config.rrf_k, min_bm25_score: index.config.min_bm25_score,
        min_query_coverage: index.config.min_query_coverage } : null,
      passages: (raw.passages || []).map((p, i) => ({ rank: i + 1, chunk_id: p._raw ? p._raw.chunk_id : p.chunk_id || null,
        source_id: p.citation ? p.citation.source_id : null, licence_bucket: p.citation ? p.citation.licence_bucket : null,
        withheld_dose_text: Boolean(index && p.text === index.withheld_text), scores: p.scores })) }),
    explanation: (note, index) => ({ writer: "template (explain.js; this page runs no model)", status: note.status,
      sentences: (note.sentences || []).length, cited_passages: [...new Set((note.sentences || []).flatMap((s) => s.cites || []))].sort((a, b) => a - b),
      no_dose_note: Boolean(index && note.note === index.no_dose_note) }),
    card: (c) => ({ claims: (c.claims || []).length, effect_rows: (c.effects || []).length,
      evidence_levels: (c.evidence_levels || []).map((lv) => ({ option: lv.option, level: lv.level })), excluded: (c.excluded || []).length,
      cautions: (c.cautions || []).length, abstain_notices: (c.abstain || []).length,
      drivers: Object.fromEntries(Object.entries(c.drivers || {}).map(([k, v]) => [k, v.length])) }),
  };

  function view(t) {
    const { span: _s, notRun: _n, step: _st, _t0, _ids, _stack, ...rest } = t;
    return { ...rest, ...rollup(t.spans) };
  }

  function list() { return traces.map(view); }
  function get(id) { const t = traces.find((x) => x.trace_id === id); return t ? view(t) : null; }
  function clear() { traces.length = 0; emit(); }
  function emit() { for (const fn of listeners) { try { fn(); } catch { /* a listener never breaks the work */ } } }
  function subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn); }

  /** The layers a stopped run never reached, listed as "not run" (no time), so the screen shows where it stopped. */
  function notRunAfter(t, layers, reached) {
    if (!t) return;
    const done = new Set(t.spans.filter((s) => s.kind === "layer").map((s) => s.name));
    for (const [name, pipeline, component] of layers) if (!done.has(name) && name !== reached) t.notRun(name, pipeline, component);
  }

  window.DiaCausalTrace = { start, finish, list, get, clear, subscribe, safe, rollup, describe, notRunAfter, opened, MAX, REDACTED };
})();
