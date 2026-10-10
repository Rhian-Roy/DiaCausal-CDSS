/*
 * DiaCausal input guards, in the browser: a line-by-line mirror of diacausal/guards/input_guards.py (P27).
 *
 * Research prototype for clinician evaluation; not a marketed medical device;
 * not for unsupervised clinical use.
 *
 * Seven checks, in the order of plan 8.6: scope, identifier, red flag, injection, range and unit, length and language, dose request.
 * All seven always run. Every word list, number, pattern and message comes from guards.json (python -m diacausal.guards.export_web);
 * nothing is typed here. A blocked question is never sent anywhere or kept, and a message never repeats what matched.
 * tests/web/test_web.py runs this file and the Python guards on the same questions and fails if any result differs.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.DiaCausalGuards = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const D = [[0,1,2,3,4,5,6,7,8,9],[1,2,3,4,0,6,7,8,9,5],[2,3,4,0,1,7,8,9,5,6],[3,4,0,1,2,8,9,5,6,7],[4,0,1,2,3,9,5,6,7,8],
    [5,9,8,7,6,0,4,3,2,1],[6,5,9,8,7,1,0,4,3,2],[7,6,5,9,8,2,1,0,4,3],[8,7,6,5,9,3,2,1,0,4],[9,8,7,6,5,4,3,2,1,0]];
  const P = [[0,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4],[5,8,0,3,7,9,6,1,4,2],[8,9,1,6,0,4,3,5,2,7],[9,4,5,3,1,2,6,8,7,0],
    [4,2,8,6,5,7,3,9,0,1],[2,7,9,3,8,0,6,4,1,5],[7,0,4,6,9,1,3,2,5,8]];

  // The Verhoeff check digit (an Aadhaar number's last digit): a published algorithm, not a clinical number.
  function verhoeffOk(num) {
    let c = 0;
    [...num].reverse().forEach((ch, i) => { c = D[c][P[i % 8][Number(ch)]]; });
    return c === 0;
  }

  const rx = (spec, extra = "") => new RegExp(spec.source, [...new Set((spec.flags + extra).split(""))].join(""));
  const norm = (text) => text.normalize("NFKC").toLowerCase();

  function make(G) {
    const R = G.regex;
    const word = rx(R.word);
    const words = (text) => norm(text).match(word) || [];
    const p = G.params;

    function phraseHits(phrases, text) {
      const joined = " " + words(text).join(" ") + " ";
      const hits = [];
      for (const phrase of phrases) {
        const key = " " + words(phrase).join(" ") + " ";
        let start = joined.indexOf(key);
        while (start !== -1) {
          hits.push(joined.slice(0, start).split(/\s+/).filter(Boolean).length);
          start = joined.indexOf(key, start + 1);
        }
      }
      return hits;
    }

    function cued(text, index) {
      const toks = words(text);
      const cues = G.rules.context_cues;
      const before = toks.slice(Math.max(0, index - cues.window_words), index).join(" ");
      return [...cues.negation, ...cues.history].some((c) => ` ${before} `.includes(` ${c} `));
    }

    const uncuedHit = (phrases, text) => phraseHits(phrases, text).some((i) => !cued(text, i));
    const presentState = (text) => phraseHits(p.present_state_words, text).length > 0;
    const aboutDrugsInGeneral = (text) => phraseHits(p.knowledge_question_words, text).length > 0 && !presentState(text);
    const wordsBefore = (text, at) => words(text.slice(0, at)).length;
    const result = (id, blocked) => ({ id, status: blocked ? "BLOCK" : "PASS", blocked_reason: blocked || null });
    const fmt = (template, values) => template.replace(/\{(\w+)\}/g, (m, k) => (k in values ? String(values[k]) : m));
    const scopeMessage = (topic) => fmt(G.messages.scope, { about: G.topic_names[topic] });

    // 1. scope
    function scope(q, patient) {
      if (patient) {
        if (patient.type1) return result("scope", scopeMessage("type_1"));
        if (!patient.on_metformin) return result("scope", scopeMessage("not_on_metformin"));
        if (patient.age < G.ranges.age[0]) return result("scope", scopeMessage("under_18"));
      }
      const labelQuestion = phraseHits(p.label_question_words, q).length > 0 && !presentState(q);
      for (const topic of G.scope_topics) {
        if (topic === "type_1" && labelQuestion) continue;
        if (uncuedHit(G.rules.out_of_scope[topic], q)) return result("scope", scopeMessage(topic));
      }
      for (const m of q.matchAll(rx(R.age_text))) {
        const value = parseInt(m[1] || m[2], 10);
        if (value < G.ranges.age[0] && !cued(q, wordsBefore(q, m.index))) return result("scope", scopeMessage("under_18"));
      }
      return result("scope", null);
    }

    // 2. identifier
    function hasIdentifier(text) {
      for (const spec of R.identifiers) {
        for (const m of text.matchAll(rx(spec))) {
          if (spec.verhoeff && p.aadhaar_checksum_required && !verhoeffOk(m[0].replace(/\D/g, ""))) continue;
          return true;
        }
      }
      return rx(R.honorific_name).test(text);
    }
    const identifier = (q) => result("identifier", hasIdentifier(q) ? G.messages.identifier : null);

    // 3. red flag
    const toMgDl = (value, unit) => ((unit || "mg/dl").toLowerCase().startsWith("mmol") ? value * p.mmol_to_mg_dl : value);
    const glucoseIsEmergency = (mgDl) => mgDl < p.glucose_low_below_mg_dl || mgDl > p.glucose_high_above_mg_dl;
    function redFlag(q, patient) {
      const wordsAlone = uncuedHit(G.rules.emergency_phrases, q) || uncuedHit(G.rules.out_of_scope.dka_hhs, q);
      if (wordsAlone && !aboutDrugsInGeneral(q)) return result("red_flag", G.messages.red_flag);
      for (const m of q.matchAll(rx(R.glucose))) {
        if (glucoseIsEmergency(toMgDl(parseFloat(m[1]), m[2])) && !cued(q, wordsBefore(q, m.index))) return result("red_flag", G.messages.red_flag);
      }
      if (patient && patient.glucose_mg_dl !== null && patient.glucose_mg_dl !== undefined && glucoseIsEmergency(patient.glucose_mg_dl)) {
        return result("red_flag", G.messages.red_flag);
      }
      return result("red_flag", null);
    }

    // 4. injection
    function looksEncoded(text) {
      for (const m of text.matchAll(rx(R.base64))) {
        const run = m[0];
        if (/[A-Z]/.test(run) && /[a-z]/.test(run) && /[0-9]/.test(run)) return true;
      }
      return false;
    }
    function injection(q) {
      const hit = phraseHits(p.injection_phrases, q).length > 0 || R.role_tags.some((s) => rx(s).test(q)) || looksEncoded(q);
      return result("injection", hit ? G.messages.injection : null);
    }

    // 5. range and unit
    const isATime = (text, end) => new RegExp(`^\\s*(?:${p.number_followed_by_words_to_ignore.join("|")})\\b`, "iu").test(text.slice(end));
    const rangeMessage = (key) => fmt(G.messages.range, { name: G.range_names[key] });
    function rangeUnit(q, patient) {
      if (patient) {
        for (const [name, [low, high]] of Object.entries(G.ranges)) {
          const value = patient[name];
          if (value === null || value === undefined) continue;
          if (!(low <= value && value <= high)) {
            return result("range", name === "hba1c_pct" && value > high ? G.messages.hba1c_unit : rangeMessage(name));
          }
        }
      }
      const mmolMol = new Set(p.mmol_per_mol_words.map((w) => w.replace(/ /g, "")));
      for (const [name, spec] of Object.entries(R.text_values)) {
        for (const m of q.matchAll(rx(spec, "d"))) {
          if (isATime(q, m.indices[1][1])) continue;
          let value = parseFloat(m[1]);
          const unit = m.length > 2 ? (m[2] || "").toLowerCase().replace(/ /g, "") : "";
          if (name === "hba1c" && (mmolMol.has(unit) || value > G.ranges.hba1c_pct[1])) return result("range", G.messages.hba1c_unit);
          if (name === "glucose") value = toMgDl(value, unit);
          const key = G.range_key[name];
          const [low, high] = G.ranges[key];
          if (!(low <= value && value <= high)) return result("range", rangeMessage(key));
        }
      }
      for (const m of q.matchAll(rx(R.age_text))) {
        if (parseInt(m[1] || m[2], 10) > G.ranges.age[1]) return result("range", rangeMessage("age"));
      }
      return result("range", null);
    }

    // 6. length and language
    const blocked = new Set(G.rules.blocked_words), allowed = new Set(G.rules.medical_allowlist);
    function lengthLanguage(q) {
      const n = [...q.trim()].length;
      if (n < p.question_min_chars) return result("length_language", fmt(G.messages.too_short, { n: p.question_min_chars }));
      if (n > p.question_max_chars) return result("length_language", fmt(G.messages.too_long, { n: p.question_max_chars }));
      const letters = [...q].filter((ch) => /\p{L}/u.test(ch));
      if (!letters.length || letters.filter((ch) => !/\p{Script=Latin}/u.test(ch)).length / letters.length > p.non_latin_letter_share_max) {
        return result("length_language", letters.length ? G.messages.not_english : G.messages.language);
      }
      if (words(q).some((w) => blocked.has(w) && !allowed.has(w)) || phraseHits(G.rules.blocked_phrases, q).length) {
        return result("length_language", G.messages.language);
      }
      return result("length_language", null);
    }

    // 7. dose request
    const doseRequest = (q) => result("dose_request", R.dose.some((s) => rx(s).test(q.normalize("NFKC"))) ? G.messages.dose_request : null);

    const GUARDS = { scope, identifier, red_flag: redFlag, injection, range: rangeUnit, length_language: lengthLanguage, dose_request: doseRequest };

    /** The seven results, in the order of 8.6. `patient` (optional) uses the API's names: age, type1, on_metformin, hba1c_pct, ... */
    function evaluate(question, patient = null) {
      return G.order.map((id) => GUARDS[id](question, patient));
    }

    /** { status, checks: [{id, result}], blocked_reason, code, shown }: an emergency is shown first, then the order of 8.6. */
    function run(question, patient = null) {
      const results = evaluate(question, patient);
      const byId = Object.fromEntries(results.map((r) => [r.id, r]));
      const blockedIds = G.show_first.filter((id) => byId[id].status === "BLOCK");
      const shown = blockedIds[0] || null;
      return { status: shown ? "BLOCK" : "PASS", checks: results.map((r) => ({ id: r.id, result: r.status })),
        blocked_reason: shown ? byId[shown].blocked_reason : null, code: shown ? G.codes[shown] : null, shown };
    }

    return { evaluate, run, hasIdentifier, words, phraseHits };
  }

  return { make, verhoeffOk };
});
