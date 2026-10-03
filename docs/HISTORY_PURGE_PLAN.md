# History purge plan (NOT RUN)

> Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

**Status: written on 2026-10-03, never executed.** Nothing in this file has been run. Rewriting history is a team decision (Rhian, with the guide if needed), not something an agent does on its own (`AGENTS.md`: never rewrite history).

## Why

Third-party files whose licence is not cleared are gone from the current files (branch `chore/remove-restricted-files`), but **git keeps every old version**, so anyone can still download them from the public history.

| Path (as it exists in history) | In history since | Register entry (`RAG/sources.csv`) |
|---|---|---|
| `RAG/IDF_Rec_2025.pdf` | 2026-08-27 (`886eb46`) | S11, "all rights reserved" |
| `Research Papers/` (6 PDFs) | first commit | RP01 to RP05, licence UNVERIFIED |
| `RAG/dc252383.pdf` (ADA *Diabetes Care* article) | 2026-08-27, removed 2026-09-20 (`26afc41`) | X02, © ADA |
| `RAG/BTN_D1_Diabetes Management guidelines.pdf` | 2026-08-27, removed 2026-09-20 | X01 |
| `RAG/Diabetes handbooks, ency....pdf` | 2026-08-27, removed 2026-09-20 | X03 |

Not included: `RAG/Figure.ppt` (not in the register; probably the team's own flow chart; decide separately).

## Before you start (all of these, in order)

1. **Tell everyone** to push or finish their work and stop pushing until you say so.
2. **Merge or close all open pull requests.** They cannot survive the rewrite.
3. **Back up everything:**
   ```bash
   bash scripts/backup_repos.sh
   ```
   This makes mirror clones and zips in `~/DiaCausal-backups/<date>/` and in Google Drive. Check the zip for `DiaCausal-CDSS` exists and is about 120 MB.
4. **Install the tool** (once): `brew install git-filter-repo` (it is not installed on this computer today).

## The command

Run it on a **fresh clone**, never on your working folder (filter-repo refuses a non-fresh clone for a reason):

```bash
cd ~
git clone https://github.com/Rhian-Roy/DiaCausal-CDSS.git DiaCausal-purge
cd DiaCausal-purge
git filter-repo --invert-paths \
  --path "RAG/IDF_Rec_2025.pdf" \
  --path "Research Papers/" \
  --path "RAG/dc252383.pdf" \
  --path "RAG/BTN_D1_Diabetes Management guidelines.pdf" \
  --path "RAG/Diabetes handbooks, ency....pdf"
```

`--invert-paths` means "keep everything except these paths". Then check it worked, before anything goes to GitHub:

```bash
git log --all --oneline -- "RAG/IDF_Rec_2025.pdf" "Research Papers/" "RAG/dc252383.pdf"   # must print nothing
git count-objects -vH                                                                    # the repository should be smaller
python3.12 scripts/setup.py && python3 scripts/check_all.py                              # must still pass
```

Publishing the rewritten history needs a **force-push**, which also needs branch protection on `main` to be relaxed for a moment (it blocks force-pushes today). That step is deliberately not scripted here; do it only after the team agrees.

## Consequences

- **Every commit gets a new ID.** All links to old commits, and the commit IDs quoted in `docs/AUDIT_2026-10-03.md`, stop matching.
- **Everyone must re-clone.** Anyone who pulls into an old clone will mix old and new history and can push the removed files back. Delete old clones.
- **Open pull requests, branches and Dependabot branches break** and must be recreated.
- **Forks and other copies keep the old history.** Anyone who cloned or forked earlier still has the files. A purge limits future copying; it cannot recall past copies.
- **GitHub can keep cached views** of old commits (by direct commit link) until GitHub Support is asked to run garbage collection. For a copyright complaint, ask Support to purge cached views.
- **Issues, labels, milestones and the project board are not touched** (they are not in git).
- **The backup zips still contain the files.** Keep them private (Google Drive, not public).

## If something goes wrong

Restore from the mirror made in the backup step (`~/DiaCausal-backups/<date>/DiaCausal-CDSS.git`) with `git push --mirror` to a new empty repository, then compare. Do not delete the old repository until the new one has been checked and everyone has re-cloned.

## Not purging is also an option

The files are old third-party PDFs of modest size. If the team and the guide decide the risk is acceptable, record that decision here and in `RAG/sources.csv` notes instead of rewriting history.
