"""
ACT 8 — Where the two halves meet. The reason this project has two halves.
=========================================================================

Everything up to here has been one half or the other. This file is the join, and
it is the whole thesis of the project in one function.

--------------------------------------------------------------------------------
THE ARGUMENT, IN THREE RECOMMENDATIONS FOR THE SAME PATIENT
--------------------------------------------------------------------------------
Take Mrs R: 68, BMI 34, HbA1c 9.1%, eGFR 46, established heart disease.

The population average effect of the drug is **+0.93 HbA1c points** — it helps.
Her true individual effect, which we know because we authored it, is **-0.76** —
it harms. Everything below turns on that gap.

    RAG ALONE
        "Guidelines recommend considering an SGLT2 inhibitor in patients with
         established cardiovascular disease."

        True, cited, and population-level. It is the same sentence for every
        patient with heart disease. It cannot tell you that THIS patient's
        kidneys are too far gone for the glucose-lowering mechanism to work.

    CAUSAL ALONE
        "Estimated effect: about -0.7 HbA1c points."

        Personal, and unusable. Why? Says who? On what evidence? A clinician
        cannot act on a number with no provenance, and should not.

    BOTH
        "For this patient the model estimates SGLT2i gives about 0.7 points LESS
         HbA1c reduction than metformin — worse than metformin, despite being
         better on population average — because eGFR 46 limits the renal
         mechanism the drug depends on [ADA, p.184]. However, her established
         cardiovascular disease is an independent indication on outcomes rather
         than glycaemia [ADA, p.181], which this model does not measure. Discuss
         both."

        Personalised, cited, and honest about its own scope.

That third answer is what neither half can produce alone, and it is why the
project is built the way it is.

--------------------------------------------------------------------------------
THE PIPELINE
--------------------------------------------------------------------------------
    patient ──> CATE model ──────────> personal effect estimate
            │                                    │
            ├──> question builder ──> RAG ──> cited guideline passages
            │                                    │
            └──> guardrails ─────────────────────┤
                                                 v
                                        recommendation card

The guardrails sit LAST and can veto everything upstream. That ordering is the
safety property: no amount of model confidence can talk its way past a
contraindication.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import guardrails
from .data import COVARIATES, authored_cate

#: Four patients chosen to make the argument. Each one breaks a different
#: assumption a simpler system would make, and — deliberately — each one comes
#: back with a DIFFERENT guardrail verdict: HOLD, APPROVED, BLOCKED, CAUTION.
#:
#: Their BMI and eGFR values are not arbitrary. They were solved backwards out of
#: the authored effect function in `data.authored_cate` so that each patient
#: lands in the region that demonstrates its lesson: Mrs R just above the renal
#: warning line but well into genuine harm, Ms U within a rounding error of zero,
#: Mr T below the contraindication threshold. Choosing them by hand and then
#: checking the model against the truth is the only way to know the demo shows
#: what it claims to show.
DEMO_PATIENTS: dict[str, dict] = {
    "Mrs R — the patient the population average gets WRONG": {
        "age": 68, "bmi": 34.0, "baseline_hba1c": 9.1, "egfr": 46.0,
        "has_cvd": 1, "has_ckd": 0,
        "story": (
            "The flagship case, and the reason this project exists. On population "
            "average this drug HELPS — about +0.93 HbA1c points. Her BMI argues "
            "for it too. But at eGFR 46 the renal mechanism the drug depends on "
            "has largely failed, and the true effect for her is NEGATIVE: the "
            "drug is worse than metformin for her glycaemic control. Any tool "
            "reasoning from the average recommends it. Ours does not. And then it "
            "adds the thing a naive 'don't give it' would miss — her established "
            "heart disease is an independent reason to use the drug anyway, for a "
            "benefit this model does not measure. Nothing about this patient is "
            "simple, and a single number would hide all of it."
        ),
    },
    "Mr S — the clear yes": {
        "age": 54, "bmi": 38.5, "baseline_hba1c": 8.7, "egfr": 92.0,
        "has_cvd": 0, "has_ckd": 0,
        "story": (
            "Heavy, good kidney function, moderately raised HbA1c. Every gradient "
            "points the same way and the model predicts a large benefit. Worth "
            "showing because a CDSS must be unremarkable in the easy cases to be "
            "trusted in the hard ones — a system that flags everything is a "
            "system nobody reads."
        ),
    },
    "Mr T — the veto, and the model being wrong": {
        "age": 77, "bmi": 26.0, "baseline_hba1c": 8.2, "egfr": 24.0,
        "has_cvd": 1, "has_ckd": 1,
        "story": (
            "Advanced renal impairment. Two things happen here and both matter. "
            "First, the guardrail refuses to issue a recommendation at all, "
            "because metformin is contraindicated below eGFR 30 and SGLT2i "
            "glucose-lowering is minimal there — neither arm of our comparison "
            "is appropriate, so the honest output is 'refer', not 'pick one'. "
            "Second, look at the model error: this patient sits in the sparse "
            "tail of the training data and the estimate is off by around two "
            "whole HbA1c points. The safety layer caught a bad estimate WITHOUT "
            "needing to know it was bad. That is the entire argument for putting "
            "hard rules above a statistical model rather than inside it."
        ),
    },
    "Ms U — a coin toss, honestly reported": {
        "age": 61, "bmi": 29.0, "baseline_hba1c": 7.6, "egfr": 55.0,
        "has_cvd": 0, "has_ckd": 0,
        "story": (
            "Her BMI pushes the benefit up and her eGFR pulls it down, and the two "
            "very nearly cancel: the true effect is within a rounding error of "
            "zero. The valuable behaviour here is refusing to manufacture a "
            "preference from noise. 'These are equivalent — decide on cost, "
            "tolerability and preference' is a real answer, and a better one than "
            "a spurious ranking that would be reversed by a different random seed."
        ),
    },
}


# ═════════════════════════════════════════════════════════════════════════════
# QUESTION BUILDING — turning a patient into a retrieval query
# ═════════════════════════════════════════════════════════════════════════════

def build_questions(patient: dict, cate: float | None = None) -> list[str]:
    """Turn a patient's profile into the guideline questions it raises.

    This little function is where a lot of the system's apparent intelligence
    actually lives, and it deserves to be looked at rather than skipped.

    A naive design sends one fixed query — "SGLT2 inhibitor type 2 diabetes" —
    and gets the same three passages for every patient. The citations then look
    like decoration, because they are: they do not depend on who the patient is.

    Instead we read the patient's features and ask the questions those features
    raise. Low eGFR raises a renal-dosing question. Established CVD raises an
    outcomes question. A predicted harm raises a "when is this drug not
    appropriate" question. The retrieved evidence then genuinely differs from
    patient to patient, which is the difference between a cited recommendation
    and a decorated one.
    """
    qs: list[str] = []
    egfr = patient.get("egfr", 90)
    bmi = patient.get("bmi", 28)
    a1c = patient.get("baseline_hba1c", 8.0)

    # Always: the core drug-choice question.
    qs.append("SGLT2 inhibitor metformin first line therapy type 2 diabetes")

    if egfr < 60:
        qs.append("SGLT2 inhibitor eGFR renal impairment glycaemic efficacy dose")
    if egfr < 45:
        qs.append("metformin contraindication renal impairment eGFR lactic acidosis")
    if patient.get("has_cvd"):
        qs.append("SGLT2 inhibitor cardiovascular disease heart failure outcome benefit")
    if patient.get("has_ckd"):
        qs.append("SGLT2 inhibitor chronic kidney disease progression benefit")
    if bmi >= 32:
        qs.append("obesity weight loss glucose lowering agent preferred diabetes")
    if a1c >= 10.0:
        qs.append("severe hyperglycaemia combination therapy insulin initiation")
    elif a1c < 8.0:
        qs.append("HbA1c target individualised glycaemic control older adults")
    if cate is not None and cate <= -0.3:
        qs.append("when SGLT2 inhibitor is not appropriate limited glycaemic benefit")
    if patient.get("age", 60) >= 75:
        qs.append("older adults deprescribing hypoglycaemia risk treatment burden")

    return qs


# ═════════════════════════════════════════════════════════════════════════════
# THE ENGINE
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class Recommendation:
    """One patient's recommendation card, with everything needed to audit it."""

    patient: dict
    cate: float
    cate_se: float | None
    direction: str                       #: "SGLT2i", "Metformin", or "equivalent"
    guard: guardrails.GuardrailResult
    citations: list = field(default_factory=list)   #: list[rag_lite.Hit]
    questions: list[str] = field(default_factory=list)
    true_cate: float | None = None       #: only on synthetic patients
    notes: dict = field(default_factory=dict)

    @property
    def blocked(self) -> bool:
        return self.guard.vetoed

    @property
    def headline(self) -> str:
        if self.blocked:
            return "NO RECOMMENDATION — contraindication present"
        if self.direction == "equivalent":
            return "The two options are clinically equivalent for this patient"
        if self.direction == "SGLT2i":
            return f"SGLT2 inhibitor preferred (+{self.cate:.2f} HbA1c points vs metformin)"
        return f"Metformin preferred (SGLT2i is {self.cate:+.2f} HbA1c points)"


class DiaCausalCDSS:
    """The assembled system: causal engine + retrieval + safety layer.

    Constructed once (fitting the CATE model is the expensive part), then queried
    per patient. The Streamlit app holds one of these behind a cache.
    """

    def __init__(self, cohort, cate_model=None, index=None, learner: str = "X-learner"):
        """
        Parameters
        ----------
        cohort
            The training cohort. Also supplies the honest training-data envelope
            used by the out-of-distribution guardrail.
        cate_model
            A fitted :class:`~causal_engine.estimators.CateModel`. Fitted here
            with the X-learner if not supplied — X-learner because Act 7's
            leaderboard shows it recovers the authored CATE best (MAE 0.08,
            rank correlation 0.98).
        index
            A :class:`~causal_engine.rag_lite.GuidelineIndex`. Built from `RAG/`
            if not supplied.
        """
        from . import rag_lite
        from .estimators import ALL_CATE_LEARNERS

        self.cohort = cohort
        self.cate_model = cate_model or ALL_CATE_LEARNERS[learner](
            cohort.X, cohort.T, cohort.Y
        )
        self.index = index if index is not None else rag_lite.build_index()
        self.ranges = guardrails.training_ranges(cohort)

        # A bootstrap-free uncertainty proxy: the spread of the cohort's
        # estimated effects around this patient's neighbourhood is NOT a standard
        # error, so we use the AIPW influence-function SE for the population as a
        # floor. Stated as the approximation it is, rather than dressed up.
        from .estimators import aipw_ate

        self._pop = aipw_ate(cohort.X, cohort.T, cohort.Y, cross_fit=True)

    # ── the one public method ───────────────────────────────────────────────
    def recommend(self, patient: dict, k_citations: int = 3) -> Recommendation:
        """Produce a full recommendation card for one patient.

        The five steps, in the order they must happen:

            1. ESTIMATE   Ask the CATE model for this patient's personal effect.
            2. ASK        Turn the patient's profile into guideline questions.
            3. RETRIEVE   Pull cited passages that answer those questions.
            4. CHECK      Run the safety rules over patient AND estimate.
            5. ASSEMBLE   Compose the card — with the guardrails able to veto.
        """
        # 1 ── estimate
        x = np.array([[float(patient[c]) for c in COVARIATES]])
        cate = float(self.cate_model.effect(x)[0])

        # A patient-level SE is genuinely hard and we do not pretend otherwise:
        # what we report is the population-level influence-function SE, which
        # understates individual uncertainty. Flagged in `notes` and in the card.
        se = self._pop.std_error

        # 2 ── ask
        questions = build_questions(patient, cate)

        # 3 ── retrieve. One passage per raised question, and — where the scores
        #      allow it — from DIFFERENT documents.
        #
        #      Why bother with the source-diversity pass: the curated snippets
        #      are short and dense, so TF-IDF scores them highly on almost any
        #      clinical query (short documents have less to dilute the match).
        #      Taking the top hit per question therefore returns three passages
        #      from one document, which looks like a retrieval system with one
        #      book on the shelf. So we look at the top few per question and
        #      prefer a source we have not cited yet, falling back to the best
        #      overall when no alternative clears the relevance floor. Nothing
        #      irrelevant is promoted — we only reorder among genuine matches.
        seen_pages: set[tuple[str, int]] = set()
        used_sources: set[str] = set()
        citations = []
        for q in questions:
            if len(citations) >= k_citations:
                break
            pool = [
                h for h in self.index.retrieve(q, k=6)
                if (h.chunk.source, h.chunk.page) not in seen_pages
            ]
            if not pool:
                continue
            fresh = [h for h in pool if h.chunk.source not in used_sources]
            hit = fresh[0] if fresh else pool[0]
            seen_pages.add((hit.chunk.source, hit.chunk.page))
            used_sources.add(hit.chunk.source)
            citations.append(hit)

        # 4 ── check
        guard = guardrails.check(
            patient,
            {"cate": cate, "cate_se": se, "training_ranges": self.ranges},
        )

        # 5 ── assemble
        if abs(cate) < 0.3:
            direction = "equivalent"
        elif cate > 0:
            direction = "SGLT2i"
        else:
            direction = "Metformin"

        return Recommendation(
            patient=patient,
            cate=cate,
            cate_se=se,
            direction=direction,
            guard=guard,
            citations=citations,
            questions=questions,
            # Only possible because this cohort is synthetic and WE wrote the
            # effect function. On a real patient this field would be None
            # forever — which is the whole difficulty of the field, and the
            # reason a synthetic demo is worth building before a real one.
            true_cate=float(authored_cate(patient["bmi"], patient["egfr"])),
            notes={
                "learner": self.cate_model.name,
                "se_caveat": (
                    "The ± shown is the POPULATION influence-function standard "
                    "error, not a patient-level one. It understates individual "
                    "uncertainty. A deployed system would need conformal "
                    "prediction intervals per patient."
                ),
                "population_ate": self._pop.value,
            },
        )

    # ── the counterfactual view, for one named patient ──────────────────────
    def counterfactual_card(self, row_index: int) -> str:
        """The Fundamental Problem of Causal Inference, for one real row.

        Only possible on the synthetic cohort, and that is exactly the point:
        we can print the column that reality never shows anyone.
        """
        df = self.cohort.data
        r = df.iloc[row_index]
        took = "SGLT2i" if r["treatment_sglt2i"] == 1 else "Metformin"
        other = "Metformin" if r["treatment_sglt2i"] == 1 else "SGLT2i"
        observed = r["hba1c_reduction"]
        counter = r["y0"] if r["treatment_sglt2i"] == 1 else r["y1"]

        x = np.array([[float(r[c]) for c in COVARIATES]])
        pred = float(self.cate_model.effect(x)[0])

        return "\n".join([
            f"PATIENT #{int(r['patient_id'])}  —  the counterfactual, printed",
            "=" * 72,
            f"    age {r['age']:.0f}   BMI {r['bmi']:.1f}   HbA1c {r['baseline_hba1c']:.1f}%"
            f"   eGFR {r['egfr']:.0f}   CVD {int(r['has_cvd'])}",
            "",
            f"    FACTUAL          took {took:<10s} -> HbA1c fell {observed:+.2f}",
            f"    COUNTERFACTUAL   had they taken {other:<10s} it would have fallen "
            f"{counter:+.2f}",
            "",
            f"    So the TRUE effect of the drug for this one person: {r['true_cate']:+.2f}",
            f"    Our model, which never saw that column:              {pred:+.2f}",
            f"    Error:                                              {pred - r['true_cate']:+.2f}",
            "",
            "    In a real clinic the COUNTERFACTUAL line is blank, permanently, for",
            "    every patient who ever lived. That is the Fundamental Problem of",
            "    Causal Inference. Every method in this project exists to fill that",
            "    line in from the rest of the population — and the only reason we can",
            "    check whether it worked is that here, uniquely, we wrote it ourselves.",
        ])


# ═════════════════════════════════════════════════════════════════════════════
# RENDERING — the card a clinician would actually read
# ═════════════════════════════════════════════════════════════════════════════

def format_card(rec: Recommendation, width: int = 78) -> str:
    """Render a recommendation as a text card.

    Layout choices that are deliberate rather than cosmetic:

        * The SAFETY block comes before the recommendation. A clinician skimming
          must hit the veto before the number, not after it.
        * The number is always shown WITH its uncertainty and its caveat. A bare
          point estimate invites false confidence.
        * Citations carry page numbers and a `[curated]` marker where relevant, so
          provenance survives all the way to the reader.
        * On synthetic patients the TRUE effect is printed. Nowhere else in the
          project is that possible, and it is what makes the demo checkable.
    """
    p = rec.patient
    line = "─" * width
    out = [
        "┌" + line + "┐",
        f"│ DIACAUSAL CDSS — treatment recommendation".ljust(width + 1) + "│",
        "├" + line + "┤",
    ]

    prof = (f"  age {p['age']:.0f} · BMI {p['bmi']:.1f} · HbA1c {p['baseline_hba1c']:.1f}%"
            f" · eGFR {p['egfr']:.0f} · CVD {'yes' if p.get('has_cvd') else 'no'}"
            f" · CKD {'yes' if p.get('has_ckd') else 'no'}")
    out.append("│" + prof.ljust(width) + "│")
    out.append("├" + line + "┤")

    # ── 1. SAFETY FIRST ──
    out.append("│" + f"  SAFETY REVIEW: {rec.guard.status}".ljust(width) + "│")
    if rec.guard.flags:
        for f in rec.guard.flags:
            out.append("│" + f"    [{guardrails.SEVERITY_LABEL[f.severity]}]".ljust(width) + "│")
            for chunk in _wrap(f.message, width - 8):
                out.append("│" + f"        {chunk}".ljust(width) + "│")
            for chunk in _wrap(f"source: {f.source}", width - 8):
                out.append("│" + f"        {chunk}".ljust(width) + "│")
    else:
        out.append("│" + "    No safety rule triggered.".ljust(width) + "│")
    out.append("├" + line + "┤")

    # ── 2. THE RECOMMENDATION ──
    out.append("│" + f"  RECOMMENDATION".ljust(width) + "│")
    for chunk in _wrap(rec.headline, width - 4):
        out.append("│" + f"    {chunk}".ljust(width) + "│")
    if rec.blocked:
        out.append("│" + "    (the model's estimate is withheld — see safety review)".ljust(width) + "│")
    else:
        se = f" ± {rec.cate_se:.2f}" if rec.cate_se else ""
        out.append("│" + f"    personal estimated effect: {rec.cate:+.2f}{se} HbA1c points".ljust(width) + "│")
        out.append("│" + f"    population average effect: {rec.notes['population_ate']:+.2f} "
                          f"(shown for contrast)".ljust(width) + "│")
        if rec.true_cate is not None:
            err = rec.cate - rec.true_cate
            out.append("│" + f"    TRUE effect (synthetic only): {rec.true_cate:+.2f}   "
                              f"model error {err:+.2f}".ljust(width) + "│")
    out.append("├" + line + "┤")

    # ── 3. EVIDENCE ──
    out.append("│" + f"  GUIDELINE EVIDENCE ({len(rec.citations)} passages retrieved)".ljust(width) + "│")
    if not rec.citations:
        out.append("│" + "    No guideline passage scored above the relevance floor.".ljust(width) + "│")
    for h in rec.citations:
        out.append("│" + f"    • {h.chunk.citation}  (similarity {h.score:.2f})".ljust(width) + "│")
        for chunk in _wrap(h.chunk.preview(300), width - 8):
            out.append("│" + f"      {chunk}".ljust(width) + "│")
    out.append("├" + line + "┤")

    # ── 4. WHAT THIS DOES NOT KNOW ──
    out.append("│" + "  SCOPE OF THIS ESTIMATE".ljust(width) + "│")
    for chunk in _wrap(
        "Estimates HbA1c reduction only. Does NOT estimate cardiovascular or "
        "kidney outcomes, side effects, cost, or adherence. " + rec.notes["se_caveat"],
        width - 6,
    ):
        out.append("│" + f"      {chunk}".ljust(width) + "│")
    out.append("└" + line + "┘")
    return "\n".join(out)


def _wrap(text: str, width: int) -> list[str]:
    import textwrap

    return textwrap.wrap(" ".join(text.split()), width=max(width, 20)) or [""]


# ═════════════════════════════════════════════════════════════════════════════
# THE THREE-WAY CONTRAST — the project's thesis, printed
# ═════════════════════════════════════════════════════════════════════════════

def three_way_contrast(cdss: DiaCausalCDSS, patient: dict, name: str = "this patient") -> str:
    """RAG alone vs causal alone vs both, for one patient. The money slide.

    Nothing is straw-manned here. The RAG-only answer is genuinely correct and
    genuinely cited; the causal-only answer is genuinely personalised. The point
    is that each is missing something the other has, and that the gap is not
    cosmetic — for a patient like Mrs R the two halves point in *different
    directions*, and only the combination can say why.
    """
    rec = cdss.recommend(patient)

    # (a) RAG alone: retrieve on the generic question, ignore the patient.
    generic = cdss.index.retrieve_diverse(
        "SGLT2 inhibitor metformin first line therapy type 2 diabetes", k=1
    )
    rag_only = generic[0].chunk.preview(280) if generic else "(no passage found)"
    rag_cite = generic[0].chunk.citation if generic else "—"

    parts = [
        f"THE SAME PATIENT, THREE WAYS  —  {name}",
        "=" * 78,
        "",
        "① RAG ALONE — retrieval with no model",
        "-" * 78,
        f"    \"{rag_only}\"",
        f"        — {rag_cite}",
        "",
        "    Correct, cited, and IDENTICAL for every patient with type 2 diabetes.",
        f"    It cannot know this patient's eGFR is {patient['egfr']:.0f}, so it cannot know",
        "    the mechanism the drug relies on is failing in them.",
        "",
        "② CAUSAL ALONE — a model with no evidence",
        "-" * 78,
        f"    Estimated individual treatment effect: {rec.cate:+.2f} HbA1c points",
        "",
        "    Personal, and unusable. No justification, no source, no statement of",
        "    what it does not cover. A clinician cannot audit it, so a clinician",
        "    should not act on it — and a regulator would agree.",
        "",
        "③ BOTH — what this project actually builds",
        "-" * 78,
    ]
    parts.append(format_card(rec))
    parts += [
        "",
        "-" * 78,
        "    The third answer is personalised BECAUSE of the causal half, defensible",
        "    BECAUSE of the retrieval half, and safe BECAUSE of the guardrails. Remove",
        "    any one of the three and it stops being something you could put in front",
        "    of a clinician.",
    ]
    return "\n".join(parts)


def demo_all_patients(cdss: DiaCausalCDSS) -> str:
    """Run the four demo patients. Each shows a different failure a simpler tool makes."""
    out = []
    for name, spec in DEMO_PATIENTS.items():
        patient = {k: v for k, v in spec.items() if k != "story"}
        rec = cdss.recommend(patient)
        out += [
            "",
            "█" * 80,
            f"  {name}",
            "█" * 80,
            "",
            "  WHY THIS PATIENT IS IN THE DEMO:",
        ]
        out += [f"    {c}" for c in _wrap(spec["story"], 74)]
        out += ["", format_card(rec)]
    return "\n".join(out)
