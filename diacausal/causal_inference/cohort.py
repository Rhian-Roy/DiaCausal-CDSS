"""Step (a): the causal dataset — a synthetic, India-calibrated cohort with known truth.

Plain English: we invent patients who are already on metformin and "give" each one of the
three add-on drugs the way doctors tend to (sicker patients more often get certain drugs —
confounding by indication). Because we invented them, we also know what WOULD have happened
under each of the other two drugs. Those hidden true answers are stored so we can grade our
methods; the estimators only ever see the observed columns.

Every number comes from data/params.yaml (with its source and status). None is typed here.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from diacausal_engine import ARMS, CONTRASTS
from diacausal_engine.config import Params
from diacausal_engine.dag import load_dag

BINARY = ("female", "ascvd", "hf", "hypo_history", "dka_history", "pancreatitis_history", "low_income")
CONTINUOUS = ("age", "duration_years", "hba1c", "egfr", "bmi")
# Columns only the simulator knows. observed_view() drops them.
TRUTH_PREFIXES = ("y_true_", "mu_true_", "e_true_", "wmu_true_", "w_true_", "hp_true_", "h_true_")
SECONDARY_STREAM = 17  # secondary outcomes use rng([seed, 17]): the primary cohort never changes


def _clip_normal(rng, mean, sd, lo, hi, n):
    return np.clip(rng.normal(mean, sd, n), lo, hi)


def draw_covariates(params: Params, n: int, rng: np.random.Generator) -> pd.DataFrame:
    """Patient details before any drug is chosen."""
    c = "generator.covariates"
    g = params.get
    age = _clip_normal(rng, g(f"{c}.age.mean"), g(f"{c}.age.sd"), g(f"{c}.age.min"), g(f"{c}.age.max"), n)
    female = rng.random(n) < g(f"{c}.female_share")
    duration = np.minimum(
        rng.gamma(g(f"{c}.duration_years.gamma_shape"), g(f"{c}.duration_years.gamma_scale"), n),
        g(f"{c}.duration_years.max"),
    )
    hba1c = np.minimum(
        g("generator.inclusion.hba1c_min")
        + rng.gamma(g(f"{c}.hba1c.gamma_shape"), g(f"{c}.hba1c.gamma_scale"), n),
        g(f"{c}.hba1c.max"),
    )
    egfr_mean = g(f"{c}.egfr.mean_at_55") + g(f"{c}.egfr.change_per_year_of_age") * (age - g(f"{c}.age.mean"))
    egfr = np.clip(
        rng.normal(egfr_mean, g(f"{c}.egfr.sd")), g("generator.inclusion.egfr_min"), g(f"{c}.egfr.max")
    )
    bmi = _clip_normal(rng, g(f"{c}.bmi.mean"), g(f"{c}.bmi.sd"), g(f"{c}.bmi.min"), g(f"{c}.bmi.max"), n)
    prev = params.group(f"{c}.prevalence")
    df = pd.DataFrame(
        {
            "age": np.round(age, 0),
            "female": female.astype(int),
            "duration_years": np.round(duration, 1),
            "hba1c": np.round(hba1c, 1),
            "egfr": np.round(egfr, 0),
            "bmi": np.round(bmi, 1),
        }
    )
    for name in ("ascvd", "hf", "hypo_history", "dka_history", "pancreatitis_history", "low_income"):
        df[name] = (rng.random(n) < prev[name]).astype(int)
    df["ckd"] = (df["egfr"] < g(f"{c}.ckd_egfr_below")).astype(int)
    df["t1d"] = 0  # cohort definition: type 2 diabetes only
    return df


def true_propensity(params: Params, df: pd.DataFrame) -> np.ndarray:
    """P(drug | patient) used to assign drugs: (n, 3) in ARMS order. DPP-4i is the reference."""
    centre = params.group("generator.assignment.centre")
    logits = np.zeros((len(df), len(ARMS)))
    for j, arm in enumerate(ARMS):
        if arm == "DPP4i":
            continue
        coefs = params.group(f"generator.assignment.{arm}")
        z = np.full(len(df), coefs.pop("intercept"), dtype=float)
        for var, beta in coefs.items():
            z += beta * (df[var].to_numpy(float) - centre.get(var, 0.0))
        logits[:, j] = z
    logits -= logits.max(axis=1, keepdims=True)
    p = np.exp(logits)
    return p / p.sum(axis=1, keepdims=True)


def true_expected_outcomes(params: Params, df: pd.DataFrame) -> np.ndarray:
    """Noise-free E[Y(a) | X] for each arm: (n, 3) in ARMS order, percentage points."""
    o = "generator.outcome"
    centre = params.group(f"{o}.centre")
    hba1c_c = df["hba1c"].to_numpy(float) - centre["hba1c"]
    egfr_c = (df["egfr"].to_numpy(float) - centre["egfr"]) / 10.0
    dur_c = df["duration_years"].to_numpy(float) - centre["duration_years"]
    common = (
        params.get(f"{o}.drift")
        + params.get(f"{o}.regression_to_mean") * hba1c_c
        + params.get(f"{o}.female") * df["female"].to_numpy(float)
    )
    out = np.empty((len(df), len(ARMS)))
    for j, arm in enumerate(ARMS):
        e = params.group(f"{o}.effects.{arm}")
        out[:, j] = (
            common
            + e["base"]
            + e["per_hba1c_pct"] * hba1c_c
            + e["per_10_egfr"] * egfr_c
            + e["per_duration_year"] * dur_c
        )
    return out


def true_secondary(params: Params, df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Noise-free truth for the secondary outcomes, each (n, 3) in ARMS order:
    expected 6-month weight change (kg) and the probability of any hypoglycaemia by 6 months."""
    w, h = "generator.secondary.weight", "generator.secondary.hypo"
    g = params.get
    bmi_c = df["bmi"].to_numpy(float) - g(f"{w}.centre_bmi")
    age_c = df["age"].to_numpy(float) - g("generator.assignment.centre.age")
    below = np.maximum(0.0, (g("generator.assignment.centre.egfr") - df["egfr"].to_numpy(float)) / 10.0)
    weight = np.empty((len(df), len(ARMS)))
    logit = np.empty((len(df), len(ARMS)))
    base_logit = (g(f"{h}.intercept") + g(f"{h}.hypo_history") * df["hypo_history"].to_numpy(float)
                  + g(f"{h}.age_per_year") * age_c + g(f"{h}.egfr_per_10_below_80") * below)
    for j, arm in enumerate(ARMS):
        weight[:, j] = g(f"{w}.drift") + g(f"{w}.{arm}.base") + g(f"{w}.{arm}.per_bmi") * bmi_c
        extra = g(f"{h}.su_extra_age_per_year") * age_c if arm == "SU" else 0.0
        logit[:, j] = base_logit + g(f"{h}.{arm}") + extra
    return weight, 1.0 / (1.0 + np.exp(-logit))


def generate_cohort(params: Params, n: int | None = None, seed: int = 0) -> pd.DataFrame:
    """One synthetic cohort: covariates, the drug received, the observed outcome, and the truth."""
    n = int(n or params.get("generator.n_patients"))
    rng = np.random.default_rng(seed)
    df = draw_covariates(params, n, rng)
    e = true_propensity(params, df)
    cum = e.cumsum(axis=1)
    idx = (rng.random(n)[:, None] > cum).sum(axis=1)
    mu = true_expected_outcomes(params, df)
    y_all = mu + rng.normal(0.0, params.get("generator.outcome.noise_sd"), (n, 1))
    df["treatment"] = np.array(ARMS)[idx]
    for j, arm in enumerate(ARMS):
        df[f"e_true_{arm}"] = e[:, j]
        df[f"mu_true_{arm}"] = mu[:, j]
        df[f"y_true_{arm}"] = y_all[:, j]
    df["y"] = y_all[np.arange(n), idx]
    # Secondary outcomes from their own stream (so the primary draws above are unchanged).
    rng2 = np.random.default_rng([seed, SECONDARY_STREAM])
    w_mu, h_p = true_secondary(params, df)
    w_all = w_mu + rng2.normal(0.0, params.get("generator.secondary.weight.noise_sd"), (n, len(ARMS)))
    h_all = (rng2.random((n, 1)) < h_p).astype(int)  # one shared uniform: potential outcomes are coupled
    for j, arm in enumerate(ARMS):
        df[f"wmu_true_{arm}"] = w_mu[:, j]
        df[f"w_true_{arm}"] = w_all[:, j]
        df[f"hp_true_{arm}"] = h_p[:, j]
        df[f"h_true_{arm}"] = h_all[:, j]
    df["weight_change_6m"] = np.round(w_all[np.arange(n), idx], 2)
    df["hypo_6m"] = h_all[np.arange(n), idx]
    return df


def observed_view(df: pd.DataFrame) -> pd.DataFrame:
    """What a real dataset would contain: no hidden truth columns."""
    return df[[c for c in df.columns if not c.startswith(TRUTH_PREFIXES)]].copy()


def features(params: Params, df: pd.DataFrame) -> np.ndarray:
    """The DAG's adjustment set as a numeric matrix (never a mediator, never the truth)."""
    cols = load_dag(params).adjustment_set
    return df[cols].to_numpy(float)


def treatment_index(df: pd.DataFrame) -> np.ndarray:
    return df["treatment"].map({a: i for i, a in enumerate(ARMS)}).to_numpy()


def true_population_effects(params: Params, seed: int = 12345) -> dict[str, float]:
    """True average outcome under each arm and true average contrasts, from a large draw."""
    n = int(params.get("generator.population_truth_n"))
    rng = np.random.default_rng(seed)
    mu = true_expected_outcomes(params, draw_covariates(params, n, rng))
    out = {arm: float(mu[:, j].mean()) for j, arm in enumerate(ARMS)}
    for a, b in CONTRASTS:
        out[f"{a}-{b}"] = out[a] - out[b]
    return out


def true_secondary_population(params: Params, seed: int = 12345) -> dict[str, float]:
    """True average weight change (kg) and hypoglycaemia risk under each arm, and their contrasts."""
    n = int(params.get("generator.population_truth_n"))
    df = draw_covariates(params, n, np.random.default_rng(seed))
    w, h = true_secondary(params, df)
    out: dict[str, float] = {}
    for name, m in (("weight", w), ("hypo", h)):
        for j, arm in enumerate(ARMS):
            out[f"{name}:{arm}"] = float(m[:, j].mean())
        for a, b in CONTRASTS:
            out[f"{name}:{a}-{b}"] = out[f"{name}:{a}"] - out[f"{name}:{b}"]
    return out


def load_dataset(path: Path | str, params: Params) -> pd.DataFrame:
    """Causal dataset ingestion for a real (de-identified) CSV later on.

    Needs the adjustment-set columns, `treatment` (one of SGLT2i, DPP4i, SU) and `y`
    (6-month HbA1c change, percentage points). Derives `ckd` from eGFR like the generator.
    """
    df = pd.read_csv(path)
    needed = set(load_dag(params).adjustment_set) | {"treatment", "y"}
    missing = needed - set(df.columns)
    if missing:
        raise ValueError(f"dataset is missing columns: {sorted(missing)}")
    bad = set(df["treatment"]) - set(ARMS)
    if bad:
        raise ValueError(f"unknown treatment values: {sorted(bad)}")
    df = df.dropna(subset=sorted(needed)).copy()
    df["ckd"] = (df["egfr"] < params.get("generator.covariates.ckd_egfr_below")).astype(int)
    if "t1d" not in df:
        df["t1d"] = 0
    return df
