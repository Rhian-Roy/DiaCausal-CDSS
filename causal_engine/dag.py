"""
ACT 3 — Draw your assumptions before you compute anything.
==========================================================

A regression tells you nothing about causation. The *same* regression can be
correct or catastrophically wrong depending on facts that live nowhere in the
data: which variable came first, and what caused what. Those facts have to come
from clinical knowledge, and the honest way to state them is a picture.

A DAG (Directed Acyclic Graph) is that picture. Arrows mean "causes".
"Acyclic" means nothing causes itself, directly or in a loop.

--------------------------------------------------------------------------------
THE THREE ROLES A VARIABLE CAN PLAY — and why they need OPPOSITE treatment
--------------------------------------------------------------------------------
This is the single most useful thing in causal inference, and it is the thing
that most projects get wrong. Structurally these three look nearly identical.
Statistically they are indistinguishable. Yet what you must DO with them is
opposite:

    CONFOUNDER    C -> T  and  C -> Y          ADJUST FOR IT
                  Severity causes both the prescription and the outcome.
                  Ignore it and you get the sign flip from Act 2.

    MEDIATOR      T -> M -> Y                  DO NOT ADJUST
                  The drug works partly BY improving adherence. Adjusting for
                  adherence subtracts away part of the very effect you want.
                  You will get a number that is too small and looks precise.

    COLLIDER      T -> K  and  Y -> K          NEVER ADJUST, NEVER FILTER ON IT
                  Hospitalisation is caused by side effects AND by bad glucose
                  control. Conditioning on it INVENTS an association that does
                  not exist in reality. Adjusting for more variables made your
                  answer worse.

The last one is the counter-intuitive one, and it is why "just control for
everything you have" is wrong. This module *demonstrates* all three on our data
instead of asserting them.

--------------------------------------------------------------------------------
BACKDOOR PATHS, in one sentence
--------------------------------------------------------------------------------
A backdoor path is any path from Treatment to Outcome that starts by pointing
INTO the treatment (T <- ... -> Y). It is a route by which association leaks
between T and Y without T causing anything. Block every backdoor path and what
remains is causal. That is the whole game.

Graph structure follows Causal_Inference_Study_Guide.docx §7.3 verbatim, so the
code and the report use identical notation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import PALETTE

TREATMENT_NODE = "Treatment"
OUTCOME_NODE = "Outcome"

#: The DAG as (cause -> effect) pairs. Straight from study guide §7.3.
EDGES: list[tuple[str, str]] = [
    # Age is an upstream common cause of almost everything.
    ("Age", "BMI"),
    ("Age", "HbA1c_baseline"),
    ("Age", "Comorbidities"),
    ("Age", "Treatment"),
    ("Age", "Outcome"),
    # Clinical state drives BOTH the prescription and the result: confounders.
    ("BMI", "Treatment"),
    ("BMI", "Outcome"),
    ("HbA1c_baseline", "Treatment"),
    ("HbA1c_baseline", "Outcome"),
    ("Comorbidities", "Treatment"),
    ("Comorbidities", "Outcome"),
    ("eGFR", "Treatment"),
    ("eGFR", "Outcome"),
    ("eGFR", "Comorbidities"),
    # The causal effect we are after.
    ("Treatment", "Outcome"),
    # A MEDIATOR: part of how the drug works.
    ("Treatment", "Adherence"),
    ("Adherence", "Outcome"),
    # A side effect, and a COLLIDER downstream of it.
    ("Treatment", "AdverseEvents"),
    ("AdverseEvents", "Hospitalisation"),
    ("SevereHyperglycaemia", "Hospitalisation"),
    ("Outcome", "SevereHyperglycaemia"),
]

#: Role of each node, which determines whether it may enter the adjustment set.
NODE_ROLES: dict[str, str] = {
    "Age": "confounder",
    "BMI": "confounder",
    "HbA1c_baseline": "confounder",
    "Comorbidities": "confounder",
    "eGFR": "confounder",
    "Treatment": "treatment",
    "Outcome": "outcome",
    "Adherence": "mediator",
    "AdverseEvents": "descendant of treatment",
    "SevereHyperglycaemia": "descendant of outcome",
    "Hospitalisation": "collider",
}

ROLE_COLOURS: dict[str, str] = {
    "confounder": PALETTE["amber"],
    "treatment": PALETTE["primary"],
    "outcome": PALETTE["truth"],
    "mediator": PALETTE["muted"],
    "descendant of treatment": PALETTE["muted"],
    "descendant of outcome": PALETTE["muted"],
    "collider": PALETTE["alert"],
}


def build_graph():
    """Return the DAG as a `networkx.DiGraph`, and assert it really is acyclic."""
    import networkx as nx

    g = nx.DiGraph()
    for node, role in NODE_ROLES.items():
        g.add_node(node, role=role)
    g.add_edges_from(EDGES)

    # The 'A' in DAG is a claim about the world, so we check it rather than
    # trust it. A cycle would mean we had written down something impossible.
    if not nx.is_directed_acyclic_graph(g):
        raise ValueError(f"Graph contains a cycle: {nx.find_cycle(g)}")
    return g


# ═════════════════════════════════════════════════════════════════════════════
# Backdoor paths, enumerated in code rather than claimed in prose
# ═════════════════════════════════════════════════════════════════════════════

def backdoor_paths(
    graph=None,
    treatment: str = TREATMENT_NODE,
    outcome: str = OUTCOME_NODE,
) -> list[list[str]]:
    """List every backdoor path from treatment to outcome.

    Method: walk the *undirected* version of the graph (association flows both
    ways along an edge), keep only paths whose first step points INTO the
    treatment — that is what makes a path a "backdoor" — and exclude any path
    that leaves through the causal arrow T -> Y, which is the front door and
    is exactly what we want to keep.

    Every path in this list is a route by which severity leaks into our
    comparison. Each one must be blocked.
    """
    import networkx as nx

    g = graph if graph is not None else build_graph()
    parents_of_t = set(g.predecessors(treatment))

    found = []
    for path in nx.all_simple_paths(g.to_undirected(), treatment, outcome):
        if len(path) < 3:
            continue                       # the direct T -> Y arrow itself
        if path[1] not in parents_of_t:
            continue                       # leaves through the front door
        found.append(path)
    return found


def adjustment_sets(graph=None) -> dict[str, list[str]]:
    """Which variables belong in the adjustment set, and which must be excluded.

    Reading this dictionary out loud is a complete answer to "how did you choose
    your covariates?" — a question that sinks projects whose answer is
    "everything in the dataset".
    """
    g = graph if graph is not None else build_graph()
    roles: dict[str, list[str]] = {"adjust_for": [], "must_not_adjust_for": []}

    for node, data in g.nodes(data=True):
        role = data["role"]
        if role == "confounder":
            roles["adjust_for"].append(node)
        elif role in {"mediator", "collider", "descendant of treatment",
                      "descendant of outcome"}:
            roles["must_not_adjust_for"].append(node)
    return roles


def explain_adjustment(graph=None) -> pd.DataFrame:
    """A per-variable verdict table: role, decision, and the reason."""
    g = graph if graph is not None else build_graph()
    reasons = {
        "confounder": "causes BOTH treatment and outcome — leaves a backdoor open",
        "mediator": "carries part of the real effect — adjusting deletes it",
        "collider": "caused by both sides — adjusting INVENTS an association",
        "descendant of treatment": "happens after treatment — cannot confound it",
        "descendant of outcome": "happens after the outcome — cannot cause it",
        "treatment": "this is the exposure",
        "outcome": "this is what we are measuring",
    }
    rows = []
    for node, data in g.nodes(data=True):
        role = data["role"]
        rows.append(
            {
                "variable": node,
                "role": role,
                "adjust?": {
                    "confounder": "YES",
                    "treatment": "—",
                    "outcome": "—",
                }.get(role, "NO"),
                "why": reasons[role],
            }
        )
    return pd.DataFrame(rows).sort_values(
        "adjust?", key=lambda s: s.map({"YES": 0, "—": 1, "NO": 2})
    ).reset_index(drop=True)


# ═════════════════════════════════════════════════════════════════════════════
# Rendering. `graphviz`/`dot` is not installed here, so we lay the DAG out
# by hand with matplotlib — which is better anyway, because we control exactly
# where each node sits and can group by role.
# ═════════════════════════════════════════════════════════════════════════════

#: Hand-placed coordinates: causes on the left, effects on the right, the
#: causal arrow T -> Y running straight through the middle.
LAYOUT: dict[str, tuple[float, float]] = {
    "Age": (0.0, 2.6),
    "BMI": (0.0, 1.5),
    "HbA1c_baseline": (0.0, 0.4),
    "eGFR": (0.0, -0.7),
    "Comorbidities": (0.0, -1.8),
    "Treatment": (2.2, 0.4),
    "Outcome": (4.6, 0.4),
    "Adherence": (3.4, 1.8),
    "AdverseEvents": (3.4, -1.3),
    "SevereHyperglycaemia": (5.9, -0.8),
    "Hospitalisation": (4.9, -2.1),
}


def draw_dag(
    graph=None,
    highlight_paths: list[list[str]] | None = None,
    title: str = "DiaCausal DAG — what we believe causes what",
    ax=None,
    save_to: str | None = None,
):
    """Draw the DAG, colour-coded by role.

    Amber = confounder (adjust). Red = collider (never adjust). Grey =
    downstream of treatment (leave alone). Teal = treatment, violet = outcome.

    `highlight_paths` overdraws specific backdoor paths in red so a viva
    audience can literally see the leak the adjustment is going to plug.
    """
    import matplotlib.pyplot as plt
    import networkx as nx

    g = graph if graph is not None else build_graph()
    if ax is None:
        _, ax = plt.subplots(figsize=(13, 7.5))

    pos = LAYOUT
    causal_edge = (TREATMENT_NODE, OUTCOME_NODE)

    highlight_edges = set()
    for path in highlight_paths or []:
        for a, b in zip(path, path[1:]):
            highlight_edges.add(frozenset((a, b)))

    for u, v in g.edges():
        is_causal = (u, v) == causal_edge
        is_hot = frozenset((u, v)) in highlight_edges
        ax.annotate(
            "",
            xy=pos[v],
            xytext=pos[u],
            arrowprops=dict(
                arrowstyle="-|>",
                linewidth=3.0 if is_causal else (2.2 if is_hot else 1.1),
                color=(
                    PALETTE["primary"] if is_causal
                    else PALETTE["alert"] if is_hot
                    else PALETTE["muted"]
                ),
                shrinkA=26,
                shrinkB=26,
                connectionstyle="arc3,rad=0.08",
                alpha=1.0 if (is_causal or is_hot) else 0.55,
            ),
        )

    for node, (x, y) in pos.items():
        role = g.nodes[node]["role"]
        colour = ROLE_COLOURS[role]
        emphasised = role in {"treatment", "outcome"}
        ax.scatter(
            [x], [y],
            s=2900 if emphasised else 2100,
            c=colour,
            edgecolors=PALETTE["secondary"],
            linewidths=2.0 if emphasised else 1.0,
            zorder=3,
        )
        ax.text(
            x, y,
            node.replace("_", "\n").replace("Severe", "Severe\n"),
            ha="center", va="center",
            fontsize=7.4, fontweight="bold",
            color="white", zorder=4,
        )

    # A legend that states the DECISION, not just the name — because the
    # decision is the part people forget.
    from matplotlib.lines import Line2D
    legend = [
        ("Confounder — ADJUST for it", PALETTE["amber"]),
        ("Treatment (the exposure)", PALETTE["primary"]),
        ("Outcome (what we measure)", PALETTE["truth"]),
        ("Mediator / descendant — do NOT adjust", PALETTE["muted"]),
        ("Collider — NEVER adjust or filter on it", PALETTE["alert"]),
    ]
    ax.legend(
        handles=[
            Line2D([], [], marker="o", linestyle="", markersize=11,
                   markerfacecolor=c, markeredgecolor=PALETTE["secondary"], label=lab)
            for lab, c in legend
        ],
        loc="lower left", frameon=True, fontsize=8.5,
    )

    ax.set_title(title, fontsize=13, fontweight="bold", color=PALETTE["secondary"])
    ax.set_xlim(-1.2, 7.2)
    ax.set_ylim(-3.0, 3.4)
    ax.axis("off")

    if save_to:
        ax.figure.tight_layout()
        ax.figure.savefig(save_to, dpi=150, bbox_inches="tight")
    return ax


# ═════════════════════════════════════════════════════════════════════════════
# DEMONSTRATIONS — the part that makes this act more than a diagram
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class StructuralDemo:
    """One structural mistake, priced in units of HbA1c."""

    name: str
    correct: float
    mistaken: float
    truth: float
    explanation: str
    extra: dict = field(default_factory=dict)

    @property
    def damage(self) -> float:
        """How far the mistake moved the answer away from the truth."""
        return abs(self.mistaken - self.truth) - abs(self.correct - self.truth)

    def __str__(self) -> str:
        return (
            f"{self.name}\n"
            f"    done right : {self.correct:+.4f}   (truth {self.truth:+.4f})\n"
            f"    done wrong : {self.mistaken:+.4f}   "
            f"-> {self.damage:+.4f} worse\n"
            f"    {self.explanation}"
        )


def demo_collider_bias(cohort) -> StructuralDemo:
    """Show that filtering on a collider MANUFACTURES an association.

    `hospitalised` is caused by adverse events (which the drug causes) and by
    bad glucose control (the outcome). Looking only at hospitalised patients is
    the kind of thing that happens by accident all the time — "we analysed our
    inpatient cohort", "we dropped patients lost to follow-up" — and it
    fabricates association out of nothing.

    BEST SEEN ON THE 'rct' SCENARIO. There the naive difference is *provably
    correct*, so any distortion has exactly one possible source. Split that
    clean randomised trial by hospitalisation and the two subgroups disagree
    with the truth and with each other:

        whole trial          +1.14      (truth +1.23 — correct)
        hospitalised only    +1.44      (too high)
        not hospitalised     +1.07      (too low)

    Nothing about the drug changed between those three lines. We broke a
    randomised trial using a variable measured AFTER treatment.

    The intuition, worth saying out loud in a viva:
        Among hospitalised patients, if you know the drug did NOT cause a side
        effect, something else must explain the admission — most likely bad
        glucose control. So within this subgroup, taking the drug now
        *predicts* better control for a purely arithmetic reason. Nothing
        causal happened. We selected our way into a correlation.
    """
    from .data import OUTCOME, TREATMENT

    df = cohort.data
    t, y = cohort.T, cohort.Y

    # The comparison in the FULL population.
    full = float(y[t == 1].mean() - y[t == 0].mean())

    # The same comparison inside each level of the collider.
    strata = {}
    for h in (1, 0):
        sub = df[df["hospitalised"] == h]
        ts = sub[TREATMENT].to_numpy()
        ys = sub[OUTCOME].to_numpy()
        strata[h] = (
            float(ys[ts == 1].mean() - ys[ts == 0].mean()),
            int(len(sub)),
        )

    among_hosp = strata[1][0]

    return StructuralDemo(
        name="COLLIDER BIAS — filtering on hospitalisation",
        correct=full,
        mistaken=among_hosp,
        truth=cohort.true_ate,
        explanation=(
            "Hospitalisation is caused by BOTH the drug (via side effects) and "
            "the outcome (via poor control). Restricting to one level of it "
            "opens a path between them that does not exist in the full "
            "population. Note that BOTH subgroups are wrong, in OPPOSITE "
            "directions, and neither equals the whole — the signature of a "
            "collider. More filtering, worse answer."
        ),
        extra={
            "n_full": int(len(df)),
            "hospitalised_effect": strata[1][0],
            "n_hospitalised": strata[1][1],
            "not_hospitalised_effect": strata[0][0],
            "n_not_hospitalised": strata[0][1],
            "shift": among_hosp - full,
            "subgroups_disagree_by": abs(strata[1][0] - strata[0][0]),
        },
    )


def demo_over_adjustment(cohort) -> StructuralDemo:
    """Show that adjusting for a MEDIATOR destroys the effect you want.

    Adherence sits on the causal pathway: the drug helps partly *because*
    patients take it. Putting adherence in the adjustment set asks "what is the
    drug's effect, holding fixed the very mechanism through which it works?" —
    which is a question nobody wanted the answer to.

    This is the most common real-world error in applied causal work, because
    adherence looks exactly like a helpful, informative covariate.
    """
    from .data import COVARIATES
    from .estimators import g_computation

    X_ok = cohort.data[COVARIATES].to_numpy(dtype=float)
    X_bad = cohort.data[COVARIATES + ["adherence"]].to_numpy(dtype=float)

    ok = g_computation(X_ok, cohort.T, cohort.Y).value
    bad = g_computation(X_bad, cohort.T, cohort.Y).value

    return StructuralDemo(
        name="OVER-ADJUSTMENT — controlling for adherence (a mediator)",
        correct=ok,
        mistaken=bad,
        truth=cohort.true_ate,
        explanation=(
            "Adherence is on the pathway Treatment -> Adherence -> Outcome. "
            "Adjusting for it holds fixed part of HOW the drug works, so part of "
            "the real effect is subtracted away. The estimate shrinks and looks "
            "just as confident."
        ),
    )


def demo_confounder_omission(cohort) -> StructuralDemo:
    """The baseline mistake, for contrast: leave a confounder OUT.

    Included so all three structural roles appear in one table. Only here does
    "add the variable" help — which is the point. There is no universal rule
    like "adjust for more"; the graph decides, one variable at a time.
    """
    from .data import COVARIATES
    from .estimators import g_computation

    keep = [c for c in COVARIATES if c != "baseline_hba1c"]
    ok = g_computation(cohort.data[COVARIATES].to_numpy(float), cohort.T, cohort.Y).value
    bad = g_computation(cohort.data[keep].to_numpy(float), cohort.T, cohort.Y).value

    return StructuralDemo(
        name="OMITTED CONFOUNDER — dropping baseline HbA1c",
        correct=ok,
        mistaken=bad,
        truth=cohort.true_ate,
        explanation=(
            "Baseline HbA1c causes both the prescription and the outcome. Leave "
            "it out and its backdoor path stays open. This is the ONE case where "
            "adding a variable helps — which is exactly why 'adjust for "
            "everything' is not a rule."
        ),
    )


def structural_mistakes_table(cohort) -> pd.DataFrame:
    """All three structural roles, side by side, priced in HbA1c points.

    The punchline of Act 3: two of these three mistakes are made by ADDING a
    variable, and one by REMOVING one. No amount of statistical sophistication
    tells you which is which. Only the graph does.

    The collider row is measured on a *randomised* cohort, where the naive
    answer is provably correct — so the damage is attributable to the collider
    alone rather than tangled up with the confounding this cohort already has.
    """
    from .data import generate_cohort

    rct = generate_cohort(
        n_patients=len(cohort.data), scenario="rct", seed=cohort.seed
    )
    rows = [
        (demo_confounder_omission(cohort), cohort.scenario.name),
        (demo_over_adjustment(cohort), cohort.scenario.name),
        (demo_collider_bias(rct), "rct"),
    ]
    return pd.DataFrame(
        [
            {
                "structural mistake": d.name.split(" — ")[0],
                "what we did": d.name.split(" — ")[1],
                "measured on": where,
                "done right": round(d.correct, 4),
                "done wrong": round(d.mistaken, 4),
                "truth": round(d.truth, 4),
                "damage": round(d.damage, 4),
            }
            for d, where in rows
        ]
    )


def path_report(graph=None) -> str:
    """A printable summary of the graph: paths found, and how we block them."""
    g = graph if graph is not None else build_graph()
    paths = backdoor_paths(g)
    sets = adjustment_sets(g)

    lines = [
        f"Backdoor paths from {TREATMENT_NODE} to {OUTCOME_NODE}: {len(paths)}",
        "",
    ]
    for p in paths:
        lines.append("    " + "  <-  ".join([p[0]] + p[1:2]) + "  ->  " + "  ->  ".join(p[2:]))
    lines += [
        "",
        f"Blocked by adjusting for : {', '.join(sorted(sets['adjust_for']))}",
        f"Deliberately EXCLUDED    : {', '.join(sorted(sets['must_not_adjust_for']))}",
        "",
        "Every backdoor path above passes through at least one adjusted variable,",
        "so all of them are blocked. What remains between Treatment and Outcome",
        "is the front door: the causal effect itself.",
    ]
    return "\n".join(lines)
