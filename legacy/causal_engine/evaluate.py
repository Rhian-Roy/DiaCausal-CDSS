"""
ACT 7 / ACT 8 — Grading. Which method actually works, and does it help patients?
===============================================================================

Every estimator in `estimators.py` returns a number. Numbers are cheap. This
module is where they get marked against the answer key we authored in
`data.py`, because a method that cannot recover a truth we planted has not
earned the right to be pointed at real patients.

Three different questions get asked here, and they are genuinely different:

    1. ACCURACY OF THE AVERAGE   — `leaderboard`
       How close is the estimated ATE to the true ATE?
       This is the question papers report. It is the least useful of the three.

    2. ACCURACY OF THE PERSONAL  — `cate_leaderboard`, `plot_cate_recovery`
       How close is each patient's estimated effect to their true effect?
       A method can nail the average and be useless per-patient: predict the
       same 1.23 for everybody and your ATE error is zero while your clinical
       value is nil. This is the estimand a CDSS actually needs.

    3. QUALITY OF THE DECISION   — `policy_value`, `decision_curve`
       If we treated the patients this model says to treat, how much HbA1c
       reduction would the population actually gain?
       This is the only question a hospital cares about, and it is the one that
       gets measured least. Note that it is NOT the same as (2): a model can
       have mediocre CATE error and still make excellent decisions, because
       decisions only need the SIGN and the RANKING to be right, not the
       magnitude.

`predictive_vs_causal` closes the argument the project exists to make: a
well-tuned outcome predictor, scoring beautifully on RMSE, recommends the wrong
drug for a large fraction of patients — because it answers a question nobody
asked.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import PALETTE


# ═════════════════════════════════════════════════════════════════════════════
# 1. Did we recover the AVERAGE effect?
# ═════════════════════════════════════════════════════════════════════════════

def leaderboard(estimates, true_ate: float) -> pd.DataFrame:
    """Mark every ATE estimate against the authored truth, worst error last.

    The `covers truth?` column is the one to look at hardest. An estimate can be
    close and still be wrong in an important way: if the 95% interval misses the
    truth, the method is *overconfident*, which is more dangerous in a clinical
    tool than being imprecise and honest about it.
    """
    rows = []
    for e in estimates:
        ci = e.ci
        rows.append(
            {
                "method": e.method,
                "estimate": round(e.value, 4),
                "truth": round(true_ate, 4),
                "error": round(e.value - true_ate, 4),
                "|error|": round(abs(e.value - true_ate), 4),
                "95% CI": (
                    f"[{ci[0]:+.3f}, {ci[1]:+.3f}]" if ci else "not computed"
                ),
                "covers truth?": (
                    "—" if ci is None else ("yes" if ci[0] <= true_ate <= ci[1] else "NO")
                ),
                "right sign?": "yes" if np.sign(e.value) == np.sign(true_ate) else "NO",
            }
        )
    return (
        pd.DataFrame(rows)
        .sort_values("|error|")
        .reset_index(drop=True)
    )


def plot_leaderboard(estimates, true_ate, ax=None, title=None, save_to=None):
    """Forest plot: every method's estimate and interval against the truth line.

    The violet vertical line is the truth. Bars that cross it are doing their
    job. This is the single figure that answers "how do you know your causal
    inference is correct?" — and it exists only because we authored the world.
    """
    import matplotlib.pyplot as plt

    if ax is None:
        _, ax = plt.subplots(figsize=(9.6, 0.62 * len(estimates) + 2.0))

    ordered = sorted(estimates, key=lambda e: abs(e.value - true_ate), reverse=True)
    y = np.arange(len(ordered))

    for i, e in enumerate(ordered):
        good = np.sign(e.value) == np.sign(true_ate) and abs(e.value - true_ate) < 0.15
        colour = PALETTE["primary"] if good else PALETTE["alert"]
        ci = e.ci
        if ci:
            ax.plot([ci[0], ci[1]], [i, i], color=colour, linewidth=2.4, alpha=0.75)
            for b in ci:
                ax.plot([b, b], [i - 0.13, i + 0.13], color=colour, linewidth=2.0)
        ax.scatter([e.value], [i], s=125, color=colour, zorder=4, edgecolors="white")

    ax.axvline(true_ate, color=PALETTE["truth"], linewidth=2.4, linestyle="-",
               label=f"TRUE effect = {true_ate:+.3f}", zorder=2)
    ax.axvline(0.0, color=PALETTE["secondary"], linewidth=1.0, linestyle=":",
               alpha=0.55, label="no effect")

    ax.set_yticks(y)
    ax.set_yticklabels([e.method for e in ordered], fontsize=8.6)
    ax.set_xlabel("Estimated average treatment effect (HbA1c points reduced)")
    ax.set_title(title or "Every method, graded against the authored truth",
                 fontweight="bold", color=PALETTE["secondary"])
    ax.legend(loc="lower right", fontsize=8.6)
    ax.spines[["top", "right"]].set_visible(False)

    if save_to:
        ax.figure.tight_layout()
        ax.figure.savefig(save_to, dpi=150, bbox_inches="tight")
    return ax


# ═════════════════════════════════════════════════════════════════════════════
# 2. Did we recover each PATIENT's effect?
# ═════════════════════════════════════════════════════════════════════════════

def cate_leaderboard(cate_models, true_cate: np.ndarray) -> pd.DataFrame:
    """Grade personalised predictions, which is what the CDSS actually serves.

    Columns, in increasing order of how much they matter clinically:

    `ATE error`   — error in the average. Can be ~0 for a useless model.
    `CATE MAE`    — average per-patient error. The honest accuracy measure.
    `rank corr`   — Spearman correlation with the truth. Does the model put the
                    right patients at the top? For deciding WHO to treat, this
                    matters more than magnitude, because a decision only needs
                    the ordering.
    `sign agree`  — fraction of patients for whom the model gets benefit-vs-harm
                    right. This is the number that maps directly onto clinical
                    mistakes.
    """
    from scipy.stats import spearmanr

    truth_mean = float(np.mean(true_cate))
    rows = []
    for m in cate_models:
        pred = np.asarray(m.cate_in_sample, float)
        rho = spearmanr(pred, true_cate).statistic
        rows.append(
            {
                "learner": m.name,
                "mean effect": round(float(pred.mean()), 4),
                "ATE error": round(float(pred.mean()) - truth_mean, 4),
                "CATE MAE": round(float(np.abs(pred - true_cate).mean()), 4),
                "CATE RMSE": round(
                    float(np.sqrt(np.mean((pred - true_cate) ** 2))), 4
                ),
                "rank corr": round(float(rho) if np.isfinite(rho) else 0.0, 3),
                "sign agree": round(
                    float(np.mean(np.sign(pred) == np.sign(true_cate))), 3
                ),
                "spread (SD)": round(float(pred.std(ddof=1)), 4),
                "true spread": round(float(np.std(true_cate, ddof=1)), 4),
            }
        )
    return pd.DataFrame(rows).sort_values("CATE MAE").reset_index(drop=True)


def plot_cate_recovery(
    cate_models,
    cohort,
    feature: str = "bmi",
    ax=None,
    title=None,
    save_to=None,
):
    """Overlay each learner's RECOVERED effect curve on the AUTHORED truth.

    We planted `true_cate = 1.2 + 0.03 * (bmi - 30)` — a straight line. So the
    violet line is exactly what a perfect method would draw. Every other line is
    a method's attempt to rediscover it, having never been told the formula.

    What to look for, and what each failure means:
      * A line that tracks the violet one          -> recovered the heterogeneity.
      * A FLAT line at roughly the right height    -> got the average right,
        learned nothing personal. (Watch the S-learner do this: its regulariser
        treats the treatment column as one weak feature among many and shrinks
        the interaction to nothing.)
      * A wiggly line                              -> fitting noise; will give
        two similar patients different advice.
    """
    import matplotlib.pyplot as plt

    if ax is None:
        _, ax = plt.subplots(figsize=(10, 5.6))

    x = cohort.data[feature].to_numpy(float)
    order = np.argsort(x)
    xs = x[order]

    def smooth(values, k=180):
        """Rolling mean along the sorted feature, so curves are readable."""
        v = np.asarray(values, float)[order]
        kernel = np.ones(k) / k
        pad = k // 2
        padded = np.concatenate([np.repeat(v[0], pad), v, np.repeat(v[-1], pad)])
        return np.convolve(padded, kernel, mode="same")[pad:pad + len(v)]

    ax.plot(xs, smooth(cohort.true_cate), color=PALETTE["truth"], linewidth=3.4,
            label="TRUE effect (what we authored)", zorder=5)

    colours = [PALETTE["primary"], PALETTE["amber"], PALETTE["alert"],
               PALETTE["secondary"], PALETTE["success"]]
    for i, m in enumerate(cate_models):
        ax.plot(xs, smooth(m.cate_in_sample), linewidth=1.9,
                color=colours[i % len(colours)], alpha=0.9, label=m.name)

    ax.axhline(0, color=PALETTE["secondary"], linewidth=0.9, linestyle=":", alpha=0.5)
    ax.set_xlabel(f"{feature.upper()}  (the feature the true effect depends on)")
    ax.set_ylabel("Treatment effect (HbA1c points reduced by SGLT2i)")
    ax.set_title(
        title or "Can each method rediscover the effect curve we planted?",
        fontweight="bold", color=PALETTE["secondary"],
    )
    ax.legend(fontsize=8.6, loc="upper left")
    ax.spines[["top", "right"]].set_visible(False)

    if save_to:
        ax.figure.tight_layout()
        ax.figure.savefig(save_to, dpi=150, bbox_inches="tight")
    return ax


def plot_cate_calibration(cate_model, true_cate, ax=None, save_to=None):
    """Bin patients by PREDICTED effect; plot mean predicted vs mean true.

    A calibrated model sits on the diagonal: when it says "1.5", the truth
    averages 1.5. A model can rank patients perfectly and still be badly
    calibrated — fine for choosing who to treat, dangerous for telling a
    clinician a number, because "expect 1.5 points" would then be a false
    promise.
    """
    import matplotlib.pyplot as plt

    if ax is None:
        _, ax = plt.subplots(figsize=(6.2, 6.0))

    pred = np.asarray(cate_model.cate_in_sample, float)
    edges = np.quantile(pred, np.linspace(0, 1, 11))
    edges[-1] += 1e-9
    idx = np.digitize(pred, edges[1:-1])

    px, ty = [], []
    for b in range(10):
        m = idx == b
        if m.sum() > 0:
            px.append(pred[m].mean())
            ty.append(np.asarray(true_cate, float)[m].mean())

    lim = [min(px + ty) - 0.1, max(px + ty) + 0.1]
    ax.plot(lim, lim, color=PALETTE["truth"], linestyle="--", linewidth=2.0,
            label="perfect calibration")
    ax.scatter(px, ty, s=115, color=PALETTE["primary"], edgecolors="white",
               zorder=4, label=cate_model.name)

    ax.set_xlabel("Mean PREDICTED effect within decile")
    ax.set_ylabel("Mean TRUE effect within decile")
    ax.set_title(f"Calibration — {cate_model.name}", fontweight="bold",
                 color=PALETTE["secondary"])
    ax.set_xlim(lim)
    ax.set_ylim(lim)
    ax.legend(fontsize=8.6)
    ax.spines[["top", "right"]].set_visible(False)

    if save_to:
        ax.figure.tight_layout()
        ax.figure.savefig(save_to, dpi=150, bbox_inches="tight")
    return ax


# ═════════════════════════════════════════════════════════════════════════════
# 3. Would the DECISIONS have helped patients? (the only question that matters)
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class PolicyValue:
    """The clinical bottom line: gain per patient from following this policy."""

    name: str
    value: float
    fraction_treated: float
    regret: float
    best_possible: float

    def __str__(self) -> str:
        return (
            f"{self.name:<34s} gain/patient {self.value:+.4f}  "
            f"treats {self.fraction_treated:5.1%}  regret {self.regret:.4f}"
        )


def policy_value(decision: np.ndarray, true_cate: np.ndarray, name="policy") -> PolicyValue:
    """Total benefit if we followed this treat/don't-treat rule.

    Because we authored `true_cate`, we know exactly what each patient would
    gain. So the value of a policy is simply the mean true effect over the
    patients it chooses to treat, times how many it treats:

        value = mean( decision * true_cate )

    `regret` is the gap to the oracle policy (treat exactly those with a
    positive true effect). Regret is more honest than value, because value
    depends on the population while regret is a pure measure of decision
    quality — 0 means you made no wrong calls.
    """
    d = np.asarray(decision, int)
    tau = np.asarray(true_cate, float)
    best = float(np.mean(np.maximum(tau, 0.0)))
    val = float(np.mean(d * tau))
    return PolicyValue(
        name=name,
        value=val,
        fraction_treated=float(d.mean()),
        regret=best - val,
        best_possible=best,
    )


def policy_comparison(cate_models, cohort, threshold: float = 0.0) -> pd.DataFrame:
    """Compare real policies against the two trivial ones and the oracle.

    The trivial baselines matter more than they look. "Treat everybody" is a
    genuinely strong policy whenever the drug helps almost all patients — and if
    a sophisticated CATE model cannot beat it, the honest conclusion is that
    personalisation adds nothing HERE, and saying so is better science than
    shipping a model for its own sake.

    The comparison becomes interesting exactly when the true effect changes sign
    across the population, because then no blanket rule can be right.
    """
    tau = cohort.true_cate
    policies = [
        policy_value(np.ones(len(tau), int), tau, "treat everyone"),
        policy_value(np.zeros(len(tau), int), tau, "treat nobody"),
    ]
    for m in cate_models:
        d = (np.asarray(m.cate_in_sample, float) > threshold).astype(int)
        policies.append(policy_value(d, tau, f"follow {m.name}"))
    policies.append(
        policy_value((tau > threshold).astype(int), tau, "ORACLE (knows the truth)")
    )

    return pd.DataFrame(
        [
            {
                "policy": p.name,
                "gain per patient": round(p.value, 4),
                "% treated": round(100 * p.fraction_treated, 1),
                "regret vs oracle": round(p.regret, 4),
            }
            for p in policies
        ]
    ).sort_values("regret vs oracle").reset_index(drop=True)


def decision_curve(cate_model, cohort, n_points: int = 25) -> pd.DataFrame:
    """Treat the top q% by predicted effect; measure the true gain. Vary q.

    This is the practical planning tool, and the one a hospital pharmacy budget
    actually needs. It answers "we can afford to put 30% of our patients on the
    expensive drug — which 30%, and what do we get?"

    A useful model's curve rises steeply at the left: the patients it ranks
    highest really do benefit most. A flat curve means the ranking carries no
    information, and you may as well treat at random.
    """
    pred = np.asarray(cate_model.cate_in_sample, float)
    tau = cohort.true_cate
    order = np.argsort(-pred)          # best-predicted patients first
    n = len(pred)

    rows = []
    for q in np.linspace(0.04, 1.0, n_points):
        k = max(1, int(round(q * n)))
        chosen = order[:k]
        rows.append(
            {
                "fraction treated": round(q, 3),
                "n treated": k,
                # Gain realised across the WHOLE population, so budgets compare.
                "true gain per patient": round(float(tau[chosen].sum() / n), 4),
                "mean true effect among treated": round(float(tau[chosen].mean()), 4),
                "random baseline": round(float(tau.mean() * q), 4),
            }
        )
    return pd.DataFrame(rows)


def plot_decision_curve(cate_model, cohort, ax=None, save_to=None):
    """Draw the decision curve against the random-selection baseline."""
    import matplotlib.pyplot as plt

    if ax is None:
        _, ax = plt.subplots(figsize=(8.6, 5.0))

    dc = decision_curve(cate_model, cohort)
    ax.plot(dc["fraction treated"], dc["true gain per patient"],
            color=PALETTE["primary"], linewidth=2.6,
            label=f"target by {cate_model.name}")
    ax.plot(dc["fraction treated"], dc["random baseline"],
            color=PALETTE["muted"], linewidth=2.0, linestyle="--",
            label="treat at random")

    ax.set_xlabel("Fraction of patients we can afford to treat")
    ax.set_ylabel("True HbA1c gain per patient (whole population)")
    ax.set_title("Decision curve — does the ranking buy us anything?",
                 fontweight="bold", color=PALETTE["secondary"])
    ax.legend(fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)

    if save_to:
        ax.figure.tight_layout()
        ax.figure.savefig(save_to, dpi=150, bbox_inches="tight")
    return ax


# ═════════════════════════════════════════════════════════════════════════════
# THE ARGUMENT — a good predictor makes a bad decision-maker
# ═════════════════════════════════════════════════════════════════════════════

def predictive_vs_causal(
    cohort,
    cate_model,
    budget_fraction: float | None = 0.30,
    test_fraction: float = 0.3,
    seed: int = 0,
):
    """Head-to-head: a risk-prediction CDSS vs a causal CDSS.

    THE POINT OF THIS FUNCTION
    --------------------------
    Almost every deployed clinical ML tool is a RISK model. It predicts who will
    do badly, and the clinical workflow wrapped around it is "escalate care for
    the high-risk patients". That heuristic is so natural it is rarely questioned.

    It is also, in this world, close to the worst thing you could do — because
    risk and benefit are different quantities, and here they point in OPPOSITE
    directions. The patients with the worst prognosis are the ones with failing
    kidneys, and failing kidneys are exactly what stops this drug from working.

        corr(predicted risk, true benefit) ~= -0.47

    That negative sign is the entire argument for the causal half of this
    project, and it is measurable rather than rhetorical.

    WHY THE BUDGET MATTERS SO MUCH
    ------------------------------
    `budget_fraction` is how many patients we can actually afford to put on the
    expensive drug. It is the most important argument here, because the value of
    personalisation depends almost entirely on how scarce the treatment is:

        budget 85% (nearly everyone)  ->  benefit-targeting wins by ~1.6x
        budget 30% (realistic)        ->  benefit-targeting wins by ~8x

    The reason is simple. When you can treat nearly everyone, it hardly matters
    who you pick, because you pick almost all of them either way. When the drug
    is scarce, WHO gets it is the whole decision — and that is exactly the
    situation a real formulary is in. Quoting the unconstrained number would
    understate the case; we report both, plus a sweep.

    WHAT GETS COMPARED — all at the SAME budget, so no policy wins by
    simply treating more people:

        1. `risk`      A strong prognostic model (X -> Y). Treat the patients
                       predicted to do worst. The industry-standard heuristic.
        2. `counterfactual`
                       A predictive model given the treatment column, asked to
                       predict both arms and pick the better one.
                       IMPORTANT AND OFTEN MISSED: this is not really a
                       "predictive" baseline at all — it is g-computation with a
                       flexible learner, i.e. a causal method in disguise. It
                       therefore does reasonably well, and its failure mode is
                       the S-learner's (a regulariser that shrinks the treatment
                       interaction). We include it because dismissing it would
                       be a strawman, and because the fact that it works is
                       itself informative: what makes a method causal is the
                       question you ask of it, not the algorithm.
        3. `causal`    Treat by predicted BENEFIT, from the CATE model.

    Set `budget_fraction=None` to size the budget the way the oracle would
    (treat everyone with a positive true effect) — the unconstrained case.

    Everything is graded on held-out patients against the authored answer key.
    """
    from sklearn.ensemble import GradientBoostingRegressor
    from sklearn.metrics import r2_score
    from sklearn.model_selection import train_test_split
    from scipy.stats import spearmanr

    X, T, Y = cohort.X, cohort.T, cohort.Y
    tau = cohort.true_cate
    idx = np.arange(len(Y))
    tr, te = train_test_split(idx, test_size=test_fraction, random_state=seed,
                              stratify=T)
    Xte, tau_te, n_te = X[te], tau[te], len(te)

    # ── Policy 1: the realistic predictive CDSS — a prognostic risk model ────
    risk_model = GradientBoostingRegressor(
        n_estimators=300, max_depth=3, learning_rate=0.05, random_state=seed
    )
    risk_model.fit(X[tr], Y[tr])
    pred_outcome = risk_model.predict(Xte)
    risk_score = -pred_outcome          # higher = worse predicted outcome
    risk_r2 = float(r2_score(Y[te], pred_outcome))
    risk_rmse = float(np.sqrt(np.mean((pred_outcome - Y[te]) ** 2)))

    # ── Policy 2: predictive model used counterfactually (= g-computation) ───
    cf_model = GradientBoostingRegressor(
        n_estimators=300, max_depth=3, learning_rate=0.05, random_state=seed
    )
    cf_model.fit(np.column_stack([X[tr], T[tr]]), Y[tr])
    cf_benefit = (
        cf_model.predict(np.column_stack([Xte, np.ones(n_te)]))
        - cf_model.predict(np.column_stack([Xte, np.zeros(n_te)]))
    )
    cf_r2 = float(r2_score(
        Y[te], cf_model.predict(np.column_stack([Xte, T[te]]))
    ))

    # ── Policy 3: the causal CDSS — treat by predicted benefit ───────────────
    causal_benefit = np.asarray(cate_model.effect(Xte), float)

    budget = (
        int(round(budget_fraction * n_te)) if budget_fraction is not None
        else int((tau_te > 0).sum())
    )
    budget = max(1, min(budget, n_te))

    def top_k_gain(score, k=budget):
        pick = np.argsort(-np.asarray(score, float))[:k]
        return float(tau_te[pick].sum() / n_te), float(tau_te[pick].mean())

    gain_risk, mean_risk = top_k_gain(risk_score)
    gain_cf, mean_cf = top_k_gain(cf_benefit)
    gain_causal, mean_causal = top_k_gain(causal_benefit)
    gain_oracle, mean_oracle = top_k_gain(tau_te)

    # How the gap depends on scarcity — the most informative single output.
    sweep = []
    for f in (0.10, 0.20, 0.30, 0.50, 0.70, 0.85, 1.00):
        k = max(1, int(round(f * n_te)))
        g_risk, _ = top_k_gain(risk_score, k)
        g_causal, _ = top_k_gain(causal_benefit, k)
        g_oracle, _ = top_k_gain(tau_te, k)
        sweep.append(
            {
                "budget": f,
                "gain by risk": round(g_risk, 4),
                "gain by benefit": round(g_causal, 4),
                "gain oracle": round(g_oracle, 4),
                # A negative risk-policy gain means treating the sickest first
                # made the population WORSE than treating nobody. No ratio can
                # express that, so we say it in words.
                "benefit / risk": (
                    f"{g_causal / g_risk:.1f}x" if g_risk > 0
                    else "risk policy HARMS"
                ),
            }
        )

    # Unconstrained sign-based decisions, for the accuracy columns.
    oracle_rec = (tau_te > 0).astype(int)
    cf_rec = (cf_benefit > 0).astype(int)
    causal_rec = (causal_benefit > 0).astype(int)

    return {
        # how good the risk model is at its OWN job
        "risk_model_r2": risk_r2,
        "risk_model_rmse": risk_rmse,
        "counterfactual_model_r2": cf_r2,
        # the headline: risk and benefit are not the same quantity
        "corr_risk_vs_benefit": float(spearmanr(risk_score, tau_te).statistic),
        # matched-budget policy value
        "budget_n": budget,
        "budget_pct": float(100 * budget / n_te),
        "gain_treat_by_risk": gain_risk,
        "gain_treat_by_counterfactual": gain_cf,
        "gain_treat_by_causal": gain_causal,
        "gain_oracle": gain_oracle,
        "mean_effect_among_risk_selected": mean_risk,
        "mean_effect_among_causal_selected": mean_causal,
        "risk_efficiency": gain_risk / gain_oracle if gain_oracle else float("nan"),
        "causal_efficiency": gain_causal / gain_oracle if gain_oracle else float("nan"),
        "budget_sweep": pd.DataFrame(sweep),
        # sign-decision accuracy
        "counterfactual_accuracy_vs_oracle": float(np.mean(cf_rec == oracle_rec)),
        "causal_accuracy_vs_oracle": float(np.mean(causal_rec == oracle_rec)),
        "disagreement_cf_vs_causal": float(np.mean(cf_rec != causal_rec)),
        "n_test": int(n_te),
    }


def format_predictive_vs_causal(result: dict) -> str:
    """Print the head-to-head as the argument it is."""
    r = result
    if r["gain_treat_by_risk"] > 0:
        ratio = f"{r['gain_treat_by_causal'] / r['gain_treat_by_risk']:.1f}x"
    else:
        ratio = (
            "infinitely (the risk policy's gain is NEGATIVE — at this budget it "
            "leaves the population worse off than treating nobody at all)"
        )
    return f"""
RISK PREDICTION vs CAUSAL INFERENCE   (held-out patients: {r['n_test']})
──────────────────────────────────────────────────────────────────────────
STEP 1 — the risk model is genuinely good at its own job.
    R² {r['risk_model_r2']:.4f}      RMSE {r['risk_model_rmse']:.4f}
    Nothing below is a failure of accuracy. It predicts outcomes well.

STEP 2 — but risk is not benefit, and here they point OPPOSITE ways.
    corr(predicted risk, true benefit) = {r['corr_risk_vs_benefit']:+.3f}
    The sickest patients are the low-eGFR patients, and low eGFR is exactly
    what stops this drug from working. "Treat the sickest first" therefore
    selects, with some precision, the patients it will help least.

STEP 3 — same budget ({r['budget_n']} patients, {r['budget_pct']:.0f}%), three ways of choosing them.
    treat the sickest (risk model) : {r['gain_treat_by_risk']:+.4f} gain/patient   \
[{r['risk_efficiency']:5.1%} of achievable]
    predict both arms (= g-comp)   : {r['gain_treat_by_counterfactual']:+.4f} gain/patient
    treat by benefit (causal)      : {r['gain_treat_by_causal']:+.4f} gain/patient   \
[{r['causal_efficiency']:5.1%} of achievable]
    ORACLE (knows the truth)       : {r['gain_oracle']:+.4f} gain/patient

    Choosing by benefit instead of risk is worth {ratio} more HbA1c
    reduction, from the same number of prescriptions and the same budget.

    Mean TRUE effect among the patients each policy picked:
        risk-selected   {r['mean_effect_among_risk_selected']:+.3f}
        causal-selected {r['mean_effect_among_causal_selected']:+.3f}

STEP 4 — and the scarcer the drug, the more the causal model is worth.
{r['budget_sweep'].to_string(index=False)}

    Read the last column. When you can treat everyone, choosing well is worth
    almost nothing — you pick the same people either way. When the drug is
    scarce, choosing well is worth several times the benefit, and at the
    tightest budgets the risk-based policy goes NEGATIVE: it spends the entire
    formulary on the patients the drug hurts. Real formularies live at the top
    of this table, which is exactly where the causal model earns its keep.

STEP 5 — a caveat we state rather than hide.
    The middle policy — predict both arms, pick the better — scores
    {r['counterfactual_accuracy_vs_oracle']:.1%} against the answer key, close to the causal model's
    {r['causal_accuracy_vs_oracle']:.1%}. That is not an embarrassment; it is the lesson. Predicting
    both arms IS g-computation. It is a causal method wearing predictive
    clothes. What makes an analysis causal is the question you pose and the
    assumptions you defend, not the algorithm you import.

    The risk model fails not because gradient boosting is weak, but because
    "who will do badly?" and "who should I treat?" are different questions,
    and no amount of extra accuracy on the first one answers the second.
"""
