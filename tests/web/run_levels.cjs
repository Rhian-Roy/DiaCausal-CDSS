// Runs the evidence-level mirror of web/engine.js under Node for the parity test: node run_levels.cjs model.json cases.json
// Each case: { option, citations, retrieval_abstained, texts }. Out: { level, reason, card, count } per case.
const fs = require("fs");
const path = require("path");
const engine = require(path.join(__dirname, "..", "..", "web", "engine.js"));
const model = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const cases = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const out = cases.map((c) => {
  const a = engine.evidenceLevel(model, c.option, c.citations, c.retrieval_abstained);
  return { level: a.level, reason: a.reason, card: engine.abstainCard(model, c.option, c.retrieval_abstained), count: engine.countCitations(c.texts, c.option) };
});
process.stdout.write(JSON.stringify(out));
