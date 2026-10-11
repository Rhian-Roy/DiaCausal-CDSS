"""The demo script (P29c; docs/DEMO_SCRIPT.md) and its check (scripts/demo_check.py): the six cases give the expected states, and the
script keeps the intended-use sentence, the synthetic-cohort statement, the six cases and their screens.

Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.
"""

import importlib.util
import re
from pathlib import Path

import pytest

from diacausal import INTENDED_USE

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "docs" / "DEMO_SCRIPT.md").read_text(encoding="utf-8")


def _demo_check():
    spec = importlib.util.spec_from_file_location("demo_check", ROOT / "scripts" / "demo_check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def results():
    m = _demo_check()
    server = m.InProcess()
    try:
        yield m, m.run(server)
    finally:
        server.close()


def test_every_expected_state_of_the_six_cases_passes(results):
    m, rows = results
    assert {case for case, *_ in rows} == {c[0] for c in m.CASES}
    failed = [(case, name) for case, _, name, ok in rows if not ok]
    assert failed == []


def test_the_check_would_catch_a_wrong_screen(results):
    """A reply that does not match its case fails: the emergency reply is not the identifier notice, and an answered card is not a
    refusal."""
    m, _ = results
    emergency = {"problems": [{"check": "red_flag"}], "intended_use": INTENDED_USE}
    assert not all(ok for _, ok in m.expectations("5 identifier", 422, emergency))
    card = {"intended_use": INTENDED_USE, "decision": "Decision support only. The clinician decides.", "effects": [], "excluded": [], "abstain": []}
    assert not all(ok for _, ok in m.expectations("4 emergency", 200, card))
    assert not all(ok for _, ok in m.expectations("1 typical patient", 200, card))


def test_the_script_opens_with_the_sentence_and_the_synthetic_cohort():
    opening = SCRIPT[SCRIPT.index("## Opening"):SCRIPT.index("## The six cases")]
    assert f'"{INTENDED_USE}"' in opening
    assert "synthetic India-calibrated cohort" in opening and "the clinician decides" in opening.lower()


def test_the_script_has_the_six_cases_each_with_what_to_do_the_screen_a_sentence_and_what_if():
    cases = re.split(r"(?m)^### Case ", SCRIPT)[1:]
    assert len(cases) == 6
    screens = ["17-answer-options-compared", "21-answer-no-clear-difference", "19-insufficient-evidence", "11-notice-emergency",
               "09-notice-identifier", "10-notice-out-of-scope"]
    for screen in screens:
        assert (ROOT / "design" / "screens-v2" / f"{screen}.html").exists() and screen in SCRIPT
    for case in cases:
        for part in ("**Do:**", "**Expect:**", "**Say:**", "**If it looks different:**"):
            assert part in case, (case[:30], part)
    m = _demo_check()
    for _, _, _, message in m.CASES[3:]:
        assert f"**{message}**" in SCRIPT, message  # what the script tells you to type is what the check asks


def test_the_script_names_no_number_that_a_benchmark_rerun_would_change():
    for case in re.split(r"(?m)^### Case ", SCRIPT)[1:]:
        assert not re.search(r"[−-]\d\.\d{2}\s*%", case), "no estimate values in the script: they change when the benchmark is rerun"
