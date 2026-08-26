# Hook-event probe -- PowerShell, runs on the Windows host (NO python).
# Purpose: discover which hook events Cowork dispatches around the Agent tool,
# and make each dispatch VISIBLE IN THE CHAT UI without the model ever seeing
# it. Single visibility channel (deliberately -- one channel per test run):
#
#   displayContent banner via MessageDisplay, hook-lab's channel (b).
#   Probe events (SubagentStart / SubagentStop / PostToolUse:Agent) append a
#   tracer line to a per-session queue in $CLAUDE_PLUGIN_DATA; the
#   MessageDisplay branch drains the queue at index 0 and prepends a
#   [[punch-hooks]] banner to the rendered delta. Per docs/hooks-ref.md,
#   displayContent is display-only: the transcript and what Claude sees keep
#   the original text. NO systemMessage, NO additionalContext from this script.
#
# Every dispatch also appends to $CLAUDE_PLUGIN_DATA/hook-probe.log (pure
# forensics, invisible everywhere). PowerShell 5.1-compatible. Never blocks;
# always exit 0. Cowork/SDK note: MessageDisplay arrives once per message with
# index=0 and the full text in delta, so draining at index 0 covers both
# streaming and non-interactive modes.

$ErrorActionPreference = 'SilentlyContinue'

try {
    $raw = [Console]::In.ReadToEnd()
    if ($raw.Length -gt 0 -and $raw[0] -eq [char]0xFEFF) { $raw = $raw.Substring(1) }

    $data = $null
    try { $data = $raw | ConvertFrom-Json -ErrorAction Stop } catch { }

    $evt = 'unparsed-input'; $agent = ''; $tool = ''; $session = 'unknown-session'; $lastLen = -1
    if ($null -ne $data) {
        $evt = 'unknown'
        if ($data.PSObject.Properties['hook_event_name'] -and $data.hook_event_name) { $evt = [string]$data.hook_event_name }
        if ($data.PSObject.Properties['session_id'] -and $data.session_id)           { $session = [string]$data.session_id }
        if ($data.PSObject.Properties['agent_type'])  { $agent = [string]$data.agent_type }
        if ($data.PSObject.Properties['tool_name'])   { $tool = [string]$data.tool_name }
        if ($data.PSObject.Properties['last_assistant_message'] -and ($data.last_assistant_message -is [string])) {
            $lastLen = $data.last_assistant_message.Length
        }
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
        # Drain branch: banner the queued tracers onto the first delta.
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
                $banner = '[[punch-hooks]] ' + $queued.Count + ' event(s): ' + ($queued -join ' ; ')
                if ($banner.Length -gt 1000) { $banner = $banner.Substring(0, 1000) + '...' }
                $delta = ''
                if ($null -ne $data -and $data.PSObject.Properties['delta'] -and ($data.delta -is [string])) { $delta = $data.delta }
                $out = @{ hookSpecificOutput = @{ hookEventName = 'MessageDisplay'; displayContent = $banner + "`n`n" + $delta } }
                [Console]::Out.Write((ConvertTo-Json -InputObject $out -Compress -Depth 8))
            }
            # Empty queue: emit nothing, original delta renders untouched.
        }
    } else {
        # Probe branch: log the dispatch and queue a tracer line for the banner.
        $stamp = '{0:HH:mm:ss}Z' -f [DateTime]::UtcNow
        $tracer = "$stamp $evt"
        if ($agent) { $tracer += " agent=$agent" }
        if ($tool) { $tracer += " tool=$tool" }
        if ($lastLen -ge 0) { $tracer += " final_msg_chars=$lastLen" }

        if ($sessionDir) {
            $logLine = "{0:yyyy-MM-ddTHH:mm:ssZ} session={1} event={2} agent_type={3} tool_name={4} last_assistant_message_len={5}" -f [DateTime]::UtcNow, $session, $evt, $agent, $tool, $lastLen
            try { Add-Content -Path (Join-Path $dataRoot 'hook-probe.log') -Value $logLine -Encoding utf8 } catch { }
            if ($queuePath) {
                try { Add-Content -Path $queuePath -Value $tracer -Encoding utf8 } catch { }
            }
        }
        # No stdout: the banner is the one visibility channel under test.
    }
} catch {
    # Never let the probe become a hook failure.
}

exit 0
