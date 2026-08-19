# hook-testing-plugin

Test plugin for exercising every Claude Code hook event in the Claude Desktop Chat and
Cowork surfaces. It has no product-specific content — every hook, skill, and fixture
here exists purely to test hook behavior.

## Contents

| Component | Path | Purpose |
|-----------|------|---------|
| Manifest  | [`.claude-plugin/plugin.json`](.claude-plugin/plugin.json) | Plugin identity and metadata |
| Skill     | [`skills/hook-lab/SKILL.md`](skills/hook-lab/SKILL.md) | Test harness: replays a fixture through any hook event, or tails its live capture log |
| Hooks     | [`hooks/hooks.json`](hooks/hooks.json) | Generic logger wired to every hook event that's safe to observe live |
| Script    | [`scripts/log-event.sh`](scripts/log-event.sh) | Appends any hook event's raw JSON payload to `${CLAUDE_PLUGIN_DATA}/events/<EventName>.jsonl` |

## Installation

Distributed through the [vo-plugin-catalog](https://github.com/Engineering-PLUS/vo-plugin-catalog)
marketplace, which is registered under the name `vo-claude-plugins`.

### Manually

Add the marketplace:

```bash
claude plugin marketplace add Engineering-PLUS/vo-plugin-catalog
```

Then install the plugin:

```bash
claude plugin install hook-testing-plugin@vo-claude-plugins
```

### Automatically, via settings

`extraKnownMarketplaces` only *registers* the catalog — on its own, nothing appears
under Plugins. Pair it with `enabledPlugins` so the plugin is installed and enabled
on startup with no manual step:

```json
{
  "extraKnownMarketplaces": {
    "vo-claude-plugins": {
      "source": {
        "source": "github",
        "repo": "Engineering-PLUS/vo-plugin-catalog"
      }
    }
  },
  "enabledPlugins": {
    "hook-testing-plugin@vo-claude-plugins": true
  }
}
```

Put this in `~/.claude/settings.json` to enable it for yourself, or in a project's
`.claude/settings.json` to prompt teammates when they trust that folder.

### Verifying

Run `/reload-plugins` (or restart the session), then run
`/hook-testing-plugin:hook-lab --list`. A healthy install lists every fixture the
plugin ships and how many live captures each event has in the central log (or the
local fallback, if the central path isn't reachable from this surface).

## Cowork compatibility notes

- **Must live inside the marketplace repo.** This plugin is referenced by the relative
  path `./plugins/hook-testing-plugin`, not by a separate repository. Managed
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
- **Central logging, with a sandbox caveat:** `scripts/log-event.sh` writes to
  `G:\Software\VO\plugin-logs\<machine>\<session_id>\<EventName>.jsonl` by default so
  logs from every machine you test on land in one shared place. Cowork's sandboxed VM
  cannot reach that path (or any host path), so captures made there fall back to
  `${CLAUDE_PLUGIN_DATA}/events/<machine>/<session_id>/` **inside the VM**, which isn't
  retrievable after the session ends — treat Cowork captures as ephemeral and pull them
  out with `/hook-testing-plugin:hook-lab --logs <EventName>` before the session closes.
- **Silent by design:** `scripts/log-event.sh` never prints to stdout, so it can never
  influence a hook's decision (`permissionDecision`, `block`, `continue`, etc.) for any
  event it's attached to — it only logs.
- **Unsupported in Cowork:** background monitors and LSP servers are skipped on
  restricted hosts and are intentionally omitted here.

## Testing surfaces: Chat, Cowork, and Code

This plugin is developed for use with **Chat** and **Cowork** in the Claude Desktop app,
with **Code** disabled. Hooks fire identically across every surface Claude Code runs in
(terminal, IDE extensions, Desktop, and the web), but the two enabled surfaces differ in
what can trigger a given event:

| Aspect | Chat | Cowork |
| --- | --- | --- |
| Tool execution | Limited/no local tool calls, so most `PreToolUse`/`PostToolUse`-family events may never fire | Runs an agentic loop with a full tool set inside a sandboxed Linux VM — tool events fire normally |
| Shell access | Not applicable | Hook shell commands run unsandboxed but cannot reach the host machine; keep commands POSIX-compatible |
| Personal skills (`~/.claude/skills`) | Not read on your machine | Not read either — Cowork loads only skills enabled for your claude.ai account plus the repo's committed `.claude/skills/` |
| Skill `!` shell injection | N/A | Replaced with a `[shell command execution disabled by policy]` placeholder for **synced** skills; a plugin skill's own dynamic context still runs |
| `permission_prompt` notification timing | Routed through the Agent SDK `canUseTool` callback (Desktop hosts Claude Code this way) — fires ~6s after the ask, not deferred by typing | Same Agent SDK routing applies |
| Worktrees / `WorktreeCreate` | Not applicable | Only relevant for `--worktree` sessions, subagent `isolation: "worktree"`, or background sessions — verify separately before relying on it |

Because the exact tool surface available to **Chat** isn't fully documented, treat the
table above as a starting hypothesis and record what you actually observe per event in
the central log (see below) — that log is the source of truth for which events fire in
which surface.

## Hook test harness (`hook-lab`)

Two complementary ways to test every hook event in isolation:

1. **Live capture.** Every hook event this plugin can safely observe without changing
   its outcome is wired to `scripts/log-event.sh`, which appends the raw JSON payload to
   `G:\Software\VO\plugin-logs\<machine>\<session_id>\<EventName>.jsonl` — a central
   location shared across every machine you test on, so you never have to copy log
   files around by hand. Override the root per-machine with `CLAUDE_HOOKLAB_LOG_ROOT`
   if that drive letter or mount differs there. Just use Chat or Cowork normally and
   inspect the logs afterward to see exactly what Claude Code sent for each event that
   fired. `WorktreeCreate` is intentionally **not** wired live — see below.
2. **Synthetic replay.** The `/hook-testing-plugin:hook-lab <EventName>` skill pipes a
   realistic fixture from `skills/hook-lab/fixtures/` directly into the configured hook
   command(s) for that event and reports the exit code, stdout, and stderr. This works
   for every event, including ones that are hard or unsafe to trigger organically (for
   example `WorktreeCreate`, `TaskCreated`, `Elicitation`).

Run `/hook-testing-plugin:hook-lab --logs <EventName>` to instead tail the live capture
log for that event (current machine and session by default).

`WorktreeCreate` **replaces** Claude Code's default git worktree creation — a live hook
here that doesn't return a valid path would break real worktree creation for whoever has
the plugin enabled. Test it only through the synthetic fixture, never by wiring it into
`hooks/hooks.json`.
