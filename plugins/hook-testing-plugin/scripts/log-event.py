#!/usr/bin/env python3
"""Flight recorder + visible tracer for every hook event it's wired to.

1. Appends the event's JSON payload (compacted to one line) to
   <log_root>/<session_id>/<Event>.jsonl
2. Emits {"systemMessage": "..."} on stdout so the USER sees which event fired,
   what triggered it, where it was logged, and a truncated payload excerpt.
   systemMessage is display-only: no decision fields, so outcomes are never
   affected. Set CLAUDE_HOOKLAB_QUIET to any non-empty value to silence it
   (logging still happens).

Why Python and not a .sh: the 2026-08-19 field reports (fervent-optimistic-
ptolemy) proved hooks execute wherever Claude Code itself runs — on the WINDOWS
HOST in Cowork Chat, not in the sandbox VM. An exec-form `sh` spawn dies there
with "Executable not found in $PATH" before any script runs. hooks.json now
uses shell form (`python "${CLAUDE_PLUGIN_ROOT}/scripts/log-event.py"`), which
Claude Code routes to sh, Git Bash, or PowerShell as appropriate per platform;
`python "<path>"` is valid syntax in all three. Python is also immune to the
CRLF corruption that broke the original dash script.

Log root resolution order:
  1. ${CLAUDE_HOOKLAB_LOG_ROOT}          -- explicit per-machine override, used as-is
  2. ${CLAUDE_PROJECT_DIR}/.hook-lab/events
  3. Cowork-VM mount autodetect: if $HOME/mnt exists (VM-only layout), the first
     writable non-internal folder under it + /.hook-lab/events -- so captures
     land in the connected folder (host-visible) when running inside the VM,
     where $PWD is the VM-private $HOME. (fervent-optimistic-ptolemy finding B)
  4. $PWD/.hook-lab/events               -- normal case on hosts and CLI
  5. ${CLAUDE_PLUGIN_DATA}/events        -- last resort

No machine-name path segment: session_id (already in the path) disambiguates.
This script must NEVER exit non-zero or print anything but the systemMessage
object: every failure path is swallowed.
"""
import json
import os
import sys

COWORK_INTERNAL_MOUNTS = {
    "outputs", "uploads", ".claude", ".local-plugins", ".auto-memory", ".hook-lab",
}


def candidate_roots():
    roots = []
    override = os.environ.get("CLAUDE_HOOKLAB_LOG_ROOT", "")
    if override:
        roots.append(override)

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if project_dir:
        roots.append(os.path.join(project_dir, ".hook-lab", "events"))
    else:
        # Cowork-VM mount autodetect (only meaningful where $HOME/mnt exists)
        home = os.environ.get("HOME", "")
        mnt = os.path.join(home, "mnt") if home else ""
        if mnt and os.path.isdir(mnt):
            try:
                for name in sorted(os.listdir(mnt)):
                    if name in COWORK_INTERNAL_MOUNTS:
                        continue
                    path = os.path.join(mnt, name)
                    if os.path.isdir(path) and os.access(path, os.W_OK):
                        roots.append(os.path.join(path, ".hook-lab", "events"))
                        break
            except Exception:
                pass

    cwd = os.environ.get("PWD", "") or os.getcwd()
    roots.append(os.path.join(cwd, ".hook-lab", "events"))

    plugin_data = os.environ.get("CLAUDE_PLUGIN_DATA", ".")
    roots.append(os.path.join(plugin_data, "events"))
    return roots


def main():
    # Read bytes and decode with utf-8-sig: Windows PowerShell pipes prepend a
    # UTF-8 BOM, which json.loads rejects. Real hook stdin is BOM-free, but a
    # BOM-tolerant reader costs nothing and survives any re-encoding middleman.
    raw = sys.stdin.buffer.read()
    try:
        payload = raw.decode("utf-8-sig")
    except Exception:
        payload = raw.decode("latin-1", "replace")
    try:
        data = json.loads(payload)
        # Compact to one line so the .jsonl invariant holds even for
        # pretty-printed input (e.g. fixture replays).
        line = json.dumps(data, separators=(",", ":")) + "\n"
    except Exception:
        data = {}
        line = payload if payload.endswith("\n") else payload + "\n"

    event = (data.get("hook_event_name") if isinstance(data, dict) else None) or "unknown"
    session = (data.get("session_id") if isinstance(data, dict) else None) or "unknown-session"

    logged_to = ""
    for root in candidate_roots():
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
    if not os.environ.get("CLAUDE_HOOKLAB_QUIET", ""):
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
        try:
            sys.stdout.write(json.dumps({"systemMessage": msg}))
        except Exception:
            pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
