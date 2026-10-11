"""The CI workflows (P28): the one command runs on pull requests, and CI can never deploy the website.

The Netlify site `diacausal` is deployed by hand (docs/DEPLOY.md section 1): every production deploy costs credits. These tests
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


DEPLOY = (ROOT / "docs" / "DEPLOY.md").read_text(encoding="utf-8")


def test_deploy_guide_puts_the_public_site_first_with_a_draft_before_production_and_a_credit_check():
    """P29(a): section 1 is the public site; the free draft comes before the 15-credit production deploy, the credits are
    checked before each, and the old chat app's Docker guide is kept at the very end under its own title."""
    sections = [line for line in DEPLOY.splitlines() if line.startswith("## ")]
    assert sections[0].startswith("## 1. The public site")
    assert sections[-1] == "## Legacy chat app - not part of the submitted system"
    site = DEPLOY[DEPLOY.index("## 1. The public site"):DEPLOY.index("## 2. ")]
    draft, prod = site.index("### 1.5 Draft deploy"), site.index("### 1.6 Production deploy")
    commands_before_production = "".join(re.findall(r"```bash\n(.*?)```", site[:prod], re.S))
    assert draft < prod and "netlify deploy" in commands_before_production and "--prod" not in commands_before_production
    for part in (site[draft:prod], site[prod:]):
        assert "Check the credits" in part
    assert "15 credits" in site and "free" in site.lower()
    legacy = DEPLOY[DEPLOY.index("## Legacy chat app"):]
    for kept in ("docker compose up --build -d", "create_admin.py", "Backups", "Deploy checklist", "When something is wrong"):
        assert kept in legacy, kept


def test_the_deploy_guide_never_holds_a_key_and_says_where_to_set_it():
    assert not re.search(r"sb_publishable_[A-Za-z0-9_-]{6,}|sb_secret_|eyJhbGciOi", DEPLOY)
    assert "netlify env:set SUPABASE_PUBLISHABLE_KEY" in DEPLOY and "read -rs" in DEPLOY


def test_netlify_config_publishes_the_folder_with_no_build_secret_and_calls_only_supabase():
    toml = (ROOT / "web" / "netlify.toml").read_text(encoding="utf-8")
    assert re.search(r'^\s*publish\s*=\s*"\."', toml, re.M) and re.search(r'^\s*command\s*=\s*""', toml, re.M)
    assert not re.search(r"\$\{?[A-Z_]+|env\.|SECRET|KEY\s*=", toml), "no build step may need a secret"
    csp = re.search(r'Content-Security-Policy\s*=\s*"([^"]+)"', toml).group(1)
    directives = dict(d.strip().split(" ", 1) for d in csp.split(";") if d.strip())
    assert directives["default-src"] == "'self'" and directives["script-src"] == "'self'"
    connect = directives["connect-src"].split()
    assert connect[0] == "'self'" and len(connect) == 2 and re.fullmatch(r"https://[a-z0-9]{20}\.supabase\.co", connect[1]), connect
    assert directives["frame-ancestors"] == "'none'" and directives["object-src"] == "'none'"
