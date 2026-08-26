#!/bin/sh
# PostToolUse hook (POSIX half; check-draft-voice.ps1 is the Windows half).
#
# When drafted_items.json is written or edited, sweep it for the two field-report
# voice rules and for em/en dashes, and report any hit back as context so it is
# fixed at authoring time rather than at build time.
#
# build_master.py already fails the build on all three. This hook exists because
# that failure arrives minutes later, after photos and clips have been rebuilt,
# and because both voice rules were originally caught by a human reading a
# rendered draft rather than by any check at all.
#
# Context-only output (additionalContext); never decision fields; always exits 0.
# Disable with EPLUS_NO_PUNCH_VOICE_CHECK=1.
#
# Pure POSIX sh: sed pulls the file path out of the payload and grep does the
# sweep, so no python or JSON parser is needed. The check is line-oriented and
# therefore coarser than the .ps1 half (it cannot scope itself to the description
# field), so it reports a count and defers the detail to build_master.py.

# Windows guard: check-draft-voice.ps1 handles Windows hosts. Exit before reading
# stdin so the .ps1 (which runs first in the polyglot command) gets the full
# payload and this half never double-fires.
[ "${OS:-}" = "Windows_NT" ] && exit 0
case "$(uname -s 2>/dev/null)" in
  MINGW*|MSYS*|CYGWIN*) exit 0 ;;
esac

payload=$(cat)

[ -n "${EPLUS_NO_PUNCH_VOICE_CHECK:-}" ] && exit 0

case "$payload" in
  *drafted_items.json*) ;;
  *) exit 0 ;;
esac

file=$(printf '%s' "$payload" \
       | sed -n 's/.*"file_path"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' \
       | head -1)
[ -n "$file" ] || exit 0
[ -f "$file" ] || exit 0

# Editor's Notes legitimately discuss photographs, so a whole-file grep
# overcounts. Restrict to description lines, which is where the rule applies.
hits=$(grep -o '"description"[^"]*"[^"]*"' "$file" 2>/dev/null \
       | grep -ciE 'photograph|in the frame|this photo|the field engineer')
dashes=$(grep -c '[—–]' "$file" 2>/dev/null)
[ "${hits:-0}" -eq 0 ] && [ "${dashes:-0}" -eq 0 ] && exit 0

printf '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"[punch-report] Voice check on drafted_items.json flagged %s description(s) and %s line(s) with an em or en dash. Item descriptions are in field-report voice: state the condition directly rather than narrating the evidence (\\"Metal stud framing at this location carries a junction box with...\\", not \\"the photograph shows...\\"), and never refer to the field engineer in the third person since this report is theirs (\\"Work remained in progress at the time of the walk.\\"). For genuinely unclear pins write \\"could not be established during the walk and requires field verification\\". No em or en dashes anywhere. Editor%ss Notes are internal and exempt. build_master.py will fail the build and name the offending item, so fix these now rather than after a rebuild."}}' \
  "${hits:-0}" "${dashes:-0}" "'"

exit 0
