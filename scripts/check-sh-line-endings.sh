#!/bin/sh
# Fails if any tracked .sh file contains a carriage return. Cowork's sandbox runs
# hook scripts under dash, which aborts on CRLF — a corrupted "log-only" hook then
# blocks every event it's wired to (see cowork-field-reports 2026-08-19).
# Run from the repo root: sh scripts/check-sh-line-endings.sh
set -u

status=0
for f in $(git ls-files '*.sh'); do
  if grep -q "$(printf '\r')" "$f"; then
    echo "CRLF contamination: $f" >&2
    status=1
  fi
done

[ "$status" -eq 0 ] && echo "OK: all tracked .sh files are LF-clean"
exit "$status"
