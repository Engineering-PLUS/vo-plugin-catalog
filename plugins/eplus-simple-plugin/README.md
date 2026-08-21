# eplus-simple-plugin

Test plugin for Engineering Plus — a minimal AEC toolkit used to verify plugin
installation and activation in Claude Cowork's sandboxed VM.

## Contents

| Component | Path | Purpose |
|-----------|------|---------|
| Manifest  | [`.claude-plugin/plugin.json`](.claude-plugin/plugin.json) | Plugin identity and metadata |
| Skill     | [`skills/aec-verify/SKILL.md`](skills/aec-verify/SKILL.md) | Confirms the plugin is loaded and reports the AEC project stage |
| Subagent  | [`agents/project-folder-inspector.md`](agents/project-folder-inspector.md) | Read-only: inventories a directory and reports findings |
| Hooks     | [`hooks/hooks.json`](hooks/hooks.json) | `SessionStart` env prep, `PreToolUse` layer-naming reminder, `SubagentStart`/`SubagentStop` activity logging |
| Settings  | [`settings.json`](settings.json) | Ships a default `subagentStatusLine` |
| Script    | [`scripts/subagent-statusline.sh`](scripts/subagent-statusline.sh) | Renders the per-subagent row in the agent panel |

## Subagent observability

The default agent-panel row (`name · description · token count`) says little about what a
subagent is actually doing. Two mechanisms address that, and they cover different halves:

**Live** — [`settings.json`](settings.json) ships a `subagentStatusLine`. Plugin
`settings.json` supports only the `agent` and `subagentStatusLine` keys, and this is the
latter. The script receives every visible row as one JSON object on stdin and writes one
`{"id": ..., "content": ...}` line per row it wants to override; rows it skips keep the
default rendering. It degrades to silence when no JSON parser is present, so a missing
`python3`/`jq` costs you the custom row, not the panel.

**After the fact** — `SubagentStart` and `SubagentStop` append their full hook payloads to
`${CLAUDE_PLUGIN_DATA}/subagent-activity.log`, one JSON object per line. `SubagentStop`
carries `agent_transcript_path`, which points at the subagent's own transcript — the
complete record of what it did.

Two things worth knowing before you extend this:

- **Anchor plugin-scoped matchers.** A plugin subagent's `agent_type` contains a colon,
  which puts the matcher on the regular-expression path. Write
  `^eplus-simple-plugin:project-folder-inspector$`, not the bare name.
- **`hooks` in agent frontmatter is ignored for plugin subagents.** Subagent hooks have to
  live here in `hooks/hooks.json`. Note also that every hook event fires *inside* subagents
  — `PreToolUse`/`PostToolUse` included, with `agent_type` present in the payload — so
  per-tool-call tracing is available without any subagent-specific event. A `Stop` hook
  inside a subagent is automatically converted to `SubagentStop`; don't declare both.

## Installation

Distributed through the [eplus-plugin-catalog](https://github.com/Engineering-PLUS/eplus-plugin-catalog)
marketplace, which is registered under the name `eplus-claude-plugins`.

### Manually

Add the marketplace:

```bash
claude plugin marketplace add Engineering-PLUS/eplus-plugin-catalog
```

Then install the plugin:

```bash
claude plugin install eplus-simple-plugin@eplus-claude-plugins
```

### Automatically, via settings

`extraKnownMarketplaces` only *registers* the catalog — on its own, nothing appears
under Plugins. Pair it with `enabledPlugins` so the plugin is installed and enabled
on startup with no manual step:

```json
{
  "extraKnownMarketplaces": {
    "eplus-claude-plugins": {
      "source": {
        "source": "github",
        "repo": "Engineering-PLUS/eplus-plugin-catalog"
      }
    }
  },
  "enabledPlugins": {
    "eplus-simple-plugin@eplus-claude-plugins": true
  }
}
```

Put this in `~/.claude/settings.json` to enable it for yourself, or in a project's
`.claude/settings.json` to prompt teammates when they trust that folder.

### Verifying

Run `/reload-plugins` (or restart the session), then invoke `/aec-verify`. A healthy
install reports the plugin as active, echoes the `drafting` project stage injected by
the `SessionStart` hook, and notes that the `project-folder-inspector` subagent is
available.

## Cowork compatibility notes

- **Must live inside the marketplace repo.** This plugin is referenced by the relative
  path `./plugins/eplus-simple-plugin`, not by a separate repository. Managed
  deployments that register the catalog through `allowedPluginMarketplaces` mark any
  plugin whose `source` is an *object* (`github`, `url`, `git-subdir`) as `external`
  and exclude it from install — the marketplace appears in the Directory's
  Organization tab with "No plugins available". Only a string source (a path inside
  this repo) is installable there. Keep it that way.
- **Clone transport (Claude Code CLI only):** a plugin source of type `github` clones
  over SSH and fails with `Permission denied (publickey)` on machines without an SSH
  key. Not applicable to the relative-path layout above, but relevant if you ever add
  a plugin from an outside repo for CLI-only use.
- **Sandbox isolation:** hook shell commands run in a hardened Linux VM and cannot
  reach the host machine. Keep commands POSIX-compatible.
- **Path substitution:** reference bundled files with `${CLAUDE_PLUGIN_ROOT}`.
- **Session context:** the `SessionStart` hook emits `additionalContext` (the supported
  mechanism) rather than writing to an env file, so the confirmation and project stage
  are injected reliably at session start.
- **Unsupported in Cowork:** background monitors and LSP servers are skipped on
  restricted hosts and are intentionally omitted here.
