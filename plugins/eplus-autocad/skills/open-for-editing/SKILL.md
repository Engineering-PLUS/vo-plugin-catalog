---
name: open-for-editing
description: Use when the user wants to edit a drawing, open a DWG in the Civil 3D automation session, or prepare a working copy for modification. Calls the autocad MCP open_for_editing tool. Launches Civil 3D (a license seat) and works on a clone; confirm first.
---

# Open a drawing for editing

Call the `open_for_editing` tool on the `autocad` MCP server (tool name
`mcp__autocad__open_for_editing`; use the plugin-scoped variant if that is
the one available).

**What it does:** clones the DWG to a job folder and opens the *clone* in
the separate Civil 3D automation session, launching Civil 3D if it is not
already running. The engineer's own session and the original file are
never touched.

**Before calling, confirm with the user** — this launches Civil 3D, which
consumes a license seat, and first launch takes a while. A permission
prompt may also appear; that is expected. Civil 3D is not installed
company-wide: if the launch fails, run `check-cad-installation` to see
whether this machine has it at all.

**After opening:** tell the user where the clone lives (a job folder under
`%LOCALAPPDATA%\autocad-mcp\work`) and that edits happen there, not in the
original — merging results back is a manual, deliberate step.

**On failure:** if the tool is missing or errors, tell the user the
`autocad` connector is not connected or failed, quote the exact error, and
suggest checking the connector in the Claude desktop settings.
