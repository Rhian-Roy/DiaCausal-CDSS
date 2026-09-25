# rag/corpus — licence-cleared documents only

Put a document here only if its source row in `RAG/sources.csv` has bucket **exactly**
`cleared_ingest` (today: S01 WHO 2018 and S08 FDA Drug Safety Communications, once Member B has
confirmed each licence and filled `checked_by`). Everything else is refused by `rag/ingest.py`.

Format: plain text, sections start with `## Section name`, page markers like `[page 12]`.
List each file in `manifest.csv` with its source id:

```
file,source_id
who_2018_second_line.txt,S01
```

Never put here: the IDF 2025 PDF, ADA Standards, NICE, textbooks, or anything "cite_only".
