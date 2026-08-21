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
| Script    | [`scripts/log-event.py`](scripts/log-event.py) | Appends any hook event's JSON payload to the capture log and emits a visible `systemMessage` trace |

## Installation

Distributed through the [vo-plugin-catalog](https://github.com/Engineering-PLUS/vo-plugin-catalog)
marketplace, which is registered under the name `vo-claude-plugins`.

**Bootstrap only — no terminal commands.** This plugin is delivered to Claude Desktop
by including `extraKnownMarketplaces` and `enabledPlugins` in the bootstrap settings
payload, not by running `claude plugin marketplace add` / `claude plugin install` in a
terminal. That's the only installation mechanism used for testing this plugin:

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

`extraKnownMarketplaces` only *registers* the catalog — on its own, nothing appears
under Plugins. `enabledPlugins` is what installs and enables the plugin on startup with
no manual step.

### Verifying

Restart the session (or wait for the next bootstrap), then run
`/hook-testing-plugin:hook-lab --list`. A healthy install lists every fixture the
plugin ships and how many live captures each event has in the session's capture log
(under the working directory's `.hook-lab/events/`, unless overridden).

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
- **Hooks run on the HOST, not in the VM (Cowork Chat):** confirmed 2026-08-19 via
  the desktop app's own logs (`[HostLoop] cli.js`): hook commands execute wherever
  Claude Code itself runs, which for Cowork Chat is the user's Windows machine.
  An exec-form `sh` spawn therefore fails there ("Executable not found in $PATH").
  Hook commands must be cross-platform with ZERO interpreter assumptions: the
  single shell-form command runs `log-event.ps1` (PowerShell — the only
  interpreter guaranteed on Windows; Claude Code auto-detects pwsh/5.1) and
  `log-event.sh` (POSIX — guaranteed in the sandbox VM), each a no-op on the
  other's platform, with a trailing `exit 0` valid in both shell families.
  Verified on all three shell routes Claude Code uses: PowerShell 5.1, Git Bash,
  and plain sh — one capture, one message, exit 0 on each.
- **Path substitution:** reference bundled files with `${CLAUDE_PLUGIN_ROOT}`.
- **Working-directory logging:** the logger (`scripts/log-event.ps1` on Windows,
  `scripts/log-event.sh` → `log-event.py` on POSIX) writes to
  `<working directory>/.hook-lab/events/<session_id>/<EventName>.jsonl` by default
  (`$CLAUDE_PROJECT_DIR`, else the hook's `$PWD`). The working directory is the one
  location shared by the hook runner, the session's file tools, the bash tool, and —
  in Cowork — the connected folder, so captures made in the sandbox are retrievable
  from the host after the session ends. Set `CLAUDE_HOOKLAB_LOG_ROOT` per-machine to
  redirect captures somewhere else (e.g. a shared drive on Windows machines);
  `${CLAUDE_PLUGIN_DATA}/events` remains as a last-resort fallback.
- **Visible but harmless by design — three channels:** the logger's stdout
  carries display/context output only, never decision fields
  (`permissionDecision`, `block`, `continue`, etc.), so it can never influence
  an outcome. The channels (per the beautiful-vigilant-bohr field report:
  Cowork transcribes hook `systemMessage` as `hook_system_message` attachments
  but never renders them, and the model never sees them):
  1. `systemMessage` — inline tracer for terminal surfaces
     (`CLAUDE_HOOKLAB_QUIET=1` silences it).
  2. `additionalContext` relay — tracers queue in
     `<root>/<session>/pending-relay.txt`; events that support context
     injection (SessionStart, Setup, SubagentStart, UserPromptSubmit,
     UserPromptExpansion, PreToolUse, PostToolUse, PostToolUseFailure — NOT
     Stop/SubagentStop, whose additionalContext keeps the turn alive) drain the
     queue and instruct the assistant to echo the tracer lines in a fenced
     `hook-lab` block at the top of its visible reply
     (`CLAUDE_HOOKLAB_NO_RELAY=1` disables).
  3. `displayContent` banner — MessageDisplay (index 0) drains
     `pending-banner.txt` into a `[[hook-lab]] N event(s): ...` line prepended
     to the rendered message; display-only, invisible to the model and the
     transcript (`CLAUDE_HOOKLAB_NO_BANNER=1` disables).
  4. SessionStart extras: `initialUserMessage` injects a synthetic first USER
     turn (documented for `-p`/SDK surfaces — how Cowork hosts Claude Code) so
     the assistant visibly acknowledges the hook; note this makes the harness
     non-passive at session start (`CLAUDE_HOOKLAB_NO_INITMSG=1` disables).
     Field-tested caveat: the live renderer hides the synthetic turn, but
     re-opening the session renders it as a USER bubble.
     `sessionTitle` stamps the session title `hook-lab <source> <session8>` —
     field-tested as NOT visibly honored in Cowork (auto-titler wins); kept for
     other surfaces (`CLAUDE_HOOKLAB_NO_TITLE=1` disables).

  `tests/run_hook_suite.py` enforces the no-decision-fields invariant: stdout
  limited to `systemMessage` + `hookSpecificOutput.{hookEventName,
  additionalContext, displayContent}`, anything else fails as
  `FAIL_UNSAFE_STDOUT`.
- **Fail-open by design:** `hooks/hooks.json` invokes the logger through a wrapper
  that forces exit 0, so even a corrupted or CRLF-mangled copy of the script cannot
  block an event (a real failure mode: see the 2026-08-19 Cowork field reports, where
  an `autocrlf` checkout turned the logger into a blanket `PreToolUse` blocker under
  dash). `.gitattributes` pins `*.sh` to LF for the same reason.
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
| Shell access | Not applicable | The model's Bash tool runs inside the VM, but hook commands run on the HOST (see Cowork compatibility notes) — two different machines, two different filesystems |
| Personal skills (`~/.claude/skills`) | Not read on your machine | Not read either — Cowork loads only skills enabled for your claude.ai account plus the repo's committed `.claude/skills/` |
| Skill `!` shell injection | N/A | Replaced with a `[shell command execution disabled by policy]` placeholder for **synced** skills; a plugin skill's own dynamic context still runs |
| `permission_prompt` notification timing | Routed through the Agent SDK `canUseTool` callback (Desktop hosts Claude Code this way) — fires ~6s after the ask, not deferred by typing | Same Agent SDK routing applies |
| Worktrees / `WorktreeCreate` | Not applicable | Only relevant for `--worktree` sessions, subagent `isolation: "worktree"`, or background sessions — verify separately before relying on it |

Because the exact tool surface available to **Chat** isn't fully documented, treat the
table above as a starting hypothesis and record what you actually observe per event in
the capture log (see below) — that log is the source of truth for which events fire in
which surface.

## Hook test harness (`hook-lab`)

Two complementary ways to test every hook event in isolation:

1. **Live capture.** Every hook event this plugin can safely observe without changing
   its outcome is wired to `scripts/log-event.py`, which appends the raw JSON payload to
   `<working directory>/.hook-lab/events/<session_id>/<EventName>.jsonl` — right next
   to whatever you were working on when the event fired, and (in Cowork) inside the
   connected folder so it survives the session. Override the root per-machine with
   `CLAUDE_HOOKLAB_LOG_ROOT` to centralize captures on a shared drive instead. Just
   use Chat or Cowork normally and inspect the logs afterward to see exactly what
   Claude Code sent for each event that fired. `WorktreeCreate` is intentionally
   **not** wired live — see below.
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
