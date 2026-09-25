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
  }
  body.push(...ruleLines(o));
  body.push(h("p", { class: "sub" }, `Cost: ${o.cost.label}`));
  return h("div", { class: `opt opt--${kind}` },
    h("div", { class: "opt__head" },
      h("div", {}, h("div", { class: "opt__name" }, o.name), h("div", { class: "opt__example" }, `e.g. ${o.example_molecule}`)),
      h("span", { class: "badge" }, badge)),
    ...body);
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

function render(result) {
  const out = $("#out");
  out.replaceChildren();
  if (result.error) return;
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

// ── Routing and start-up ──────────────────────────────────────────────────
function route() {
  const name = (location.hash || "#try").slice(1).split("?")[0];
  const known = ["try", "results", "learn", "about"].includes(name) ? name : "try";
  for (const v of document.querySelectorAll(".view")) v.hidden = v.id !== `view-${known}`;
  for (const a of document.querySelectorAll(".tabs a")) {
    if (a.dataset.route === known) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  }
  if (known === "results") renderResults();
  if (known === "learn" && !$("#doc").childNodes.length) showDoc("causal-engine.md");
  window.scrollTo(0, 0);
}

async function share() {
  const data = { title: "DiaCausal", text: "DiaCausal: compare add-ons to metformin (research prototype, synthetic data).", url: location.origin + location.pathname };
  try {
    if (navigator.share) await navigator.share(data);
    else { await navigator.clipboard.writeText(data.url); $("#share").textContent = "Link copied"; }
  } catch { /* the user closed the share sheet */ }
}

async function start() {
  [MODEL, RESULTS] = await Promise.all([
    fetch("./model.json").then((r) => r.json()),
    fetch("./results.json").then((r) => r.json()).catch(() => null),
  ]);
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
  window.addEventListener("hashchange", route);
  fillForm(PRESETS[0]); pressPreset(0); showBmi(); run();
  route();
  if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost")) navigator.serviceWorker.register("./sw.js").catch(() => {});
}

document.addEventListener("DOMContentLoaded", start);
