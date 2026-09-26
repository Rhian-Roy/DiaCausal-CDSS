"""Write docs/SOURCES.md (RAG guide step R1) from RAG/sources.csv — the licence table.

    python -m diacausal_rag.sources_table        # regenerate after editing RAG/sources.csv
"""

from __future__ import annotations

from diacausal_rag.ingest import CLEARED, ROOT, is_confirmed, load_sources

OUT = ROOT / "docs" / "SOURCES.md"
COLS = [("id", "ID"), ("title", "Source"), ("version", "Version / year"), ("bucket", "Licence bucket"),
        ("use_in_diacausal", "Use in DiaCausal"), ("date_checked", "Checked on"), ("checked_by", "Checked by")]


def _cell(text: str) -> str:
    return (text or "—").replace("|", "/").replace("\n", " ").strip()


def render() -> str:
    rows = load_sources().values()
    lines = [
        "# Guideline sources and licences (generated — do not edit by hand)",
        "",
        "> Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.",
        "",
        "Generated from `RAG/sources.csv` by `python -m diacausal_rag.sources_table`. Edit the CSV, then regenerate.",
        f"`diacausal_rag/ingest.py` ingests **only** rows whose bucket is exactly `{CLEARED}`; every other row is refused.",
        "A row stays a draft until a team member confirms the licence and fills \"Checked by\"; drafts are never ingested.",
        "",
        "| " + " | ".join(h for _, h in COLS) + " |",
        "|" + "---|" * len(COLS),
    ]
    for r in rows:
        lines.append("| " + " | ".join(_cell(r.get(k, "")) for k, _ in COLS) + " |")
    cleared = [r for r in rows if r["bucket"] == CLEARED]
    ready = [r["id"] for r in cleared if is_confirmed(r)] or ["none"]
    waiting = [r["id"] for r in cleared if not is_confirmed(r)] or ["none"]
    lines += ["", f"**Licence confirmed, may be ingested:** {', '.join(ready)}.",
              f"**Cleared bucket, waiting for a team member to confirm:** {', '.join(waiting)}."]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT}")
