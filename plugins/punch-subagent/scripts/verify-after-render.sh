#!/bin/sh
# PostToolUse hook (POSIX half; verify-after-render.ps1 is the Windows half).
#
# After gen_report.js runs, remind the model to verify the rendered document
# before calling the run finished.
#
# Stateless and deterministic: it keys off the render command itself rather than
# trying to track whether a document exists, which is why this is a PostToolUse
# on the render rather than a Stop hook.
#
# Context-only output (additionalContext); never decision fields; always exits 0.
# Disable with EPLUS_NO_PUNCH_VERIFY_NUDGE=1.

# Windows guard: verify-after-render.ps1 handles Windows hosts. Exit before
# reading stdin so the .ps1 (which runs first in the polyglot command) gets the
# full payload and this half never double-fires.
[ "${OS:-}" = "Windows_NT" ] && exit 0
case "$(uname -s 2>/dev/null)" in
  MINGW*|MSYS*|CYGWIN*) exit 0 ;;
esac

payload=$(cat)

[ -n "${EPLUS_NO_PUNCH_VERIFY_NUDGE:-}" ] && exit 0

case "$payload" in
  *gen_report.js*) ;;
  *) exit 0 ;;
esac
# run_pipeline.sh already verifies as its last step; no need to say it twice.
case "$payload" in
  *run_pipeline.sh*) exit 0 ;;
esac

printf '%s' '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"[punch-report] The report was just rendered. Run scripts/verify_report.py <build>/<output>.docx <build>/master_report_items.json before calling this done. It reads the OOXML directly and checks the things that are invisible in a quick look: em and en dashes, the field-report voice rules on descriptions, PAGEREF/bookmark integrity, absence of baked-in page numbers, w:updateFields, one page break per item, embedded photo count, and that the letterhead is native rather than a pasted bitmap. If you rendered from a local working copy, sync the sources back to the project folder too, not just the .docx, so the document and the file that generates it cannot disagree."}}'

exit 0
