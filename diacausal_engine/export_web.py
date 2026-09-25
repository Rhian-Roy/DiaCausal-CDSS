"""Export the fitted engine to the website (web/model.json) so it runs in any browser.

    python -m diacausal_engine.export_web

Plain English: after training, the engine only needs a few hundred numbers to answer a
patient. They are the propensity model's coefficients, the DR-learner's formula and its
uncertainty, the range of the cohort, the safety rules and the thresholds. We write those to
JSON, and web/engine.js repeats exactly the same steps as recommend.py in the visitor's
browser, so nothing a user types ever leaves their phone. A test
(tests/web/test_web.py) proves the two give the same answers.

It also copies the benchmark results, the five figures (resized for phones) and the two
plain-English docs into web/.
"""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

from diacausal_engine import ARMS, CONTRASTS, INTENDED_USE, __version__
from diacausal_engine.config import ROOT
from diacausal_engine.estimators import TARGETS
from diacausal_engine.recommend import ASSUMPTIONS, DOSE_PATTERN, Engine

WEB = ROOT / "web"
FIGURES = ("overlap", "love_plot", "ate_vs_truth", "cate_recovery", "calibration")
DOCS = {"causal-engine.md": ROOT / "docs/explain/07-causal-engine.md",
        "results-summary.md": ROOT / "docs/RESULTS_SUMMARY.md"}


def _floats(a) -> list:
    return [float(v) for v in a] if getattr(a, "ndim", 1) == 1 else [_floats(r) for r in a]


def model_dict(engine: Engine) -> dict:
    p, f = engine.params, engine.fitted
    scaler, logit = f.propensity.named_steps["standardscaler"], f.propensity.named_steps["logisticregression"]
    if list(logit.classes_) != [0, 1, 2]:
        raise ValueError("propensity model must have classes 0, 1, 2 (SGLT2i, DPP4i, SU)")
    obs = f.observed
    support = {}
    for col in engine.adjustment:
        values = obs[col]
        if values.nunique() <= 2:
            support[col] = {"kind": "values", "values": sorted(float(v) for v in set(values.astype(float)))}
        else:
            support[col] = {"kind": "range", "min": float(values.min()), "max": float(values.max())}
    return {
        "intended_use": INTENDED_USE,
        "arms": [{"arm": a, "name": p.arm_name(a), "example": p.raw["arms"][a]["example"]} for a in ARMS],
        "contrasts": [list(c) for c in CONTRASTS],
        "targets": TARGETS,
        "features": engine.adjustment,
        "propensity": {"mean": _floats(scaler.mean_), "scale": _floats(scaler.scale_),
                       "coef": _floats(logit.coef_), "intercept": _floats(logit.intercept_)},
        "dr": {"mean": _floats(f.dr.mean_), "scale": _floats(f.dr.scale_),
               "beta": _floats(f.dr.beta_), "cov": [_floats(c) for c in f.dr.cov_]},
        "support": support,
        "t1d_in_cohort": bool(obs["t1d"].any()),
        "rules": [{"rule_id": r.rule_id, "arm": r.arm, "field": r.field, "op": r.op, "value": r.value,
                   "action": r.action, "message": r.message, "source": r.source, "section": r.section,
                   "status": r.status, "condition": r.condition} for r in engine.rules.rules],
        "thresholds": {
            "overlap_min_propensity": engine.threshold,
            "ci_z": engine.z,
            "bmi_underweight_below": p.get("display.bmi_underweight_below"),
            "bmi_overweight_from": p.get("display.bmi_overweight_from"),
            "bmi_obese_from": p.get("display.bmi_obese_from"),
            "input_ranges": p.group("display.input_ranges"),
        },
        "prices": {a: engine.prices[a].model_dump() for a in ARMS},
        "assumptions": ASSUMPTIONS,
        "dose_pattern": DOSE_PATTERN.pattern,
        "method": "DR-learner on cross-fitted AIPW scores, HC3 95% interval",
        "versions": {"engine": __version__, "params": p.version, "params_sha": p.fingerprint,
                     "rules_sha": engine.rules.version, "cohort": f"synthetic n={engine.n} seed={engine.seed}"},
    }


def results_dict() -> dict:
    rows = list(csv.DictReader((ROOT / "results/benchmark_summary.csv").open()))
    ref = list(csv.DictReader((ROOT / "results/refutation.csv").open()))
    ev = list(csv.DictReader((ROOT / "results/evalues.csv").open()))
    info = json.loads((ROOT / "results/run_info.json").read_text())
    return {"summary": rows, "refutation": ref, "evalues": ev,
            "run": {k: info[k] for k in ("reps", "n_patients", "n_test_patients", "seconds",
                                         "refutation_checks_passed", "true_population_effects")}}


def copy_figures(width: int = 1100) -> None:
    from PIL import Image

    out = WEB / "results"
    out.mkdir(parents=True, exist_ok=True)
    for name in FIGURES:
        img = Image.open(ROOT / "results/figures" / f"{name}.png").convert("RGB")
        if img.width > width:
            img = img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)
        img.save(out / f"{name}.png", optimize=True)


def export(engine: Engine | None = None) -> dict:
    engine = engine or Engine()
    model = model_dict(engine)
    WEB.mkdir(exist_ok=True)
    (WEB / "model.json").write_text(json.dumps(model, indent=1) + "\n", encoding="utf-8")
    (WEB / "results.json").write_text(json.dumps(results_dict(), indent=1) + "\n", encoding="utf-8")
    copy_figures()
    (WEB / "docs").mkdir(exist_ok=True)
    for name, src in DOCS.items():
        shutil.copyfile(src, WEB / "docs" / name)
    return model


if __name__ == "__main__":
    m = export()
    print(f"wrote web/model.json (engine {m['versions']['engine']}, params {m['versions']['params_sha']}, "
          f"rules {m['versions']['rules_sha']}), web/results.json, web/results/*.png, web/docs/*.md")
