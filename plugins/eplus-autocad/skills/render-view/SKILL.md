---
name: render-view
description: Use when the user wants an image of a drawing - PNG, PDF, or SVG render of a DWG, a view of the extents or a coordinate window, or a layer-filtered picture - without touching their live CAD session. Calls the autocad MCP render_view tool. Headless, works on a clone.
---

# Render a drawing view

Call the `render_view` tool on the `autocad` MCP server (tool name
`mcp__autocad__render_view`; use the plugin-scoped variant if that is the
one available).

**What it does:** headless render of a drawing clone. PNG uses the fast
PIL path — seconds even at ~348k entities — and returns inline. PDF/SVG
are vector via matplotlib and **slow on huge drawings**; warn the user
before choosing them for a large DWG.

**Options worth knowing:**

- Views: current viewport (read passively from the session), extents, or
  an explicit coordinate window.
- Layer wildcard filter to render only matching layers.
- Dark or white background.

**Not what they see:** this renders the clone with default styling. If the
user wants *exactly* what is on their screen (Civil 3D styles included),
use `capture-session-view` instead.

**On failure:** if the tool is missing or errors, tell the user the
`autocad` connector is not connected or failed, quote the exact error, and
suggest checking the connector in the Claude desktop settings.
