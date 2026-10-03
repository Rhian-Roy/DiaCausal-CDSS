#!/usr/bin/env bash
# Back up the DiaCausal GitHub repositories (every branch, tag and commit).
#
#   bash scripts/backup_repos.sh
#
# Makes ~/DiaCausal-backups/<date>/, runs `git clone --mirror` for each repository,
# zips each mirror, and copies the zips to Google Drive if Google Drive for desktop
# is installed. Safe to rerun: a second run on the same day makes a new, time-stamped
# mirror and zip next to the first, so an earlier snapshot is never changed or replaced.
# It never deletes anything and never pushes.
set -uo pipefail

REPOS=(
  "Rhian-Roy/DiaCausal-CDSS"
  "Rhian-Roy/DiaCausal-RAG-Core"
)

DATE="$(date +%F)"
STAMP="$DATE"
DEST="$HOME/DiaCausal-backups/$DATE"
mkdir -p "$DEST"
# Already backed up today? Give this run its own name instead of touching the earlier one.
for repo in "${REPOS[@]}"; do
  if [ -e "$DEST/${repo#*/}.git" ]; then STAMP="$DATE-$(date +%H%M%S)"; break; fi
done
echo "Backing up to $DEST"

failed=0
zips=()
for repo in "${REPOS[@]}"; do
  name="${repo#*/}"
  if [ "$STAMP" = "$DATE" ]; then mirror_name="$name.git"; else mirror_name="$name-${STAMP#$DATE-}.git"; fi
  echo "- $repo: cloning a mirror"
  git clone --quiet --mirror "https://github.com/$repo.git" "$DEST/$mirror_name" \
    || { echo "  FAILED to clone $repo"; failed=1; continue; }
  zip="$DEST/$name-$STAMP.zip"
  (cd "$DEST" && zip -qr "$zip" "$mirror_name") || { echo "  FAILED to zip $repo"; failed=1; continue; }
  echo "  $(du -h "$zip" | cut -f1)  $zip"
  zips+=("$zip")
done

# Google Drive for desktop mounts at ~/Library/CloudStorage/GoogleDrive-<account>/.
drive=""
for d in "$HOME"/Library/CloudStorage/GoogleDrive-*; do
  [ -d "$d" ] || continue
  if [ -d "$d/My Drive" ]; then drive="$d/My Drive"; else drive="$d"; fi
  break
done

if [ -z "$drive" ]; then
  echo "Google Drive for desktop not found; zips are only in $DEST"
elif [ "${#zips[@]}" -gt 0 ]; then
  target="$drive/DiaCausal-backups/$DATE"
  mkdir -p "$target"
  cp "${zips[@]}" "$target/" && echo "Copied ${#zips[@]} zip(s) to $target" \
    || { echo "FAILED to copy to Google Drive"; failed=1; }
fi

if [ "$failed" -ne 0 ]; then
  echo "Backup finished WITH ERRORS (see above)."
  exit 1
fi
echo "Backup finished."
