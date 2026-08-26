#!/bin/sh
# SessionStart hook (POSIX half; orient-punch-session.ps1 is the Windows half).
#
# When the session opens on a folder that already holds a punch report pipeline,
# point the model at that project's CLAUDE.md before it starts guessing, and
# restate the standing rules that have been re-derived before.
#
# Silent unless a pipeline is actually present, so it costs nothing in unrelated
# sessions.
#
# Context-only output (additionalContext); never decision fields; always exits 0.
# Disable with EPLUS_NO_PUNCH_ORIENT=1.

# Windows guard: orient-punch-session.ps1 handles Windows hosts. Exit before
# reading stdin so the .ps1 (which runs first in the polyglot command) gets the
# full payload and this half never double-fires.
[ "${OS:-}" = "Windows_NT" ] && exit 0
case "$(uname -s 2>/dev/null)" in
  MINGW*|MSYS*|CYGWIN*) exit 0 ;;
esac

payload=$(cat)

[ -n "${EPLUS_NO_PUNCH_ORIENT:-}" ] && exit 0

cwd=$(printf '%s' "$payload" \
      | sed -n 's/.*"cwd"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' \
      | head -1)
[ -n "$cwd" ] || cwd=$(pwd)
[ -d "$cwd" ] || exit 0

manual=$(find "$cwd" -maxdepth 3 -path '*_pipeline/CLAUDE.md' 2>/dev/null | head -1)
[ -n "$manual" ] || exit 0

rel=${manual#"$cwd"/}

printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"[punch-report] This folder holds a punch report pipeline. Read %s before touching any script; it carries this project%ss scope decision and the rules the renderer bakes in. Standing rules that have each been re-derived at least once: the pipeline outputs .docx ONLY (the reviewer makes the PDF from Word, which recalculates the TOC PAGEREF fields); the letterhead is built natively and never pasted in as a bitmap; item descriptions are in field-report voice, not photo narration and never third-person about the field engineer; scope lives only in SCOPE / consolidate.py --only. The project folder is on a network share and is over 45x slower than local disk for many-small-file steps, so copy out, work locally, and copy back, sources as well as outputs. Run scripts/smoke_test.sh before trusting the tooling."}}' \
  "$rel" "'"

exit 0
