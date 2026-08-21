# eplus-autocad

Skills and hooks that teach Claude the EPLUS CAD workflow. The `autocad`
MCP server itself is **not** bundled — it is delivered separately as a
managed connection (see the
[autocad-mcp](https://github.com/Engineering-PLUS/autocad-mcp) repo's
`DEPLOYMENT.md`). This plugin makes the model use those tools correctly
and report connector failures instead of improvising.

## Contents

| Component | Path | Purpose |
|-----------|------|---------|
| Manifest  | [`.claude-plugin/plugin.json`](.claude-plugin/plugin.json) | Plugin identity and metadata |
| Skill     | [`skills/cad-workflow/SKILL.md`](skills/cad-workflow/SKILL.md) | Umbrella: three-lane doctrine, clone rules, tool selection guide |
| Skills    | [`skills/`](skills/) | One skill per MCP tool (9 total): `get-cad-status`, `check-cad-installation`, `inspect-drawing`, `analyze-size-distribution`, `inspect-entities`, `render-view`, `capture-session-view`, `select-in-session`, `open-for-editing` |
| Hooks     | [`hooks/hooks.json`](hooks/hooks.json) | `SessionStart` context; `PreToolUse` ask-gate on the two session-touching tools |

Every per-tool skill ends with the same failure protocol: if the `autocad`
connector is missing or the call errors, the model tells the user exactly
that (with the real error) instead of silently skipping or fabricating
results. Skill descriptions are the discovery surface — the model invokes
them on its own from task context; slash commands are just the manual
override. If testers find a natural phrasing that fails to trigger a
skill, add it to that skill's `description` and bump the version.

## Tool naming

The managed connection must keep the server name `autocad` so tools appear
as `mcp__autocad__<tool>` — the skills and hooks reference that name. The
hook matcher also tolerates the plugin-scoped prefix
(`mcp__plugin_eplus-autocad_autocad__*`) in case the server is ever
bundled again:

```
^mcp__(plugin_eplus-autocad_)?autocad__(select_in_session|open_for_editing)$
```

## Versioning

Explicit semver in `plugin.json` — bump `version` whenever a change should
reach installed machines; pushing commits alone does nothing while a
version is pinned. Server updates are coordinated separately in the
managed connection config (the pinned `@v0.X.Y` uvx tag).

## Do not bundle the server here

A bundled `.mcp.json` was removed deliberately (v0.2.1). Verified behavior
on fleet machines: an admin-managed connector named `autocad` wins the
name and the app drops the plugin's copy with "collides with an
admin-managed direct-pool connector"; inside the Cowork VM the Windows
launch command cannot run at all. The managed connection is the single
delivery path for the server.

## Installation

From the `eplus-claude-plugins` marketplace (registered fleet-wide via the
managed deployment; manually: `claude plugin marketplace add
Engineering-PLUS/eplus-plugin-catalog`):

```bash
claude plugin install eplus-autocad@eplus-claude-plugins
```

Verify: the skills list shows the ten skills above, and with the managed
`autocad` connection active, asking *"what's the status of my CAD
session?"* triggers `get-cad-status` and returns live session data.
