"""Write tests/contract/examples/<ModelName>.json (P09). Run once; the files are committed and edited by hand
afterwards if a contract changes. Examples marked ILLUSTRATIVE in their "_note" are not measured results.

    .venv/bin/python scripts/make_contract_examples.py

Plan 8.4 gives the shapes for AskRequestV1, GuardResultV1, EligibleOptionsV1, CausalOutputV1, DriverV1,
EvidenceBundleV1 and AnswerDraftV1; the rest are built from plan 8.8 to 8.11. CausalOutputV1 uses the engine's
own output (real field names and values) with the plan's illustrative drivers added.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from diacausal.api.schemas import (AnswerCardV1, AnswerDraftV1, AskRequestV1, CausalOutputV1, GuardedDraftV1,  # noqa: E402
                                   PatientV1, to_engine_patient)
from diacausal.causal_inference.recommend import Engine  # noqa: E402

OUT = ROOT / "tests" / "contract" / "examples"
ILLUSTRATIVE = "ILLUSTRATIVE: numbers from plan section 8.4/8.11, not a measured result."

PATIENT = {"age": 52, "sex": "M", "duration_years": 6, "hba1c_pct": 8.6, "egfr": 72, "bmi": 27.1, "ascvd": False,
           "heart_failure": False, "ckd": False, "past_hypo": False, "past_dka": False, "past_pancreatitis": False,
           "type1": False, "on_metformin": True, "cost_concern": True}
DRIVERS = [{"feature": "hba1c_pct", "value": 8.6, "contribution": -0.04}, {"feature": "egfr", "value": 72, "contribution": 0.032},
           {"feature": "bmi", "value": 27.1, "contribution": -0.011}]
CHUNK = {"chunk_id": "S01-p12-c3", "source": "WHO 2018 second- and third-line medicines", "version": "2018",
         "section": "Recommendations", "page": 12, "licence": "CC BY-NC-SA 3.0 IGO",
         "text": "ILLUSTRATIVE passage text, shown verbatim in the real bundle.",
         "scores": {"bm25": 7.1, "dense": 0.62, "rrf": 0.031}}


def write(name: str, data: dict) -> None:
    (OUT / f"{name}.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    patient = PatientV1.model_validate(PATIENT)
    write("PatientV1", {"_note": "From plan 8.4 (the patient inside AskRequestV1).", **PATIENT})
    write("AskRequestV1", {"_note": "Plan 8.4.", "schema_version": "1.0", "request_id": "c2f1", "patient": PATIENT,
                           "question": "Is an SGLT2 inhibitor reasonable for this patient?", "mode": "template"})
    write("GuardResultV1", {"_note": "Plan 8.4.", "status": "PASS", "blocked_reason": None,
                            "checks": [{"id": i, "result": "PASS"} for i in
                                       ("scope", "identifier", "red_flag", "injection", "range", "length_language", "dose_request")]})
    rules_sha = Engine().recommend(to_engine_patient(patient), audit=False).versions.rules_sha
    write("EligibleOptionsV1", {"_note": "Plan 8.4, with a real rule (R07, data/rules.csv) in place of 'R0x'.",
                                "rules_version": f"rules.csv@{rules_sha}", "excluded": [],
                                "caution": [{"option": "SU", "rule_id": "R07", "source": "Glimepiride US prescribing information, Sec 5.1"}],
                                "eligible": ["SGLT2i", "DPP4i", "SU"]})
    out = json.loads(Engine().recommend(to_engine_patient(patient), audit=False).model_dump_json())
    out["request_id"] = "c2f1"
    for o in out["options"]:
        o["drivers"] = DRIVERS if o["arm"] == "SGLT2i" and o["status"] == "estimate" else []
    CausalOutputV1.model_validate(out)
    write("CausalOutputV1", {"_note": "The engine's real output for the plan-8.4 patient (existing field names unchanged); "
                                     "the drivers on SGLT2i are ILLUSTRATIVE (plan 8.4) until P25 computes them.", **out})
    write("DriverV1", {"_note": "Plan 8.4.", **DRIVERS[0]})
    write("EvidenceChunkV1", {"_note": ILLUSTRATIVE, **CHUNK})
    write("EvidenceBundleV1", {"_note": ILLUSTRATIVE, "status": "OK", "index_version": "kb-2026-10-15", "chunks": [CHUNK]})
    write("AnswerDraftV1", {"_note": "Plan 8.4.", "question_context": "The question asks whether an SGLT2 inhibitor is reasonable for this patient.",
                            "evidence_summary": [{"claim": "ILLUSTRATIVE claim supported by the passage.", "chunk_ids": ["S01-p12-c3"]}],
                            "limitations": "Estimates come from a synthetic cohort and have not been validated on real patients."})
    write("LLMRequestV1", {"_note": ILLUSTRATIVE + " Fields are the placeholders of the plan-8.9 prompt.", "request_id": "c2f1", "mode": "ollama",
                          "question": "Is an SGLT2 inhibitor reasonable for this patient?",
                          "patient_summary": "52 y, M, HbA1c 8.6%, eGFR 72, BMI 27.1 (overweight)", "excluded_by_rules": [],
                          "causal_output": {k: v for k, v in json.loads((OUT / "CausalOutputV1.json").read_text()).items() if k != "_note"},
                          "drivers": {"SGLT2i": DRIVERS},
                          "evidence": {"status": "OK", "index_version": "kb-2026-10-15", "chunks": [CHUNK]}, "max_claims": 4})
    write("GuardedDraftV1", {"_note": ILLUSTRATIVE, "status": "PASS", "dropped_claims": 0, "fallback_reason": None,
                             "checks": [{"id": i, "result": "PASS"} for i in
                                        ("parse", "citations", "numbers", "dose_threshold", "excluded_option", "insufficient_wording", "identifier_causal")],
                             "draft": {k: v for k, v in json.loads((OUT / "AnswerDraftV1.json").read_text()).items() if k != "_note"}})
    co = json.loads((OUT / "CausalOutputV1.json").read_text())
    rows = []
    for o in co["options"]:
        est = o["status"] == "estimate"
        sec = o.get("secondary") or {}
        rows.append({"option": o["arm"], "status": {"estimate": "ESTIMATED", "excluded": "EXCLUDED", "insufficient_evidence": "INSUFFICIENT_EVIDENCE"}[o["status"]],
                     "caution": est and bool(o["safety"]), "hba1c_change": o["effect"] if est else None, "vs_comparator": None,
                     "weight_change_kg": sec.get("weight_change_kg") if est else None, "hypo_risk_pct": sec.get("hypo_risk_pct") if est else None,
                     "cost_label": o["cost"]["label"]})
    levels = [{"option": r["option"], "level": "Moderate" if r["status"] == "ESTIMATED" else "Insufficient",
               "reason": "ILLUSTRATIVE: the TEAM-SET rule of plan 8.11 is applied in P24."} for r in rows]
    card = {"_note": ILLUSTRATIVE + " Effects are the engine's real numbers; levels, claims and citations are illustrative.",
            "request_id": "c2f1", "mode": "template", "question": "Is an SGLT2 inhibitor reasonable for this patient?",
            "patient_summary": "52 y, M, HbA1c 8.6%, eGFR 72, BMI 27.1 (overweight)", "comparator": "DPP4i",
            "claims": [{"text": "ILLUSTRATIVE claim supported by the passage.", "citations": [{"chunk_id": "S01-p12-c3", "label": "WHO 2018, p.12"}]}],
            "effects": rows, "drivers": {"SGLT2i": DRIVERS}, "evidence_levels": levels,
            "excluded": [], "abstain": [], "versions": co["versions"]}
    AnswerCardV1.model_validate({k: v for k, v in card.items() if k != "_note"})
    GuardedDraftV1.model_validate({k: v for k, v in json.loads((OUT / "GuardedDraftV1.json").read_text()).items() if k != "_note"})
    write("AnswerCardV1", card)
    AskRequestV1.model_validate({k: v for k, v in json.loads((OUT / "AskRequestV1.json").read_text()).items() if k != "_note"})
    print("wrote", len(list(OUT.glob("*.json"))), "examples to", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
