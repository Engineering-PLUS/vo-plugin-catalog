# Flight recorder + visible tracer -- Windows implementation.
# PowerShell 5.1-compatible (no ||, ?:, or pwsh-only syntax). Mirrors
# log-event.py exactly: appends the payload as one compact JSON line to
# <log_root>/<session_id>/<Event>.jsonl and emits {"systemMessage": "..."}
# on stdout. Display-only output; never decision fields; always exits 0.
#
# Runs on Windows hosts, where PowerShell is the only guaranteed interpreter
# (2026-08-19 field reports: hooks execute on the HOST in Cowork Chat, and
# neither sh nor python can be assumed on the app's PATH there).

$ErrorActionPreference = 'SilentlyContinue'

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
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    foreach ($root in $roots) {
        if (-not $root) { continue }
        try {
            $dir = Join-Path $root $session
            New-Item -ItemType Directory -Force -Path $dir -ErrorAction Stop | Out-Null
            $path = Join-Path $dir ($event + '.jsonl')
            [IO.File]::AppendAllText($path, $line, $utf8NoBom)
            $loggedTo = $path
            break
        } catch { continue }
    }

    # Visible trace for the user. systemMessage only -- never decision fields.
    if (-not $env:CLAUDE_HOOKLAB_QUIET) {
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
        if ($null -ne $data) {
            $excerpt = ConvertTo-Json -InputObject $data -Compress -Depth 64
        } else {
            $excerpt = $payload.Trim()
        }
        if ($excerpt.Length -gt 500) { $excerpt = $excerpt.Substring(0, 500) + '... [truncated]' }
        $msg = "[hook-lab] $event fired"
        if ($triggerBits.Count -gt 0) { $msg += ' (' + ($triggerBits -join ', ') + ')' }
        if ($loggedTo) { $msg += " | logged: $loggedTo" } else { $msg += ' | logged: NOWHERE (all log roots failed)' }
        $msg += " | payload: $excerpt"
        $out = ConvertTo-Json -InputObject @{ systemMessage = $msg } -Compress
        [Console]::Out.Write($out)
    }
} catch {
    # Never let a logging failure become a hook failure.
}

exit 0
