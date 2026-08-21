---
name: inspect-entities
description: Use when the user needs detailed DXF properties, bounding boxes, or a deep dump of specific entities in a DWG - "what is this entity", "why is this object invisible", or debugging a handful of problem objects by type or layer. Calls the autocad MCP inspect_entities tool.
---

# Inspect entities

Call the `inspect_entities` tool on the `autocad` MCP server (tool name
`mcp__autocad__inspect_entities`; use the plugin-scoped variant if that is
the one available).

**What it does:** full DXF property and bounding-box dump for a *few*
entities, filtered by type and/or layer. This is a microscope, not a
survey — use `inspect-drawing` for whole-drawing inventories and keep the
entity count here small.

**Reading results:** a failed bounding box means the entity has no visible
graphics — that is a finding, not an error; say so explicitly when the
user is chasing invisible objects.

**On failure:** if the tool is missing or errors, tell the user the
`autocad` connector is not connected or failed, quote the exact error, and
suggest checking the connector in the Claude desktop settings. Do not
describe entity properties you did not observe.
