"""The CI workflows (P28): the one command runs on pull requests, and CI can never deploy the website.

The Netlify site `diacausal` is deployed by hand (docs/DEPLOY.md section 9): every production deploy costs credits. These tests
fail if a workflow mentions Netlify, a production deploy or a deploy secret, or if the checks stop running on pull requests.
"""

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.y*ml"))


def load(path):
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["on"] = data.pop(True, data.get("on"))  # YAML reads a bare `on:` key as the boolean True
    return data


def test_there_is_a_workflow_and_it_parses():
    assert WORKFLOWS, "no workflow found"
    for path in WORKFLOWS:
        assert "jobs" in load(path), path.name


def test_no_workflow_can_deploy_the_website():
    forbidden = [r"netlify", r"--prod\b", r"\bnetlify[-_ ]?cli\b", r"api\.netlify\.com", r"NETLIFY_", r"build[-_ ]hook", r"vercel", r"\bsupabase\b.*\bdeploy"]
    for path in WORKFLOWS:
        text = json.dumps(load(path))  # the parsed workflow: its comments may say "never Netlify"
        for pattern in forbidden:
            assert not re.search(pattern, text, re.I), f"{path.name} mentions {pattern!r}: CI must never deploy the website"
        triggers = load(path)["on"]
        assert set(triggers if isinstance(triggers, dict) else [triggers]) <= {"push", "pull_request", "workflow_dispatch", "schedule"}, \
            f"{path.name} reacts to an event that could be a deploy"


def test_there_is_no_site_wide_netlify_config_that_a_git_connection_would_pick_up():
    """Only web/netlify.toml exists (headers, no build step), and it says to skip every Git-triggered build, so connecting the
    site to GitHub by mistake would still not deploy. CLI deploys (`netlify deploy`) are unaffected."""
    assert not (ROOT / "netlify.toml").exists()
    toml = (ROOT / "web" / "netlify.toml").read_text(encoding="utf-8")
    assert re.search(r'^\s*ignore\s*=\s*"exit 0"', toml, re.M)
    assert re.search(r'^\s*command\s*=\s*""', toml, re.M)


def test_the_one_command_runs_on_pull_requests_on_linux_and_macos_and_windows_only_sets_up():
    wf = load(ROOT / ".github" / "workflows" / "check.yml")
    assert "pull_request" in wf["on"]
    jobs = wf["jobs"]
    check = jobs["check"]
    assert check["strategy"]["matrix"]["os"] == ["ubuntu-latest", "macos-latest"]
    assert "scripts/check_all.py" in "\n".join(step.get("run", "") for step in check["steps"])
    setup = jobs["setup-windows"]
    assert setup["runs-on"] == "windows-latest"
    runs = "\n".join(step.get("run", "") for step in setup["steps"])
    assert "scripts/setup.py" in runs and "check_all" not in runs
    for name, job in jobs.items():  # Windows appears nowhere else
        if name != "setup-windows":
            matrix = job.get("strategy", {}).get("matrix", {}).get("os", [])
            assert "windows-latest" not in matrix and "windows" not in str(job.get("runs-on", "")), name


def test_check_all_covers_everything_the_plan_lists():
    text = (ROOT / "scripts" / "check_all.py").read_text(encoding="utf-8")
    for needle in ("tests/engine", "tests/rag", "tests/guards", "tests/contract", "tests/test_imports.py", "tests/test_no_legacy_imports.py",
                   "tests/web", "test_privacy.py", "benchmark", "--quick", "xai_ablation.py", "pip_audit"):
        assert needle in text, needle
