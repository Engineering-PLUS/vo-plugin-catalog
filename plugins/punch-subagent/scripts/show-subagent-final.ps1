# SubagentStop echo -- PowerShell, runs on the Windows host (NO python).
# Surfaces the subagent's FINAL message via the PROVEN visibility channel:
# queues a banner line that hook-probe.ps1's MessageDisplay branch renders as
# a [[punch-hooks]] prefix on the next reply (display-only -- the model and
# the transcript never see it). The 2026-08-26 field run proved the banner
# renders in Cowork while systemMessage leaves no trace anywhere, so
# systemMessage is gone. The FULL final message is appended to
# <session project dir>/<session_id>/subagent-final-messages.log, which the
# session exporter zips, so Log Lens shows the complete text per run.
#
# Never additionalContext or decision fields (injection-shaped; on
# SubagentStop it would continue the turn). PowerShell 5.1-compatible.
# Never blocks; exit 0. Disable with EPLUS_NO_SUBAGENT_ECHO=1.

$ErrorActionPreference = 'SilentlyContinue'

try {
    $raw = [Console]::In.ReadToEnd()
    if ($env:EPLUS_NO_SUBAGENT_ECHO) { exit 0 }
    if ($raw.Length -gt 0 -and $raw[0] -eq [char]0xFEFF) { $raw = $raw.Substring(1) }

    $data = $null
    try { $data = $raw | ConvertFrom-Json -ErrorAction Stop } catch { exit 0 }
    if ($null -eq $data) { exit 0 }

    $msg = $null
    if ($data.PSObject.Properties['last_assistant_message'] -and ($data.last_assistant_message -is [string])) {
        $msg = $data.last_assistant_message
    }
    if (-not $msg -or -not $msg.Trim()) { exit 0 }
    $body = $msg.Trim()

    $agent = 'subagent'
    if ($data.PSObject.Properties['agent_type'] -and $data.agent_type) { $agent = [string]$data.agent_type }
    $session = 'unknown-session'
    if ($data.PSObject.Properties['session_id'] -and $data.session_id) { $session = [string]$data.session_id }

    # Banner excerpt -> same per-session queue hook-probe.ps1 drains on
    # MessageDisplay. Keep it short; the full text goes to the session log.
    $excerpt = $body -replace '\s+', ' '
    if ($excerpt.Length -gt 220) { $excerpt = $excerpt.Substring(0, 220) + '...' }
    if ($env:CLAUDE_PLUGIN_DATA) {
        try {
            $sessionDir = Join-Path $env:CLAUDE_PLUGIN_DATA $session
            if (-not (Test-Path -LiteralPath $sessionDir)) { New-Item -ItemType Directory -Path $sessionDir -Force | Out-Null }
            Add-Content -Path (Join-Path $sessionDir 'pending-banner.txt') -Value "[$agent final] $excerpt" -Encoding utf8
        } catch { }
    }

    # Full final message -> session project dir (rides along in the export).
    if ($data.PSObject.Properties['transcript_path'] -and $data.transcript_path) {
        try {
            $tdir = Split-Path -Path ([string]$data.transcript_path) -Parent
            if ($tdir) {
                $exportDir = Join-Path $tdir $session
                if (-not (Test-Path -LiteralPath $exportDir)) { New-Item -ItemType Directory -Path $exportDir -Force | Out-Null }
                $stamp = '{0:yyyy-MM-ddTHH:mm:ssZ}' -f [DateTime]::UtcNow
                $entry = "==== $stamp $agent ($($body.Length) chars) ====`r`n$body`r`n"
                Add-Content -Path (Join-Path $exportDir 'subagent-final-messages.log') -Value $entry -Encoding utf8
            }
        } catch { }
    }
} catch {
    # Never let the echo become a hook failure.
}

exit 0
