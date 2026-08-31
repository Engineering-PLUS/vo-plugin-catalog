# SubagentStop hook, scoped to opus-deep -- closes the review loop. The
# stakes rule says high-stakes output gets an opus-deep review; this makes
# the review VERDICT visible instead of buried in a subagent result the main
# model may paraphrase away: a 220-char excerpt goes to the [model-routing]
# banner (drained by routing-probe.ps1's MessageDisplay branch) and the full
# verdict is appended to <session project dir>/<session_id>/review-verdicts.log,
# which rides along in the session export for Log Lens.
#
# PowerShell 5.1-compatible; never blocks; exit 0.
# Disable with EPLUS_NO_REVIEW_ECHO=1.

$ErrorActionPreference = 'SilentlyContinue'

try {
    $raw = [Console]::In.ReadToEnd()
    if ($env:EPLUS_NO_REVIEW_ECHO) { exit 0 }
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

    $session = 'unknown-session'
    if ($data.PSObject.Properties['session_id'] -and $data.session_id) { $session = [string]$data.session_id }

    $excerpt = $body -replace '\s+', ' '
    if ($excerpt.Length -gt 220) { $excerpt = $excerpt.Substring(0, 220) + '...' }
    if ($env:CLAUDE_PLUGIN_DATA) {
        try {
            $sessionDir = Join-Path $env:CLAUDE_PLUGIN_DATA $session
            if (-not (Test-Path -LiteralPath $sessionDir)) { New-Item -ItemType Directory -Path $sessionDir -Force | Out-Null }
            Add-Content -Path (Join-Path $sessionDir 'pending-banner.txt') -Value "[opus-deep review] $excerpt" -Encoding utf8
        } catch { }
    }

    if ($data.PSObject.Properties['transcript_path'] -and $data.transcript_path) {
        try {
            $tdir = Split-Path -Path ([string]$data.transcript_path) -Parent
            if ($tdir) {
                $exportDir = Join-Path $tdir $session
                if (-not (Test-Path -LiteralPath $exportDir)) { New-Item -ItemType Directory -Path $exportDir -Force | Out-Null }
                $stamp = '{0:yyyy-MM-ddTHH:mm:ssZ}' -f [DateTime]::UtcNow
                $entry = "==== $stamp opus-deep ($($body.Length) chars) ====`r`n$body`r`n"
                Add-Content -Path (Join-Path $exportDir 'review-verdicts.log') -Value $entry -Encoding utf8
            }
        } catch { }
    }
} catch {
    # Never let the echo become a hook failure.
}

exit 0
