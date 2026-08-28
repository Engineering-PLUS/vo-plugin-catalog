#!/bin/sh
# PreToolUse hook (POSIX half; block-punch-pdf.ps1 is the Windows half).
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

# Windows guard: block-punch-pdf.ps1 handles Windows hosts. Exit before reading
# stdin so the .ps1 (which runs first in the polyglot command) gets the full
# payload and this half never double-fires.
[ "${OS:-}" = "Windows_NT" ] && exit 0
case "$(uname -s 2>/dev/null)" in
  MINGW*|MSYS*|CYGWIN*) exit 0 ;;
esac

payload=$(cat)

[ -n "${EPLUS_NO_PUNCH_PDF_GUARD:-}" ] && exit 0

# scripts/render_preview.py rasterises for INSPECTION only: scratch-dir
# conversion, PNGs kept, PDF deleted. The deliverable ban does not apply.
case "$payload" in
  *render_preview.py*) exit 0 ;;
esac

# Both conditions must hold: a PDF conversion, and punch report material.
case "$payload" in
  *soffice*|*libreoffice*) ;;
  *) exit 0 ;;
esac
case "$payload" in
  *convert-to*pdf*) ;;
  *) exit 0 ;;
esac
case "$payload" in
  *_pipeline*|*punch*|*Punch*) ;;
  *) exit 0 ;;
esac

printf '%s' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"The punch report pipeline outputs .docx only, by design. Word recalculates the TOC PAGEREF fields on open and on PDF export; LibreOffice does not, and it paginates differently, so a PDF made this way carries blank or wrong page numbers. That exact bug already shipped once. The reviewer generates the PDF from Word when their markup is done. If you need to verify the document, use scripts/verify_report.py, which reads the OOXML directly and needs no LibreOffice."}}'

exit 0
