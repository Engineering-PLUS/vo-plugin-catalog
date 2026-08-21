---
name: inspect-drawing
description: Use when the user wants an inventory or overview of a DWG drawing - layers, entity counts by type, blocks, xrefs, coordinate system (CRS), AEC or proxy objects, or a general "what's in this drawing" deep inspection. Calls the autocad MCP inspect_drawing tool. Works on a clone, never the original.
---

# Inspect a drawing

Call the `inspect_drawing` tool on the `autocad` MCP server (tool name
`mcp__autocad__inspect_drawing`; use the plugin-scoped variant if that is
the one available).

**What it does:** clones the DWG and inventories it headlessly in Core
Console: layers (including frozen/off), entity counts by type, AEC/proxy
objects, blocks, xrefs, and CRS. Roughly ~12s for a 38 MB drawing.

**Targeting:** defaults to the engineer's active drawing; accepts an
explicit path instead, in which case no session is needed at all.

**Caveats to relay when relevant:**

- The clone comes from the *last save* — run `get-cad-status` first and
  warn the user if there are unsaved changes.
- Headless Core Console lacks Map 3D `ade` functions (CRS may read
  unassigned) and AEC object enablers (Civil 3D objects may count as
  proxies). Xrefs are reported but not cloned.

**On failure:** if the tool is missing or errors, tell the user the
`autocad` connector is not connected or failed, quote the exact error, and
suggest checking the connector in the Claude desktop settings. Do not
describe drawing contents you did not observe.
