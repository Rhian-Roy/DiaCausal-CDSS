// Runs explainEffect / effectDrivers of web/engine.js under Node for the parity test: node run_explain_effect.cjs model.json patients.json
// Out: for every patient, { target: { base, estimate, contributions, shown: [feature, ...] } } for the three comparisons.
const fs = require("fs");
const path = require("path");
const engine = require(path.join(__dirname, "..", "..", "web", "engine.js"));
const model = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const patients = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const out = patients.map((p) => Object.fromEntries(model.xai.explained_targets.map((t) => {
  const e = engine.explainEffect(model, p, t);
  const shown = engine.effectDrivers(model, e).map((c) => c.feature);
  return [t, { ...e, shown, other: engine.otherDetails(model, p, t, shown) }];
})));
process.stdout.write(JSON.stringify(out));
