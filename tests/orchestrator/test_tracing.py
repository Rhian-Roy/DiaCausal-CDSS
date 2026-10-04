"""diacausal/tracing.py (plan 8.5): the exact lines, the three outcomes, and nothing free-form in them."""

import logging
import re

import pytest

from diacausal import tracing
from diacausal.tracing import AbstainSignal, layer, traced

LINE = r"\[r1\] (entered|executing) x layer|\[r1\] (passed x layer|abstained x layer reason=[A-Z_]+|failed x layer error=\w+) \(\d+ ms\)"


def lines(caplog):
    return [r.getMessage() for r in caplog.records if r.name == "diacausal.trace"]


def test_a_passing_layer_logs_entered_executing_passed(caplog):
    caplog.set_level(logging.INFO)
    with layer("input guards", "c2f1"):
        pass
    got = lines(caplog)
    assert got[:2] == ["[c2f1] entered input guards layer", "[c2f1] executing input guards layer"]
    assert re.fullmatch(r"\[c2f1\] passed input guards layer \(\d+ ms\)", got[2]) and len(got) == 3


def test_an_abstain_logs_the_reason_code_and_is_re_raised(caplog):
    caplog.set_level(logging.INFO)
    with pytest.raises(AbstainSignal) as e, layer("retrieval", "r1"):
        raise AbstainSignal("NO_EVIDENCE", result={"kept": 1})
    assert e.value.code == "NO_EVIDENCE" and e.value.result == {"kept": 1}
    assert re.fullmatch(r"\[r1\] abstained retrieval layer reason=NO_EVIDENCE \(\d+ ms\)", lines(caplog)[-1])


def test_a_failure_logs_only_the_exception_class_never_its_message(caplog):
    caplog.set_level(logging.DEBUG)
    with pytest.raises(ValueError), layer("rules", "r1"):
        raise ValueError("secret patient value 9.87")
    last = lines(caplog)[-1]
    assert re.fullmatch(r"\[r1\] failed rules layer error=ValueError \(\d+ ms\)", last)
    assert "9.87" not in " ".join(r.getMessage() + str(r.exc_info) + str(r.args) for r in caplog.records)


def test_a_failure_is_a_warning_and_the_rest_are_info(caplog):
    caplog.set_level(logging.DEBUG)
    with pytest.raises(RuntimeError), layer("rules", "r1"):
        raise RuntimeError
    assert [r.levelno for r in caplog.records if r.name == "diacausal.trace"] == [logging.INFO, logging.INFO, logging.WARNING]


@pytest.mark.parametrize("bad", ["my question is zebra", "no_evidence", "X", "A" * 60, "NO EVIDENCE", ""])
def test_an_abstain_reason_must_be_a_code_not_free_text(bad):
    with pytest.raises(ValueError):
        AbstainSignal(bad)


@pytest.mark.parametrize("bad", ["Input Guards", "rules; drop", "x" * 60, "9 lives", ""])
def test_a_layer_name_must_be_plain_lower_case_words(bad):
    with pytest.raises(ValueError), layer(bad, "r1"):
        pass


def test_a_request_id_that_is_not_a_plain_id_is_logged_as_a_dash(caplog):
    caplog.set_level(logging.INFO)
    with layer("rules", "has spaces and 9.87"):
        pass
    assert all(m.startswith("[-] ") for m in lines(caplog)) and "9.87" not in " ".join(lines(caplog))


def test_the_decorator_traces_like_the_context_manager(caplog):
    caplog.set_level(logging.INFO)

    class Ctx:
        request_id = "d1"

    @traced("formatter")
    def run(ctx, x):
        return x + 1

    assert run(Ctx(), 1) == 2
    assert [m.split("] ")[1] for m in lines(caplog)][:2] == ["entered formatter layer", "executing formatter layer"]
    assert lines(caplog)[0].startswith("[d1] ") and "passed formatter layer" in lines(caplog)[2]

    @traced("formatter")
    def with_kw(*, request_id):
        raise tracing.AbstainSignal("NOTHING_TO_SAY")

    with pytest.raises(AbstainSignal):
        with_kw(request_id="d2")
    assert "[d2] abstained formatter layer reason=NOTHING_TO_SAY" in lines(caplog)[-1]


def test_a_stub_says_it_checked_nothing(caplog):
    caplog.set_level(logging.INFO)
    tracing.stub_notice("input guards", "s1")
    assert lines(caplog) == ["[s1] input guards layer is a STUB: nothing was checked, passing through"]


def test_the_console_handler_is_on_in_development_off_in_production_and_never_doubled():
    log = logging.getLogger("diacausal.trace")
    before = list(log.handlers)
    try:
        for h in [h for h in log.handlers if h.get_name() == "diacausal-trace-console"]:
            log.removeHandler(h)
        tracing.configure_console("development")
        tracing.configure_console("development")
        assert sum(h.get_name() == "diacausal-trace-console" for h in log.handlers) == 1
        tracing.configure_console("production")
        assert not any(h.get_name() == "diacausal-trace-console" for h in log.handlers)
    finally:
        log.handlers[:] = before


def test_the_trace_prints_to_the_console_in_development(capsys):
    log = logging.getLogger("diacausal.trace")
    before = list(log.handlers)
    try:
        for h in [h for h in log.handlers if h.get_name() == "diacausal-trace-console"]:
            log.removeHandler(h)  # a handler made earlier would hold an earlier test's stream
        tracing.configure_console("development")
        with layer("rules", "cons1"):
            pass
        err = capsys.readouterr().err
    finally:
        log.handlers[:] = before
    assert "[cons1] entered rules layer" in err and "[cons1] passed rules layer" in err
