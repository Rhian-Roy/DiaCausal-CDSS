"""Check the clinical rules table before review. From backend/:

    .venv/bin/python -m app.clinical.check

Prints every rule with its action, condition and source, and fails (exit 1) if any rule
is unusable — no source, a TODO left in, or a condition we cannot read. Member D and the
collaborating doctor should see a clean run, and every `reviewed_by` filled in, before
this table is used for anything but development.
"""

import sys

from app.clinical.rules import RULES_FILE, RuleProblem, load


def main() -> int:
    print(f"Clinical rules: {RULES_FILE}")
    try:
        table = load(strict=True)
    except RuleProblem as problem:
        print(f"\nNOT USABLE: {problem}", file=sys.stderr)
        print("Fix that rule (or remove it) — until then it is ignored by the running app.", file=sys.stderr)
        loose = load()
        print(f"\n{len(loose.rules)} rule(s) would still be used; {len(loose.refused)} refused.", file=sys.stderr)
        return 1

    print(f"version {table.version}: {len(table.rules)} rules, all with a source\n")
    for rule in table.rules:
        who = rule.option or "the patient"
        print(f"  {rule.id:45} {rule.action:12} {who:12} when {rule.when}")
        for source in rule.sources:
            print(f"      source: {source}")
        if rule.needs_recheck:
            print("      NEEDS RECHECK: re-open the source and confirm this rule")
        if rule.is_draft:
            print("      NOT REVIEWED: reviewed_by is empty")
    not_reviewed = [rule.id for rule in table.rules if rule.is_draft]
    if not_reviewed:
        print(f"\nDRAFT: {len(not_reviewed)} rule(s) have no reviewer. Every answer says so.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
