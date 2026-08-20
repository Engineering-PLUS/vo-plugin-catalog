# Delete gate -- Windows half (see delete-gate.py for the full rationale).
# PowerShell 5.1-compatible. When a tool call's command looks like it deletes
# files, return permissionDecision "ask" so the permission prompt appears.
# Fail-open: any parse failure or error -> no output, exit 0, normal flow.
# Disable with EPLUS_GUARDRAILS_NO_DELETE_GATE=1.

$ErrorActionPreference = 'SilentlyContinue'

try {
    $raw = [Console]::In.ReadToEnd()
    if ($env:EPLUS_GUARDRAILS_NO_DELETE_GATE) { exit 0 }
    if ($raw.Length -gt 0 -and $raw[0] -eq [char]0xFEFF) { $raw = $raw.Substring(1) }

    $data = $null
    try { $data = $raw | ConvertFrom-Json -ErrorAction Stop } catch { exit 0 }
    if ($null -eq $data) { exit 0 }

    $command = $null
    if ($data.PSObject.Properties['tool_input'] -and $null -ne $data.tool_input) {
        $ti = $data.tool_input
        if ($ti.PSObject.Properties['command'] -and ($ti.command -is [string])) { $command = $ti.command }
    }
    if (-not $command) { exit 0 }

    # Mirrors DELETE_RE in delete-gate.py. PowerShell -match is
    # case-insensitive by default.
    $deleteRe = '(?:(?:^|[\s;|&(])(?:rm|rmdir|unlink|shred|rimraf|del|erase|rd|ri)(?:$|[\s;|&)]))' +
                '|remove-item' +
                '|\[io\.(?:file|directory)\]::delete' +
                '|git\s+clean' +
                '|-delete(?:$|[\s;|&)])'
    if ($command -notmatch $deleteRe) { exit 0 }
    $matched = $Matches[0].Trim()

    $excerpt = $command
    if ($excerpt.Length -gt 160) { $excerpt = $excerpt.Substring(0, 160) + '...' }
    $reason = '[delete-gate] This command appears to delete files or directories ' +
              "(matched: $matched). Command: $excerpt -- confirm before it runs."

    $out = @{ hookSpecificOutput = @{
        hookEventName            = 'PreToolUse'
        permissionDecision       = 'ask'
        permissionDecisionReason = $reason
    } }
    [Console]::Out.Write((ConvertTo-Json -InputObject $out -Compress -Depth 8))
} catch {
    # Fail-open: never lock the user out because the gate itself broke.
}

exit 0
