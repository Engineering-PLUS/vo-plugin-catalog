# PostToolUse hook -- Windows half (see verify-after-render.sh for the
# rationale). After gen_report.js runs, remind the model to verify the rendered
# document before calling the run finished.
#
# Stateless and deterministic: it keys off the render command itself rather than
# trying to track whether a document exists, which is why this is a PostToolUse
# on the render rather than a Stop hook.
#
# Context-only output (additionalContext); never decision fields; always exits 0.
# Disable with EPLUS_NO_PUNCH_VERIFY_NUDGE=1.

$ErrorActionPreference = 'SilentlyContinue'

try {
    $raw = [Console]::In.ReadToEnd()
    if ($env:EPLUS_NO_PUNCH_VERIFY_NUDGE) { exit 0 }

    $payload = $raw | ConvertFrom-Json
    $cmd = $payload.tool_input.command
    if (-not $cmd) { exit 0 }
    # Fire only on an actual render: node executing gen_report.js. Two thirds of
    # firings in the 2026-08-26 session were grep/sed/node --check commands that
    # merely CONTAINED the filename (CHANGE-LIST item 10).
    if ($cmd -notmatch '(?i)\bnode(\.exe)?("|\s)+[^|;&]*gen_report\.js') { exit 0 }
    if ($cmd -match '--check') { exit 0 }

    # run_pipeline.sh already verifies as its last step; no need to say it twice.
    if ($cmd -match 'run_pipeline\.sh') { exit 0 }

    $ctx = '[punch-report] The report was just rendered. Run ' +
           'scripts/verify_report.py <build>/<output>.docx <build>/master_report_items.json ' +
           'before calling this done. It reads the OOXML directly and checks the things that ' +
           'are invisible in a quick look: em and en dashes, the field-report voice rules on ' +
           'descriptions, PAGEREF/bookmark integrity, absence of baked-in page numbers, ' +
           'w:updateFields, one page break per item, embedded photo count, and that the ' +
           'letterhead is native rather than a pasted bitmap. If you rendered from a local ' +
           'working copy, sync the sources back to the project folder too, not just the .docx, ' +
           'so the document and the file that generates it cannot disagree.'

    $out = @{ hookSpecificOutput = @{
        hookEventName     = 'PostToolUse'
        additionalContext = $ctx
    } }
    [Console]::Out.Write((ConvertTo-Json -InputObject $out -Compress -Depth 8))
} catch {
    # A reminder is never worth failing a tool call over.
}

exit 0
