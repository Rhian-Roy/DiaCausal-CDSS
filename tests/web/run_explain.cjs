// Runs web/explain.js under Node for the parity test: node run_explain.cjs evidence.json cases.json
// cases: [{question, answer?}] -> [{search, explain, model?}]
const fs = require("fs");
const path = require("path");
const E = require(path.join(__dirname, "..", "..", "web", "evidence.js"));
const X = require(path.join(__dirname, "..", "..", "web", "explain.js"));
const index = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const cases = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const out = cases.map((c) => {
  const res = E.search(index, c.question);
  const o = { status: res.status, explain: X.explain(index, c.question, res) };
  if (c.answer !== undefined) o.model = X.fromModel(index, c.question, res, "gemini", c.answer);
  return o;
});
process.stdout.write(JSON.stringify(out));
