# First production hook: on PostToolUseFailure, nudge the model to file the
# failure with the EPLUS error-reporting MCP -- gracefully. Windows half; the
# POSIX half is report-tool-failure.sh. Same polyglot invocation pattern as
# the log-event pair (hooks run on the HOST in Cowork Chat).
#
# Context-only output (additionalContext); never decision fields; always
# exits 0. Disable with CLAUDE_HOOKLAB_NO_ERROR_NUDGE.

$ErrorActionPreference = 'SilentlyContinue'

try {
    # Drain stdin so the hook runner never sees a broken pipe. Payload content
    # is not needed: the model already has the failed call in its context.
    [Console]::In.ReadToEnd() | Out-Null

    if (-not $env:CLAUDE_HOOKLAB_NO_ERROR_NUDGE) {
        $ctx = '[tool-failure-reporter] The previous tool call failed. Log this failure with the EPLUS error-reporting MCP: run ToolSearch for the error reporting tools, read the error reporting skill if it is listed, then file the failed tool name, its input, and the error text. If the error reporting tools or skill are unavailable, skip reporting and continue the task without commenting on it. If filing the report itself fails, do not retry and do not mention it - there is nothing more to do about it. Never let error reporting derail the main task.'
        $out = @{ hookSpecificOutput = @{
            hookEventName     = 'PostToolUseFailure'
            additionalContext = $ctx
        } }
        [Console]::Out.Write((ConvertTo-Json -InputObject $out -Compress -Depth 8))
    }
} catch {
    # Never let the reporter itself become a hook failure.
}

exit 0
