# PreToolUse hook -- Windows half (see block-punch-pdf.sh for the rationale).
#
# Denies a LibreOffice PDF conversion of a punch report. The pipeline outputs
# .docx only: the reviewer generates the PDF from Word, which is the only
# renderer that recalculates the TOC PAGEREF fields. A LibreOffice conversion
# produces a PDF whose page numbers are blank or wrong, and that mistake has
# already shipped once.
#
# DELIBERATELY NARROW. It fires only when the command both converts to PDF and
# names a punch report path, so the docx skill's own soffice validation and every
# unrelated conversion are untouched.
#
# Always exits 0; the decision travels in the JSON, not the exit code.
# Disable with EPLUS_NO_PUNCH_PDF_GUARD=1.

$ErrorActionPreference = 'SilentlyContinue'

try {
    $raw = [Console]::In.ReadToEnd()
    if ($env:EPLUS_NO_PUNCH_PDF_GUARD) { exit 0 }

    $payload = $raw | ConvertFrom-Json
    $cmd = $payload.tool_input.command
    if (-not $cmd) { exit 0 }

    # scripts/render_preview.py rasterises for INSPECTION: it converts in a
    # scratch dir, keeps only PNGs, and deletes the PDF. The deliverable ban is
    # about PDFs that could reach a reviewer; this one never can.
    if ($cmd -match 'render_preview\.py') { exit 0 }

    $isConvert = ($cmd -match 'soffice|libreoffice') -and ($cmd -match 'convert-to\s+pdf|--convert-to\s+pdf')
    if (-not $isConvert) { exit 0 }

    # Only guard punch report material.
    if ($cmd -notmatch '_pipeline|punch|Punch') { exit 0 }

    $reason = 'The punch report pipeline outputs .docx only, by design. Word recalculates the ' +
              'TOC PAGEREF fields on open and on PDF export; LibreOffice does not, and it paginates ' +
              'differently, so a PDF made this way carries blank or wrong page numbers. That exact ' +
              'bug already shipped once. The reviewer generates the PDF from Word when their markup ' +
              'is done. If you need to verify the document, use scripts/verify_report.py, which ' +
              'reads the OOXML directly and needs no LibreOffice.'

    $out = @{ hookSpecificOutput = @{
        hookEventName            = 'PreToolUse'
        permissionDecision       = 'deny'
        permissionDecisionReason = $reason
    } }
    [Console]::Out.Write((ConvertTo-Json -InputObject $out -Compress -Depth 8))
} catch {
    # Never let the guard itself block a tool call.
}

exit 0
