/*
 * DiaCausal engine, in the browser — a line-by-line mirror of diacausal_engine/recommend.py.
 *
 * Research prototype for clinician evaluation; not a marketed medical device;
 * not for unsupervised clinical use. SYNTHETIC DATA ONLY. The clinician decides.
 *
 * Every number (coefficients, thresholds, rules) comes from model.json, which Python writes
 * (python -m diacausal_engine.export_web). Nothing clinical is typed here. The patient's
 * details never leave the device. tests/web/test_web.py checks this file gives exactly the
 * same answers as the Python engine.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.DiaCausal = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const OPS = {
    lt: (a, b) => a < b, le: (a, b) => a <= b, gt: (a, b) => a > b, ge: (a, b) => a >= b, eq: (a, b) => a === b,
  };
  const FIELDS = ["age", "sex", "duration_years", "hba1c", "egfr", "bmi"];
  const FLAGS = ["ascvd", "hf", "hypo_history", "t1d", "dka_history", "pancreatitis_history", "low_income"];

  // Python's f"{x:g}" for the values we print (6 significant digits, no trailing zeros).
  function g(x) {
    const s = Number(x).toPrecision(6);
    return String(Number(s));
  }

  // Python round(x, n): round half to even on the exact binary value.
  function roundN(x, n) {
    const f = 10 ** n;
    const scaled = x * f;
    const r = Math.round(scaled);
    const tie = Math.abs(scaled - Math.trunc(scaled)) === 0.5;
    const v = tie && r % 2 !== 0 ? r - 1 : r;
    return v / f === 0 ? 0 : v / f;
  }
  function round3(x) { return roundN(x, 3); }

  function dot(a, b) { let s = 0; for (let i = 0; i < a.length; i++) s += a[i] * b[i]; return s; }

  function validate(model, p) {
    const problems = [];
    const ranges = model.thresholds.input_ranges;
    for (const f of FIELDS) {
      if (p[f] === undefined || p[f] === null || p[f] === "") problems.push(`${f}: this field is required`);
    }
    if (p.sex !== undefined && p.sex !== "female" && p.sex !== "male") problems.push("sex: must be female or male");
    for (const [f, [lo, hi]] of Object.entries(ranges)) {
      const v = Number(p[f]);
      if (p[f] !== undefined && p[f] !== "" && (!Number.isFinite(v) || v < lo || v > hi)) {
        problems.push(`${f}: out of the plausible range (${g(lo)} to ${g(hi)})`);
      }
    }
    if (p.age !== undefined && !Number.isInteger(Number(p.age))) problems.push("age: must be a whole number of years");
    return problems;
  }

  function row(p) {
    const r = { female: p.sex === "female" ? 1 : 0 };
    for (const f of FIELDS) if (f !== "sex") r[f] = Number(p[f]);
    for (const f of FLAGS) r[f] = p[f] ? 1 : 0;
    return r;
  }

  function applyRules(model, r) {
    const verdicts = {};
    for (const a of model.arms) verdicts[a.arm] = { excluded: false, fired: [] };
    for (const rule of model.rules) {
      if (!(rule.field in r)) throw new Error(`${rule.rule_id} needs '${rule.field}', which was not given`);
      if (OPS[rule.op](Number(r[rule.field]), rule.value)) {
        verdicts[rule.arm].fired.push(rule);
        if (rule.action === "EXCLUDE") verdicts[rule.arm].excluded = true;
      }
    }
    return verdicts;
  }

  function supportCheck(model, r) {
    const reasons = [];
    if (r.t1d && !model.t1d_in_cohort) reasons.push("type 1 diabetes: the cohort contains only type 2 diabetes");
    for (const col of model.features) {
      if (!(col in r)) continue;
      const v = Number(r[col]);
      const s = model.support[col];
      if (s.kind === "values") {
        if (!s.values.includes(v)) reasons.push(`${col} = ${g(v)}: no patient in the cohort has this value`);
      } else if (v < s.min || v > s.max) {
        reasons.push(`${col} = ${g(v)} is outside the cohort's range (${g(s.min)} to ${g(s.max)})`);
      }
    }
    return reasons;
  }

  function propensity(model, x) {
    const m = model.propensity;
    const z = x.map((v, i) => (v - m.mean[i]) / m.scale[i]);
    const logits = m.coef.map((c, k) => dot(c, z) + m.intercept[k]);
    const top = Math.max(...logits);
    const e = logits.map((l) => Math.exp(l - top));
    const s = e.reduce((a, b) => a + b, 0);
    return e.map((v) => v / s);
  }

  function drPredict(model, x, d = model.dr) {
    const b = [1, ...x.map((v, i) => (v - d.mean[i]) / d.scale[i])];
    const out = {};
    model.targets.forEach((t, k) => {
      const beta = d.beta.map((rowB) => rowB[k]);
      const value = dot(b, beta);
      const cov = d.cov[k];
      let q = 0;
      for (let i = 0; i < b.length; i++) q += b[i] * dot(cov[i], b);
      const se = Math.sqrt(q);
      const z = model.thresholds.ci_z;
      out[t] = [value, value - z * se, value + z * se];
    });
    return out;
  }


  /** Weight change (kg, 2 dp) and hypoglycaemia risk (% clipped to 0-100, 1 dp), each with a 95% interval. */
  function secondaryPredict(model, x) {
    if (!model.secondary || !model.secondary.weight || !model.secondary.hypo) return {};
    const w = drPredict(model, x, model.secondary.weight), h = drPredict(model, x, model.secondary.hypo);
    const out = {};
    const pct = (v) => roundN(Math.min(100, Math.max(0, 100 * v)), 1);
    for (const a of model.arms.map((m) => m.arm)) {
      out[a] = {
        weight_change_kg: { value: roundN(w[a][0], 2), ci_low: roundN(w[a][1], 2), ci_high: roundN(w[a][2], 2), level: 0.95 },
        hypo_risk_pct: { value: pct(h[a][0]), ci_low: pct(h[a][1]), ci_high: pct(h[a][2]), level: 0.95 },
        note: model.secondary_note,
      };
    }
    return out;
  }

  function bmiCategory(model, bmi) {
    const t = model.thresholds;
    const u = g(t.bmi_underweight_below), o = g(t.bmi_overweight_from), b = g(t.bmi_obese_from);
    if (bmi < t.bmi_underweight_below) return `Underweight (below ${u})`;
    if (bmi < t.bmi_overweight_from) return `Normal (${u} to below ${o})`;
    if (bmi < t.bmi_obese_from) return `Overweight (${o} to below ${b}, Asian-Indian cut-off)`;
    return `Obese (${b} or above, Asian-Indian cut-off)`;
  }

  function checkOutput(model, result) {
    const dose = new RegExp(model.dose_pattern, "i");
    if (dose.test(JSON.stringify(result))) throw new Error("dose-like text found in the reply");
    if (result.intended_use !== model.intended_use) throw new Error("intended-use statement missing");
    for (const o of result.options) {
      if (o.status === "estimate") {
        const e = o.effect;
        if (!e || !(e.ci_low <= e.value && e.value <= e.ci_high) || !o.confidence) throw new Error(`${o.arm}: estimate without interval`);
        if (o.secondary) {
          for (const iv of [o.secondary.weight_change_kg, o.secondary.hypo_risk_pct]) {
            if (!(iv.ci_low <= iv.value && iv.value <= iv.ci_high)) throw new Error(`${o.arm}: secondary outcome without interval`);
          }
        }
      } else if (o.effect || o.secondary) throw new Error(`${o.arm}: ${o.status} options must not carry a number`);
      if (o.status === "excluded" && !o.safety.some((s) => s.action === "EXCLUDE")) throw new Error(`${o.arm}: excluded without rule`);
    }
    if (result.applicable === "NOT_APPLICABLE" && result.options.some((o) => o.status === "estimate")) {
      throw new Error("NOT_APPLICABLE reply carries estimates");
    }
  }

  function requestId() {
    const bytes = new Uint8Array(6);
    (typeof crypto !== "undefined" && crypto.getRandomValues ? crypto : { getRandomValues: (a) => a.map(() => Math.floor(Math.random() * 256)) }).getRandomValues(bytes);
    return Array.from(bytes, (x) => x.toString(16).padStart(2, "0")).join("");
  }

  /** One patient -> Causal Output (same shape as diacausal_engine.schemas.CausalOutput). */
  function recommend(model, patient, opts = {}) {
    const problems = validate(model, patient);
    if (problems.length) return { error: "invalid_request", problems, intended_use: model.intended_use };
    const r = row(patient);
    const verdicts = applyRules(model, r); // 2. safety rules first
    const outside = supportCheck(model, r); // 3.
    const x = model.features.map((c) => r[c]);
    const p = propensity(model, x); // 4.
    const threshold = model.thresholds.overlap_min_propensity;
    const ok = p.map((v) => v >= threshold);
    let estimable = model.arms.map((a) => a.arm).filter((a, j) => !verdicts[a].excluded && !outside.length && ok[j]);
    const pred = estimable.length ? drPredict(model, x) : {}; // 5. only surviving options
    const width = {};
    for (const a of estimable) width[a] = pred[a][2] - pred[a][1];
    const maxWidth = model.thresholds.max_interval_width;
    estimable = estimable.filter((a) => width[a] <= maxWidth); // too uncertain -> abstain
    const secondary = estimable.length ? secondaryPredict(model, x) : {};

    const options = model.arms.map((a, j) => {
      const v = verdicts[a.arm];
      const base = {
        arm: a.arm, name: a.name, example_molecule: a.example,
        safety: v.fired.map((rule) => ({
          rule_id: rule.rule_id, action: rule.action, condition: rule.condition, message: rule.message,
          source: rule.source, section: rule.section, rule_status: rule.status,
        })),
        effect: null, confidence: null, insufficient_reason: null, cost: model.prices[a.arm], secondary: null,
      };
      if (v.excluded) return { ...base, status: "excluded" };
      if (outside.length) return { ...base, status: "insufficient_evidence", insufficient_reason: "Outside the cohort: " + outside.join("; ") };
      if (!ok[j]) {
        return {
          ...base, status: "insufficient_evidence",
          insufficient_reason: `Too few similar patients received this option (propensity ${p[j].toFixed(3)}, below ${g(threshold)}). A fair comparison is not possible.`,
        };
      }
      if (!estimable.includes(a.arm)) {
        return {
          ...base, status: "insufficient_evidence",
          insufficient_reason: `Too uncertain: this patient's 95% range is ${width[a.arm].toFixed(2)} points wide (limit ${g(maxWidth)}). A useful estimate is not possible.`,
        };
      }
      const [est, lo, hi] = pred[a.arm];
      return {
        ...base, status: "estimate",
        effect: { value: round3(est), ci_low: round3(lo), ci_high: round3(hi), level: 0.95 },
        secondary: secondary[a.arm] || null,
        confidence: { propensity: round3(p[j]), overlap_threshold: threshold, interval_level: 0.95, method: model.method },
        _raw: opts.raw ? { value: est, ci_low: lo, ci_high: hi, propensity: p[j] } : undefined,
      };
    });

    const comparisons = [];
    for (const [a, b] of model.contrasts) {
      if (estimable.includes(a) && estimable.includes(b)) {
        const [d, lo, hi] = pred[`${a}-${b}`];
        comparisons.push({ first: a, second: b, difference: { value: round3(d), ci_low: round3(lo), ci_high: round3(hi), level: 0.95 } });
      }
    }
    const reasons = [...outside];
    if (model.arms.every((a) => verdicts[a.arm].excluded)) reasons.push("every option is excluded by a safety rule");
    else if (!estimable.length && !outside.length) reasons.push("no option has enough similar patients (or a narrow enough 95% range) for a useful estimate");

    const result = {
      schema_version: "1.0",
      request_id: requestId(),
      applicable: estimable.length ? "APPLICABLE" : "NOT_APPLICABLE",
      not_applicable_reasons: estimable.length ? [] : reasons,
      intervention: "Add one of three options to metformin: SGLT2 inhibitor, DPP-4 inhibitor or sulfonylurea",
      outcome: { name: "Change in HbA1c at 6 months", unit: "percentage points of HbA1c (%)", direction: "negative = HbA1c falls (better glucose control)" },
      options, comparisons,
      assumptions: model.assumptions,
      bmi_category: bmiCategory(model, Number(patient.bmi)),
      versions: model.versions,
      decision: "Decision support only. The clinician decides.",
      intended_use: model.intended_use,
      computed_on: "this device (nothing was sent anywhere)",
    };
    const clean = JSON.parse(JSON.stringify(result));
    checkOutput(model, clean);
    return opts.raw ? result : clean;
  }

  return { recommend, validate, bmiCategory, FIELDS, FLAGS, _internals: { g, round3, roundN, propensity, drPredict, secondaryPredict, supportCheck, applyRules } };
});
