# SubagentStop echo -- PowerShell, runs on the Windows host (NO python).
# Surfaces the subagent's FINAL message to the user: reads last_assistant_message
# (provided directly in the SubagentStop input) and emits it as a systemMessage,
# which renders as a visible hook block.
#
# systemMessage only -- never additionalContext (injection-shaped, and on
# SubagentStop it would continue the turn). PowerShell 5.1-compatible. exit 0.
# Disable with EPLUS_NO_SUBAGENT_ECHO=1.

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

    $agent = 'subagent'
    if ($data.PSObject.Properties['agent_type'] -and $data.agent_type) { $agent = [string]$data.agent_type }

    $body = $msg.Trim()
    if ($body.Length -gt 6000) { $body = $body.Substring(0, 6000) + "`n... [final message truncated]" }

    $out = "[$agent - final message]`n`n$body"
    [Console]::Out.Write((ConvertTo-Json -InputObject @{ systemMessage = $out } -Compress))
} catch {
    # Never let the echo become a hook failure.
}

exit 0
