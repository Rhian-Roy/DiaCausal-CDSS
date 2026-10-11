"""Check the six demo cases of docs/DEMO_SCRIPT.md before a demo (P29c; run it before the dry run on Tue 27 Oct).

    .venv/bin/python scripts/demo_check.py                              # the same app, started here (no port opened)
    .venv/bin/python scripts/demo_check.py --url http://127.0.0.1:8000  # a clinic server already running (scripts/start_clinic.*)

The three presets are asked "Compare the three options for this patient." (the question the page's Compare button uses); the other
three cases are the messages the script tells you to type. Each expected state is one PASS or FAIL line. Exit code 0 only when every
line passes. Only case names and check names are printed: never a patient value, a reply or a passage. In-process, the audit log goes
to a temporary file, never to logs/audit.jsonl.

Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from diacausal import INTENDED_USE  # noqa: E402
from diacausal.causal_inference.recommend import DOSE_PATTERN  # noqa: E402
from diacausal.llm.golden import PRESET_PATIENTS, _FLAGS  # noqa: E402

COMPARE = "Compare the three options for this patient."
COMPARATOR = "DPP4i"
# (case, screen in design/screens-v2/, patient preset, what is typed). The messages are the ones docs/DEMO_SCRIPT.md tells you to type;
# the Aadhaar number is made up (it only has to pass the Verhoeff check digit, as a real one would).
CASES = [
    ("1 typical patient", "17-answer-options-compared.html", "typical", COMPARE),
    ("2 eGFR 40, past pancreatitis", "21-answer-no-clear-difference.html", "egfr40_pancreatitis", COMPARE),
    ("3 older, past hypoglycaemia", "21-answer-no-clear-difference.html + the abstain card of 19-insufficient-evidence.html", "older_hypo", COMPARE),
    ("4 emergency", "11-notice-emergency.html", "typical", "Patient unconscious in OPD, which add-on?"),
    ("5 identifier", "09-notice-identifier.html", "typical", "Patient Aadhaar 726018159082, HbA1c 8.4%, which add-on?"),
    ("6 out of scope (pregnancy)", "10-notice-out-of-scope.html", "typical", "She is pregnant, which add-on?"),
]


def leads(effect: dict) -> bool:
    """More HbA1c lowering than DPP-4i: the 95% interval of the difference is wholly below zero (the page's lead tag)."""
    d = effect.get("vs_comparator")
    return bool(d) and d["ci_high"] < 0


def expectations(case: str, status: int, reply: dict) -> list[tuple[str, bool]]:
    """The expected states of one case, as (check name, passed)."""
    checks = [("the intended-use sentence, word for word", reply.get("intended_use") == INTENDED_USE),
              ("no dose text anywhere in the reply", not DOSE_PATTERN.search(json.dumps(reply)))]
    if case.startswith(("4", "5", "6")):
        first = (reply.get("problems") or [{}])[0].get("check")
        want = {"4": "red_flag", "5": "identifier", "6": "scope"}[case[0]]
        checks += [("refused before anything else ran (HTTP 422)", status == 422),
                   (f"the {want.replace('_', ' ')} check is the one shown", first == want)]
        if case.startswith("5"):
            checks.append(("the identifier is not repeated in the reply", "726018159082" not in json.dumps(reply)))
        return checks
    effects = {e["option"]: e for e in reply.get("effects", [])}
    excluded = {(x["option"], x["rule_id"]) for x in reply.get("excluded", [])}
    checks += [("answered (HTTP 200)", status == 200), ("the card's decision line ends with \"The clinician decides.\"", str(reply.get("decision", "")).endswith("The clinician decides.")),
               ("every shown estimate has a 95% interval", all(e["hba1c_change"] is None or {"ci_low", "ci_high"} <= set(e["hba1c_change"])
                                                               for e in effects.values()))]
    if case.startswith("1"):
        checks += [("all three options estimated", all(effects.get(a, {}).get("status") == "ESTIMATED" for a in ("SGLT2i", "DPP4i", "SU"))),
                   ("no option removed by a rule", not excluded),
                   ("SGLT2i shows more HbA1c lowering than DPP-4i (interval excludes zero)", leads(effects.get("SGLT2i", {})))]
    elif case.startswith("2"):
        checks += [("SGLT2i removed by rule R01, not estimated", ("SGLT2i", "R01") in excluded and effects.get("SGLT2i", {}).get("status") == "EXCLUDED"
                    and effects["SGLT2i"]["hba1c_change"] is None),
                   ("DPP-4i and sulfonylurea estimated", all(effects.get(a, {}).get("status") == "ESTIMATED" for a in ("DPP4i", "SU"))),
                   ("no clear difference (no option leads)", not any(leads(e) for e in effects.values()))]
    elif case.startswith("3"):
        abstain = {a["option"] for a in reply.get("abstain", [])}
        checks += [("SGLT2i removed by rule R01", ("SGLT2i", "R01") in excluded),
                   ("sulfonylurea: insufficient evidence, with its abstain card and no number",
                    "SU" in abstain and effects.get("SU", {}).get("status") == "INSUFFICIENT_EVIDENCE" and effects["SU"]["hba1c_change"] is None),
                   ("DPP-4i estimated", effects.get("DPP4i", {}).get("status") == "ESTIMATED")]
    return checks


class InProcess:
    def __init__(self):
        from fastapi.testclient import TestClient

        from diacausal.api.main import create_app
        from diacausal.causal_inference import recommend

        recommend.AUDIT_PATH = Path(tempfile.gettempdir()) / "diacausal-demo-check-audit.jsonl"  # never the real audit log
        self.client = TestClient(create_app())
        self.client.__enter__()

    def ask(self, body: dict) -> tuple[int, dict]:
        r = self.client.post("/api/v1/ask", json=body)
        return r.status_code, r.json()

    def close(self):
        self.client.__exit__(None, None, None)


class Remote:
    def __init__(self, url: str):
        self.url = url.rstrip("/")

    def ask(self, body: dict) -> tuple[int, dict]:
        req = urllib.request.Request(f"{self.url}/api/v1/ask", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    def close(self):
        pass


def run(server) -> list[tuple[str, str, str, bool]]:
    """(case, screen, check, passed) for every expected state of the six cases."""
    out = []
    for i, (case, screen, preset, message) in enumerate(CASES, 1):
        body = {"schema_version": "1.0", "request_id": f"demo-check-{i}", "patient": {**_FLAGS, **PRESET_PATIENTS[preset]},
                "question": message, "mode": "template"}
        status, reply = server.ask(body)
        out += [(case, screen, name, ok) for name, ok in expectations(case, status, reply)]
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", help="check a server that is already running, e.g. http://127.0.0.1:8000")
    a = ap.parse_args(argv)
    server = Remote(a.url) if a.url else InProcess()
    try:
        rows = run(server)
    finally:
        server.close()
    last = None
    for case, screen, name, ok in rows:
        if case != last:
            print(f"\nCase {case}   (screen {screen})")
            last = case
        print(f"   [{'PASS' if ok else 'FAIL'}] {name}")
    failed = sum(not ok for *_, ok in rows)
    print(f"\n{'ALL' if not failed else failed} {'' if not failed else 'of '}{len(rows)} DEMO CHECKS {'PASSED' if not failed else 'FAILED'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
