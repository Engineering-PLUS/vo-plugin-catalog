# punch-subagent  (vo test plugin)

A focused test of **subagent delegation** for context preservation and cost
control, using the EPLUS punch corpus as the workload.

Instead of querying the punch database in the main conversation, the plugin's
`punch` skill routes every punch request to a **`punch-researcher`** subagent
that does the lookups in its own isolated context on **Haiku**, and returns
only a concise summary.

## Why the punch corpus is a good subagent test

Punch lookups are verbose (measured against the live corpus):

| Call | ≈ tokens |
|---|---|
| `punch_stats` (trade×status) | 120 |
| `grep_punch` (30 hits) | 780 |
| `get_punch_item` (one) | 970 |
| `list_punch` (50 rows) | 3,250 |
| `query_hermes_punch` (limit 25) | 9,800 |

Running those inline dumps raw item rows and expiring photo links into the main
context — on whatever (more expensive) model the session uses. Delegating keeps
that volume in the subagent and runs it on a cheaper model. Only the summary
returns.

## What's here (deliberately lean)

| Path | Purpose |
|---|---|
| `agents/punch-researcher.md` | The subagent: `model: haiku`, tools scoped to `mcp__eplus-punch-engine` + `Read`, with the full punch query workflow (tool routing, filter vocabulary, failure protocol) in its body. Returns a concise summary, never a raw dump. |
| `skills/punch/SKILL.md` | Main-facing skill: triggers on punch topics and **delegates** to `punch-researcher`. It contains no query workflow, so the main model can't do the lookups inline. |

Deliberately **not** copied from the production `eplus-punch-reports` plugin:
its `.mcp.json` (carries the shared bearer token — kept out of this repo), its
10 MB bundled `node_modules`, and the docx report-generation machinery. This is
a delegation test, not the full report pipeline.

## Requirement: managed punch server

This plugin bundles no MCP server. The `eplus-punch-engine` server must be
available to the session as a bootstrap **managed** server (same pattern as
`error-reporting-managed`), so the token never enters this repo:

```json
{
  "managedMcpServers": [
    { "name": "eplus-punch-engine", "transport": "sse",
      "url": "http://20.9.42.66:8653/sse",
      "headers": { "Authorization": "Bearer <token>" } }
  ],
  "coworkEgressAllowedHosts": ["20.9.42.66"]
}
```

The subagent's `tools: mcp__eplus-punch-engine` assumes the managed server name
`eplus-punch-engine` (tools resolve as `mcp__eplus-punch-engine__*`). If the
server is delivered bundled instead, the tool prefix differs
(`mcp__plugin_<plugin>_eplus-punch-engine__*`) and the subagent's `tools` list
would need to match.

## Test procedure (Cowork machine)

1. Ensure `eplus-punch-engine` is available as a managed server (above), with
   `20.9.42.66` in `coworkEgressAllowedHosts`.
2. Enable `punch-subagent` (it's `defaultEnabled: false`).
3. Ask a punch question, e.g. *"how many open Telecom items on POR03B?"* or
   *"what do we usually find on a security walk?"*
4. **Observe:**
   - Claude delegates to `punch-researcher` (a subagent row appears) rather
     than calling the punch tools itself.
   - The subagent runs on Haiku (cheaper), and the verbose corpus output stays
     in its context — the main thread receives only the summary.
   - The answer is grounded in real items (cited `PROJECT-number`), not general
     construction knowledge.

If Claude answers inline instead of delegating, the skill's delegation
instruction needs strengthening — that's part of what this test calibrates.
