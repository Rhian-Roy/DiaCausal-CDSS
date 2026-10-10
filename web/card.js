/*
 * DiaCausal answer card, in the browser: builds the same AnswerCardV1 the API returns (diacausal/output/formatter.py,
 * docs/ANSWER_FORMAT.md) from the engine's output (engine.js), the cited passages (evidence.js) and the quoted
 * sentences (explain.js). No DOM here: app.js draws the card (screens 17, 19, 21). tests/web checks every card built
 * here is a valid AnswerCardV1 and that its evidence levels are Python's.
 *
 * Research prototype for clinician evaluation; not a marketed medical device;
 * not for unsupervised clinical use. Every number comes from the engine. The clinician decides.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory(require("./engine.js"));
  else root.DiaCausalCard = factory(root.DiaCausal);
})(typeof self !== "undefined" ? self : this, function (Engine) {
  "use strict";

  const COMPARATOR = "DPP4i";
  const STATUS = { estimate: "ESTIMATED", insufficient_evidence: "INSUFFICIENT_EVIDENCE", excluded: "EXCLUDED" };
  const g = (x) => Engine._internals.g(x);

  /** "52 y, M, HbA1c 8.4%, eGFR 88, BMI 27 (Overweight ...)": the same words as patient_summary() in Python. */
  function patientSummary(p, bmiCategory) {
    const sex = p.sex === "female" ? "F" : "M";
    return `${g(p.age)} y, ${sex}, HbA1c ${g(p.hba1c)}%, eGFR ${g(p.egfr)}, BMI ${g(p.bmi)} (${bmiCategory})`;
  }

  /** "WHO 2018, p.12"-style label of a passage (source ID, short title, version, page). */
  function label(c) {
    const year = String(c.version || "").match(/\d{4}/);
    const page = c.page && c.page !== "?" ? `, p.${c.page}` : "";
    return `${c.source_id} · ${c.title}${year ? ` (${year[0]})` : ""}${page}`;
  }

  const ruleHits = (o, action) => o.safety.filter((s) => s.action === action)
    .map((s) => ({ schema_version: "1.0", option: o.arm, rule_id: s.rule_id, source: `${s.source}, ${s.section}` }));

  /**
   * One AnswerCardV1.
   *   result      engine.recommend(model, patient)
   *   opts.question            the question (compare without one: "Compare the three options for this patient.")
   *   opts.passages            the passages cited on the card, each { chunk_id, text, citation } (numbered from 1)
   *   opts.sentences           quoted sentences { text, cites: [passage numbers] } (explain.js), at most 4 are kept
   *   opts.textsByOption       { arm: [texts] } the passages that count as citations for each option (default: all passages)
   *   opts.retrievalAbstained  the search for the question found nothing (every level becomes Insufficient)
   */
  function build(model, result, patient, opts = {}) {
    const passages = opts.passages || [];
    const allTexts = passages.map((p) => p.text).filter((t) => t !== opts.withheldText);
    const levels = [];
    for (const o of result.options) {
      if (o.status === "excluded") continue;
      const texts = opts.textsByOption ? opts.textsByOption[o.arm] || [] : allTexts;
      const a = Engine.evidenceLevel(model, o, Engine.countCitations(texts, o), Boolean(opts.retrievalAbstained));
      levels.push({ schema_version: "1.0", option: o.arm, level: a.level, reason: a.reason });
    }
    const insufficient = new Set(levels.filter((l) => l.level === "Insufficient").map((l) => l.option));
    const versus = {};
    for (const c of result.comparisons) if (c.second === COMPARATOR) versus[c.first] = c.difference;
    const interval = (x) => (x ? { value: x.value, ci_low: x.ci_low, ci_high: x.ci_high, level: 0.95 } : null);
    const effects = result.options.map((o) => {
      const shown = o.status === "estimate" && !insufficient.has(o.arm);
      return {
        schema_version: "1.0", option: o.arm,
        status: o.status === "estimate" && !shown ? "INSUFFICIENT_EVIDENCE" : STATUS[o.status],
        caution: o.safety.some((s) => s.action === "CAUTION"),
        hba1c_change: shown ? interval(o.effect) : null,
        vs_comparator: shown && o.arm !== COMPARATOR ? interval(versus[o.arm]) : null,
        weight_change_kg: shown && o.secondary ? interval(o.secondary.weight_change_kg) : null,
        hypo_risk_pct: shown && o.secondary ? interval(o.secondary.hypo_risk_pct) : null,
        cost_label: o.cost.label,
      };
    });
    const abstain = result.options.filter((o) => insufficient.has(o.arm)).map((o) => {
      const byOverlap = o.status !== "estimate" && Boolean(o.confidence);
      return { schema_version: "1.0", option: o.arm,
        why: Engine.abstainWhy(model, o, Boolean(opts.retrievalAbstained) && o.status === "estimate"),
        propensity: byOverlap ? o.confidence.propensity : null,
        threshold: byOverlap ? model.evidence_level.insufficient_propensity_below : null };
    });
    const claims = (opts.sentences || []).slice(0, 4).map((s) => ({
      schema_version: "1.0", text: s.text,
      citations: s.cites.map((n) => ({ schema_version: "1.0", chunk_id: passages[n - 1].chunk_id, label: label(passages[n - 1].citation) })),
    }));
    return {
      schema_version: "1.0", request_id: result.request_id, mode: "template",
      question: opts.question || "Compare the three options for this patient.",
      patient_summary: patientSummary(patient, result.bmi_category), comparator: COMPARATOR,
      claims, question_context: null, limitations: null, effects, drivers: {}, evidence_levels: levels,
      excluded: result.options.flatMap((o) => ruleHits(o, "EXCLUDE")),
      cautions: result.options.filter((o) => o.status !== "excluded").flatMap((o) => ruleHits(o, "CAUTION")),
      abstain, fallback_used: false, failed_checks: [], fallback_reason: null, dropped_claims: 0,
      versions: result.versions, decision: result.decision, intended_use: result.intended_use,
    };
  }

  /** Leader logic (HANDOFF.md section 4): only an option whose interval vs DPP-4i excludes 0, and only on HbA1c. */
  function leaders(card) {
    return card.effects.filter((e) => e.vs_comparator && (e.vs_comparator.ci_high < 0 || e.vs_comparator.ci_low > 0));
  }

  return { build, leaders, label, patientSummary, COMPARATOR };
});
