# UserPromptSubmit hook -- one-line stakes reminder, ONLY when the prompt
# looks like client-facing or drafting work (the easy-but-high-stakes quadrant
# the two-axis rule exists for). Silent on everything else so it costs nothing
# on routine turns.
#
# PowerShell 5.1-compatible; hooks run on the Windows host. Never blocks;
# exit 0. Disable with EPLUS_NO_ROUTING_HINTS=1.

$ErrorActionPreference = 'SilentlyContinue'

try {
    $raw = [Console]::In.ReadToEnd()
    if ($env:EPLUS_NO_ROUTING_HINTS) { exit 0 }

    $data = $null
    try { $data = $raw | ConvertFrom-Json -ErrorAction Stop } catch { exit 0 }
    if ($null -eq $data) { exit 0 }

    $prompt = ''
    if ($data.PSObject.Properties['prompt'] -and ($data.prompt -is [string])) { $prompt = $data.prompt }
    if (-not $prompt) { exit 0 }

    # Stakes vocabulary: client-facing artifacts and commitments. Deliberately
    # narrow -- a noisy hint gets ignored like the skill did.
    if ($prompt -notmatch '(?i)\b(client|email|e-mail|letter|memo|proposal|rfi|submittal|report|spec|contract|change order|deliverable)\b') { exit 0 }

    $ctx = '[model-routing] This looks like client-facing or professional output. ' +
           'Stakes rule: draft on sonnet-standard, but the FINAL version needs an ' +
           'opus-deep review before it goes out -- surface the review verdict to the user.'

    $out = @{ hookSpecificOutput = @{
        hookEventName     = 'UserPromptSubmit'
        additionalContext = $ctx
    } }
    [Console]::Out.Write((ConvertTo-Json -InputObject $out -Compress -Depth 8))
} catch {
    # Never let the hint become a hook failure.
}

exit 0
