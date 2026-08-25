---
name: error-reporting-managed
description: (vo test variant) Use this skill whenever a tool call on any EPLUS MCP server errors, misbehaves, or returns something clearly wrong, or whenever the user explicitly asks for a change, fix, or feature on the EPLUS side of the tooling. Teaches when and how to file a report with the report_issue tool — fire-and-forget logging to the EPLUS central review system, one report per distinct issue, never blocking the user's actual task. This variant bundles NO MCP server; the error-reporting server is supplied via bootstrap managedMcpServers.
---

# EPLUS error reporting — MANAGED-SERVER test variant

Test copy of the error-reporting skill for the managed-MCP experiment. This
plugin **bundles no MCP server** — the error-reporting server is declared in the
bootstrap `managedMcpServers` config instead. So the `report_issue` tool should
appear here as `mcp__error-reporting__report_issue` (managed form), NOT the
plugin-bundled form `mcp__plugin_error-reporting_error-reporting__report_issue`.

The plugin's `tool-name-probe` PreToolUse hook echoes the exact tool name each
time `report_issue` is called, so the naming difference between the two delivery
paths is directly observable. Everything below is the same filing contract as
the production plugin.

This is Claude's line to the EPLUS central logging system. Reports are
reviewed periodically by the EPLUS team to fix issues on their end.
Filing a report does exactly one thing: logs the message. Nothing else
happens.

## The tool

```
report_issue(message: str, category: str = "tool_failure",
             tool_name: str = "", server_name: str = "",
             severity: str = "medium", details: str = "")
```

Returns `{"status": "logged", "log_id": "<12-hex>", "message": "..."}`.

- `category` — `tool_failure` | `change_request` | `other`
- `severity` — `low` | `medium` | `high`. Use `high` only when the
  issue is blocking the user right now.
- `details` — the verbose supporting info: exact error text, the tool
  inputs that failed, what was tried.

## When to file

**Tool failure** — a tool call on any EPLUS MCP server
(`document-analysis`, `eplus-rfi-engine`, or `error-reporting` itself)
errors, misbehaves, or returns something clearly wrong (empty payloads,
stub markers, malformed results, wrong-document answers). File with:

- `category: "tool_failure"`
- the real `tool_name` and `server_name` that failed
- `message`: one line stating what went wrong
- `details`: the exact error text **verbatim**, the tool inputs that
  triggered it (argument names and shapes), and what was tried

**Change request** — the user explicitly asks for a change, fix, or
feature on the EPLUS side (server behavior, tool capabilities, workflow
gaps). File with:

- `category: "change_request"`
- `message`: one line summarizing the request
- `details`: the user's request **quoted** in their own words, plus any
  context on what prompted it

Anything worth logging that fits neither bucket: `category: "other"`.

## Fire-and-forget — the core contract

Filing a report is log-only. After the `{status: "logged", log_id}`
response comes back:

1. Tell the user the issue was logged, mentioning the `log_id`.
2. Continue the task immediately.

Never wait for, poll for, or promise a response, an answer, or a fix.
There is nothing to poll — the report went into a log for periodic
human review, and that is the whole transaction.

## One report per distinct issue

Do not re-file the same failure on every retry. File once when the
issue is established, then either work around it or tell the user it is
not working. Two genuinely different issues get two reports; the same
issue recurring gets one.

## No secrets in reports

Never put tokens, keys, credentials, or file contents into `message` or
`details`. Error text and tool argument names/shapes are enough for the
EPLUS team to diagnose.

## Reporting must never block the task

The user's actual task always comes first. If `report_issue` itself
fails, mention that to the user in one line and move on — do not retry
in a loop, and do not let a failed report derail the work. (A failure
of the error-reporting server is itself worth one `tool_failure` report
later, once it is reachable again — not a reason to stall now.)
