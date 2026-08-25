# Tool-name probe -- Windows half (see tool-name-probe.py for rationale).
# PowerShell 5.1-compatible. On any PreToolUse whose tool_name contains
# "report_issue", emits additionalContext (renders in Cowork) naming the exact
# tool, plus a systemMessage backup. Silent otherwise. Always exits 0.
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

    $ctx = '[tool-name-probe] A report_issue tool was just invoked. Its EXACT tool ' +
           "name is: ``$tool``. Quote this exact name verbatim at the top of your " +
           'reply so the managed-vs-bundled MCP naming difference is visible. ' +
           '(Bundled shows mcp__plugin_<plugin>_<server>__report_issue; a bootstrap ' +
           'managed server shows mcp__<server>__report_issue.)'
    $out = @{
        hookSpecificOutput = @{
            hookEventName     = 'PreToolUse'
            additionalContext = $ctx
        }
        systemMessage = "[tool-name-probe] report_issue tool name = $tool"
    }
    [Console]::Out.Write((ConvertTo-Json -InputObject $out -Compress -Depth 8))
} catch {
    # Never let the probe become a hook failure.
}

exit 0
