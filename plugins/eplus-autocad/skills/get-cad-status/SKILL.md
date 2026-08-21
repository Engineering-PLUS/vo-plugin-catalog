---
name: get-cad-status
description: Use when the user asks what is open in AutoCAD, Map 3D, or Civil 3D, whether a drawing is saved, which CAD sessions are running, or before starting any other CAD/drawing task. Calls the autocad MCP get_cad_status tool. Read-only, safe to call anytime.
---

# Get CAD session status

Call the `get_cad_status` tool on the `autocad` MCP server (tool name
`mcp__autocad__get_cad_status`; if only a plugin-scoped variant like
`mcp__plugin_eplus-autocad_autocad__get_cad_status` exists, use that).

**What it reports:** every running AutoCAD-family session (AutoCAD, Map 3D,
Civil 3D), open drawings, saved/unsaved state, and the last save time on
disk. Read-only — it never touches the engineer's session.

**Use it first.** Other CAD tools work on a clone of the *last-saved* DWG,
so unsaved changes are invisible to them. If status shows unsaved changes,
tell the user their latest edits won't appear in inspections until they
save.

**On failure:** if the tool is not available or the call errors, tell the
user plainly: the `autocad` connector is not connected or failed, quote the
exact error, and suggest checking the connector in the Claude desktop
settings. Do not guess at session state or continue as if you had it.
