---
name: cad-workflow
description: Use this skill whenever a task touches AutoCAD, Map 3D, Civil 3D, DWG/DXF files, drawing inspection, drawing cleanup, CAD screenshots, or the autocad MCP tools (get_cad_status, inspect_drawing, analyze_size_distribution, inspect_entities, render_view, capture_session_view, select_in_session, open_for_editing, check_cad_installation). Encodes the EPLUS three-lane CAD doctrine — always load it before calling any autocad tool.
---

# EPLUS CAD workflow (autocad MCP)

Rules for working with AutoCAD-family sessions through the `autocad` MCP
server. Depending on how the server was delivered, its tools appear as
`mcp__autocad__<tool>` (managed connector) or
`mcp__plugin_eplus-autocad_autocad__<tool>` (this plugin). Same server,
same rules.

## Always start with status

Call `get_cad_status` before any drawing work. It is read-only and reports
every running AutoCAD-family session, open drawings, save state, and last
save time on disk. Never assume which drawing is open or whether it is
saved.

`check_cad_installation` is the setup/diagnostic check (registry scan, no
launches) — use it when tools fail or on a machine you have not seen
before. Civil 3D is not installed company-wide; never assume it is present.

## The three lanes

| Lane | Used for | Why |
| --- | --- | --- |
| Engineer's session (AutoCAD/Map 3D) | Passive COM reads only | `SendCommand` queues invisibly while unfocused and flushes into the engineer's live work |
| Core Console (headless) | All inspection/read work, on a clone | No focus dependence, no session risk, no license seat |
| Civil 3D automation session (GUI) | Edits, on a clone | Isolated from the engineer's session and settings |

**Every inspection and edit works on a clone of the last-saved DWG.**
Originals are never opened for write. Clones live in job folders under
`%LOCALAPPDATA%\autocad-mcp\work`; job folders persist for debugging.
Because clones come from the *last save*, unsaved changes in the
engineer's session are invisible to inspection — check save state in
`get_cad_status` and say so if results may be stale.

## Choosing tools

- `inspect_drawing` — first look at any drawing: layers, entity counts,
  AEC/proxy objects, blocks, xrefs, CRS. Headless, on a clone.
- `analyze_size_distribution` — pick cleanup thresholds from data
  (percentiles, cumulative histogram), never by guessing. Pass `reuse_job`
  to re-filter a previous scan in seconds instead of re-cloning.
- `inspect_entities` — deep DXF property dump for a *few* entities. A
  failed bounding box means the entity has no visible graphics.
- `render_view` — headless PNG is fast even on huge drawings; vector
  PDF/SVG is slow on huge drawings, so warn before choosing it.
- `capture_session_view` — instant screenshot of exactly what the engineer
  sees (works behind other windows, not minimized). Passive.
- `select_in_session` — the one sanctioned command into the engineer's
  live session: creates a gripped QSELECT-style selection so the engineer
  can review before acting. Session-touching: confirm intent first.
- `open_for_editing` — clones the drawing and opens the clone in the
  Civil 3D automation session, launching Civil 3D (a license seat) if
  needed. Session-touching: confirm intent first.

## Known limits

- Headless Core Console lacks Map 3D `ade` functions (CRS may read
  unassigned) and AEC object enablers (AECC objects may count as proxies).
- Xrefs are reported but not cloned.
- Exports must follow AEC standard layer naming.
