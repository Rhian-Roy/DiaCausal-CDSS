// Builds answer cards with web/card.js under Node for the contract test: node run_card.cjs model.json cases.json
// Each case: { patient, passages, sentences, retrieval_abstained }. Out: { result, card } per case.
const fs = require("fs");
const path = require("path");
const engine = require(path.join(__dirname, "..", "..", "web", "engine.js"));
const Card = require(path.join(__dirname, "..", "..", "web", "card.js"));
const model = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const cases = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const out = cases.map((c) => {
  const result = engine.recommend(model, c.patient);
  const card = Card.build(model, result, c.patient, { question: c.question, passages: c.passages, sentences: c.sentences, retrievalAbstained: c.retrieval_abstained });
  return { result, card, leaders: Card.leaders(card).map((e) => e.option) };
});
process.stdout.write(JSON.stringify(out));
