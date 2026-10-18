"""More regressions from the audit of 17 Oct 2026 (the guard ones are in tests/guards/test_audit_regressions.py).

Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.
"""

import copy

import pytest
import yaml

from diacausal import config
from diacausal.orchestrator.layers import _label


def test_a_card_citation_names_the_source_its_year_the_section_and_the_page():
    """AGENTS.md invariant 6: source, version, section. The label used to stop at the year and page."""
    label = _label({"id": "S01", "issuer": "WHO", "version": "2018 (ISBN 978-92-4-155028-4)"}, "12", "Recommendations")
    assert label == "WHO 2018, § Recommendations, p.12"
    assert _label({"id": "S20", "issuer": "US FDA", "version": "2015-12-04"}, "?", "Safety Announcement") == "US FDA 2015, § Safety Announcement"
    assert _label({"id": "S01", "issuer": "WHO", "version": "2018"}, "7") == "WHO 2018, p.7"  # no section known: as before


@pytest.mark.parametrize("section", ["xai", "evidence_level"])
def test_the_params_loader_checks_the_xai_and_evidence_level_sections_too(section):
    raw = yaml.safe_load(config.PARAMS_PATH.read_text(encoding="utf-8"))
    assert section in config.SOURCED_SECTIONS
    broken = copy.deepcopy(raw)
    key = next(k for k, v in broken[section].items() if isinstance(v, dict) and "value" in v)
    del broken[section][key]["source"]
    problems = []
    config._check(broken[section], section, {}, problems)
    assert any(f"{section}.{key}" in p and "no source" in p for p in problems), problems
