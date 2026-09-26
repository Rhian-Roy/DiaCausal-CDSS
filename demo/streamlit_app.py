"""DiaCausal demo — compare three options added to metformin for one patient.

    streamlit run demo/streamlit_app.py

Research prototype for clinician evaluation; not a marketed medical device;
not for unsupervised clinical use. SYNTHETIC DATA ONLY. The clinician decides.

Colours (never green for "recommended"): red = excluded, amber = caution,
grey = insufficient evidence, pine (teal) = an estimate with its 95% range.
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import streamlit as st  # noqa: E402

from diacausal_engine import INTENDED_USE  # noqa: E402
from diacausal_engine.recommend import AUDIT_PATH, Engine  # noqa: E402
from diacausal_engine.schemas import PatientIn  # noqa: E402

# Tokens copied from frontend/src/index.css (design/chat.html).
INK, MUTED, PINE, PINE_FILL = "#1A1F1C", "#52514E", "#0E5049", "#E4EEEB"
RED, RED_FILL, AMBER, AMBER_FILL, GREY, GREY_FILL = "#8A1010", "#FADCDC", "#6E4400", "#FBEBCB", "#4A4F4C", "#ECEEEC"

PRESETS = {
    "1 · Typical patient": dict(age=52, sex="male", duration_years=5.0, hba1c=8.4, egfr=88.0, bmi=27.0),
    "2 · eGFR 40, past pancreatitis": dict(age=60, sex="female", duration_years=8.0, hba1c=8.2, egfr=40.0, bmi=25.5,
                                            pancreatitis_history=True),
    "3 · Older, past hypoglycaemia": dict(age=80, sex="male", duration_years=15.0, hba1c=8.0, egfr=38.0, bmi=24.0,
                                           hypo_history=True, ascvd=True),
}
DEFAULT = dict(age=55, sex="male", duration_years=6.0, hba1c=8.5, egfr=80.0, bmi=26.0)
FLAGS = {
    "ascvd": "Established heart disease (ASCVD)",
    "hf": "Heart failure",
    "hypo_history": "Past hypoglycaemia",
    "dka_history": "Past diabetic ketoacidosis",
    "pancreatitis_history": "Past pancreatitis",
    "t1d": "Type 1 diabetes",
    "low_income": "Cost is a major concern",
}


@st.cache_resource(show_spinner="Fitting the causal engine on the synthetic cohort (about 5 seconds)…")
def engine() -> Engine:
    return Engine()


def load_preset(values: dict) -> None:
    for k, v in (DEFAULT | {f: False for f in FLAGS} | values).items():
        st.session_state[k] = v


def card(border: str, fill: str, title: str, badge: str, body: str) -> None:
    st.markdown(
        f"""<div style="border:2px solid {border};background:{fill};border-radius:10px;padding:12px 14px;margin-bottom:10px">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <strong style="color:{INK};font-size:1.05rem">{html.escape(title)}</strong>
          <span style="background:{border};color:white;border-radius:999px;padding:2px 10px;font-size:0.8rem">{html.escape(badge)}</span>
        </div>{body}</div>""",
        unsafe_allow_html=True,
    )


def safety_html(option) -> str:
    rows = []
    for s in option.safety:
        colour = RED if s.action == "EXCLUDE" else AMBER
        rows.append(
            f'<div style="margin-top:6px;color:{colour}"><strong>{s.rule_id} · {s.action.title()}</strong> '
            f'({html.escape(s.condition)}; rule {s.rule_status.lower()}): {html.escape(s.message)}'
            f'<br><span style="color:{MUTED};font-size:0.85rem">Source: {html.escape(s.source)} — {html.escape(s.section)}</span></div>'
        )
    return "".join(rows)


def forest(options) -> plt.Figure:
    est = [o for o in options if o.status == "estimate"]
    fig, ax = plt.subplots(figsize=(7, 0.7 * len(est) + 1.2))
    fig.patch.set_facecolor("white")
    for i, o in enumerate(est):
        e = o.effect
        ax.errorbar(e.value, i, xerr=[[e.value - e.ci_low], [e.ci_high - e.value]], fmt="o", color=PINE,
                    markersize=9, capsize=5, linewidth=2.5)
        ax.text(e.ci_high + 0.02, i, f"{e.value:+.2f} ({e.ci_low:+.2f} to {e.ci_high:+.2f})", va="center",
                fontsize=9, color=INK)
    ax.axvline(0, color=MUTED, linewidth=1)
    ax.set_yticks(range(len(est)), [o.name for o in est])
    ax.set_xlabel("expected change in HbA1c at 6 months (percentage points; left = larger fall)")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", color="#E4E3DF")
    lo = min(o.effect.ci_low for o in est)
    hi = max(o.effect.ci_high for o in est)
    ax.set_xlim(lo - 0.1, max(hi + 0.6, 0.1))
    ax.set_ylim(-0.6, len(est) - 0.4)
    fig.tight_layout()
    return fig


def main() -> None:
    st.set_page_config(page_title="DiaCausal — options added to metformin", layout="wide")
    st.markdown(
        f'<div style="background:{PINE_FILL};border-left:6px solid {PINE};padding:10px 14px;border-radius:6px;'
        f'color:{INK};font-weight:600">{html.escape(INTENDED_USE)}</div>',
        unsafe_allow_html=True,
    )
    st.title("DiaCausal — what might each add-on to metformin do for this patient?")
    st.caption("Synthetic India-calibrated data only. Adults with type 2 diabetes already on metformin. "
               "Estimates are 6-month HbA1c change with a 95% range. The clinician decides.")

    if "age" not in st.session_state:
        load_preset(PRESETS["1 · Typical patient"])

    with st.sidebar:
        st.subheader("Preset patients")
        for label, values in PRESETS.items():
            st.button(label, on_click=load_preset, args=(values,), use_container_width=True)
        st.subheader("Patient details")
        st.number_input("Age (years)", 18, 110, key="age", step=1)
        st.radio("Sex", ["female", "male"], key="sex", horizontal=True)
        st.number_input("Diabetes duration (years)", 0.0, 80.0, key="duration_years", step=0.5)
        st.number_input("HbA1c (%)", 4.0, 20.0, key="hba1c", step=0.1, format="%.1f")
        st.number_input("eGFR (mL/min/1.73m²)", 0.0, 150.0, key="egfr", step=1.0, format="%.0f")
        st.number_input("BMI (kg/m²)", 12.0, 70.0, key="bmi", step=0.1, format="%.1f")
        for key, label in FLAGS.items():
            st.checkbox(label, key=key)

    patient = PatientIn(**{k: st.session_state[k] for k in PatientIn.model_fields})
    result = engine().recommend(patient)
    st.markdown(f"**BMI category:** {result.bmi_category} · **Request ID:** `{result.request_id}`")

    if result.applicable == "NOT_APPLICABLE":
        card(GREY, GREY_FILL, "Not applicable for this patient", "NOT APPLICABLE",
             "<div style='margin-top:6px'>" + html.escape("; ".join(result.not_applicable_reasons)) + "</div>")

    st.subheader("The three options (safety rules ran first)")
    cols = st.columns(3)
    for col, o in zip(cols, result.options):
        with col:
            title = f"{o.name} (e.g. {o.example_molecule})"
            cost = f"<div style='margin-top:6px;color:{MUTED}'>Cost: {html.escape(o.cost.label)}</div>"
            if o.status == "excluded":
                card(RED, RED_FILL, title, "EXCLUDED", "<div style='margin-top:6px'>Not estimated: removed by a "
                     "safety rule before the causal engine ran.</div>" + safety_html(o) + cost)
            elif o.status == "insufficient_evidence":
                card(GREY, GREY_FILL, title, "INSUFFICIENT EVIDENCE",
                     f"<div style='margin-top:6px'>{html.escape(o.insufficient_reason or '')}</div>" + safety_html(o) + cost)
            else:
                e = o.effect
                badge = "ESTIMATE · CAUTION" if o.safety else "ESTIMATE"
                border, fill = (AMBER, AMBER_FILL) if o.safety else (PINE, PINE_FILL)
                body = (f"<div style='margin-top:6px;font-size:1.3rem;color:{PINE}'><strong>{e.value:+.2f}</strong> "
                        f"<span style='font-size:0.95rem'>(95% range {e.ci_low:+.2f} to {e.ci_high:+.2f})</span></div>"
                        f"<div style='color:{MUTED};font-size:0.85rem'>percentage points of HbA1c at 6 months · "
                        f"propensity {o.confidence.propensity:.2f}</div>")
                if o.secondary:
                    w, h = o.secondary.weight_change_kg, o.secondary.hypo_risk_pct
                    body += (f"<div style='margin-top:6px;font-size:0.9rem'>Weight: <strong>{w.value:+.1f} kg</strong> "
                             f"({w.ci_low:+.1f} to {w.ci_high:+.1f})<br>Any low sugar by 6 months: "
                             f"<strong>{h.value:.1f}%</strong> ({h.ci_low:.1f} to {h.ci_high:.1f})</div>")
                card(border, fill, title, badge, body + safety_html(o) + cost)

    if any(o.status == "estimate" for o in result.options):
        st.subheader("Estimates with their 95% ranges")
        st.pyplot(forest(result.options))
    if result.comparisons:
        st.subheader("Fair comparisons between options")
        st.table([{
            "Comparison": f"{c.first} minus {c.second}",
            "Difference (points)": f"{c.difference.value:+.2f}",
            "95% range": f"{c.difference.ci_low:+.2f} to {c.difference.ci_high:+.2f}",
        } for c in result.comparisons])
        st.caption("Negative = the first option lowers HbA1c more. A range that crosses 0 means no clear difference.")

    st.markdown(f'<div style="background:{PINE_FILL};padding:10px 14px;border-radius:6px;color:{INK}">'
                f'<strong>{html.escape(result.decision)}</strong></div>', unsafe_allow_html=True)

    with st.expander("Why causal? (the worked example)"):
        st.markdown(
            "In old records doctors gave different drugs to different patients, so a plain comparison is unfair.\n\n"
            "| Group | Got SGLT2i | Got sulfonylurea | Difference |\n|---|---|---|---|\n"
            "| High starting HbA1c | 300 patients, −1.2 | 100 patients, −1.0 | −0.2 |\n"
            "| Lower starting HbA1c | 100 patients, −0.6 | 300 patients, −0.5 | −0.1 |\n"
            "| Everyone pooled (naive) | −1.05 | −0.625 | **−0.425** |\n\n"
            "Comparing like with like, weighting both groups equally: 0.5 × (−0.2) + 0.5 × (−0.1) = **−0.15**. "
            "The naive answer is about three times too big only because sicker patients got SGLT2i more often "
            "(confounding by indication). DiaCausal corrects this with propensity weighting (AIPW) and the "
            "DR-learner, and says “insufficient evidence” when too few similar patients got an option "
            "(propensity below 0.05). *Made-up illustrative numbers.*"
        )
    with st.expander("Assumptions behind these numbers"):
        for a in result.assumptions:
            st.markdown(f"- {a}")
        st.caption(f"Versions: engine {result.versions.engine}, params {result.versions.params} "
                   f"({result.versions.params_sha}), rules {result.versions.rules_sha}, cohort {result.versions.cohort}.")
    with st.expander("Audit log (last line — decisions and IDs only, never patient values)"):
        try:
            last = Path(AUDIT_PATH).read_text(encoding="utf-8").strip().splitlines()[-1]
            st.code(json.dumps(json.loads(last), indent=1), language="json")
        except (OSError, IndexError):
            st.write("No audit lines yet.")
    with st.expander("Structured Causal Output (the JSON the API returns)"):
        st.json(result.model_dump())


main()
