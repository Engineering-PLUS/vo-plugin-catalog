#!/usr/bin/env python3
"""
fix_bookmark_ids.py, give every bookmark in a rendered .docx a unique w:id.

STATUS: shipped. Used to produce Miner Building A r5.

Why this exists
---------------
The `docx` npm library writes every Bookmark with the SAME numeric id
(w:id="1"). The bookmark NAMES are correct and unique, so a name-based check
passes and the file looks fine, but Word keys bookmarks on the numeric id. With
24 bookmarks all claiming id 1 it keeps one and discards the rest, and every
TOC entry after the first renders:

    Error! Bookmark not defined.

The reviewer sees it the moment they open the document and press F9. This
shipped in r4 and is exactly the class of defect verify_report.py exists to
catch, so the matching assertion was added there too.

Renumbers bookmarkStart/bookmarkEnd pairs 1..N in document order, matching them
by position because the broken ids carry no information.

Also canonicalizes PAGEREF field instructions. The docx library emits
`<w:instrText xml:space="preserve">PAGEREF punchitem1</w:instrText>` -- no
padding, no \\h switch -- where Word itself writes
`<w:instrText xml:space="preserve"> PAGEREF punchitem1 \\h </w:instrText>`.
Word tolerates the short form most of the time, which is tolerance being
relied on rather than correctness (CHANGE-LIST 1c). Rewritten to the form
Word writes.

Usage:
    python3 fix_bookmark_ids.py <report.docx>
"""
import re
import shutil
import sys
import zipfile

DOC = "word/document.xml"


def main(path):
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        blobs = {n: z.read(n) for n in names}

    xml = blobs[DOC].decode("utf8")

    # Walk starts and ends together in document order so each end takes the id
    # of the most recently opened start.
    out, pos, next_id, stack = [], 0, 1, []
    for m in re.finditer(r'<w:bookmark(Start|End)[^>]*/>', xml):
        out.append(xml[pos:m.start()])
        tag = m.group(0)
        if m.group(1) == "Start":
            tag = re.sub(r'w:id="\d+"', f'w:id="{next_id}"', tag)
            stack.append(next_id)
            next_id += 1
        else:
            tag = re.sub(r'w:id="\d+"', f'w:id="{stack.pop() if stack else 0}"', tag)
        out.append(tag)
        pos = m.end()
    out.append(xml[pos:])
    fixed = "".join(out)

    # Canonical PAGEREF instruction form: " PAGEREF <name> \h " with
    # xml:space="preserve". Leaves already-canonical instructions unchanged.
    def canon_pageref(m):
        name = m.group(1)
        return f'<w:instrText xml:space="preserve"> PAGEREF {name} \\h </w:instrText>'
    fixed = re.sub(
        r'<w:instrText[^>]*>\s*PAGEREF\s+(\w+)(?:\s+\\h)?\s*</w:instrText>',
        canon_pageref, fixed)

    n = next_id - 1
    if fixed == xml:
        print(f"bookmark ids already unique ({n} bookmarks), nothing to do")
        return
    blobs[DOC] = fixed.encode("utf8")

    tmp = path + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        # [Content_Types].xml must be the first entry in an OOXML package.
        for name in sorted(names, key=lambda x: x != "[Content_Types].xml"):
            z.writestr(name, blobs[name])
    shutil.move(tmp, path)
    print(f"renumbered {n} bookmarks 1..{n} -> {path}")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0 if len(sys.argv) > 1 else 1)
    main(sys.argv[1])
