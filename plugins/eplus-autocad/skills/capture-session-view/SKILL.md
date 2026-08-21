---
name: capture-session-view
description: Use when the user wants a screenshot of exactly what they see in their AutoCAD, Map 3D, or Civil 3D session right now - "show me my screen", "capture my current view", including Civil 3D styling. Calls the autocad MCP capture_session_view tool. Instant and passive.
---

# Capture the session view

Call the `capture_session_view` tool on the `autocad` MCP server (tool
name `mcp__autocad__capture_session_view`; use the plugin-scoped variant
if that is the one available).

**What it does:** ~0.3s screenshot of the engineer's session window via
Win32 PrintWindow — exactly what they see, Civil 3D styling included.
Returns the PNG inline. Completely passive.

**Limits:** works even when the CAD window is behind other windows, but
**not when it is minimized** — if the capture comes back blank or fails,
ask the user to un-minimize the CAD window and retry.

**Rendered alternative:** for a clean image of the drawing itself
(extents, a coordinate window, layer-filtered), use `render-view` instead.

**On failure:** if the tool is missing or errors, tell the user the
`autocad` connector is not connected or failed, quote the exact error, and
suggest checking the connector in the Claude desktop settings.
