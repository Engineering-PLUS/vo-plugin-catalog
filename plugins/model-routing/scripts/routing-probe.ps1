# Routing visibility probe -- the field-proven punch-subagent pattern applied
# to model routing. Two branches:
#
#   SubagentStart (scoped to this plugin's workers in hooks.json): log the
#   spawn to $CLAUDE_PLUGIN_DATA/routing.log AND to
#   <session project dir>/<session_id>/routing.log (the dir the session
#   exporter zips, so Log Lens shows the routing trail), and queue a
#   [model-routing] banner tracer.
#
#   MessageDisplay: drain the queue into a display-only banner prepended to
#   the next rendered reply via displayContent (proven to render in Cowork;
#   the model and the transcript never see it).
#
# PowerShell 5.1-compatible. Never blocks; always exit 0.

$ErrorActionPreference = 'SilentlyContinue'

try {
    $raw = [Console]::In.ReadToEnd()
    if ($raw.Length -gt 0 -and $raw[0] -eq [char]0xFEFF) { $raw = $raw.Substring(1) }

    $data = $null
    try { $data = $raw | ConvertFrom-Json -ErrorAction Stop } catch { }

    $evt = 'unknown'; $agent = ''; $session = 'unknown-session'
    if ($null -ne $data) {
        if ($data.PSObject.Properties['hook_event_name'] -and $data.hook_event_name) { $evt = [string]$data.hook_event_name }
        if ($data.PSObject.Properties['session_id'] -and $data.session_id)           { $session = [string]$data.session_id }
        if ($data.PSObject.Properties['agent_type'])  { $agent = [string]$data.agent_type }
    }

    $dataRoot = $env:CLAUDE_PLUGIN_DATA
    $sessionDir = $null
    if ($dataRoot) {
        $sessionDir = Join-Path $dataRoot $session
        try {
            if (-not (Test-Path -LiteralPath $sessionDir)) { New-Item -ItemType Directory -Path $sessionDir -Force | Out-Null }
        } catch { $sessionDir = $null }
    }
    $queuePath = $null
    if ($sessionDir) { $queuePath = Join-Path $sessionDir 'pending-banner.txt' }

    if ($evt -eq 'MessageDisplay') {
        $index = -1
        if ($null -ne $data -and $data.PSObject.Properties['index']) { $index = [int]$data.index }
        if ($index -eq 0 -and $queuePath) {
            $queued = @()
            try {
                if (Test-Path -LiteralPath $queuePath) {
                    $queued = @(Get-Content -LiteralPath $queuePath -ErrorAction Stop | Where-Object { $_.Trim() })
                    Remove-Item -LiteralPath $queuePath -Force -ErrorAction SilentlyContinue
                }
            } catch { $queued = @() }
            if ($queued.Count -gt 0) {
                $banner = '[[model-routing]] ' + ($queued -join ' ; ')
                if ($banner.Length -gt 1000) { $banner = $banner.Substring(0, 1000) + '...' }
                $delta = ''
                if ($null -ne $data -and $data.PSObject.Properties['delta'] -and ($data.delta -is [string])) { $delta = $data.delta }
                $out = @{ hookSpecificOutput = @{ hookEventName = 'MessageDisplay'; displayContent = $banner + "`n`n" + $delta } }
                [Console]::Out.Write((ConvertTo-Json -InputObject $out -Compress -Depth 8))
            }
        }
    } else {
        # Spawn branch (SubagentStart on a model-routing worker).
        $stamp = '{0:HH:mm:ss}Z' -f [DateTime]::UtcNow
        $short = $agent -replace '^model-routing:', ''
        $tracer = "$stamp spawned $short"

        $logLine = "{0:yyyy-MM-ddTHH:mm:ssZ} session={1} event={2} agent_type={3}" -f [DateTime]::UtcNow, $session, $evt, $agent
        if ($sessionDir) {
            try { Add-Content -Path (Join-Path $dataRoot 'routing.log') -Value $logLine -Encoding utf8 } catch { }
            if ($queuePath) {
                try { Add-Content -Path $queuePath -Value $tracer -Encoding utf8 } catch { }
            }
        }
        if ($null -ne $data -and $data.PSObject.Properties['transcript_path'] -and $data.transcript_path) {
            try {
                $tdir = Split-Path -Path ([string]$data.transcript_path) -Parent
                if ($tdir) {
                    $exportDir = Join-Path $tdir $session
                    if (-not (Test-Path -LiteralPath $exportDir)) { New-Item -ItemType Directory -Path $exportDir -Force | Out-Null }
                    Add-Content -Path (Join-Path $exportDir 'routing.log') -Value $logLine -Encoding utf8
                }
            } catch { }
        }
    }
} catch {
    # Never let the probe become a hook failure.
}

exit 0
