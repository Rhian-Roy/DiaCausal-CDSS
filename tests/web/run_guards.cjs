// Runs web/guards.js under Node for the parity test: node run_guards.cjs guards.json cases.json
// cases: [{question, patient?}] -> [{results: [{id, status, blocked_reason}], combined: {status, checks, blocked_reason, code}}]
const fs = require("fs");
const path = require("path");
const Guards = require(path.join(__dirname, "..", "..", "web", "guards.js"));
const g = Guards.make(JSON.parse(fs.readFileSync(process.argv[2], "utf8")));
const cases = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const out = cases.map((c) => ({ results: g.evaluate(c.question, c.patient || null), combined: g.run(c.question, c.patient || null) }));
process.stdout.write(JSON.stringify(out));
