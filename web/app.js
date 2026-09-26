/*
 * DiaCausal website — page logic. The maths is in engine.js; every number it uses is in
 * model.json. Research prototype for clinician evaluation; not a marketed medical device;
 * not for unsupervised clinical use. The clinician decides.
 */
"use strict";

const PRESETS = [
  { age: 52, sex: "male", duration_years: 5, hba1c: 8.4, egfr: 88, bmi: 27.0 },
  { age: 60, sex: "female", duration_years: 8, hba1c: 8.2, egfr: 40, bmi: 25.5, pancreatitis_history: true },
  { age: 80, sex: "male", duration_years: 15, hba1c: 8.0, egfr: 38, bmi: 24.0, hypo_history: true, ascvd: true },
];
const FIGURES = [
  ["overlap", "Overlap", "For each drug, how likely each patient was to get it, split by the drug they actually got. The dashed line at 0.05 marks where DiaCausal refuses to estimate."],
  ["love_plot", "Covariate balance", "Grey rings: how different the drug groups were before weighting. Blue dots: after. Left of the 0.1 line means balanced."],
  ["ate_vs_truth", "Average effect vs the truth", "Each method's estimate with its 95% range; the black line is the true effect. Naive (grey) misses; IPW, matching and AIPW sit on it."],
  ["cate_recovery", "Patient-level effects", "Each dot is one test patient: true effect across, DR-learner estimate up. Near the diagonal means accurate."],
  ["calibration", "Calibration", "Patients grouped into tenths by predicted effect: average predicted vs average true. On the diagonal means well calibrated."],
];
const LABEL = { SGLT2i: "SGLT2i", DPP4i: "DPP-4i", SU: "Sulfonylurea" };

let MODEL = null;
let RESULTS = null;
let EVIDENCE = null; // web/evidence.json, loaded the first time the Evidence tab opens
let AUTH = null; // accounts controller (auth.js); null on a local copy without web/config.json
const $ = (sel) => document.querySelector(sel);

/** Tiny DOM builder: h("p", {class: "x"}, "text", child). Text is never parsed as HTML. */
function h(tag, attrs = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === false || v === null || v === undefined) continue;
    if (k === "class") el.className = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) if (kid !== null && kid !== undefined && kid !== false) el.append(kid);
  return el;
}
const svg = (tag, attrs = {}, ...kids) => {
  const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  for (const kid of kids) el.append(kid);
  return el;
};
const signed = (x, d = 2) => (x > 0 ? "+" : x < 0 ? "−" : "") + Math.abs(x).toFixed(d);

// ── Try it ────────────────────────────────────────────────────────────────
function readForm() {
  const f = $("#patient");
  const p = {};
  for (const name of window.DiaCausal.FIELDS) {
    if (name === "sex") { const c = f.querySelector('input[name="sex"]:checked'); p.sex = c ? c.value : undefined; continue; }
    const raw = f.elements[name].value.trim();
    p[name] = raw === "" ? undefined : Number(raw);
  }
  for (const name of window.DiaCausal.FLAGS) p[name] = f.elements[name].checked;
  return p;
}

function fillForm(p) {
  const f = $("#patient");
  for (const name of window.DiaCausal.FIELDS) {
    if (name === "sex") { for (const r of f.querySelectorAll('input[name="sex"]')) r.checked = r.value === p.sex; continue; }
    f.elements[name].value = p[name] ?? "";
  }
  for (const name of window.DiaCausal.FLAGS) f.elements[name].checked = Boolean(p[name]);
}

function showBmi() {
  const v = Number($("#patient").elements.bmi.value);
  $("#bmi-cat").textContent = Number.isFinite(v) && v > 0 ? "Category: " + window.DiaCausal.bmiCategory(MODEL, v) : "";
}

function ruleLines(o) {
  return o.safety.map((s) => h("p", { class: `rule rule--${s.action}` },
    h("strong", {}, `${s.rule_id} · ${s.action === "EXCLUDE" ? "Excluded" : "Caution"}`),
    ` (${s.condition}; rule ${s.rule_status.toLowerCase()}): ${s.message}`,
    h("span", { class: "src" }, `Source: ${s.source} — ${s.section}`)));
}

function card(o) {
  const caution = o.status === "estimate" && o.safety.length > 0;
  const kind = o.status === "excluded" ? "excluded" : o.status === "insufficient_evidence" ? "insufficient" : caution ? "caution" : "estimate";
  const badge = { excluded: "EXCLUDED", insufficient: "INSUFFICIENT EVIDENCE", caution: "ESTIMATE · CAUTION", estimate: "ESTIMATE" }[kind];
  const body = [];
  if (o.status === "excluded") body.push(h("p", { class: "sub" }, "Not estimated: removed by a safety rule before the causal engine ran."));
  if (o.status === "insufficient_evidence") body.push(h("p", { class: "sub" }, o.insufficient_reason));
  if (o.status === "estimate") {
    const e = o.effect;
    body.push(h("p", { class: "est" }, signed(e.value), " ", h("small", {}, `(95% range ${signed(e.ci_low)} to ${signed(e.ci_high)})`)));
    body.push(h("p", { class: "sub" }, `percentage points of HbA1c at 6 months · propensity ${o.confidence.propensity.toFixed(2)}`));
    if (o.secondary) {
      const w = o.secondary.weight_change_kg, r = o.secondary.hypo_risk_pct;
      body.push(h("dl", { class: "sec" },
        h("dt", {}, "Weight at 6 months"),
        h("dd", {}, h("strong", {}, `${signed(w.value, 1)} kg`), ` (95% range ${signed(w.ci_low, 1)} to ${signed(w.ci_high, 1)})`),
        h("dt", {}, "Any low sugar by 6 months"),
        h("dd", {}, h("strong", {}, `${r.value.toFixed(1)}%`), ` (95% range ${r.ci_low.toFixed(1)} to ${r.ci_high.toFixed(1)})`)));
    }
  }
  body.push(...ruleLines(o));
  body.push(h("p", { class: "sub" }, `Cost: ${o.cost.label}`));
  body.push(optionEvidence(o));
  return h("div", { class: `opt opt--${kind}` },
    h("div", { class: "opt__head" },
      h("div", {}, h("div", { class: "opt__name" }, o.name), h("div", { class: "opt__example" }, `e.g. ${o.example_molecule}`)),
      h("span", { class: "badge" }, badge)),
    ...body);
}

/** Evidence fusion: the licence-cleared passages about this option (and its fired rules), loaded on tap. */
function optionEvidence(o) {
  const d = h("details", { class: "opt__ev noprint" }, h("summary", {}, "Evidence for this option"));
  d.addEventListener("toggle", async () => {
    if (!d.open || d.dataset.done) return;
    d.dataset.done = "1";
    const index = await loadEvidence();
    const conds = o.safety.map((s) => s.condition).join(" ");
    const keys = [o.name.split(" ")[0].toLowerCase(), o.example_molecule.toLowerCase()];
    const about = (p) => p.text !== index.withheld_text && keys.some((k) => p.text.toLowerCase().includes(k));
    const seen = new Set();
    const shown = [];
    for (const q of [`${o.name} ${conds}`, `${o.name} safety`, o.name]) {
      const res = window.DiaCausalEvidence.search(index, q);
      for (const p of res.passages.filter(about)) {
        const key = `${p.citation.source_id}|${p.citation.section}|${p.text.slice(0, 40)}`;
        if (!seen.has(key) && shown.length < 2) { seen.add(key); shown.push(p); }
      }
      if (shown.length >= 2) break;
    }
    if (!shown.length) { d.append(h("p", { class: "sub" }, "No licence-cleared passage about this option yet.")); return; }
    for (const p of shown) {
      const c = p.citation;
      d.append(h("blockquote", { class: "ev-quote" }, p.text.split(/\s+/).slice(0, 60).join(" ") + (p.text.split(/\s+/).length > 60 ? " …" : ""),
        h("span", { class: "src" }, `Source ${c.source_id}: ${c.title} — “${c.section}”`)));
    }
    d.append(h("p", { class: "muted" }, "Source passages, not advice. More on the Evidence tab."));
  });
  return d;
}

function forest(options) {
  const est = options.filter((o) => o.status === "estimate");
  const W = 360, rowH = 50, top = 12, left = 96, right = 18, H = top + rowH * est.length + 36;
  const lo = Math.min(0, ...est.map((o) => o.effect.ci_low)) - 0.1;
  const hi = Math.max(0, ...est.map((o) => o.effect.ci_high)) + 0.1;
  const x = (v) => left + ((v - lo) / (hi - lo)) * (W - left - right);
  const g = svg("svg", { viewBox: `0 0 ${W} ${H}`, class: "forest", role: "img",
    "aria-label": "Expected 6-month HbA1c change for each option with its 95% range" });
  g.append(svg("line", { class: "zero", x1: x(0), x2: x(0), y1: top - 4, y2: H - 30 }));
  est.forEach((o, i) => {
    const y = top + rowH * i + rowH / 2;
    g.append(svg("text", { x: 0, y: y + 4 }, document.createTextNode(LABEL[o.arm])));
    g.append(svg("line", { class: "ci", x1: x(o.effect.ci_low), x2: x(o.effect.ci_high), y1: y, y2: y }));
    g.append(svg("circle", { class: "dot", cx: x(o.effect.value), cy: y, r: 7 }));
  });
  const axisY = H - 26;
  g.append(svg("line", { class: "axis", x1: left, x2: W - right, y1: axisY, y2: axisY }));
  const step = hi - lo > 1.2 ? 0.5 : 0.25;
  for (let t = Math.ceil(lo / step) * step; t <= hi + 1e-9; t += step) {
    g.append(svg("line", { class: "axis", x1: x(t), x2: x(t), y1: axisY, y2: axisY + 4 }));
    g.append(svg("text", { x: x(t), y: axisY + 18, "text-anchor": "middle" }, document.createTextNode(Math.abs(t) < 1e-9 ? "0" : signed(t, 2))));
  }
  return g;
}

/** Only on paper: what was entered, when, and under which versions (the page itself is never sent anywhere). */
function printHeader(result) {
  const p = readForm();
  const flags = window.DiaCausal.FLAGS.filter((f) => p[f]).map((f) => f.replace(/_/g, " "));
  return h("div", { class: "print-only print-head" },
    h("h2", {}, "DiaCausal consultation summary"),
    h("p", {}, `Printed ${new Date().toLocaleString("en-IN")} · Request ID ${result.request_id}`),
    h("p", {}, `Patient as entered: age ${p.age}, ${p.sex}, diabetes ${p.duration_years} years, HbA1c ${p.hba1c}%, eGFR ${p.egfr} mL/min/1.73m², BMI ${p.bmi} kg/m²` +
      (flags.length ? `; history: ${flags.join(", ")}` : "") + "."),
    h("p", {}, `Engine ${result.versions.engine} · params ${result.versions.params_sha} · rules ${result.versions.rules_sha} · ${result.versions.cohort}. Synthetic data only; no doses are shown.`),
    h("p", { class: "intended" }, result.intended_use));
}

function render(result) {
  const out = $("#out");
  out.replaceChildren();
  if (result.error) return;
  out.append(printHeader(result));
  out.append(h("p", { class: "sub" }, `BMI category: ${result.bmi_category} · Request ID ${result.request_id} · computed on this device`));
  if (result.applicable === "NOT_APPLICABLE") {
    out.append(h("div", { class: "notice" }, h("strong", {}, "Not applicable for this patient: "), result.not_applicable_reasons.join("; ")));
  }
  out.append(h("h2", {}, "The three options (safety rules ran first)"));
  out.append(h("div", { class: "cards" }, result.options.map(card)));
  if (result.options.some((o) => o.status === "estimate")) {
    out.append(h("div", { class: "card" }, h("h2", {}, "Estimates with their 95% ranges"), forest(result.options),
      h("p", { class: "sub" }, "Change in HbA1c at 6 months, percentage points. Further left = larger fall. Dashed line = no change.")));
  }
  if (result.comparisons.length) {
    out.append(h("div", { class: "card" }, h("h2", {}, "Fair comparisons"),
      h("div", { class: "scroll" }, h("table", {},
        h("thead", {}, h("tr", {}, h("th", {}, "Comparison"), h("th", {}, "Difference"), h("th", {}, "95% range"))),
        h("tbody", {}, result.comparisons.map((c) => h("tr", {},
          h("td", {}, `${LABEL[c.first]} minus ${LABEL[c.second]}`),
          h("td", {}, signed(c.difference.value)),
          h("td", {}, `${signed(c.difference.ci_low)} to ${signed(c.difference.ci_high)}`)))))),
      h("p", { class: "sub" }, "Negative = the first option lowers HbA1c more. A range that crosses 0 means no clear difference.")));
  }
  out.append(h("p", { class: "decide" }, result.decision));
  if (result.options.some((o) => o.secondary)) {
    out.append(h("p", { class: "sub" }, "Weight and low-sugar figures come from the same synthetic cohort and method as HbA1c; they are secondary outcomes for discussion, not a ranking."));
  }
  const printBtn = h("button", { type: "button", class: "chip noprint" }, "Print or save as PDF (consultation summary)");
  printBtn.addEventListener("click", () => window.print());
  out.append(printBtn);
  out.append(h("details", { class: "card" }, h("summary", {}, "Assumptions behind these numbers"),
    h("ul", {}, result.assumptions.map((a) => h("li", {}, a))),
    h("p", { class: "muted" }, `Engine ${result.versions.engine} · params ${result.versions.params_sha} · rules ${result.versions.rules_sha} · cohort ${result.versions.cohort}`)));
  out.append(h("details", { class: "card" }, h("summary", {}, "Structured Causal Output (JSON)"),
    h("pre", {}, JSON.stringify(result, null, 1))));
}

function run() {
  const p = readForm();
  const f = $("#patient");
  const problems = window.DiaCausal.validate(MODEL, p);
  for (const input of f.querySelectorAll("input[type=number]")) {
    input.classList.toggle("bad", problems.some((m) => m.startsWith(input.name + ":")));
  }
  const err = $("#errors");
  if (problems.length) {
    err.hidden = false;
    err.textContent = "Please check: " + problems.join("; ");
    $("#out").replaceChildren();
    return;
  }
  err.hidden = true;
  try {
    render(window.DiaCausal.recommend(MODEL, p));
  } catch (e) {
    err.hidden = false;
    err.textContent = "This answer was withheld by the safety check: " + e.message;
  }
}

function pressPreset(i) {
  document.querySelectorAll("[data-preset]").forEach((b) => b.setAttribute("aria-pressed", String(Number(b.dataset.preset) === i)));
}

// ── Results ───────────────────────────────────────────────────────────────
function renderResults() {
  if (!RESULTS) return;
  const rows = RESULTS.summary;
  const pick = (section, method, target) => rows.find((r) => r.section === section && r.method === method && (!target || r.target === target));
  const cov = (m) => {
    const vals = rows.filter((r) => r.section === "average_effect" && r.method === m).map((r) => Number(r.coverage_95) * 100);
    return `${Math.min(...vals).toFixed(0)}–${Math.max(...vals).toFixed(0)}%`;
  };
  const dr = rows.filter((r) => r.section === "patient_effect" && r.method === "DR-learner").map((r) => Number(r.coverage_95) * 100);
  const run = RESULTS.run;
  $("#res-lead").textContent = `${run.reps} synthetic India-calibrated cohorts × ${run.n_patients.toLocaleString("en-IN")} patients, where the true effects are known. SYNTHETIC DATA: this shows the methods recover a planted truth, not real-world drug effects.`;
  const tile = (value, text) => h("div", { class: "tile" }, h("b", {}, value), h("span", {}, text));
  $("#tiles").replaceChildren(
    tile(signed(Number(pick("average_effect", "naive", "SGLT2i-DPP4i").bias)), "naive bias, SGLT2i vs DPP-4i"),
    tile(signed(Number(pick("average_effect", "AIPW", "SGLT2i-DPP4i").bias), 3), "AIPW bias (corrected)"),
    tile(cov("AIPW"), "AIPW 95% ranges contain the truth"),
    tile(`${Math.min(...dr).toFixed(0)}–${Math.max(...dr).toFixed(0)}%`, "per-patient ranges contain the truth"),
    tile(run.refutation_checks_passed, "refutation checks passed"),
    tile(Number(pick("balance", "IPW weights").smd_max_after).toFixed(2), `largest imbalance after weighting (was ${Number(pick("balance", "IPW weights").smd_max_before).toFixed(2)})`),
    tile(Number(pick("policy", "DR-learner").policy_regret).toFixed(3), "policy regret, DR-learner (HbA1c points)"),
    tile(`${(Number(pick("policy", "DR-learner").abstention_rate) * 100).toFixed(1)}%`, "answers withheld (insufficient evidence or excluded)"));
  const avg = rows.filter((r) => r.section === "average_effect");
  $("#res-table").replaceChildren(h("table", {},
    h("thead", {}, h("tr", {}, ["Comparison", "Method", "Truth", "Bias", "RMSE", "Coverage"].map((t) => h("th", {}, t)))),
    h("tbody", {}, avg.map((r) => { const [a, b] = r.target.split("-"); return h("tr", {},
      h("td", {}, `${LABEL[a]} vs ${LABEL[b]}`), h("td", {}, r.method), h("td", {}, signed(Number(r.true_value), 3)),
      h("td", {}, signed(Number(r.bias), 3)), h("td", {}, Number(r.rmse).toFixed(3)), h("td", {}, `${(Number(r.coverage_95) * 100).toFixed(0)}%`)); }))));
  $("#ref-table").replaceChildren(h("table", {},
    h("thead", {}, h("tr", {}, ["Check", "Comparison", "Result", "Passed"].map((t) => h("th", {}, t)))),
    h("tbody", {}, RESULTS.refutation.map((r) => { const [a, b] = r.contrast.split("-"); return h("tr", {},
      h("td", {}, r.check), h("td", {}, `${LABEL[a]} vs ${LABEL[b]}`),
      h("td", {}, `${signed(Number(r.new_estimate), 3)} (${r.criterion})`), h("td", {}, r.passed)); }))));
  $("#figures").replaceChildren(...FIGURES.map(([file, title, text]) => h("figure", { class: "card fig" },
    h("h2", {}, title), h("img", { src: `./results/${file}.png`, alt: `${title} figure`, loading: "lazy" }), h("figcaption", {}, text))));
}

// ── Learn ─────────────────────────────────────────────────────────────────
async function showDoc(name) {
  document.querySelectorAll("[data-doc]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.doc === name)));
  const doc = $("#doc");
  doc.textContent = "Loading…";
  try {
    const md = await (await fetch(`./docs/${name}`)).text();
    const clean = md.replace(/```mermaid[\s\S]*?```/g, "*(A diagram appears here in the repository version.)*");
    doc.innerHTML = window.marked.parse(clean); // our own committed docs, not user input
  } catch {
    doc.textContent = "Could not load this page. Check your connection and try again.";
  }
}

// ── Evidence (RAG) ────────────────────────────────────────────────────────
async function loadEvidence() {
  if (!EVIDENCE) EVIDENCE = await fetch("./evidence.json").then((r) => r.json());
  if (!$("#ev-sources").childNodes.length) renderSources();
  return EVIDENCE;
}

function renderSources() {
  const label = (s) => (s.bucket === EVIDENCE.cleared_bucket && s.confirmed ? "In the search"
    : s.bucket === EVIDENCE.cleared_bucket ? "Cleared, waiting for a team check" : s.bucket.replaceAll("_", " "));
  const kind = (s) => (s.bucket === EVIDENCE.cleared_bucket && s.confirmed ? "ok" : s.bucket === "exclude" ? "no" : "wait");
  $("#ev-sources").replaceChildren(h("table", {},
    h("thead", {}, h("tr", {}, ["ID", "Source", "Licence status"].map((t) => h("th", {}, t)))),
    h("tbody", {}, EVIDENCE.sources.map((s) => h("tr", { class: `src-${kind(s)}` },
      h("td", {}, s.id), h("td", {}, `${s.title} — ${s.issuer}, ${s.version}`), h("td", {}, label(s)))))));
}

/** The ~50 words around the question's first matching word, with the whole passage one tap away. */
function excerpt(text, question) {
  const words = text.split(/\s+/);
  if (words.length <= 60) return h("p", { class: "passage__text" }, text);
  const terms = window.DiaCausalEvidence._internals.bm25Tokens(EVIDENCE, question);
  const hit = Math.max(0, words.findIndex((w) => terms.some((t) => w.toLowerCase().includes(t))));
  const from = Math.max(0, Math.min(hit - 15, words.length - 50));
  const part = (from > 0 ? "… " : "") + words.slice(from, from + 50).join(" ") + (from + 50 < words.length ? " …" : "");
  return h("div", {}, h("p", { class: "passage__text" }, part),
    h("details", {}, h("summary", {}, "Read the whole passage"), h("p", { class: "passage__text" }, text)));
}

/** The explanation card: quoted (template) or a checked model answer, every sentence with its passage number. */
function explanationView(r) {
  const title = r.backend === "template" ? "Explanation (sentences quoted from the passages below)" : `Explanation (${r.backend}, checked against the passages below)`;
  const wrap = h("div", {}, h("h2", {}, title));
  if (r.status !== "SUCCESS") {
    wrap.append(h("p", { class: "sub" }, `No explanation: ${r.note}`));
    return wrap;
  }
  wrap.append(h("ul", { class: "explain__list" }, r.sentences.map((s) => h("li", {},
    r.backend === "template" ? `“${s.text}”` : s.text, " ", h("span", { class: "cite" }, s.cites.map((c) => `[${c}]`).join(""))))));
  if (r.note) wrap.append(h("p", { class: "muted" }, r.note));
  wrap.append(h("p", { class: "muted" }, "Numbers in brackets point to the passages below. The clinician decides."));
  return wrap;
}

/** Opt-in online rewrite: the server rebuilds the passages from their IDs; the answer is checked here. */
async function onlineExplanation(index, question, res, chunkIds) {
  try {
    const { data, error } = await AUTH.client.functions.invoke("explain", { body: { question, chunk_ids: chunkIds } });
    if (error || !data || typeof data.text !== "string") throw new Error((data && data.error) || "unavailable");
    return window.DiaCausalExplain.fromModel(index, question, res, "Gemini", data.text);
  } catch (e) {
    const fallback = window.DiaCausalExplain.explain(index, question, res);
    fallback.note = "Gemini is not available right now (the free key may not be set up yet, or the daily quota is used up); showing quoted sentences instead.";
    return fallback;
  }
}

async function ask(question) {
  const out = $("#ev-out");
  const q = question.trim();
  if (!q) { out.replaceChildren(h("p", { class: "errors" }, "Please type a question.")); return; }
  const index = await loadEvidence();
  const raw = window.DiaCausalEvidence.search(index, q, { raw: true });
  const chunkIds = raw.passages.map((p) => p._raw.chunk_id);
  const res = JSON.parse(JSON.stringify({ ...raw, passages: raw.passages.map(({ _raw, ...p }) => p) }));
  out.replaceChildren();
  const note = window.DiaCausalExplain.explain(index, q, res);
  if (res.status === "SUCCESS" && note.status !== "SUCCESS" && note.note === index.no_dose_note) {
    out.append(h("div", { class: "notice" }, h("strong", {}, "No doses: "), index.no_dose_note));
  }
  if (res.status === "INSUFFICIENT_EVIDENCE") {
    out.append(h("div", { class: "notice" }, h("strong", {}, "Insufficient evidence: "), res.reason,
      h("p", { class: "sub" }, "DiaCausal does not guess. Ask about something the approved sources cover, or check the sources below.")));
    return;
  }
  const box = h("div", { class: "card explain" });
  box.append(explanationView(note));
  if (note.status === "SUCCESS" && AUTH && AUTH.view() === "app") {
    const btn = h("button", { type: "button", class: "chip" }, "Explain in plain words with Gemini (online)");
    const warn = h("p", { class: "muted" }, "Sends your question and the passage numbers (never patient details) to Google Gemini through DiaCausal's server. The answer is checked against the passages; if any sentence fails, the quotes stay.");
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      btn.textContent = "Asking Gemini…";
      box.replaceChildren(explanationView(await onlineExplanation(index, q, res, chunkIds)));
    });
    box.append(btn, warn);
  }
  out.append(box);
  out.append(h("h2", {}, `${res.passages.length} passages, best match first`));
  res.passages.forEach((p, i) => {
    const c = p.citation;
    out.append(h("article", { class: "card passage" },
      h("p", { class: "passage__cite" }, `${i + 1}. “${c.section}”, ${c.page === "?" ? "web page" : `page ${c.page}`}`),
      h("p", { class: "src" }, `Source ${c.source_id}: ${c.title}`),
      excerpt(p.text, q),
      h("p", { class: "muted" }, `Scores: keyword (BM25) ${p.scores.bm25} · vector ${p.scores.vector} · fused ${p.scores.rrf}`)));
  });
  out.append(h("p", { class: "decide" }, "These are source passages, not advice. The clinician decides."));
  out.append(h("details", { class: "card" }, h("summary", {}, "Structured evidence (JSON)"), h("pre", {}, JSON.stringify(res, null, 1))));
}

// ── Routing and start-up ──────────────────────────────────────────────────
const ROUTES = ["try", "evidence", "results", "learn", "about", "account", "signup", "forgot", "admin"];
let returnTo = "try";
let lastGate = null;

function show(view) {
  for (const v of document.querySelectorAll(".view")) v.hidden = v.id !== `view-${view}`;
}

function route() {
  if (/access_token=|error_description=/.test(location.hash)) return; // a sign-in link: auth.js reads it first
  const name = (location.hash || "#try").slice(1).split("?")[0];
  const known = ROUTES.includes(name) ? name : "try";
  for (const a of document.querySelectorAll(".tabs a")) {
    if (a.dataset.route === known) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  }
  const gate = AUTH ? AUTH.view() : "demo";
  if (window.DiaCausalAuth.PROTECTED.includes(known) && gate !== "app" && gate !== "demo") {
    returnTo = known;
    show("account");
    window.DiaCausalAccount.render(gate, known);
  } else if (["account", "signup", "forgot", "admin"].includes(known)) {
    show("account");
    window.DiaCausalAccount.render(gate, known);
  } else {
    show(known);
    if (known === "evidence") loadEvidence().catch(() => { $("#ev-sources").textContent = "Could not load the evidence index."; });
  }
  if (known === "results") renderResults();
  if (known === "learn" && !$("#doc").childNodes.length) showDoc("causal-engine.md");
  window.scrollTo(0, 0);
}

/** After a sign-in step: go back to the page the person wanted, or refresh the current screen. */
function afterAuthChange() {
  const acct = $("#acct");
  const gate = AUTH ? AUTH.view() : "demo";
  const p = AUTH && AUTH.state.profile;
  acct.textContent = !AUTH ? "Local copy" : AUTH.state.session ? (p && p.full_name ? p.full_name.split(" ")[0] : "Account") : "Sign in";
  const name = (location.hash || "#try").slice(1);
  const opened = gate === "app" && lastGate !== null && lastGate !== "app";
  lastGate = gate;
  if (opened && ["account", "signup", "forgot"].includes(name)) {
    location.hash = "#" + returnTo; // the hashchange event re-routes
    return;
  }
  route();
}

async function share() {
  const data = { title: "DiaCausal", text: "DiaCausal: compare add-ons to metformin (research prototype, synthetic data).", url: location.origin + location.pathname };
  try {
    if (navigator.share) await navigator.share(data);
    else { await navigator.clipboard.writeText(data.url); $("#share").textContent = "Link copied"; }
  } catch { /* the user closed the share sheet */ }
}

async function start() {
  let config;
  [MODEL, RESULTS, config] = await Promise.all([
    fetch("./model.json").then((r) => r.json()),
    fetch("./results.json").then((r) => r.json()).catch(() => null),
    fetch("./config.json").then((r) => (r.ok ? r.json() : null)).catch(() => null),
  ]);
  if (config && config.supabaseUrl && config.supabaseKey && window.supabase) {
    AUTH = window.DiaCausalAuth.createController(window.supabase, config, window.localStorage);
    AUTH.onChange(afterAuthChange);
    for (const ev of ["pointerdown", "keydown", "scroll"]) window.addEventListener(ev, () => AUTH.touch(), { passive: true });
    setInterval(() => AUTH.idleCheck(), 30 * 1000);
  } else {
    $("#demo").hidden = false;
  }
  $("#versions").textContent = `Engine ${MODEL.versions.engine} · params ${MODEL.versions.params_sha} · rules ${MODEL.versions.rules_sha} · ${MODEL.versions.cohort}`;
  document.querySelectorAll("[data-preset]").forEach((b) => b.addEventListener("click", () => {
    const i = Number(b.dataset.preset);
    fillForm(PRESETS[i]); pressPreset(i); showBmi(); run();
    $("#out").scrollIntoView({ block: "start" });
  }));
  document.querySelectorAll("[data-doc]").forEach((b) => b.addEventListener("click", () => showDoc(b.dataset.doc)));
  $("#patient").addEventListener("submit", (e) => { e.preventDefault(); pressPreset(-1); run(); $("#out").scrollIntoView({ block: "start" }); });
  $("#patient").addEventListener("input", () => { showBmi(); pressPreset(-1); });
  $("#share").addEventListener("click", share);
  $("#ask").addEventListener("submit", (e) => { e.preventDefault(); ask($("#ask").elements.q.value); });
  document.querySelectorAll("[data-ask]").forEach((b) => b.addEventListener("click", () => {
    $("#ask").elements.q.value = b.dataset.ask; ask(b.dataset.ask);
  }));
  window.addEventListener("hashchange", route);
  fillForm(PRESETS[0]); pressPreset(0); showBmi(); run();
  if (AUTH) await AUTH.refresh(); else afterAuthChange();
  if (/access_token=|error_description=/.test(location.hash)) history.replaceState(null, "", location.pathname + "#account");
  route();
  if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost")) navigator.serviceWorker.register("./sw.js").catch(() => {});
}

document.addEventListener("DOMContentLoaded", start);
