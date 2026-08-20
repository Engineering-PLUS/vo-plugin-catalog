# eplus-guardrails

Prestaged production hooks for EPLUS Cowork deployment. Hooks graduate here
from `hook-testing-plugin` once field-tested; this plugin should stay small,
boring, and safe to enable fleet-wide.

All hooks use the polyglot invocation pattern proven in field testing: hooks
execute wherever Claude Code runs (the **Windows host** in Cowork Chat, the VM
in CLI surfaces), so each hook ships a PowerShell half and a POSIX half in one
shell-form command, each half no-opping on the other's platform.

## Hooks

### Delete gate (`PreToolUse`)

When a tool command looks like it deletes files or directories, returns
`permissionDecision: "ask"` with a reason naming the matched token and the
command — forcing the permission prompt even under lax default permissions.
It gates for confirmation; it never hard-denies.

- Patterns: `rm`, `rmdir`, `unlink`, `shred`, `rimraf`, `del`, `erase`, `rd`,
  `ri`, `Remove-Item`, `[IO.File]::Delete` / `[IO.Directory]::Delete`,
  `git clean`, `find ... -delete` (word-boundary matched, case-insensitive).
- **Fail-open:** unparseable payload, missing command field, missing python on
  a POSIX surface, or any internal error → no output, normal permission flow.
  A broken gate must never lock anyone out of their session.
- Disable per-machine: `EPLUS_GUARDRAILS_NO_DELETE_GATE=1`.
- Scripts: `scripts/delete-gate.ps1` (host), `scripts/delete-gate.sh` →
  `delete-gate.py` (POSIX).

### Tool-failure reporter (`PostToolUseFailure`)

When any tool call fails, injects `additionalContext` nudging the model to
file the failure with the EPLUS error-reporting MCP: run ToolSearch for the
error reporting tools, read the error reporting skill if listed, then log the
failed tool name, input, and error text. Deliberately fail-quiet at every
level: if the MCP or skill is unavailable the model skips reporting without
comment, and if filing the report itself fails it does not retry or mention
it. Never derails the main task.

- Disable per-machine: `CLAUDE_HOOKLAB_NO_ERROR_NUDGE=1`.
- Scripts: `scripts/report-tool-failure.ps1` (host),
  `scripts/report-tool-failure.sh` (POSIX, pure sh — no python needed).

## Known interaction (intentional, for testing)

`hook-testing-plugin` carries a PreToolUse **allow-canary** that returns
`permissionDecision: "allow"` for commands containing
`hooklab-precedence-canary`. Running a delete command containing that token
(e.g. `rm hooklab-precedence-canary.txt`) makes this plugin say **ask** while
hook-lab says **allow** — the multi-plugin precedence experiment. Expected
per docs: the more restrictive decision wins (deny > ask > allow).
