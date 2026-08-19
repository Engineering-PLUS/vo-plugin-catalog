#!/bin/sh
# Flight recorder + visible tracer for every hook event it's wired to:
#   1. Appends the raw JSON payload to <log_root>/<session_id>/<Event>.jsonl
#   2. Emits {"systemMessage": "..."} on stdout so the USER sees, in the UI,
#      which event fired, what triggered it, where it was logged, and a
#      truncated payload excerpt. systemMessage is display-only: it carries no
#      decision fields, so it can never allow/deny/block anything.
#
# Set CLAUDE_HOOKLAB_QUIET to any non-empty value to silence the messages
# (logging still happens). hooks.json additionally invokes this through a
# fail-open wrapper that forces exit 0, so even a corrupted copy of this file
# cannot block an event.
#
# Log root resolution order:
#   1. ${CLAUDE_HOOKLAB_LOG_ROOT}  -- explicit per-machine override
#   2. ${CLAUDE_PROJECT_DIR}, else $PWD  -> <cwd>/.hook-lab/events
#      The working directory is the one location shared by the hook runner, the
#      session's file tools, the bash tool, and (via a connected folder) the host --
#      so captures made inside Cowork's sandbox are actually retrievable.
#   3. ${CLAUDE_PLUGIN_DATA}/events  -- last resort; local to wherever the hook ran
#
# No machine-name segment: every Cowork session reports hostname "claude", so the
# session_id (already in the path) is what actually disambiguates.
#
# Silent on missing python3/jq: the event still fires normally, it just isn't logged.

set -u

payload=$(cat)

cwd_root="${CLAUDE_PROJECT_DIR:-${PWD:-.}}/.hook-lab/events"
fallback_root="${CLAUDE_PLUGIN_DATA:-.}/events"

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
    | HOOKLAB_LOG_ROOT_OVERRIDE="${CLAUDE_HOOKLAB_LOG_ROOT:-}" \
      HOOKLAB_CWD_ROOT="$cwd_root" \
      HOOKLAB_FALLBACK_ROOT="$fallback_root" \
      HOOKLAB_QUIET="${CLAUDE_HOOKLAB_QUIET:-}" \
      "$pyexe" -c '
import json, os, sys

payload = sys.stdin.read()
try:
    data = json.loads(payload)
    # Compact to one line so the .jsonl invariant holds even for pretty-printed
    # input (e.g. fixture replays); live payloads are already single-line.
    line = json.dumps(data, separators=(",", ":")) + "\n"
except Exception:
    data = {}
    line = payload if payload.endswith("\n") else payload + "\n"

event = (data.get("hook_event_name") if isinstance(data, dict) else None) or "unknown"
session = (data.get("session_id") if isinstance(data, dict) else None) or "unknown-session"

roots = [
    os.environ.get("HOOKLAB_LOG_ROOT_OVERRIDE", ""),
    os.environ.get("HOOKLAB_CWD_ROOT", ""),
    os.environ.get("HOOKLAB_FALLBACK_ROOT", ""),
]

logged_to = ""
for root in roots:
    if not root:
        continue
    directory = os.path.join(root, session)
    try:
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, event + ".jsonl")
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
        logged_to = path
        break
    except Exception:
        continue

# Visible trace for the user. systemMessage only -- never decision fields.
if not os.environ.get("HOOKLAB_QUIET", ""):
    trigger_bits = []
    if isinstance(data, dict):
        for key in ("tool_name", "prompt", "file_path", "source", "reason", "message", "trigger"):
            value = data.get(key)
            if isinstance(value, str) and value:
                if len(value) > 80:
                    value = value[:80] + "..."
                trigger_bits.append(f"{key}={value}")
    excerpt = json.dumps(data, separators=(",", ":")) if data else payload.strip()
    if len(excerpt) > 500:
        excerpt = excerpt[:500] + "... [truncated]"
    msg = f"[hook-lab] {event} fired"
    if trigger_bits:
        msg += " (" + ", ".join(trigger_bits) + ")"
    msg += " | logged: " + (logged_to or "NOWHERE (all log roots failed)")
    msg += " | payload: " + excerpt
    sys.stdout.write(json.dumps({"systemMessage": msg}))
' 2>/dev/null
elif command -v jq >/dev/null 2>&1; then
  # Compact to one line for the same .jsonl-invariant reason as the python path.
  compact=$(printf '%s' "$payload" | jq -c . 2>/dev/null)
  [ -n "${compact:-}" ] && payload="$compact"
  event_name=$(printf '%s' "$payload" | jq -r '.hook_event_name // "unknown"' 2>/dev/null)
  session_id=$(printf '%s' "$payload" | jq -r '.session_id // "unknown-session"' 2>/dev/null)
  [ -z "${event_name:-}" ] && event_name="unknown"
  [ -z "${session_id:-}" ] && session_id="unknown-session"

  logged_to=""
  for root in "${CLAUDE_HOOKLAB_LOG_ROOT:-}" "$cwd_root" "$fallback_root"; do
    [ -z "$root" ] && continue
    data_dir="$root/$session_id"
    if mkdir -p "$data_dir" 2>/dev/null \
       && printf '%s\n' "$payload" >> "$data_dir/$event_name.jsonl" 2>/dev/null; then
      logged_to="$data_dir/$event_name.jsonl"
      break
    fi
  done

  if [ -z "${CLAUDE_HOOKLAB_QUIET:-}" ]; then
    excerpt=$(printf '%s' "$payload" | cut -c1-500)
    jq -n --arg msg "[hook-lab] $event_name fired | logged: ${logged_to:-NOWHERE (all log roots failed)} | payload: $excerpt" \
      '{systemMessage: $msg}' 2>/dev/null
  fi
fi

exit 0
