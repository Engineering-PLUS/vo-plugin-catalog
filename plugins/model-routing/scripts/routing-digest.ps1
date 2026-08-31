# SessionStart hook -- injects the routing policy digest so the rule is IN
# CONTEXT from turn one instead of waiting for the model to load the skill.
# Field evidence 2026-08-28: across two test sessions the skill was never
# loaded and zero workers were spawned while 45h of work ran on the Opus [1m]
# main thread. Guidance that isn't in context routes nothing.
#
# additionalContext on SessionStart is field-proven on the Cowork surface
# (eplus-simple-plugin's hook rendered this way). PowerShell 5.1-compatible;
# hooks run on the Windows host. Never blocks; exit 0.
# Disable with EPLUS_NO_ROUTING_HINTS=1.

$ErrorActionPreference = 'SilentlyContinue'

try {
    [Console]::In.ReadToEnd() | Out-Null
    if ($env:EPLUS_NO_ROUTING_HINTS) { exit 0 }

    $ctx = '[model-routing] Worker cost order, cheapest first: sonnet-standard ' +
           '(the default -- route the bulk of work here) < opus-deep (~2.5x -- hard ' +
           'reasoning, and REVIEW of any client-facing/technical output before it is ' +
           'final) < fable-frontier (~2x Opus, the most expensive -- only for problems ' +
           'Opus genuinely cannot handle). Route on difficulty AND stakes: easy but ' +
           'high-stakes output still gets an opus-deep review. If this main session ' +
           'runs on Opus or Fable, every token delegated down to sonnet-standard is ' +
           '2.5-5x cheaper. Load the model-routing skill for the full policy.'

    $out = @{ hookSpecificOutput = @{
        hookEventName     = 'SessionStart'
        additionalContext = $ctx
    } }
    [Console]::Out.Write((ConvertTo-Json -InputObject $out -Compress -Depth 8))
} catch {
    # Never let the digest become a hook failure.
}

exit 0
