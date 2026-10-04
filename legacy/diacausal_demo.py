#!/usr/bin/env python3
"""
DiaCausal — interactive demo
============================

    streamlit run diacausal_demo.py

What this adds that the notebook and the script cannot
------------------------------------------------------
The notebook proves the pipeline is correct. The console script narrates it. This
app does the one thing neither can: it lets someone who does not read Python
**move the confounding dial and watch the answer change sign.**

Two controls carry the whole demonstration:

    SCENARIO SLIDER     turns confounding up and down. At `rct` the naive answer
                        is right. At `strong` it has the wrong sign. At
                        `hidden_confounder` the causal answer is wrong too, and
                        the app says so instead of hiding it.

    PATIENT SLIDERS     drag eGFR from 90 down to 40 and watch the recommendation
                        cross from "SGLT2i" to "metformin" — because the authored
                        effect crosses zero around eGFR 55. The population average
                        never moves. That gap IS the argument for a CDSS.

Because the cohort is synthetic, every patient's TRUE individual effect is known.
So the app shows the model's estimate next to the right answer, live. Nothing here
asks you to take a number on trust.

Structure
---------
All heavy work happens in `build_engine`, behind `@st.cache_resource`, so dragging
a patient slider re-runs one CATE prediction rather than refitting four
metalearners. Every estimator is imported from `causal_engine` — the same code the
notebook and the tests run, so a number shown here cannot silently disagree with a
number shown there.

The UI lives under `if __name__ == "__main__"`, which is how Streamlit invokes a
script. That also means this module can be imported by a smoke test without
launching any interface.
"""

from __future__ import annotations

import os

# Must precede the matplotlib import: the default config directory is not
# writable in every environment this project runs in.
os.environ.setdefault("MPLCONFIGDIR", os.environ.get("TMPDIR", "/tmp"))

import warnings
from dataclasses import dataclass

warnings.filterwarnings("ignore")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

from causal_engine import (
    PALETTE, cdss, crosscheck, dag, data, diagnostics, estimators, evaluate,
    guardrails, rag_lite,
)

SCENARIO_BLURB = {
    "rct": "Randomised. Treatment is a coin flip, so the naive comparison is CORRECT. "
           "This is what an RCT buys you.",
    "mild": "Modest confounding. The naive answer drifts — already misleading, "
            "not yet obviously wrong.",
    "strong": "Heavy confounding. The naive answer has the WRONG SIGN. A "
              "correlational CDSS would withhold an effective drug.",
    "hidden_confounder": "An unrecorded frailty score drives both prescribing and "
                         "outcome. Now the CAUSAL answer is wrong too. The methods "
                         "are not magic.",
}

SEVERITY_COLOUR = {
    guardrails.Severity.INFO: PALETTE["primary"],
    guardrails.Severity.CAUTION: PALETTE["amber"],
    guardrails.Severity.WARNING: PALETTE["alert"],
    guardrails.Severity.VETO: PALETTE["alert"],
}


# ═════════════════════════════════════════════════════════════════════════════
# THE ENGINE — everything expensive, computed once per configuration
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class Engine:
    """One fitted configuration. Held in Streamlit's resource cache."""

    cohort: object
    propensity: object
    system: object
    models: dict
    truth: float
    naive: object
    aipw: object
    index: object


@st.cache_resource(show_spinner=False)
def build_engine(n_patients: int, scenario: str, seed: int, learner: str) -> Engine:
    """Generate a cohort, fit everything, wire up the CDSS.

    Cached on the four arguments, which is why the patient sliders are instant:
    changing eGFR does not change any of them, so nothing is refitted — the app
    just calls `.effect()` on an already-fitted model.
    """
    cohort = data.generate_cohort(n_patients, scenario=scenario, seed=seed)
    propensity = estimators.estimate_propensity(cohort.X, cohort.T, cross_fit=True)

    models = {
        name: fn(cohort.X, cohort.T, cohort.Y)
        for name, fn in estimators.ALL_CATE_LEARNERS.items()
    }
    index = rag_lite.build_index()
    system = cdss.DiaCausalCDSS(cohort, cate_model=models[learner], index=index)

    return Engine(
        cohort=cohort,
        propensity=propensity,
        system=system,
        models=models,
        truth=float(cohort.true_cate.mean()),
        naive=estimators.naive_difference(cohort.Y, cohort.T),
        aipw=estimators.aipw_ate(cohort.X, cohort.T, cohort.Y, cross_fit=True),
        index=index,
    )


@st.cache_resource(show_spinner=False)
def ate_table(n_patients: int, scenario: str, seed: int):
    """Every ATE estimator, graded. Returns (leaderboard, estimates).

    `cache_resource` rather than `cache_data` because the returned
    `EffectEstimate` objects carry fitted models in their `notes` — a data cache
    would have to pickle them, which is both slow and fragile.
    """
    cohort = data.generate_cohort(n_patients, scenario=scenario, seed=seed)
    prop = estimators.estimate_propensity(cohort.X, cohort.T, cross_fit=True)
    ests = [
        estimators.naive_difference(cohort.Y, cohort.T),
        estimators.stratified_effect(cohort.X, cohort.T, cohort.Y,
                                     n_strata=10, propensity=prop.scores),
        # n_bootstrap=0 deliberately: the bootstrap costs ~40s and the standard
        # error is not what this tab is showing.
        estimators.g_computation(cohort.X, cohort.T, cohort.Y, n_bootstrap=0),
        estimators.ipw_ate(cohort.Y, cohort.T, prop.scores, stabilise=True),
        estimators.aipw_ate(cohort.X, cohort.T, cohort.Y, cross_fit=True),
    ]
    return evaluate.leaderboard(ests, float(cohort.true_cate.mean())), ests


@st.cache_data(show_spinner=False)
def scenario_table(n_patients: int, seed: int) -> pd.DataFrame:
    return data.scenario_comparison(n_patients, seed=seed)


@st.cache_data(show_spinner=False)
def crosscheck_cached(n_patients: int, scenario: str, seed: int) -> pd.DataFrame:
    cohort = data.generate_cohort(n_patients, scenario=scenario, seed=seed)
    return crosscheck.crosscheck_table(cohort)


@st.cache_data(show_spinner=False)
def refutation_cached(n_patients: int, scenario: str, seed: int) -> str:
    cohort = data.generate_cohort(n_patients, scenario=scenario, seed=seed)
    return crosscheck.refutation_report(cohort)


def figure(draw, **kwargs):
    """Render one matplotlib figure into Streamlit and release it.

    Streamlit reruns the whole script on every widget change, so a figure that is
    not closed leaks on each interaction until matplotlib starts warning.
    """
    fig, ax = plt.subplots(**kwargs)
    draw(ax)
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)


# ═════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═════════════════════════════════════════════════════════════════════════════

def sidebar() -> dict:
    st.sidebar.title("DiaCausal")
    st.sidebar.caption("Type-2 diabetes CDSS · RAG + Causal Inference")

    st.sidebar.header("1 · The world")
    st.sidebar.caption(
        "How strongly did clinical severity drive prescribing? The drug's TRUE "
        "effect is identical in all four — only the difficulty of measuring it changes."
    )
    scenario = st.sidebar.selectbox(
        "Confounding scenario", list(data.SCENARIOS.keys()),
        index=list(data.SCENARIOS.keys()).index("strong"),
    )
    st.sidebar.info(SCENARIO_BLURB[scenario])

    with st.sidebar.expander("cohort settings"):
        n_patients = st.select_slider("patients", [1000, 2000, 4000, 6000], value=4000)
        seed = st.number_input("random seed", 0, 9999, 7, step=1)
        learner = st.selectbox(
            "CATE learner", list(estimators.ALL_CATE_LEARNERS.keys()),
            index=list(estimators.ALL_CATE_LEARNERS.keys()).index("X-learner"),
        )

    st.sidebar.header("2 · The patient")
    st.sidebar.caption(
        "Drag eGFR from 90 down to 40. The recommendation flips — because the "
        "true effect crosses zero near eGFR 55. The population average never moves."
    )

    preset = st.sidebar.selectbox(
        "load a demo patient", ["— custom —"] + list(cdss.DEMO_PATIENTS.keys())
    )
    if preset != "— custom —":
        spec = cdss.DEMO_PATIENTS[preset]
        defaults = {k: v for k, v in spec.items() if k != "story"}
        st.sidebar.caption(spec["story"].strip().split("\n")[0])
    else:
        defaults = {"age": 58, "bmi": 32.0, "baseline_hba1c": 8.5,
                    "egfr": 75.0, "has_cvd": 0, "has_ckd": 0}

    patient = {
        "age": st.sidebar.slider("age (years)", 30, 90, int(defaults["age"])),
        "bmi": st.sidebar.slider("BMI (kg/m²)", 20.0, 48.0,
                                 float(defaults["bmi"]), 0.5),
        "baseline_hba1c": st.sidebar.slider("baseline HbA1c (%)", 6.0, 13.0,
                                            float(defaults["baseline_hba1c"]), 0.1),
        "egfr": st.sidebar.slider("eGFR (mL/min/1.73m²)", 15.0, 120.0,
                                  float(defaults["egfr"]), 1.0),
        "has_cvd": int(st.sidebar.checkbox("established cardiovascular disease",
                                           bool(defaults["has_cvd"]))),
        "has_ckd": int(st.sidebar.checkbox("chronic kidney disease",
                                           bool(defaults["has_ckd"]))),
    }

    st.sidebar.divider()
    st.sidebar.caption(
        "Synthetic data, student project. Not a clinical tool and not for use "
        "with any real patient."
    )
    return {"scenario": scenario, "n_patients": int(n_patients), "seed": int(seed),
            "learner": learner, "patient": patient}


# ═════════════════════════════════════════════════════════════════════════════
# HEADLINE — the sign flip, always on screen
# ═════════════════════════════════════════════════════════════════════════════

def headline(eng: Engine, cfg: dict) -> None:
    st.subheader("The population answer, three ways")
    c1, c2, c3, c4 = st.columns(4)

    c1.metric("TRUE effect", f"{eng.truth:+.3f}",
              help="Known because we authored it. Impossible with real data.")
    c2.metric("Correlation says", f"{eng.naive.value:+.3f}",
              delta=f"{eng.naive.value - eng.truth:+.3f} error",
              delta_color="inverse",
              help="Naive difference in group means. No adjustment.")
    c3.metric("Causal inference says", f"{eng.aipw.value:+.3f}",
              delta=f"{eng.aipw.value - eng.truth:+.3f} error",
              delta_color="inverse",
              help="AIPW, doubly robust, hand-written NumPy.")
    c4.metric("Patients HARMED", f"{(eng.cohort.true_cate < 0).mean():.1%}",
              help="Fraction for whom the drug is genuinely worse — so the "
                   "population average is the wrong advice for them.")

    if np.sign(eng.naive.value) != np.sign(eng.truth):
        st.error(
            f"**SIGN FLIP.** Correlation says {eng.naive.value:+.2f} — the drug appears "
            f"to HARM. The truth is {eng.truth:+.2f}: it helps. Causal inference recovers "
            f"{eng.aipw.value:+.2f}. A CDSS built on correlation would withhold an "
            "effective drug from every patient who could benefit."
        )
    elif abs(eng.aipw.value - eng.truth) > 0.5:
        st.warning(
            f"**The causal estimate is wrong too** ({eng.aipw.value:+.2f} vs truth "
            f"{eng.truth:+.2f}). This scenario hides a confounder that was never recorded, "
            "so no adjustment can reach it. This is the honest limit of the method — see "
            "the Diagnostics tab for the E-value that flags it."
        )
    elif cfg["scenario"] == "rct":
        st.success(
            "**Under randomisation the naive answer is correct.** That is precisely why "
            "RCTs are the gold standard — and why observational data needs everything else "
            "in this app."
        )


# ═════════════════════════════════════════════════════════════════════════════
# TAB 1 — the patient card
# ═════════════════════════════════════════════════════════════════════════════

def tab_patient(eng: Engine, cfg: dict) -> None:
    patient = cfg["patient"]
    rec = eng.system.recommend(patient)
    true_effect = float(data.authored_cate(patient["bmi"], patient["egfr"]))

    st.subheader("Individual estimate vs the population average")
    c1, c2, c3 = st.columns(3)
    c1.metric("population average", f"{eng.aipw.value:+.3f}",
              help="What a tool with no personalisation would tell you.")
    c2.metric(f"THIS patient ({eng.system.cate_model.name})", f"{rec.cate:+.3f}",
              delta=f"{rec.cate - eng.aipw.value:+.3f} vs average")
    c3.metric("TRUE effect for this patient", f"{true_effect:+.3f}",
              delta=f"{rec.cate - true_effect:+.3f} model error",
              delta_color="inverse",
              help="Only knowable because the cohort is synthetic. This is the "
                   "grading nobody with real data can do.")

    if np.sign(rec.cate) != np.sign(eng.aipw.value) and abs(true_effect) > 0.2:
        st.error(
            f"**This is a patient the population average gets wrong.** The average says "
            f"{eng.aipw.value:+.2f} (prescribe). For this patient the model says "
            f"{rec.cate:+.2f}, and the truth is {true_effect:+.2f}."
        )

    st.divider()
    left, right = st.columns([3, 2])

    with left:
        st.subheader("Recommendation card")
        st.caption(
            "Safety block first, deliberately: a clinician should hit the "
            "contraindication before they read the number."
        )
        st.code(cdss.format_card(rec), language=None)

    with right:
        st.subheader("Safety layer")
        status = rec.guard.status
        if rec.guard.vetoed:
            st.error(f"**{status}**")
        elif rec.guard.severity == guardrails.Severity.WARNING:
            st.warning(f"**{status}**")
        elif rec.guard.severity == guardrails.Severity.CAUTION:
            st.info(f"**{status}**")
        else:
            st.success(f"**{status}**")

        st.caption("The model may RECOMMEND. Only the guardrails may FORBID.")

        if not rec.guard.flags:
            st.write("No safety rule triggered.")
        for f in rec.guard.flags:
            with st.expander(
                f"{guardrails.SEVERITY_LABEL[f.severity]} — {f.rule}",
                expanded=f.severity >= guardrails.Severity.WARNING,
            ):
                st.write(f.message)
                st.caption(f"source: {f.source}")

        st.subheader("Questions this patient raises")
        st.caption(
            "Built from the patient's own features, not fixed. A fixed query would "
            "return the same passages for everyone, which makes citations decoration."
        )
        for q in rec.questions:
            st.markdown(f"- {q}")

    st.divider()
    st.subheader("Guideline evidence retrieved for this patient")
    st.caption(
        "Real TF-IDF retrieval over the PDFs in `RAG/`. Passages marked "
        "`[curated]` come from hand-written, page-cited paraphrases of the two "
        "documents whose text cannot be extracted — never silently mixed with "
        "extracted text."
    )
    if not rec.citations:
        st.write("No passage cleared the relevance threshold.")
    for hit in rec.citations:
        with st.expander(f"{hit.chunk.citation}   ·   cosine {hit.score:.3f}"):
            st.write(hit.chunk.text)

    with st.expander("the three-way contrast: RAG alone / causal alone / both"):
        st.code(cdss.three_way_contrast(
            eng.system, patient,
            f"{patient['age']:.0f}y, BMI {patient['bmi']:.0f}, "
            f"HbA1c {patient['baseline_hba1c']:.1f}%, eGFR {patient['egfr']:.0f}"),
            language=None)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 2 — the DAG
# ═════════════════════════════════════════════════════════════════════════════

def tab_dag(eng: Engine) -> None:
    st.subheader("Assumptions, drawn before anything was computed")
    st.markdown(
        "A **backdoor path** is any path from treatment to outcome starting with an "
        "arrow *into* the treatment. Those are the leaks. Block every one and what "
        "remains is causal."
    )
    graph = dag.build_graph()
    figure(lambda ax: dag.draw_dag(graph, ax=ax), figsize=(12, 7))

    st.subheader("What to adjust for — and what not to")
    st.dataframe(dag.explain_adjustment(graph), use_container_width=True,
                 hide_index=True)

    st.info(
        "**Adjusting for a COLLIDER manufactures an association that does not exist. "
        "Adjusting for a MEDIATOR erases one that does.** From the outside both look "
        "exactly like *controlling for more variables* — which is why 'adjust for "
        "everything' is not a rule."
    )

    st.subheader("The two mistakes, measured")
    st.caption("Not defined — demonstrated, on a cohort where we know the right answer.")
    st.dataframe(dag.structural_mistakes_table(eng.cohort).round(4),
                 use_container_width=True, hide_index=True)

    for demo in (dag.demo_collider_bias(eng.cohort),
                 dag.demo_over_adjustment(eng.cohort),
                 dag.demo_confounder_omission(eng.cohort)):
        with st.expander(demo.name):
            a, b, c = st.columns(3)
            a.metric("done right", f"{demo.correct:+.4f}")
            b.metric("done wrong", f"{demo.mistaken:+.4f}",
                     delta=f"{demo.damage:+.4f} damage", delta_color="inverse")
            c.metric("truth", f"{demo.truth:+.4f}")
            st.write(demo.explanation)

    with st.expander("backdoor paths, enumerated in code"):
        st.code(dag.path_report(graph), language=None)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 3 — diagnostics
# ═════════════════════════════════════════════════════════════════════════════

def tab_diagnostics(eng: Engine) -> None:
    cohort, prop = eng.cohort, eng.propensity

    st.subheader("1 · Positivity — are you allowed to answer at all?")
    st.markdown(
        r"Every patient must have had a genuine chance of either drug: "
        r"$0 < P(T{=}1 \mid X) < 1$. If some kind of patient *always* got the drug, "
        r"there is no untreated comparison for them — not a hard comparison, an "
        r"**impossible** one."
    )
    rep = diagnostics.overlap_report(prop.scores, cohort.T)
    c1, c2, c3 = st.columns(3)
    c1.metric("verdict", rep.verdict)
    c2.metric("effective sample size", f"{rep.effective_sample_size:.0f}",
              delta=f"of {len(cohort.T)}", delta_color="off",
              help="Weighting costs you precision. This is how many patients' worth "
                   "of information survives it.")
    c3.metric("largest single weight", f"{rep.max_weight:.1f}",
              help="One patient with a propensity of 0.02 carries a weight of 50 and "
                   "can swing the whole estimate alone.")
    st.caption(rep.detail)
    figure(lambda ax: diagnostics.plot_overlap(prop.scores, cohort.T, ax=ax),
           figsize=(10, 4.5))

    st.divider()
    st.subheader("2 · Balance — did the weighting actually work?")
    st.markdown(
        r"$\mathrm{SMD} = \dfrac{\bar{x}_{T=1} - \bar{x}_{T=0}}"
        r"{\sqrt{(s_1^2 + s_0^2)/2}}$ — convention is $|\mathrm{SMD}| < 0.1$."
    )
    weights = np.where(cohort.T == 1, 1 / prop.scores, 1 / (1 - prop.scores))
    bal = diagnostics.balance_table(cohort.X, cohort.T, data.COVARIATES,
                                    weights=weights)
    c1, c2 = st.columns(2)
    c1.metric("imbalanced before weighting",
              f"{(bal['SMD before'].abs() > 0.1).sum()} of {len(bal)}")
    c2.metric("imbalanced after weighting",
              f"{(bal['SMD after'].abs() > 0.1).sum()} of {len(bal)}")
    figure(lambda ax: diagnostics.plot_love(bal, ax=ax), figsize=(8, 4.5))
    st.dataframe(bal.round(4), use_container_width=True, hide_index=True)
    st.caption(
        "The most persuasive diagnostic in the project: the adjustment doing its job, "
        "variable by variable."
    )

    st.divider()
    st.subheader("3 · Ignorability — untestable, so quantify the vulnerability")
    st.markdown(
        "You cannot test for a confounder you did not measure. What you *can* do is "
        "ask how strong one would have to be to overturn the result — the **E-value** "
        "(VanderWeele & Ding, 2017)."
    )
    lo, hi = eng.aipw.ci
    ev = diagnostics.e_value(eng.aipw.value, ci_low=lo,
                             sd=float(eng.cohort.Y.std()))
    c1, c2, c3 = st.columns(3)
    c1.metric("AIPW estimate", f"{eng.aipw.value:+.4f}",
              delta=f"95% CI [{lo:+.3f}, {hi:+.3f}]", delta_color="off")
    c2.metric("E-value (point)", f"{ev.e_value:.2f}")
    c3.metric("E-value (CI bound)", f"{ev.e_value_ci:.2f}")
    st.info(ev.interpretation)

    with st.expander("check the E-value against a confounder we planted ourselves"):
        st.caption(
            "The move only a synthetic study can make: compare the sensitivity "
            "analysis's warning against the real hidden confounder's actual strength."
        )
        hidden = data.generate_cohort(len(cohort.T), scenario="hidden_confounder",
                                      seed=7)
        st.code(diagnostics.evalue_verdict(hidden, ev), language=None)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 4 — method leaderboard
# ═════════════════════════════════════════════════════════════════════════════

def tab_methods(eng: Engine, cfg: dict) -> None:
    st.subheader("Every ATE estimator, graded against the answer key")
    st.caption(
        "All hand-written in NumPy. Each method fixes a specific weakness in the "
        "one above it: stratification → g-computation → IPW → AIPW."
    )
    board, ests = ate_table(cfg["n_patients"], cfg["scenario"], cfg["seed"])
    st.dataframe(board.round(4), use_container_width=True, hide_index=True)
    figure(lambda ax: evaluate.plot_leaderboard(ests, eng.truth, ax=ax),
           figsize=(10, 4.5))

    st.divider()
    st.subheader("Average → personal (ATE → CATE)")
    st.markdown(
        r"A clinician cannot prescribe an average. The estimand that matters is "
        r"$\tau(x) = \mathbb{E}[Y_1 - Y_0 \mid X = x]$ — and here it **crosses zero**, "
        r"so the population average is the wrong instruction for a real minority."
    )
    cate_board = evaluate.cate_leaderboard(list(eng.models.values()),
                                          eng.cohort.true_cate)
    st.dataframe(cate_board.round(4), use_container_width=True, hide_index=True)
    st.caption(
        "**Sign agreement** is the most decision-relevant column: the fraction of "
        "patients for whom the model gets *treat vs don't treat* right. **Rank "
        "correlation** matters more than MAE for a CDSS, because a treat-or-not "
        "decision depends on ordering."
    )

    feature = st.radio("recovered effect curve, plotted against",
                       ["egfr", "bmi"], horizontal=True,
                       format_func=lambda f: {"egfr": "eGFR (the zero-crossing)",
                                              "bmi": "BMI"}[f])
    figure(lambda ax: evaluate.plot_cate_recovery(
        list(eng.models.values()), eng.cohort, feature=feature, ax=ax),
        figsize=(10, 5))
    if feature == "egfr":
        st.info(
            "The authored effect has a kink at eGFR 70 and crosses zero near 55 — and "
            "the learners recover both from observational data alone, never having been "
            "told the functional form. That crossing is the boundary between *prescribe* "
            "and *don't*."
        )

    st.divider()
    st.subheader("Does better estimation lead to better decisions?")
    st.caption(
        "Regret = the HbA1c benefit forgone versus an oracle who knows every true "
        "individual effect. Look at `treat everyone` — that is the policy a "
        "population-average tool implies."
    )
    st.dataframe(evaluate.policy_comparison(list(eng.models.values()),
                                            eng.cohort).round(4),
                 use_container_width=True, hide_index=True)

    figure(lambda ax: evaluate.plot_decision_curve(
        eng.system.cate_model, eng.cohort, ax=ax), figsize=(10, 5))

    st.divider()
    st.subheader("Predictive ML vs causal inference, same drug budget")
    st.markdown(
        "Give a standard risk model and our causal model the **same fixed budget** and "
        "let each pick who gets treated. The predictive model ranks by expected "
        "**risk**; the causal model ranks by expected **benefit**. They are not the "
        "same ranking, and the difference is the argument for this project."
    )
    budget = st.slider("fraction of patients who can be treated", 0.05, 0.60, 0.30, 0.05)
    st.code(evaluate.format_predictive_vs_causal(
        evaluate.predictive_vs_causal(eng.cohort, eng.system.cate_model,
                                      budget_fraction=budget)), language=None)
    st.warning(
        "At tight budgets the risk-ranking policy can have **negative** value — it "
        "harms patients on net. The risk model is not broken; its R² is excellent. It "
        "answers a different question, and the sickest patients are the low-eGFR "
        "patients, which is exactly what stops this drug working."
    )


# ═════════════════════════════════════════════════════════════════════════════
# TAB 5 — cross-check
# ═════════════════════════════════════════════════════════════════════════════

def tab_crosscheck(cfg: dict) -> None:
    st.subheader("Is the hand-written code actually right?")
    st.markdown(
        "Writing an estimator by hand is only impressive if it is also **correct**. "
        "Each row below puts our from-scratch NumPy implementation beside the *same "
        "estimator* from DoWhy or EconML, and beside the truth."
    )
    if st.button("run the library cross-check", type="primary"):
        with st.spinner("fitting DoWhy and EconML estimators…"):
            table = crosscheck_cached(cfg["n_patients"], cfg["scenario"], cfg["seed"])
        st.dataframe(table.round(4), use_container_width=True, hide_index=True)
        st.caption(
            "`LinearDML` is held to a looser tolerance and labelled as such: it is a "
            "different estimator with a partially linear structural assumption, not a "
            "reimplementation of AIPW. Scoring it as a failure would be a category "
            "error; quietly widening every tolerance so it passes would be worse."
        )
        st.success(
            "\"My 12-line IPW function agrees with DoWhy's to four decimal places\" is "
            "a better sentence than \"I called DoWhy.\""
        )

    st.divider()
    st.subheader("Refutation — try to break our own result")
    st.markdown(
        "| test | what it does | a pass means |\n"
        "|---|---|---|\n"
        "| placebo treatment | replace treatment with a coin flip | the pipeline is not "
        "manufacturing effects from noise |\n"
        "| random common cause | add an irrelevant covariate | the estimate is not "
        "driven by junk |\n"
        "| subset refuter | re-estimate on random 80% subsets | the answer is not one "
        "fragile subgroup |\n"
    )
    st.warning(
        "**Read the asymmetry.** Passing these does not prove the answer is right. "
        "Failing any of them proves it is wrong. A smoke detector, not a certificate."
    )
    if st.button("run refutation tests (~30s)"):
        with st.spinner("re-estimating under placebo, junk covariates and subsets…"):
            st.code(refutation_cached(cfg["n_patients"], cfg["scenario"], cfg["seed"]),
                    language=None)

    st.divider()
    st.subheader("How much hidden confounding would it take to break the result?")
    if st.button("inject confounders of known strength"):
        with st.spinner("simulating unobserved confounding…"):
            cohort = data.generate_cohort(cfg["n_patients"], scenario=cfg["scenario"],
                                          seed=cfg["seed"])
            st.dataframe(crosscheck.unobserved_confounder_test(cohort).round(4),
                         use_container_width=True, hide_index=True)
        st.info(
            "Stating *where* the boundary is beats claiming there isn't one."
        )


# ═════════════════════════════════════════════════════════════════════════════
# TAB 6 — the evidence base
# ═════════════════════════════════════════════════════════════════════════════

def tab_evidence(eng: Engine) -> None:
    st.subheader("Retrieval over the guideline PDFs")
    st.markdown(
        "No vector database, no embedding API, **no PDF library** — none are installed "
        "and `pip` is unavailable here. The PDFs are parsed directly: find the "
        "compressed content streams, `zlib.decompress` them, and pull text out of the "
        "`Tj` / `TJ` operators. Then chunk → TF-IDF → cosine top-k, with page-number "
        "citations."
    )
    st.code(eng.index.summary(), language=None)
    st.dataframe(rag_lite.provenance_table(eng.index), use_container_width=True,
                 hide_index=True)

    st.error(
        "**Two of the four documents cannot be read.** One uses CID/Identity-H fonts, "
        "where the stream bytes are glyph indexes needing a ToUnicode table we do not "
        "parse. One is a scan with no text layer at all. Those two are served from "
        "curated, page-cited paraphrases, marked `[curated]` in every citation. A "
        "retrieval system that failed *silently* on half its corpus would be far worse "
        "than one that says so out loud."
    )

    st.divider()
    st.subheader("Search the guidelines yourself")
    query = st.text_input("query", "SGLT2 inhibitor eGFR renal impairment")
    k = st.slider("passages to return", 1, 8, 3)
    if query.strip():
        hits = eng.index.retrieve(query, k=k)
        if not hits:
            st.write("Nothing cleared the relevance threshold.")
        for hit in hits:
            with st.expander(f"{hit.chunk.citation}   ·   cosine {hit.score:.3f}"):
                st.write(hit.chunk.text)

        with st.expander("what the retriever is actually matching on"):
            st.caption(
                "TF-IDF is inspectable in a way embeddings are not — a genuine "
                "advantage for a system that has to be audited."
            )
            st.code(eng.index.explain_query(query), language=None)

    st.divider()
    st.subheader("Known limitations of the retrieval half")
    for i, lim in enumerate(rag_lite.KNOWN_LIMITATIONS, 1):
        st.markdown(f"{i}. {lim}")

    st.divider()
    st.subheader("The safety rule set")
    st.caption(
        "Some rules are not statistical claims at all. *Metformin is contraindicated "
        "below eGFR 30* is about lactic acidosis — a rare event no 4,000-patient effect "
        "model would learn, and should never be trusted to weigh."
    )
    st.dataframe(guardrails.rules_table(), use_container_width=True, hide_index=True)


# ═════════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════════

def main() -> None:
    st.set_page_config(page_title="DiaCausal — Causal CDSS for Type-2 Diabetes",
                       page_icon="🩺", layout="wide")
    cfg = sidebar()

    st.title("DiaCausal — a causal CDSS for Type-2 diabetes")
    st.caption(
        "SGLT2 inhibitor vs metformin · every estimator hand-written in NumPy and "
        "graded against a known answer key · guideline citations retrieved live from "
        "the PDFs in `RAG/`"
    )

    with st.spinner("generating cohort and fitting estimators…"):
        eng = build_engine(cfg["n_patients"], cfg["scenario"], cfg["seed"],
                           cfg["learner"])

    headline(eng, cfg)
    st.divider()

    tabs = st.tabs(["🩺 Patient card", "🕸 The DAG", "🔍 Diagnostics",
                    "🏁 Methods", "✅ Cross-check", "📚 Evidence base"])
    with tabs[0]:
        tab_patient(eng, cfg)
    with tabs[1]:
        tab_dag(eng)
    with tabs[2]:
        tab_diagnostics(eng)
    with tabs[3]:
        tab_methods(eng, cfg)
    with tabs[4]:
        tab_crosscheck(cfg)
    with tabs[5]:
        tab_evidence(eng)


# Streamlit executes the script with __name__ == "__main__", so this guard runs
# the app there while still allowing a smoke test to import the module.
if __name__ == "__main__":
    main()
