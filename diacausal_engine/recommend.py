"""One patient in -> one structured Causal Output out (used by the demo AND the API).

The order never changes (safety first):
    1. check the inputs            (schemas.PatientIn: units and plausible ranges)
    2. safety rules                (data/rules.csv) — an excluded option is never estimated
    3. support check               is this patient like anyone in the cohort?
    4. overlap check               propensity below 0.05 -> "insufficient evidence"
    5. DR-learner estimate         expected 6-month HbA1c change with a 95% interval
                                   (too wide a range -> "insufficient evidence" too), plus
                                   6-month weight change and hypoglycaemia risk (FR7)
    6. cost lookup                 data/prices.csv ("price unavailable" until confirmed)
    7. output check                no dose text; every number has an interval
    8. audit log                   what was decided and why — never the patient's values

Research prototype for clinician evaluation; not a marketed medical device;
not for unsupervised clinical use. The clinician decides.
"""

from __future__ import annotations

import csv
import json
import os
import re
import time
import uuid
from functools import lru_cache
from pathlib import Path

import numpy as np

from diacausal_engine import ARMS, CONTRASTS, INTENDED_USE, __version__
from diacausal_engine.cohort import generate_cohort
from diacausal_engine.config import PRICES_PATH, ROOT, Params, load_params
from diacausal_engine.dag import load_dag
from diacausal_engine.fitting import Fitted, fit_all
from diacausal_engine.guardrails import RuleTable, load_rules
from diacausal_engine.propensity import overlap_check, predict, support_check
from diacausal_engine.schemas import (
    CausalOutput,
    Comparison,
    Confidence,
    Cost,
    Interval,
    OptionOut,
    PatientIn,
    SafetyNote,
    Secondary,
    Versions,
)

ASSUMPTIONS = [
    "Synthetic data only: estimates come from an India-calibrated SIMULATED cohort, not real patients.",
    "No unmeasured confounding: every reason doctors chose a drug is among the patient details used.",
    "Positivity/overlap: similar patients received each option (checked; below 0.05 we abstain).",
    "The DAG in data/params.yaml is correct; weight change is a mediator and is not adjusted for.",
    "Effect sizes are ASSUMED-DIRECTIONAL: direction and rough size follow cited trials; exact values are team choices.",
    "The DR-learner interval assumes the effect changes roughly linearly with each patient detail.",
    "One example drug per class; safety rules are from US labels and await review for Indian practice.",
]

# Dose-looking text is never allowed in any output (strengths, frequencies, tablets).
DOSE_PATTERN = re.compile(
    r"\b\d+(\.\d+)?\s*(mg|mcg|µg|microgram|milligram)s?\b|\b(once|twice|thrice)\s+(a\s+)?daily\b|"
    r"\bmg\s*/\s*day\b|\b\d+\s*(tablet|tab)s?\b",
    re.I,
)
AUDIT_PATH = Path(os.environ.get("DIACAUSAL_AUDIT_LOG", ROOT / "logs" / "audit.jsonl"))


class OutputCheckError(RuntimeError):
    """The reply broke a safety invariant; it is withheld."""


def bmi_category(params: Params, bmi: float) -> str:
    """Asian-Indian cut-offs (Misra 2009): overweight >= 23, obese >= 25."""
    under = params.get("display.bmi_underweight_below")
    over = params.get("display.bmi_overweight_from")
    obese = params.get("display.bmi_obese_from")
    if bmi < under:
        return f"Underweight (below {under:g})"
    if bmi < over:
        return f"Normal ({under:g} to below {over:g})"
    if bmi < obese:
        return f"Overweight ({over:g} to below {obese:g}, Asian-Indian cut-off)"
    return f"Obese ({obese:g} or above, Asian-Indian cut-off)"


def load_prices(path: Path = PRICES_PATH) -> dict[str, Cost]:
    """A price is shown only when confirmed with a number, a date and a source."""
    out: dict[str, Cost] = {}
    with Path(path).open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            ok = row["status"] == "CONFIRMED" and row["inr_per_month"] and row["as_of_date"] and row["source"]
            if ok:
                value = float(row["inr_per_month"])
                out[row["arm"]] = Cost(inr_per_month=value, label=f"about INR {value:,.0f} per month",
                                       as_of_date=row["as_of_date"], source=row["source"])
            else:
                out[row["arm"]] = Cost(inr_per_month=None, label="price unavailable")
    return out


def check_output(result: CausalOutput) -> None:
    """Refuse a reply that would break a rule: doses, bare numbers, estimated exclusions."""
    text = result.model_dump_json()
    if DOSE_PATTERN.search(text):
        raise OutputCheckError("dose-like text found in the reply")
    if result.intended_use != INTENDED_USE:
        raise OutputCheckError("intended-use statement missing")
    for o in result.options:
        if o.status == "estimate":
            e = o.effect
            if e is None or not (e.ci_low <= e.value <= e.ci_high) or o.confidence is None:
                raise OutputCheckError(f"{o.arm}: an estimate without a 95% interval")
            if o.secondary is not None:
                for iv in (o.secondary.weight_change_kg, o.secondary.hypo_risk_pct):
                    if not (iv.ci_low <= iv.value <= iv.ci_high):
                        raise OutputCheckError(f"{o.arm}: a secondary outcome without a valid interval")
        elif o.effect is not None or o.secondary is not None:
            raise OutputCheckError(f"{o.arm}: {o.status} options must not carry a number")
        if o.status == "excluded" and not any(s.action == "EXCLUDE" for s in o.safety):
            raise OutputCheckError(f"{o.arm}: excluded without a cited rule")
    if result.applicable == "NOT_APPLICABLE" and any(o.status == "estimate" for o in result.options):
        raise OutputCheckError("NOT_APPLICABLE reply carries estimates")


def write_audit(result: CausalOutput, patient: PatientIn, path: Path | None = None) -> dict:
    """One JSON line: IDs, versions, which fields arrived, what was decided. No patient values."""
    line = {
        "time": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "request_id": result.request_id,
        "engine": result.versions.engine,
        "params_sha": result.versions.params_sha,
        "rules_sha": result.versions.rules_sha,
        "fields_received": sorted(patient.model_fields_set),
        "applicable": result.applicable,
        "options": {o.arm: {"status": o.status, "rules": [s.rule_id for s in o.safety]} for o in result.options},
    }
    target = Path(path or AUDIT_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line) + "\n")
    return line


class Engine:
    """Fitted once on the fixed reference cohort; then answers each patient in milliseconds."""

    def __init__(self, params: Params | None = None, rules: RuleTable | None = None,
                 n: int | None = None, seed: int | None = None):
        self.params = params or load_params()
        self.rules = rules or load_rules()
        self.seed = int(self.params.get("engine.reference_cohort_seed") if seed is None else seed)
        self.n = int(n or self.params.get("generator.n_patients"))
        cohort = generate_cohort(self.params, n=self.n, seed=self.seed)
        self.fitted: Fitted = fit_all(self.params, cohort, int(self.params.get("engine.random_seed")))
        self.adjustment = load_dag(self.params).adjustment_set
        self.prices = load_prices()
        self.z = self.params.get("engine.ci_z")
        self.threshold = self.params.get("engine.overlap_min_propensity")
        self.max_width = self.params.get("engine.max_interval_width")

    def _row(self, patient: PatientIn) -> dict:
        d = patient.model_dump()
        d["female"] = 1 if d.pop("sex") == "female" else 0
        return {k: float(v) for k, v in d.items()}

    def _secondary(self, x: np.ndarray) -> dict[str, Secondary]:
        """Weight change (kg) and hypoglycaemia risk (%) for each option, each with a 95% interval."""
        f = self.fitted
        if f.dr_weight is None or f.dr_hypo is None:
            return {}
        w, h = f.dr_weight.predict(x, self.z), f.dr_hypo.predict(x, self.z)
        out = {}
        for arm in ARMS:
            wv, wl, wh = (round(float(v), 2) for v in w[arm][0])
            hv, hl, hh = (round(float(np.clip(100 * v, 0.0, 100.0)), 1) for v in h[arm][0])
            out[arm] = Secondary(weight_change_kg=Interval(value=wv, ci_low=wl, ci_high=wh),
                                 hypo_risk_pct=Interval(value=hv, ci_low=hl, ci_high=hh))
        return out

    def recommend(self, patient: PatientIn, audit: bool = True, audit_path: Path | None = None) -> CausalOutput:
        row = self._row(patient)
        # 2. safety rules first — before anything is estimated
        verdicts = self.rules.apply(row)
        # 3. support
        outside = support_check(row, self.fitted.observed, self.params)
        # 4. overlap (for every option, from the full-data propensity model)
        x = np.array([[row[c] for c in self.adjustment]])
        p = predict(self.fitted.propensity, x)[0]
        ok = overlap_check(p, self.threshold)
        estimable = [a for a in ARMS if not verdicts[a].excluded and not outside and ok[a]]
        # 5. DR-learner — only for options that survived 2-4
        pred = self.fitted.dr.predict(x, self.z) if estimable else {}
        width = {a: float(pred[a][0][2] - pred[a][0][1]) for a in estimable}
        estimable = [a for a in estimable if width[a] <= self.max_width]  # too uncertain -> abstain
        secondary = self._secondary(x) if estimable else {}

        options = []
        for j, arm in enumerate(ARMS):
            v = verdicts[arm]
            notes = [SafetyNote(rule_id=r.rule_id, action=r.action, condition=r.condition, message=r.message,
                                source=r.source, section=r.section, rule_status=r.status) for r in v.fired]
            base = dict(arm=arm, name=self.params.arm_name(arm),
                        example_molecule=self.params.raw["arms"][arm]["example"],
                        safety=notes, cost=self.prices[arm])
            if v.excluded:
                options.append(OptionOut(status="excluded", **base))
            elif outside:
                options.append(OptionOut(status="insufficient_evidence",
                                         insufficient_reason="Outside the cohort: " + "; ".join(outside), **base))
            elif not ok[arm]:
                options.append(OptionOut(
                    status="insufficient_evidence",
                    insufficient_reason=(f"Too few similar patients received this option (propensity {p[j]:.3f}, "
                                         f"below {self.threshold:g}). A fair comparison is not possible."),
                    **base))
            elif arm not in estimable:
                options.append(OptionOut(
                    status="insufficient_evidence",
                    insufficient_reason=(f"Too uncertain: this patient's 95% range is {width[arm]:.2f} points wide "
                                         f"(limit {self.max_width:g}). A useful estimate is not possible."),
                    **base))
            else:
                est, lo, hi = pred[arm][0]
                options.append(OptionOut(
                    status="estimate",
                    secondary=secondary.get(arm),
                    effect=Interval(value=round(float(est), 3), ci_low=round(float(lo), 3), ci_high=round(float(hi), 3)),
                    confidence=Confidence(propensity=round(float(p[j]), 3), overlap_threshold=self.threshold,
                                          method="DR-learner on cross-fitted AIPW scores, HC3 95% interval"),
                    **base))

        comparisons = []
        for a, b in CONTRASTS:
            if a in estimable and b in estimable:
                d, lo, hi = pred[f"{a}-{b}"][0]
                comparisons.append(Comparison(first=a, second=b, difference=Interval(
                    value=round(float(d), 3), ci_low=round(float(lo), 3), ci_high=round(float(hi), 3))))

        reasons = list(outside)
        if all(verdicts[a].excluded for a in ARMS):
            reasons.append("every option is excluded by a safety rule")
        elif not estimable and not outside:
            reasons.append("no option has enough similar patients (or a narrow enough 95% range) for a useful estimate")
        result = CausalOutput(
            request_id=uuid.uuid4().hex[:12],
            applicable="APPLICABLE" if estimable else "NOT_APPLICABLE",
            not_applicable_reasons=reasons if not estimable else [],
            options=options,
            comparisons=comparisons,
            assumptions=ASSUMPTIONS,
            bmi_category=bmi_category(self.params, patient.bmi),
            versions=Versions(engine=__version__, params=self.params.version, params_sha=self.params.fingerprint,
                              rules_sha=self.rules.version, cohort=f"synthetic n={self.n} seed={self.seed}"),
        )
        check_output(result)  # 7.
        if audit:
            write_audit(result, patient, audit_path)  # 8.
        return result


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """The shared engine (fitted once per process: a few seconds)."""
    return Engine()
