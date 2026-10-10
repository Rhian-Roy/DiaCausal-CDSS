"""P19: nothing whose licence is not cleared is ingested or shown, and prices stay "price unavailable" until they are cleared."""

import csv
import json
from pathlib import Path

from diacausal.rag.ingest.licence_gate import CLEARED, is_confirmed, load_sources

ROOT = Path(__file__).resolve().parents[2]
NOT_CLEARED = {"not_allowed", "unknown", "verbatim_only", "cite_only", "cite_only_structured", "cite_only_permission_requested", "cleared_ingest_PENDING"}


def test_the_p19_rows_carry_the_audit_buckets_and_the_gate_is_still_closed_for_every_one_of_them():
    s = load_sources()
    assert {sid: s[sid]["bucket"] for sid in ("S02", "S04", "S05", "S06", "S18")} == {
        "S02": "cleared_ingest", "S04": "verbatim_only", "S05": "verbatim_only", "S06": "unknown", "S18": "not_allowed"}
    for sid in ("S02", "S04", "S05", "S06", "S18"):
        assert s[sid]["date_checked"] == "2026-10-09" and not is_confirmed(s[sid]), sid  # a member has not confirmed it yet: still closed
        assert "licence_evidence" in s[sid] and s[sid]["licence_evidence"] not in ("", "Not checked", "—"), sid


def test_no_source_that_is_not_cleared_and_confirmed_is_in_the_corpus_or_the_website_index():
    s = load_sources()
    ok = {sid for sid, r in s.items() if r["bucket"] == CLEARED and is_confirmed(r)}
    manifest = list(csv.DictReader((ROOT / "knowledge_sources/corpus/manifest.csv").open(encoding="utf-8")))
    assert {r["source_id"] for r in manifest} <= ok
    index = json.loads((ROOT / "web/evidence.json").read_text(encoding="utf-8"))
    assert {c["citation"]["source_id"] for c in index["chunks"]} <= ok
    shown = {r["id"] for r in index["sources"] if r["bucket"] == index["cleared_bucket"] and r["confirmed"]}  # "In the search" on the website
    assert shown <= ok and not (shown & {sid for sid, r in s.items() if r["bucket"] in NOT_CLEARED})


def test_prices_stay_unavailable_until_they_are_cleared():
    rows = list(csv.DictReader((ROOT / "data/prices.csv").open(encoding="utf-8")))
    assert rows and all(r["inr_per_month"] == "" and r["status"] == "UNCONFIRMED" for r in rows)
    model = json.loads((ROOT / "web/model.json").read_text(encoding="utf-8"))
    assert all(p["label"] == "price unavailable" and p["inr_per_month"] is None for p in model["prices"].values())
