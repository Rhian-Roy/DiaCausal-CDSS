"""
==============================================================================
DiaCausal CDSS — Causal Inference Implementation
==============================================================================
A comprehensive implementation of causal inference techniques for estimating
the effect of diabetes treatments (Metformin, SGLT2i, GLP-1RA) on HbA1c,
using synthetic EHR-like data.

Libraries:
    pip install dowhy econml pandas numpy scikit-learn matplotlib

This script covers:
    1. Synthetic EHR Data Generation (realistic diabetes patient cohort)
    2. DoWhy 4-Step Pipeline (Model → Identify → Estimate → Refute)
    3. EconML Metalearners (T-Learner, S-Learner, X-Learner)
    4. CATE Estimation (Personalized Treatment Effects)
    5. Visualization of Treatment Effect Heterogeneity
==============================================================================
"""

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from typing import Dict, Any

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: SYNTHETIC EHR DATA GENERATION
# ─────────────────────────────────────────────────────────────────────────────

def generate_diabetes_ehr_data(n_patients: int = 2000, seed: int = 42) -> pd.DataFrame:
    """
    Generate a synthetic diabetes EHR dataset that mimics real-world
    observational data with realistic confounding.

    Confounders:
        - Age, BMI, baseline_hba1c, eGFR all affect BOTH:
          (a) Which drug a doctor prescribes (treatment assignment)
          (b) The patient's HbA1c outcome

    Treatment:
        - Binary: 1 = SGLT2 inhibitor (new drug), 0 = Metformin (standard)

    Outcome:
        - hba1c_reduction: How much HbA1c dropped after 6 months (higher = better)

    True causal effect embedded:
        - Base ATE of SGLT2i = ~1.2% additional HbA1c reduction
        - Effect is HETEROGENEOUS: stronger for high-BMI patients (CATE)

    Returns:
        pd.DataFrame with patient records
    """
    np.random.seed(seed)

    # ── Patient Covariates (Confounders) ──
    age = np.random.normal(loc=58, scale=12, size=n_patients).clip(25, 85)
    bmi = np.random.normal(loc=31, scale=6, size=n_patients).clip(18, 55)
    baseline_hba1c = np.random.normal(loc=8.5, scale=1.5, size=n_patients).clip(6.0, 14.0)
    egfr = np.random.normal(loc=75, scale=20, size=n_patients).clip(15, 120)

    # Comorbidities (binary)
    has_cvd = np.random.binomial(1, p=0.3, size=n_patients)
    has_ckd = (egfr < 45).astype(int)  # CKD Stage 3b+ if eGFR < 45

    # ── Treatment Assignment (Biased — mimics doctor decision-making) ──
    # Doctors are MORE likely to prescribe SGLT2i to:
    #   - Younger patients (more tolerant of newer drugs)
    #   - Higher BMI (SGLT2i has weight loss benefit)
    #   - Better kidney function (contraindicated if eGFR too low)
    #   - Patients with CVD (cardioprotective benefit)
    logit = (
        -2.0
        - 0.02 * age          # Younger → more likely SGLT2i
        + 0.08 * bmi           # Higher BMI → more likely SGLT2i
        + 0.02 * egfr          # Better kidneys → more likely SGLT2i
        + 0.5  * has_cvd       # CVD → more likely SGLT2i (cardioprotective)
        + 0.1  * baseline_hba1c
    )
    propensity = 1 / (1 + np.exp(-logit))
    treatment = np.random.binomial(1, propensity)

    # ── Outcome: HbA1c Reduction (higher = more reduction = better) ──
    # True causal structure:
    #   hba1c_reduction = f(confounders) + TREATMENT_EFFECT * treatment + noise
    #
    # The treatment effect is HETEROGENEOUS (varies by patient):
    #   - Base effect: 1.2% reduction
    #   - Amplified for high BMI patients: extra 0.03 * (BMI - 30)
    #   - Reduced for low eGFR: penalty of 0.01 * (60 - eGFR) if eGFR < 60
    true_base_effect = 1.2
    effect_modifier_bmi = 0.03 * (bmi - 30)           # More benefit if overweight
    effect_modifier_egfr = np.where(egfr < 60, -0.01 * (60 - egfr), 0)  # Less if CKD

    true_cate = true_base_effect + effect_modifier_bmi + effect_modifier_egfr

    hba1c_reduction = (
        0.5                           # Baseline natural reduction
        + true_cate * treatment       # Causal treatment effect (heterogeneous)
        + 0.02 * baseline_hba1c       # Higher baseline → more room to drop
        - 0.01 * age                  # Older → slightly less responsive
        + 0.01 * bmi                  # BMI effect on natural outcome
        - 0.005 * (90 - egfr)         # Kidney function affects glucose metabolism
        + np.random.normal(0, 0.3, n_patients)  # Random noise
    )

    df = pd.DataFrame({
        "patient_id": range(1, n_patients + 1),
        "age": np.round(age, 1),
        "bmi": np.round(bmi, 1),
        "baseline_hba1c": np.round(baseline_hba1c, 1),
        "egfr": np.round(egfr, 1),
        "has_cvd": has_cvd,
        "has_ckd": has_ckd,
        "treatment_sglt2i": treatment,      # 1 = SGLT2i, 0 = Metformin
        "hba1c_reduction": np.round(hba1c_reduction, 3),
        "true_cate": np.round(true_cate, 3),  # Ground truth (hidden in real data)
    })

    return df


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: DoWhy 4-STEP CAUSAL INFERENCE PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

def run_dowhy_pipeline(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Execute the full DoWhy causal inference pipeline:
        Step 1: MODEL   — Define the causal graph (DAG)
        Step 2: IDENTIFY — Use graph theory to find the estimand
        Step 3: ESTIMATE — Compute the Average Treatment Effect (ATE)
        Step 4: REFUTE   — Test robustness of the estimate

    Args:
        df: Patient dataframe with treatment and outcome columns

    Returns:
        Dictionary with model, estimand, estimate, and refutation results
    """
    from dowhy import CausalModel

    print("=" * 70)
    print("  DoWhy 4-STEP CAUSAL INFERENCE PIPELINE")
    print("=" * 70)

    # ── STEP 1: MODEL — Define the Causal DAG ──
    # We declare which variables are confounders (common causes of
    # both treatment assignment and the outcome).
    print("\n[Step 1/4] MODELING — Defining the Causal DAG...")

    model = CausalModel(
        data=df,
        treatment="treatment_sglt2i",
        outcome="hba1c_reduction",
        common_causes=["age", "bmi", "baseline_hba1c", "egfr", "has_cvd", "has_ckd"],
        effect_modifiers=["bmi", "egfr"],  # Variables that modify the treatment effect
    )

    print("  ✓ DAG defined with 6 confounders and 2 effect modifiers")

    # ── STEP 2: IDENTIFY — Find the Estimand ──
    # DoWhy uses the backdoor criterion to determine WHAT we need to
    # adjust for to get an unbiased causal estimate.
    print("\n[Step 2/4] IDENTIFICATION — Finding the causal estimand...")

    identified_estimand = model.identify_effect(proceed_when_unidentifiable=True)
    print(f"  ✓ Estimand identified via: {identified_estimand.identifier}")
    print(f"  Backdoor variables: {identified_estimand.get_backdoor_variables()}")

    # ── STEP 3: ESTIMATE — Compute the ATE ──
    # We use multiple estimation methods and compare them.
    print("\n[Step 3/4] ESTIMATION — Computing Average Treatment Effect (ATE)...")

    # Method 1: Propensity Score Weighting (IPW)
    estimate_ipw = model.estimate_effect(
        identified_estimand,
        method_name="backdoor.propensity_score_weighting",
        method_params={"weighting_scheme": "ips_weight"}
    )
    print(f"\n  Method: Inverse Propensity Weighting (IPW)")
    print(f"  ► Estimated ATE = {estimate_ipw.value:.4f}")
    print(f"  ► True ATE ≈ 1.2000 (base effect we embedded)")

    # Method 2: Linear Regression
    estimate_lr = model.estimate_effect(
        identified_estimand,
        method_name="backdoor.linear_regression"
    )
    print(f"\n  Method: Linear Regression (OLS)")
    print(f"  ► Estimated ATE = {estimate_lr.value:.4f}")

    # ── STEP 4: REFUTE — Robustness Checks ──
    print("\n[Step 4/4] REFUTATION — Testing robustness of the estimate...")

    # Refutation 1: Add a random (irrelevant) confounder
    # If estimate changes significantly → model is fragile
    refute_random = model.refute_estimate(
        identified_estimand,
        estimate_ipw,
        method_name="random_common_cause",
        random_seed=42
    )
    print(f"\n  Test 1: Random Common Cause")
    print(f"  ► New estimate after adding random confounder: {refute_random.new_effect:.4f}")
    print(f"  ► p-value: {refute_random.refutation_result.get('p_value', 'N/A') if isinstance(refute_random.refutation_result, dict) else 'N/A'}")

    # Refutation 2: Placebo treatment (replace real treatment with random)
    # Effect SHOULD drop to ~0
    refute_placebo = model.refute_estimate(
        identified_estimand,
        estimate_ipw,
        method_name="placebo_treatment_refuter",
        placebo_type="permute",
        random_seed=42
    )
    print(f"\n  Test 2: Placebo Treatment (should be ~0)")
    print(f"  ► Placebo effect: {refute_placebo.new_effect:.4f}")

    # Refutation 3: Data subset test (re-estimate on random 80% subset)
    refute_subset = model.refute_estimate(
        identified_estimand,
        estimate_ipw,
        method_name="data_subset_refuter",
        subset_fraction=0.8,
        random_seed=42
    )
    print(f"\n  Test 3: Data Subset (80% of data)")
    print(f"  ► Subset estimate: {refute_subset.new_effect:.4f}")

    print("\n" + "=" * 70)
    print("  DoWhy Pipeline Complete")
    print("=" * 70)

    return {
        "model": model,
        "estimand": identified_estimand,
        "estimate_ipw": estimate_ipw,
        "estimate_lr": estimate_lr,
        "refutation_random": refute_random,
        "refutation_placebo": refute_placebo,
        "refutation_subset": refute_subset,
    }


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: EconML METALEARNERS — PERSONALIZED TREATMENT EFFECTS (CATE)
# ─────────────────────────────────────────────────────────────────────────────

def run_econml_cate_estimation(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Estimate Conditional Average Treatment Effects (CATE) using EconML
    metalearners. This is the core of personalized treatment recommendations.

    Metalearners used:
        - T-Learner: Trains separate outcome models for treated/control
        - S-Learner: Trains a single model with treatment as a feature
        - X-Learner: Cross-fits imputed treatment effects (best for imbalanced data)

    Args:
        df: Patient dataframe

    Returns:
        Dictionary with CATE estimates from each metalearner
    """
    from econml.metalearners import TLearner, SLearner, XLearner
    from sklearn.ensemble import GradientBoostingRegressor, GradientBoostingClassifier

    print("\n" + "=" * 70)
    print("  EconML METALEARNERS — CATE ESTIMATION")
    print("=" * 70)

    # Prepare data matrices
    feature_cols = ["age", "bmi", "baseline_hba1c", "egfr", "has_cvd", "has_ckd"]
    X = df[feature_cols].values          # Patient covariates
    T = df["treatment_sglt2i"].values    # Treatment assignment
    Y = df["hba1c_reduction"].values     # Outcome
    true_cate = df["true_cate"].values   # Ground truth (for validation only)

    results = {}

    # ── T-Learner ──
    # Trains μ₀(x) on control group and μ₁(x) on treated group
    # CATE(x) = μ₁(x) − μ₀(x)
    print("\n[1/3] T-Learner (Two separate models)...")
    t_learner = TLearner(
        models=GradientBoostingRegressor(n_estimators=100, max_depth=4, random_state=42)
    )
    t_learner.fit(Y, T, X=X)
    cate_t = t_learner.effect(X).flatten()
    mae_t = np.mean(np.abs(cate_t - true_cate))
    print(f"  ► Mean estimated CATE: {cate_t.mean():.4f}")
    print(f"  ► MAE vs. true CATE:   {mae_t:.4f}")
    results["t_learner"] = {"model": t_learner, "cate": cate_t, "mae": mae_t}

    # ── S-Learner ──
    # Trains a single model μ(x, t) on all data
    # CATE(x) = μ(x, 1) − μ(x, 0)
    print("\n[2/3] S-Learner (Single model with treatment as feature)...")
    s_learner = SLearner(
        overall_model=GradientBoostingRegressor(n_estimators=100, max_depth=4, random_state=42)
    )
    s_learner.fit(Y, T, X=X)
    cate_s = s_learner.effect(X).flatten()
    mae_s = np.mean(np.abs(cate_s - true_cate))
    print(f"  ► Mean estimated CATE: {cate_s.mean():.4f}")
    print(f"  ► MAE vs. true CATE:   {mae_s:.4f}")
    results["s_learner"] = {"model": s_learner, "cate": cate_s, "mae": mae_s}

    # ── X-Learner ──
    # Cross-fits imputed treatment effects — best when treatment groups are imbalanced
    # Uses propensity-weighted combination of two CATE estimates
    print("\n[3/3] X-Learner (Cross-fitting with propensity weighting)...")
    x_learner = XLearner(
        models=GradientBoostingRegressor(n_estimators=100, max_depth=4, random_state=42),
        propensity_model=GradientBoostingClassifier(n_estimators=50, max_depth=3, random_state=42)
    )
    x_learner.fit(Y, T, X=X)
    cate_x = x_learner.effect(X).flatten()
    mae_x = np.mean(np.abs(cate_x - true_cate))
    print(f"  ► Mean estimated CATE: {cate_x.mean():.4f}")
    print(f"  ► MAE vs. true CATE:   {mae_x:.4f}")
    results["x_learner"] = {"model": x_learner, "cate": cate_x, "mae": mae_x}

    # ── Summary ──
    print("\n" + "-" * 50)
    print("  CATE Estimation Summary")
    print("-" * 50)
    print(f"  {'Learner':<12} {'Mean CATE':>12} {'MAE':>10}")
    print(f"  {'─' * 12} {'─' * 12} {'─' * 10}")
    print(f"  {'T-Learner':<12} {cate_t.mean():>12.4f} {mae_t:>10.4f}")
    print(f"  {'S-Learner':<12} {cate_s.mean():>12.4f} {mae_s:>10.4f}")
    print(f"  {'X-Learner':<12} {cate_x.mean():>12.4f} {mae_x:>10.4f}")
    print(f"  {'True ATE':<12} {true_cate.mean():>12.4f} {'—':>10}")
    print("-" * 50)

    best = min(results.items(), key=lambda x: x[1]["mae"])
    print(f"\n  ★ Best performer: {best[0]} (MAE = {best[1]['mae']:.4f})")

    return results


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: PERSONALIZED TREATMENT RECOMMENDATION (CDSS SIMULATION)
# ─────────────────────────────────────────────────────────────────────────────

def simulate_cdss_recommendation(
    cate_model,
    feature_cols: list,
    patient_data: Dict[str, float]
) -> Dict[str, Any]:
    """
    Simulate how the DiaCausal CDSS would use the trained CATE model
    to generate a personalized treatment recommendation for a single patient.

    This is exactly what the /api/v1/cdss/causal-estimate endpoint would do.

    Args:
        cate_model: A trained EconML metalearner
        feature_cols: List of feature column names
        patient_data: Dictionary with patient's clinical values

    Returns:
        Recommendation dictionary with CATE estimate and clinical guidance
    """
    print("\n" + "=" * 70)
    print("  DiaCausal CDSS — PERSONALIZED RECOMMENDATION")
    print("=" * 70)

    # Build patient feature vector
    X_patient = np.array([[patient_data[col] for col in feature_cols]])

    # Estimate the CATE for this specific patient
    estimated_cate = cate_model.effect(X_patient).flatten()[0]

    # ── Clinical Guardrail Checks ──
    guardrail_flags = []
    recommendation_status = "APPROVED"

    # Rule 1: Metformin contraindicated if eGFR < 30
    if patient_data.get("egfr", 100) < 30:
        guardrail_flags.append(
            "⚠ CONTRAINDICATION: eGFR < 30 mL/min — Metformin is contraindicated (risk of lactic acidosis). "
            "SGLT2i should also be used with caution."
        )
        recommendation_status = "FLAGGED — REQUIRES SPECIALIST REVIEW"

    # Rule 2: SGLT2i caution if recurrent UTIs or DKA history
    # (simplified — in production this would check comorbidities_json)

    # Rule 3: Minimal benefit threshold
    if estimated_cate < 0.3:
        guardrail_flags.append(
            "ℹ LOW EFFECT: Estimated benefit is marginal (< 0.3% HbA1c reduction). "
            "Consider alternative therapies or combination therapy."
        )

    # ── Format Output ──
    print(f"\n  Patient Profile:")
    for key, val in patient_data.items():
        print(f"    {key:>20s}: {val}")

    print(f"\n  ┌─────────────────────────────────────────────────┐")
    print(f"  │  Estimated CATE (SGLT2i vs. Metformin):         │")
    print(f"  │  ► {estimated_cate:+.4f}% additional HbA1c reduction    │")
    print(f"  │  Status: {recommendation_status:<39s} │")
    print(f"  └─────────────────────────────────────────────────┘")

    if guardrail_flags:
        print(f"\n  Safety Guardrail Alerts:")
        for flag in guardrail_flags:
            print(f"    {flag}")

    if estimated_cate > 0.8:
        clinical_guidance = (
            "STRONG RECOMMENDATION: SGLT2 inhibitor is estimated to provide substantial "
            f"additional benefit ({estimated_cate:.2f}% HbA1c reduction) for this patient profile. "
            "This aligns with ADA 2025 guidelines recommending SGLT2i for patients with "
            "high BMI and preserved renal function."
        )
    elif estimated_cate > 0.3:
        clinical_guidance = (
            "MODERATE RECOMMENDATION: SGLT2 inhibitor shows moderate benefit "
            f"({estimated_cate:.2f}% additional HbA1c reduction). Consider patient preference "
            "and cost factors."
        )
    else:
        clinical_guidance = (
            "WEAK/NO RECOMMENDATION: Estimated benefit of SGLT2i over Metformin is minimal "
            f"({estimated_cate:.2f}%). Standard Metformin therapy may be sufficient."
        )

    print(f"\n  Clinical Guidance:")
    print(f"    {clinical_guidance}")

    return {
        "patient_data": patient_data,
        "estimated_cate": estimated_cate,
        "recommendation_status": recommendation_status,
        "guardrail_flags": guardrail_flags,
        "clinical_guidance": clinical_guidance,
    }


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: VISUALIZATION — TREATMENT EFFECT HETEROGENEITY
# ─────────────────────────────────────────────────────────────────────────────

def plot_cate_analysis(df: pd.DataFrame, cate_estimates: np.ndarray, save_path: str):
    """
    Generate publication-quality visualizations of treatment effect heterogeneity.

    Creates a 2x2 figure:
        1. CATE Distribution (histogram)
        2. CATE vs. BMI (scatter — shows effect modification)
        3. CATE vs. eGFR (scatter — shows kidney function impact)
        4. Estimated vs. True CATE (calibration scatter)

    Args:
        df: Patient dataframe
        cate_estimates: Array of estimated CATE values from best metalearner
        save_path: File path to save the figure
    """
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(
        "DiaCausal CDSS — Treatment Effect Heterogeneity Analysis\n"
        "(SGLT2 Inhibitor vs. Metformin on HbA1c Reduction)",
        fontsize=14, fontweight="bold", y=1.02
    )

    colors = {
        "primary": "#0D9488",    # Teal accent
        "secondary": "#0F172A",  # Deep clinical slate
        "alert": "#DC2626",      # Warning red
        "success": "#16A34A",    # Success green
        "amber": "#D97706",      # Caution amber
    }

    # ── Plot 1: CATE Distribution ──
    ax1 = axes[0, 0]
    ax1.hist(cate_estimates, bins=40, color=colors["primary"], alpha=0.7, edgecolor="white")
    ax1.axvline(x=cate_estimates.mean(), color=colors["alert"], linestyle="--", linewidth=2,
                label=f"Mean CATE = {cate_estimates.mean():.3f}")
    ax1.axvline(x=1.2, color=colors["amber"], linestyle=":", linewidth=2,
                label="True Base ATE = 1.200")
    ax1.set_xlabel("Estimated CATE (% HbA1c Reduction)")
    ax1.set_ylabel("Number of Patients")
    ax1.set_title("Distribution of Personalized Treatment Effects")
    ax1.legend(fontsize=9)

    # ── Plot 2: CATE vs BMI (Effect Modifier) ──
    ax2 = axes[0, 1]
    scatter2 = ax2.scatter(df["bmi"], cate_estimates, c=cate_estimates, cmap="RdYlGn",
                           s=8, alpha=0.6, edgecolors="none")
    ax2.set_xlabel("BMI (kg/m²)")
    ax2.set_ylabel("Estimated CATE")
    ax2.set_title("CATE vs. BMI (Effect Modifier)")
    # Add trend line
    z = np.polyfit(df["bmi"], cate_estimates, 1)
    p = np.poly1d(z)
    bmi_range = np.linspace(df["bmi"].min(), df["bmi"].max(), 100)
    ax2.plot(bmi_range, p(bmi_range), color=colors["alert"], linewidth=2, linestyle="--",
             label=f"Trend: slope={z[0]:.4f}")
    ax2.legend(fontsize=9)
    plt.colorbar(scatter2, ax=ax2, label="CATE")

    # ── Plot 3: CATE vs eGFR ──
    ax3 = axes[1, 0]
    scatter3 = ax3.scatter(df["egfr"], cate_estimates, c=df["has_ckd"], cmap="coolwarm",
                           s=8, alpha=0.6, edgecolors="none")
    ax3.axvline(x=45, color=colors["alert"], linestyle="--", alpha=0.7,
                label="CKD Stage 3b threshold (eGFR=45)")
    ax3.axvline(x=30, color=colors["alert"], linestyle="-", alpha=0.9,
                label="Metformin contraindication (eGFR=30)")
    ax3.set_xlabel("eGFR (mL/min/1.73m²)")
    ax3.set_ylabel("Estimated CATE")
    ax3.set_title("CATE vs. Kidney Function (eGFR)")
    ax3.legend(fontsize=8)

    # ── Plot 4: Estimated vs True CATE (Calibration) ──
    ax4 = axes[1, 1]
    true_cate = df["true_cate"].values
    ax4.scatter(true_cate, cate_estimates, s=8, alpha=0.4, color=colors["primary"],
                edgecolors="none")
    # Perfect calibration line
    cate_range = [min(true_cate.min(), cate_estimates.min()),
                  max(true_cate.max(), cate_estimates.max())]
    ax4.plot(cate_range, cate_range, color=colors["alert"], linewidth=2, linestyle="--",
             label="Perfect Calibration")
    ax4.set_xlabel("True CATE (Ground Truth)")
    ax4.set_ylabel("Estimated CATE")
    ax4.set_title("Model Calibration: Estimated vs. True CATE")
    correlation = np.corrcoef(true_cate, cate_estimates)[0, 1]
    ax4.legend(fontsize=9, title=f"Pearson r = {correlation:.3f}")

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    print(f"\n  📊 Visualization saved to: {save_path}")
    plt.close()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: DOUBLE MACHINE LEARNING (DML) — ADVANCED ESTIMATION
# ─────────────────────────────────────────────────────────────────────────────

def run_dml_estimation(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Double/Debiased Machine Learning (DML) estimation using EconML.

    DML is the state-of-the-art method for CATE estimation because:
        1. It is robust to model misspecification (doubly robust)
        2. It provides valid confidence intervals
        3. It uses cross-fitting to avoid overfitting bias

    This is what the production CDSS Causal Engine should use.

    Args:
        df: Patient dataframe

    Returns:
        DML results with CATE estimates and confidence intervals
    """
    from econml.dml import LinearDML, CausalForestDML
    from sklearn.ensemble import GradientBoostingRegressor, GradientBoostingClassifier

    print("\n" + "=" * 70)
    print("  DOUBLE MACHINE LEARNING (DML) — ADVANCED CATE ESTIMATION")
    print("=" * 70)

    feature_cols = ["age", "bmi", "baseline_hba1c", "egfr", "has_cvd", "has_ckd"]
    X = df[feature_cols].values
    T = df["treatment_sglt2i"].values  # 1D for discrete_treatment=True
    Y = df["hba1c_reduction"].values
    W = X  # Confounders to partial out

    # ── Linear DML ──
    # Assumes the CATE is a linear function of X
    # discrete_treatment=True tells EconML that treatment is binary,
    # so it uses a classifier for the treatment model internally.
    print("\n[1/2] Linear DML...")
    linear_dml = LinearDML(
        model_y=GradientBoostingRegressor(n_estimators=100, max_depth=4, random_state=42),
        model_t=GradientBoostingClassifier(n_estimators=100, max_depth=4, random_state=42),
        discrete_treatment=True,
        random_state=42,
        cv=3
    )
    linear_dml.fit(Y, T, X=X, W=W)
    cate_linear = linear_dml.effect(X).flatten()
    print(f"  ► Mean CATE:  {cate_linear.mean():.4f}")
    print(f"  ► ATE:        {linear_dml.ate(X):.4f}")

    # Get confidence intervals for ATE
    ate_inf = linear_dml.ate_inference(X)
    ci_low, ci_high = ate_inf.conf_int_mean()  # Returns tuple of two scalars
    print(f"  ► ATE 95% CI: [{float(ci_low):.4f}, {float(ci_high):.4f}]")
    try:
        pval = float(ate_inf.pvalue())
        print(f"  ► p-value:    {pval:.6f}")
    except Exception:
        print("  ► p-value:    N/A")

    # ── Causal Forest DML ──
    # Non-parametric CATE estimation using random forests
    # Best for discovering complex treatment effect heterogeneity
    print("\n[2/2] Causal Forest DML...")
    cf_dml = CausalForestDML(
        model_y=GradientBoostingRegressor(n_estimators=100, max_depth=4, random_state=42),
        model_t=GradientBoostingClassifier(n_estimators=100, max_depth=4, random_state=42),
        discrete_treatment=True,
        n_estimators=200,
        random_state=42,
        cv=3
    )
    cf_dml.fit(Y, T, X=X, W=W)
    cate_cf = cf_dml.effect(X).flatten()
    true_cate = df["true_cate"].values

    mae_linear = np.mean(np.abs(cate_linear - true_cate))
    mae_cf = np.mean(np.abs(cate_cf - true_cate))

    print(f"  ► Mean CATE:  {cate_cf.mean():.4f}")
    print(f"  ► MAE vs true CATE: {mae_cf:.4f}")

    print("\n" + "-" * 50)
    print("  DML Summary")
    print("-" * 50)
    print(f"  {'Method':<20} {'Mean CATE':>12} {'MAE':>10}")
    print(f"  {'─' * 20} {'─' * 12} {'─' * 10}")
    print(f"  {'Linear DML':<20} {cate_linear.mean():>12.4f} {mae_linear:>10.4f}")
    print(f"  {'Causal Forest DML':<20} {cate_cf.mean():>12.4f} {mae_cf:>10.4f}")
    print(f"  {'True ATE':<20} {true_cate.mean():>12.4f} {'—':>10}")
    print("-" * 50)

    return {
        "linear_dml": {"model": linear_dml, "cate": cate_linear, "mae": mae_linear},
        "causal_forest": {"model": cf_dml, "cate": cate_cf, "mae": mae_cf},
    }


# ─────────────────────────────────────────────────────────────────────────────
# MAIN EXECUTION
# ─────────────────────────────────────────────────────────────────────────────

def main():
    """
    Main execution pipeline — runs the full causal inference demonstration.
    """
    print("\n" + "█" * 70)
    print("  DiaCausal CDSS — CAUSAL INFERENCE IMPLEMENTATION")
    print("  Estimating Treatment Effects for Diabetes Management")
    print("█" * 70)

    # ── 1. Generate Data ──
    print("\n\n📊 GENERATING SYNTHETIC DIABETES EHR DATA...")
    df = generate_diabetes_ehr_data(n_patients=2000)
    print(f"  Generated {len(df)} patient records")
    print(f"  Treatment distribution: {df['treatment_sglt2i'].value_counts().to_dict()}")
    print(f"  Mean HbA1c reduction (treated):   {df[df['treatment_sglt2i']==1]['hba1c_reduction'].mean():.3f}")
    print(f"  Mean HbA1c reduction (control):    {df[df['treatment_sglt2i']==0]['hba1c_reduction'].mean():.3f}")
    print(f"  Naive difference (BIASED):         {df[df['treatment_sglt2i']==1]['hba1c_reduction'].mean() - df[df['treatment_sglt2i']==0]['hba1c_reduction'].mean():.3f}")
    print(f"  True ATE (ground truth):           {df['true_cate'].mean():.3f}")

    # Save synthetic data for reference
    csv_path = "/Users/rhor/FCRIT/Major Project/Datasets/synthetic_diabetes_ehr.csv"
    df.to_csv(csv_path, index=False)
    print(f"\n  💾 Synthetic data saved to: {csv_path}")

    # ── 2. DoWhy Pipeline ──
    print("\n")
    dowhy_results = run_dowhy_pipeline(df)

    # ── 3. EconML Metalearners ──
    print("\n")
    econml_results = run_econml_cate_estimation(df)

    # ── 4. DML Advanced Estimation ──
    print("\n")
    dml_results = run_dml_estimation(df)

    # ── 5. Visualization ──
    print("\n\n📈 GENERATING VISUALIZATIONS...")
    best_learner_name = min(econml_results.items(), key=lambda x: x[1]["mae"])[0]
    best_cate = econml_results[best_learner_name]["cate"]
    plot_path = "/Users/rhor/FCRIT/Major Project/cate_analysis.png"
    plot_cate_analysis(df, best_cate, save_path=plot_path)

    # ── 6. CDSS Simulation — Example Patient Recommendations ──
    feature_cols = ["age", "bmi", "baseline_hba1c", "egfr", "has_cvd", "has_ckd"]

    # Use the best metalearner's model for recommendations
    best_model = econml_results[best_learner_name]["model"]

    # Patient A: Young, obese, good kidneys → should strongly benefit from SGLT2i
    print("\n\n" + "━" * 70)
    print("  PATIENT CASE STUDIES")
    print("━" * 70)

    simulate_cdss_recommendation(best_model, feature_cols, {
        "age": 45.0, "bmi": 38.0, "baseline_hba1c": 9.2,
        "egfr": 85.0, "has_cvd": 0.0, "has_ckd": 0.0
    })

    # Patient B: Elderly, normal BMI, low eGFR → marginal benefit, safety flags
    simulate_cdss_recommendation(best_model, feature_cols, {
        "age": 72.0, "bmi": 25.0, "baseline_hba1c": 7.8,
        "egfr": 28.0, "has_cvd": 1.0, "has_ckd": 1.0
    })

    # Patient C: Middle-aged, moderate BMI, moderate kidney function
    simulate_cdss_recommendation(best_model, feature_cols, {
        "age": 55.0, "bmi": 32.0, "baseline_hba1c": 8.5,
        "egfr": 55.0, "has_cvd": 0.0, "has_ckd": 0.0
    })

    print("\n\n" + "█" * 70)
    print("  IMPLEMENTATION COMPLETE")
    print("  Files generated:")
    print(f"    📄 {csv_path}")
    print(f"    📊 {plot_path}")
    print("█" * 70 + "\n")


if __name__ == "__main__":
    main()
