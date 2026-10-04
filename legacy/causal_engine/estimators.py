"""
ACT 5 — Four fixes for confounding, every one written out by hand.
=================================================================

This module is the answer to the question that the existing DoWhy-based
implementation cannot answer:

    "Show me how IPW actually works."

Not one estimator here calls a causal-inference library. Every method is plain
NumPy plus scikit-learn for the ordinary regressions, and each one fits on a
single screen. `crosscheck.py` then proves these hand-written functions agree
with DoWhy and EconML to three decimal places.

--------------------------------------------------------------------------------
THE ONE IDEA BEHIND ALL FOUR METHODS
--------------------------------------------------------------------------------
The problem is that treated and untreated patients were never comparable. Every
method below is a different way of saying "compare like with like":

    1. STRATIFICATION   Sort patients into bins of similar people. Compare
                        inside each bin, then average the bins.
                        -> The most explainable method that exists.

    2. G-COMPUTATION    Fit a model of the outcome, then ask it to predict
                        twice for EVERY patient: once as if treated, once as
                        if untreated. Average the difference.
                        -> "Simulate the trial you could not run."

    3. IPW              Weight each patient by 1/(their chance of getting the
                        drug they got). Rare choices count for more, which
                        rebuilds a pseudo-randomised population.
                        -> "Undo the doctor's bias by re-weighting."

    4. AIPW             Do 2 and 3 at once, so being wrong about one still
       (doubly robust)  leaves you right overall.
                        -> "Two independent chances to be correct."

Then, to go from an average to a *person* (Act 7):

    S / T / X-learner   Predict the outcome under each drug for THIS patient
                        and subtract. This is the CATE, the quantity the CDSS
                        actually needs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from sklearn.base import clone
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

# Propensity scores of exactly 0 or 1 make the IPW weights infinite. Clipping
# is the standard, honest fix — but it is a fix, so we record how often it bites.
PROPENSITY_CLIP = (0.01, 0.99)


@dataclass
class EffectEstimate:
    """One estimate of a treatment effect, with everything needed to judge it."""

    method: str
    value: float
    std_error: float | None = None
    #: Per-patient effects, when the method produces them (CATE methods do).
    cate: np.ndarray | None = None
    notes: dict = field(default_factory=dict)

    @property
    def ci(self) -> tuple[float, float] | None:
        """95% confidence interval, if we could compute a standard error."""
        if self.std_error is None or not np.isfinite(self.std_error):
            return None
        return (self.value - 1.96 * self.std_error, self.value + 1.96 * self.std_error)

    def error_vs(self, truth: float) -> float:
        return self.value - truth

    def covers(self, truth: float) -> bool | None:
        """Does the 95% interval actually contain the true answer? (Honest test.)"""
        interval = self.ci
        if interval is None:
            return None
        return bool(interval[0] <= truth <= interval[1])

    def __str__(self) -> str:
        out = f"{self.method:<28s} {self.value:+.4f}"
        if self.std_error is not None and np.isfinite(self.std_error):
            lo, hi = self.ci  # type: ignore[misc]
            out += f"   95% CI [{lo:+.4f}, {hi:+.4f}]"
        return out


# ═════════════════════════════════════════════════════════════════════════════
# Default models. Deliberately boring: the point is the causal logic, not the ML.
# ═════════════════════════════════════════════════════════════════════════════

def default_outcome_model():
    """A flexible regressor for E[Y | X]."""
    return GradientBoostingRegressor(
        n_estimators=200, max_depth=3, learning_rate=0.05, random_state=0
    )


def default_treatment_model():
    """A classifier for P(T=1 | X) — i.e. the propensity score."""
    return make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=5000, C=1.0),
    )


# ═════════════════════════════════════════════════════════════════════════════
# METHOD 0 — The naive answer. Included so we can watch it fail.
# ═════════════════════════════════════════════════════════════════════════════

def naive_difference(Y: np.ndarray, T: np.ndarray) -> EffectEstimate:
    """Just compare the two groups' average outcomes.

        estimate = mean(Y among treated) - mean(Y among untreated)

    This is what almost every dashboard, spreadsheet and "AI insight" computes.
    It answers the question "who ended up better?" — NOT "what does the drug
    do?". When sicker patients were the ones given the drug, this is not merely
    imprecise, it can point the wrong way entirely.
    """
    y1, y0 = Y[T == 1], Y[T == 0]
    diff = float(y1.mean() - y0.mean())
    # Standard two-sample standard error.
    se = float(np.sqrt(y1.var(ddof=1) / len(y1) + y0.var(ddof=1) / len(y0)))
    return EffectEstimate(
        method="naive difference in means",
        value=diff,
        std_error=se,
        notes={
            "n_treated": int(len(y1)),
            "n_control": int(len(y0)),
            "warning": "Valid ONLY if treatment was randomly assigned.",
        },
    )


# ═════════════════════════════════════════════════════════════════════════════
# METHOD 1 — Stratification. The most explainable method there is.
# ═════════════════════════════════════════════════════════════════════════════

def stratified_effect(
    X: np.ndarray,
    T: np.ndarray,
    Y: np.ndarray,
    n_strata: int = 5,
    propensity: np.ndarray | None = None,
) -> EffectEstimate:
    """Compare like with like, then average the comparisons.

    Explain it to anyone in one sentence:

        "Sort the patients into five buckets of similar people. Inside a
         bucket everyone is comparable, so a plain comparison is fair. Do
         that in every bucket, then take a weighted average."

    We bucket on the propensity score, because a remarkable fact (Rosenbaum &
    Rubin, 1983) says that one number is enough: patients who had the same
    *chance* of being treated are comparable on all the covariates that went
    into it. One dimension replaces six.
    """
    if propensity is None:
        propensity = estimate_propensity(X, T).scores

    # Equal-frequency buckets, so every stratum holds a decent number of people.
    edges = np.quantile(propensity, np.linspace(0, 1, n_strata + 1))
    edges[0], edges[-1] = -np.inf, np.inf
    bucket = np.digitize(propensity, edges[1:-1])

    rows, total_weight, weighted_sum, var_sum = [], 0.0, 0.0, 0.0
    for b in range(n_strata):
        m = bucket == b
        yt, yc = Y[m & (T == 1)], Y[m & (T == 0)]
        if len(yt) == 0 or len(yc) == 0:
            # No comparison possible in this bucket — this is what a positivity
            # violation looks like from the inside. We must skip it, which
            # silently changes the population we are talking about.
            rows.append({"stratum": b, "n": int(m.sum()), "effect": np.nan,
                         "n_treated": int(len(yt)), "n_control": int(len(yc))})
            continue
        eff = float(yt.mean() - yc.mean())
        w = float(m.sum())            # weight by stratum size -> targets the ATE
        weighted_sum += w * eff
        total_weight += w
        var_sum += (w ** 2) * (yt.var(ddof=1) / len(yt) + yc.var(ddof=1) / len(yc))
        rows.append({"stratum": b, "n": int(m.sum()), "effect": round(eff, 4),
                     "n_treated": int(len(yt)), "n_control": int(len(yc))})

    if total_weight == 0:
        return EffectEstimate("stratification", float("nan"), None,
                              notes={"error": "no stratum had both arms"})

    ate = weighted_sum / total_weight
    se = float(np.sqrt(var_sum) / total_weight)
    skipped = sum(1 for r in rows if not np.isfinite(r["effect"]))
    return EffectEstimate(
        method=f"stratification ({n_strata} strata)",
        value=float(ate),
        std_error=se,
        notes={
            "per_stratum": rows,
            "strata_skipped": skipped,
            "warning": (
                f"{skipped} stratum/strata had no valid comparison — the "
                "estimate no longer describes the whole population."
            ) if skipped else None,
        },
    )


# ═════════════════════════════════════════════════════════════════════════════
# METHOD 2 — G-computation / standardisation. "Simulate the trial."
# ═════════════════════════════════════════════════════════════════════════════

def g_computation(
    X: np.ndarray,
    T: np.ndarray,
    Y: np.ndarray,
    model=None,
    n_bootstrap: int = 0,
    random_state: int = 0,
) -> EffectEstimate:
    """Fit one outcome model, then ask it to imagine both worlds.

    The recipe:
        1. Fit  mu(X, T)  =  E[Y | X, T]   on the real data.
        2. For EVERY patient, predict twice: once with T forced to 1, once
           with T forced to 0. (This is Pearl's do-operator, in code.)
        3. Average the difference across all patients.

    Step 2 is where the causal claim enters: we hand the model a row that never
    existed — the treated patient as if untreated. This is why the identifying
    assumptions matter. The model is extrapolating into a counterfactual, and
    only the backdoor criterion licenses us to believe it.

    THE FAILURE MODE THIS ESTIMATOR ACTUALLY HAS
    --------------------------------------------
    Note that ``T`` is appended as *one more feature* — this is an S-learner. It
    is the obvious way to write g-computation, and it has a specific, measurable
    weakness that is worth more than any amount of theory.

    A regularised learner spends its capacity where the signal is largest. In
    this cohort the outcome's *level* is driven by eGFR, age and baseline HbA1c;
    the treatment *contrast* is comparatively small. So the gradient booster
    gives ``TREATMENT`` only about 4% of its feature importance, barely splits on
    it, and shrinks the contrast toward zero:

        truth                      +0.9800
        gradient boosting          +0.8155   (attenuated by 0.16)
        the same GB, lr 0.3        +0.9156   (less shrinkage, less attenuation)
        LinearRegression           +0.9624   (T gets its own un-shrunk coefficient)

    That ordering is the surprise, and it is *not* a bug in this function. It is
    **regularisation bias** — the phenomenon double machine learning was invented
    to remove (Chernozhukov et al. 2018). The flexible model is better at
    predicting Y and worse at estimating the effect of T, because shrinkage
    applied to a nuisance parameter leaks into the estimand.

    :func:`aipw_ate` uses this *same* gradient booster and lands at +0.9786. The
    difference is not a better outcome model; it is the propensity-weighted
    residual correction, which cancels exactly this bias. So the honest lesson is
    the opposite of the intuitive one: do not reach for a more flexible model,
    reach for an estimator whose errors cancel.

    The same mechanism reappears in :func:`s_learner`, which is the worst
    performer on the CATE leaderboard for precisely this reason.

    ON THE STANDARD ERROR — a trap worth understanding
    --------------------------------------------------
    There is no closed-form standard error for g-computation, because the
    uncertainty lives inside a fitted machine-learning model. The tempting
    shortcut is to take the spread of the per-patient effects and divide by
    sqrt(n) — and it is *wrong*, because the spread of per-patient effects is
    **effect heterogeneity**, not sampling uncertainty. They are different
    quantities that happen to have compatible units.

    You can see the bug clearly with a linear no-interaction model: every
    patient gets the identical predicted effect, the spread is exactly 0, and
    the "confidence interval" collapses to a single point. A method cannot be
    infinitely certain because it was too simple to notice any variation.

    So by default we report ``std_error=None`` — an honest "not computed" beats
    a confident wrong number. Pass ``n_bootstrap=200`` for a real one: refit the
    whole procedure on resampled patients and look at how much the answer moves.
    """
    model = default_outcome_model() if model is None else clone(model)
    Xt = np.column_stack([X, T])
    model.fit(Xt, Y)

    n = len(Y)
    mu1 = model.predict(np.column_stack([X, np.ones(n)]))
    mu0 = model.predict(np.column_stack([X, np.zeros(n)]))
    per_patient = mu1 - mu0

    std_error = None
    notes: dict = {
        "se_method": "not computed — see docstring",
        "why_no_se": (
            "The spread of per-patient effects measures heterogeneity, not "
            "sampling error. Pass n_bootstrap for a valid SE."
        ),
    }

    if n_bootstrap > 0:
        # The honest way: resample patients, redo the ENTIRE procedure (refit
        # included), and measure how much the final number moves.
        rng = np.random.default_rng(random_state)
        boot = np.empty(n_bootstrap)
        for b in range(n_bootstrap):
            idx = rng.integers(0, n, n)
            m = clone(model)
            m.fit(np.column_stack([X[idx], T[idx]]), Y[idx])
            nb = len(idx)
            boot[b] = float(
                (
                    m.predict(np.column_stack([X[idx], np.ones(nb)]))
                    - m.predict(np.column_stack([X[idx], np.zeros(nb)]))
                ).mean()
            )
        std_error = float(boot.std(ddof=1))
        notes = {
            "se_method": f"nonparametric bootstrap, {n_bootstrap} resamples",
            "bootstrap_mean": float(boot.mean()),
        }

    return EffectEstimate(
        method=f"g-computation ({type(model).__name__})",
        value=float(per_patient.mean()),
        std_error=std_error,
        cate=per_patient,
        notes=notes,
    )


# ═════════════════════════════════════════════════════════════════════════════
# METHOD 3 — Propensity scores and IPW. "Undo the doctor's bias."
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class PropensityResult:
    scores: np.ndarray
    model: object
    cross_fitted: bool
    notes: dict = field(default_factory=dict)


def estimate_propensity(
    X: np.ndarray,
    T: np.ndarray,
    model=None,
    cross_fit: bool = False,
    n_folds: int = 5,
    clip: tuple[float, float] = PROPENSITY_CLIP,
    random_state: int = 0,
) -> PropensityResult:
    """P(T=1 | X) — each patient's chance of having been given the new drug.

    Read the propensity score as "how unsurprising was this prescription?".
    A patient with e(x) = 0.95 who received the drug tells us almost nothing:
    of course they got it. A patient with e(x) = 0.05 who received it anyway is
    hugely informative — they are the closest thing we have to a randomised
    comparison.

    `cross_fit=True` predicts each patient's score from a model that never saw
    that patient, which removes overfitting bias. This is the trick at the heart
    of Double ML.
    """
    model = default_treatment_model() if model is None else clone(model)

    if not cross_fit:
        model.fit(X, T)
        scores = model.predict_proba(X)[:, 1]
    else:
        scores = np.zeros(len(T), dtype=float)
        splitter = StratifiedKFold(n_folds, shuffle=True, random_state=random_state)
        for train_idx, test_idx in splitter.split(X, T):
            fold = clone(model)
            fold.fit(X[train_idx], T[train_idx])
            scores[test_idx] = fold.predict_proba(X[test_idx])[:, 1]
        model.fit(X, T)  # refit on everything, for later prediction on new patients

    n_clipped = int(np.sum((scores < clip[0]) | (scores > clip[1])))
    scores = np.clip(scores, *clip)

    return PropensityResult(
        scores=scores,
        model=model,
        cross_fitted=cross_fit,
        notes={
            "n_clipped": n_clipped,
            "clip": clip,
            "min": float(scores.min()),
            "max": float(scores.max()),
        },
    )


def ipw_ate(
    Y: np.ndarray,
    T: np.ndarray,
    propensity: np.ndarray,
    stabilise: bool = True,
) -> EffectEstimate:
    """Inverse Probability Weighting — rebuild a pseudo-randomised trial.

    Each patient is given a weight equal to 1 / (their probability of receiving
    the treatment they actually received):

        treated patient    ->  w = 1 / e(x)
        untreated patient  ->  w = 1 / (1 - e(x))

    A patient who was very unlikely to get the drug but got it anyway stands in
    for all the similar patients who didn't. Weighting them up manufactures a
    population in which treatment looks random.

    `stabilise=True` uses the Hajek form (divide by the sum of the weights
    rather than by n). It is what everyone actually uses, because the raw
    Horvitz-Thompson version has wild variance. We report both so the
    difference is visible rather than asserted.
    """
    e = propensity
    w1 = T / e
    w0 = (1 - T) / (1 - e)

    if stabilise:
        mean1 = float((w1 * Y).sum() / w1.sum())
        mean0 = float((w0 * Y).sum() / w0.sum())
        label = "IPW (stabilised / Hajek)"
    else:
        n = len(Y)
        mean1 = float((w1 * Y).sum() / n)
        mean0 = float((w0 * Y).sum() / n)
        label = "IPW (raw Horvitz-Thompson)"

    ate = mean1 - mean0

    # Influence-function standard error: the spread of each patient's individual
    # contribution to the estimate. Simple, and asymptotically correct.
    psi = w1 * (Y - mean1) - w0 * (Y - mean0)
    se = float(psi.std(ddof=1) / np.sqrt(len(Y)))

    weights = np.where(T == 1, w1, w0)
    return EffectEstimate(
        method=label,
        value=ate,
        std_error=se,
        notes={
            "max_weight": float(weights.max()),
            # Effective sample size: how many patients this analysis is really
            # standing on. If a handful of huge weights dominate, ESS collapses
            # and the estimate is fragile no matter what the CI says.
            "effective_sample_size": float(weights.sum() ** 2 / np.sum(weights ** 2)),
            "n": int(len(Y)),
        },
    )


@dataclass
class TrimReport:
    """What overlap trimming threw away, and what it cost you conceptually."""

    keep: np.ndarray            # boolean mask of retained patients
    bounds: tuple[float, float]
    n_before: int
    n_dropped: int
    dropped_profile: dict       # who we lost, on average

    @property
    def n_after(self) -> int:
        return self.n_before - self.n_dropped

    @property
    def fraction_kept(self) -> float:
        return self.n_after / self.n_before

    def __str__(self) -> str:
        lo, hi = self.bounds
        return (
            f"trim to e(x) in [{lo:.2f}, {hi:.2f}]: kept {self.n_after}/"
            f"{self.n_before} ({self.fraction_kept:.0%}), dropped "
            f"{self.n_dropped} patients with no honest comparison group"
        )


def trim_by_overlap(
    propensity: np.ndarray,
    bounds: tuple[float, float] = (0.1, 0.9),
    covariates: np.ndarray | None = None,
    covariate_names: list[str] | None = None,
) -> TrimReport:
    """Drop patients who had almost no chance of one of the two treatments.

    THE PROBLEM THIS SOLVES
    -----------------------
    IPW divides by e(x). A patient with e(x) = 0.005 who somehow got treated
    receives a weight of 200 — one person speaking for two hundred. The estimate
    stops being an average over your cohort and becomes a rumour about a handful
    of unusual patients. You can see it in the effective sample size: 4000
    patients can carry the statistical weight of 600.

    Trimming (Crump et al., 2009) refuses to guess. Patients outside the overlap
    region are removed from the analysis rather than extrapolated over.

    THE PRICE, WHICH MUST BE STATED OUT LOUD
    ----------------------------------------
    **Trimming changes the question you are answering.** Before trimming you
    were estimating the ATE for your whole cohort. After trimming you are
    estimating it for the subset in whom both drugs were realistically
    prescribed — a different, narrower population. The number gets more
    trustworthy and less general at the same time.

    That trade is often the right one clinically: the trimmed-away patients are
    usually those with a contraindication, for whom the question "what if we
    gave them the drug anyway?" was never a real clinical option. But it must be
    reported, not buried — hence the profile of who was dropped.

    Returns
    -------
    TrimReport
        A mask plus an audit trail. Apply it yourself (``X[rep.keep]``) so the
        subsetting stays visible in the calling code.
    """
    lo, hi = bounds
    keep = (propensity >= lo) & (propensity <= hi)

    profile: dict = {}
    if covariates is not None and (~keep).any():
        names = covariate_names or [f"x{i}" for i in range(covariates.shape[1])]
        dropped, kept = covariates[~keep], covariates[keep]
        for j, nm in enumerate(names):
            profile[nm] = {
                "dropped_mean": float(dropped[:, j].mean()),
                "kept_mean": float(kept[:, j].mean()),
            }

    return TrimReport(
        keep=keep,
        bounds=bounds,
        n_before=int(len(propensity)),
        n_dropped=int((~keep).sum()),
        dropped_profile=profile,
    )


# ═════════════════════════════════════════════════════════════════════════════
# METHOD 4 — AIPW / doubly robust. "Two chances to be right."
# ═════════════════════════════════════════════════════════════════════════════

def aipw_ate(
    X: np.ndarray,
    T: np.ndarray,
    Y: np.ndarray,
    outcome_model=None,
    treatment_model=None,
    cross_fit: bool = True,
    n_folds: int = 5,
    random_state: int = 0,
) -> EffectEstimate:
    """Augmented IPW — the workhorse. Combine the outcome model and the weights.

        psi_i = mu1(x_i) - mu0(x_i)                    <- g-computation part
                + T_i (Y_i - mu1(x_i)) / e(x_i)        <- correction, treated
                - (1-T_i)(Y_i - mu0(x_i)) / (1-e(x_i)) <- correction, untreated

        ATE = mean(psi)

    Why this is called *doubly robust*: the two correction terms are the
    residuals of the outcome model, re-weighted. If the outcome model is
    perfect, the residuals are zero and you are left with pure g-computation. If
    the propensity model is perfect, the weighting alone is unbiased and the
    outcome model's mistakes cancel out. **Either one being right is enough.**

    A further gift: because ATE is a plain average of the psi_i, the standard
    error is just their standard deviation over root-n. Valid confidence
    intervals, three lines of code, no bootstrap.
    """
    n = len(Y)
    outcome_model = default_outcome_model() if outcome_model is None else outcome_model
    prop = estimate_propensity(
        X, T, model=treatment_model, cross_fit=cross_fit,
        n_folds=n_folds, random_state=random_state,
    )
    e = prop.scores

    mu0 = np.zeros(n)
    mu1 = np.zeros(n)

    if cross_fit:
        # Every patient's mu is predicted by a model that never saw them, so
        # the residuals below are honest out-of-sample residuals.
        splitter = StratifiedKFold(n_folds, shuffle=True, random_state=random_state)
        for train_idx, test_idx in splitter.split(X, T):
            ctrl = train_idx[T[train_idx] == 0]
            trt = train_idx[T[train_idx] == 1]
            m0, m1 = clone(outcome_model), clone(outcome_model)
            m0.fit(X[ctrl], Y[ctrl])
            m1.fit(X[trt], Y[trt])
            mu0[test_idx] = m0.predict(X[test_idx])
            mu1[test_idx] = m1.predict(X[test_idx])
    else:
        m0, m1 = clone(outcome_model), clone(outcome_model)
        m0.fit(X[T == 0], Y[T == 0])
        m1.fit(X[T == 1], Y[T == 1])
        mu0, mu1 = m0.predict(X), m1.predict(X)

    psi = (
        (mu1 - mu0)
        + T * (Y - mu1) / e
        - (1 - T) * (Y - mu0) / (1 - e)
    )

    return EffectEstimate(
        method=f"AIPW / doubly robust{' (cross-fitted)' if cross_fit else ''}",
        value=float(psi.mean()),
        std_error=float(psi.std(ddof=1) / np.sqrt(n)),
        cate=psi,  # noisy per-patient pseudo-outcomes; useful as a CATE target
        notes={
            "cross_fitted": cross_fit,
            "propensity_clipped": prop.notes["n_clipped"],
            "mu0_mean": float(mu0.mean()),
            "mu1_mean": float(mu1.mean()),
        },
    )


# ═════════════════════════════════════════════════════════════════════════════
# ACT 7 — From an average to a PERSON. The metalearners.
# ═════════════════════════════════════════════════════════════════════════════
#
# The ATE answers "does this drug work?". A clinician needs "does it work for
# HER?". That is the CATE:  tau(x) = E[Y(1) - Y(0) | X = x].
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class CateModel:
    """A fitted model that predicts one patient's personal treatment effect."""

    name: str
    predict_effect: object          # callable: X -> per-row effect
    cate_in_sample: np.ndarray
    parts: dict = field(default_factory=dict)

    def effect(self, X: np.ndarray) -> np.ndarray:
        X = np.atleast_2d(np.asarray(X, dtype=float))
        return np.asarray(self.predict_effect(X)).ravel()

    def as_estimate(self) -> EffectEstimate:
        c = self.cate_in_sample
        return EffectEstimate(
            method=self.name,
            value=float(c.mean()),
            std_error=float(c.std(ddof=1) / np.sqrt(len(c))),
            cate=c,
            notes={"note": "SE is of the mean CATE, not of an individual effect."},
        )


def s_learner(X, T, Y, model=None) -> CateModel:
    """ONE model, with treatment as just another feature.

        mu(x, t)  ->  tau(x) = mu(x, 1) - mu(x, 0)

    Simplest possible thing. Its weakness is real and worth stating: a
    regulariser sees `T` as one column among seven and may shrink it toward
    zero, flattening genuine heterogeneity into a constant.
    """
    model = default_outcome_model() if model is None else clone(model)
    model.fit(np.column_stack([X, T]), Y)

    def predict(Xn):
        n = len(Xn)
        return (model.predict(np.column_stack([Xn, np.ones(n)]))
                - model.predict(np.column_stack([Xn, np.zeros(n)])))

    return CateModel("S-learner", predict, predict(X), {"model": model})


def t_learner(X, T, Y, model=None) -> CateModel:
    """TWO models, one per arm — the most intuitive CATE method.

        mu0 fitted on the untreated,  mu1 fitted on the treated
        tau(x) = mu1(x) - mu0(x)

    "What do patients like her look like on drug A? On drug B? Subtract."
    Its weakness is the mirror image of the S-learner's: with one arm much
    smaller, that arm's model is noisy, and the noise lands squarely in the
    difference.
    """
    model = default_outcome_model() if model is None else model
    m0, m1 = clone(model), clone(model)
    m0.fit(X[T == 0], Y[T == 0])
    m1.fit(X[T == 1], Y[T == 1])

    def predict(Xn):
        return m1.predict(Xn) - m0.predict(Xn)

    return CateModel("T-learner", predict, predict(X), {"mu0": m0, "mu1": m1})


def x_learner(X, T, Y, model=None, propensity_model=None) -> CateModel:
    """The X-learner (Künzel et al., 2019) — built for lopsided arms.

    Four steps:
      1. Fit mu0 and mu1, as in the T-learner.
      2. IMPUTE each patient's effect using the OTHER arm's model:
             treated   :  D1 = Y - mu0(x)   ("how much better than predicted?")
             untreated :  D0 = mu1(x) - Y   ("how much worse than predicted?")
      3. Fit tau1 on the treated's D1, and tau0 on the untreated's D0.
      4. Blend by propensity:  tau(x) = e(x)*tau0(x) + (1-e(x))*tau1(x)

    Step 4's weighting looks backwards until you see it: where e(x) is high
    almost everyone is treated, so mu1 is the well-estimated model, so the
    imputation that *relies* on mu1 — namely D0, giving tau0 — is the one to
    trust. Lean on whichever model had the most data.
    """
    model = default_outcome_model() if model is None else model
    m0, m1 = clone(model), clone(model)
    m0.fit(X[T == 0], Y[T == 0])
    m1.fit(X[T == 1], Y[T == 1])

    d1 = Y[T == 1] - m0.predict(X[T == 1])
    d0 = m1.predict(X[T == 0]) - Y[T == 0]

    tau1, tau0 = clone(model), clone(model)
    tau1.fit(X[T == 1], d1)
    tau0.fit(X[T == 0], d0)

    prop = estimate_propensity(X, T, model=propensity_model)
    ps_model = prop.model

    def predict(Xn):
        e = np.clip(ps_model.predict_proba(Xn)[:, 1], *PROPENSITY_CLIP)
        return e * tau0.predict(Xn) + (1 - e) * tau1.predict(Xn)

    return CateModel(
        "X-learner", predict, predict(X),
        {"mu0": m0, "mu1": m1, "tau0": tau0, "tau1": tau1, "propensity": ps_model},
    )


def dr_learner(X, T, Y, model=None, n_folds: int = 5, random_state: int = 0) -> CateModel:
    """DR-learner: regress the AIPW pseudo-outcomes on X.

    The neat observation that makes this work: the per-patient AIPW term psi_i
    is a noisy but *unbiased* estimate of that patient's own effect. So fitting
    an ordinary regression of psi on X smooths the noise away and leaves a CATE
    surface that inherits AIPW's double robustness.

    This is essentially what EconML's DML estimators do, in eight lines.
    """
    est = aipw_ate(X, T, Y, outcome_model=model, cross_fit=True,
                   n_folds=n_folds, random_state=random_state)
    pseudo = est.cate
    smoother = default_outcome_model() if model is None else clone(model)
    smoother.fit(X, pseudo)

    def predict(Xn):
        return smoother.predict(Xn)

    return CateModel("DR-learner (AIPW pseudo-outcomes)", predict, predict(X),
                     {"smoother": smoother, "aipw": est})


ALL_CATE_LEARNERS = {
    "S-learner": s_learner,
    "T-learner": t_learner,
    "X-learner": x_learner,
    "DR-learner": dr_learner,
}
