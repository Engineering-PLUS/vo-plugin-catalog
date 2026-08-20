#!/bin/sh
# Six-case fixture replay verifying the patched log-event.py (POSIX half).
# Run from this directory: sh verify-fix.sh
# Expected results are asserted; exits non-zero on any deviation.
#
# Cases:
#   1. SessionStart  -> systemMessage + hookSpecificOutput.additionalContext (relay drains own tracer)
#   2. PreToolUse    -> same relay behavior; queue drained between calls
#   3. Stop          -> systemMessage ONLY (additionalContext would continue the conversation)
#   4. Notification  -> systemMessage ONLY (output discarded by design anyway; queued for later)
#   5. MessageDisplay index 0 -> hookSpecificOutput.displayContent with banner listing
#                                the queued Stop+Notification tracers; NO systemMessage
#   6. MessageDisplay index 1 -> empty stdout (original delta displays unchanged)
set -e
SCRIPT="${1:-../proposed-fix/log-event.py}"
ROOT="$(mktemp -d)"
trap 'rm -rf "$ROOT"' EXIT

run() {
  printf '%s' "$2" | CLAUDE_HOOKLAB_LOG_ROOT="$ROOT" python3 "$SCRIPT"
}

assert_has()    { echo "$1" | grep -q "$2" || { echo "FAIL($3): missing $2"; exit 1; }; }
assert_lacks()  { echo "$1" | grep -q "$2" && { echo "FAIL($3): unexpected $2"; exit 1; } || true; }

O=$(run 1 '{"session_id":"s","hook_event_name":"SessionStart","source":"startup"}')
assert_has "$O" '"additionalContext"' 1; assert_has "$O" '"systemMessage"' 1
echo "PASS 1: SessionStart relays additionalContext"

O=$(run 2 '{"session_id":"s","hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"ls"}}')
assert_has "$O" '"additionalContext"' 2; assert_has "$O" 'PreToolUse' 2
echo "PASS 2: PreToolUse relays additionalContext"

O=$(run 3 '{"session_id":"s","hook_event_name":"Stop","stop_hook_active":false}')
assert_lacks "$O" 'additionalContext' 3; assert_has "$O" '"systemMessage"' 3
echo "PASS 3: Stop emits no conversation-continuing context"

O=$(run 4 '{"session_id":"s","hook_event_name":"Notification","message":"needs attention"}')
assert_lacks "$O" 'additionalContext' 4; assert_has "$O" '"systemMessage"' 4
echo "PASS 4: Notification emits systemMessage only"

O=$(run 5 '{"session_id":"s","hook_event_name":"MessageDisplay","index":0,"final":true,"delta":"Hello."}')
assert_has "$O" '"displayContent"' 5; assert_has "$O" 'Stop fired' 5
assert_has "$O" 'Notification fired' 5; assert_lacks "$O" 'systemMessage' 5
echo "PASS 5: MessageDisplay index 0 prepends banner with queued events"

O=$(run 6 '{"session_id":"s","hook_event_name":"MessageDisplay","index":1,"final":true,"delta":"more"}')
[ -z "$O" ] || { echo "FAIL(6): expected empty stdout, got: $O"; exit 1; }
echo "PASS 6: MessageDisplay index 1 stays silent"

echo "ALL 6 CASES PASS"
