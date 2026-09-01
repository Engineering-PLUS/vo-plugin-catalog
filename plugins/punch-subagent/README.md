# punch-subagent  (vo test catalog)

The full EPLUS punch plugin — report production **and** corpus research —
carrying the vo-catalog modifications under test: subagent delegation, the
researcher call budget, and UI-visible hook diagnostics.

Two halves, same as the production `eplus-punch-reports` v0.4.0 it was
completed from (2026-08-26):

- **Produce** a punch report from a PlanGrid pull: `/punch-report [project
  folder]` stamps the `_pipeline/` into the project folder and walks intake →
  consolidate → draft → precedent → sheet clips → render → verify. Output is a
  .docx only (the reviewer generates the PDF from Word; a hook blocks the
  LibreOffice shortcut that broke TOC page numbers once already).
- **Search** four years of punch walks for precedent — but unlike production,
  every corpus lookup is **delegated to the `punch-researcher` subagent**
  instead of running in the main conversation.

## What's modified vs the production plugin (keep these on merge)

| Path | Change |
|---|---|
| `skills/punch/SKILL.md` | Delegation version: routes every punch request to `punch-researcher` instead of documenting the corpus tools inline. |
| `agents/punch-researcher.md` | The subagent (Sonnet 5, via model-routing): full query workflow, **hard budget of 3–4 corpus calls**, oversized-result protocol (Grep the spilled file, never whole-file Read), tools `mcp__punch-query, mcp__eplus-punch-engine, Read, Grep, Glob, Bash`. |
| `hooks/hooks.json` | Production's four workflow hooks **plus** the subagent diagnostics family (below). |
| `scripts/hook-probe.ps1`, `scripts/show-subagent-final.ps1` | Diagnostics + final-message echo, Windows-host PowerShell. |
| *(absent)* `.mcp.json` | Deliberately not bundled — see managed server below. Production's copy carries the shared bearer token; it stays out of this repo. |

## Hook visibility (field results 2026-08-26)

Proven on the Cowork test fleet:

- `SubagentStart` / `SubagentStop` / `PostToolUse:Agent` **all dispatch**, with
  `agent_type` = `punch-subagent:punch-researcher` (plugin-scoped — the anchored
  matcher is correct).
- `systemMessage` is a dead channel on Cowork: not rendered, not transcribed.
  Nothing here uses it.
- The **`[[punch-hooks]]` banner renders**: probe events queue tracer lines,
  and a `MessageDisplay` hook drains them into a display-only prefix on the
  next assistant reply (`displayContent` — the model and the transcript never
  see it; placement at the top of the reply is inherent to the channel).
- Every dispatch is also logged to
  `<session project dir>/<session_id>/hook-probe.log`, and the subagent's full
  final message to `subagent-final-messages.log` alongside it — both inside the
  directory the session exporter zips, so session-export zips carry the hook
  trail and Claude Log Lens displays them in its Logs tab.
- Machine-local fallback log: `$CLAUDE_PLUGIN_DATA/hook-probe.log`.
- Disable the final-message echo with `EPLUS_NO_SUBAGENT_ECHO=1`. Workflow
  hooks keep their own `EPLUS_NO_*` escape hatches (see hooks.json).

## Why delegate the corpus work

Punch lookups are verbose (measured against the live corpus):

| Call | ≈ tokens |
|---|---|
| `punch_stats` (trade×status) | 120 |
| `grep_punch` (30 hits) | 780 |
| `get_punch_item` (one) | 970 |
| `list_punch` (50 rows) | 3,250 |
| `query_hermes_punch` (limit 25) | 9,800 |

Running those inline dumps raw item rows and expiring photo links into the main
context. Delegating keeps that volume in the subagent; only the summary
returns. Budget: **3–4 corpus calls per subagent session** — at budget it
returns partial findings plus a proposed follow-up query, and the **main agent
decides** whether to relaunch with tighter direction. Local inspection of
spilled result files (Grep/Read windows/ls) is free.

## Requirement: managed servers (punch + plangrid)

This plugin bundles no MCP server. Both engines come from bootstrap
**managed** servers (same pattern as `error-reporting-managed`), so no token
ever enters this repo:

```json
{
  "managedMcpServers": [
    { "name": "punch-query", "transport": "sse",
      "url": "http://20.9.42.66:8653/sse",
      "headers": { "Authorization": "Bearer <token>" } }
  ],
  "coworkEgressAllowedHosts": ["20.9.42.66"]
}
```

**PlanGrid:** the skills additionally expect a managed server named
`plangrid` (tools `mcp__plangrid__*`). Its URL, token, and egress entries
live only in the bootstrap config — the operational note that matters here
is that `get_task_clips` / `get_photos` results are **curl'd directly**, so
the egress allowlist must cover the hosts those file/signed URLs are served
from, not just the MCP server itself. A missing egress host fails the
download, not the tool call — which is how it will present in a session.

**The managed server's `name` determines the tool prefix**, and the subagent's
`tools` allowlist must include it — the exact bug the first test hit
(2026-08-25): server named `punch-query` while the subagent allowlisted only
`mcp__eplus-punch-engine`. The subagent now allowlists **both** names; a third
name needs `mcp__<that-name>` added to its `tools`.

## Test procedure (Cowork machine)

1. Managed punch server available (named `punch-query` or
   `eplus-punch-engine`), `20.9.42.66` in `coworkEgressAllowedHosts`.
2. Refresh the marketplace clone and confirm the version — clone staleness has
   silently run old plugin builds before (2026-08-25).
3. Ask a punch question. Observe: delegation happens (subagent row appears),
   the `[[punch-hooks]]` banner prefixes the reply with
   SubagentStart/Stop tracers and the final-message excerpt, and the subagent
   stays within its 3–4 corpus-call budget.
4. Export the session and drop it in Log Lens: `hook-probe.log` and
   `subagent-final-messages.log` should appear under Logs.
5. For the report half: `/punch-report` in a project folder with a PlanGrid
   pull, per `skills/punch-report-generation/SKILL.md`.
6. **PlanGrid MCP:** confirm the managed `plangrid` server completes its
   OAuth sign-in on Cowork (unproven route — record the result), then
   `get_task_clips` on a scoped set and check all three result buckets
   behave (`mapped` downloads into `build/sheet_clips_jpg/`, `ambiguous`
   routes to the Task Report path, `unpublished` raises the publish-or-export
   question instead of silently picking).
