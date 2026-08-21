# eplus-guardrails

Prestaged production hooks for EPLUS Cowork deployment. Hooks graduate here
from `hook-testing-plugin` once field-tested; this plugin should stay small,
boring, and safe to enable fleet-wide.

All hooks use the polyglot invocation pattern proven in field testing: hooks
execute wherever Claude Code runs (the **Windows host** in Cowork Chat, the VM
in CLI surfaces), so each hook ships a PowerShell half and a POSIX half in one
shell-form command, each half no-opping on the other's platform.

## Hooks

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

## Removed hooks

A **delete gate** (`PreToolUse` → `permissionDecision: "ask"` on delete-shaped
commands) was field-tested and removed 2026-08-20: Cowork already applies its
own internal guardrail to delete operations, so the hook produced a redundant
**second** permission prompt for the same action. The internal guardrail is
sufficient.
