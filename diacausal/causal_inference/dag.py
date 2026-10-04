"""The causal diagram (DAG): which variables cause what, read from data/params.yaml.

Plain English: before estimating anything we write down our assumptions as arrows.
Variables that point into the treatment (and maybe the outcome) happened BEFORE the
drug was chosen, so we adjust for them. Variables the drug itself changes (mediators,
like weight change) must NOT be adjusted for — that would hide part of the drug's effect.
"""

from __future__ import annotations

from dataclasses import dataclass

from diacausal_engine.config import Params

ROLES = ("confounder", "treatment_predictor", "outcome_predictor", "derived", "mediator")
ADJUST_ROLES = ("confounder", "treatment_predictor", "outcome_predictor")


class DagError(ValueError):
    pass


@dataclass(frozen=True)
class Dag:
    treatment: str
    outcome: str
    roles: dict[str, str]
    edges: tuple[tuple[str, str], ...]

    def parents(self, node: str) -> set[str]:
        return {a for a, b in self.edges if b == node}

    def children(self, node: str) -> set[str]:
        return {b for a, b in self.edges if a == node}

    @property
    def adjustment_set(self) -> list[str]:
        """Pre-treatment variables we adjust for, in a fixed order (never a mediator)."""
        return [n for n, r in self.roles.items() if r in ADJUST_ROLES]

    @property
    def mediators(self) -> list[str]:
        return [n for n, r in self.roles.items() if r == "mediator"]

    def check(self) -> None:
        """Each role must agree with the arrows drawn."""
        nodes = set(self.roles) | {self.treatment, self.outcome}
        for a, b in self.edges:
            if a not in nodes or b not in nodes:
                raise DagError(f"edge {a} -> {b} uses an unknown node")
        for node, role in self.roles.items():
            if role not in ROLES:
                raise DagError(f"{node}: unknown role {role!r}")
            kids = self.children(node)
            if role == "confounder" and not {self.treatment, self.outcome} <= kids:
                raise DagError(f"{node} is a confounder but lacks an arrow to treatment and outcome")
            if role == "treatment_predictor" and self.treatment not in kids:
                raise DagError(f"{node} is a treatment predictor without an arrow to treatment")
            if role == "outcome_predictor" and self.outcome not in kids:
                raise DagError(f"{node} is an outcome predictor without an arrow to the outcome")
            if role == "mediator" and self.treatment not in self.parents(node):
                raise DagError(f"{node} is a mediator but the treatment does not cause it")
        if (self.treatment, self.outcome) not in self.edges:
            raise DagError("the DAG must contain treatment -> outcome")


def load_dag(params: Params) -> Dag:
    raw = params.raw["dag"]
    dag = Dag(
        treatment=raw["treatment"],
        outcome=raw["outcome"],
        roles=dict(raw["nodes"]),
        edges=tuple((a, b) for a, b in raw["edges"]),
    )
    dag.check()
    return dag
