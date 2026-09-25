// Runs web/engine.js under Node for the parity test: node run_engine.cjs model.json patients.json
const fs = require("fs");
const path = require("path");
const engine = require(path.join(__dirname, "..", "..", "web", "engine.js"));
const model = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const patients = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const out = patients.map((p) => engine.recommend(model, p, { raw: true }));
process.stdout.write(JSON.stringify(out));
