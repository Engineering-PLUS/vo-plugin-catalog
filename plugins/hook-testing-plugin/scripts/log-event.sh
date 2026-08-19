#!/bin/sh
# Appends every hook event's raw JSON payload to a central log server instead of the
# plugin's local data dir, split into <log_root>/<machine>/<session_id>/<Event>.jsonl,
# so logs from every machine testing this plugin land in one shared place instead of
# files you'd otherwise have to copy around by hand.
#
# stdin  : the hook's JSON input, for any event
# stdout : nothing, ever -- this hook only logs, so it can never influence a
#          decision (permissionDecision, block, continue, etc.) for any event
#          it's attached to.
#
# Default central log root is G:\Software\VO\plugin-logs (a Windows path, resolved
# natively by python3 -- no drive letter guessing needed). Override per-machine with
# CLAUDE_HOOKLAB_LOG_ROOT if that drive/mount differs there.
#
# Falls back to ${CLAUDE_PLUGIN_DATA}/events/<machine>/<session_id>/ when the central
# root can't be created or written to -- notably inside Cowork's sandboxed VM, which
# cannot reach the host filesystem at all, so a network or local Windows drive is
# never reachable from there. Silent on missing python3/jq: the event still fires
# normally, it just isn't logged centrally (or, without either, isn't logged at all).

set -u

payload=$(cat)
fallback_root="${CLAUDE_PLUGIN_DATA:-.}/events"

machine_name="${COMPUTERNAME:-${HOSTNAME:-}}"
if [ -z "${machine_name:-}" ]; then
  machine_name=$(hostname 2>/dev/null)
fi
[ -z "${machine_name:-}" ] && machine_name="unknown-machine"

# Windows commonly only has "python", not "python3" (the latter is often an
# execution-alias stub that errors instead of running), so try both names.
pyexe=""
for candidate in python3 python; do
  if "$candidate" -c '' >/dev/null 2>&1; then
    pyexe="$candidate"
    break
  fi
done

if [ -n "$pyexe" ]; then
  printf '%s' "$payload" \
    | HOOKLAB_MACHINE="$machine_name" \
      HOOKLAB_LOG_ROOT_OVERRIDE="${CLAUDE_HOOKLAB_LOG_ROOT:-}" \
      HOOKLAB_FALLBACK_ROOT="$fallback_root" \
      "$pyexe" -c '
import json, os, platform, sys

payload = sys.stdin.read()
try:
    data = json.loads(payload)
except Exception:
    data = {}

event = data.get("hook_event_name") or "unknown"
session = data.get("session_id") or "unknown-session"
machine = os.environ.get("HOOKLAB_MACHINE", "unknown-machine")
line = payload if payload.endswith("\n") else payload + "\n"

override = os.environ.get("HOOKLAB_LOG_ROOT_OVERRIDE", "")
roots = []
if override:
    roots.append(override)
elif platform.system() == "Windows":
    # Native Windows path; python3 resolves this directly, no /g/ translation needed.
    roots.append(r"G:\Software\VO\plugin-logs")
roots.append(os.environ.get("HOOKLAB_FALLBACK_ROOT", ""))

for root in roots:
    if not root:
        continue
    directory = os.path.join(root, machine, session)
    try:
        os.makedirs(directory, exist_ok=True)
        with open(os.path.join(directory, event + ".jsonl"), "a", encoding="utf-8") as f:
            f.write(line)
        break
    except Exception:
        continue
' 2>/dev/null
elif command -v jq >/dev/null 2>&1; then
  event_name=$(printf '%s' "$payload" | jq -r '.hook_event_name // "unknown"' 2>/dev/null)
  session_id=$(printf '%s' "$payload" | jq -r '.session_id // "unknown-session"' 2>/dev/null)
  [ -z "${event_name:-}" ] && event_name="unknown"
  [ -z "${session_id:-}" ] && session_id="unknown-session"

  data_dir="$fallback_root/$machine_name/$session_id"
  mkdir -p "$data_dir" 2>/dev/null
  printf '%s\n' "$payload" >> "$data_dir/$event_name.jsonl" 2>/dev/null
fi

exit 0
