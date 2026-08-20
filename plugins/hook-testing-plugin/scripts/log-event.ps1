# Flight recorder + visible tracer -- Windows implementation.
# PowerShell 5.1-compatible (no ||, ?:, or pwsh-only syntax). Mirrors
# log-event.py exactly. Appends the payload as one compact JSON line to
# <log_root>/<session_id>/<Event>.jsonl, then emits ONE JSON object on stdout.
#
# COWORK VISIBILITY (2026-08-19 field reports, beautiful-vigilant-bohr):
# Cowork accepts hook systemMessage and transcribes it as a
# `hook_system_message` attachment but never renders it in the chat UI.
# Two channels compensate (see log-event.py header for the full rationale):
#   a. additionalContext relay on RELAY_EVENTS (drains pending-relay.txt);
#      the assistant echoes the tracer lines in its visible reply.
#      Disable with CLAUDE_HOOKLAB_NO_RELAY.
#   b. displayContent banner on MessageDisplay index 0 (drains
#      pending-banner.txt). Disable with CLAUDE_HOOKLAB_NO_BANNER.
# Stop/SubagentStop are NOT relay events: additionalContext there continues
# the conversation -- unacceptable for a passive tracer.
#
# Display-only and context-only output; never decision fields; always exits 0.

$ErrorActionPreference = 'SilentlyContinue'

$RelayEvents = @('SessionStart', 'Setup', 'SubagentStart',
                 'UserPromptSubmit', 'UserPromptExpansion',
                 'PreToolUse', 'PostToolUse', 'PostToolUseFailure')
$QueueSkip = @('MessageDisplay')
$RelayQueue = 'pending-relay.txt'
$BannerQueue = 'pending-banner.txt'
$MaxRelayChars = 6000

try {
    $raw = [Console]::In.ReadToEnd()
    $payload = $raw
    if ($payload.Length -gt 0 -and $payload[0] -eq [char]0xFEFF) {
        $payload = $payload.Substring(1)
    }

    $data = $null
    $line = $null
    try {
        $data = $payload | ConvertFrom-Json -ErrorAction Stop
        $line = (ConvertTo-Json -InputObject $data -Compress -Depth 64) + "`n"
    } catch {
        $data = $null
        if ($payload.EndsWith("`n")) { $line = $payload } else { $line = $payload + "`n" }
    }

    $event = 'unknown'
    $session = 'unknown-session'
    if ($null -ne $data) {
        if ($data.PSObject.Properties['hook_event_name'] -and $data.hook_event_name) { $event = [string]$data.hook_event_name }
        if ($data.PSObject.Properties['session_id'] -and $data.session_id) { $session = [string]$data.session_id }
    }

    # Log root resolution -- same order as log-event.py:
    # override -> CLAUDE_PROJECT_DIR -> ($HOME/mnt autodetect; VM-only layout,
    # effectively never present on a Windows host) -> cwd -> plugin data.
    $roots = @()
    if ($env:CLAUDE_HOOKLAB_LOG_ROOT) { $roots += $env:CLAUDE_HOOKLAB_LOG_ROOT }
    if ($env:CLAUDE_PROJECT_DIR) {
        $roots += (Join-Path $env:CLAUDE_PROJECT_DIR '.hook-lab\events')
    } elseif ($env:HOME -and (Test-Path (Join-Path $env:HOME 'mnt'))) {
        $internal = @('outputs', 'uploads', '.claude', '.local-plugins', '.auto-memory', '.hook-lab')
        $mounts = Get-ChildItem -LiteralPath (Join-Path $env:HOME 'mnt') -Directory -Force |
            Where-Object { $internal -notcontains $_.Name } | Sort-Object Name
        if ($mounts) { $roots += (Join-Path $mounts[0].FullName '.hook-lab\events') }
    }
    $roots += (Join-Path (Get-Location).Path '.hook-lab\events')
    if ($env:CLAUDE_PLUGIN_DATA) { $roots += (Join-Path $env:CLAUDE_PLUGIN_DATA 'events') } else { $roots += (Join-Path '.' 'events') }

    $loggedTo = ''
    $sessionDir = ''
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    foreach ($root in $roots) {
        if (-not $root) { continue }
        try {
            $dir = Join-Path $root $session
            New-Item -ItemType Directory -Force -Path $dir -ErrorAction Stop | Out-Null
            $path = Join-Path $dir ($event + '.jsonl')
            [IO.File]::AppendAllText($path, $line, $utf8NoBom)
            $loggedTo = $path
            $sessionDir = $dir
            break
        } catch { continue }
    }

    # Compact one-line tracer used by systemMessage, relay, and banner.
    $triggerBits = @()
    if ($null -ne $data) {
        foreach ($key in @('tool_name', 'prompt', 'file_path', 'source', 'reason', 'message', 'trigger')) {
            $prop = $data.PSObject.Properties[$key]
            if ($prop -and ($prop.Value -is [string]) -and $prop.Value) {
                $value = $prop.Value
                if ($value.Length -gt 80) { $value = $value.Substring(0, 80) + '...' }
                $triggerBits += "$key=$value"
            }
        }
    }
    $tracer = "[hook-lab] $event fired"
    if ($triggerBits.Count -gt 0) { $tracer += ' (' + ($triggerBits -join ', ') + ')' }

    # Queue the tracer for both visibility channels.
    if ($sessionDir -and ($QueueSkip -notcontains $event)) {
        foreach ($qf in @($RelayQueue, $BannerQueue)) {
            try {
                [IO.File]::AppendAllText((Join-Path $sessionDir $qf), $tracer + "`n", $utf8NoBom)
            } catch { }
        }
    }

    $out = @{}

    if ($event -eq 'MessageDisplay' -and (-not $env:CLAUDE_HOOKLAB_NO_BANNER)) {
        # Channel b: displayContent banner on the first delta only.
        $index = -1
        if ($null -ne $data -and $data.PSObject.Properties['index']) { $index = [int]$data.index }
        if ($index -eq 0) {
            $queued = @()
            if ($sessionDir) {
                $qpath = Join-Path $sessionDir $BannerQueue
                try {
                    if (Test-Path -LiteralPath $qpath) {
                        $queued = @(Get-Content -LiteralPath $qpath -ErrorAction Stop | Where-Object { $_.Trim() })
                        Remove-Item -LiteralPath $qpath -Force -ErrorAction SilentlyContinue
                    }
                } catch { $queued = @() }
            }
            if ($queued.Count -gt 0) {
                $items = @()
                foreach ($q in $queued) { $items += $q.Replace('[hook-lab] ', '') }
                $banner = '[[hook-lab]] ' + $queued.Count + ' event(s): ' + ($items -join '; ')
            } else {
                $banner = '[[hook-lab]] displayContent render test (no queued events)'
            }
            if ($banner.Length -gt 1000) { $banner = $banner.Substring(0, 1000) + '...' }
            $delta = ''
            if ($null -ne $data -and $data.PSObject.Properties['delta'] -and ($data.delta -is [string])) { $delta = $data.delta }
            $out['hookSpecificOutput'] = @{
                hookEventName  = 'MessageDisplay'
                displayContent = $banner + "`n`n" + $delta
            }
        }
        # Non-first deltas: no output; original text displays unchanged.
    } elseif (($RelayEvents -contains $event) -and (-not $env:CLAUDE_HOOKLAB_NO_RELAY)) {
        # Channel a: additionalContext relay.
        $queued = @($tracer)
        if ($sessionDir) {
            $qpath = Join-Path $sessionDir $RelayQueue
            try {
                if (Test-Path -LiteralPath $qpath) {
                    $queued = @(Get-Content -LiteralPath $qpath -ErrorAction Stop | Where-Object { $_.Trim() })
                    Remove-Item -LiteralPath $qpath -Force -ErrorAction SilentlyContinue
                }
            } catch { $queued = @($tracer) }
        }
        $block = $queued -join "`n"
        if ($block.Length -gt $MaxRelayChars) {
            $block = "[...older tracer lines truncated...]`n" + $block.Substring($block.Length - $MaxRelayChars)
        }
        $ctx = '[hook-lab visible tracer] The Cowork UI does not render hook ' +
               'systemMessage output, so you are the display channel. At the very ' +
               'top of your next visible reply, render the tracer lines below ' +
               'verbatim in a fenced code block labeled hook-lab, then continue ' +
               "with your normal answer. Do not omit or summarize them.`n" + $block
        $out['hookSpecificOutput'] = @{
            hookEventName     = $event
            additionalContext = $ctx
        }

        # SessionStart-only extras (mirrors log-event.py):
        # channel c -- initialUserMessage creates a visible USER turn on
        # -p / SDK surfaces (how Cowork hosts Claude Code).
        # channel d -- sessionTitle renders in the UI with zero model
        # involvement; never overwrites a title the user already set.
        if ($event -eq 'SessionStart') {
            if (-not $env:CLAUDE_HOOKLAB_NO_INITMSG) {
                $out['hookSpecificOutput']['initialUserMessage'] =
                    '[hook-lab] This synthetic first message was injected by the ' +
                    'hook-testing-plugin SessionStart hook via initialUserMessage ' +
                    'to test turn-creation visibility on this surface. Tracer: ' +
                    $tracer + '. Acknowledge this tracer in one short line, then ' +
                    "wait for the user's real prompt."
            }
            if (-not $env:CLAUDE_HOOKLAB_NO_TITLE) {
                $existingTitle = $null
                if ($null -ne $data -and $data.PSObject.Properties['session_title']) { $existingTitle = $data.session_title }
                if (-not $existingTitle) {
                    $source = '?'
                    if ($null -ne $data -and $data.PSObject.Properties['source'] -and $data.source) { $source = [string]$data.source }
                    $sess8 = $session
                    if ($sess8.Length -gt 8) { $sess8 = $sess8.Substring(0, 8) }
                    $out['hookSpecificOutput']['sessionTitle'] = "hook-lab $source $sess8"
                }
            }
        }
    }

    # systemMessage retained for terminal surfaces. Discarded-by-design on
    # some events; harmless. Skipped on MessageDisplay (always discarded).
    if ((-not $env:CLAUDE_HOOKLAB_QUIET) -and ($event -ne 'MessageDisplay')) {
        if ($null -ne $data) {
            $excerpt = ConvertTo-Json -InputObject $data -Compress -Depth 64
        } else {
            $excerpt = $payload.Trim()
        }
        if ($excerpt.Length -gt 500) { $excerpt = $excerpt.Substring(0, 500) + '... [truncated]' }
        $msg = $tracer
        if ($loggedTo) { $msg += " | logged: $loggedTo" } else { $msg += ' | logged: NOWHERE (all log roots failed)' }
        $msg += " | payload: $excerpt"
        $out['systemMessage'] = $msg
    }

    if ($out.Count -gt 0) {
        $json = ConvertTo-Json -InputObject $out -Compress -Depth 8
        [Console]::Out.Write($json)
    }
} catch {
    # Never let a logging failure become a hook failure.
}

exit 0
