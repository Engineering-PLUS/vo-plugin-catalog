---
name: hook-lab
description: Test a single Claude Code hook event in isolation, either by replaying a synthetic JSON fixture through its configured hook command(s), or by tailing the live capture log. Use when verifying hook input/output schemas, permission decisions, or additionalContext behavior without needing to organically trigger the event in a live Chat or Cowork session.
argument-hint: "[EventName] | --logs [EventName] | --list"
disable-model-invocation: true
allowed-tools: Bash(cat ${CLAUDE_SKILL_DIR}/fixtures/*), Bash(ls *), Bash(find *), Bash(hostname), Bash(python ${CLAUDE_PLUGIN_ROOT}/scripts/log-event.py), Bash(tail *)
---

# Hook Lab

Test harness for every Claude Code hook event this plugin knows about. Two modes:

1. **Fixture replay** (default): `/hook-testing-plugin:hook-lab <EventName>` pipes
   `fixtures/<EventName>.json` into the hook command(s) configured for that event in
   `${CLAUDE_PLUGIN_ROOT}/hooks/hooks.json`, and reports exactly what each command
   returned.
2. **Live log tail**: `/hook-testing-plugin:hook-lab --logs <EventName>` shows the most
   recent real payloads captured from an actual Chat or Cowork session, from the
   central log (or its local fallback — see "Locating the log root" below).

Run with no arguments, or `--list`, to see which events have fixtures and how many live
captures each has.

## Locating the log root

`scripts/log-event.py` writes to the first of these that it can create/write to.
Remember hooks execute wherever Claude Code itself runs — the user's HOST machine
in Cowork Chat, not the sandbox VM — so the resolved root may be a host path.

1. `${CLAUDE_HOOKLAB_LOG_ROOT}`, if that environment variable is set (explicit
   per-machine override, e.g. to point a Windows machine at a shared drive).
2. `${CLAUDE_PROJECT_DIR}` + `/.hook-lab/events`, when that variable is set.
3. Cowork-VM mount autodetect: when `$HOME/mnt` exists (the VM's layout), the
   first writable non-internal folder under it (i.e. the connected folder)
   + `/.hook-lab/events` — because in the VM, `$PWD` is the VM-private `$HOME`,
   not the connected folder.
4. The hook's `$PWD` + `/.hook-lab/events` — the normal case on hosts and CLI.
5. `${CLAUDE_PLUGIN_DATA}/events` — last resort, local to wherever the hook ran.

Within whichever root wins, payloads are split into
`<root>/<session_id>/<EventName>.jsonl` (no machine segment — Cowork sessions all
report the same hostname, so the session id is what disambiguates). Use
`${CLAUDE_SESSION_ID}` for the current session's `<session_id>` unless the user asks
about a different one.

## Available fixtures

`${CLAUDE_SKILL_DIR}/fixtures/` has one JSON file per event: `SessionStart`, `Setup`,
`InstructionsLoaded`, `UserPromptSubmit`, `UserPromptExpansion`, `MessageDisplay`,
`PreToolUse`, `PermissionRequest`, `PostToolUse`, `PostToolUseFailure`, `PostToolBatch`,
`PermissionDenied`, `Notification`, `SubagentStart`, `SubagentStop`, `TaskCreated`,
`TaskCompleted`, `Stop`, `StopFailure`, `TeammateIdle`, `ConfigChange`, `CwdChanged`,
`DirectoryAdded`, `FileChanged`, `WorktreeCreate`, `WorktreeRemove`, `PreCompact`,
`PostCompact`, `SessionEnd`, `Elicitation`, `ElicitationResult`. Each fixture matches the
input schema documented in `${CLAUDE_PLUGIN_ROOT}/docs/hooks-ref.md` for that event
(common fields plus the event-specific ones), with placeholder values under
`/tmp/hook-lab/`.

<Warning>
`WorktreeCreate` **replaces** Claude Code's default git worktree creation. Only ever test
it through this fixture-replay mode. Never wire a live `WorktreeCreate` hook into
`hooks/hooks.json` unless it reliably prints a valid worktree path, or real worktree
creation breaks for everyone with the plugin enabled.
</Warning>

## Steps

### 1. Parse `$ARGUMENTS`

- Empty or `--list`: list mode.
- Starts with `--logs `: log-tail mode, event name is the remainder.
- Otherwise: fixture-replay mode, event name is `$ARGUMENTS` trimmed.

### 2. List mode

Run `ls "${CLAUDE_SKILL_DIR}/fixtures"` to show every testable event. Resolve the log
root per "Locating the log root" above, then for each event check whether
`<root>/${CLAUDE_SESSION_ID}/<name>.jsonl` exists and how many lines it has
(`wc -l` if present) so the user can see which events have already fired live in this
session. Mention which root won (override, working directory, or plugin-data
fallback) so the user knows where captures are landing.

### 3. Fixture-replay mode

1. Confirm `${CLAUDE_SKILL_DIR}/fixtures/<EventName>.json` exists. If not, list the
   available names from step 2's `ls` output and stop — don't guess a fixture.
2. Read `${CLAUDE_PLUGIN_ROOT}/hooks/hooks.json` and find every hook handler registered
   under `.hooks.<EventName>`. For each `type: "command"` handler:
   - If it has an `if` field, check whether the fixture's `tool_input.command` (when
     present) plausibly matches the Bash pattern; note the check but run it anyway if
     unsure, since `if` filtering is best-effort in real usage too.
   - Reconstruct the exact shell invocation Claude Code would run (its `command` and
     `args`, with `${CLAUDE_PLUGIN_ROOT}` resolved to this plugin's root) and run it with
     the fixture piped to stdin, e.g.:
     `cat "${CLAUDE_SKILL_DIR}/fixtures/<EventName>.json" | python "${CLAUDE_PLUGIN_ROOT}/scripts/log-event.py"`
   - Capture stdout, stderr, and exit code separately for each handler.
3. Report, per handler:
   - The exact command run.
   - Exit code.
   - Raw stdout, and whether it would be parsed as JSON (starts with `{` after trimming
     leading whitespace, per the exit-code-0 rule in
     `${CLAUDE_PLUGIN_ROOT}/docs/hooks-ref.md#exit-code-0`) — if so, pretty-print it.
   - Raw stderr, if any.
   - What that output means for `<EventName>` specifically: look up the event's
     "decision control" section in `${CLAUDE_PLUGIN_ROOT}/docs/hooks-ref.md` and state
     plainly whether the tool call / prompt / stop / etc. would be allowed, blocked, or
     left to the normal flow. If that file is somehow missing from the bundle, fall
     back to the general rule: exit 0 = allow/normal flow (stdout parsed as JSON if it
     starts with `{`), exit 2 = block with stderr fed back to Claude, any other
     non-zero = non-blocking warning shown to the user.
4. Confirm the generic logger worked: resolve the log root per "Locating the log root"
   above and check that `<root>/${CLAUDE_SESSION_ID}/<EventName>.jsonl` grew
   by one line matching the fixture (`tail -n 1`).

### 4. Log-tail mode

Resolve the log root per "Locating the log root" above, then run
`tail -n 20 "<root>/${CLAUDE_SESSION_ID}/<EventName>.jsonl"`. If the user asks
for a different session, `ls "<root>"` first to find its `<session_id>`. If
no matching file exists, say plainly that this event hasn't fired live yet in this
surface (Chat or Cowork) and suggest an action that would trigger it, based on
`${CLAUDE_PLUGIN_ROOT}/docs/hooks-ref.md`'s description of when that event fires.
Pretty-print each captured JSON line.
