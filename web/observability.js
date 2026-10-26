/* DiaCausal — the Observability screen (#observability; docs/OBSERVABILITY.md).
 *
 * Two sources of REAL execution records, never examples:
 *   - this browser tab: every Compare, question and Investigate search run on this device (trace.js; memory only, newest 50);
 *   - this computer's server (clinic mode only, when the page is served by the local DiaCausal server): every POST /api/v1/ask, stored
 *     on this computer (GET ./api/v1/observability/...; the server answers only requests from the same computer).
 * On the public website there is no server, so the page makes no request for traces and shows this tab's runs only.
 * Uses h(), svg(), icon(), CLINIC and MODEL from app.js (loaded before this file). No inline style: classes from styles.css only.
 *
 * Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.
 */
(function () {
  "use strict";
  const API = "./api/v1/observability";
  const PAGE = 25;
  const PIPE = { guards: "Input checks", ci: "Causal inference", rag: "Retrieval (RAG)", llm: "Explanation (LLM)", output: "Output", request: "Request" };
  const STATUS_CLASS = { completed: "obs-ok", partial: "obs-warn", abstained: "obs-warn", blocked: "obs-warn", failed: "obs-bad",
    running: "obs-run", skipped: "obs-muted", "not run": "obs-muted", cancelled: "obs-muted" };
  const STATUS_WORD = { completed: "Completed", partial: "Partial", abstained: "Abstained", blocked: "Blocked", failed: "Failed", running: "Running",
    skipped: "Skipped", "not run": "Not run", cancelled: "Cancelled" };
  const state = { source: "browser", server: null, q: "", status: "", pipeline: "", problems: false, sort: "time-desc", offset: 0,
    trace: null, spanFilter: "all", unsubscribe: null, rows: [], total: 0, summary: null, engine: null, error: null };

  const root = () => document.getElementById("obs-root");
  const fmtTime = (s) => (s ? new Date(s * 1000).toLocaleString("en-IN") : "—");
  const fmtMs = (ms) => (ms === null || ms === undefined ? "—" : ms >= 1000 ? `${(ms / 1000).toFixed(2)} s` : `${ms.toFixed(1)} ms`);
  const pct = (x) => (x === null || x === undefined ? "—" : `${(100 * x).toFixed(1)}%`);
  const badge = (status) => h("span", { class: `badge obs-badge ${STATUS_CLASS[status] || "obs-muted"}` }, STATUS_WORD[status] || status || "—");
  const label = (k) => k.replace(/_/g, " ");

  async function getJSON(path) {
    const r = await fetch(`${API}${path}`, { cache: "no-store" });
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(body.message || `The server answered ${r.status}.`);
    return body;
  }

  // ── where the records come from ─────────────────────────────────────────
  async function detectServer() {
    if (state.server !== null) return state.server;
    if (typeof CLINIC === "undefined" || !CLINIC) { state.server = false; return false; } // the public site: no request at all
    try { await getJSON("/summary"); state.server = true; } catch { state.server = false; }
    return state.server;
  }

  function browserRows() {
    const T = window.DiaCausalTrace;
    let rows = T ? T.list() : [];
    if (state.q) rows = rows.filter((t) => t.trace_id.startsWith(state.q) || t.request_id.startsWith(state.q));
    if (state.status) rows = rows.filter((t) => t.status === state.status);
    if (state.pipeline) rows = rows.filter((t) => t[`${state.pipeline}_status`] !== "not run");
    if (state.problems) rows = rows.filter((t) => t.n_errors || t.n_warnings || ["failed", "blocked"].includes(t.status));
    const [key, dir] = state.sort.split("-");
    const val = (t) => (key === "duration" ? t.duration_ms ?? -1 : t.started_at);
    rows.sort((a, b) => (dir === "asc" ? val(a) - val(b) : val(b) - val(a)));
    return rows;
  }

  function browserSummary(all) {
    const by = (s) => all.filter((t) => t.status === s).length;
    const done = all.map((t) => t.duration_ms).filter((x) => x !== null).sort((a, b) => a - b);
    const at = (p) => (done.length ? done[Math.min(done.length - 1, Math.round(p * (done.length - 1)))] : null);
    const fails = (p) => all.filter((t) => t[`${p}_status`] === "failed").length;
    return { total: all.length, by_status: { completed: by("completed"), partial: by("partial"), blocked: by("blocked"), failed: by("failed"),
      cancelled: by("cancelled") }, running: by("running"), answered_share: all.length ? (by("completed") + by("partial")) / all.length : null,
    duration_ms: { mean: done.length ? done.reduce((a, b) => a + b, 0) / done.length : null, p50: at(0.5), p95: at(0.95), n: done.length },
    failures: { ci: fails("ci"), rag: fails("rag"), llm: fails("llm"), output: fails("output") },
    recent_problems: all.filter((t) => t.n_errors || t.n_warnings || ["failed", "blocked"].includes(t.status)).slice(0, 10) };
  }

  async function load() {
    state.error = null;
    if (state.source === "server") {
      try {
        const [key, dir] = state.sort.split("-");
        const params = new URLSearchParams({ sort: key, order: dir, limit: String(PAGE), offset: String(state.offset) });
        if (state.q) params.set("q", state.q);
        if (state.status) params.set("status", state.status);
        if (state.pipeline) params.set("pipeline", state.pipeline);
        if (state.problems) params.set("problems", "true");
        const [list, summary] = await Promise.all([getJSON(`/traces?${params}`), getJSON("/summary")]);
        state.rows = list.traces;
        state.total = list.total;
        state.summary = { ...summary.stored, running: summary.running };
        if (!state.engine) state.engine = await getJSON("/engine").catch(() => null);
      } catch (e) {
        state.rows = []; state.total = 0; state.summary = null; state.error = e.message;
      }
    } else {
      const all = window.DiaCausalTrace ? window.DiaCausalTrace.list() : [];
      const rows = browserRows();
      state.total = rows.length;
      state.rows = rows.slice(state.offset, state.offset + PAGE);
      state.summary = browserSummary(all);
    }
  }

  async function traceDoc(id) {
    if (state.source === "server") return (await getJSON(`/traces/${encodeURIComponent(id)}`)).trace;
    return window.DiaCausalTrace ? window.DiaCausalTrace.get(id) : null;
  }

  // ── drawing ─────────────────────────────────────────────────────────────
  function sourceSwitch() {
    const opt = (value, text, disabled) => [
      h("input", { type: "radio", name: "obs-src", id: `obs-src-${value}`, value, checked: state.source === value ? "" : null, disabled: disabled ? "" : null }),
      h("label", { for: `obs-src-${value}` }, icon("check", 18, "tick"), text)];
    const seg = h("div", { class: "seg", role: "radiogroup", "aria-label": "Where the records come from" },
      ...opt("browser", "This browser tab"), ...(state.server ? opt("server", "This computer's server (stored)") : []));
    seg.addEventListener("change", (e) => { state.source = e.target.value; state.offset = 0; state.trace = null; go(); });
    const scope = state.source === "server"
      ? "Every request answered by the DiaCausal server on this computer (POST /api/v1/ask), stored on this computer: the newest 1,000 for 30 days. Readable only on this computer."
      : `Every Compare, question and Investigate search run in this tab since it opened at ${new Date(window.DiaCausalTrace.opened * 1000).toLocaleTimeString("en-IN")}. `
        + `Kept in memory only (the newest ${window.DiaCausalTrace.MAX}); a reload or a sign-out clears them. Nothing is sent anywhere.`;
    const note = state.server === false && typeof CLINIC !== "undefined" && CLINIC
      ? "The local server's traces could not be read." : !state.server ? "On this website everything runs in your browser, so only this tab's runs exist. On the clinic laptop the server's stored traces appear here too." : null;
    return h("section", { class: "card card--flat stack" }, h("h2", {}, "Records"), seg, h("p", { class: "field__hint" }, scope),
      note ? h("p", { class: "field__hint" }, note) : null);
  }

  function tiles() {
    const s = state.summary;
    if (!s) return null;
    const tile = (v, t) => h("div", { class: "tile" }, h("b", {}, String(v)), h("span", {}, t));
    const scope = state.source === "server" ? "all stored requests" : "this tab";
    return h("section", { class: "card card--flat stack", "aria-labelledby": "obs-sum-h" },
      h("div", { class: "row" }, h("h2", { id: "obs-sum-h" }, "Summary"), h("span", { class: "badge" }, `Calculated from ${scope}`)),
      h("div", { class: "tiles" },
        tile(s.total, "Requests"), tile(s.by_status.completed, "Completed"), tile(s.by_status.partial, "Partial (a layer abstained)"),
        tile(s.by_status.blocked, "Blocked by a check"), tile(s.by_status.failed, "Failed"), tile(s.running || 0, "Running now"),
        tile(pct(s.answered_share), "Answered (completed or partial)"), tile(fmtMs(s.duration_ms.mean), "Mean duration"),
        tile(fmtMs(s.duration_ms.p95), "95th percentile duration"), tile(s.failures.ci, "Causal inference failures"),
        tile(s.failures.rag, "Retrieval failures"), tile(s.failures.llm, "Explanation failures")),
      state.source === "browser" && s.by_status.cancelled ? h("p", { class: "field__hint" },
        `${s.by_status.cancelled} cancelled: newer details replaced them before they were shown.`) : null,
      h("p", { class: "field__hint" }, "Durations are measured around the real calls (performance.now in the browser, perf_counter on the server). Partial means an answer was shown although a layer could not give its part (for example no evidence passed the retrieval checks)."));
  }

  function problems() {
    const s = state.summary;
    if (!s || !s.recent_problems || !s.recent_problems.length) return null;
    return h("section", { class: "card card--flat stack", "aria-labelledby": "obs-prob-h" }, h("h2", { id: "obs-prob-h" }, "Recent errors and warnings"),
      h("div", { class: "tablewrap" }, h("table", { class: "rtable" },
        h("thead", {}, h("tr", {}, ...["Time", "Trace", "Outcome", "Stage", "Code or error", "Errors / warnings"].map((t) => h("th", { scope: "col" }, t)))),
        h("tbody", {}, ...s.recent_problems.map((p) => h("tr", {},
          h("td", { "data-label": "Time" }, fmtTime(p.started_at)),
          h("td", { "data-label": "Trace" }, openButton(p.trace_id, p.request_id)),
          h("td", { "data-label": "Outcome" }, badge(p.status)),
          h("td", { "data-label": "Stage" }, p.failed_stage || (p.status === "blocked" ? "input checks" : "a layer abstained")),
          h("td", { "data-label": "Code or error" }, p.error_type || p.code || "—"),
          h("td", { "data-label": "Errors / warnings" }, `${p.n_errors || 0} / ${p.n_warnings || 0}`)))))));
  }

  function openButton(traceId, requestId) {
    const b = h("button", { class: "btn btn--ghost obs-open", type: "button", "data-trace": traceId }, h("code", {}, traceId.slice(0, 8)), requestId ? ` · ${requestId}` : "");
    b.addEventListener("click", () => { state.trace = traceId; go(true); });
    return b;
  }

  function controls() {
    const sel = (id, labelText, options, value) => h("div", { class: "field obs-field" }, h("label", { class: "field__label", for: id }, labelText),
      h("select", { class: "select", id }, ...options.map(([v, t]) => h("option", { value: v, selected: v === value ? "" : null }, t))));
    const search = h("input", { class: "input", id: "obs-q", type: "search", value: state.q, placeholder: "Trace ID or request ID", autocomplete: "off",
      spellcheck: "false", maxlength: "64" });
    const box = h("form", { class: "obs-controls", role: "search" },
      h("div", { class: "field obs-field obs-field--q" }, h("label", { class: "field__label", for: "obs-q" }, "Search"), search),
      sel("obs-status", "Status", [["", "Any"], ["completed", "Completed"], ["partial", "Partial"], ["blocked", "Blocked"], ["failed", "Failed"],
        ...(state.source === "browser" ? [["cancelled", "Cancelled"], ["running", "Running"]] : [["running", "Running now"]])], state.status),
      sel("obs-pipe", "Reached", [["", "Any stage"], ["ci", "Causal inference"], ["rag", "Retrieval (RAG)"], ["llm", "Explanation"], ["output", "Output"]], state.pipeline),
      sel("obs-sort", "Sort", [["time-desc", "Newest first"], ["time-asc", "Oldest first"], ["duration-desc", "Slowest first"], ["duration-asc", "Fastest first"]], state.sort),
      h("label", { class: "obs-check" }, h("input", { type: "checkbox", id: "obs-problems", checked: state.problems ? "" : null }), " Only errors and warnings"),
      h("div", { class: "obs-actions" }, h("button", { class: "btn btn--primary", type: "submit" }, "Apply"),
        h("button", { class: "btn btn--ghost", type: "button", id: "obs-refresh" }, "Refresh")));
    box.addEventListener("submit", (e) => {
      e.preventDefault();
      const q = search.value.trim();
      if (q && !/^[A-Za-z0-9_-]{1,64}$/.test(q)) { state.error = "Search by a trace ID or request ID: letters, digits, - and _ only."; draw(); return; }
      Object.assign(state, { q, status: $("#obs-status").value, pipeline: $("#obs-pipe").value, sort: $("#obs-sort").value,
        problems: $("#obs-problems").checked, offset: 0 });
      go();
    });
    box.querySelector("#obs-refresh").addEventListener("click", () => go());
    return box;
  }

  function table() {
    const cols = ["Trace", "Started", "Workflow", "Status", "Causal inference", "Retrieval", "Explanation", "Duration", "Events", "Errors / warnings"];
    const body = state.rows.map((t) => h("tr", { class: t.trace_id === state.trace ? "obs-row--open" : null },
      h("td", { "data-label": "Trace" }, openButton(t.trace_id, t.request_id)),
      h("td", { "data-label": "Started" }, fmtTime(t.started_at)),
      h("td", { "data-label": "Workflow" }, t.workflow, h("span", { class: "ci" }, t.source === "server" ? "server" : "this browser")),
      h("td", { "data-label": "Status" }, badge(t.status), t.code ? h("span", { class: "ci" }, t.code) : null),
      h("td", { "data-label": "Causal inference" }, badge(t.ci_status)),
      h("td", { "data-label": "Retrieval" }, badge(t.rag_status)),
      h("td", { "data-label": "Explanation" }, badge(t.llm_status)),
      h("td", { "data-label": "Duration" }, fmtMs(t.duration_ms)),
      h("td", { "data-label": "Events" }, String(t.n_spans ?? "—")),
      h("td", { "data-label": "Errors / warnings" }, `${t.n_errors ?? 0} / ${t.n_warnings ?? 0}`)));
    const pager = h("div", { class: "row obs-pager" },
      h("span", { class: "muted" }, state.total ? `${state.offset + 1}–${state.offset + state.rows.length} of ${state.total}` : "No requests match."),
      h("button", { class: "btn btn--ghost", type: "button", disabled: state.offset ? null : "" , "data-page": "prev" }, "Previous"),
      h("button", { class: "btn btn--ghost", type: "button", disabled: state.offset + PAGE < state.total ? null : "", "data-page": "next" }, "Next"));
    pager.addEventListener("click", (e) => {
      const b = e.target.closest("[data-page]");
      if (!b || b.disabled) return;
      state.offset = Math.max(0, state.offset + (b.dataset.page === "next" ? PAGE : -PAGE));
      go();
    });
    const empty = !state.rows.length && !state.q && !state.status && !state.pipeline && !state.problems;
    return h("section", { class: "card card--flat stack", "aria-labelledby": "obs-req-h" },
      h("h2", { id: "obs-req-h" }, "Requests"), controls(),
      state.error ? h("p", { class: "errors", role: "alert" }, state.error) : null,
      empty ? h("div", { class: "emptystate stack" }, h("p", {}, h("strong", {}, "No requests recorded yet.")),
        h("p", { class: "muted" }, state.source === "server"
          ? "Ask a question about a filled-in patient on this computer; each request the server answers appears here."
          : "Compare the options in Patient Details, ask a question, or search in Investigate: each run appears here with every step it went through."))
        : h("div", { class: "tablewrap" }, h("table", { class: "rtable obs-table" }, h("caption", { class: "sr-only" }, "Recorded requests"),
          h("thead", {}, h("tr", {}, ...cols.map((c) => h("th", { scope: "col" }, c)))), h("tbody", {}, ...body))),
      empty ? null : pager);
  }

  // ── one trace ───────────────────────────────────────────────────────────
  function depthOf(spans) {
    const by = Object.fromEntries(spans.map((s) => [s.span_id, s]));
    const depth = (s) => (s.parent_id && by[s.parent_id] ? 1 + depth(by[s.parent_id]) : 0);
    return Object.fromEntries(spans.map((s) => [s.span_id, Math.min(3, depth(s))]));
  }

  function value(v) {
    if (v === null || v === undefined) return h("span", { class: "muted" }, "—");
    if (typeof v === "boolean") return v ? "yes" : "no";
    if (Array.isArray(v)) {
      if (!v.length) return h("span", { class: "muted" }, "none");
      if (v.every((x) => x === null || typeof x !== "object")) return v.join(", ");
      const keys = [...new Set(v.flatMap((x) => Object.keys(x || {})))];
      return h("div", { class: "tablewrap" }, h("table", { class: "obs-kvtable" },
        h("thead", {}, h("tr", {}, ...keys.map((k) => h("th", {}, label(k))))),
        h("tbody", {}, ...v.map((x) => h("tr", {}, ...keys.map((k) => h("td", {}, value((x || {})[k]))))))));
    }
    if (typeof v === "object") return kv(v);
    return String(v);
  }

  function kv(obj) {
    const entries = Object.entries(obj || {});
    if (!entries.length) return h("span", { class: "muted" }, "nothing recorded");
    return h("dl", { class: "obs-kv" }, ...entries.flatMap(([k, v]) => [h("dt", {}, label(k)), h("dd", {}, value(v))]));
  }

  function lifecycle(t) {
    const top = t.spans.filter((s) => !s.parent_id);
    const arrow = () => svg("svg", { class: "icon flow__arrow", width: 22, height: 22, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor",
      "stroke-width": "2.2", "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true" },
    svg("path", { d: "M5 12h14" }), svg("path", { d: "M13 6l6 6-6 6" })); // the Guide's flow arrow
    return h("ol", { class: "flow obs-flow", "aria-label": "Request lifecycle, in the order it ran" }, ...top.map((s, i) => h("li", {},
      h("div", { class: `flow__box obs-flowbox ${STATUS_CLASS[s.status] || ""}` },
        h("span", { class: "flow__n" }, `${i + 1} · ${PIPE[s.pipeline] || s.pipeline}`), h("span", { class: "flow__name" }, s.name),
        h("span", { class: "flow__desc" }, `${STATUS_WORD[s.status] || s.status}${s.code ? ` (${s.code})` : ""}${s.error_type ? ` (${s.error_type})` : ""} · ${fmtMs(s.duration_ms)}`)),
      i < top.length - 1 ? arrow() : null)));
  }

  function bar(s, total) {
    const g = svg("svg", { class: "obsbar", viewBox: "0 0 100 10", preserveAspectRatio: "none", "aria-hidden": "true" },
      svg("rect", { class: "obsbar__track", x: 0, y: 4, width: 100, height: 2 }));
    if (s.start_ms !== null && s.duration_ms !== null && total > 0) {
      const x = Math.max(0, Math.min(99.5, (s.start_ms / total) * 100));
      g.append(svg("rect", { class: `obsbar__bar ${STATUS_CLASS[s.status] || ""}`, x: x.toFixed(2), y: 1,
        width: Math.max(0.5, Math.min(100 - x, (s.duration_ms / total) * 100)).toFixed(2), height: 8 }));
    }
    return g;
  }

  function timeline(t) {
    const depth = depthOf(t.spans);
    const total = t.duration_ms || Math.max(1, ...t.spans.map((s) => (s.start_ms || 0) + (s.duration_ms || 0)));
    const shown = t.spans.filter((s) => state.spanFilter === "all" || s.pipeline === state.spanFilter);
    const chips = h("div", { class: "chips", role: "group", "aria-label": "Show the spans of" }, ...["all", "guards", "ci", "rag", "llm", "output"]
      .filter((p) => p === "all" || t.spans.some((s) => s.pipeline === p))
      .map((p) => h("button", { class: "chip", type: "button", "aria-pressed": String(state.spanFilter === p), "data-filter": p }, p === "all" ? "All" : PIPE[p])));
    chips.addEventListener("click", (e) => { const b = e.target.closest("[data-filter]"); if (b) { state.spanFilter = b.dataset.filter; drawTrace(t); } });
    const rows = shown.map((s) => h("details", { class: `obs-span obs-depth-${depth[s.span_id]}`, "data-span": s.span_id },
      h("summary", { class: "obs-span__row" },
        h("span", { class: "obs-span__name" }, s.name, h("span", { class: "obs-span__kind" }, `${s.kind} · ${PIPE[s.pipeline] || s.pipeline}`)),
        bar(s, total),
        h("span", { class: "obs-span__end" }, badge(s.status), h("span", { class: "obs-span__ms" }, fmtMs(s.duration_ms)))),
      h("div", { class: "obs-span__body stack" },
        kv({ span_id: s.span_id, parent_span_id: s.parent_id, component: s.component, started_at_ms: s.start_ms === null ? null : `${s.start_ms} ms after the request began`,
          duration: fmtMs(s.duration_ms), status: STATUS_WORD[s.status] || s.status, code: s.code, error_type: s.error_type }),
        h("h4", {}, "What it produced"), kv(s.summary))));
    return h("section", { class: "stack", "aria-labelledby": "obs-tl-h" }, h("h3", { id: "obs-tl-h" }, "Timeline (every span, in the order it started)"),
      chips, h("p", { class: "field__hint" }, "Indented rows ran inside the row above them. The bar shows when each step ran within the request. Open a row for its details."),
      h("div", { class: "obs-spans" }, ...rows));
  }

  /** How the outputs flowed into the answer: one row per stage, each read from the span named in the last column. */
  function integrated(t) {
    const find = (name) => t.spans.find((s) => s.name === name);
    const rows = [];
    const add = (stage, span, text) => { if (span) rows.push([stage, text(span.summary || {}, span), span.name]); };
    add("Input checks", find("input guards") || find("input check"), (m, s) => `${STATUS_WORD[s.status]}${s.code ? ` (${s.code})` : ""}`
      + (m.checks ? ` · ${m.checks.filter((c) => c.result === "BLOCK").map((c) => c.check).join(", ") || "all seven passed"}` : ""));
    add("Safety rules", find("rules") || find("safety rules"), (m) => `eligible: ${(m.eligible || Object.keys(m.fired || {}).filter((a) => !(m.excluded || []).includes(a))).join(", ") || "none"}`
      + ` · excluded: ${(m.excluded || []).map((x) => (typeof x === "string" ? x : `${x.option} (${x.rule_id})`)).join(", ") || "none"}`);
    add("Causal engine", find("causal engine"), (m) => (m.options || []).map((o) => `${o.option}: ${o.status}${o.why_no_estimate ? ` (${o.why_no_estimate})` : ""}`).join(" · ")
      || "no options recorded");
    add("Drivers of the estimate", find("shap drivers"), (m) => Object.entries(m.clear_drivers || {}).map(([k, v]) => `${k}: ${v}`).join(" · ") || "none clear");
    add("Evidence", find("retrieval") || find("evidence for each option"), (m) => (m.passages && m.passages.map ? `${m.status || ""} · ${m.passages.length} passage(s): `
      + m.passages.map((p) => p.chunk_id).join(", ") : `${m.passages ?? 0} passage(s)`) + (m.reason ? ` (${m.reason})` : ""));
    add("Explanation", find("explanation"), (m) => `${m.writer || ""}${m.model_asked ? " (local model asked)" : ""} · `
      + `${(m.answer || m).sentences ?? 0} sentence(s)`);
    add("Server pipeline", find("server pipeline"), (m) => (m.reached ? `HTTP ${m.http_status} · server trace ${m.server_trace_id || "—"}` : "not reached"));
    add("Output checks", find("output guards"), (m) => `${(m.checks_run || []).length} checks · ${m.sentences_checked ?? 0} sentence(s) checked`);
    add("Answer card", find("formatter") || find("answer card"), (m) => (m.evidence_levels || []).map((x) => `${x.option}: ${x.level}`).join(" · ")
      + ` · ${m.claims ?? 0} claim(s)`);
    if (!rows.length) return null;
    return h("section", { class: "stack", "aria-labelledby": "obs-int-h" }, h("h3", { id: "obs-int-h" }, "From the inputs to the answer"),
      h("p", { class: "field__hint" }, "What each stage handed on, read from this trace's spans. In this pipeline every stage runs after the one before it (nothing runs in parallel)."
        + " Retrieval scores rank passages against the question; they are not a measure of accuracy or clinical validity."),
      h("div", { class: "tablewrap" }, h("table", { class: "rtable" },
        h("thead", {}, h("tr", {}, ...["Stage", "What it produced", "Read from span"].map((c) => h("th", { scope: "col" }, c)))),
        h("tbody", {}, ...rows.map(([a, b, c]) => h("tr", {}, h("th", { scope: "row" }, a), h("td", { "data-label": "What it produced" }, b),
          h("td", { "data-label": "Read from span" }, h("code", {}, c))))))));
  }

  function drawTrace(t) {
    const box = document.getElementById("obs-trace");
    if (!box) return;
    if (!t) { box.replaceChildren(); return; }
    const server = t.spans.find((s) => s.name === "server pipeline" && s.summary && s.summary.server_trace_id);
    const toServer = server && state.server ? h("button", { class: "btn btn--ghost", type: "button" }, "Open the server's trace of this request") : null;
    if (toServer) toServer.addEventListener("click", () => { state.source = "server"; state.trace = server.summary.server_trace_id; go(true); });
    const close = h("button", { class: "btn btn--ghost", type: "button" }, "Close");
    close.addEventListener("click", () => { state.trace = null; go(); });
    box.replaceChildren(h("section", { class: "card stack obs-detail", "aria-labelledby": "obs-tr-h", tabindex: "-1" },
      h("div", { class: "row" }, h("h2", { id: "obs-tr-h" }, "Trace ", h("code", {}, t.trace_id)), badge(t.status), close),
      kv({ request_id: t.request_id, workflow: t.workflow, recorded_by: t.source === "server" ? "the DiaCausal server on this computer" : "this browser tab",
        started: fmtTime(t.started_at), finished: fmtTime(t.ended_at), duration: fmtMs(t.duration_ms), http_status: t.http_status, outcome_code: t.code,
        events: t.spans.length, errors: t.n_errors, warnings: t.n_warnings, failed_stage: t.failed_stage, context: t.context }),
      toServer, h("h3", {}, "Lifecycle"), lifecycle(t), integrated(t), timeline(t)));
  }

  function engineCard() {
    if (state.source === "server" && state.engine) {
      const e = state.engine;
      return h("details", { class: "card card--flat obs-engine" }, h("summary", {}, "The causal engine and the pipeline behind these traces"),
        h("p", { class: "field__hint" }, e.engine.provenance), kv(e.engine),
        h("h4", {}, "The pipeline, as diacausal/registry.py lists it"), value(e.layers), h("h4", {}, "Parts inside the layers"), value(e.parts),
        h("p", { class: "field__hint" }, e.order));
    }
    if (typeof MODEL !== "undefined" && MODEL) {
      return h("details", { class: "card card--flat obs-engine" }, h("summary", {}, "The causal engine behind these traces"),
        h("p", { class: "field__hint" }, "web/engine.js with web/model.json (made by python -m diacausal.causal_inference.export_web from the engine fitted on the synthetic reference cohort); it mirrors diacausal/causal_inference/recommend.py, and tests/web compares them."),
        kv({ versions: MODEL.versions, features: MODEL.features, method: MODEL.method,
          overlap_min_propensity: MODEL.thresholds.overlap_min_propensity, max_interval_width: MODEL.thresholds.max_interval_width }));
    }
    return null;
  }

  function notes() {
    return h("details", { class: "card card--flat" }, h("summary", {}, "What is recorded, what is never recorded, and how this differs from SHAP and LIME"),
      h("ul", { class: "list" },
        h("li", {}, "Recorded: which step ran, in which order, inside which step, how long it took, its status (completed, abstained with a code, failed with the error's class name, skipped, not run), and what it produced as IDs, codes, counts, versions and settings."),
        h("li", {}, "Never recorded: the patient's values, the question, a passage's text, a prompt, a model's reply or any key. Per-patient numbers (estimates, intervals, propensities, driver contributions) stay on the answer card the clinician sees; the trace says which options got one and why the others did not."),
        h("li", {}, "Cohort-level effects (ATE) are not computed per request: they come from the offline benchmark on the Analysis tab."),
        h("li", {}, "SHAP and LIME explain a model's prediction; this screen records what the system did. The drivers of each estimate (exact SHAP of the causal estimate) appear here as the \"shap drivers\" step; the XAI-only baseline (SHAP + LIME, version A) is on the Analysis tab and is never run for a request.")),
      h("p", {}, h("a", { href: "#analysis" }, "Open the Analysis tab")));
  }

  function draw() {
    const r = root();
    if (!r) return;
    r.replaceChildren(sourceSwitch(), tiles(), problems(), table(), h("div", { id: "obs-trace" }), engineCard(), notes());
  }

  async function go(focusTrace = false) {
    await load();
    draw();
    if (state.trace) {
      let t = null;
      try { t = await traceDoc(state.trace); } catch (e) { state.error = e.message; }
      if (!t) {
        document.getElementById("obs-trace").replaceChildren(h("p", { class: "errors", role: "alert" },
          state.error || "This trace is no longer here (a reload clears this tab's records; the server keeps the newest 1,000)."));
        return;
      }
      drawTrace(t);
      if (focusTrace) { const d = document.querySelector(".obs-detail"); if (d) { d.scrollIntoView({ block: "start" }); d.focus({ preventScroll: true }); } }
    }
  }

  async function open(hash) {
    const params = new URLSearchParams((hash || "").split("?")[1] || "");
    await detectServer();
    if (params.get("src") === "server" && state.server) state.source = "server";
    if (/^[0-9a-f]{16}$/.test(params.get("trace") || "")) state.trace = params.get("trace");
    if (!state.unsubscribe && window.DiaCausalTrace) {
      state.unsubscribe = window.DiaCausalTrace.subscribe(() => { if (state.source === "browser" && !document.getElementById("view-observability").hidden) go(); });
    }
    await go(Boolean(state.trace));
  }

  function close() {
    if (state.unsubscribe) { state.unsubscribe(); state.unsubscribe = null; }
  }

  window.DiaCausalObservability = { open, close, _state: state };
})();
