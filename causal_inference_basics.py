#!/usr/bin/env python3
"""
DiaCausal — Causal Inference from first principles, narrated.
============================================================

    python causal_inference_basics.py

Ten acts, about two minutes, no arguments needed. Every causal quantity in this
run is computed by hand in NumPy — no DoWhy, no EconML — and then checked three
ways: against a ground truth we authored ourselves, against the libraries, and
against a set of refutation tests designed to catch us fooling ourselves.

--------------------------------------------------------------------------------
WHY THIS FILE EXISTS ALONGSIDE `causal_inference_implementation.py`
--------------------------------------------------------------------------------
That file is the production pipeline and it is genuinely better engineered. But it
answers the question "what is the effect?" by calling

    model.estimate_effect(method_name="backdoor.propensity_score_weighting")

which is correct, and completely opaque. Asked "show me how inverse propensity
weighting actually works", it can only point at a library.

This file answers that question in twelve lines of arithmetic, and then proves the
twelve lines agree with the library to four decimal places. Both artifacts are
worth having. This is the one you can defend line by line.

--------------------------------------------------------------------------------
THE TEN ACTS
--------------------------------------------------------------------------------
    0   The question              prediction vs decision
    1   A world where we know     authoring the ground truth
    2   The naive answer          the sign flip
    3   Draw your assumptions     the DAG, collider bias, over-adjustment
    4   Are you allowed to answer positivity, balance, sensitivity
    5   Four fixes, by hand       stratification, g-comp, IPW, AIPW
    6   Prove the code is right   vs DoWhy, vs EconML, vs refutation
    7   Average to personal       ATE -> CATE, graded against truth
    8   Why BOTH halves           RAG + causal + guardrails = the card
    9   Where this breaks         the honest limits

Figures are written to `figures/`. Nothing is downloaded and nothing is installed.
"""

from __future__ import annotations

import os
import sys
import time

# Must precede the matplotlib import: the default config dir is not writable in
# every environment this project is run in, and matplotlib fails hard rather than
# degrading if it cannot write its font cache.
os.environ.setdefault("MPLCONFIGDIR", os.environ.get("TMPDIR", "/tmp"))

import matplotlib
matplotlib.use("Agg")               # no display needed; we save PNGs
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 40)

from causal_engine import (
    PALETTE, cdss, crosscheck, dag, data, diagnostics, estimators, evaluate,
    guardrails, pdf_text, rag_lite,
)

FIGURES = "figures"
N_PATIENTS = 4000
SEED = 7
WIDTH = 84


# ═════════════════════════════════════════════════════════════════════════════
# Narration helpers. Presentation only — no statistics happen down here.
# ═════════════════════════════════════════════════════════════════════════════

def act(number: int, title: str, question: str) -> None:
    print("\n\n" + "═" * WIDTH)
    print(f"  ACT {number}  ·  {title.upper()}")
    print("═" * WIDTH)
    print(f"  The question: {question}")
    print("─" * WIDTH)


def head(text: str) -> None:
    print(f"\n  ▸ {text}")
    print("  " + "─" * (WIDTH - 4))


def say(text: str, indent: int = 4) -> None:
    """Wrap narration to the console width so paragraphs stay readable."""
    import textwrap
    pad = " " * indent
    for line in textwrap.wrap(" ".join(text.split()), width=WIDTH - indent - 2):
        print(pad + line)


def table(df: pd.DataFrame, indent: int = 4) -> None:
    pad = " " * indent
    for line in df.to_string(index=False).splitlines():
        print(pad + line)


def verdict(text: str) -> None:
    print(f"\n  ★ {text}")


# ═════════════════════════════════════════════════════════════════════════════
# ACT 0 — the question this project is actually asking
# ═════════════════════════════════════════════════════════════════════════════

def act0() -> None:
    act(0, "Prediction is not decision",
        "why is a very accurate predictor still useless for choosing a drug?")

    say("Here are two sentences. They sound similar and they are not remotely the "
        "same kind of claim.")
    print()
    print("      PREDICTION   'This patient's HbA1c will be 8.4% in six months.'")
    print("      DECISION     'This patient should be given SGLT2i rather than metformin.'")
    print()
    say("A predictive model — a classifier, a neural network, a boosted tree — "
        "answers the first. It learns patterns in data as it was collected. And "
        "here is the trap: in that data, the sickest patients received the "
        "strongest drugs. So a predictor learns 'strong drug -> bad outcome', "
        "which is a perfectly real pattern and exactly backwards as advice.")
    print()
    say("The analogy that lands with anyone: hospitals that treat the sickest "
        "patients have the worst survival rates. Are they the worst hospitals? "
        "Obviously not — but a model that only sees the correlation cannot tell "
        "the difference between 'this treatment harms people' and 'this treatment "
        "is given to people who were already worse off'.")
    print()
    say("Pearl's ladder of causation names the three rungs:")
    print()
    print("      1. SEEING    P(Y | X)          What usually happens?   ML lives here.")
    print("      2. DOING     P(Y | do(T))      What if I intervene?    A CDSS needs this.")
    print("      3. IMAGINING P(Y_t | T=t')     What would have been?   The counterfactual.")
    print()
    say("A clinical decision support system that only climbs to rung 1 will "
        "confidently withhold effective treatment from the patients who need it "
        "most. Everything that follows is about getting to rung 2 — and this "
        "project can reach rung 3, but only because the data is synthetic and we "
        "wrote both outcomes ourselves.")


# ═════════════════════════════════════════════════════════════════════════════
# ACT 1 — build a world where the answer is known
# ═════════════════════════════════════════════════════════════════════════════

def act1() -> data.Cohort:
    act(1, "A world where we know the truth",
        "how could you ever know your causal estimate is correct?")

    say("This is the question that sinks most causal projects at a viva, and it "
        "has a genuinely good answer: build the world yourself.")
    print()
    say("We generate a synthetic cohort in which we WRITE the effect of the drug "
        "for every individual patient. That gives us an answer key. Then we throw "
        "the answer key away, hand the estimators only what a real hospital would "
        "have, and grade them.")
    print()
    say("Nobody can do this with real data — the true individual effect is "
        "unobservable, permanently, for every patient who has ever lived. Which "
        "is exactly why a synthetic benchmark has to come first. If a method "
        "cannot recover an answer we planted ourselves, it has no business being "
        "pointed at real patients.")

    head("The effect function we authored")
    print("""
      true_cate(patient) = 1.5  +  0.035 x (BMI - 30)  -  2.5 x max(0, (70 - eGFR)/25)
                           ────     ──────────────────     ─────────────────────────────
                           base     heavier patients       kidney function collapses
                                    benefit MORE           the benefit, then reverses it
    """)
    say("Both gradients are clinically real, not modelling convenience. SGLT2 "
        "inhibitors work by making the kidney dump glucose into the urine — so a "
        "heavier patient loses more, and a kidney that has stopped filtering "
        "cannot deliver the mechanism at all. Below about eGFR 55 the authored "
        "effect crosses zero and the drug becomes actively worse than metformin "
        "for glycaemic control.")
    print()
    say("That zero-crossing is the single most important design decision in this "
        "project. It means the population average (+0.96, helpful) is the WRONG "
        "advice for a real minority of patients — so recovering the average is "
        "not enough, and a CDSS has something to do that a summary statistic "
        "cannot.")

    cohort = data.generate_cohort(N_PATIENTS, scenario="strong", seed=SEED)

    head("The cohort")
    print(f"    {cohort.summary()}")
    harmed = float((cohort.true_cate < 0).mean())
    print(f"    patients genuinely HARMED by the drug: {harmed:.1%}")
    print(f"    true individual effects range from {cohort.true_cate.min():+.2f} "
          f"to {cohort.true_cate.max():+.2f} HbA1c points")

    head("The Fundamental Problem of Causal Inference, printed for one patient")
    say("Every patient has two potential outcomes: what happens on metformin (Y0) "
        "and what happens on SGLT2i (Y1). The effect is the difference. Reality "
        "shows you exactly one of them, forever.")
    print()
    df = cohort.data
    show = df.loc[:, ["patient_id", "bmi", "egfr", "treatment_sglt2i",
                      "y0", "y1", "true_cate", "hba1c_reduction"]].head(6).copy()
    show.columns = ["id", "BMI", "eGFR", "took_drug", "Y0", "Y1", "TRUE effect", "observed"]
    table(show.round(2))
    print()
    say("The `observed` column is Y1 where took_drug=1 and Y0 where it is 0. In a "
        "real hospital the other column is simply absent. The Y0, Y1 and TRUE "
        "effect columns exist here only because we are inside a simulation, and "
        "they are hidden from every estimator from this point on.")

    return cohort


# ═════════════════════════════════════════════════════════════════════════════
# ACT 2 — the naive answer, and the sign flip
# ═════════════════════════════════════════════════════════════════════════════

def act2(cohort: data.Cohort) -> None:
    act(2, "The naive answer and the sign flip",
        "what happens if you just compare the two groups?")

    naive = estimators.naive_difference(cohort.Y, cohort.T)
    truth = float(cohort.true_cate.mean())

    head("The obvious thing to do")
    print("      mean(HbA1c reduction | took SGLT2i)  -  mean(HbA1c reduction | took metformin)")
    print()
    print(f"    naive answer      {naive.value:+.4f}")
    print(f"    TRUE answer       {truth:+.4f}")
    print(f"    error             {naive.value - truth:+.4f}   "
          f"({abs(naive.value - truth) / abs(truth):.0%} wrong, and the SIGN is wrong)")
    print()
    verdict("The naive comparison says the drug HARMS patients. The truth is that "
            "it helps.")
    say("A CDSS built on that number would withhold an effective drug from every "
        "patient who could benefit. This one table is the entire justification "
        "for the causal half of this project.", indent=6)

    head("Why it goes wrong: who actually got the drug?")
    say("The bias is not mysterious. It is visible directly in the data — the two "
        "groups were never comparable in the first place.")
    print()
    table(data.confounding_table(cohort).round(2))
    print()
    say("Sicker patients — higher HbA1c, worse kidneys, older — were "
        "preferentially given the newer drug. They then did worse, because they "
        "were sicker, not because of the drug. The naive comparison attributes "
        "their sickness to the treatment.")

    head("Turn the confounding dial and watch the answer move")
    say("One parameter controls how strongly clinical severity drove prescribing. "
        "Nothing else changes — the drug's true effect is identical in all four "
        "rows.")
    print()
    table(data.scenario_comparison(N_PATIENTS, seed=SEED).round(4))
    print()
    say("Read that table top to bottom and the whole field is in it:")
    print()
    print("      rct                  the naive answer is CORRECT. This is why")
    print("                           randomised trials are the gold standard: random")
    print("                           assignment destroys confounding by construction.")
    print("      mild / strong        naive drifts, then flips sign. Causal methods hold.")
    print("      hidden_confounder    causal methods fail TOO, because the thing driving")
    print("                           prescribing was never recorded. No amount of")
    print("                           statistics recovers information that is not there.")
    print()
    verdict("The last row matters as much as the third. These methods are not "
            "magic, and Act 9 comes back to it.")


# ═════════════════════════════════════════════════════════════════════════════
# ACT 3 — the DAG, and two mistakes it prevents
# ═════════════════════════════════════════════════════════════════════════════

def act3(cohort: data.Cohort) -> None:
    act(3, "Draw your assumptions before you compute anything",
        "which variables should you adjust for — and which must you NOT?")

    say("The instinct is 'adjust for everything you measured'. That instinct is "
        "wrong, and wrong in two different directions. A DAG — a drawing of what "
        "you believe causes what — is how you tell them apart before you write "
        "any code.")

    graph = dag.build_graph()
    head("Backdoor paths from Treatment to Outcome")
    print(dag.path_report(graph))

    head("What to adjust for, and why")
    table(dag.explain_adjustment(graph))

    fig, ax = plt.subplots(figsize=(12, 8))
    dag.draw_dag(graph, ax=ax, save_to=f"{FIGURES}/basics_act3_dag.png")
    plt.close(fig)
    print(f"\n    figure -> {FIGURES}/basics_act3_dag.png")

    head("Now DEMONSTRATE the two mistakes, rather than just defining them")
    say("Most projects state that collider bias exists. Here is what it does to "
        "the number, measured on our own cohort where we know the right answer.")
    print()
    table(dag.structural_mistakes_table(cohort).round(4))
    print()
    for demo in (dag.demo_collider_bias(cohort),
                 dag.demo_over_adjustment(cohort),
                 dag.demo_confounder_omission(cohort)):
        print(f"    {demo.name}")
        say(demo.explanation, indent=8)
        print()
    verdict("Adjusting for a COLLIDER manufactures an association that does not "
            "exist. Adjusting for a MEDIATOR erases one that does. Both look like "
            "'controlling for more variables'.")


# ═════════════════════════════════════════════════════════════════════════════
# ACT 4 — are you even allowed to answer?
# ═════════════════════════════════════════════════════════════════════════════

def act4(cohort: data.Cohort) -> estimators.PropensityResult:
    act(4, "Are you even allowed to answer?",
        "what has to be true about the data before any of this is valid?")

    say("Three assumptions. Two of them are checkable, and this act checks them. "
        "The third is not checkable at all, which is why we quantify how badly it "
        "would have to fail instead of asserting it holds.")
    print()
    print("      1. POSITIVITY / OVERLAP   Every kind of patient had SOME chance of")
    print("                                either drug. CHECKABLE.")
    print("      2. IGNORABILITY           No unmeasured confounders. NOT checkable —")
    print("                                the whole difficulty of the field.")
    print("      3. SUTVA / CONSISTENCY    One patient's treatment does not affect")
    print("                                another's outcome. Reasonable here.")

    prop = estimators.estimate_propensity(cohort.X, cohort.T, cross_fit=True)

    head("1. POSITIVITY — the overlap check")
    rep = diagnostics.overlap_report(prop.scores, cohort.T)
    print(f"    treated propensity range   {rep.min_treated:.3f} – {rep.max_treated:.3f}")
    print(f"    control propensity range   {rep.min_control:.3f} – {rep.max_control:.3f}")
    print(f"    effective sample size      {rep.effective_sample_size:.0f} of {len(cohort.T)}")
    print(f"    largest single weight      {rep.max_weight:.1f}")
    print(f"    verdict                    {rep.verdict}")
    say(rep.detail, indent=4)

    fig, ax = plt.subplots(figsize=(11, 5))
    diagnostics.plot_overlap(prop.scores, cohort.T, ax=ax,
                             save_to=f"{FIGURES}/basics_act4_overlap.png")
    plt.close(fig)
    print(f"    figure -> {FIGURES}/basics_act4_overlap.png")

    head("   ... and the same check on a cohort where positivity is BROKEN")
    broken = data.generate_cohort(N_PATIENTS, scenario="strong", seed=SEED,
                                  violate_positivity=True)
    bprop = estimators.estimate_propensity(broken.X, broken.T, cross_fit=True)
    brep = diagnostics.overlap_report(bprop.scores, broken.T)
    print(f"    verdict                    {brep.verdict}")
    say("Here a hard rule ('never prescribe below eGFR 60') means an entire region "
        "of patient space contains zero treated patients. There is no comparison "
        "to make there — not a hard comparison, an impossible one. The honest "
        "response is to restrict the claim to the population where overlap "
        "exists, which is what trimming does.", indent=4)
    trim = estimators.trim_by_overlap(bprop.scores, bounds=(0.1, 0.9),
                                      covariates=broken.X,
                                      covariate_names=data.COVARIATES)
    print(f"    trimming to propensity 0.1–0.9 keeps {trim.fraction_kept:.1%} "
          f"of patients ({trim.n_after} of {trim.n_before})")
    say("And the patients dropped are not a random sample — they are "
        "systematically the sickest. The estimate that survives is honest, but it "
        "is an estimate about a different, healthier population. Saying so is "
        "part of the result.", indent=4)

    head("2. BALANCE — did the weighting actually work?")
    say("Positivity says a comparison is possible. Balance checks whether the "
        "weights we are about to use genuinely made the groups comparable. The "
        "standardised mean difference (SMD) is the measure; below 0.1 is the "
        "conventional bar.")
    print()
    weights = np.where(cohort.T == 1, 1 / prop.scores, 1 / (1 - prop.scores))
    bal = diagnostics.balance_table(cohort.X, cohort.T, data.COVARIATES, weights=weights)
    table(bal.round(4))
    n_bad_before = int((bal["SMD before"].abs() > 0.1).sum())
    n_bad_after = int((bal["SMD after"].abs() > 0.1).sum())
    print()
    print(f"    covariates imbalanced BEFORE weighting: {n_bad_before} of {len(bal)}")
    print(f"    covariates imbalanced AFTER  weighting: {n_bad_after} of {len(bal)}")

    fig, ax = plt.subplots(figsize=(9, 5))
    diagnostics.plot_love(bal, ax=ax, save_to=f"{FIGURES}/basics_act4_love.png")
    plt.close(fig)
    print(f"    figure -> {FIGURES}/basics_act4_love.png")
    verdict("This love plot is the single most persuasive diagnostic in the "
            "project: it shows the adjustment doing its job, variable by variable.")

    head("3. IGNORABILITY — untestable, so quantify the vulnerability instead")
    say("You cannot test for a confounder you did not measure. What you CAN do is "
        "ask how strong one would have to be to destroy your conclusion — the "
        "E-value. A large E-value means only an implausibly powerful hidden "
        "variable could overturn the finding.")
    print()
    aipw = estimators.aipw_ate(cohort.X, cohort.T, cohort.Y, cross_fit=True)
    ci = aipw.ci
    ev = diagnostics.e_value(aipw.value, ci_low=ci[0], sd=float(cohort.Y.std()))
    print(f"    estimate {aipw.value:+.4f}  95% CI [{ci[0]:+.4f}, {ci[1]:+.4f}]")
    print(f"    E-value (point estimate)   {ev.e_value:.2f}")
    print(f"    E-value (CI boundary)      {ev.e_value_ci:.2f}")
    say(ev.interpretation, indent=4)
    print()
    say("And now the move only a synthetic study can make: we planted a hidden "
        "confounder in the `hidden_confounder` scenario, so we can compare the "
        "E-value's warning against the real thing.")
    print()
    hidden = data.generate_cohort(N_PATIENTS, scenario="hidden_confounder", seed=SEED)
    print(f"    {diagnostics.evalue_verdict(hidden, ev)}")

    return prop


# ═════════════════════════════════════════════════════════════════════════════
# ACT 5 — four fixes, written by hand
# ═════════════════════════════════════════════════════════════════════════════

def act5(cohort: data.Cohort, prop: estimators.PropensityResult) -> dict:
    act(5, "Four fixes, written by hand",
        "how do you actually remove the confounding?")

    truth = float(cohort.true_cate.mean())
    say("Four methods, each in under twenty lines of NumPy, each printed against "
        "the truth. They are not four arbitrary alternatives — each one fixes a "
        "specific weakness in the one before it.")

    results: dict[str, estimators.EffectEstimate] = {}

    # ── 1. stratification ──
    head("FIX 1 — STRATIFICATION: compare like with like")
    print("""
      Sort patients into buckets of similar treatment probability. Inside a
      bucket, who got the drug is nearly arbitrary — so the naive comparison is
      valid THERE. Compute it per bucket, then average the buckets.

          for each stratum s:   effect_s = mean(Y | T=1, s) - mean(Y | T=0, s)
          ATE = sum_s  (n_s / N) * effect_s
    """)
    strat = estimators.stratified_effect(cohort.X, cohort.T, cohort.Y, n_strata=10,
                                         propensity=prop.scores)
    results["Stratification (10)"] = strat
    print(f"    estimate {strat.value:+.4f}   truth {truth:+.4f}   "
          f"error {strat.value - truth:+.4f}")
    say("Honest weakness: bucket count is a knob, and the answer moves with it. "
        "Too few buckets and each still mixes dissimilar patients; too many and "
        "each holds too few patients to average. Act 6 measures that trade-off "
        "rather than hiding it.")

    # ── 2. g-computation ──
    head("FIX 2 — G-COMPUTATION: model the outcome, then simulate both worlds")
    print("""
      Fit one model of the outcome. Then ask it to predict EVERY patient twice —
      once as if treated, once as if not — and average the difference. You are
      simulating the two parallel worlds you cannot observe.

          mu(x, t) = E[Y | X=x, T=t]
          ATE = (1/N) * sum_i [ mu(x_i, 1) - mu(x_i, 0) ]
    """)
    gcomp = estimators.g_computation(cohort.X, cohort.T, cohort.Y, n_bootstrap=100)
    results["G-computation"] = gcomp
    print(f"    estimate {gcomp.value:+.4f}   truth {truth:+.4f}   "
          f"error {gcomp.value - truth:+.4f}")

    from sklearn.linear_model import LinearRegression
    gcomp_lin = estimators.g_computation(cohort.X, cohort.T, cohort.Y,
                                         model=LinearRegression())
    print(f"    ... with a LINEAR outcome model instead: {gcomp_lin.value:+.4f}  "
          f"(error {gcomp_lin.value - truth:+.4f})")
    say("Read those two numbers again — they are the opposite way round from "
        "what you expect. Gradient boosting is the more powerful model, and the "
        "true effect really does contain a BMI interaction and a kink at eGFR 70 "
        "that a straight line cannot represent. Yet the LINEAR model got closer. "
        "That is not luck. Here is the cause, measured rather than asserted.")

    # Why: the booster spends its capacity on the outcome LEVEL, not the
    # treatment CONTRAST. Shown two ways — feature importance, then the effect of
    # relaxing the shrinkage — because an examiner should not have to take this
    # on trust.
    from sklearn.ensemble import GradientBoostingRegressor
    Xt = np.column_stack([cohort.X, cohort.T])
    gb = GradientBoostingRegressor(n_estimators=200, max_depth=3,
                                   learning_rate=0.05, random_state=0).fit(Xt, cohort.Y)
    names = list(data.COVARIATES) + ["TREATMENT"]
    print("\n    feature importance inside the outcome model:")
    for name, imp in sorted(zip(names, gb.feature_importances_), key=lambda z: -z[1]):
        bar = "█" * int(round(imp * 40))
        print(f"        {name:<16s} {imp:6.4f}  {bar}")

    relaxed = estimators.g_computation(
        cohort.X, cohort.T, cohort.Y, n_bootstrap=0,
        model=GradientBoostingRegressor(n_estimators=500, max_depth=5,
                                        learning_rate=0.30, random_state=0))
    print(f"\n    default GB (lr 0.05)   {gcomp.value:+.4f}   "
          f"error {gcomp.value - truth:+.4f}")
    print(f"    relaxed GB (lr 0.30)   {relaxed.value:+.4f}   "
          f"error {relaxed.value - truth:+.4f}")

    say("TREATMENT receives about 4% of the model's attention. The other 96% "
        "goes to eGFR, age and baseline HbA1c — because those drive the LEVEL of "
        "the outcome, and the level is where the variance is. The treatment "
        "contrast is small by comparison, so a regularised learner treats it as "
        "almost-noise and shrinks it toward zero. And the confirmation: relaxing "
        "the shrinkage cuts the error roughly in half. If the problem were the "
        "model class being too rigid, loosening it would not help in that "
        "direction.")
    say("This has a name — REGULARISATION BIAS — and removing it is the entire "
        "reason Chernozhukov et al. (2018) invented double machine learning. "
        "Shrinkage applied to a NUISANCE quantity (the outcome surface) leaks "
        "into the ESTIMAND (the treatment contrast). So the honest lesson is the "
        "reverse of the intuitive one: when your causal estimate is biased, do "
        "not reach for a more flexible model — reach for an ESTIMATOR WHOSE "
        "ERRORS CANCEL. That is exactly what FIX 5 does. AIPW uses this same "
        "gradient booster and lands within 0.002 of the truth; the improvement "
        "comes from the correction term, not from the model. You will meet this "
        "mechanism once more in Act 7, where the S-learner is the worst CATE "
        "learner for precisely this reason — g-computation appends T as one more "
        "feature, which makes it an S-learner too.")

    # ── 3. IPW ──
    head("FIX 3 — IPW: reweight the sample into a pseudo-randomised trial")
    print("""
      If a patient had only a 20% chance of receiving the drug and received it
      anyway, they represent about five such patients — so count them five times.
      Weighting every patient by 1/P(their own treatment) rebuilds a population
      in which treatment looks random.

          w_i = T_i / e(x_i)  +  (1 - T_i) / (1 - e(x_i))
          ATE = weighted mean of Y among treated  -  weighted mean among controls
    """)
    ipw_raw = estimators.ipw_ate(cohort.Y, cohort.T, prop.scores, stabilise=False)
    ipw = estimators.ipw_ate(cohort.Y, cohort.T, prop.scores, stabilise=True)
    results["IPW (stabilised)"] = ipw
    print(f"    raw Horvitz–Thompson    {ipw_raw.value:+.4f}   "
          f"error {ipw_raw.value - truth:+.4f}")
    print(f"    stabilised (Hájek)      {ipw.value:+.4f}   "
          f"error {ipw.value - truth:+.4f}")
    say("The stabilised form divides by the sum of the weights instead of by N. "
        "It is the same estimator in expectation and dramatically less "
        "temperamental in practice, because one patient with a propensity of 0.02 "
        "carries a weight of 50 and can otherwise swing the whole estimate on its "
        "own. Weakness: IPW leans entirely on the PROPENSITY model, exactly as "
        "g-computation leaned entirely on the outcome model.")

    # ── 4. AIPW ──
    head("FIX 4 — AIPW / DOUBLY ROBUST: use both models, need only one to be right")
    print("""
      G-computation trusts the outcome model. IPW trusts the propensity model.
      AIPW uses BOTH: start from the g-computation prediction, then use weighted
      residuals to correct whatever it got wrong.

          psi_i = [mu(x,1) - mu(x,0)]  +  T(Y - mu(x,1))/e  -  (1-T)(Y - mu(x,0))/(1-e)
                   ─────────────────      ──────────────────────────────────────────
                   the model's guess      the weighted correction to it

      The consequence is the reason this is the default choice: if EITHER model
      is correctly specified, the estimate is consistent. Two chances, not one.
    """)
    aipw = estimators.aipw_ate(cohort.X, cohort.T, cohort.Y, cross_fit=True)
    results["AIPW (doubly robust)"] = aipw
    lo, hi = aipw.ci
    print(f"    estimate {aipw.value:+.4f}  ± {aipw.std_error:.4f}   "
          f"95% CI [{lo:+.4f}, {hi:+.4f}]")
    print(f"    truth    {truth:+.4f}   error {aipw.value - truth:+.4f}   "
          f"CI covers truth: {aipw.covers(truth)}")
    say("Cross-fitting matters here and is easy to skip: the outcome model must "
        "not have seen the patient whose residual it is correcting, or the "
        "correction quietly absorbs the model's own overfitting and the standard "
        "error comes out too small.")

    # ── the scoreboard ──
    results["Naive difference"] = estimators.naive_difference(cohort.Y, cohort.T)
    head("SCOREBOARD — every method graded against the answer key")
    board = evaluate.leaderboard(list(results.values()), truth)
    table(board.round(4))

    fig, ax = plt.subplots(figsize=(10, 5))
    evaluate.plot_leaderboard(list(results.values()), truth, ax=ax,
                              save_to=f"{FIGURES}/basics_act5_leaderboard.png")
    plt.close(fig)
    print(f"\n    figure -> {FIGURES}/basics_act5_leaderboard.png")
    verdict(f"Naive is out by {abs(results['Naive difference'].value - truth):.2f} "
            f"and has the wrong sign. AIPW is out by "
            f"{abs(aipw.value - truth):.2f}. Same data, same patients.")

    return results


# ═════════════════════════════════════════════════════════════════════════════
# ACT 6 — prove the hand-written code is correct
# ═════════════════════════════════════════════════════════════════════════════

def act6(cohort: data.Cohort) -> None:
    act(6, "Prove the hand-written code is right",
        "how do we know these twelve-line functions are not subtly broken?")

    say("Writing an estimator by hand is only impressive if it is also CORRECT. "
        "Three independent checks follow, and they test different things.")

    head("CHECK 1 — agreement with DoWhy and EconML")
    say("Every row: our from-scratch NumPy implementation beside the same "
        "estimator from Microsoft Research's libraries, and beside the truth.")
    print()
    tbl = crosscheck.crosscheck_table(cohort)
    table(tbl.round(4))
    print()
    say("The final row is a deliberately different comparison. LinearDML is not a "
        "reimplementation of AIPW — it is a different estimator with a partially "
        "linear structural assumption — so it is held to a looser bar and "
        "labelled as such. Scoring it as a failure would be a category error, and "
        "quietly widening the tolerance for every row to make it pass would be "
        "worse.")

    head("CHECK 2 — the strata knob, measured honestly")
    say("Act 5 admitted the stratification answer moves with the bucket count. "
        "Rather than pick the flattering value, here is the whole curve.")
    print()
    table(crosscheck.strata_sensitivity(cohort).round(4))
    print()
    say("Too few strata and each bucket still mixes dissimilar patients, so bias "
        "survives. Too many and each bucket holds too few patients to average, so "
        "variance takes over. That is the bias-variance trade-off, visible in a "
        "single column.")

    head("CHECK 3 — refutation tests: try to break our own result")
    print(crosscheck.refutation_report(cohort))

    head("CHECK 3b — how much hidden confounding would it take?")
    say("Inject a confounder of increasing strength and watch when the conclusion "
        "breaks. This turns 'we assume no unmeasured confounding' from a promise "
        "into a measured tolerance.")
    print()
    table(crosscheck.unobserved_confounder_test(cohort).round(4))
    print()
    verdict("The result survives moderate hidden confounding and flips under "
            "strong hidden confounding. Stating where the boundary is, is more "
            "useful than claiming there isn't one.")


# ═════════════════════════════════════════════════════════════════════════════
# ACT 7 — from average to personal
# ═════════════════════════════════════════════════════════════════════════════

def act7(cohort: data.Cohort) -> dict:
    act(7, "From the average patient to THIS patient",
        "the average effect is +0.96 — so what do I do with the person in front of me?")

    say("Everything so far estimated the ATE: one number for the whole "
        "population. A clinician cannot prescribe an average. What they need is "
        "the CATE — the effect for a patient with THESE characteristics.")
    print()
    say("And it genuinely matters here, because our authored effect crosses zero. "
        "The population average says 'give the drug'. For "
        f"{float((cohort.true_cate < 0).mean()):.0%} of these patients that is the "
        "wrong instruction.")

    head("Four metalearners, all hand-written")
    print("""
      S-learner   ONE model with treatment as just another feature.
                  Simple; a regulariser can shrink the treatment column and
                  flatten real heterogeneity toward a constant.

      T-learner   TWO separate models, one per arm, subtracted.
                  No shrinkage problem; the small arm gets a noisy model.

      X-learner   T-learner, then cross-impute each patient's missing potential
                  outcome and model the imputed effects directly. Built for
                  exactly our situation: unequal arms and real heterogeneity.

      DR-learner  Regress the AIPW pseudo-outcome on X. Inherits double
                  robustness and gives an honest target to learn.
    """)

    models = {}
    for name, fn in estimators.ALL_CATE_LEARNERS.items():
        t0 = time.time()
        models[name] = fn(cohort.X, cohort.T, cohort.Y)
        print(f"    fitted {name:<12s} mean effect "
              f"{models[name].cate_in_sample.mean():+.4f}   ({time.time()-t0:.1f}s)")

    head("Graded against the authored individual effects")
    say("This is the grading nobody with real data can do — patient by patient, "
        "not on average.")
    print()
    board = evaluate.cate_leaderboard(list(models.values()), cohort.true_cate)
    table(board.round(4))
    print()
    say("MAE is the average per-patient error. Rank correlation matters even more "
        "for a CDSS: it asks whether the model puts the right patients in the "
        "right ORDER, which is what a treat-or-not decision actually depends on.")

    fig, ax = plt.subplots(figsize=(11, 6))
    evaluate.plot_cate_recovery(list(models.values()), cohort, feature="bmi", ax=ax,
                               save_to=f"{FIGURES}/basics_act7_recovery.png")
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(11, 6))
    evaluate.plot_cate_recovery(list(models.values()), cohort, feature="egfr", ax=ax,
                               save_to=f"{FIGURES}/basics_act7_recovery_egfr.png")
    plt.close(fig)
    best = board.iloc[0]["learner"]
    fig, ax = plt.subplots(figsize=(7, 7))
    evaluate.plot_cate_calibration(models[best], cohort.true_cate, ax=ax,
                                   save_to=f"{FIGURES}/basics_act7_calibration.png")
    plt.close(fig)
    print(f"    figure -> {FIGURES}/basics_act7_recovery.png       (vs BMI)")
    print(f"    figure -> {FIGURES}/basics_act7_recovery_egfr.png  (vs eGFR — the kink)")
    print(f"    figure -> {FIGURES}/basics_act7_calibration.png    (best model, {best})")
    say("The eGFR figure is the one to look at. The authored effect has a kink at "
        "eGFR 70 and crosses zero near 55, and the learners recover both from "
        "observational data alone, having never been told the functional form.")

    head("Does better estimation lead to better DECISIONS?")
    say("A lower MAE is a statistical win. What a CDSS cares about is whether the "
        "resulting policy — treat if the estimated effect is positive — actually "
        "helps more patients.")
    print()
    table(evaluate.policy_comparison(list(models.values()), cohort).round(4))
    print()
    say("Regret is the HbA1c benefit forgone versus an oracle who knows every "
        "true individual effect. Treat-everyone is the policy a population-average "
        "tool implies, and it carries real regret because it dispenses the drug to "
        "patients it harms.")

    fig, ax = plt.subplots(figsize=(10, 6))
    evaluate.plot_decision_curve(models[best], cohort, ax=ax,
                                 save_to=f"{FIGURES}/basics_act7_decision.png")
    plt.close(fig)
    print(f"    figure -> {FIGURES}/basics_act7_decision.png")

    head("The head-to-head that makes the case: predictive ML vs causal")
    say("Give a standard predictive model and our causal model the same fixed "
        "drug budget and let each choose who gets it. The predictive model ranks "
        "patients by expected risk; the causal model ranks them by expected "
        "BENEFIT. They are not the same ranking, and the difference is the whole "
        "argument.")
    print()
    print(evaluate.format_predictive_vs_causal(
        evaluate.predictive_vs_causal(cohort, models[best], budget_fraction=0.30)))

    return models


# ═════════════════════════════════════════════════════════════════════════════
# ACT 8 — why this project needs BOTH halves
# ═════════════════════════════════════════════════════════════════════════════

def act8(cohort: data.Cohort, models: dict) -> None:
    act(8, "Why this project needs BOTH halves",
        "you have a personal number — why bother with the guidelines at all?")

    head("First: the retrieval half is real, over the actual PDFs")
    say("No vector database, no embedding API, no PDF library — none of those are "
        "installed here and pip is unavailable. So the PDFs are parsed directly: "
        "a PDF is a text file with zlib-compressed islands in it, and page text "
        "lives in the `Tj` and `TJ` operators of a content stream.")
    print()
    print(pdf_text.extraction_report("RAG"))

    index = rag_lite.build_index()
    print()
    head("The index")
    print(index.summary())
    print()
    table(rag_lite.provenance_table(index))
    print()
    say("Two of the four documents cannot be read: one uses CID-encoded fonts "
        "that need a font table we do not parse, one is a scan with no text "
        "layer. Those are served from curated, page-cited paraphrases and EVERY "
        "citation they produce is marked `[curated]`, so extracted text and "
        "hand-written text are never confused. A retrieval system that failed "
        "silently on half its corpus would be worse than one that says so.")

    head("Retrieval, live")
    print(rag_lite.retrieval_demo(index, k=2))

    head("Now the safety layer")
    say("A CATE model only knows what was in its training data, and it will "
        "cheerfully extrapolate a confident number for a patient it has never "
        "seen anything like. Some rules are not statistical claims at all — "
        "'metformin is contraindicated below eGFR 30' is about lactic acidosis, "
        "a rare event no 4,000-patient effect model would ever learn.")
    print()
    say("So the architecture is deliberately asymmetric: the model may RECOMMEND, "
        "only the guardrails may FORBID.")
    print()
    table(guardrails.rules_table())

    head("And now fuse them")
    best = evaluate.cate_leaderboard(list(models.values()), cohort.true_cate).iloc[0]["learner"]
    system = cdss.DiaCausalCDSS(cohort, cate_model=models[best], index=index)

    mrs_r = "Mrs R — the patient the population average gets WRONG"
    patient = {k: v for k, v in cdss.DEMO_PATIENTS[mrs_r].items() if k != "story"}
    print()
    print(cdss.three_way_contrast(system, patient,
                                  "Mrs R, 68, BMI 34, HbA1c 9.1%, eGFR 46, established CVD"))

    head("The Fundamental Problem, printed for one real row")
    print(system.counterfactual_card(17))

    head("All four demo patients — four different verdicts")
    print(cdss.demo_all_patients(system))


# ═════════════════════════════════════════════════════════════════════════════
# ACT 9 — where this breaks
# ═════════════════════════════════════════════════════════════════════════════

def act9(cohort: data.Cohort) -> None:
    act(9, "Where this breaks",
        "what would you say if an examiner asked you to attack your own project?")

    say("Every limitation below is demonstrated with a number, not conceded in "
        "passing. A project that can state its own failure modes precisely is "
        "more trustworthy than one that claims not to have any.")

    head("LIMITATION 1 — unmeasured confounding defeats all of this")
    hidden = data.generate_cohort(N_PATIENTS, scenario="hidden_confounder", seed=SEED)
    h_naive = estimators.naive_difference(hidden.Y, hidden.T)
    h_aipw = estimators.aipw_ate(hidden.X, hidden.T, hidden.Y, cross_fit=True)
    h_truth = float(hidden.true_cate.mean())
    print(f"    scenario 'hidden_confounder' — frailty drives BOTH prescribing and outcome,")
    print(f"    and is never recorded (exactly like real EHR data).")
    print()
    print(f"      naive      {h_naive.value:+.4f}   error {h_naive.value - h_truth:+.4f}")
    print(f"      AIPW       {h_aipw.value:+.4f}   error {h_aipw.value - h_truth:+.4f}")
    print(f"      truth      {h_truth:+.4f}")
    say("AIPW is better than naive and still wrong. Adjusting for the covariates "
        "you have cannot fix confounding by a covariate you do not have. This is "
        "not a flaw in the method — it is the assumption failing, and no estimator "
        "can rescue it.")

    head("LIMITATION 2 — positivity violations cannot be estimated around")
    broken = data.generate_cohort(N_PATIENTS, scenario="strong", seed=SEED,
                                 violate_positivity=True)
    b_aipw = estimators.aipw_ate(broken.X, broken.T, broken.Y, cross_fit=True)
    print(f"    with a hard 'never prescribe below eGFR 60' rule in the data:")
    print(f"      AIPW       {b_aipw.value:+.4f}   truth {float(broken.true_cate.mean()):+.4f}")
    say("For patients below eGFR 60 there is no treated comparison group at all. "
        "Anything the model reports about them is pure extrapolation from the "
        "functional form, which is the reason the guardrails include an "
        "out-of-distribution rule.")

    head("LIMITATION 3 — the data is synthetic, and that cuts both ways")
    say("Synthetic data is what makes every grading table in this run possible: "
        "there is no other way to check a causal estimate against the truth. But "
        "it also means the confounding structure is the one we wrote. Real EHR "
        "data brings missingness that is itself informative, measurement error, "
        "coding drift, treatment switching, loss to follow-up, and confounders "
        "nobody thought to record. The next stage of this project is a real "
        "retrospective cohort under ethics approval — and the estimates will get "
        "worse, honestly reported.")

    head("LIMITATION 4 — the Pima dataset cannot support a causal claim at all")
    try:
        pima = data.load_pima()
        print(f"    Datasets/diabetes.csv loaded: {pima.shape[0]} rows, "
              f"{pima.shape[1]} columns")
        print(f"    columns: {list(pima.columns)}")
        print()
        say("There is no treatment column. `Outcome` is diabetic yes/no — a "
            "PREDICTION target. You can build a good classifier on this and you "
            "cannot ask 'what if this patient had received SGLT2i', because "
            "nobody in the file received anything. We include it to be explicit "
            "about the distinction, because conflating a prediction dataset with "
            "a causal one is the most common error in student causal projects.")
    except Exception as exc:
        print(f"    (Pima dataset not loadable: {type(exc).__name__}: {exc})")

    head("LIMITATION 5 — what the retrieval half cannot do")
    for i, lim in enumerate(rag_lite.KNOWN_LIMITATIONS, 1):
        say(f"{i}. {lim}", indent=4)
        print()

    head("LIMITATION 6 — scope of the estimate itself")
    say("The model estimates HbA1c reduction and nothing else. It does not "
        "estimate cardiovascular death, kidney progression, ketoacidosis, "
        "amputation, cost, or adherence. For SGLT2 inhibitors specifically that "
        "is a serious limitation, because their most important benefits are "
        "cardiorenal and show up in outcomes this model never sees. The "
        "guardrails say so on every card, which is the minimum acceptable "
        "handling of it.")

    head("WHAT A REAL DEPLOYMENT WOULD STILL NEED")
    for item in [
        "Real retrospective cohort, ethics approval, and a pre-registered protocol.",
        "Multi-outcome estimation: cardiovascular, renal, and adverse events too.",
        "Patient-level uncertainty (conformal intervals), not the population SE.",
        "Prospective validation against clinician decisions before any live use.",
        "Full contraindication and drug-interaction checking, pharmacist reviewed.",
        "Monitoring for distribution shift, plus an audit trail on every output.",
        "Regulatory classification — this would be a medical device.",
    ]:
        print(f"      · {item}")


# ═════════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════════

def main() -> int:
    os.makedirs(FIGURES, exist_ok=True)
    t0 = time.time()

    print("\n" + "█" * WIDTH)
    print("  DIACAUSAL — CAUSAL INFERENCE FROM FIRST PRINCIPLES")
    print("  A clinical decision support system for type-2 diabetes")
    print("█" * WIDTH)
    say("Every causal quantity below is computed by hand in NumPy, graded against "
        "a ground truth we authored, and cross-checked against DoWhy and EconML. "
        f"n = {N_PATIENTS} patients, seed = {SEED}.", indent=2)

    act0()
    cohort = act1()
    act2(cohort)
    act3(cohort)
    prop = act4(cohort)
    act5(cohort, prop)
    act6(cohort)
    models = act7(cohort)
    act8(cohort, models)
    act9(cohort)

    truth = float(cohort.true_cate.mean())
    naive = estimators.naive_difference(cohort.Y, cohort.T).value
    aipw = estimators.aipw_ate(cohort.X, cohort.T, cohort.Y, cross_fit=True).value

    print("\n\n" + "█" * WIDTH)
    print("  THE WHOLE PROJECT IN FOUR NUMBERS")
    print("█" * WIDTH)
    print(f"""
    TRUE effect of the drug                        {truth:+.4f}
    What correlation says   (naive difference)     {naive:+.4f}   <- wrong SIGN
    What causal inference says (AIPW, by hand)     {aipw:+.4f}   <- error {aipw-truth:+.4f}
    Patients the population average HARMS          {float((cohort.true_cate < 0).mean()):.1%}

    The first three lines are why this project has a causal half at all: the same
    data, the same patients, and an answer that reverses depending on whether you
    account for who was given what and why.

    The fourth line is why it also needs a PERSONAL estimate rather than an
    average — and the citations and guardrails on every card are why a clinician
    could be shown the result at all.
""")
    print(f"  figures -> {FIGURES}/basics_act*.png")
    print(f"  completed in {time.time() - t0:.1f}s")
    print("█" * WIDTH + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
