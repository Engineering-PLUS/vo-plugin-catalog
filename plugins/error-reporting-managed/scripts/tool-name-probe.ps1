# Tool-name probe -- PowerShell, runs on the Windows host (NO python).
# On any PreToolUse whose tool_name contains "report_issue", emits ONLY a
# systemMessage (renders as a visible hook block) naming the exact tool, so the
# managed form (mcp__<server>__report_issue) can be compared against the bundled
# form (mcp__plugin_<plugin>_<server>__report_issue). Silent otherwise.
#
# systemMessage only -- never additionalContext (injection-shaped on a tool turn,
# classifier-blockable). PowerShell 5.1-compatible. Always exits 0.
# Disable with EPLUS_NO_TOOLNAME_PROBE=1.

$ErrorActionPreference = 'SilentlyContinue'

try {
    $raw = [Console]::In.ReadToEnd()
    if ($env:EPLUS_NO_TOOLNAME_PROBE) { exit 0 }
    if ($raw.Length -gt 0 -and $raw[0] -eq [char]0xFEFF) { $raw = $raw.Substring(1) }

    $data = $null
    try { $data = $raw | ConvertFrom-Json -ErrorAction Stop } catch { exit 0 }
    if ($null -eq $data) { exit 0 }

    $tool = $null
    if ($data.PSObject.Properties['tool_name'] -and ($data.tool_name -is [string])) { $tool = $data.tool_name }
    if (-not $tool -or ($tool -notmatch 'report_issue')) { exit 0 }

    if ($tool -like 'mcp__plugin_*') { $shape = 'plugin-bundled MCP' } else { $shape = 'managed MCP server' }
    $msg = "[tool-name-probe] report_issue tool name = $tool  ($shape)"
    [Console]::Out.Write((ConvertTo-Json -InputObject @{ systemMessage = $msg } -Compress))
} catch {
    # Never let the probe become a hook failure.
}

exit 0
