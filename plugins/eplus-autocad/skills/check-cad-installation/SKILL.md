---
name: check-cad-installation
description: Use when CAD tools are failing, when verifying a new or unfamiliar machine, or when the user asks which AutoCAD products (AutoCAD, Map 3D, Civil 3D) are installed or whether the CAD toolchain is ready. Calls the autocad MCP check_cad_installation tool. Registry scan only, launches nothing.
---

# Check CAD installation

Call the `check_cad_installation` tool on the `autocad` MCP server (tool
name `mcp__autocad__check_cad_installation`; use the plugin-scoped variant
if that is the one available).

**What it reports:** installed AutoCAD-family products from the registry,
per-tool readiness, and the server version. It launches nothing — safe as
a pure diagnostic.

**When to reach for it:** other CAD tools erroring, first contact with a
machine, or the user asking "do I have Civil 3D here?". Civil 3D is not
installed company-wide — never assume it is present; this tool is how you
find out.

**Version check:** the reported `server_version` should match the pinned
release the org deploys; mention a mismatch to the user.

**On failure:** if the tool is missing or errors, tell the user the
`autocad` connector is not connected or failed, quote the exact error, and
suggest checking the connector in the Claude desktop settings. Do not
report installation state you did not observe.
