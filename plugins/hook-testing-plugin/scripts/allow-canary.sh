#!/bin/sh
# Precedence-test canary -- POSIX half (see allow-canary.ps1). Pure sh: the
# canary token is unique enough that a grep on the raw payload is safe, so no
# python or JSON parsing is needed. Inert without the token. Always exits 0.

[ "${OS:-}" = "Windows_NT" ] && exit 0
case "$(uname -s 2>/dev/null)" in
  MINGW*|MSYS*|CYGWIN*) exit 0 ;;
esac

payload=$(cat)

case "$payload" in
  *hooklab-precedence-canary*)
    printf '%s' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","permissionDecisionReason":"[hook-lab allow-canary] allow issued for hooklab-precedence-canary -- multi-plugin precedence test (expect the more restrictive decision to win)"}}'
    ;;
esac

exit 0
