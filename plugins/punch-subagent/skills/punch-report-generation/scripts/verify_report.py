#!/usr/bin/env python3
"""
verify_report.py, check the rendered .docx without converting it to PDF.

Verification used to run by converting to PDF with LibreOffice and scanning the
text layer. That is no longer done, for two reasons:

  1. We do not produce the PDF any more. Victor generates it from Word when the
     markup is finished, so Word recalculates fields on export.
  2. LibreOffice paginates differently from Word, so any check that depended on
     its pagination was measuring the wrong renderer. That is exactly what made
     the old static TOC page numbers wrong.

So these checks read the OOXML directly, which is what Word will actually open.
Anything genuinely pagination dependent cannot be asserted here and is instead
handled by making Word compute it (PAGEREF fields + w:updateFields).

Usage:
    python3 verify_report.py build/Miner-Building-A-Punch-Report-DRAFT-v0.1.docx
"""
import json
import os
import re
import sys
import zipfile

DASH_RE = re.compile(r"[–—]")
VOICE_BANNED = [r"photograph", r"in the frame", r"field engineer", r"this photo"]


USAGE = ("usage: verify_report.py <report.docx> [master_report_items.json]\n"
         "\n"
         "Checks the rendered .docx by reading its OOXML directly. No LibreOffice\n"
         "and no PDF conversion: verification must read the artifact the reader\n"
         "actually opens, and LibreOffice paginates differently from Word.\n"
         "\n"
         "  report.docx                the rendered report\n"
         "  master_report_items.json   defaults to alongside the .docx\n")


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(USAGE)
        sys.exit(0 if len(sys.argv) > 1 else 2)
    path = sys.argv[1]
    master_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        os.path.dirname(path) or ".", "master_report_items.json")

    z = zipfile.ZipFile(path)
    doc = z.read("word/document.xml").decode("utf8")
    settings = z.read("word/settings.xml").decode("utf8")
    master = json.load(open(master_path))
    n_items = len(master)

    # report.config.json carries some INTERNAL fields that must never reach the
    # client-facing document. Absent config just skips those checks.
    cfg_path = os.path.join(os.path.dirname(master_path) or ".", "report.config.json")
    cfg = {}
    if os.path.isfile(cfg_path):
        try:
            cfg = json.load(open(cfg_path, encoding="utf8"))
        except Exception:
            cfg = {}

    # visible text only, so XML attributes cannot create false positives
    text = " ".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", doc))

    pagerefs = re.findall(r"PAGEREF\s+(\w+)", doc)
    bookmarks = set(re.findall(r'w:bookmarkStart[^>]*w:name="(punchitem\d+)"', doc))
    media = [n for n in z.namelist() if n.startswith("word/media/")]
    expected_photos = sum(len(m["photo_paths"]) for m in master)

    checks = []

    # content integrity
    checks.append(("no em or en dashes", not DASH_RE.findall(text),
                   f"{len(DASH_RE.findall(text))} found"))
    # Voice rule applies to DESCRIPTIONS ONLY. Editor's Notes are internal, are
    # deleted before issuing, and legitimately talk about photos and pins, so
    # scanning the whole document text produces false failures.
    voice_hits = []
    for m in master:
        for pat in VOICE_BANNED:
            hit = re.search(pat, m["description"], re.I)
            if hit:
                voice_hits.append(f"{m['plangrid_ref']}:{hit.group(0)}")
    checks.append(("no photo narration or third person in descriptions", not voice_hits,
                   f"matched {voice_hits}"))
    checks.append(("verbatim pin note not rendered", "original note" not in text, "found"))

    # TOC must be live fields, not baked text
    checks.append((f"{n_items} PAGEREF fields present", len(pagerefs) == n_items,
                   f"got {len(pagerefs)}"))
    checks.append(("every PAGEREF resolves to a bookmark",
                   not (set(pagerefs) - bookmarks),
                   f"dangling: {sorted(set(pagerefs) - bookmarks)}"))
    # Names being right is NOT enough. The docx library writes every bookmark
    # with w:id="1", and Word keys bookmarks on the numeric id, not the name:
    # duplicate ids mean it keeps one and discards the rest, so every TOC entry
    # after the first renders "Error! Bookmark not defined." on F9. That shipped
    # once. fix_bookmark_ids.py renumbers them; this asserts it ran.
    bm_ids = re.findall(r'<w:bookmarkStart[^>]*w:id="(\d+)"', doc)
    dup_ids = sorted({i for i in bm_ids if bm_ids.count(i) > 1})
    checks.append(("bookmark ids are unique", not dup_ids,
                   f"duplicated w:id {dup_ids}, run scripts/fix_bookmark_ids.py"))

    checks.append(("no stale hardcoded page numbers",
                   not re.findall(r">p\. \d+<", doc), "found baked 'p. N' text"))
    checks.append(("Word set to refresh fields on open",
                   "<w:updateFields" in settings, "w:updateFields missing"))

    # The contents block must be a REAL TOC field (begin / instr / separate /
    # cached entries / end), not free-standing paragraphs: only a field makes
    # Word's Update Table repair titles, numbers AND entry count together.
    # Checked in the form Word actually consumes, not by trusting the renderer.
    toc_instrs = re.findall(r"<w:instrText[^>]*>([^<]*TOC[^<]*)</w:instrText>", doc)
    checks.append(("a TOC field instruction is present", len(toc_instrs) == 1,
                   f"found {len(toc_instrs)} TOC instrText nodes, expected 1"))
    if toc_instrs:
        canonical = re.match(r"^ TOC \\o &quot;1-1&quot; \\h \\z \\u $", toc_instrs[0]) \
            or re.match(r'^ TOC \\o "1-1" \\h \\z \\u $', toc_instrs[0])
        checks.append(("TOC instruction is canonical", bool(canonical),
                       f"got {toc_instrs[0]!r}"))
        # The field must open before the first cached entry and close after the
        # last: an unterminated field swallows the rest of the document on F9.
        toc_pos = doc.find(toc_instrs[0])
        seg = doc[:toc_pos]
        begins = seg.count('w:fldCharType="begin"')
        after = doc[toc_pos:]
        checks.append(("TOC field opens and closes",
                       begins >= 1 and 'w:fldCharType="separate"' in after
                       and 'w:fldCharType="end"' in after,
                       "field chars incomplete around TOC instruction"))
    checks.append((f"TOC cached entries match item count ({n_items})",
                   len(pagerefs) == n_items,
                   f"{len(pagerefs)} entries against {n_items} items -- the TOC has rotted; "
                   "re-render or run scripts/fix_toc.py"))

    # layout
    checks.append(("one page break per item",
                   doc.count("<w:pageBreakBefore/>") >= n_items,
                   f"got {doc.count('<w:pageBreakBefore/>')}"))
    checks.append(("all photos embedded", len(media) >= expected_photos,
                   f"{len(media)} media vs {expected_photos} photos"))

    # letterhead must be native, not the pasted strip
    checks.append(("letterhead built natively",
                   not any("letterhead" in n for n in z.namelist()),
                   "letterhead_strip bitmap is embedded"))

    # The EP project number is internal tracking. It belongs in report.config.json
    # and in our own records, never on a page a client, GC or subcontractor reads.
    # Asserted rather than remembered, because it is the kind of thing that gets
    # pasted onto a cover once and then ships for years.
    ep_no = str(cfg.get("ep_project_no") or "").strip()
    if ep_no and not ep_no.startswith("<"):
        norm = re.sub(r"\s+", " ", text)
        checks.append(("EP project number not rendered (internal only)",
                       ep_no not in norm,
                       f"'{ep_no}' appears in the document text"))

    print(f"verifying {os.path.basename(path)}  ({n_items} items)\n")
    failed = 0
    for name, ok, detail in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  <- {detail}"))
        failed += not ok

    print(f"\n  embedded media: {len(media)}  |  file size: {os.path.getsize(path)/1e6:.1f} MB")
    print("\n  NOTE: page numbers are Word fields. They are blank or stale until Word")
    print("  updates them, which it does on open and on PDF export. Ctrl+A then F9 forces it.")

    if failed:
        sys.exit(f"\n{failed} check(s) FAILED")
    print("\nall checks passed")


if __name__ == "__main__":
    main()
