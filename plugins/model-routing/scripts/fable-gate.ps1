# PreToolUse:Agent hook -- the teeth on the expensive tier, plus a spawn log.
#
# Every Agent spawn's subagent_type is logged (routing telemetry: PreToolUse
# on Agent is field-proven to dispatch, so the log is complete even if other
# channels misbehave). When the spawn targets fable-frontier -- the most
# expensive model, ~2x Opus, ~5x Sonnet -- the hook returns
# permissionDecision "ask", so a Fable spawn requires an explicit user click
# instead of happening on a reflex for "important".
#
# Escape hatch: EPLUS_ALLOW_FABLE=1 skips the gate (spawns still logged).
# PowerShell 5.1-compatible; never blocks anything else; exit 0.

$ErrorActionPreference = 'SilentlyContinue'

try {
    $raw = [Console]::In.ReadToEnd()

    $data = $null
    try { $data = $raw | ConvertFrom-Json -ErrorAction Stop } catch { exit 0 }
    if ($null -eq $data) { exit 0 }

    $sub = ''
    if ($data.PSObject.Properties['tool_input'] -and $data.tool_input -and
        $data.tool_input.PSObject.Properties['subagent_type']) {
        $sub = [string]$data.tool_input.subagent_type
    }
    $session = 'unknown-session'
    if ($data.PSObject.Properties['session_id'] -and $data.session_id) { $session = [string]$data.session_id }

    # Spawn telemetry, machine-local and per-session-exported.
    $logLine = "{0:yyyy-MM-ddTHH:mm:ssZ} session={1} event=PreToolUse:Agent subagent_type={2}" -f [DateTime]::UtcNow, $session, $sub
    if ($env:CLAUDE_PLUGIN_DATA) {
        try {
            if (-not (Test-Path -LiteralPath $env:CLAUDE_PLUGIN_DATA)) { New-Item -ItemType Directory -Path $env:CLAUDE_PLUGIN_DATA -Force | Out-Null }
            Add-Content -Path (Join-Path $env:CLAUDE_PLUGIN_DATA 'routing.log') -Value $logLine -Encoding utf8
        } catch { }
    }
    if ($data.PSObject.Properties['transcript_path'] -and $data.transcript_path) {
        try {
            $tdir = Split-Path -Path ([string]$data.transcript_path) -Parent
            if ($tdir) {
                $exportDir = Join-Path $tdir $session
                if (-not (Test-Path -LiteralPath $exportDir)) { New-Item -ItemType Directory -Path $exportDir -Force | Out-Null }
                Add-Content -Path (Join-Path $exportDir 'routing.log') -Value $logLine -Encoding utf8
            }
        } catch { }
    }

    if ($sub -ne 'model-routing:fable-frontier') { exit 0 }
    if ($env:EPLUS_ALLOW_FABLE) { exit 0 }

    $reason = 'fable-frontier runs Fable 5, the MOST expensive model (~2x Opus, ~5x ' +
              'Sonnet per token). It is reserved for problems Opus genuinely cannot ' +
              'handle -- "important" alone means an opus-deep review, not Fable. ' +
              'Approve only if this task truly needs the frontier tier. ' +
              '(Set EPLUS_ALLOW_FABLE=1 to disable this gate.)'

    $out = @{ hookSpecificOutput = @{
        hookEventName            = 'PreToolUse'
        permissionDecision       = 'ask'
        permissionDecisionReason = $reason
    } }
    [Console]::Out.Write((ConvertTo-Json -InputObject $out -Compress -Depth 8))
} catch {
    # Never let the gate itself break a tool call.
}

exit 0
