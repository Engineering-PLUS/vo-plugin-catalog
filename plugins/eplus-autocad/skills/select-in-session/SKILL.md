---
name: select-in-session
description: Use when the user wants entities selected or highlighted in their live AutoCAD or Map 3D session - "select all the short lines", "highlight everything on this layer", QSELECT-style selection by type, layer, or length - so they can review before acting. Calls the autocad MCP select_in_session tool. Touches the live session; confirm first.
---

# Select in the live session

Call the `select_in_session` tool on the `autocad` MCP server (tool name
`mcp__autocad__select_in_session`; use the plugin-scoped variant if that
is the one available).

**What it does:** creates a live gripped selection in the engineer's own
session (QSELECT-style) by entity-type and layer wildcards, with optional
length bounds. The engineer sees the grips and decides what to do — you
select, they act.

**This is the one sanctioned command into the live session.** Everything
else works on clones. Before calling:

1. Confirm with the user that touching their live session right now is
   okay — a permission prompt may also appear; that is expected.
2. State what the filter will select so they can veto it.

Pair with `analyze-size-distribution` during cleanup: pick a threshold
from data, then select it live so the user can review before deleting.

**On failure:** if the tool is missing or errors, tell the user the
`autocad` connector is not connected or failed, quote the exact error, and
suggest checking the connector in the Claude desktop settings. Never claim
a selection exists that you did not create.
