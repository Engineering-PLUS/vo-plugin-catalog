#!/usr/bin/env bash
#
# run_pipeline.sh -- build a punch report end to end, from a PlanGrid pull to a
# rendered .docx. Run from the project's _pipeline directory:
#
#     bash scripts/run_pipeline.sh
#
# Inputs are auto-detected from the parent folder and can be overridden:
#
#     PULL=../Some_Pull_dir TASK_REPORT="../Task Report.pdf" SCOPE=11-30 \
#         bash scripts/run_pipeline.sh
#
# SCOPE is the ONLY place report scope lives. Unset means every item in the pull.
#
# Produces a .docx ONLY. No PDF is generated here, by design:
#   - The reviewer generates the PDF from Word once markup is finished.
#   - Word recalculates the TOC page number fields on open and on PDF export.
#     LibreOffice does not, and it paginates differently from Word anyway, so a
#     PDF produced here would carry page numbers that do not match the document
#     the reviewer is actually editing. That was the original bug.
# Do not add a soffice conversion step back into this script.
#
set -euo pipefail

BUILD="${BUILD:-build}"

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

# --- input discovery -------------------------------------------------------
# A PlanGrid pull is a directory holding tasks.json. A Task Report is a PDF
# exported separately from PlanGrid; it is NOT part of an API pull, and it is
# the only source of the per-item annotated sheet clips.
if [ -z "${PULL:-}" ]; then
    PULL=$(find .. -maxdepth 2 -name tasks.json -not -path '*/delta_*' 2>/dev/null \
           | head -1 | xargs -r dirname)
fi
if [ -z "${TASK_REPORT:-}" ]; then
    TASK_REPORT=$(find .. -maxdepth 1 -iname '*task report*.pdf' 2>/dev/null | head -1)
fi

if [ -z "${PULL:-}" ] || [ ! -d "$PULL" ]; then
    echo "ERROR: no PlanGrid pull found. Set PULL=<dir containing tasks.json>." >&2
    exit 1
fi

echo "==> inputs"
echo "    pull        : $PULL"
echo "    task report : ${TASK_REPORT:-(none, items will render '(no pin clip)')}"
echo "    scope       : ${SCOPE:-(all items in the pull)}"
echo

# --- 1. consolidate --------------------------------------------------------
echo "==> 1/5 consolidate"
if [ -n "${SCOPE:-}" ]; then
    "$PY" scripts/consolidate.py "$PULL" -o data/items.json --only "$SCOPE"
else
    "$PY" scripts/consolidate.py "$PULL" -o data/items.json
fi

# --- 2. photos -------------------------------------------------------------
# EXIF rotation is applied here. PIL does not apply it on save, and the
# originals look upright in every normal image viewer, so a missed transpose
# only shows up as sideways photos in the rendered docx.
echo "==> 2/5 normalise photos"
"$PY" scripts/normalize_photos.py --items data/items.json \
    --dest "$BUILD/thumbs_uniform" --dims-out data/thumb_dims.json

# --- 3. sheet clips --------------------------------------------------------
echo "==> 3/5 sheet clips"
if [ -n "${TASK_REPORT:-}" ] && [ -f "$TASK_REPORT" ]; then
    "$PY" scripts/extract_sheet_clips.py "$TASK_REPORT" "$BUILD/sheet_clips_jpg" \
        --items-from data/items.json --dims-out "$BUILD/sheet_clip_dims_jpg.json"
else
    echo "    No Task Report PDF. Items will render '(no pin clip)'."
    echo "    Export a Task Report from PlanGrid and re-run to add pin clips."
    [ -f "$BUILD/sheet_clip_dims_jpg.json" ] || echo '{}' > "$BUILD/sheet_clip_dims_jpg.json"
fi

# --- 4. master -------------------------------------------------------------
# Fails loudly on a missing draft, an em/en dash, or a voice-rule violation.
echo "==> 4/5 build master"
"$PY" scripts/build_master.py --items data/items.json \
    --drafted data/drafted_items.json -o "$BUILD/master_report_items.json"

# --- 5. render -------------------------------------------------------------
echo "==> 5/5 render"
node scripts/gen_report.js "$BUILD"

echo "==> verify"
OUT=$("$PY" -c "import json;print(json.load(open('$BUILD/report.config.json'))['output_filename'])")
"$PY" scripts/verify_report.py "$BUILD/$OUT" "$BUILD/master_report_items.json"

echo
echo "==> done: $BUILD/$OUT"
echo "    Open in Word. Page numbers populate on open (Ctrl+A then F9 to force)."
