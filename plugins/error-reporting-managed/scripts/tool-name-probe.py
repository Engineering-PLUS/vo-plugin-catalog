#!/usr/bin/env python3
"""Tool-name probe (POSIX half; tool-name-probe.ps1 is the Windows half).

Purpose: reveal the EXACT tool name Claude Code assigns to report_issue, so we
can compare the two delivery paths:
  - bundled in a plugin's .mcp.json -> mcp__plugin_<plugin>_<server>__report_issue
  - declared as a bootstrap managed MCP server -> mcp__<server>__report_issue

On any PreToolUse whose tool_name contains "report_issue", emits
additionalContext (the channel proven to render in Cowork) telling the model to
quote the exact tool name verbatim, plus a systemMessage backup for terminal
surfaces. Silent for every other tool. Context-only; never a decision field;
always exits 0.

Disable with EPLUS_NO_TOOLNAME_PROBE=1.
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

    ctx = (
        "[tool-name-probe] A report_issue tool was just invoked. Its EXACT tool "
        "name is: `" + tool + "`. Quote this exact name verbatim at the top of "
        "your reply so the managed-vs-bundled MCP naming difference is visible. "
        "(Bundled shows mcp__plugin_<plugin>_<server>__report_issue; a bootstrap "
        "managed server shows mcp__<server>__report_issue.)"
    )
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": ctx,
        },
        "systemMessage": "[tool-name-probe] report_issue tool name = " + tool,
    }
    sys.stdout.write(json.dumps(out))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
