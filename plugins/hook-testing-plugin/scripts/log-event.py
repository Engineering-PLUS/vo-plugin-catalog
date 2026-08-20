#!/usr/bin/env python3
"""Flight recorder + visible tracer for every hook event it's wired to.

1. Appends the event's JSON payload (compacted to one line) to
   <log_root>/<session_id>/<Event>.jsonl
2. Emits {"systemMessage": "..."} on stdout so terminal surfaces show which
   event fired. Set CLAUDE_HOOKLAB_QUIET to any non-empty value to silence it
   (logging still happens).
3. COWORK VISIBILITY (2026-08-19 field reports, beautiful-vigilant-bohr):
   the Cowork desktop app accepts systemMessage and writes it to the
   transcript as a `hook_system_message` attachment but NEVER RENDERS it in
   the chat UI, and it never reaches the model either. Two extra channels
   compensate:
   a. additionalContext relay -- every event appends a one-line tracer to
      <root>/<session>/pending-relay.txt. When an event fires whose output
      schema supports hookSpecificOutput.additionalContext (see RELAY_EVENTS),
      the queue is drained into an additionalContext block that instructs the
      assistant to echo the tracer lines verbatim at the top of its next
      visible reply. Guaranteed to display on any surface, because it exits
      through normal assistant text. Disable with CLAUDE_HOOKLAB_NO_RELAY.
   b. displayContent banner experiment -- MessageDisplay drains its own queue
      (pending-banner.txt) and prepends a compact one-line banner to the
      displayed message via hookSpecificOutput.displayContent. Display-only;
      tests whether the Cowork renderer honors displayContent. Disable with
      CLAUDE_HOOKLAB_NO_BANNER.
   Stop and SubagentStop are deliberately NOT relay events: on those events
   additionalContext is "non-error feedback that continues the conversation",
   i.e. it would keep the turn alive -- unacceptable side effect for a
   passive tracer.

Why Python and not a .sh: the 2026-08-19 field reports (fervent-optimistic-
ptolemy) proved hooks execute wherever Claude Code itself runs -- on the
WINDOWS HOST in Cowork Chat, not in the sandbox VM. See log-event.ps1 for the
Windows half; this script is the POSIX half and must mirror it exactly.

Log root resolution order:
  1. ${CLAUDE_HOOKLAB_LOG_ROOT}          -- explicit per-machine override, used as-is
  2. ${CLAUDE_PROJECT_DIR}/.hook-lab/events
  3. Cowork-VM mount autodetect: if $HOME/mnt exists (VM-only layout), the first
     writable non-internal folder under it + /.hook-lab/events
  4. $PWD/.hook-lab/events               -- normal case on hosts and CLI
  5. ${CLAUDE_PLUGIN_DATA}/events        -- last resort

No machine-name path segment: session_id (already in the path) disambiguates.
This script must NEVER exit non-zero or print anything but the single JSON
output object: every failure path is swallowed.
"""
import json
import os
import sys

COWORK_INTERNAL_MOUNTS = {
    "outputs", "uploads", ".claude", ".local-plugins", ".auto-memory", ".hook-lab",
}

# Events whose JSON output schema honors hookSpecificOutput.additionalContext
# with no decision side effects. Stop/SubagentStop excluded on purpose: their
# additionalContext continues the conversation.
RELAY_EVENTS = {
    "SessionStart", "Setup", "SubagentStart",
    "UserPromptSubmit", "UserPromptExpansion",
    "PreToolUse", "PostToolUse", "PostToolUseFailure",
}

# Events never appended to the tracer queues (too chatty / self-referential).
QUEUE_SKIP = {"MessageDisplay"}

RELAY_QUEUE = "pending-relay.txt"
BANNER_QUEUE = "pending-banner.txt"
MAX_RELAY_CHARS = 6000


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


def queue_append(session_dir, filename, line):
    try:
        with open(os.path.join(session_dir, filename), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def queue_drain(session_dir, filename):
    """Read all queued lines and remove the queue file. Best-effort."""
    path = os.path.join(session_dir, filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = [ln.rstrip("\n") for ln in f if ln.strip()]
        os.remove(path)
        return lines
    except Exception:
        return []


def main():
    raw = sys.stdin.buffer.read()
    try:
        payload = raw.decode("utf-8-sig")
    except Exception:
        payload = raw.decode("latin-1", "replace")
    try:
        data = json.loads(payload)
        line = json.dumps(data, separators=(",", ":")) + "\n"
    except Exception:
        data = {}
        line = payload if payload.endswith("\n") else payload + "\n"

    event = (data.get("hook_event_name") if isinstance(data, dict) else None) or "unknown"
    session = (data.get("session_id") if isinstance(data, dict) else None) or "unknown-session"

    logged_to = ""
    session_dir = ""
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
            session_dir = directory
            break
        except Exception:
            continue

    # Compact one-line tracer used by systemMessage, relay, and banner.
    trigger_bits = []
    if isinstance(data, dict):
        for key in ("tool_name", "prompt", "file_path", "source", "reason", "message", "trigger"):
            value = data.get(key)
            if isinstance(value, str) and value:
                if len(value) > 80:
                    value = value[:80] + "..."
                trigger_bits.append(f"{key}={value}")
    tracer = f"[hook-lab] {event} fired"
    if trigger_bits:
        tracer += " (" + ", ".join(trigger_bits) + ")"

    # Queue the tracer for both visibility channels.
    if session_dir and event not in QUEUE_SKIP:
        queue_append(session_dir, RELAY_QUEUE, tracer)
        queue_append(session_dir, BANNER_QUEUE, tracer)

    out = {}

    # Channel b: displayContent banner on MessageDisplay (first delta only).
    if event == "MessageDisplay" and not os.environ.get("CLAUDE_HOOKLAB_NO_BANNER", ""):
        index = data.get("index") if isinstance(data, dict) else None
        if index == 0:
            queued = queue_drain(session_dir, BANNER_QUEUE) if session_dir else []
            if queued:
                banner = "[[hook-lab]] " + str(len(queued)) + " event(s): " + "; ".join(
                    q.replace("[hook-lab] ", "") for q in queued)
            else:
                banner = "[[hook-lab]] displayContent render test (no queued events)"
            if len(banner) > 1000:
                banner = banner[:1000] + "..."
            delta = data.get("delta") if isinstance(data, dict) else ""
            if not isinstance(delta, str):
                delta = ""
            out = {"hookSpecificOutput": {
                "hookEventName": "MessageDisplay",
                "displayContent": banner + "\n\n" + delta,
            }}
        # Non-first deltas: no output; original text displays unchanged.

    # Channel a: additionalContext relay on supporting events.
    elif event in RELAY_EVENTS and not os.environ.get("CLAUDE_HOOKLAB_NO_RELAY", ""):
        queued = queue_drain(session_dir, RELAY_QUEUE) if session_dir else [tracer]
        block = "\n".join(queued)
        if len(block) > MAX_RELAY_CHARS:
            block = "[...older tracer lines truncated...]\n" + block[-MAX_RELAY_CHARS:]
        ctx = (
            "[hook-lab visible tracer] The Cowork UI does not render hook "
            "systemMessage output, so you are the display channel. At the very "
            "top of your next visible reply, render the tracer lines below "
            "verbatim in a fenced code block labeled hook-lab, then continue "
            "with your normal answer. Do not omit or summarize them.\n" + block
        )
        out = {"hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": ctx,
        }}

        # SessionStart-only extras (beautiful-vigilant-bohr follow-up):
        # channel c -- initialUserMessage creates a visible USER turn (documented
        # for -p / SDK surfaces, which is how Cowork hosts Claude Code). Strong
        # visibility signal; makes the harness non-passive on session start.
        # channel d -- sessionTitle renders in the UI with zero model
        # involvement; never overwrites a title the user already set.
        if event == "SessionStart":
            if not os.environ.get("CLAUDE_HOOKLAB_NO_INITMSG", ""):
                out["hookSpecificOutput"]["initialUserMessage"] = (
                    "[hook-lab] This synthetic first message was injected by the "
                    "hook-testing-plugin SessionStart hook via initialUserMessage "
                    "to test turn-creation visibility on this surface. Tracer: "
                    + tracer + ". Acknowledge this tracer in one short line, then "
                    "wait for the user's real prompt."
                )
            if not os.environ.get("CLAUDE_HOOKLAB_NO_TITLE", ""):
                existing_title = data.get("session_title") if isinstance(data, dict) else None
                if not existing_title:
                    source = (data.get("source") if isinstance(data, dict) else None) or "?"
                    out["hookSpecificOutput"]["sessionTitle"] = (
                        "hook-lab " + source + " " + session[:8]
                    )

    # systemMessage retained for terminal surfaces (and the flight recorder
    # confirmation it carries). Discarded-by-design on some events; harmless.
    if not os.environ.get("CLAUDE_HOOKLAB_QUIET", "") and event != "MessageDisplay":
        excerpt = json.dumps(data, separators=(",", ":")) if data else payload.strip()
        if len(excerpt) > 500:
            excerpt = excerpt[:500] + "... [truncated]"
        msg = tracer
        msg += " | logged: " + (logged_to or "NOWHERE (all log roots failed)")
        msg += " | payload: " + excerpt
        out["systemMessage"] = msg

    if out:
        try:
            sys.stdout.write(json.dumps(out))
        except Exception:
            pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
