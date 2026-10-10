/*
 * DiaCausal website — page logic. The maths is in engine.js; every number it uses is in
 * model.json. Screens follow design/screens-v2 (Patient Details 09–21, Investigate 22–23, Analysis 24, Guide 25, About 26).
 * Every question is checked by guards.js (the seven input guards) before anything else; a blocked one is never searched,
 * sent or kept.
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
let GUARD = null; // the seven input guards (guards.js + guards.json); null until loaded, and then nothing is searched
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
  safe: ["M7.5 12.5l3 3 6-6.5"],
  warn: ["M12 3.5l9.5 16.5h-19z", "M12 10v4.5", "M12 17.4h.01"],
  lead: ["M5 19V9", "M12 19V5", "M19 19v-7"],
  hidden: ["M3 3l18 18", "M10.6 6.3A9.7 9.7 0 0 1 12 6.2c5 0 8.5 3.6 9.5 5.8a12 12 0 0 1-3.1 3.9",
    "M6.4 8.1A12.3 12.3 0 0 0 2.5 12c1 2.2 4.5 5.8 9.5 5.8 1.4 0 2.7-.3 3.8-.8", "M9.9 10.2a3 3 0 0 0 4.2 4.2"],
  unclear: ["M20.5 12.6c0 3.6-3.8 6.5-8.5 6.5-1 0-2-.1-2.9-.4L3.5 20.5l1.6-4A6.6 6.6 0 0 1 3.5 12c0-3.6 3.8-6.5 8.5-6.5 2 0 3.9.5 5.3 1.5",
    "M14.5 9.5l-5 5", "M9.5 9.5l5 5"],
  search: ["M20 20l-4.2-4.2"],
  external: ["M14 4h6v6", "M20 4l-9 9", "M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"],
};
function icon(name, size = 22, cls = "") {
  const el = svg("svg", { class: `icon ${cls}`.trim(), width: size, height: size, viewBox: "0 0 24 24", fill: "none",
    stroke: "currentColor", "stroke-width": "2.3", "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true" });
  if (["waiting", "clock", "info", "cross", "safe"].includes(name)) el.append(svg("circle", { cx: 12, cy: 12, r: name === "waiting" ? 8.5 : 9 }));
  if (name === "search") el.append(svg("circle", { cx: 11, cy: 11, r: 6.5 }));
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
  ["Retrieving cited passages", "run"],
  ["Writing the answer (sentences quoted from the passages; this page runs no model)", "run"],
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

/** Six steps in pipeline order, all run on this device (step 5 quotes passage sentences; the website runs no model). */
function stagesCard() {
  const list = h("ul", { class: "stages", "aria-live": "polite" });
  const note = h("p", { class: "field__hint" });
  const card = h("section", { class: "card", "aria-busy": "true" }, h("h2", {}, "Working through it"),
    h("p", {}, "Six steps run in order. Safety rules finish before anything is estimated."), list, note);
  const draw = (step) => {
    list.replaceChildren(...STAGES.map(([name, kind], i) =>
      stageItem(name, kind === "skip" && i < step ? "skip" : i < step ? "done" : i === step ? (kind === "skip" ? "skip" : "now") : "wait")));
    note.textContent = step < STAGES.length ? `Step ${step + 1} of ${STAGES.length}.` : "All steps finished, on this device.";
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
  const evidence = loadEvidence();
  const next = async () => {
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
      const built = compareCard(await evidence, result, p);
      renderCard(built.card, answer, { result, passages: built.passages, patient: p });
    }
    answer.scrollIntoView({ block: "start" });
  };
  setTimeout(next, STAGE_MS);
}

// ── Input guards and their notices (screens 09–12; diacausal/guards/input_guards.py, mirrored in guards.js) ─────
/** The panel's patient in the API's names, for the guards. The panel is for patients on metformin and has no glucose field. */
function guardPatient(p) {
  return p ? { age: p.age, type1: Boolean(p.t1d), on_metformin: true, duration_years: p.duration_years, hba1c_pct: p.hba1c, egfr: p.egfr, bmi: p.bmi } : null;
}

/** The seven checks on a question (patient null: Investigate, the question alone). If the checks could not load, nothing runs. */
function checkQuestion(q, patient) {
  if (!GUARD) return { status: "BLOCK", shown: "unavailable", blocked_reason: "The input checks could not load, so nothing was searched. Reload the page and try again." };
  return GUARD.run(q, patient);
}

/** Notice 09 (identifier), 10 (out of scope), 11 (emergency) or 12 (cannot answer as written), from the guard's fixed message.
 *  The message never repeats what was typed. */
function guardNotice(check) {
  const parts = check.blocked_reason.replace(/^Cannot answer as written\.\s*/, "").split(/(?<=\.)\s+(?=[A-Z])/);
  if (check.shown === "red_flag") {
    return h("div", { class: "emergency", role: "alert" }, h("div", { class: "emergency__bar" }, icon("stop", 26), " Emergency"),
      h("div", { class: "emergency__body" }, h("p", { class: "emergency__lead" }, parts.slice(0, -1).join(" ") || parts[0]),
        parts.length > 1 ? h("p", {}, parts[parts.length - 1]) : null));
  }
  const [kind, glyph, word, lines] = check.shown === "identifier" ? ["check", icon("hidden", 28, "c-check"), "Identifier removed — not sent", parts]
    : check.shown === "scope" ? ["info", icon("info", 28, "c-pine"), "Out of scope", [parts.slice(0, -1).join(" "), parts[parts.length - 1]]]
      : ["plain", icon("unclear", 28), "Cannot answer as written", parts];
  return h("div", { class: `msgnotice msgnotice--${kind}`, role: "status", "data-guard": check.shown },
    glyph, h("div", { class: "stack" }, h("span", { class: "msgnotice__word" }, word), ...lines.filter(Boolean).map((t) => h("p", {}, t))));
}

/** What the thread shows for a blocked question: the question (never one holding an identifier) and the notice. */
function blockedTurn(thread, q, check) {
  const said = check.shown === "identifier" ? "[Not shown: it contained a patient identifier, so it was removed and not sent.]" : q;
  thread.append(h("section", { class: "turn" }, h("span", { class: "who" }, "You asked"), h("p", {}, said)), guardNotice(check));
}

// ── The answer card (AnswerCardV1, screens 17, 19 and 21; docs/ANSWER_FORMAT.md) ───────────────
const armName = (arm) => MODEL.arms.find((a) => a.arm === arm).name;
const pct = (x) => `${signed(x, 2)} %`;
const ci = (x, d = 2, sign = true) => `95% CI ${sign ? signed(x.ci_low, d) : x.ci_low.toFixed(d)} to ${sign ? signed(x.ci_high, d) : x.ci_high.toFixed(d)}`;
const WORDS = ["No", "One", "Two", "Three"];

/** The evidence level as the design's 3-bar meter and its word (never "High"). */
function levelMeter(level) {
  const filled = { Moderate: 2, Low: 1 }[level] || 0;
  const g = svg("svg", { class: "icon", width: 22, height: 18, viewBox: "0 0 23 18", "aria-hidden": "true" });
  [[2, 11, 6], [9, 7, 10], [16, 3, 14]].forEach(([x, y, hh], i) => {
    g.append(i < filled ? svg("rect", { x, y, width: 5, height: hh, rx: 1, fill: "currentColor" })
      : svg("rect", { x: x + 0.8, y: y + 0.8, width: 3.4, height: hh - 1.6, rx: 1, fill: "none", stroke: "currentColor", "stroke-width": 1.6 }));
  });
  return h("span", { class: "level" }, g, " ", level || "Not assessed");
}

/** Dot-and-interval glyph on the design's -1.6 to 0 % axis (positions set through the CSSOM, never a style attribute). */
function dtrack(text, x) {
  const at = (v) => `${Math.max(0, Math.min(100, ((v + 1.6) / 1.6) * 100)).toFixed(2)}%`;
  const bar = h("span", { class: "dci" }), dot = h("span", { class: "dpt" });
  bar.style.left = at(x.ci_low);
  bar.style.width = `${(parseFloat(at(x.ci_high)) - parseFloat(at(x.ci_low))).toFixed(2)}%`;
  dot.style.left = at(x.value);
  return h("span", { class: "dtrack", role: "img", "aria-label": text, title: text }, bar, dot);
}

function citeButton(n, onOpen) {
  const b = h("button", { class: "cite", type: "button", "aria-label": `Evidence ${n} — open source` }, String(n));
  b.addEventListener("click", () => onOpen(n));
  return b;
}

/** Safety checks: one card per option, with the rule ID and source of every rule that fired. */
function safetyCards(card, result) {
  return h("div", { class: "scards" }, result.options.map((o) => {
    const stop = card.excluded.filter((r) => r.option === o.arm), check = card.cautions.filter((r) => r.option === o.arm);
    const kind = stop.length ? "stop" : check.length ? "check" : "safe";
    const word = { stop: "Do not use", check: "Check first", safe: "Safe to consider" }[kind];
    const fired = [...stop, ...check];
    const why = kind === "stop" ? "Removed before estimation. It is not compared with the others."
      : kind === "check" ? o.safety.filter((s) => s.action === "CAUTION").map((s) => s.message).join(" ")
        : "No exclusion or check-first rule matched for this record.";
    return h("article", { class: `scard scard--${kind}` }, h("h4", {}, armName(o.arm)),
      h("span", { class: "scard__word" }, icon({ stop: "stop", check: "warn", safe: "safe" }[kind], 20), ` ${word}`),
      h("p", {}, why),
      fired.length ? fired.map((r) => h("p", { class: "scard__rule" }, h("span", {}, h("strong", {}, "Rule"), ` ${r.rule_id}`),
        h("span", {}, h("strong", {}, "Source"), ` ${r.source}`)))
        : h("p", { class: "scard__rule" }, h("span", {}, h("strong", {}, "Rule"), " none fired"),
          h("span", {}, h("strong", {}, "Source"), ` the rules table, version ${card.versions.rules_sha}`)));
  }));
}

/** The finding box: a leader only when its interval vs DPP-4i excludes 0, and only on HbA1c (pine, never green). */
function finding(card) {
  const comp = card.effects.find((e) => e.option === card.comparator);
  const leads = window.DiaCausalCard.leaders(card);
  if (!comp || !comp.hba1c_change) {
    return h("div", { class: "finding finding--even" }, icon("info", 24, "c-muted"),
      h("p", {}, h("strong", {}, "No comparison against DPP-4 inhibitor for this patient."), " It has no estimate, so no option is set against it."));
  }
  if (!leads.length) {
    return h("div", { class: "finding finding--even" }, icon("info", 24, "c-muted"),
      h("p", {}, h("strong", {}, "No clear difference in HbA1c for this patient."), " Every difference against DPP-4 inhibitor has a 95% interval that includes zero."));
  }
  return h("div", { class: "finding" }, icon("lead", 24, "c-pine"), h("p", {}, ...leads.flatMap((e) => {
    const d = e.vs_comparator, more = d.ci_high < 0;
    const [a, b] = more ? [armName(e.option), armName(card.comparator)] : [armName(card.comparator), armName(e.option)];
    return [h("strong", {}, `${a} shows more HbA1c lowering than ${b} for this patient:`),
      ` difference ${pct(d.value)} (${ci(d)}). The interval excludes zero. `];
  }), "This is a difference on HbA1c only."));
}

function optionsTable(card) {
  const leads = new Set(window.DiaCausalCard.leaders(card).filter((e) => e.vs_comparator.ci_high < 0).map((e) => e.option));
  const levels = Object.fromEntries(card.evidence_levels.map((l) => [l.option, l]));
  const removed = new Set(card.excluded.map((r) => r.option));
  const rows = card.effects.map((e) => {
    const name = armName(e.option);
    const mini = removed.has(e.option) ? ["stop", "Do not use"] : e.caution ? ["check", "Check first"] : ["safe", "Safe to consider"];
    const head = h("th", { scope: "row" }, name, h("span", { class: "sub" }, "added to metformin"),
      h("span", { class: `mini mini--${mini[0]}` }, icon({ stop: "stop", check: "warn", safe: "safe" }[mini[0]], 16), ` ${mini[1]}`),
      leads.has(e.option) ? h("span", { class: "badge badge--pine leadtag" }, icon("lead", 16), " More HbA1c lowering than DPP-4i") : null);
    const lv = levels[e.option];
    const levelCell = h("td", { "data-label": "Evidence level" }, levelMeter(lv ? lv.level : null),
      h("span", { class: "ci" }, lv ? lv.reason : `Removed by rule ${card.excluded.filter((r) => r.option === e.option).map((r) => r.rule_id).join(", ")} before estimation.`));
    const cost = h("td", { "data-label": "Cost" }, e.cost_label, h("span", { class: "ci" }, "per month"));
    if (!e.hba1c_change) {
      const rule = card.excluded.filter((r) => r.option === e.option).map((r) => r.rule_id).join(", ");
      return h("tr", { class: removed.has(e.option) ? "row--excluded" : null }, head,
        h("td", { "data-label": "HbA1c change at 6 months" }, h("span", { class: "num" }, removed.has(e.option) ? "Not estimated" : "No estimate"),
          h("span", { class: "ci" }, removed.has(e.option) ? `Removed by rule ${rule} before estimation` : "Insufficient evidence (see below)")),
        h("td", { "data-label": "vs DPP-4i" }, "—"), h("td", { "data-label": "Any hypoglycaemia" }, "—"),
        h("td", { "data-label": "Weight change at 6 months" }, "—"), cost, levelCell);
    }
    const x = e.hba1c_change, d = e.vs_comparator;
    const glyph = `${name}: ${pct(x.value)} (${ci(x)})`;
    const versus = e.option === card.comparator
      ? [h("span", { class: "num" }, "Comparator"), h("span", { class: "ci" }, "DPP-4 inhibitor is the reference")]
      : d ? [h("span", { class: "num" }, pct(d.value)), h("span", { class: "ci" }, ci(d)),
        h("span", { class: "zero" }, icon(d.ci_high < 0 || d.ci_low > 0 ? "check" : "info", 16), d.ci_high < 0 || d.ci_low > 0 ? " Interval excludes 0" : " Interval includes 0")]
        : ["—"];
    return h("tr", {}, head,
      h("td", { "data-label": "HbA1c change at 6 months" }, h("span", { class: "num" }, pct(x.value)), h("span", { class: "ci" }, ci(x)), dtrack(glyph, x)),
      h("td", { "data-label": "vs DPP-4i" }, ...versus),
      h("td", { "data-label": "Any hypoglycaemia" }, e.hypo_risk_pct ? [h("span", { class: "num" }, `${e.hypo_risk_pct.value.toFixed(1)} %`), h("span", { class: "ci" }, ci(e.hypo_risk_pct, 1, false))] : "—"),
      h("td", { "data-label": "Weight change at 6 months" }, e.weight_change_kg ? [h("span", { class: "num" }, `${signed(e.weight_change_kg.value, 1)} kg`), h("span", { class: "ci" }, ci(e.weight_change_kg, 1))] : "—"),
      cost, levelCell);
  });
  return h("div", { class: "tablewrap" }, h("table", { class: "options" },
    h("caption", { class: "sr-only" }, "Three options compared for this patient"),
    h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Option"),
      h("th", { scope: "col" }, "HbA1c change, 6 months", h("br"), h("span", { class: "th-note" }, "dot = estimate · bar = 95% CI · axis −1.6 to 0 %")),
      h("th", { scope: "col" }, "Difference vs DPP-4i"), h("th", { scope: "col" }, "Any hypo­glycaemia"),
      h("th", { scope: "col" }, "Weight, 6 months"), h("th", { scope: "col" }, "Cost, ₹/month"), h("th", { scope: "col" }, "Evidence level"))),
    h("tbody", {}, rows)));
}

function tradeOffs(card) {
  const shown = card.effects.filter((e) => e.hba1c_change);
  const items = [];
  const w = shown.filter((e) => e.weight_change_kg);
  if (w.length) items.push(h("li", {}, h("strong", {}, "Weight:"), " " + w.map((e) => `${armName(e.option)} ${signed(e.weight_change_kg.value, 1)} kg (${ci(e.weight_change_kg, 1)})`).join("; ") + "."));
  const y = shown.filter((e) => e.hypo_risk_pct);
  if (y.length) items.push(h("li", {}, h("strong", {}, "Any hypoglycaemia by 6 months:"), " " + y.map((e) => `${armName(e.option)} ${e.hypo_risk_pct.value.toFixed(1)} % (${ci(e.hypo_risk_pct, 1, false)})`).join("; ") + "."));
  items.push(h("li", {}, h("strong", {}, "Cost:"), " " + card.effects.map((e) => `${armName(e.option)}: ${e.cost_label}`).join("; ") + "."));
  return [h("h3", {}, "Trade-offs"), h("ul", { class: "trade" }, items),
    h("p", { class: "small muted" }, "Weight and hypoglycaemia come from the same synthetic cohort and method as HbA1c; they are for discussion, not a ranking.")];
}

/** "What drives this estimate" (screen 17; P25): for each option with an estimate, its comparison against DPP-4i, up to 3 CLEAR
 *  drivers (95% interval excludes zero) in HbA1c points and plain words, with their 95% intervals and the dot-and-interval glyph.
 *  Drivers describe the estimate: it is larger or smaller for patients with these details. They are never causes. */
function driversSection(card, patient) {
  const comp = card.effects.find((e) => e.option === card.comparator);
  const rows = card.effects.filter((e) => e.hba1c_change && e.option !== card.comparator && e.vs_comparator);
  if (!comp || !comp.hba1c_change || !rows.length || !patient) return [];
  const labels = MODEL.xai.labels;
  const amount = (v) => Math.abs(v).toFixed(3);
  const words = (phi) => (phi < 0 ? "more lowering" : "less lowering");
  const glyph = (text, phi, lo, hi, axis) => {
    const at = (v) => `${Math.max(0, Math.min(100, 50 + (-v / axis) * 50)).toFixed(2)}%`; // right of 0 = more lowering
    const zero = h("span", { class: "dzero" }), bar = h("span", { class: "dci" }), dot = h("span", { class: "dpt" });
    zero.style.left = "50%";
    bar.style.left = at(hi);
    bar.style.width = `${(parseFloat(at(lo)) - parseFloat(at(hi))).toFixed(2)}%`;
    dot.style.left = at(phi);
    return h("span", { class: "dtrack", role: "img", "aria-label": text, title: text }, zero, bar, dot);
  };
  const blocks = rows.map((e) => {
    const target = `${e.option}-${card.comparator}`;
    const ex = window.DiaCausal.explainEffect(MODEL, patient, target);
    const shown = (card.drivers[e.option] || []).map((d) => ex.contributions.find((c) => c.feature === d.feature));
    const d = e.vs_comparator;
    const head = h("p", { class: "small muted" }, h("strong", {}, `${armName(e.option)} vs ${armName(card.comparator)}`),
      `: ${pct(d.value)} for this patient (${ci(d)}); ${pct(ex.base)} for the average patient. Up to ${MODEL.xai.max_drivers} clear drivers, in HbA1c points.`);
    if (!shown.length) return [head, h("p", {}, "No single patient detail clearly drives this estimate.")];
    const axis = Math.max(0.1, Math.ceil(Math.max(...shown.map((c) => Math.max(Math.abs(c.ci_low), Math.abs(c.ci_high)))) / 0.05) * 0.05);
    const lines = shown.map((c) => {
      const l = labels[c.feature] || { text: c.feature.replace(/_/g, " "), kind: "continuous", unit: "" };
      const who = l.kind === "yes_no" ? `${l.text[0].toUpperCase()}${l.text.slice(1)}: ${c.value ? "yes" : "no"}`
        : `${c.value > c.mean ? "Higher" : "Lower"} ${l.text} — this patient ${g3(c.value)}${l.unit || ""}`;
      const [lo, hi] = c.phi < 0 ? [-c.ci_high, -c.ci_low] : [c.ci_low, c.ci_high];
      const text = `${who}: ${amount(c.phi)} ${words(c.phi)} (95% CI ${f3(lo)} to ${f3(hi)})`;
      return h("div", { class: "drow" }, h("p", {}, h("strong", {}, `${who}:`), ` ${amount(c.phi)} ${words(c.phi)} `,
        h("span", { class: "muted" }, `(95% CI ${f3(lo)} to ${f3(hi)})`)), h("div", {}, glyph(text, c.phi, c.ci_low, c.ci_high, axis)));
    });
    const rest = window.DiaCausal.otherDetails(MODEL, patient, target, shown.map((c) => c.feature));
    const [rlo, rhi] = rest.phi < 0 ? [-rest.ci_high, -rest.ci_low] : [rest.ci_low, rest.ci_high];
    lines.push(h("div", { class: "drow" }, h("p", {}, h("strong", {}, "All other details together:"), ` ${amount(rest.phi)} ${words(rest.phi)} `,
      h("span", { class: "muted" }, `(95% CI ${f3(rlo)} to ${f3(rhi)})`)), h("span", {})));
    lines.push(h("div", { class: "drow" }, h("span", {}), h("div", { class: "daxis" }, h("span", {}, "← less lowering"), h("span", {}, "0"), h("span", {}, "more lowering →"))));
    return [head, ...lines];
  });
  return [h("details", { class: "drivers", open: true }, h("summary", {}, h("h3", {}, "What drives this estimate")),
    ...blocks.flat(),
    h("p", { class: "small muted" }, "The estimate is larger or smaller for patients with these details. These show how the estimate changes across patients like this one. They are not causes."))];
}
const g3 = (v) => String(Number(v.toFixed(3)));
const f3 = (v) => (v < 0 ? "−" : "") + Math.abs(v).toFixed(3); // a true minus sign, as everywhere else on the card

/** The abstain card of plan 8.11, exactly: one per option whose level is Insufficient. */
function abstainCards(card) {
  return card.abstain.map((n) => h("div", { class: "abstaincard", role: "note" },
    h("p", {}, h("strong", {}, `Insufficient evidence for: ${MODEL.short_names[n.option]}`)),
    h("p", {}, `Why: ${n.why}.`), h("p", {}, MODEL.still_see), h("p", {}, `The clinician decides. ${card.intended_use}`)));
}

/** Cited evidence: the quoted sentences with their citation markers, then every cited passage. Each number opens the
 *  evidence drawer (screen 18), where the passage is shown exactly as stored. */
function citedEvidence(card, passages) {
  const open = (n) => openEvidence(n, passages[n - 1]);
  const sources = h("div", { class: "basis" }, h("strong", {}, "Sources cited"),
    passages.map((p, i) => h("p", { class: "srcline" }, citeButton(i + 1, open), ` ${window.DiaCausalCard.label(p.citation)} — “${p.citation.section}”`)),
    h("p", { class: "small" }, `Estimates: DiaCausal causal engine ${card.versions.engine}, synthetic India-calibrated cohort, params ${card.versions.params_sha}, rules ${card.versions.rules_sha}.`));
  const number = Object.fromEntries(passages.map((p, i) => [p.chunk_id, i + 1]));
  const list = card.claims.length
    ? h("ul", { class: "trade" }, card.claims.map((c) => h("li", {}, `“${c.text}”`, ...c.citations.map((x) => citeButton(number[x.chunk_id], open)))))
    : h("p", { class: "sub" }, "No passage sentence is quoted for this answer.");
  return [h("h3", {}, "Cited evidence"), list, h("p", { class: "small muted" }, "Sentences quoted from licence-cleared sources, not advice. Tap a number to read the passage."), sources];
}

// ── The evidence drawer (screen 18): one passage exactly as stored, with where it came from ─────────────────────
let drawerReturn = null;
const sourceOf = (id) => (EVIDENCE && EVIDENCE.sources.find((x) => x.id === id)) || {};
const pageText = (page) => (page && page !== "?" ? String(page) : "Web page (no page numbers)");

/** Source, version, section, page and licence of a passage, as recorded in the index and the licence register. */
function citationMeta(c, withChecked) {
  const src = sourceOf(c.source_id);
  const rows = [["Source", `${c.source_id} · ${src.issuer ? `${src.issuer}, ` : ""}${c.title}`], ["Version", c.version || "not recorded"],
    ["Section", `§ ${c.section}`], ["Page", pageText(c.page)], ["Licence", src.licence_as_found || "not recorded"]];
  if (withChecked) rows.push(["Checked", `Licence checked ${src.date_checked || "(date not recorded)"} · index ${EVIDENCE.versions.corpus_sha}`]);
  return h("dl", { class: "meta" }, rows.flatMap(([k, v]) => [h("dt", {}, k), h("dd", {}, v)]));
}

/** A short report for the team: passage ID, source and versions. No patient detail and no question is included. */
function mismatchReport(passage) {
  const c = passage.citation, v = EVIDENCE.versions, m = MODEL.versions;
  return ["DiaCausal evidence mismatch report", `Passage: ${passage.chunk_id}`,
    `Source: ${c.source_id}, ${c.title}, ${c.version}, § ${c.section}, page ${c.page}`,
    `Index: corpus ${v.corpus_sha}, sources ${v.sources_sha}, settings ${v.config_sha}`,
    `Engine: ${m.engine}, params ${m.params_sha}, rules ${m.rules_sha}`,
    "What does not match (write it here; do not add patient details):"].join("\n");
}

function openEvidence(n, passage) {
  if (!passage) return;
  const opener = document.activeElement;
  closeEvidence();
  drawerReturn = opener;
  const c = passage.citation;
  const close = h("button", { class: "iconbtn", type: "button", "aria-label": "Close evidence" }, icon("cross", 22));
  const inv = h("button", { class: "btn btn--ghost", type: "button" }, icon("search", 20), " Open in Investigate");
  const report = h("button", { class: "btn btn--ghost", type: "button" }, "Report a mismatch");
  const status = h("div", { class: "stack", role: "status" });
  const drawer = h("aside", { class: "drawer noprint", id: "drawer", role: "dialog", "aria-modal": "true", "aria-labelledby": "ev-title" },
    h("div", { class: "drawer__head" }, h("div", { class: "stack" }, h("span", { class: "who" }, `Evidence ${n}`), h("h2", { id: "ev-title" }, c.title)), close),
    citationMeta(c, true), h("h3", {}, "Retrieved passage"), h("blockquote", { class: "passage" }, passage.text),
    h("p", { class: "field__hint" }, "Shown exactly as stored. If it does not support the claim it is attached to, report it."),
    h("div", { class: "row" }, inv, report), status);
  const scrim = h("div", { class: "scrim noprint", id: "scrim" });
  document.body.append(scrim, drawer);
  close.addEventListener("click", closeEvidence);
  scrim.addEventListener("click", closeEvidence);
  inv.addEventListener("click", () => { closeEvidence(); showInInvestigate(passage); });
  report.addEventListener("click", async () => {
    const text = mismatchReport(passage);
    try {
      await navigator.clipboard.writeText(text);
      status.replaceChildren(h("p", { class: "field__hint" }, "Report copied: passage ID, source and versions, no patient details. Paste it into a message to the team."));
    } catch {
      status.replaceChildren(h("p", { class: "field__hint" }, "Copy this report and send it to the team:"), h("pre", {}, text));
    }
  });
  drawer.addEventListener("keydown", (e) => { // Esc closes; Tab stays inside the drawer
    if (e.key === "Escape") { e.preventDefault(); closeEvidence(); return; }
    if (e.key !== "Tab") return;
    const items = [...drawer.querySelectorAll("button, a[href], pre")].filter((el) => !el.hidden);
    const first = items[0], last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  });
  close.focus();
}

function closeEvidence() {
  const d = $("#drawer");
  if (!d) return;
  d.remove();
  $("#scrim")?.remove();
  if (drawerReturn && drawerReturn.isConnected) drawerReturn.focus();
  drawerReturn = null;
}

/** Draws one AnswerCardV1. `result` is the engine's output (for the rule messages); `passages` are the cited passages. */
function renderCard(card, into, { result, passages = [], patient = null }) {
  const prev = $("#out");
  if (prev) prev.removeAttribute("id");
  const out = h("section", { class: "card", id: "out", "aria-labelledby": `ans-${card.request_id}` });
  into.append(out);
  out.append(printHeader(result), h("div", { class: "card__head" }, h("span", { class: "who" }, "DiaCausal answered")));
  const anyEstimate = card.effects.some((e) => e.hba1c_change);
  const removed = card.excluded.map((r) => r.option).filter((v, i, a) => a.indexOf(v) === i).length;
  const checks = card.cautions.map((r) => r.option).filter((v, i, a) => a.indexOf(v) === i).length;
  const facts = h("p", { class: "sub" }, h("strong", {}, "Question: "), card.question, h("br"), h("strong", {}, "Patient: "), card.patient_summary);
  if (!anyEstimate) { // screen 19
    // every option removed by a rule (no abstain notice): the reasons are the rules themselves
    const reasons = card.abstain.length ? [...new Set(card.abstain.map((n) => n.why))].map((why) => why[0].toUpperCase() + why.slice(1) + ".")
      : card.excluded.map((r) => `${armName(r.option)} was removed by rule ${r.rule_id} before any estimate was made (${r.source}).`);
    out.append(h("h2", { id: `ans-${card.request_id}` }, card.abstain.length ? "Insufficient evidence — no comparison shown" : "No comparison shown — the safety rules removed every option"), facts,
      h("div", { class: "finding finding--check" }, icon("info", 24, "c-check"), h("p", {}, "DiaCausal will not show estimates for this patient.")),
      h("h3", {}, "Why"), h("ul", { class: "stages" }, reasons.map((text) =>
        h("li", { class: "stage" }, h("span", { class: "stage__name stage__name--plain" }, text)))),
      h("p", { class: "field__hint" }, "Only the reasons that applied are listed."),
      h("h3", {}, "What you can do instead"), h("ul", { class: "stages" },
        ["Check the patient details for a typing error, then compare again.",
          "Look up the question in Investigate, which shows cited passages without estimates.",
          "Use your usual guideline, as you would without this tool."].map((t) => h("li", { class: "stage" }, icon("check", 20, "c-pine"), h("span", { class: "stage__name stage__name--plain" }, t)))),
      ...abstainCards(card), h("h3", {}, "Safety checks"), safetyCards(card, result), ...citedEvidence(card, passages));
  } else { // screens 17 (a leader) and 21 (no clear difference)
    const leader = window.DiaCausalCard.leaders(card).length > 0;
    out.append(h("h2", { id: `ans-${card.request_id}` }, "Three options compared for this patient"), facts,
      h("div", { class: "guardrail" }, icon("shield", 24, "c-pine"), h("p", {}, `Safety rules ran first. ${removed ? `${WORDS[removed]} of the three options ${removed === 1 ? "was" : "were"} removed before any estimate was made` : "No option was removed"}${checks ? `; ${WORDS[checks].toLowerCase()} ${checks === 1 ? "needs" : "need"} checking` : ""}.`)),
      h("h3", {}, "Safety checks"), safetyCards(card, result));
    if (!leader) out.append(finding(card), ...tradeOffs(card), h("h3", {}, "HbA1c at 6 months"), optionsTable(card));
    else out.append(h("h3", {}, "HbA1c at 6 months"), finding(card), optionsTable(card));
    out.append(h("p", { class: "legend" }, h("strong", {}, "Evidence level"), " — Moderate: a narrow interval, enough similar patients and at least two cited passages. Low: a wide interval, few similar patients or fewer than two cited passages. Insufficient: no estimate is shown. It is never “High”, because every estimate comes from a synthetic cohort."));
    if (leader) out.append(...tradeOffs(card));
    out.append(...driversSection(card, patient), ...abstainCards(card), ...citedEvidence(card, passages));
  }
  const printBtn = h("button", { type: "button", class: "btn btn--ghost noprint" }, "Print or save as PDF (consultation summary)");
  printBtn.addEventListener("click", () => window.print());
  out.append(h("div", { class: "row" }, printBtn),
    h("details", { class: "noprint" }, h("summary", {}, "Answer card (AnswerCardV1, JSON)"), h("pre", {}, JSON.stringify(card, null, 1))),
    h("p", { class: "field__hint intended-line" }, card.intended_use),
    h("div", { class: "decides" }, icon("check", 24, "c-pine"), h("p", {}, "The clinician decides.")));
  return out;
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

/** Passages that name one option (its class word or example molecule), from three searches: at most two. */
function optionPassages(index, o) {
  const conds = o.safety.map((s) => s.condition).join(" ");
  const keys = [o.name.split(" ")[0].toLowerCase(), o.example_molecule.toLowerCase()];
  const about = (p) => p.text !== index.withheld_text && keys.some((k) => p.text.toLowerCase().includes(k));
  const seen = new Set();
  const shown = [];
  for (const q of [`${o.name} ${conds}`, `${o.name} safety`, o.name]) {
    const res = window.DiaCausalEvidence.search(index, q, { raw: true });
    for (const p of res.passages.filter(about)) {
      if (!seen.has(p._raw.chunk_id) && shown.length < 2) { seen.add(p._raw.chunk_id); shown.push({ chunk_id: p._raw.chunk_id, text: p.text, citation: p.citation }); }
    }
    if (shown.length >= 2) break;
  }
  return shown;
}

/** The card for "Compare the three options": each option's own passages are its citations; one quoted sentence each. */
function compareCard(index, result, p) {
  const passages = [];
  const textsByOption = {};
  const sentences = [];
  for (const o of result.options) {
    const mine = optionPassages(index, o);
    textsByOption[o.arm] = mine.map((x) => x.text);
    for (const x of mine) if (!passages.some((y) => y.chunk_id === x.chunk_id)) passages.push(x);
    if (o.status === "excluded" || !mine.length) continue;
    const note = window.DiaCausalExplain.template(index, `${o.name} ${o.safety.map((s) => s.condition).join(" ")}`, { status: "SUCCESS", passages: mine });
    const s = note.sentences && note.sentences[0];
    if (s) sentences.push({ text: s.text, cites: [passages.findIndex((y) => y.chunk_id === mine[s.cites[0] - 1].chunk_id) + 1] });
  }
  return { card: window.DiaCausalCard.build(MODEL, result, p, { passages, sentences, textsByOption, withheldText: index.withheld_text }), passages };
}

/** The card for a question about this patient: the question's passages and quoted sentences (Patient Details and Investigate). */
function questionCard(index, result, p, q, raw) {
  const passages = raw.passages.map((x) => ({ chunk_id: x._raw.chunk_id, text: x.text, citation: x.citation }));
  const res = JSON.parse(JSON.stringify({ ...raw, passages: raw.passages.map(({ _raw, ...x }) => x) }));
  const note = window.DiaCausalExplain.explain(index, q, res);
  const sentences = note.status === "SUCCESS" ? note.sentences : [];
  return { card: window.DiaCausalCard.build(MODEL, result, p, { question: q, passages, sentences, withheldText: index.withheld_text,
    retrievalAbstained: raw.status !== "SUCCESS" }), passages };
}

/** The panel's patient when it is complete and plausible (else null). */
function readyPatient() {
  if (!MODEL || Object.keys(panelProblems()).length) return null;
  const p = readForm();
  return window.DiaCausal.validate(MODEL, p).length ? null : p;
}

function pressPreset(i) {
  document.querySelectorAll("[data-preset]").forEach((b) => b.setAttribute("aria-pressed", String(Number(b.dataset.preset) === i)));
}

/** The message box: a question about the three options. With the patient filled in, the answer is the card for that patient
 *  (the question's passages are its cited evidence); without, the quoted passages alone. Nothing leaves the device. */
async function askInThread(question) {
  const q = question.trim();
  if (!q) return;
  const thread = $("#thread");
  if (thread.querySelector(".thread-intro")) thread.replaceChildren();
  const check = checkQuestion(q, guardPatient(readyPatient()));
  if (window.matchMedia("(max-width: 900px)").matches) $("#pd").open = false; // on a phone, fold the panel so the reply is in view
  if (check.status === "BLOCK") { // never searched, sent or kept; the message box is already empty
    blockedTurn(thread, q, check);
    thread.lastElementChild.previousElementSibling.scrollIntoView({ block: "start" });
    return;
  }
  thread.append(h("section", { class: "turn" }, h("span", { class: "who" }, "You asked"), h("p", {}, q)));
  const box = h("section", { class: "answer" });
  thread.append(box);
  const index = await loadEvidence();
  const raw = window.DiaCausalEvidence.search(index, q, { raw: true });
  const res = JSON.parse(JSON.stringify({ ...raw, passages: raw.passages.map(({ _raw, ...p }) => p) }));
  const note = window.DiaCausalExplain.explain(index, q, res);
  const patient = readyPatient();
  if (note.note === index.no_dose_note) {
    box.append(h("span", { class: "who" }, "DiaCausal answered"), h("div", { class: "card" }, h("p", {}, h("strong", {}, "No doses. "), index.no_dose_note),
      h("div", { class: "decides" }, icon("check", 24, "c-pine"), h("p", {}, "The clinician decides."))));
  } else if (patient) {
    const result = window.DiaCausal.recommend(MODEL, patient);
    const built = questionCard(index, result, patient, q, raw);
    renderCard(built.card, box, { result, passages: built.passages, patient });
  } else {
    box.append(h("span", { class: "who" }, "DiaCausal answered"));
    const card = h("div", { class: "card" });
    box.append(card);
    if (res.status === "INSUFFICIENT_EVIDENCE") {
      card.append(h("h3", {}, "Insufficient evidence"), h("p", {}, res.reason),
        h("p", {}, "DiaCausal does not guess. Try Investigate, or ask about something the approved sources cover."));
    } else {
      card.append(explanationView(note));
      res.passages.slice(0, 3).forEach((p, i) => {
        const c = p.citation;
        card.append(h("blockquote", { class: "passage" }, h("p", { class: "passage__cite" }, `${i + 1}. Source ${c.source_id}: ${c.title} — “${c.section}”`), excerpt(p.text, q)));
      });
    }
    card.append(h("p", { class: "field__hint" }, "Fill in the patient details to see the three options compared for that patient."),
      h("div", { class: "decides" }, icon("check", 24, "c-pine"), h("p", {}, "These are source passages, not advice. The clinician decides.")));
  }
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
  $("#lvl-table").replaceChildren(h("table", {},
    h("thead", {}, h("tr", {}, ["Evidence level", "Patient-option pairs", "Share", "Interval contains the truth", "Mean interval width"].map((t) => h("th", {}, t)))),
    h("tbody", {}, (RESULTS.evidence_levels || []).filter((r) => r.option === "all").map((r) => h("tr", {},
      h("td", {}, r.level), h("td", {}, Number(r.n).toLocaleString("en-IN")), h("td", {}, `${(Number(r.share) * 100).toFixed(1)}%`),
      h("td", {}, r.coverage_95 === "" ? "—" : `${(Number(r.coverage_95) * 100).toFixed(1)}%`),
      h("td", {}, r.mean_ci_width === "" ? "—" : `${Number(r.mean_ci_width).toFixed(2)} points`))))));
  renderAblation();
  $("#figures").replaceChildren(...FIGURES.map(([file, title, text]) => h("figure", { class: "card card--flat fig" },
    h("h2", {}, title), h("img", { src: `./results/${file}.png`, alt: `${title} figure`, loading: "lazy" }), h("figcaption", {}, text))));
}

/** Screen 24 (P26 numbers, drawn in P27): the A-D table (results/xai_ablation.csv) and three charts drawn as SVG here, with no chart
 *  library (results.json xai_charts: mean |SHAP| for A and C, LIME stability for A). Synthetic benchmark only. */
const VERSIONS = [["A", "XAI only", "SHAP + LIME on a model that predicts HbA1c"], ["B", "Causal only", "Safety rules + causal engine"],
  ["C", "Causal + XAI", "B + exact SHAP on the causal estimate"], ["D", "Causal + XAI + RAG", "C + drivers steer the cited passages and checks"]];
const ABLATION_COLS = [ // metric, comparison, column title, a share?, what an empty cell means
  ["regret", "all", "Policy regret (HbA1c points, lower is better)", false, "Not measured"],
  ["pehe", "SGLT2i-DPP4i", "Error of the patient-level effect, SGLT2i vs DPP-4i (PEHE, lower is better)", false, "Not measured"],
  ["coverage", "SGLT2i-DPP4i", "95% interval coverage, SGLT2i vs DPP-4i", true, "No interval"],
  ["answered_when_thin_pairs", "all", "Numbers given for options this patient almost never gets (lower is safer)", true, "Not measured"],
  ["modifier_precision_at_k", "SGLT2i-DPP4i", "Top features are the true effect modifiers", true, "No explanation"],
  ["false_driver_rate", "SGLT2i-DPP4i", "Shown drivers that are not true modifiers (lower is better)", true, "No drivers with intervals"],
  ["citation_precision", "all", "Quoted sentences supported by their passage (60 gold questions)", true, "No citations"],
  ["number_match_pass", "all", "Local-model drafts whose every number is the engine's (20 golden questions)", true, "No model draft"],
  ["abstention_rate", "all", "Answers withheld", true, "Not measured"],
];
const fmtShare = (x) => `${(Number(x) * 100).toFixed(0)}%`;

function renderAblation() {
  const rows = RESULTS.xai_ablation || [];
  if (!rows.length) { $("#xai-table").replaceChildren(h("p", { class: "sub" }, "The A-D table has not been run yet.")); return; }
  const cell = (v, [metric, comparison, title, share, empty]) => {
    const r = rows.find((x) => x.version === v && x.metric === metric && x.comparison === comparison);
    const td = h("td", { "data-label": title });
    if (!r || r.mean === "") { td.append(empty); return td; }
    const n = (x) => (share ? fmtShare(x) : Number(x).toFixed(3));
    td.append(n(r.mean));
    if (r.ci_low !== "") td.append(h("span", { class: "ci" }, `95% CI ${n(r.ci_low)} to ${n(r.ci_high)}`));
    return td;
  };
  $("#xai-table").replaceChildren(h("table", { class: "rtable" }, h("caption", { class: "sr-only" }, "Versions A to D, synthetic benchmark"),
    h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Version"), h("th", { scope: "col" }, "Uses"), ABLATION_COLS.map((c) => h("th", { scope: "col" }, c[2])))),
    h("tbody", {}, VERSIONS.map(([v, name, uses]) => h("tr", {}, h("th", { scope: "row" }, v, h("span", { class: "ci" }, name)),
      h("td", { "data-label": "Uses" }, uses), ABLATION_COLS.map((c) => cell(v, c)))))));
  renderXaiCharts();
}

/** One horizontal-bar chart: label, an SVG bar on a 0..max axis, the value; then "Show values as a table" (screen 24's .crow rows). */
function barChart(title, sub, items, { max, axisEnd, valueText, header, note }) {
  const crow = (it) => {
    const text = `${it.label}: ${valueText(it.value)}`;
    const graph = svg("svg", { class: "cbar", viewBox: "0 0 100 24", preserveAspectRatio: "none", role: "img", "aria-label": text },
      svg("rect", { class: "cbar__track", x: 0, y: 11, width: 100, height: 2 }),
      svg("rect", { class: it.mark ? "cbar__bar cbar__bar--mark" : "cbar__bar", x: 0, y: 5, width: Math.max(0.5, Math.min(100, (it.value / max) * 100)).toFixed(2), height: 14 }));
    graph.append(svg("title", {}, text));
    return h("div", { class: "crow" }, h("span", { class: "crow__label" }, it.label + (it.mark ? " *" : "")), graph, h("span", { class: "crow__val" }, valueText(it.value)));
  };
  return [h("h3", {}, title), h("p", { class: "chart__sub" }, sub), ...items.map(crow),
    h("div", { class: "caxis" }, h("span", {}), h("span", {}, h("span", {}, "0"), h("span", {}, axisEnd)), h("span", {})),
    note ? h("p", { class: "chart__sub" }, note) : null,
    h("details", { class: "tview" }, h("summary", {}, "Show values as a table"),
      h("table", {}, h("thead", {}, h("tr", {}, header.map((t) => h("th", {}, t)))),
        h("tbody", {}, items.map((it) => h("tr", {}, h("td", {}, it.label + (it.mark ? " *" : "")), h("td", {}, valueText(it.value)), ...(it.extra || []).map((x) => h("td", {}, x)))))))].filter(Boolean);
}

function renderXaiCharts() {
  const x = RESULTS.xai_charts;
  if (!x || !x.shap_A_vs_C.length) { $("#xai-charts").replaceChildren(); $("#xai-lime").replaceChildren(); return; }
  const label = (f) => { const t = (MODEL.xai.labels[f] || { text: f.replace(/_/g, " ") }).text; return t[0].toUpperCase() + t.slice(1); };
  const top = (v) => [...x.shap_A_vs_C].sort((a, b) => b[v] - a[v]).slice(0, 6).map((r) => ({ label: label(r.feature), value: r[v], mark: r.true_modifier }));
  const nice = (v) => { const step = 10 ** Math.floor(Math.log10(v)); return Number((Math.ceil(v / step) * step).toPrecision(2)); };
  const [a, b] = x.shap_comparison.split("-");
  const pair = `${LABEL[a]} vs ${LABEL[b]}`;
  const chart = (v, title, sub, note) => {
    const items = top(v);
    const max = nice(Math.max(...items.map((i) => i.value)));
    return h("section", { class: "card card--flat chart" }, ...barChart(title, sub, items, { max, axisEnd: `${max} HbA1c points`,
      valueText: (z) => z.toFixed(3), header: ["Feature", "Mean |SHAP| (HbA1c points)"], note }));
  };
  $("#xai-charts").replaceChildren(
    chart("A", "A · SHAP on the HbA1c prediction model", `${pair}. Explains what the prediction model uses to predict HbA1c. It does not explain treatment effects.`,
      "Scales differ between A and C: compare the order, not the bar lengths."),
    chart("C", "C · SHAP on the causal estimate", `${pair}. The estimate is larger or smaller for patients with these features. These are not causes.`,
      `Mean absolute SHAP value over the test patients of the synthetic cohorts (${x.reps} cohorts). * = a true effect modifier of the synthetic cohort.`));
  const PRESET = { typical: "Typical patient", egfr40_pancreatitis: "eGFR 40, past pancreatitis", older_hypo: "Older, past hypoglycaemia" };
  const lime = x.lime_stability.map((r) => { const [o1, o2] = r.comparison.split("-");
    return { label: `${PRESET[r.preset] || r.preset} · ${LABEL[o1]} vs ${LABEL[o2]}`, value: Number(r.lime_top3_jaccard), extra: [r.n_seeds] }; });
  $("#xai-lime").replaceChildren(...barChart("LIME stability across reruns (version A)",
    `Share of the top-3 features that stay the same when LIME is rerun with ${lime.length ? x.lime_stability[0].n_seeds : ""} different random seeds (0 = none, 1 = all). One value per example patient and comparison, so no interval.`,
    lime, { max: 1, axisEnd: "1", valueText: (z) => z.toFixed(2), header: ["Example patient · comparison", "Stability (0 to 1)", "Seeds"],
      note: "Only version A uses LIME. Version C's SHAP values are computed exactly, so a rerun gives the same values." }));
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

/** The licence-cleared sources: in the search (confirmed by a team member), or cleared and not yet added. */
function renderSources() {
  const cleared = EVIDENCE.sources.filter((x) => x.bucket === EVIDENCE.cleared_bucket);
  const year = (v) => (String(v || "").match(/\d{4}/) || [""])[0];
  $("#ev-sources").replaceChildren(h("ul", { class: "srclist" }, cleared.map((x) => h("li", { class: x.confirmed ? "src-ok" : "src-later" },
    h("strong", {}, `${x.id} · ${x.issuer}${year(x.version) ? `, ${year(x.version)}` : ""}`), h("span", {}, x.title),
    x.confirmed ? h("span", { class: "state c-safe" }, icon("safe", 16), " In the search") : h("span", { class: "state c-check" }, icon("clock", 16), " Cleared, not yet added")))),
  h("p", { class: "field__hint" }, `Only licence-cleared sources are searched. ${EVIDENCE.chunks.length} passages in the index. ${EVIDENCE.sources.length - cleared.length} other sources are tracked in the licence register and are not searched.`));
}

/** One passage as stored (screen 22): number, title, source, version, section, page, licence, the text, and two actions. */
function resultCard(p, i) {
  const c = p.citation, src = sourceOf(c.source_id);
  const copy = h("button", { class: "btn btn--ghost", type: "button" }, icon("copy", 20), " Copy citation");
  copy.addEventListener("click", async () => {
    const text = `${c.source_id}: ${c.title}, ${c.version}, § ${c.section}, ${c.page && c.page !== "?" ? `page ${c.page}` : "web page"}.`;
    try { await navigator.clipboard.writeText(text); copy.lastChild.textContent = " Citation copied"; } catch { copy.lastChild.textContent = " Could not copy"; }
  });
  const actions = h("div", { class: "row" }, copy);
  if (/^https:\/\//.test(src.url || "")) {
    actions.append(h("a", { class: "btn btn--ghost", href: src.url, target: "_blank", rel: "noopener noreferrer" }, icon("external", 20), " Open source"));
  }
  return h("article", { class: "card card--flat result" },
    h("div", { class: "row" }, h("span", { class: "result__num" }, String(i + 1)), h("h3", {}, c.title)),
    citationMeta(c, false), h("blockquote", { class: "passage" }, p.text), actions);
}

/** Screen 23: no passage answers the search. */
function insufficientView() {
  const li = (t) => h("li", {}, t);
  return h("section", { class: "card card--flat", role: "status", "aria-labelledby": "none-h" },
    h("div", { class: "finding finding--check" }, icon("info", 24, "c-check"),
      h("p", {}, h("strong", { id: "none-h" }, "Insufficient evidence."), " No passage in the licence-cleared sources answers this search.")),
    h("h3", {}, "Why this can happen"),
    h("ul", { class: "trade" }, li("The topic is not covered by the sources currently in the search."), li("The search words differ from the wording the source uses.")),
    h("h3", {}, "What you can do"),
    h("ul", { class: "trade" }, li("Try different words, or one of the example searches above."), li("Check the list of sources to see what is covered."),
      li("Use your usual guideline. DiaCausal does not write an answer when it has no source.")));
}

const toPatientDetails = () => h("p", {}, h("a", { class: "btn btn--ghost", href: "#patient-details" }, "See the three options for this patient in Patient Details"));
const passagesEnd = () => h("div", { class: "decides" }, icon("check", 24, "c-pine"), h("p", {}, "These are source passages, not advice. The clinician decides."));

/** Investigate (screens 22 and 23): the seven checks, then the passages as stored. Nothing is generated here. */
async function ask(question) {
  const out = $("#ev-out");
  const q = question.trim();
  if (!q) { out.replaceChildren(h("p", { class: "errors" }, "Please type a search.")); return; }
  await searchAndShow(out, q);
  if (window.matchMedia("(max-width: 900px)").matches) out.scrollIntoView({ block: "start" }); // on a phone the results are below the box
}

async function searchAndShow(out, q) {
  const check = checkQuestion(q, null);
  if (check.status === "BLOCK") { // never searched or kept
    if (check.shown === "identifier") $("#q").value = "";
    out.replaceChildren(guardNotice(check));
    return;
  }
  const index = await loadEvidence();
  const raw = window.DiaCausalEvidence.search(index, q, { raw: true });
  if (window.DiaCausalExplain.explain(index, q, { ...raw, passages: [] }).note === index.no_dose_note) {
    out.replaceChildren(guardNotice({ shown: "dose_request", blocked_reason: index.no_dose_note }));
    return;
  }
  if (raw.status !== "SUCCESS") { out.replaceChildren(insufficientView()); return; }
  const passages = raw.passages.map((x) => ({ chunk_id: x._raw.chunk_id, text: x.text, citation: x.citation }));
  out.replaceChildren(h("p", { class: "muted" }, `${passages.length} passage${passages.length === 1 ? "" : "s"} found · ranked by keyword and TF-IDF search, fused`),
    ...passages.map(resultCard), toPatientDetails(), passagesEnd());
}

/** "Open in Investigate" from the drawer: that one passage, as stored. */
async function showInInvestigate(passage) {
  location.hash = "#investigate";
  await loadEvidence();
  $("#ev-out").replaceChildren(h("p", { class: "muted" }, "The passage you opened from the answer"), resultCard(passage, 0), toPatientDetails(), passagesEnd());
  $("#ev-out").scrollIntoView({ block: "start" });
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
  let config, guards;
  [MODEL, RESULTS, config, guards] = await Promise.all([
    fetch("./model.json").then((r) => r.json()),
    fetch("./results.json").then((r) => r.json()).catch(() => null),
    fetch("./config.json").then((r) => (r.ok ? r.json() : null)).catch(() => null),
    fetch("./guards.json").then((r) => r.json()).catch(() => null), // without it, nothing typed is searched
  ]);
  if (guards && window.DiaCausalGuards) GUARD = window.DiaCausalGuards.make(guards);
  if (window.matchMedia("(max-width: 900px)").matches) document.querySelectorAll("details[data-phone-closed]").forEach((d) => { d.open = false; });
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
    $("#thread .compare-btn")?.focus();
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
