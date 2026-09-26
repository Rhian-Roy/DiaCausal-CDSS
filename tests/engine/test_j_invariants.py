"""Step (j): the project rules, checked across many patients and the whole repo."""

import re
import subprocess
from pathlib import Path

import numpy as np
import pytest

from diacausal_engine import INTENDED_USE
from diacausal_engine.recommend import DOSE_PATTERN
from diacausal_engine.schemas import PatientIn

ROOT = Path(__file__).resolve().parents[2]


def random_patients(n: int, seed: int = 0):
    rng = np.random.default_rng(seed)
    for _ in range(n):
        yield PatientIn(
            age=int(rng.integers(18, 100)),
            sex=str(rng.choice(["female", "male"])),
            duration_years=float(rng.uniform(0, 40)),
            hba1c=float(np.round(rng.uniform(5, 15), 1)),
            egfr=float(rng.integers(5, 140)),
            bmi=float(np.round(rng.uniform(15, 50), 1)),
            **{f: bool(rng.random() < 0.15) for f in
               ("ascvd", "hf", "hypo_history", "t1d", "dka_history", "pancreatitis_history", "low_income")},
        )


@pytest.fixture(scope="module")
def sweep(engine, tmp_path_factory):
    path = tmp_path_factory.mktemp("sweep") / "audit.jsonl"
    return [(p, engine.recommend(p, audit_path=path)) for p in random_patients(300)]


def test_every_reply_carries_the_intended_use_statement(sweep):
    assert all(r.intended_use == INTENDED_USE for _, r in sweep)


def test_no_reply_ever_contains_dose_text(sweep):
    for _, r in sweep:
        assert not DOSE_PATTERN.search(r.model_dump_json())


def test_every_number_has_a_95_percent_interval(sweep):
    for _, r in sweep:
        for o in r.options:
            if o.status == "estimate":
                assert o.effect.ci_low <= o.effect.value <= o.effect.ci_high and o.effect.level == 0.95
            else:
                assert o.effect is None
        for c in r.comparisons:
            assert c.difference.ci_low <= c.difference.value <= c.difference.ci_high


def test_excluded_options_always_cite_a_rule_and_never_get_a_number(sweep):
    for _, r in sweep:
        for o in r.options:
            if o.status == "excluded":
                assert o.effect is None and any(s.action == "EXCLUDE" and s.source for s in o.safety)


def test_low_propensity_always_means_insufficient_evidence(sweep, engine):
    threshold = engine.params.get("engine.overlap_min_propensity")
    for _, r in sweep:
        for o in r.options:
            if o.status == "estimate":
                assert o.confidence.propensity >= threshold


def test_comparisons_only_between_estimated_options(sweep):
    for _, r in sweep:
        estimated = {o.arm for o in r.options if o.status == "estimate"}
        for c in r.comparisons:
            assert {c.first, c.second} <= estimated


def test_the_sweep_exercises_every_outcome(sweep):
    seen = {o.status for _, r in sweep for o in r.options} | {r.applicable for _, r in sweep}
    assert {"estimate", "excluded", "insufficient_evidence", "APPLICABLE", "NOT_APPLICABLE"} <= seen


SECRET = re.compile(
    # a real key starts after a non-letter (quote, space, "="), so "risk-leg-and-foot" is not "sk-..."
    r"(?<![A-Za-z0-9])(?:sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{30,}|xox[bap]-[A-Za-z0-9-]{10,}|"
    r"AIza[0-9A-Za-z_-]{35})|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|(api[_-]?key|secret|token|password)\s*[:=]\s*['\"][A-Za-z0-9/+_-]{16,}['\"]",
    re.I,
)


def test_the_secret_scanner_catches_real_looking_keys():
    fake = "sk-" + "a1B2" * 6
    for text in (f'KEY="{fake}"', f"key: {fake}", "AKIA" + "ABCD1234EFGH5678", "ghp_" + "x" * 36,
                 "AIza" + "Sy" + "A" * 33, 'password = "' + "Zq9" * 6 + '"'):
        assert SECRET.search(text), text
    assert not SECRET.search("fda-removes-boxed-warning-about-risk-leg-and-foot-amputations-diabetes-medicine")


def test_no_secrets_are_committed():
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    hits = []
    for name in files:
        if "node_modules" in name or not name.endswith((".py", ".ts", ".tsx", ".js", ".json", ".yaml", ".yml",
                                                        ".toml", ".cfg", ".ini", ".txt", ".md", ".env", ".example", ".csv")):
            continue
        text = (ROOT / name).read_text(errors="ignore")
        hits += [f"{name}: {m.group(0)[:12]}…" for m in SECRET.finditer(text)]
    assert not hits, hits


def test_requirements_are_exactly_pinned():
    for line in (ROOT / "requirements-engine.txt").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            assert re.fullmatch(r"[A-Za-z0-9_.-]+==[0-9][0-9.]*", line), line


def test_no_two_paths_differ_only_by_letter_case():
    """macOS and Windows ignore case: `rag/` next to `RAG/` becomes one folder and breaks imports."""
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split("\n")
    paths = set()
    for f in filter(None, files):
        parts = f.split("/")
        paths.update("/".join(parts[:i]) for i in range(1, len(parts) + 1))
    seen: dict[str, str] = {}
    clashes = []
    for p in sorted(paths):
        other = seen.setdefault(p.lower(), p)
        if other != p:
            clashes.append((other, p))
    assert not clashes, clashes
