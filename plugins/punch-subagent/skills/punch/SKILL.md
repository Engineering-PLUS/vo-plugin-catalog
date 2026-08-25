---
name: punch
description: Use this skill whenever a task involves punch lists, punch walks, punch reports, field progress or site-inspection reports, security acceptance walks, construction deficiencies or defects, "what do we usually find" / recurring-issue questions, punch counts or closeout statistics, per-trade punch checklists, pulling field photos or marked-up sheets for an issue, or exporting a filtered punch list. It routes every such request to the punch-researcher subagent instead of querying inline.
argument-hint: <what to look up — e.g. "recurring telecom issues at NVA05A" or "open security items on sheet T02-01B">
---

# Punch requests — delegate to the punch-researcher subagent

**Do not query the punch database yourself.** For any punch-related request,
delegate the whole thing to the **`punch-researcher`** subagent (this plugin's
agent). It researches the EPLUS punch corpus in its own isolated context on a
cheaper model (Haiku) and returns only a concise summary.

## Why delegate

Punch lookups are verbose: a single `query_hermes_punch` at limit 25 returns
~9,800 tokens, and a `list_punch` page ~3,250. Running those inline floods this
conversation with raw item rows and photo links you won't reference again, on
whatever (more expensive) model this session uses. Delegating:

- **Preserves context** — the raw corpus output stays in the subagent; only the
  summary comes back here.
- **Cuts cost** — the research runs on Haiku, not the main model.

## How to delegate

Hand the user's punch request to the `punch-researcher` subagent via the Agent
tool (or name it in natural language / @-mention it). Pass the user's intent
verbatim plus any project / trade / status / sheet the user named — the
subagent owns the filter vocabulary and tool routing, so you don't need to.

When it returns, relay its summary to the user. If the user asks a follow-up on
the same thread of research, resume the same subagent rather than starting a new
one, so it keeps its context.

## What NOT to do

- Don't call the punch tools (`mcp__punch-query__*` /
  `mcp__eplus-punch-engine__*`) directly from the main conversation — that's the
  subagent's job and defeats the context savings.
- Don't answer punch questions from general construction knowledge. If the
  subagent reports the database was unreachable, relay that plainly and offer
  to retry; never fabricate a "recurring issues" list.

## Requirement

The punch MCP server must be available to the session as a bootstrap **managed**
server (this plugin bundles no `.mcp.json` and no token). The subagent inherits
those tools. Its `tools` allowlist accepts either managed server name —
`punch-query` or `eplus-punch-engine` — so whichever you deploy, the subagent
gets the tools. Without the server, the subagent reports the punch database
can't be reached.
