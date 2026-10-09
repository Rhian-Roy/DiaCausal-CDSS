"""The 20 golden questions for the local-model benchmark (eval/llm_golden.csv; plan 8.8) and the inputs each one needs.

A golden question is a question of eval/rag_gold.csv (so its answer is in the corpus) paired with one of the three demo patients
(the presets of demo/streamlit_app.py), so that the causal output the model must copy numbers from is a real one. `prepare` runs the
SAME layers the pipeline runs (rules, causal engine, retrieval) and returns the filled context; nothing is faked.

The file is a draft written by Claude: Members B and D review the questions and their pairing (column `review`).
"""

from __future__ import annotations

import csv
import tempfile
from pathlib import Path

from diacausal.api.schemas import AskRequestV1
from diacausal.config import ROOT

GOLDEN_CSV = ROOT / "eval" / "llm_golden.csv"

_FLAGS = dict(ascvd=False, heart_failure=False, ckd=False, past_hypo=False, past_dka=False, past_pancreatitis=False, type1=False,
              on_metformin=True, cost_concern=False)
# The three demo presets as v1 patients (the same people as tests/orchestrator/pipeline_helpers.py).
PRESET_PATIENTS = {
    "typical": dict(age=52, sex="M", duration_years=5.0, hba1c_pct=8.4, egfr=88.0, bmi=27.0),
    "egfr40_pancreatitis": dict(age=60, sex="F", duration_years=8.0, hba1c_pct=8.2, egfr=40.0, bmi=25.5, past_pancreatitis=True, ckd=True),
    "older_hypo": dict(age=80, sex="M", duration_years=15.0, hba1c_pct=8.0, egfr=38.0, bmi=24.0, past_hypo=True, ascvd=True, ckd=True),
}


def load_golden(path: Path = GOLDEN_CSV) -> list[dict]:
    with Path(path).open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def request_for(row: dict, mode: str = "ollama") -> AskRequestV1:
    return AskRequestV1(schema_version="1.0", request_id=row["id"], patient={**_FLAGS, **PRESET_PATIENTS[row["preset"]]},
                        question=row["question"], mode=mode)


def prepare(row: dict, engine=None):
    """The pipeline context of one golden question, after the rules, causal and retrieval layers (no model call, no audit line in
    the real audit log). Returns None when retrieval found no evidence (the question cannot be used)."""
    from diacausal import registry
    from diacausal.causal_inference import recommend
    from diacausal.causal_inference.recommend import get_engine
    from diacausal.api.schemas.patient import to_engine_patient
    from diacausal.orchestrator.context import Context
    from diacausal.tracing import AbstainSignal

    request = request_for(row)
    ctx = Context(request=request, engine=engine or get_engine(), patient=to_engine_patient(request.patient))
    real = recommend.AUDIT_PATH
    recommend.AUDIT_PATH = Path(tempfile.gettempdir()) / "diacausal-bench-audit.jsonl"  # never the real audit log
    try:
        for name in ("rules", "causal engine", "retrieval"):
            try:
                registry.layer_function(name)(ctx)
            except AbstainSignal:
                if name == "retrieval":
                    return None
    finally:
        recommend.AUDIT_PATH = real
    return ctx
