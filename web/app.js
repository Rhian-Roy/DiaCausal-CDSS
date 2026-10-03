/*
 * DiaCausal website — page logic. The maths is in engine.js; every number it uses is in
 * model.json. Screens follow design/screens-v2 (Patient Details 13–16 and 20, Guide 25, About 26).
 * Research prototype for clinician evaluation; not a marketed medical device;
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
// Panel fields: label and unit for messages. The plausible ranges come from model.json, never from here.
const NUMERIC = {
  age: ["Age", " years"], duration_years: ["Diabetes duration", " years"], hba1c: ["HbA1c", "%"],
  egfr: ["eGFR", " mL/min/1.73m²"], bmi: ["BMI", " kg/m²"],
};
const YES_NO = ["ascvd", "hf", "dka_history", "pancreatitis_history", "t1d", "low_income"];

let MODEL = null;
let RESULTS = null;
let EVIDENCE = null; // web/evidence.json, loaded the first time it is needed
let AUTH = null; // accounts controller (auth.js); null on a local copy without web/config.json
let fromExample = false; // the panel holds example data (badge "Example data")
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
/** The design's line icons (design/screens-v2), drawn from path data. */
const ICON_PATHS = {
  done: ["M4.5 12.8l4.6 4.6L19.5 7"],
  running: ["M12 3.5a8.5 8.5 0 1 0 8.5 8.5"],
  waiting: [], // a circle, below
  skip: ["M7 12h10"],
  shield: ["M12 3l7.5 3.2v5.6c0 4.6-3.1 8.2-7.5 9.7-4.4-1.5-7.5-5.1-7.5-9.7V6.2z", "M9.2 12.1l2 2 3.6-3.8"],
  book: ["M4 4.5h7a3 3 0 0 1 3 3v12a2.5 2.5 0 0 0-2.5-2.5H4z", "M20 4.5h-3a3 3 0 0 0-3 3v12a2.5 2.5 0 0 1 2.5-2.5H20z"],
  form: ["M5.5 6.5a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v12.5a2 2 0 0 1-2 2h-9a2 2 0 0 1-2-2z", "M9 11h6", "M9 15h4"],
  check: ["M4.5 12.8l4.6 4.6L19.5 7"],
  cross: ["M15 9l-6 6", "M9 9l6 6"],
  copy: ["M15 6.5V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h1.5"],
  lock: ["M8 10V7a4 4 0 0 1 8 0v3"],
  clock: ["M12 7v5.3l3.3 2"],
  info: ["M12 11v5.5", "M12 7.6h.01"],
  stop: ["M8.3 2.6h7.4l5.7 5.7v7.4l-5.7 5.7H8.3l-5.7-5.7V8.3z", "M15 9l-6 6", "M9 9l6 6"],
};
function icon(name, size = 22, cls = "") {
  const el = svg("svg", { class: `icon ${cls}`.trim(), width: size, height: size, viewBox: "0 0 24 24", fill: "none",
    stroke: "currentColor", "stroke-width": "2.3", "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true" });
  if (name === "waiting" || name === "clock" || name === "info" || name === "cross") el.append(svg("circle", { cx: 12, cy: 12, r: name === "waiting" ? 8.5 : 9 }));
  if (name === "lock") el.append(svg("rect", { x: 4, y: 10, width: 16, height: 10.5, rx: 2 }));
  if (name === "copy") el.append(svg("rect", { x: 9, y: 9, width: 11, height: 11, rx: 2 }));
  for (const d of ICON_PATHS[name] || []) el.append(svg("path", name === "running" ? { d, class: "spin" } : { d }));
  return el;
}
const signed = (x, d = 2) => (x > 0 ? "+" : x < 0 ? "−" : "") + Math.abs(x).toFixed(d);

// ── Patient Details: the panel (screens 13–16) ───────────────────────────
function radio(name) {
  const c = $("#patient").querySelector(`input[name="${name}"]:checked`);
  return c ? c.value : undefined;
}
function setRadio(name, value) {
  for (const r of $("#patient").querySelectorAll(`input[name="${name}"]`)) r.checked = r.value === value;
}

/** The engine's inputs, from the panel. Past hypoglycaemia Mild or Severe = yes. Adds no model inputs. */
function readForm() {
  const f = $("#patient");
  const p = {};
  for (const name of window.DiaCausal.FIELDS) {
    if (name === "sex") { p.sex = radio("sex"); continue; }
    const raw = f.elements[name].value.trim().replace(",", ".");
    p[name] = raw === "" ? undefined : Number(raw);
  }
  for (const name of window.DiaCausal.FLAGS) {
    p[name] = name === "hypo_history" ? ["mild", "severe"].includes(radio("hypo")) : radio(name) === "yes";
  }
  return p;
}

function fillForm(p) {
  const f = $("#patient");
  for (const name of window.DiaCausal.FIELDS) {
    if (name === "sex") { setRadio("sex", p.sex); continue; }
    f.elements[name].value = p[name] ?? "";
  }
  for (const name of YES_NO) setRadio(name, p[name] ? "yes" : "no");
  setRadio("hypo", p.hypo_history ? "mild" : "none");
  f.elements.budget.value = "";
}

function clearForm() {
  const f = $("#patient");
  for (const input of f.querySelectorAll("input[type=text]")) input.value = "";
  for (const input of f.querySelectorAll("input[type=radio]")) input.checked = false;
}

/** Every problem with the panel, per field, in plain words (empty = ready to compare). */
function panelProblems() {
  const f = $("#patient");
  const ranges = MODEL.thresholds.input_ranges;
  const out = {};
  for (const [name, [label, unit]] of Object.entries(NUMERIC)) {
    const raw = f.elements[name].value.trim().replace(",", ".");
    if (raw === "") { out[name] = `Enter the ${label === "eGFR" || label === "BMI" || label === "HbA1c" ? label : label.toLowerCase()}.`; continue; }
    const v = Number(raw);
    const [lo, hi] = ranges[name];
    if (!Number.isFinite(v) || v < lo || v > hi) out[name] = `${label} ${raw}${unit}? Check the value — expected ${lo}–${hi}${unit}.`;
    else if (name === "age" && !Number.isInteger(v)) out[name] = "Age must be a whole number of years.";
  }
  if (!radio("sex")) out.sex = "Choose female or male.";
  for (const name of [...YES_NO, "hypo"]) if (!radio(name)) out[name] = "Answer this question.";
  return out;
}

/** Show or hide each field's message (screen 15); returns true when the panel is complete and plausible. */
function showProblems(problems, touchedOnly) {
  const f = $("#patient");
  for (const box of f.querySelectorAll("[data-field]")) {
    const name = box.dataset.field;
    const err = box.querySelector(".fielderror");
    if (!err) continue;
    const msg = problems[name];
    const show = Boolean(msg) && (!touchedOnly || box.dataset.touched === "1");
    err.hidden = !show;
    err.querySelector("strong").textContent = show ? msg : "";
    const unit = box.querySelector(".unitbox");
    if (unit) unit.classList.toggle("unitbox--invalid", show);
    for (const input of box.querySelectorAll("input")) {
      if (show) input.setAttribute("aria-invalid", "true"); else input.removeAttribute("aria-invalid");
    }
  }
  return Object.keys(problems).length === 0;
}

function showBmi() {
  const v = Number($("#patient").elements.bmi.value.replace(",", "."));
  $("#bmi-cat").textContent = Number.isFinite(v) && v > 0 ? "Category: " + window.DiaCausal.bmiCategory(MODEL, v) : "";
}

/** The one-line summary strip (desktop above the thread; phone in the folded panel). No dose. */
function summaryText(p) {
  const n = (x) => String(x).replace(/\.0$/, "");
  return [`Adult, ${n(p.age)} y`, `T2D ${n(p.duration_years)} y`, "on metformin", `HbA1c ${n(p.hba1c)}%`,
    `eGFR ${n(p.egfr)}`, `BMI ${n(p.bmi)}`].join(" · ");
}

function updateStrip(ready) {
  const p = readForm();
  const text = ready ? summaryText(p) : "";
  $("#strip").hidden = !ready;
  $("#strip-text").textContent = text;
  $("#pd-strip").textContent = text || "Not filled in yet";
  for (const b of document.querySelectorAll(".pd-badge")) {
    b.hidden = !ready;
    b.className = `badge pd-badge${fromExample ? " badge--example" : ""}`;
    b.textContent = fromExample ? "Example data" : "Entered by you";
  }
}

/** Panel changed: messages, BMI category, strip, and the thread's empty / ready card. */
function panelChanged(touchedOnly = true) {
  showBmi();
  const ok = showProblems(panelProblems(), touchedOnly);
  updateStrip(ok);
  const thread = $("#thread");
  const intro = thread.querySelector(".thread-intro");
  if (!thread.querySelector(".turn") && (!intro || intro.dataset.ready !== String(ok))) {
    thread.replaceChildren(ok ? readyCard() : emptyCard());
  }
  for (const b of document.querySelectorAll(".compare-btn")) b.disabled = !ok;
  return ok;
}

function emptyCard() { // screen 13
  return h("div", { class: "emptystate thread-intro", "data-ready": "false" }, icon("form", 26, "c-muted"),
    h("div", { class: "stack" }, h("h3", {}, "Fill in the patient details to start"),
      h("p", {}, "DiaCausal compares three second-line options for an adult with type 2 diabetes already on metformin. Nothing is compared until the details are in."),
      h("p", { class: "field__hint" }, "Do not type names, Aadhaar, phone, PAN or email.")));
}

function readyCard() { // screens 14 and 16
  const btn = h("button", { class: "btn btn--primary compare-btn", type: "button" }, "Compare the three options");
  btn.addEventListener("click", compare);
  return h("div", { class: "card thread-intro", "data-ready": "true" }, h("h3", {}, "Details received"),
    h("p", {}, "Compare the three options for this patient, or ask about them below."),
    h("div", { class: "row" }, btn));
}

function newPatient() {
  clearForm();
  fromExample = false;
  pressPreset(-1);
  for (const box of $("#patient").querySelectorAll("[data-field]")) delete box.dataset.touched;
  $("#thread").replaceChildren();
  $("#pd").open = true;
  panelChanged();
}

// ── Patient Details: the conversation and the six stages (screen 20) ──────
const STAGES = [
  ["Checking the question and patient details", "run"],
  ["Applying safety rules", "run"],
  ["Estimating each option's HbA1c change with a 95% interval", "run"],
  ["Retrieving cited passages", "skip"],
  ["Writing the answer (local model, or template if it is unavailable)", "skip"],
  ["Checking the answer before it is shown", "run"],
];
const STATE_WORD = { done: "Done", now: "Running", wait: "Waiting", skip: "Not run on this page yet" };
const STATE_ICON = { done: "done", now: "running", wait: "waiting", skip: "skip" };

function stageItem(name, state) {
  return h("li", { class: `stage stage--${state}`, "aria-current": state === "now" ? "step" : null },
    icon(STATE_ICON[state], 22, state === "done" ? "c-safe" : state === "now" ? "c-pine" : "c-muted"),
    h("span", { class: "stage__name" }, name),
    h("span", { class: "stage__state" }, icon(STATE_ICON[state], 16), " ", STATE_WORD[state]));
}

/** Six steps in pipeline order; the website runs 1–3 and 6 itself, and says so for 4 and 5. */
function stagesCard() {
  const list = h("ul", { class: "stages", "aria-live": "polite" });
  const note = h("p", { class: "field__hint" });
  const card = h("section", { class: "card", "aria-busy": "true" }, h("h2", {}, "Working through it"),
    h("p", {}, "Six steps run in order. Safety rules finish before anything is estimated."), list, note);
  const draw = (step) => {
    list.replaceChildren(...STAGES.map(([name, kind], i) =>
      stageItem(name, kind === "skip" && i < step ? "skip" : i < step ? "done" : i === step ? (kind === "skip" ? "skip" : "now") : "wait")));
    note.textContent = step < STAGES.length ? `Step ${step + 1} of ${STAGES.length}.` : "All steps finished. Retrieval and writing run in the full app; this page shows the engine's own wording.";
    if (step >= STAGES.length) card.removeAttribute("aria-busy");
  };
  return { card, draw };
}

const STAGE_MS = 140;
function compare() {
  if (!panelChanged(false)) return;
  const p = readForm();
  const problems = window.DiaCausal.validate(MODEL, p);
  if (problems.length) return; // the panel's own messages already say what to fix
  let result = null;
  let withheld = null;
  try {
    result = window.DiaCausal.recommend(MODEL, p);
  } catch (e) {
    withheld = e.message;
  }
  const thread = $("#thread");
  if (thread.querySelector(".thread-intro")) thread.replaceChildren();
  thread.append(h("section", { class: "turn" }, h("span", { class: "who" }, "You asked"), h("p", {}, "Compare the three options for this patient.")));
  const { card, draw } = stagesCard();
  thread.append(card);
  if (window.matchMedia("(max-width: 900px)").matches) $("#pd").open = false;
  let step = 0;
  draw(step);
  const next = () => {
    step += 1;
    draw(step);
    if (step < STAGES.length) { setTimeout(next, STAGE_MS); return; }
    const answer = h("section", { class: "answer" });
    thread.append(answer);
    if (withheld) {
      answer.append(h("div", { class: "msgnotice msgnotice--plain" }, icon("stop", 26, "c-danger"),
        h("div", { class: "stack" }, h("span", { class: "msgnotice__word" }, "Answer withheld"),
          h("p", {}, "The output check withheld this answer: " + withheld), h("p", {}, "The clinician decides."))));
    } else {
      render(result, answer);
    }
    answer.scrollIntoView({ block: "start" });
  };
  setTimeout(next, STAGE_MS);
}

function ruleLines(o) {
  return o.safety.map((s) => h("p", { class: `rule rule--${s.action}` },
    h("strong", {}, `Rule ${s.rule_id} · ${s.action === "EXCLUDE" ? "Do not use" : "Check first"}`),
    ` (${s.condition}; rule ${s.rule_status.toLowerCase()}): ${s.message}`,
    h("span", { class: "src" }, `Source: ${s.source} — § ${s.section}`)));
}

function card(o) {
  const caution = o.status === "estimate" && o.safety.length > 0;
  const kind = o.status === "excluded" ? "excluded" : o.status === "insufficient_evidence" ? "insufficient" : caution ? "caution" : "estimate";
  const badge = { excluded: "EXCLUDED", insufficient: "INSUFFICIENT EVIDENCE", caution: "ESTIMATE · CHECK FIRST", estimate: "ESTIMATE" }[kind];
  const body = [];
  if (o.status === "excluded") body.push(h("p", { class: "sub" }, "Not estimated — removed by a safety rule before estimation."));
  if (o.status === "insufficient_evidence") body.push(h("p", { class: "sub" }, o.insufficient_reason));
  if (o.status === "estimate") {
    const e = o.effect;
    body.push(h("p", { class: "est" }, signed(e.value), " ", h("small", {}, `(95% CI ${signed(e.ci_low)} to ${signed(e.ci_high)})`)));
    body.push(h("p", { class: "sub" }, `percentage points of HbA1c at 6 months · propensity ${o.confidence.propensity.toFixed(2)}`));
    if (o.secondary) {
      const w = o.secondary.weight_change_kg, r = o.secondary.hypo_risk_pct;
      body.push(h("dl", { class: "sec" },
        h("dt", {}, "Weight at 6 months"),
        h("dd", {}, h("strong", {}, `${signed(w.value, 1)} kg`), ` (95% CI ${signed(w.ci_low, 1)} to ${signed(w.ci_high, 1)})`),
        h("dt", {}, "Any low sugar by 6 months"),
        h("dd", {}, h("strong", {}, `${r.value.toFixed(1)}%`), ` (95% CI ${r.ci_low.toFixed(1)} to ${r.ci_high.toFixed(1)})`)));
    }
  }
  body.push(...ruleLines(o));
  body.push(h("p", { class: "sub" }, `Cost: ${o.cost.label}`));
  body.push(optionEvidence(o));
  return h("div", { class: `opt opt--${kind}` },
    h("div", { class: "opt__head" },
      h("div", {}, h("div", { class: "opt__name" }, o.name), h("div", { class: "opt__example" }, `e.g. ${o.example_molecule}`)),
      h("span", { class: "opt__badge" }, badge)),
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
    d.append(h("p", { class: "muted" }, "Source passages, not advice. More in Investigate."));
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
    "aria-label": "Expected 6-month HbA1c change for each option with its 95% interval" });
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

/** Today's answer (engine.js output, until P24 builds screens 17/19/21). Ends "The clinician decides." */
function render(result, into) {
  const prev = $("#out");
  if (prev) prev.removeAttribute("id");
  const out = h("div", { class: "card", id: "out" });
  into.append(h("span", { class: "who" }, "DiaCausal answered"), out);
  out.append(printHeader(result));
  out.append(h("h2", {}, "Three options compared for this patient"));
  out.append(h("p", { class: "sub" }, `Safety rules ran first · BMI category: ${result.bmi_category} · Request ID ${result.request_id} · computed on this device`));
  if (result.applicable === "NOT_APPLICABLE") {
    out.append(h("div", { class: "notice" }, h("strong", {}, "Not applicable for this patient: "), result.not_applicable_reasons.join("; ")));
  }
  out.append(h("div", { class: "cards" }, result.options.map(card)));
  if (result.options.some((o) => o.status === "estimate")) {
    out.append(h("div", { class: "stack" }, h("h3", {}, "Estimates with their 95% intervals"), forest(result.options),
      h("p", { class: "sub" }, "Change in HbA1c at 6 months, percentage points. Further left = larger fall. Dashed line = no change.")));
  }
  if (result.comparisons.length) {
    out.append(h("div", { class: "stack" }, h("h3", {}, "Fair comparisons"),
      h("div", { class: "scroll" }, h("table", {},
        h("thead", {}, h("tr", {}, h("th", {}, "Comparison"), h("th", {}, "Difference"), h("th", {}, "95% CI"))),
        h("tbody", {}, result.comparisons.map((c) => h("tr", {},
          h("td", {}, `${LABEL[c.first]} minus ${LABEL[c.second]}`),
          h("td", {}, signed(c.difference.value)),
          h("td", {}, `${signed(c.difference.ci_low)} to ${signed(c.difference.ci_high)}`)))))),
      h("p", { class: "sub" }, "Negative = the first option lowers HbA1c more. An interval that crosses 0 means no clear difference.")));
  }
  if (result.options.some((o) => o.secondary)) {
    out.append(h("p", { class: "sub" }, "Weight and low-sugar figures come from the same synthetic cohort and method as HbA1c; they are secondary outcomes for discussion, not a ranking."));
  }
  const printBtn = h("button", { type: "button", class: "btn btn--ghost noprint" }, "Print or save as PDF (consultation summary)");
  printBtn.addEventListener("click", () => window.print());
  out.append(h("div", { class: "row" }, printBtn));
  out.append(h("details", {}, h("summary", {}, "Assumptions behind these numbers"),
    h("ul", {}, result.assumptions.map((a) => h("li", {}, a))),
    h("p", { class: "muted" }, `Engine ${result.versions.engine} · params ${result.versions.params_sha} · rules ${result.versions.rules_sha} · cohort ${result.versions.cohort}`)));
  out.append(h("details", {}, h("summary", {}, "Structured Causal Output (JSON)"),
    h("pre", {}, JSON.stringify(result, null, 1))));
  out.append(h("div", { class: "decides" }, icon("check", 24, "c-pine"), h("p", {}, result.decision)));
}

function pressPreset(i) {
  document.querySelectorAll("[data-preset]").forEach((b) => b.setAttribute("aria-pressed", String(Number(b.dataset.preset) === i)));
}

/** The message box: a question about the three options, answered from the licence-cleared passages on this device. */
async function askInThread(question) {
  const q = question.trim();
  if (!q) return;
  const thread = $("#thread");
  if (thread.querySelector(".thread-intro")) thread.replaceChildren();
  thread.append(h("section", { class: "turn" }, h("span", { class: "who" }, "You asked"), h("p", {}, q)));
  const box = h("section", { class: "answer" });
  thread.append(box);
  box.append(h("span", { class: "who" }, "DiaCausal answered"));
  const index = await loadEvidence();
  const raw = window.DiaCausalEvidence.search(index, q, { raw: true });
  const res = JSON.parse(JSON.stringify({ ...raw, passages: raw.passages.map(({ _raw, ...p }) => p) }));
  const note = window.DiaCausalExplain.explain(index, q, res);
  const card = h("div", { class: "card" });
  box.append(card);
  if (note.note === index.no_dose_note) {
    card.append(h("p", {}, h("strong", {}, "No doses. "), index.no_dose_note));
  } else if (res.status === "INSUFFICIENT_EVIDENCE") {
    card.append(h("h3", {}, "Insufficient evidence"), h("p", {}, res.reason),
      h("p", {}, "DiaCausal does not guess. Try Investigate, or ask about something the approved sources cover."));
  } else {
    card.append(explanationView(note));
    res.passages.slice(0, 3).forEach((p, i) => {
      const c = p.citation;
      card.append(h("blockquote", { class: "passage" }, h("p", { class: "passage__cite" }, `${i + 1}. Source ${c.source_id}: ${c.title} — “${c.section}”`), excerpt(p.text, q)));
    });
  }
  card.append(h("div", { class: "decides" }, icon("check", 24, "c-pine"), h("p", {}, "These are source passages, not advice. The clinician decides.")));
  box.scrollIntoView({ block: "start" });
}

// ── Analysis (today's benchmark) ──────────────────────────────────────────
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
    tile(cov("AIPW"), "AIPW 95% intervals contain the truth"),
    tile(`${Math.min(...dr).toFixed(0)}–${Math.max(...dr).toFixed(0)}%`, "per-patient intervals contain the truth"),
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
  $("#figures").replaceChildren(...FIGURES.map(([file, title, text]) => h("figure", { class: "card card--flat fig" },
    h("h2", {}, title), h("img", { src: `./results/${file}.png`, alt: `${title} figure`, loading: "lazy" }), h("figcaption", {}, text))));
}

// ── Guide: Methods (for reviewers) ────────────────────────────────────────
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

// ── Investigate (today's evidence search) ─────────────────────────────────
async function loadEvidence() {
  if (!EVIDENCE) EVIDENCE = await fetch("./evidence.json").then((r) => r.json());
  if (!$("#ev-sources").childNodes.length) renderSources();
  $("#guide-passages").textContent = String(EVIDENCE.chunks.length);
  return EVIDENCE;
}

/** Only the sources that are in the search (licence-cleared and confirmed); the full register is RAG/sources.csv. */
function renderSources() {
  const inSearch = EVIDENCE.sources.filter((s) => s.bucket === EVIDENCE.cleared_bucket && s.confirmed);
  $("#ev-sources").replaceChildren(h("table", {},
    h("thead", {}, h("tr", {}, ["ID", "Source", "Licence status"].map((t) => h("th", {}, t)))),
    h("tbody", {}, inSearch.map((s) => h("tr", { class: "src-ok" },
      h("td", {}, s.id), h("td", {}, `${s.title} — ${s.issuer}, ${s.version}`), h("td", {}, "In the search"))))),
  h("p", { class: "field__hint" }, `${EVIDENCE.sources.length - inSearch.length} other sources are tracked in the licence register and are not searched.`));
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

/** The explanation: sentences quoted from the passages, each with its passage number. */
function explanationView(r) {
  const wrap = h("div", { class: "stack" }, h("h3", {}, "Explanation (sentences quoted from the passages)"));
  if (r.status !== "SUCCESS") {
    wrap.append(h("p", { class: "sub" }, `No explanation: ${r.note}`));
    return wrap;
  }
  wrap.append(h("ul", { class: "explain__list" }, r.sentences.map((s) => h("li", {},
    `“${s.text}”`, " ", h("span", { class: "cites" }, s.cites.map((c) => `[${c}]`).join(""))))));
  if (r.note) wrap.append(h("p", { class: "muted" }, r.note));
  wrap.append(h("p", { class: "muted" }, "Numbers in brackets point to the passages."));
  return wrap;
}

async function ask(question) {
  const out = $("#ev-out");
  const q = question.trim();
  if (!q) { out.replaceChildren(h("p", { class: "errors" }, "Please type a question.")); return; }
  const index = await loadEvidence();
  const raw = window.DiaCausalEvidence.search(index, q, { raw: true });
  const res = JSON.parse(JSON.stringify({ ...raw, passages: raw.passages.map(({ _raw, ...p }) => p) }));
  out.replaceChildren();
  const note = window.DiaCausalExplain.explain(index, q, res);
  if (note.note === index.no_dose_note) {
    out.append(h("div", { class: "notice" }, h("strong", {}, "No doses: "), index.no_dose_note,
      h("p", { class: "sub" }, "Ask about safety, kidney function or side effects instead; the approved sources cover those.")));
    return;
  }
  if (res.status === "INSUFFICIENT_EVIDENCE") {
    out.append(h("div", { class: "notice" }, h("strong", {}, "Insufficient evidence: "), res.reason,
      h("p", { class: "sub" }, "DiaCausal does not guess. Ask about something the approved sources cover, or check the sources below.")));
    return;
  }
  out.append(h("div", { class: "card card--flat explain" }, explanationView(note)));
  out.append(h("h2", {}, `${res.passages.length} passages, best match first`));
  res.passages.forEach((p, i) => {
    const c = p.citation;
    out.append(h("article", { class: "card card--flat passage" },
      h("p", { class: "passage__cite" }, `${i + 1}. “${c.section}”, ${c.page === "?" ? "web page" : `page ${c.page}`}`),
      h("p", { class: "src" }, `Source ${c.source_id}: ${c.title}`),
      excerpt(p.text, q),
      h("p", { class: "muted" }, `Scores: keyword (BM25) ${p.scores.bm25} · vector ${p.scores.vector} · fused ${p.scores.rrf}`)));
  });
  out.append(h("div", { class: "decides" }, icon("check", 24, "c-pine"), h("p", {}, "These are source passages, not advice. The clinician decides.")));
  out.append(h("details", { class: "card card--flat" }, h("summary", {}, "Structured evidence (JSON)"), h("pre", {}, JSON.stringify(res, null, 1))));
}

// ── Routing and start-up ──────────────────────────────────────────────────
// Internal names (and the gate in auth.js) stay as before; the tabs use the new names,
// and the old links (#try, #evidence, #results, #learn) still work.
const VIEWS = ["try", "evidence", "results", "guide", "about", "account", "signup", "forgot", "admin"];
const ALIASES = { "patient-details": "try", investigate: "evidence", analysis: "results", learn: "guide" };
const PUBLIC = { try: "patient-details", evidence: "investigate", results: "analysis" };
let returnTo = "try";
let lastGate = null;
let hadSession = false;

const canonical = (name) => ALIASES[name] || (VIEWS.includes(name) ? name : "try");
const viewOf = (name) => (["account", "signup", "forgot", "admin"].includes(name) ? "account" : name);

function show(view) {
  for (const v of document.querySelectorAll(".view")) v.hidden = v.id !== `view-${view}`;
}

function route() {
  if (/access_token=|error_description=/.test(location.hash)) return; // a sign-in link: auth.js reads it first
  const name = canonical((location.hash || "#patient-details").slice(1).split("?")[0]);
  for (const a of document.querySelectorAll(".tabs a")) {
    if (canonical(a.dataset.route) === name) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  }
  const gate = AUTH ? AUTH.view() : "demo";
  if (window.DiaCausalAuth.PROTECTED.includes(name) && gate !== "app" && gate !== "demo") {
    returnTo = name;
    show("account");
    window.DiaCausalAccount.render(gate, name);
  } else if (viewOf(name) === "account") {
    show("account");
    window.DiaCausalAccount.render(gate, name);
  } else {
    show(name);
    if (name === "evidence") loadEvidence().catch(() => { $("#ev-sources").textContent = "Could not load the evidence index."; });
  }
  if (name === "results") renderResults();
  if (name === "guide") loadEvidence().catch(() => {});
  const main = document.querySelector(`#view-${viewOf(name)}`);
  if (main && main.classList.contains("docmain")) main.scrollTop = 0;
}

/** After a sign-in step: go back to the page the person wanted, or refresh the current screen. */
function afterAuthChange() {
  const acct = $("#acct");
  const nameLink = $("#acct-name");
  const gate = AUTH ? AUTH.view() : "demo";
  const p = AUTH && AUTH.state.profile;
  const session = Boolean(AUTH && AUTH.state.session);
  acct.textContent = !AUTH ? "Local copy" : session ? "Sign out" : "Sign in";
  nameLink.hidden = !session;
  nameLink.textContent = session ? (p && p.full_name) || "Your account" : "";
  if (hadSession && !session) newPatient(); // signed out (or timed out): clear the conversation on screen
  hadSession = session;
  if (!session) $("#session-modal").hidden = true;
  const name = canonical((location.hash || "#patient-details").slice(1));
  const opened = gate === "app" && lastGate !== null && lastGate !== "app";
  lastGate = gate;
  if (opened && ["account", "signup", "forgot"].includes(name)) {
    location.hash = "#" + (PUBLIC[returnTo] || returnTo); // the hashchange event re-routes
    return;
  }
  route();
}

/** Screen 08: two minutes before the idle sign-out, ask whether to stay. */
function sessionCheck() {
  if (!AUTH || !AUTH.state.session) return;
  const modal = $("#session-modal");
  const warn = AUTH.idleFor() > AUTH.IDLE_MS - AUTH.WARN_BEFORE_MS;
  if (warn && modal.hidden) { modal.hidden = false; $("#sess-stay").focus(); }
  if (!warn) modal.hidden = true;
  AUTH.idleCheck();
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
    for (const ev of ["pointerdown", "keydown"]) window.addEventListener(ev, () => { if ($("#session-modal").hidden) AUTH.touch(); }, { passive: true });
    setInterval(sessionCheck, 15 * 1000);
  } else {
    $("#demo").hidden = false;
  }
  const v = MODEL.versions;
  $("#versions").textContent = `Engine ${v.engine} · params ${v.params_sha} · rules ${v.rules_sha} · ${v.cohort}`;
  $("#acct").addEventListener("click", (e) => {
    if (AUTH && AUTH.state.session) { e.preventDefault(); AUTH.signOut(); }
  });
  $("#sess-stay").addEventListener("click", () => { AUTH.touch(); $("#session-modal").hidden = true; });
  $("#sess-out").addEventListener("click", () => { $("#session-modal").hidden = true; AUTH.signOut(); });
  document.querySelectorAll("[data-preset]").forEach((b) => b.addEventListener("click", () => {
    const i = Number(b.dataset.preset);
    fillForm(PRESETS[i]);
    fromExample = true;
    pressPreset(i);
    panelChanged(false);
    compare();
  }));
  $("#new-patient").addEventListener("click", newPatient);
  const form = $("#patient");
  form.addEventListener("input", (e) => {
    const box = e.target.closest("[data-field]");
    if (box && e.target.type === "text") box.dataset.touched = "1";
    if (fromExample) { fromExample = false; pressPreset(-1); }
    panelChanged();
  });
  form.addEventListener("change", (e) => {
    const box = e.target.closest("[data-field]");
    if (box) box.dataset.touched = "1";
    panelChanged();
  });
  form.addEventListener("focusout", (e) => {
    const box = e.target.closest("[data-field]");
    if (box && e.target.value !== "") { box.dataset.touched = "1"; panelChanged(); }
  });
  form.addEventListener("submit", (e) => { e.preventDefault(); compare(); });
  $("#composer").addEventListener("submit", (e) => {
    e.preventDefault();
    const box = $("#message");
    askInThread(box.value);
    box.value = "";
  });
  $("#message").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing && e.keyCode !== 229) { e.preventDefault(); $("#composer").requestSubmit(); }
  });
  document.querySelectorAll("[data-doc]").forEach((b) => b.addEventListener("click", () => showDoc(b.dataset.doc)));
  $("#g-methods").addEventListener("toggle", () => { if ($("#g-methods").open && !$("#doc").childNodes.length) showDoc("causal-engine.md"); });
  document.querySelectorAll("[data-jump]").forEach((a) => a.addEventListener("click", (e) => {
    e.preventDefault();
    const target = document.getElementById(a.dataset.jump);
    if (target.tagName === "DETAILS") target.open = true;
    target.scrollIntoView({ block: "start" });
  }));
  $("#share").addEventListener("click", share);
  $("#ask").addEventListener("submit", (e) => { e.preventDefault(); ask($("#ask").elements.q.value); });
  document.querySelectorAll("[data-ask]").forEach((b) => b.addEventListener("click", () => {
    $("#ask").elements.q.value = b.dataset.ask; ask(b.dataset.ask);
  }));
  window.addEventListener("hashchange", route);
  newPatient();
  if (AUTH) await AUTH.refresh(); else afterAuthChange();
  if (/access_token=|error_description=/.test(location.hash)) history.replaceState(null, "", location.pathname + "#account");
  route();
  if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost")) navigator.serviceWorker.register("./sw.js").catch(() => {});
}

document.addEventListener("DOMContentLoaded", start);
