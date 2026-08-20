#!/usr/bin/env python3
"""Delete gate -- PreToolUse decision-control hook (POSIX half; the Windows
half is delete-gate.ps1, invoked by the same polyglot command since hooks run
on the HOST in Cowork Chat).

When a tool call's command looks like it deletes files, return
permissionDecision "ask" so the permission prompt appears even under lax
default permissions. Everything else: no output, normal flow.

Fail-open by design: unparseable payload, no command field, or any internal
error -> no output, exit 0, normal permission flow. This hook GATES deletes
for confirmation; it is not a hard deny, so a hook failure must never lock
the user out of their own session.

Disable with EPLUS_GUARDRAILS_NO_DELETE_GATE=1.
"""
import json
import os
import re
import sys

# Delete-shaped commands. Word-ish boundaries keep npm/format/etc. clean.
# rm/rmdir/unlink/shred/rimraf (POSIX), del/erase/rd/ri (cmd + PowerShell
# aliases), Remove-Item, [IO.File]::Delete, git clean, find ... -delete.
DELETE_RE = re.compile(
    r"(?i)"
    r"(?:(?:^|[\s;|&(])(?:rm|rmdir|unlink|shred|rimraf|del|erase|rd|ri)(?:$|[\s;|&)]))"
    r"|remove-item"
    r"|\[io\.(?:file|directory)\]::delete"
    r"|git\s+clean"
    r"|-delete(?:$|[\s;|&)])"
)


def main():
    if os.environ.get("EPLUS_GUARDRAILS_NO_DELETE_GATE", ""):
        return
    raw = sys.stdin.buffer.read()
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except Exception:
        return
    if not isinstance(data, dict):
        return
    tool_input = data.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str) or not command:
        return
    match = DELETE_RE.search(command)
    if not match:
        return

    excerpt = command if len(command) <= 160 else command[:160] + "..."
    reason = (
        "[delete-gate] This command appears to delete files or directories "
        "(matched: " + match.group(0).strip() + "). Command: " + excerpt
        + " -- confirm before it runs."
    )
    sys.stdout.write(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": reason,
        }
    }))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
