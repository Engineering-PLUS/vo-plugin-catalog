#!/usr/bin/env python3
"""Tool-name probe -- single cross-platform script (Windows host + Linux VM).

Reveals the EXACT tool name Claude Code assigns to report_issue so the two
delivery paths can be compared:
  - bundled in a plugin's .mcp.json -> mcp__plugin_<plugin>_<server>__report_issue
  - bootstrap managed MCP server    -> mcp__<server>__report_issue

On any PreToolUse whose tool_name contains "report_issue", emits ONLY a
`systemMessage` (which renders in the chat as a hook code block, visible
directly). It does NOT inject additionalContext: an imperative instruction on a
PreToolUse turn reads as prompt injection and gets the tool call BLOCKED by the
auto-mode classifier (observed 2026-08-25). systemMessage carries no instruction
to the model, so it's safe.

Silent for every other tool. Never a decision field; always exits 0.
Disable with EPLUS_NO_TOOLNAME_PROBE=1.

Invoked directly as `python <this>` -- one interpreter, no shell polyglot, so
there is no foreign-shell "command not found" noise. Requires python on PATH
(host and VM).
"""
import json
import os
import sys


def main():
    if os.environ.get("EPLUS_NO_TOOLNAME_PROBE", ""):
        return
    raw = sys.stdin.buffer.read()
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except Exception:
        return
    if not isinstance(data, dict):
        return
    tool = data.get("tool_name")
    if not isinstance(tool, str) or "report_issue" not in tool:
        return

    if tool.startswith("mcp__plugin_"):
        shape = "plugin-bundled MCP"
    else:
        shape = "managed MCP server"
    msg = "[tool-name-probe] report_issue tool name = " + tool + "  (" + shape + ")"
    sys.stdout.write(json.dumps({"systemMessage": msg}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
