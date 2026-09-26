// Builds docs/midsem/DiaCausal_MidSem_Presentation.pptx (22 slides, 4:3, FCRIT college format).
//   npm install pptxgenjs@3.12.0   (once, anywhere on NODE_PATH)
//   node scripts/make_midsem_deck.js
// Numbers on the slides come from results/ (synthetic data) and docs/RESULTS_SUMMARY.md.
// Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.
const path = require("path");
const pptxgen = require("pptxgenjs");

const ROOT = path.resolve(__dirname, "..");
const M = (p) => path.join(ROOT, "docs", "midsem", p);
const R = (p) => path.join(ROOT, p);
const OUT = M("DiaCausal_MidSem_Presentation.pptx");

const NAVY = "002060", INK = "1F2328", MUTED = "5B6470", PALE = "EEF2F8", LINE = "C9D2E3";
const RED = "8A1010", REDF = "FADCDC", AMBER = "6E4400", AMBERF = "FBEBCB", GREY = "3F4744", GREYF = "ECEEEC", TEAL = "00897B";
const INTENDED = "Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.";
const TITLE_FONT = "Times New Roman", BODY = "Calibri", MONO = "Courier New";

const pres = new pptxgen();
pres.layout = "LAYOUT_4x3"; // 10 x 7.5 in
pres.title = "DiaCausal — Major Project Progress Presentation-II";
pres.author = "Group 28, FCRIT Vashi";

let slideNo = 0;
function content(title, presenter, notes) {
  const s = pres.addSlide();
  slideNo += 1;
  s.background = { color: "FFFFFF" };
  s.addImage({ path: M("fcritlogo.jpg"), x: 9.0, y: 0.12, w: 0.78, h: 0.79 });
  s.addText(title, { x: 0.8, y: 0.2, w: 8.1, h: 0.75, fontFace: TITLE_FONT, fontSize: 28, bold: true, color: NAVY, align: "center", valign: "middle", margin: 0, isTextBox: true });
  s.addShape(pres.shapes.LINE, { x: 0.4, y: 1.02, w: 9.2, h: 0, line: { color: NAVY, width: 1.25 } }); // college format rule
  s.addText(`Group 28 · DiaCausal · ${presenter}`, { x: 0.4, y: 7.1, w: 6, h: 0.3, fontFace: BODY, fontSize: 10, color: MUTED, margin: 0, isTextBox: true });
  s.addText(String(slideNo), { x: 8.9, y: 7.1, w: 0.7, h: 0.3, fontFace: BODY, fontSize: 10, color: MUTED, align: "right", margin: 0, isTextBox: true });
  if (notes) s.addNotes(`Presenter: ${presenter}. ${notes}`);
  return s;
}
function bullets(s, items, opts) {
  const runs = items.map((t, i) => {
    const parts = Array.isArray(t) ? t : [t];
    return parts.map((p, j) => ({
      text: typeof p === "string" ? p : p.text,
      options: { bold: typeof p === "object" && p.bold, breakLine: j === parts.length - 1 && i < items.length - 1,
        paraSpaceAfter: 8, color: INK },
    }));
  }).flat();
  s.addText(runs, { fontFace: BODY, fontSize: 17, valign: "top", margin: 0.05, paraSpaceAfter: 8, isTextBox: true, ...opts });
}
function card(s, x, y, w, h, fill) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color: fill || PALE }, line: { color: LINE, width: 0.75 } });
}
function table(s, rows, opts) {
  const head = rows[0].map((t) => ({ text: t, options: { bold: true, color: "FFFFFF", fill: { color: NAVY } } }));
  const body = rows.slice(1).map((r, i) => r.map((t) => (typeof t === "object" ? t : { text: t, options: { fill: { color: i % 2 ? "FFFFFF" : "F5F7FB" } } })));
  s.addTable([head, ...body], { fontFace: BODY, fontSize: 12, color: INK, border: { type: "solid", pt: 0.5, color: LINE }, valign: "middle", margin: 0.05, ...opts });
}

// ── 1. Title ─────────────────────────────────────────────────────────────
{
  const s = pres.addSlide(); slideNo += 1;
  s.background = { color: "FFFFFF" };
  s.addShape(pres.shapes.RECTANGLE, { x: 0.4, y: 0.35, w: 9.2, h: 1.95, fill: { color: "FFFFFF" }, line: { color: NAVY, width: 1 } });
  s.addImage({ path: M("fcritlogo.jpg"), x: 0.6, y: 0.5, w: 1.6, h: 1.62 });
  s.addText([
    { text: "Agnel Charities'", options: { italic: true, fontSize: 15, breakLine: true } },
    { text: "Fr. C. Rodrigues Institute of Technology, Vashi", options: { bold: true, fontSize: 21, breakLine: true } },
    { text: "(An Autonomous Institute & Permanently Affiliated to University of Mumbai)", options: { bold: true, fontSize: 12, color: "C00000", breakLine: true } },
    { text: "Computer Engineering Department", options: { bold: true, fontSize: 15 } },
  ], { x: 2.35, y: 0.45, w: 7.1, h: 1.75, fontFace: TITLE_FONT, color: INK, align: "center", valign: "middle", margin: 0, isTextBox: true });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.4, y: 2.75, w: 9.2, h: 1.9, fill: { color: NAVY }, line: { color: NAVY } });
  s.addText([
    { text: "Major Project Progress Presentation-II", options: { fontSize: 30, bold: true, breakLine: true } },
    { text: "B.Tech (Computer) Sem - VII", options: { fontSize: 24 } },
  ], { x: 0.5, y: 2.8, w: 9.0, h: 1.8, fontFace: TITLE_FONT, color: "FFFFFF", align: "center", valign: "middle", margin: 0, isTextBox: true });
  s.addText("2026-27", { x: 0.4, y: 4.9, w: 9.2, h: 0.8, fontFace: TITLE_FONT, fontSize: 36, bold: true, color: "7F7F7F", align: "center", margin: 0, isTextBox: true });
  s.addText("DiaCausal: Intelligent Diabetes Clinical Decision Support System using Causal Inference and RAG", { x: 0.6, y: 5.9, w: 8.8, h: 0.6, fontFace: BODY, fontSize: 16, color: NAVY, align: "center", margin: 0, isTextBox: true });
  s.addText(INTENDED, { x: 0.6, y: 6.6, w: 8.8, h: 0.5, fontFace: BODY, fontSize: 11, italic: true, color: MUTED, align: "center", margin: 0, isTextBox: true });
  s.addNotes("Presenter: Pratham. Good morning. We are Group 28. Our project is DiaCausal, a decision-support prototype for choosing the second diabetes drug after metformin. It is a research prototype for clinician evaluation, not a medical device.");
}

// ── 2. Project and team ──────────────────────────────────────────────────
{
  const s = pres.addSlide(); slideNo += 1;
  s.background = { color: "FFFFFF" };
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 1.9, fill: { color: NAVY }, line: { color: NAVY } });
  s.addText("Intelligent Diabetes Clinical Decision Support System using Causal Inference and RAG", { x: 0.4, y: 0.2, w: 8.3, h: 1.5, fontFace: TITLE_FONT, fontSize: 26, bold: true, color: "FFFFFF", valign: "middle", margin: 0, isTextBox: true });
  s.addImage({ path: M("fcritlogo.jpg"), x: 8.85, y: 0.5, w: 0.9, h: 0.91 });
  s.addText("Group No. 28", { x: 0.6, y: 2.25, w: 8.8, h: 0.55, fontFace: TITLE_FONT, fontSize: 24, bold: true, color: NAVY, margin: 0, isTextBox: true });
  const people = [["Pratham Pawar", "1023226"], ["Graceton Santhmayor", "1022246"], ["Rhian Roy Kuttikadan", "1023268"], ["Advik Saxena", "1023245"]];
  people.forEach(([n, r], i) => {
    const x = 0.6 + (i % 2) * 4.5, y = 3.05 + Math.floor(i / 2) * 1.05;
    card(s, x, y, 4.2, 0.85);
    s.addText([{ text: n, options: { bold: true, fontSize: 19, breakLine: true } }, { text: `Roll no. ${r}`, options: { fontSize: 13, color: MUTED } }],
      { x: x + 0.2, y, w: 3.8, h: 0.85, fontFace: BODY, color: INK, valign: "middle", margin: 0, isTextBox: true });
  });
  s.addText([{ text: "Guide: ", options: { bold: true, color: NAVY } }, { text: "Mr. Rahul Jadhav" }], { x: 0.6, y: 5.35, w: 8.8, h: 0.55, fontFace: BODY, fontSize: 21, color: INK, margin: 0, isTextBox: true });
  s.addText("Department of Computer Engineering · Fr. C. Rodrigues Institute of Technology, Vashi · 2026–27", { x: 0.6, y: 6.2, w: 8.8, h: 0.4, fontFace: BODY, fontSize: 13, color: MUTED, margin: 0, isTextBox: true });
  s.addNotes("Presenter: Pratham. Our team: Pratham, Graceton, Rhian and Advik, guided by Mr. Rahul Jadhav.");
}

// ── 3. Outline ───────────────────────────────────────────────────────────
{
  const s = content("Presentation Outline", "Pratham", "We follow the six items the department asked for, and end with what is completed and what is planned for October.");
  const items = [["1", "Proposed System", "slides 4–6"], ["2", "Hardware & Software Requirements", "slides 7–8"], ["3", "Timeline / Gantt Chart", "slide 9"],
    ["4", "System Design", "slides 10–13"], ["5", "Implementation", "slides 14–15"], ["6", "Initial Results / Demo", "slides 16–18"]];
  items.forEach(([n, t, sub], i) => {
    const x = 0.55 + (i % 2) * 4.55, y = 1.35 + Math.floor(i / 2) * 1.55;
    card(s, x, y, 4.35, 1.35);
    s.addShape(pres.shapes.OVAL, { x: x + 0.22, y: y + 0.35, w: 0.66, h: 0.66, fill: { color: NAVY }, line: { color: NAVY } });
    s.addText(n, { x: x + 0.22, y: y + 0.35, w: 0.66, h: 0.66, fontFace: BODY, fontSize: 20, bold: true, color: "FFFFFF", align: "center", valign: "middle", margin: 0, isTextBox: true });
    s.addText([{ text: t, options: { bold: true, fontSize: 17, breakLine: true } }, { text: sub, options: { fontSize: 12, color: MUTED } }],
      { x: x + 1.05, y, w: 3.15, h: 1.35, fontFace: BODY, color: INK, valign: "middle", margin: 0, isTextBox: true });
  });
  s.addText("Then: completed vs planned work (slide 19) · conclusion · references", { x: 0.55, y: 6.1, w: 8.9, h: 0.5, fontFace: BODY, fontSize: 15, italic: true, color: NAVY, margin: 0, isTextBox: true });
}

// ── 4. Proposed system: the problem ──────────────────────────────────────
{
  const s = content("Proposed System — the Problem", "Rhian", "When metformin alone is not enough, the doctor adds a second drug. Which one helps this patient most is a what-if question. Old records mislead because doctors gave SGLT2 inhibitors to sicker patients. In this made-up example the naive difference is minus 0.425, but comparing like with like gives minus 0.15, about three times smaller.");
  bullets(s, [
    [{ text: "Adult with type 2 diabetes, ", bold: false }, { text: "already on metformin", bold: true }, " and not controlled."],
    ["Add one of three: ", { text: "SGLT2 inhibitor, DPP-4 inhibitor or sulfonylurea", bold: true }, "."],
    ["Question: ", { text: "what would this patient's HbA1c be in 6 months under each?", bold: true }],
    ["Plain comparisons mislead: sicker patients got SGLT2i more often (", { text: "confounding by indication", bold: true }, ")."],
    "India: 101 million adults with diabetes (ICMR-INDIAB 2023); no open Indian dataset records drug and outcome.",
  ], { x: 0.5, y: 1.25, w: 4.5, h: 5.6, fontSize: 15 });
  table(s, [["Group", "Got SGLT2i", "Got SU", "Diff."],
    ["High HbA1c", "300 pts, −1.2", "100 pts, −1.0", "−0.2"], ["Lower HbA1c", "100 pts, −0.6", "300 pts, −0.5", "−0.1"],
    [{ text: "Naive (pooled)", options: { bold: true } }, "−1.05", "−0.625", { text: "−0.425", options: { bold: true, color: RED } }]],
    { x: 5.2, y: 1.4, w: 4.4, colW: [1.25, 1.1, 1.1, 0.95], fontSize: 12 });
  card(s, 5.2, 3.7, 4.4, 2.3, "F5F7FB");
  s.addText([
    { text: "Like with like: ", options: { bold: true, color: NAVY } },
    { text: "0.5 × (−0.2) + 0.5 × (−0.1) = ", options: {} },
    { text: "−0.15", options: { bold: true, color: TEAL, breakLine: true } },
    { text: "The naive answer is about 3× too big. Causal inference corrects this.", options: { fontSize: 13, color: MUTED } },
  ], { x: 5.4, y: 3.8, w: 4.0, h: 2.1, fontFace: BODY, fontSize: 16, color: INK, valign: "middle", margin: 0, isTextBox: true });
  s.addText("Illustrative synthetic numbers; HbA1c change in %", { x: 5.2, y: 6.1, w: 4.4, h: 0.3, fontFace: BODY, fontSize: 10, italic: true, color: MUTED, margin: 0, isTextBox: true });
}

// ── 5. Proposed system: how it works ─────────────────────────────────────
{
  const s = content("Proposed System — How It Works", "Rhian", "Every request follows the same order. Safety rules first remove unsafe drugs. Then the propensity model checks if enough similar patients got each drug; if not, we say insufficient evidence. Otherwise AIPW and the DR-learner give the six-month HbA1c change with a 95 percent range. Then cost, then cited evidence, and the clinician decides. Everything is logged without patient values.");
  const steps = [["Patient details", "age, HbA1c, eGFR, BMI, history"], ["Safety rules", "cited drug-label rules remove unsafe options"], ["Propensity + overlap", "enough similar patients?"],
    ["AIPW / DR-learner", "6-month HbA1c change ± 95% range"], ["Cost lookup", "INR / month, dated"], ["Cited evidence (RAG)", "licence-cleared passages"], ["Clinician decides", "decision support only"]];
  steps.forEach(([t, sub], i) => {
    const y = 1.3 + i * 0.8;
    const fill = i === 6 ? NAVY : "FFFFFF";
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.8, y, w: 4.6, h: 0.62, rectRadius: 0.08, fill: { color: fill }, line: { color: NAVY, width: 1 } });
    s.addText([{ text: `${i + 1}. ${t}`, options: { bold: true, breakLine: true, color: i === 6 ? "FFFFFF" : NAVY } }, { text: sub, options: { fontSize: 11, color: i === 6 ? "DDE4F0" : MUTED } }],
      { x: 0.95, y, w: 4.3, h: 0.62, fontFace: BODY, fontSize: 14, valign: "middle", margin: 0, isTextBox: true });
    if (i < 6) s.addShape(pres.shapes.LINE, { x: 3.1, y: y + 0.62, w: 0, h: 0.18, line: { color: NAVY, width: 1.25, endArrowType: "triangle" } });
  });
  card(s, 5.9, 2.75, 3.7, 1.25, GREYF);
  s.addText([{ text: "Too few similar patients? ", options: { bold: true, color: GREY } }, { text: "Show “insufficient evidence”, never a guess (propensity < 0.05).", options: {} }],
    { x: 6.05, y: 2.8, w: 3.4, h: 1.15, fontFace: BODY, fontSize: 13, color: INK, valign: "middle", margin: 0, isTextBox: true });
  s.addShape(pres.shapes.LINE, { x: 5.4, y: 2.91, w: 0.5, h: 0.45, line: { color: GREY, width: 1, dashType: "dash", endArrowType: "triangle" } });
  card(s, 5.9, 4.3, 3.7, 1.75, "F5F7FB");
  s.addText([{ text: "Audit log ", options: { bold: true, color: NAVY } }, { text: "records versions, statuses and rule IDs for every request — never the patient's values.", options: {} }],
    { x: 6.05, y: 4.35, w: 3.4, h: 1.65, fontFace: BODY, fontSize: 13, color: INK, valign: "middle", margin: 0, isTextBox: true });
}

// ── 6. Safety rules ──────────────────────────────────────────────────────
{
  const s = content("Proposed System — Safety Rules", "Advik", "Six rules are never broken, and tests check each one. The strongest: safety rules always run before any estimate, and we never show drug doses.");
  const rules = [["Decision support only", "the clinician always decides"], ["Safety first", "cited rules run before any estimate; excluded options are never estimated"],
    ["Honest uncertainty", "every estimate has a 95% interval"], ["Refuse to guess", "“insufficient evidence” when propensity < 0.05"],
    ["No doses, no invented rules", "thresholds live only in rules.csv, each with a source"], ["Synthetic data only", "every generator number has a source and a status"]];
  rules.forEach(([t, sub], i) => {
    const x = 0.5 + (i % 2) * 4.6, y = 1.3 + Math.floor(i / 2) * 1.35;
    card(s, x, y, 4.4, 1.15);
    s.addShape(pres.shapes.OVAL, { x: x + 0.18, y: y + 0.28, w: 0.58, h: 0.58, fill: { color: NAVY }, line: { color: NAVY } });
    s.addText(String(i + 1), { x: x + 0.18, y: y + 0.28, w: 0.58, h: 0.58, fontFace: BODY, fontSize: 17, bold: true, color: "FFFFFF", align: "center", valign: "middle", margin: 0, isTextBox: true });
    s.addText([{ text: t, options: { bold: true, fontSize: 15, breakLine: true } }, { text: sub, options: { fontSize: 12, color: MUTED } }],
      { x: x + 0.9, y, w: 3.4, h: 1.15, fontFace: BODY, color: INK, valign: "middle", margin: 0, isTextBox: true });
  });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 5.45, w: 9.0, h: 1.0, fill: { color: NAVY }, line: { color: NAVY } });
  s.addText([{ text: "On every screen and every reply: ", options: { bold: true, breakLine: true } }, { text: INTENDED, options: {} }],
    { x: 0.7, y: 5.45, w: 8.6, h: 1.0, fontFace: BODY, fontSize: 14, color: "FFFFFF", valign: "middle", margin: 0, isTextBox: true });
}

// ── 7. Hardware & software ───────────────────────────────────────────────
{
  const s = content("Hardware & Software Requirements", "Advik", "Everything runs on an ordinary laptop, and the website runs on any phone. All software is open source and all hosting is on free tiers, so the running cost is zero.");
  table(s, [["Tier", "Hardware", "Software"],
    ["Development", "Laptop, ≥ 8 GB RAM (MacBook Air, Apple silicon)", "Python 3.12, NumPy, pandas, scikit-learn, Matplotlib, pytest, Node.js 24, Git/GitHub"],
    ["Causal engine & API", "Same laptop", "FastAPI, Uvicorn, Pydantic; Streamlit demo"],
    ["Website", "Any phone or laptop browser", "HTML/CSS/JS installable app (works offline); Netlify hosting; Supabase accounts (Mumbai)"],
    ["Chat application", "Laptop or 2-CPU / 4 GB server", "FastAPI, React, TypeScript, SQLite, faster-whisper, Docker"],
    ["RAG", "Same laptop", "PDF parser, BM25 + vector search, rank fusion; template / free online / local model"],
    ["Documentation", "Any laptop", "LaTeX (Overleaf), presentation software"]],
    { x: 0.5, y: 1.3, w: 9.0, colW: [1.8, 2.6, 4.6], fontSize: 12.5 });
  card(s, 0.5, 6.0, 9.0, 0.75, "F5F7FB");
  s.addText([{ text: "Cost: ", options: { bold: true, color: NAVY } }, { text: "₹0 — open-source software and free hosting tiers; effort ≈ 670 person-hours (4 members × 12 h/week × 14 weeks)." }],
    { x: 0.7, y: 6.0, w: 8.6, h: 0.75, fontFace: BODY, fontSize: 14, color: INK, valign: "middle", margin: 0, isTextBox: true });
}

// ── 8. System requirements ───────────────────────────────────────────────
{
  const s = content("System Requirements", "Advik", "Functional requirements say what the system does; nine of twelve are already done. Non-functional requirements say how well: safety tested automatically, under three seconds, privacy, usability score of 68 or more.");
  s.addText("Functional (status on 26 Sept)", { x: 0.5, y: 1.2, w: 4.4, h: 0.4, fontFace: BODY, fontSize: 16, bold: true, underline: { style: "sng" }, color: NAVY, margin: 0, isTextBox: true });
  table(s, [["ID", "Requirement", "Status"],
    ["FR1–2", "Capture and validate patient details, units", "Done"], ["FR3", "Cited safety rules with reasons", "Done"],
    ["FR4–5", "Propensity, overlap, “insufficient evidence”", "Done"], ["FR6", "6-month HbA1c change ± 95%", "Done"],
    ["FR7", "Hypoglycaemia risk, weight change", "In progress"], ["FR8", "Cost (INR/month), dated", "Done*"],
    ["FR9", "Cited explanation (RAG)", "Retrieval done"], ["FR10", "Audit log (no patient values)", "Done"],
    ["FR11", "Consultation summary", "In progress"], ["FR12", "Sign-up, MFA, admin approval", "Done"]],
    { x: 0.5, y: 1.65, w: 4.6, colW: [0.8, 2.6, 1.2], fontSize: 11 });
  s.addText("*prices shown as “unavailable” until confirmed", { x: 0.5, y: 6.55, w: 4.6, h: 0.3, fontFace: BODY, fontSize: 9.5, italic: true, color: MUTED, margin: 0, isTextBox: true });
  s.addText("Non-functional", { x: 5.4, y: 1.2, w: 4.2, h: 0.4, fontFace: BODY, fontSize: 16, bold: true, underline: { style: "sng" }, color: NAVY, margin: 0, isTextBox: true });
  bullets(s, [
    [{ text: "Safety: ", bold: true }, "8 rules enforced by automated tests"], [{ text: "Correctness: ", bold: true }, "estimators tested against known truth"],
    [{ text: "Performance: ", bold: true }, "< 3 s per request"], [{ text: "Privacy: ", bold: true }, "patient details never leave the device; DPDP Act 2023"],
    [{ text: "Security: ", bold: true }, "HTTPS, authenticator app, admin approval"], [{ text: "Usability: ", bold: true }, "SUS ≥ 68; WCAG 2.1 AA"],
    [{ text: "Licences: ", bold: true }, "every source recorded with its licence"],
  ], { x: 5.4, y: 1.7, w: 4.2, h: 4.9, fontSize: 14 });
}

// ── 9. Gantt ─────────────────────────────────────────────────────────────
{
  const s = content("Timeline / Gantt Chart", "Advik", "Teal is done, amber is in progress, hatched is planned. The dashed line is today's presentation. October is RAG, evaluation, the clinician review and the paper; November is exams; December is final submission.");
  s.addImage({ path: M("gantt.png"), x: 0.35, y: 1.3, w: 9.3, h: 4.8 });
  s.addText("Early phases (July–August) are approximate. Buffer days: 2 Oct (Gandhi Jayanti), 20 Oct (Dussehra).", { x: 0.5, y: 6.3, w: 9.0, h: 0.4, fontFace: BODY, fontSize: 12, italic: true, color: MUTED, margin: 0, isTextBox: true });
}

// ── 10. Architecture ─────────────────────────────────────────────────────
{
  const s = content("System Design — Architecture", "Graceton", "The layers: the user interface on top, then accounts and the API, then safety rules, the causal engine and cost lookup, with the evidence search on the side and the audit log. The website runs the same model inside the phone, and a test proves it gives identical answers to Python.");
  s.addImage({ path: M("diagrams/block.png"), x: 0.5, y: 1.3, w: 9.0, h: 4.47 });
  card(s, 0.5, 5.95, 9.0, 0.8, "F5F7FB");
  s.addText([{ text: "Same answers everywhere: ", options: { bold: true, color: NAVY } }, { text: "the phone website runs the exported model; tests check it against Python on 155 patients and 40 questions." }],
    { x: 0.7, y: 5.95, w: 8.6, h: 0.8, fontFace: BODY, fontSize: 13, color: INK, valign: "middle", margin: 0, isTextBox: true });
}

// ── 11. Data flow ────────────────────────────────────────────────────────
{
  const s = content("System Design — Data Flow", "Graceton", "Level 0: the clinician gives patient details and gets options with ranges and reasons; guideline documents feed passages; every request is recorded. Level 1 breaks this into six processes with their data stores.");
  s.addText("DFD level 0", { x: 0.5, y: 1.2, w: 9, h: 0.35, fontFace: BODY, fontSize: 15, bold: true, underline: { style: "sng" }, color: NAVY, margin: 0, isTextBox: true });
  s.addImage({ path: M("diagrams/dfd0.png"), x: 1.0, y: 1.6, w: 8.0, h: 2.61 });
  s.addText("DFD level 1", { x: 0.5, y: 4.3, w: 9, h: 0.35, fontFace: BODY, fontSize: 15, bold: true, underline: { style: "sng" }, color: NAVY, margin: 0, isTextBox: true });
  s.addImage({ path: M("diagrams/dfd1.png"), x: 1.3, y: 4.7, w: 7.4, h: 2.52 * 0.93 });
}

// ── 12. Use case and sequence ────────────────────────────────────────────
{
  const s = content("System Design — Use Case & Sequence", "Graceton", "Three actors: clinician, evaluator and administrator. The sequence shows one consultation: the API checks the rules first, then asks the causal engine, then cites evidence, logs the request and returns the comparison.");
  s.addImage({ path: M("diagrams/usecase.png"), x: 0.4, y: 1.2, w: 3.6, h: 2.69 });
  s.addImage({ path: M("diagrams/sequence.png"), x: 0.9, y: 4.0, w: 8.2, h: 3.07 });
  bullets(s, [
    [{ text: "Clinician: ", bold: true }, "sign in, enter details, compare options, search evidence"],
    [{ text: "Evaluator: ", bold: true }, "benchmark results, evidence"],
    [{ text: "Administrator: ", bold: true }, "approves accounts; manages rules, prices and sources"],
    [{ text: "Order is fixed: ", bold: true }, "rules → estimate → evidence → log → clinician"],
  ], { x: 4.3, y: 1.35, w: 5.3, h: 2.5, fontSize: 14 });
}

// ── 13. Data and API ─────────────────────────────────────────────────────
{
  const s = content("System Design — Data & API", "Graceton", "Rules live in a table, each with a source and a status. Three cut-offs are team-set and flagged for the doctor. The API takes the patient details and returns each option's estimate with its range, or insufficient evidence, with the reasons and versions.");
  s.addText("rules.csv (10 rules; examples)", { x: 0.5, y: 1.2, w: 9, h: 0.35, fontFace: BODY, fontSize: 15, bold: true, underline: { style: "sng" }, color: NAVY, margin: 0, isTextBox: true });
  table(s, [["Rule", "Option", "Condition", "Action", "Source", "Status"],
    ["R01", "SGLT2i", "eGFR < 45", { text: "Exclude", options: { color: RED, bold: true } }, "FARXIGA label §1, 2.2; KDIGO 2022", "Verified"],
    ["R05", "DPP-4i", "past pancreatitis", { text: "Caution", options: { color: AMBER, bold: true } }, "JANUVIA label §1, 5.1", "Verified"],
    ["R08", "SU", "age ≥ 65", { text: "Caution", options: { color: AMBER, bold: true } }, "Glimepiride label §2.1, 8.5", "Team-set cut-off"]],
    { x: 0.5, y: 1.6, w: 9.0, colW: [0.6, 0.9, 1.5, 0.9, 3.4, 1.7], fontSize: 11.5 });
  s.addText("POST /api/v1/recommend", { x: 0.5, y: 3.1, w: 9, h: 0.35, fontFace: BODY, fontSize: 15, bold: true, underline: { style: "sng" }, color: NAVY, margin: 0, isTextBox: true });
  card(s, 0.5, 3.5, 9.0, 2.0, "F5F7FB");
  s.addText([
    { text: '{"age": 60, "sex": "female", "hba1c": 8.2, "egfr": 40, "bmi": 25.5, ...}', options: { breakLine: true } },
    { text: "→ applicable, options[3]: status (estimate | excluded | insufficient_evidence),", options: { breakLine: true } },
    { text: "  effect {value, ci_low, ci_high, level 0.95}, safety [rule_id, message, source],", options: { breakLine: true } },
    { text: "  confidence {propensity, overlap_threshold 0.05}, cost, comparisons,", options: { breakLine: true } },
    { text: "  assumptions, versions {engine, params_sha, rules_sha}, request_id, intended_use", options: {} },
  ], { x: 0.7, y: 3.55, w: 8.6, h: 1.9, fontFace: MONO, fontSize: 11.5, color: INK, valign: "middle", margin: 0, isTextBox: true });
  bullets(s, [
    [{ text: "Other endpoints: ", bold: true }, "GET /api/v1/rules, GET /health"],
    [{ text: "Every reply: ", bold: true }, "intended-use statement; refused if an estimate lacks an interval or contains dose-like text"],
  ], { x: 0.5, y: 5.75, w: 9.0, h: 1.1, fontSize: 14 });
}

// ── 14. Implementation status ────────────────────────────────────────────
{
  const s = content("Implementation — What's Built", "Rhian", "Much more than 25 percent is built and tested: the full causal engine with benchmark and refutation tests, a live phone website with approved accounts, and the first evidence search. 168 automated tests pass on Linux, Mac and Windows.");
  const pill = (t) => ({ text: t, options: { bold: true, color: t === "Done" ? "FFFFFF" : t === "Planned" ? GREY : "FFFFFF", fill: { color: t === "Done" ? TEAL : t === "Planned" ? GREYF : "C47A00" } } });
  table(s, [["Module", "Status", "Evidence"],
    ["Synthetic India-calibrated cohort", pill("Done"), "Every number sourced in params.yaml"],
    ["Safety rules (10, cited)", pill("Done"), "rules.csv; tests"],
    ["Propensity + overlap check", pill("Done"), "Overlap figure"],
    ["Naive, IPW, matching, AIPW", pill("Done"), "Results table, 95% CIs"],
    ["DR-learner (per patient)", pill("Done"), "Recovery + calibration figures"],
    ["Benchmark, refutation, E-values", pill("Done"), "20 × 5,000 patients; 9/9 checks pass"],
    ["Streamlit demo + FastAPI", pill("Done"), "/api/v1/recommend"],
    ["Phone website + accounts", pill("Done"), "diacausal.netlify.app; MFA; admin approval"],
    ["RAG retrieval with citations", pill("In progress"), "FDA source; Evidence tab"],
    ["Secondary outcomes, summary", pill("In progress"), "Target 9 Oct"],
    ["RAG explanations, clinician review", pill("Planned"), "1–23 Oct"]],
    { x: 0.5, y: 1.25, w: 9.0, colW: [3.4, 1.4, 4.2], fontSize: 12 });
  s.addText("168 automated tests pass (139 engine · 13 RAG · 16 website) on Linux, macOS and Windows", { x: 0.5, y: 6.45, w: 9.0, h: 0.4, fontFace: BODY, fontSize: 12, bold: true, color: NAVY, margin: 0, isTextBox: true });
}

// ── 15. Code ─────────────────────────────────────────────────────────────
{
  const s = content("Implementation — How the Code Works", "Rhian", "Two short pieces. AIPW: the outcome model makes a guess and the second term corrects it using patients who really got that drug, weighted by one over the propensity; if either model is right, the average is right. The DR-learner regresses those scores on patient details, and a robust standard error gives each patient's 95 percent interval.");
  s.addText("AIPW score (doubly robust)", { x: 0.5, y: 1.2, w: 9, h: 0.35, fontFace: BODY, fontSize: 15, bold: true, underline: { style: "sng" }, color: NAVY, margin: 0, isTextBox: true });
  card(s, 0.5, 1.6, 9.0, 1.45, "F5F7FB");
  s.addText([
    { text: "def aipw_scores(Y, T, e, mu):", options: { breakLine: true } },
    { text: "    # phi_a = mu_a(X) + 1{T=a} (Y - mu_a(X)) / e_a(X)", options: { breakLine: true, color: MUTED } },
    { text: "    got = (T[:, None] == np.arange(3)[None, :]).astype(float)", options: { breakLine: true } },
    { text: "    return mu + got * (Y[:, None] - mu) / e", options: {} },
  ], { x: 0.7, y: 1.65, w: 8.6, h: 1.35, fontFace: MONO, fontSize: 12.5, color: INK, valign: "middle", margin: 0, isTextBox: true });
  s.addText("DR-learner: this patient's estimate ± 95% interval", { x: 0.5, y: 3.25, w: 9, h: 0.35, fontFace: BODY, fontSize: 15, bold: true, underline: { style: "sng" }, color: NAVY, margin: 0, isTextBox: true });
  card(s, 0.5, 3.65, 9.0, 1.75, "F5F7FB");
  s.addText([
    { text: "beta = pinv(B.T @ B) @ B.T @ pseudo          # regress scores on details", options: { breakLine: true } },
    { text: "value = B @ beta                                # this patient's effect", options: { breakLine: true } },
    { text: "se = sqrt(x' V x)   # HC3 robust covariance V", options: { breakLine: true } },
    { text: "interval = value ± 1.96 * se", options: {} },
  ], { x: 0.7, y: 3.7, w: 8.6, h: 1.65, fontFace: MONO, fontSize: 12.5, color: INK, valign: "middle", margin: 0, isTextBox: true });
  bullets(s, [
    [{ text: "Safety rules are data, not code: ", bold: true }, "a test scans the code to prove no threshold is typed in."],
    [{ text: "Output check: ", bold: true }, "every reply is refused if it lacks an interval or contains dose-like text."],
  ], { x: 0.5, y: 5.6, w: 9.0, h: 1.3, fontSize: 14 });
}

// ── 16. Results: accuracy ────────────────────────────────────────────────
{
  const s = content("Initial Results — Accuracy", "Rhian", "Synthetic data, so we know the truth. The naive comparison overstates SGLT2 inhibitor versus DPP-4 inhibitor by about 75 percent; the corrected methods remove almost all the bias. AIPW's 95 percent intervals contain the truth 90 to 95 percent of the time, and the DR-learner's per-patient intervals about 93 to 95 percent.");
  s.addChart(pres.charts.BAR, [{ name: "Bias", labels: ["Naive", "IPW", "Matching", "AIPW"], values: [-0.159, 0.001, -0.002, 0.002] }], {
    x: 0.4, y: 1.25, w: 5.2, h: 3.9, barDir: "col", chartColors: ["1F4E9A"],
    showTitle: true, title: "Bias vs truth, SGLT2i minus DPP-4i (HbA1c points)", titleFontSize: 12, titleColor: INK, titleFontFace: BODY,
    showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 11, dataLabelColor: INK, dataLabelFormatCode: "0.000",
    catAxisLabelColor: MUTED, valAxisLabelColor: MUTED, valAxisLabelFontSize: 10, catAxisLabelFontSize: 11,
    valGridLine: { color: "E3E7EE", size: 0.5 }, catGridLine: { style: "none" }, showLegend: false, valAxisMinVal: -0.2, valAxisMaxVal: 0.05,
  });
  const stats = [["−0.159 → +0.002", "bias: naive → AIPW"], ["90–95%", "AIPW 95% CI coverage"], ["92.7–94.7%", "per-patient interval coverage"], ["0.011", "policy regret (naive 0.062)"]];
  stats.forEach(([big, lab], i) => {
    const y = 1.25 + i * 1.02;
    card(s, 5.85, y, 3.75, 0.9, "F5F7FB");
    s.addText([{ text: big, options: { bold: true, fontSize: 22, color: NAVY, breakLine: true } }, { text: lab, options: { fontSize: 12, color: MUTED } }],
      { x: 6.0, y, w: 3.5, h: 0.9, fontFace: BODY, valign: "middle", margin: 0, isTextBox: true });
  });
  s.addText("20 synthetic India-calibrated cohorts × 5,000 patients; true effect −0.211. Balance: largest SMD 0.70 → 0.08 after weighting. Refutation 9/9 passed.", { x: 0.5, y: 5.45, w: 9.0, h: 0.7, fontFace: BODY, fontSize: 13, color: INK, margin: 0, isTextBox: true });
  s.addText("Synthetic data: shows the methods recover a planted truth, not real-world drug effects.", { x: 0.5, y: 6.25, w: 9.0, h: 0.4, fontFace: BODY, fontSize: 12, italic: true, color: RED, margin: 0, isTextBox: true });
}

// ── 17. Results: plots ───────────────────────────────────────────────────
{
  const s = content("Initial Results — Plots", "Pratham", "Left: overlap — the dashed line at 0.05 is where we refuse to estimate. Middle: balance — after weighting every patient detail is below the 0.1 line. Right: each dot is a test patient; estimates lie close to the diagonal, meaning the per-patient effects are recovered.");
  const figs = [["overlap.png", "Overlap (0.05 = abstain)"], ["love_plot.png", "Balance before/after weighting"], ["cate_recovery.png", "Per-patient effects vs truth"]];
  figs.forEach(([f, cap], i) => {
    const x = 0.35 + i * 3.12;
    card(s, x, 1.3, 3.0, 4.6, "FFFFFF");
    s.addImage({ path: R(`results/figures/${f}`), x: x + 0.08, y: 1.45, w: 2.84, h: 3.6, sizing: { type: "contain", w: 2.84, h: 3.6 } });
    s.addText(cap, { x: x + 0.1, y: 5.15, w: 2.8, h: 0.6, fontFace: BODY, fontSize: 12, bold: true, color: NAVY, align: "center", valign: "middle", margin: 0, isTextBox: true });
  });
  s.addText("Full-size figures and the calibration plot: report Chapter 5 and the website's Results tab.", { x: 0.5, y: 6.2, w: 9.0, h: 0.4, fontFace: BODY, fontSize: 12, italic: true, color: MUTED, margin: 0, isTextBox: true });
}

// ── 18. Demo ─────────────────────────────────────────────────────────────
{
  const s = content("Demo — Live on Any Phone", "Graceton", "Three preset patients. One: a typical patient, three estimates with ranges. Two: eGFR 40 and past pancreatitis: SGLT2 inhibitor excluded in red with its source, DPP-4 inhibitor caution in amber. Three: an older patient with past hypoglycaemia: sulfonylurea shows insufficient evidence in grey. Then open the live website.");
  const shots = [["demo1_cards.png", "1 · Typical patient"], ["demo2_cards.png", "2 · eGFR 40, pancreatitis"], ["demo3_cards.png", "3 · Older, past hypoglycaemia"]];
  shots.forEach(([f, cap], i) => {
    const x = 0.35 + i * 3.12;
    s.addImage({ path: M(`screens/${f}`), x, y: 1.3, w: 3.0, h: 1.99, sizing: { type: "contain", w: 3.0, h: 1.99 } });
    s.addText(cap, { x, y: 3.35, w: 3.0, h: 0.4, fontFace: BODY, fontSize: 12, bold: true, color: NAVY, align: "center", margin: 0, isTextBox: true });
  });
  const legend = [[REDF, RED, "Red = excluded by a cited rule"], [AMBERF, AMBER, "Amber = caution"], [GREYF, GREY, "Grey = insufficient evidence"], ["E4EEEB", "0E5049", "Pine = estimate ± 95% range"]];
  legend.forEach(([f, c, t], i) => {
    const y = 4.0 + i * 0.5;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.5, y, w: 0.4, h: 0.34, rectRadius: 0.05, fill: { color: f }, line: { color: c, width: 1.5 } });
    s.addText(t, { x: 1.05, y: y - 0.03, w: 4.2, h: 0.4, fontFace: BODY, fontSize: 13, color: INK, margin: 0, valign: "middle", isTextBox: true });
  });
  s.addImage({ path: R("web/icons/qr.png"), x: 7.55, y: 3.95, w: 1.95, h: 1.95 });
  s.addText([{ text: "diacausal.netlify.app", options: { bold: true, color: NAVY, breakLine: true } }, { text: "Add to Home Screen · works offline · never green for “recommended”", options: { fontSize: 11, color: MUTED } }],
    { x: 5.1, y: 4.1, w: 2.35, h: 1.8, fontFace: BODY, fontSize: 14, valign: "middle", margin: 0, isTextBox: true });
  s.addText("Backup: 98-second recorded demo (DiaCausal_demo.mp4)", { x: 0.5, y: 6.25, w: 9.0, h: 0.4, fontFace: BODY, fontSize: 12, italic: true, color: MUTED, margin: 0, isTextBox: true });
}

// ── 19. Completed vs planned ─────────────────────────────────────────────
{
  const s = content("Completed vs Planned", "Advik", "Completed: the whole causal engine, results, demo, API, the phone website with accounts, and the first cited evidence search. Planned for October: secondary outcomes, the RAG explanations and evaluation, integration with the chat app, the clinician review and the research paper.");
  card(s, 0.5, 1.3, 4.35, 5.3, "E6F3F1");
  s.addText("Completed (by 30 Sept)", { x: 0.7, y: 1.4, w: 4.0, h: 0.45, fontFace: BODY, fontSize: 17, bold: true, color: TEAL, margin: 0, isTextBox: true });
  bullets(s, ["Scope, data strategy, requirements, design", "Synthetic India-calibrated cohort", "Cited safety rules (10)", "Propensity, overlap, IPW, AIPW, DR-learner",
    "Benchmark, refutation, E-values", "Streamlit demo, FastAPI, 168 tests", "Phone website: accounts, MFA, admin approval", "Evidence search with citations (1st source)"],
    { x: 0.7, y: 1.9, w: 4.0, h: 4.6, fontSize: 14 });
  card(s, 5.15, 1.3, 4.35, 5.3, "F5F7FB");
  s.addText("Planned (October)", { x: 5.35, y: 1.4, w: 4.0, h: 0.45, fontFace: BODY, fontSize: 17, bold: true, color: NAVY, margin: 0, isTextBox: true });
  bullets(s, ["Hypoglycaemia + weight outcomes; printable summary (by 9 Oct)", "More licence-cleared sources; explanation writer (template / free online / offline)",
    "Gold questions; RAG evaluation (recall, citation precision)", "Engine inside the chat app", "Clinician review of 60 cases; usability (SUS)", "Results frozen 16 Oct; IEEE paper; final report"],
    { x: 5.35, y: 1.9, w: 4.0, h: 4.6, fontSize: 14 });
}

// ── 20. Conclusion ───────────────────────────────────────────────────────
{
  const s = content("Conclusion", "Pratham", "Four points to remember: we answer a causal what-if question; safety comes first; we are honest about uncertainty and refuse to guess; and it already runs on any phone, with the clinician always deciding.");
  const pts = [["A causal question, answered causally", "per-patient 6-month HbA1c change for three add-on drugs"], ["Safety before prediction", "cited rules run first; no doses; excluded options never estimated"],
    ["Honest uncertainty", "95% intervals; “insufficient evidence” instead of a guess"], ["Working today", "tested engine, live phone website, first cited evidence; the clinician decides"]];
  pts.forEach(([t, sub], i) => {
    const y = 1.35 + i * 1.3;
    card(s, 0.6, y, 8.8, 1.1);
    s.addShape(pres.shapes.OVAL, { x: 0.8, y: y + 0.24, w: 0.62, h: 0.62, fill: { color: NAVY }, line: { color: NAVY } });
    s.addText(String(i + 1), { x: 0.8, y: y + 0.24, w: 0.62, h: 0.62, fontFace: BODY, fontSize: 18, bold: true, color: "FFFFFF", align: "center", valign: "middle", margin: 0, isTextBox: true });
    s.addText([{ text: t, options: { bold: true, fontSize: 17, breakLine: true } }, { text: sub, options: { fontSize: 13, color: MUTED } }],
      { x: 1.6, y, w: 7.6, h: 1.1, fontFace: BODY, color: INK, valign: "middle", margin: 0, isTextBox: true });
  });
  s.addText(INTENDED, { x: 0.6, y: 6.55, w: 8.8, h: 0.4, fontFace: BODY, fontSize: 11, italic: true, color: MUTED, align: "center", margin: 0, isTextBox: true });
}

// ── 21. References ───────────────────────────────────────────────────────
{
  const s = content("References", "Advik", "Our key references, in IEEE style; the full list of 35 is in the report.");
  const refs = [
    "R. M. Anjana et al., “Metabolic non-communicable disease health report of India: ICMR-INDIAB-17,” Lancet Diabetes Endocrinol., vol. 11, no. 7, pp. 474–489, 2023.",
    "B. M. Shields et al., “Patient stratification for determining optimal second-line and third-line therapy for type 2 diabetes: the TriMaster study,” Nature Medicine, vol. 29, pp. 376–383, 2023.",
    "J. M. Dennis et al., “Development of a treatment selection algorithm for SGLT2 and DPP-4 inhibitor therapies,” Lancet Digit. Health, vol. 4, no. 12, pp. e873–e883, 2022.",
    "A. Tsapas et al., “Comparative effectiveness of glucose-lowering drugs for type 2 diabetes,” Ann. Intern. Med., vol. 173, no. 4, pp. 278–286, 2020.",
    "E. H. Kennedy, “Towards optimal doubly robust estimation of heterogeneous causal effects,” Electron. J. Stat., vol. 17, no. 2, pp. 3008–3049, 2023.",
    "M. A. Hernán and J. M. Robins, Causal Inference: What If. Chapman & Hall/CRC, 2020.",
    "P. C. Austin, “Balance diagnostics for comparing the distribution of baseline covariates…,” Stat. Med., vol. 28, no. 25, pp. 3083–3107, 2009.",
    "P. Lewis et al., “Retrieval-augmented generation for knowledge-intensive NLP tasks,” in Proc. NeurIPS 33, pp. 9459–9474, 2020.",
    "A. Misra et al., “Consensus statement for diagnosis of obesity… for Asian Indians,” J. Assoc. Physicians India, vol. 57, pp. 163–170, 2009.",
  ];
  s.addText(refs.map((r, i) => ({ text: `[${i + 1}] ${r}`, options: { breakLine: i < refs.length - 1, paraSpaceAfter: 6 } })),
    { x: 0.5, y: 1.25, w: 9.0, h: 5.7, fontFace: BODY, fontSize: 12, color: INK, valign: "top", margin: 0, isTextBox: true });
}

// ── 22. Thank you ────────────────────────────────────────────────────────
{
  const s = pres.addSlide(); slideNo += 1;
  s.background = { color: "FFFFFF" };
  const L = { color: NAVY, width: 2.5 };
  s.addShape(pres.shapes.LINE, { x: 0.8, y: 2.3, w: 8.4, h: 0, line: { ...L } });
  s.addShape(pres.shapes.LINE, { x: 0.8, y: 5.2, w: 8.4, h: 0, line: { ...L } });
  s.addShape(pres.shapes.LINE, { x: 2.2, y: 1.2, w: 0, h: 5.1, line: { ...L } });
  s.addShape(pres.shapes.LINE, { x: 7.8, y: 1.2, w: 0, h: 5.1, line: { ...L } });
  s.addText("Thank You!", { x: 2.2, y: 2.3, w: 5.6, h: 2.9, fontFace: TITLE_FONT, fontSize: 54, bold: true, color: "000000", align: "center", valign: "middle", margin: 0, isTextBox: true });
  s.addText("Questions? · diacausal.netlify.app", { x: 0.8, y: 6.4, w: 8.4, h: 0.5, fontFace: BODY, fontSize: 16, color: NAVY, align: "center", margin: 0, isTextBox: true });
  s.addNotes("Everyone. Thank you. We are happy to take questions, and we can show the live website on a phone.");
}

pres.writeFile({ fileName: OUT }).then((f) => console.log("wrote", f));
