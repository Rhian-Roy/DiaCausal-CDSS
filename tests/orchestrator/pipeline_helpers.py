"""Helpers for the pipeline tests: the three demo presets as v1 patients (a module of its own, not `conftest`)."""

FLAGS = dict(ascvd=False, heart_failure=False, ckd=False, past_hypo=False, past_dka=False, past_pancreatitis=False,
             type1=False, on_metformin=True)

# The three presets of the demo (demo/streamlit_app.py), written as v1 patients, each with a question.
PRESETS = {
    "typical": (dict(age=52, sex="M", duration_years=5.0, hba1c_pct=8.4, egfr=88.0, bmi=27.0),
                "Can SGLT2 inhibitors cause ketoacidosis?"),
    "egfr40_pancreatitis": (dict(age=60, sex="F", duration_years=8.0, hba1c_pct=8.2, egfr=40.0, bmi=25.5,
                                 past_pancreatitis=True, ckd=True),
                            "Is a DPP-4 inhibitor safe after pancreatitis?"),
    "older_hypo": (dict(age=80, sex="M", duration_years=15.0, hba1c_pct=8.0, egfr=38.0, bmi=24.0, past_hypo=True,
                        ascvd=True, ckd=True),
                   "Do sulfonylureas cause low blood sugar in older adults?"),
}


def body(patient: dict, question: str, request_id: str = "t1") -> dict:
    return {"schema_version": "1.0", "request_id": request_id, "patient": {**FLAGS, **patient}, "question": question}
