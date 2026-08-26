#!/usr/bin/env bash
#
# smoke_test.sh -- prove every documented command actually exists and parses.
#
# This exists because the previous generation of this pipeline documented three
# features its shipped code did not have: a TOC dot-leader alignment that was
# really padded dots, an "--items-from" interface on a script that accepted no
# arguments at all, and a review_sheet.py that was simply absent. All three
# would have been caught here in under a second.
#
# Run from the skill's scripts/ directory, or from a project's _pipeline dir:
#     bash scripts/smoke_test.sh
#
set -u
cd "$(dirname "$0")"

# The pipeline normally runs on the Linux side, where the interpreter is
# python3; a Windows host usually only has `python`. Resolve rather than assume,
# so a wrong interpreter name cannot masquerade as a missing dependency.
# Probe by RUNNING the candidate, not with `command -v`: on Windows, a
# Microsoft Store alias stub named python3 sits on PATH and fails when invoked,
# so an existence check picks an interpreter that cannot run anything.
PY=""
for cand in python3 python; do
    if "$cand" -c 'import sys; sys.exit(0)' >/dev/null 2>&1; then PY="$cand"; break; fi
done
if [ -z "$PY" ]; then
    echo "ERROR: no working python interpreter on PATH (tried python3, then python)." >&2
    exit 1
fi

fail=0
ok()   { printf '  [PASS] %s\n' "$1"; }
bad()  { printf '  [FAIL] %s\n' "$1"; fail=$((fail+1)); }

echo "smoke test: $(pwd)"
echo

# Every python entry point must answer --help without importing its heavy deps
# failing the run. A missing dep is reported separately from a broken interface.
for s in consolidate.py normalize_photos.py extract_sheet_clips.py \
         build_master.py review_sheet.py verify_report.py read_comments.py; do
    if [ ! -f "$s" ]; then bad "$s is missing"; continue; fi
    out=$("$PY" "$s" --help 2>&1)
    case "$?:$out" in
        0:*)                   ok "$s --help" ;;
        *:*ModuleNotFoundError*) bad "$s: missing dependency -> $(printf '%s' "$out" | tail -1)" ;;
        *)                     bad "$s --help exited nonzero -> $(printf '%s' "$out" | tail -1)" ;;
    esac
done

# The renderer has no --help; require it to parse and to refuse a missing build.
if [ ! -f gen_report.js ]; then
    bad "gen_report.js is missing"
elif node --check gen_report.js >/dev/null 2>&1; then
    ok "gen_report.js parses"
else
    bad "gen_report.js has a syntax error"
fi

[ -f run_pipeline.sh ] && bash -n run_pipeline.sh 2>/dev/null \
    && ok "run_pipeline.sh parses" || bad "run_pipeline.sh missing or unparseable"

# Deps the pipeline cannot run without.
"$PY" -c 'import fitz'    2>/dev/null && ok "pymupdf"  || bad "pymupdf not installed (pip install pymupdf)"
"$PY" -c 'import PIL'     2>/dev/null && ok "pillow"   || bad "pillow not installed (pip install pillow)"
"$PY" -c 'import openpyxl' 2>/dev/null && ok "openpyxl" || bad "openpyxl not installed (pip install openpyxl)"
node -e 'require("docx")'   2>/dev/null && ok "docx"     || bad "docx not installed (npm install docx@^9.7.1)"

echo
if [ "$fail" -gt 0 ]; then
    echo "$fail check(s) FAILED"
    exit 1
fi
echo "all checks passed"
