# Precedence-test canary -- Windows half. If the raw PreToolUse payload
# contains the token "hooklab-precedence-canary", return
# permissionDecision "allow". eplus-guardrails' delete-gate says "ask" for
# delete commands, so `rm hooklab-precedence-canary.txt` makes two plugins
# disagree on the same call -- the multi-plugin aggregation experiment.
# Docs predict the more restrictive decision wins (deny > ask > allow).
# Inert on every command that lacks the token. Always exits 0.

$ErrorActionPreference = 'SilentlyContinue'

try {
    $raw = [Console]::In.ReadToEnd()
    if ($raw -match 'hooklab-precedence-canary') {
        $out = @{ hookSpecificOutput = @{
            hookEventName            = 'PreToolUse'
            permissionDecision       = 'allow'
            permissionDecisionReason = '[hook-lab allow-canary] allow issued for hooklab-precedence-canary -- multi-plugin precedence test (expect the more restrictive decision to win)'
        } }
        [Console]::Out.Write((ConvertTo-Json -InputObject $out -Compress -Depth 8))
    }
} catch { }

exit 0
