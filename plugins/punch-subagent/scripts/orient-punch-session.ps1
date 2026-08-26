# SessionStart hook -- Windows half (see orient-punch-session.sh for the
# rationale). When the session opens on a folder that already holds a punch
# report pipeline, point the model at that project's CLAUDE.md before it starts
# guessing, and restate the standing rules that have been re-derived before.
#
# Silent unless a pipeline is actually present, so it costs nothing in unrelated
# sessions.
#
# Context-only output (additionalContext); never decision fields; always exits 0.
# Disable with EPLUS_NO_PUNCH_ORIENT=1.

$ErrorActionPreference = 'SilentlyContinue'

try {
    $raw = [Console]::In.ReadToEnd()
    if ($env:EPLUS_NO_PUNCH_ORIENT) { exit 0 }

    $payload = $raw | ConvertFrom-Json
    $cwd = $payload.cwd
    if (-not $cwd) { $cwd = (Get-Location).Path }
    if (-not (Test-Path -LiteralPath $cwd)) { exit 0 }

    $manual = Get-ChildItem -LiteralPath $cwd -Filter 'CLAUDE.md' -Recurse -Depth 2 -File |
              Where-Object { $_.DirectoryName -match '_pipeline' } |
              Select-Object -First 1
    if (-not $manual) { exit 0 }

    $rel = $manual.FullName.Substring($cwd.Length).TrimStart('\', '/')

    $ctx = "[punch-report] This folder holds a punch report pipeline. Read $rel before " +
           'touching any script; it carries this project''s scope decision and the rules the ' +
           'renderer bakes in. Standing rules that have each been re-derived at least once: the ' +
           'pipeline outputs .docx ONLY (the reviewer makes the PDF from Word, which recalculates ' +
           'the TOC PAGEREF fields); the letterhead is built natively and never pasted in as a ' +
           'bitmap; item descriptions are in field-report voice, not photo narration and never ' +
           'third-person about the field engineer; scope lives only in SCOPE / consolidate.py ' +
           '--only. The project folder is on a network share and is over 45x slower than local ' +
           'disk for many-small-file steps, so copy out, work locally, and copy back, sources as ' +
           'well as outputs. Run scripts/smoke_test.sh before trusting the tooling.'

    $out = @{ hookSpecificOutput = @{
        hookEventName     = 'SessionStart'
        additionalContext = $ctx
    } }
    [Console]::Out.Write((ConvertTo-Json -InputObject $out -Compress -Depth 8))
} catch {
    # Orientation is a convenience; never let it fail a session start.
}

exit 0
