"""P25 through /api/v1/ask: each option with an estimate carries up to 3 CLEAR drivers of its estimate against DPP-4i (exact SHAP of
the causal engine), each with a 95% interval that excludes zero; removed, abstained or hidden options carry none."""

import pytest
from pipeline_helpers import PRESETS, body

from diacausal.api.schemas import AnswerCardV1
from diacausal.config import load_params
from diacausal.xai import truth


def card(client, preset, question=None, rid="dr1"):
    patient, q = PRESETS[preset]
    r = client.post("/api/v1/ask", json=body(patient, question or q, rid))
    assert r.status_code == 200, r.text
    return AnswerCardV1.model_validate(r.json())


def test_options_with_an_estimate_carry_clear_drivers_with_95_percent_intervals(client):
    c = card(client, "typical")
    rows = {e.option: e for e in c.effects}
    assert set(c.drivers) == {"SGLT2i", "SU"}  # each against DPP-4i, the comparator; DPP-4i itself has nothing to compare
    modifiers = truth.modifiers(load_params())
    for option, drivers in c.drivers.items():
        assert rows[option].status == "ESTIMATED" and 1 <= len(drivers) <= 3
        for d in drivers:
            lo, hi = d.ci95
            assert lo <= d.contribution <= hi and (lo > 0 or hi < 0), d  # a driver's interval excludes zero
            assert d.feature in modifiers[f"{option}-DPP4i"]  # on this synthetic cohort the clear drivers are the true modifiers
        assert [abs(d.contribution) for d in drivers] == sorted((abs(d.contribution) for d in drivers), reverse=True)


def test_a_removed_option_carries_no_drivers(client):
    c = card(client, "egfr40_pancreatitis")  # SGLT2i removed by R01
    assert "SGLT2i" not in c.drivers and all(e.status == "ESTIMATED" for e in c.effects if e.option in c.drivers)


@pytest.mark.parametrize("preset,question", [("typical", "zebra-test")])
def test_when_no_estimate_is_shown_no_driver_is_either(client, preset, question):
    c = card(client, preset, question=question)  # the search found nothing: every level Insufficient, every estimate hidden
    assert c.drivers == {}


def test_the_drivers_also_reach_the_prompt_and_the_number_check(client, monkeypatch):
    from diacausal.llm import prompt_builder

    seen = {}
    real = prompt_builder.build_llm_prompt

    def spy(request, eligible, causal, drivers, evidence, **kw):
        seen["drivers"] = drivers
        return real(request, eligible, causal, drivers, evidence, **kw)

    monkeypatch.setattr(prompt_builder, "build_llm_prompt", spy)
    from diacausal.llm.providers import ollama

    cfg = ollama.load_llm_config()
    monkeypatch.setattr(ollama, "load_llm_config", lambda *a, **k: {**cfg, "provider": "ollama", "ollama_url": "http://127.0.0.1:9", "timeout_seconds": 1})
    patient, q = PRESETS["typical"]
    client.post("/api/v1/ask", json={**body(patient, q, "dr2"), "mode": "ollama"})
    assert set(seen["drivers"]) == {"SGLT2i", "SU"}
