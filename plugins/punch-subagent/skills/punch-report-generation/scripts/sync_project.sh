#!/bin/sh
# sync_project.sh -- copy between the project folder (network share) and the
# local workspace, with verification. "Run a long copy and assume it finished"
# is unsafe at share latency: a 217 MB PlanGrid pull once died silently at
# 120 of 171 files when the copy outlived a 120-second tool timeout, and a
# VPN drop makes a mounted share read as an EMPTY directory with no error.
#
# So this script:
#   1. refuses to treat an empty source as meaningful without --allow-empty
#      (empty and unreachable look identical on a dropped share)
#   2. copies incrementally (rsync when present, cp -R otherwise; re-running
#      resumes what a timeout cut short)
#   3. VERIFIES by comparing file count and total byte size, and exits nonzero
#      on any difference -- run it again until it passes
#
# Usage:
#   sh sync_project.sh <src_dir> <dst_dir> [--allow-empty]
#
# Copy back in small batches: the .docx first, then data/, scripts/, build/.
# Sync SOURCES back too, not just the .docx -- a drafted_items.json edit that
# lives only locally means the document and the file that generates it
# disagree, and a re-run silently reverts the change.

set -u

SRC="${1:?usage: sync_project.sh <src_dir> <dst_dir> [--allow-empty]}"
DST="${2:?usage: sync_project.sh <src_dir> <dst_dir> [--allow-empty]}"
ALLOW_EMPTY="${3:-}"

[ -d "$SRC" ] || { echo "ERROR: source not reachable: $SRC" >&2; exit 2; }

count_files() { find "$1" -type f 2>/dev/null | wc -l | tr -d ' '; }
total_bytes() {
  # portable du: -sb is GNU; fall back to summing find output
  if du -sb "$1" >/dev/null 2>&1; then du -sb "$1" | cut -f1
  else find "$1" -type f -exec wc -c {} + 2>/dev/null | tail -1 | awk '{print $1}'
  fi
}

SRC_N=$(count_files "$SRC")
if [ "$SRC_N" -eq 0 ] && [ "$ALLOW_EMPTY" != "--allow-empty" ]; then
  echo "ERROR: source has ZERO files: $SRC" >&2
  echo "An empty listing on a network share can mean the VPN dropped and the" >&2
  echo "mount is dead, not that the folder is empty. Verify the share is" >&2
  echo "reachable; pass --allow-empty only when empty is genuinely expected." >&2
  exit 3
fi

mkdir -p "$DST"
if command -v rsync >/dev/null 2>&1; then
  rsync -r --size-only "$SRC"/ "$DST"/
else
  cp -R "$SRC"/. "$DST"/
fi

DST_N=$(count_files "$DST")
SRC_B=$(total_bytes "$SRC")
DST_B=$(total_bytes "$DST")

echo "source : $SRC_N files, $SRC_B bytes"
echo "dest   : $DST_N files, $DST_B bytes"

if [ "$DST_N" -lt "$SRC_N" ] || [ "$DST_B" != "$SRC_B" ]; then
  echo "ERROR: copy INCOMPLETE (count or size differs). Re-run to resume;" >&2
  echo "a share-latency timeout mid-copy reports nothing on its own." >&2
  exit 4
fi
echo "verified: copy complete"
