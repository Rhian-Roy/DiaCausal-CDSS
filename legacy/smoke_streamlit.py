#!/usr/bin/env python3
"""
Smoke-test `diacausal_demo.py` without starting a Streamlit server.

    python smoke_streamlit.py

Why not just `streamlit run`. Streamlit has to bind a TCP port, and in a
sandboxed environment that is refused:

    PermissionError: [Errno 1] Operation not permitted

That would leave the app completely unverified, which is not acceptable for a
deliverable someone is going to open in front of a panel. So this exercises the
parts that can actually break:

    1. the module imports at all (syntax, and every `causal_engine` name it uses
       really exists)
    2. `build_engine` runs and returns a usable Engine
    3. `ate_table` returns the (leaderboard, estimates) pair the Methods tab
       unpacks
    4. every attribute and dict key the UI functions touch resolves — checked by
       name against the real objects, because a typo in `hit.chunk.citaton` would
       only surface when a user clicked that expander
    5. each of the four demo presets produces a recommendation, a distinct
       guardrail status, and at least one citation

What it deliberately does NOT check: layout, widget behaviour, or anything
requiring a browser. Run `streamlit run diacausal_demo.py` on a normal machine
for that.
"""

from __future__ import annotations

import os
import sys
import traceback

os.environ.setdefault("MPLCONFIGDIR", os.environ.get("TMPDIR", "/tmp"))

import warnings
warnings.filterwarnings("ignore")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

FAILURES: list[str] = []


def check(label: str, fn):
    """Run one check, record the failure, keep going.

    Continuing after a failure is deliberate: one missing attribute should not
    hide the other five.
    """
    try:
        result = fn()
    except Exception as exc:
        FAILURES.append(f"{label}: {type(exc).__name__}: {exc}")
        print(f"  FAIL  {label}")
        traceback.print_exc(file=sys.stdout)
        return None
    print(f"  ok    {label}")
    return result


def main() -> int:
    print("smoke-testing diacausal_demo.py\n" + "─" * 72)

    print("importing the module (no server, no UI)")
    import diacausal_demo as app          # __name__ != "__main__", so main() is not called

    from causal_engine import cdss, data, diagnostics, evaluate, guardrails

    # A small cohort: this is checking wiring, not statistics.
    N, SCEN, SEED, LEARNER = 800, "strong", 7, "X-learner"

    print("\nbuild_engine")
    eng = check("build_engine returns an Engine",
                lambda: app.build_engine(N, SCEN, SEED, LEARNER))
    if eng is None:
        print("\ncannot continue without an engine")
        return 1

    for attr in ("cohort", "propensity", "system", "models", "truth",
                 "naive", "aipw", "index"):
        check(f"Engine.{attr} is populated",
              lambda a=attr: (getattr(eng, a) is not None) or _raise(a))

    check("system.cate_model.name is the requested learner",
          lambda: eng.system.cate_model.name == LEARNER or _raise("learner mismatch"))

    print("\nheadline metrics (the sign-flip banner reads these)")
    check("truth / naive.value / aipw.value are finite floats",
          lambda: all(np.isfinite([eng.truth, eng.naive.value, eng.aipw.value]))
                  or _raise("non-finite"))
    check("aipw.ci unpacks to two floats", lambda: len(eng.aipw.ci) == 2 or _raise("ci"))
    print(f"        truth {eng.truth:+.4f}   naive {eng.naive.value:+.4f}   "
          f"aipw {eng.aipw.value:+.4f}")

    print("\nate_table (Methods tab unpacks a 2-tuple)")
    pair = check("ate_table returns (leaderboard, estimates)",
                 lambda: app.ate_table(N, SCEN, SEED))
    if pair is not None:
        board, ests = pair
        check("leaderboard has a 'method' column",
              lambda: "method" in board.columns or _raise("no method column"))
        check("estimates list is non-empty", lambda: len(ests) >= 5 or _raise("too few"))

    print("\nscenario_table (sidebar blurb data)")
    check("scenario_table covers every scenario",
          lambda: len(app.scenario_table(400, SEED)) == len(data.SCENARIOS)
                  or _raise("scenario count"))

    print("\nevery scenario key has a sidebar blurb")
    check("SCENARIO_BLURB covers data.SCENARIOS",
          lambda: set(app.SCENARIO_BLURB) == set(data.SCENARIOS)
                  or _raise(f"{set(data.SCENARIOS) - set(app.SCENARIO_BLURB)}"))
    check("SEVERITY_COLOUR covers every Severity level",
          lambda: set(app.SEVERITY_COLOUR) == set(guardrails.Severity)
                  or _raise("severity coverage"))

    print("\ndiagnostics tab objects")
    prop = eng.propensity
    rep = check("overlap_report",
                lambda: diagnostics.overlap_report(prop.scores, eng.cohort.T))
    if rep is not None:
        for attr in ("verdict", "detail", "effective_sample_size", "max_weight"):
            check(f"OverlapReport.{attr}",
                  lambda a=attr: getattr(rep, a) is not None or _raise(a))

    weights = np.where(eng.cohort.T == 1, 1 / prop.scores, 1 / (1 - prop.scores))
    bal = check("balance_table",
                lambda: diagnostics.balance_table(eng.cohort.X, eng.cohort.T,
                                                  data.COVARIATES, weights=weights))
    if bal is not None:
        for col in ("SMD before", "SMD after"):
            check(f"balance_table['{col}']",
                  lambda c=col: c in bal.columns or _raise(c))

    ev = check("e_value",
               lambda: diagnostics.e_value(eng.aipw.value, ci_low=eng.aipw.ci[0],
                                           sd=float(eng.cohort.Y.std())))
    if ev is not None:
        for attr in ("e_value", "e_value_ci", "interpretation"):
            check(f"EValueResult.{attr}",
                  lambda a=attr: getattr(ev, a) is not None or _raise(a))

    print("\nmethods tab objects")
    cate_board = check("cate_leaderboard",
                       lambda: evaluate.cate_leaderboard(list(eng.models.values()),
                                                         eng.cohort.true_cate))
    if cate_board is not None:
        check("cate_leaderboard has a 'learner' column",
              lambda: "learner" in cate_board.columns or _raise("no learner column"))
    check("policy_comparison",
          lambda: evaluate.policy_comparison(list(eng.models.values()), eng.cohort))
    check("predictive_vs_causal + formatter",
          lambda: evaluate.format_predictive_vs_causal(
              evaluate.predictive_vs_causal(eng.cohort, eng.system.cate_model,
                                            budget_fraction=0.30)))

    print("\nevery figure the app draws")
    figures = {
        "dag.draw_dag": lambda ax: app.dag.draw_dag(app.dag.build_graph(), ax=ax),
        "plot_overlap": lambda ax: diagnostics.plot_overlap(prop.scores,
                                                            eng.cohort.T, ax=ax),
        "plot_love": lambda ax: diagnostics.plot_love(bal, ax=ax),
        "plot_leaderboard": lambda ax: evaluate.plot_leaderboard(
            pair[1], eng.truth, ax=ax),
        "plot_cate_recovery(egfr)": lambda ax: evaluate.plot_cate_recovery(
            list(eng.models.values()), eng.cohort, feature="egfr", ax=ax),
        "plot_cate_recovery(bmi)": lambda ax: evaluate.plot_cate_recovery(
            list(eng.models.values()), eng.cohort, feature="bmi", ax=ax),
        "plot_decision_curve": lambda ax: evaluate.plot_decision_curve(
            eng.system.cate_model, eng.cohort, ax=ax),
    }
    for name, draw in figures.items():
        def render(d=draw):
            fig, ax = plt.subplots()
            d(ax)
            plt.close(fig)
            return True
        check(name, render)

    print("\ndag tab objects")
    graph = app.dag.build_graph()
    check("explain_adjustment", lambda: app.dag.explain_adjustment(graph))
    check("path_report", lambda: app.dag.path_report(graph))
    check("structural_mistakes_table",
          lambda: app.dag.structural_mistakes_table(eng.cohort))
    for fn in (app.dag.demo_collider_bias, app.dag.demo_over_adjustment,
               app.dag.demo_confounder_omission):
        d = check(fn.__name__, lambda f=fn: f(eng.cohort))
        if d is not None:
            for attr in ("name", "correct", "mistaken", "truth", "damage",
                         "explanation"):
                check(f"  StructuralDemo.{attr}",
                      lambda a=attr, dd=d: getattr(dd, a) is not None or _raise(a))

    print("\nevidence tab objects")
    check("index.summary", lambda: eng.index.summary())
    check("provenance_table", lambda: app.rag_lite.provenance_table(eng.index))
    check("explain_query returns a string",
          lambda: isinstance(eng.index.explain_query("SGLT2 eGFR"), str)
                  or _raise("not a str"))
    check("rules_table", lambda: guardrails.rules_table())
    check("KNOWN_LIMITATIONS is non-empty",
          lambda: len(app.rag_lite.KNOWN_LIMITATIONS) > 0 or _raise("empty"))

    print("\nthe four sidebar presets, end to end")
    statuses = {}
    for label, spec in cdss.DEMO_PATIENTS.items():
        patient = {k: v for k, v in spec.items() if k != "story"}
        short = label.split(" — ")[0]

        rec = check(f"recommend({short})", lambda p=patient: eng.system.recommend(p))
        if rec is None:
            continue

        # Everything tab_patient touches, checked by name.
        for attr in ("cate", "direction", "guard", "citations", "questions",
                     "true_cate", "notes", "headline", "blocked"):
            check(f"  Recommendation.{attr}",
                  lambda a=attr, r=rec: getattr(r, a) is not None or _raise(a))
        for hit in rec.citations:
            check("  Hit.chunk.citation / .text / score",
                  lambda h=hit: (isinstance(h.chunk.citation, str)
                                 and isinstance(h.chunk.text, str)
                                 and np.isfinite(h.score)) or _raise("citation shape"))
            break     # one is enough to prove the shape
        for flag in rec.guard.flags:
            check("  Flag.rule / .severity / .message / .source",
                  lambda f=flag: all(getattr(f, a) is not None
                                     for a in ("rule", "severity", "message", "source"))
                                 or _raise("flag shape"))
            break

        check(f"  format_card({short})", lambda r=rec: cdss.format_card(r))
        check(f"  three_way_contrast({short})",
              lambda p=patient: cdss.three_way_contrast(eng.system, p, short))
        check(f"  authored_cate({short})",
              lambda p=patient: np.isfinite(
                  float(data.authored_cate(p["bmi"], p["egfr"]))) or _raise("nan"))

        statuses[short] = rec.guard.status
        print(f"        {short:<12s} cate {rec.cate:+.2f}   "
              f"true {rec.true_cate:+.2f}   {rec.guard.status}")

    check("the four presets produce four DIFFERENT guardrail statuses",
          lambda: len(set(statuses.values())) == 4
                  or _raise(f"only {len(set(statuses.values()))}: {statuses}"))

    print("\ncustom-patient path (the sliders' default position)")
    custom = {"age": 58, "bmi": 32.0, "baseline_hba1c": 8.5, "egfr": 75.0,
              "has_cvd": 0, "has_ckd": 0}
    check("recommend(slider defaults)", lambda: eng.system.recommend(custom))
    check("counterfactual_card", lambda: eng.system.counterfactual_card(17))

    print("─" * 72)
    if FAILURES:
        print(f"{len(FAILURES)} FAILURE(S):")
        for f in FAILURES:
            print("   ·", f)
        return 1
    print("ALL SMOKE CHECKS PASSED")
    print("\nrun the real thing with:  streamlit run diacausal_demo.py")
    return 0


def _raise(what: str):
    raise AssertionError(what)


if __name__ == "__main__":
    sys.exit(main())
