#!/usr/bin/env python3
"""
build_master.py, assemble the render-ready master_report_items.json.

This closes the gap the NVA06B pipeline left open: master_report_items.json was
assembled ad hoc from items.json plus hand-written drafts, so a report could not
be rebuilt from source without redoing that step by hand. This script makes the
assembly reproducible.

Inputs
  data/items.json           consolidate.py output, the PlanGrid facts
  data/drafted_items.json   the human/model judgment layer, keyed by PlanGrid number
Output
  build/master_report_items.json

Rules enforced here so the renderer never has to care:
  - NO EM OR EN DASHES anywhere in any string. Swept and asserted, not hoped for.
    (Standing EPLUS report rule; verification asserts zero in the PDF text layer.)
  - Corrective actions always start with a capital letter.
  - photo_paths are BASENAMES ONLY. The renderer resolves them against its own
    thumbs_uniform directory. Passing absolute source paths silently renders the
    unnormalized, EXIF-sideways original.
  - Items with no drafted entry fail loudly rather than rendering blank.

Usage:
    python3 build_master.py --items data/items.json \
        --drafted data/drafted_items.json -o build/master_report_items.json
"""
import argparse
import json
import os
import re
import sys

DASH_RE = re.compile(r"[–—]")
UNDETERMINED_CA = "N/A, see Editor's Note"

# Item descriptions are written in field-report voice: the engineer stating what the
# condition IS. Two failure modes get caught here because both read badly to a client
# and both are easy to slip back into:
#   1. Narrating the evidence ("the photograph shows...", "not visible in the frame").
#      The report describes the site, not the photo library.
#   2. Third person self-reference ("the field engineer recorded..."). This report is
#      written BY the field engineer, so that reads as someone else talking about them.
# Editor's Notes are internal and exempt, they may discuss photos and pins freely.
VOICE_BANNED = [
    r"photograph", r"photo shows", r"in the frame", r"\bimages?\b",
    r"field engineer", r"no description was recorded", r"this photo",
    r"not determinable from",
]


# PlanGrid's sheet-name OCR reads the character after a leading T as the LETTER O
# rather than a ZERO when drawings are uploaded, so a set that is really T02-01A1
# comes back as TO2-01A1. The upload-side fix is to correct each sheet name by hand
# at upload time, which is easy to forget and is not something the report can rely on.
# Every sheet in the punch corpus (85 distinct, all T-series) uses a zero, so the
# correct form is unambiguous.
#
# Scoped deliberately narrowly: a leading T, then a LETTER O, then a DIGIT. That
# matches TO2-01A1 and TO5-09 while leaving any genuine word starting with "TO"
# alone, because a real sheet designator always has a digit in that position.
SHEET_OCR_RE = re.compile(r"\bT[Oo](?=\d)")


def normalize_sheet(name):
    """Repair the PlanGrid letter-O-for-zero OCR error in a sheet designator."""
    return SHEET_OCR_RE.sub("T0", name or "")


def sanitize(s):
    """Remove em/en dashes and hyphens used as em dashes. Preserve real hyphens."""
    if not isinstance(s, str):
        return s
    s = DASH_RE.sub(",", s)
    s = re.sub(r" - ", ", ", s)
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip()


def walk_sanitize(obj):
    if isinstance(obj, str):
        return sanitize(obj)
    if isinstance(obj, list):
        return [walk_sanitize(v) for v in obj]
    if isinstance(obj, dict):
        return {k: walk_sanitize(v) for k, v in obj.items()}
    return obj


def capitalize_first(s):
    if not s:
        return s
    return s[0].upper() + s[1:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", default="data/items.json")
    ap.add_argument("--drafted", default="data/drafted_items.json")
    ap.add_argument("-o", "--out", default="build/master_report_items.json")
    ap.add_argument("--omit", default="", help="comma list of PlanGrid numbers to drop")
    args = ap.parse_args()

    items = json.load(open(args.items))
    drafted = {d["number"]: d for d in json.load(open(args.drafted))}
    omit = {int(x) for x in args.omit.split(",") if x.strip()}

    missing = [i["number"] for i in items if i["number"] not in drafted and i["number"] not in omit]
    if missing:
        sys.exit(f"ERROR: no drafted entry for PlanGrid items {missing}. "
                 f"Every item must be drafted, including undeterminable ones.")

    master, display_n = [], 0
    for it in sorted(items, key=lambda x: x["number"]):
        num = it["number"]
        if num in omit:
            continue
        d = drafted[num]
        display_n += 1

        ca = d.get("corrective_action") or UNDETERMINED_CA
        sheet_name = normalize_sheet(it.get("sheet_name") or "")
        sheet_desc = it.get("sheet_description") or ""
        sheet_display = f"{sheet_name}, {sheet_desc}" if sheet_desc else (sheet_name or "N/A")

        room = (it.get("room") or "").strip()

        master.append({
            "display_number": display_n,
            "plangrid_ref": f"#{num}",
            "title": d["title"],
            "description": d["description"],
            "corrective_action": capitalize_first(ca),
            # PlanGrid room is empty on 100% of pins in this pull. Say so rather
            # than printing a bare "N/A" the reader has to interpret.
            "location": room or "Not recorded in PlanGrid, see sheet reference",
            "sheet_display": sheet_display,
            "sheet_name": sheet_name,
            "sheet_description": sheet_desc,
            "photo_paths": [os.path.basename(p["path"]).split("__")[0] + ".jpg"
                            for p in it["photos"]],
            "photo_titles": [p["title"] for p in it["photos"]],
            "origin": d.get("origin"),
            "confidence": d.get("confidence"),
            # renderer expects this key name for the engineer's verbatim wording
            "jim_original_text": d.get("field_note"),
            "precedent_note": d.get("precedent_note"),
            "editor_note": d.get("editor_note"),
            "status": it.get("status"),
            "photo_date": (it["photos"][0]["captured"][:8] if it["photos"] else None),
        })

    master = walk_sanitize(master)

    # Belt and braces: assert the dash rule actually held.
    blob = json.dumps(master)
    bad = DASH_RE.findall(blob)
    if bad:
        sys.exit(f"ERROR: {len(bad)} em/en dashes survived sanitization.")

    # voice guard, descriptions only
    offenders = []
    for m in master:
        for pat in VOICE_BANNED:
            hit = re.search(pat, m["description"], re.I)
            if hit:
                offenders.append(f"  {m['plangrid_ref']}: {hit.group(0)!r} in description")
    if offenders:
        sys.exit("ERROR: item descriptions must be in field-report voice, not photo "
                 "narration or third person.\n" + "\n".join(offenders))

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    json.dump(master, open(args.out, "w"), indent=2)

    origins = {}
    for m in master:
        origins[m["origin"]] = origins.get(m["origin"], 0) + 1
    print(f"wrote {args.out}")
    print(f"  items          : {len(master)} (omitted {sorted(omit) or 'none'})")
    print(f"  photos         : {sum(len(m['photo_paths']) for m in master)}")
    print(f"  origins        : {origins}")
    print(f"  with precedent : {sum(1 for m in master if m['precedent_note'])}")
    print(f"  editor notes   : {sum(1 for m in master if m['editor_note'])}")
    print(f"  em/en dashes   : 0 (asserted)")


if __name__ == "__main__":
    main()
