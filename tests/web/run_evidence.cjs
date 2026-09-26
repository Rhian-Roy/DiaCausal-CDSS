// Runs web/evidence.js under Node for the parity test: node run_evidence.cjs evidence.json questions.json
const fs = require("fs");
const path = require("path");
const evidence = require(path.join(__dirname, "..", "..", "web", "evidence.js"));
const index = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const questions = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
process.stdout.write(JSON.stringify(questions.map((q) => evidence.search(index, q, { raw: true }))));
