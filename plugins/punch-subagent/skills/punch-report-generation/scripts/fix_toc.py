#!/usr/bin/env python3
"""
fix_toc.py, rebuild the table of contents of a hand-edited punch report.

STATUS: proposed for the plugin. Derived from two working ad hoc
implementations, one for Miner Building A r2 and one for Miner Operations.

The problem it solves
---------------------
The pipeline builds the contents page as ORDINARY PARAGRAPHS, each holding a
hand-written PAGEREF field. There is no TOC field in the document. The result is
a split behaviour that misleads reviewers:

    reviewer presses F9        -> page numbers update correctly
    reviewer deletes an item   -> body renumbers itself, TOC does NOT
    reviewer retypes a heading -> TOC title goes stale AND the bookmark is lost
    reviewer pastes an item    -> no TOC entry, and a duplicate bookmark

So the TOC self-heals in exactly one respect and rots silently in every other,
which teaches the reviewer that F9 fixes it. It does not.

Observed end states: Miner Operations had 16 TOC entries against 9 items, seven
pointing at bookmarks that no longer existed, and two headings retyped so their
bookmarks were gone and the names stranded as punchitem12 and punchitem15.

The real fix is to emit a genuine `TOC \\o "1-1" \\h \\z \\u` field so Word's own
Update Table handles all of this. See CHANGE-LIST.md item 1. This script is what
you need anyway, for documents already in circulation and for reviewers who will
keep hand-editing.

What it does
------------
  1. Strips every punchitem bookmark, orphaned or not, so names can be reused.
  2. Re-anchors punchitem1..N onto the Heading1 paragraphs that actually exist,
     in document order, with UNIQUE numeric ids. Word keys bookmarks on w:id,
     not on the name; duplicates are why "Error! Bookmark not defined." appears.
  3. Rebuilds the TOC entries from those headings, titles taken verbatim.
  4. Sets w:updateFields so Word recalculates page numbers on open.

It never touches item body text. Descriptions, corrective actions and photos are
left byte-identical, which matters because the reviewer's wording is approved.

Two traps this handles, both of which produced wrong output on the first attempt:

  * The label runs are split by spellcheck markers (w:proofErr). Replacing only
    the first <w:t> leaves fragments of the old title stranded in the entry, so
    the whole hyperlink body is rebuilt as a single run.
  * w:updateFields must sit immediately before w:hdrShapeDefaults, because
    CT_Settings is an XSD sequence and Word rejects the file if it lands
    anywhere else.

Usage:
    python3 fix_toc.py <report.docx> [-o <out.docx>] [--check]

--check reports drift and exits nonzero without modifying anything, which is
what you want in a pre-issue gate.
"""
import argparse
import os
import re
import shutil
import sys
import zipfile

P_RE = re.compile(r'<w:p[ >].*?</w:p>', re.S)
HEAD_RE = re.compile(r'<w:pStyle w:val="Heading1"/>')


def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def text_of(p):
    return ''.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', p))


def strip_punchitem_bookmarks(doc):
    ids = re.findall(r'<w:bookmarkStart[^>]*w:name="punchitem\d+"[^>]*/>', doc)
    out = []
    for tag in ids:
        m = re.search(r'w:id="(\d+)"', tag)
        if m:
            out.append(m.group(1))
    doc = re.sub(r'<w:bookmarkStart[^>]*w:name="punchitem\d+"[^>]*/>', '', doc)
    for bid in out:
        doc = doc.replace(f'<w:bookmarkEnd w:id="{bid}"/>', '', 1)
    return doc, len(out)


def build_entry(template, k, title, cached):
    """Clone an existing TOC paragraph, swapping in the new label and anchor."""
    p = template
    # Rebuild each hyperlink body as ONE run. The originals are fragmented by
    # w:proofErr spellcheck markers, so a first-run-only substitution strands
    # pieces of the previous title.
    label = esc(f'Item {k}.  {title}')
    p = re.sub(
        r'(<w:hyperlink w:anchor="[^"]+" w:history="1">).*?(</w:hyperlink>)',
        lambda m: (m.group(1)
                   + '<w:r><w:rPr><w:sz w:val="19"/><w:szCs w:val="19"/></w:rPr>'
                   + f'<w:t xml:space="preserve">{label}</w:t></w:r>'
                   + m.group(2)),
        p, count=1, flags=re.S)
    p = re.sub(r'w:anchor="punchitem\d+"', f'w:anchor="punchitem{k}"', p)
    # Canonical field instruction: leading and trailing spaces, and the \h
    # switch. Word writes it this way; the renderer currently does not, which is
    # a latent source of fields that refuse to update.
    p = re.sub(r'<w:instrText[^>]*>[^<]*</w:instrText>',
               f'<w:instrText xml:space="preserve"> PAGEREF punchitem{k} \\\\h </w:instrText>',
               p, count=1)
    p = re.sub(r'(<w:fldChar w:fldCharType="separate"/></w:r>.*?<w:t>)\d+(</w:t>)',
               lambda m: m.group(1) + cached + m.group(2), p, count=1, flags=re.S)
    return p


def process(xml, check_only):
    paras = list(P_RE.finditer(xml))
    heads = [i for i, m in enumerate(paras) if HEAD_RE.search(m.group(0))]
    toc = [i for i, m in enumerate(paras) if 'PAGEREF punchitem' in m.group(0)]

    if not heads:
        raise SystemExit('ERROR: no Heading1 paragraphs found, is this a punch report?')
    if not toc:
        raise SystemExit('ERROR: no TOC entries found.')
    if toc != list(range(toc[0], toc[-1] + 1)):
        raise SystemExit('ERROR: TOC entries are not contiguous, refusing to guess.')
    for a, b in zip(toc, toc[1:]):
        if xml[paras[a].end():paras[b].start()].strip():
            raise SystemExit('ERROR: unexpected content between TOC entries.')

    titles = [text_of(paras[i].group(0)) for i in heads]
    toc_titles = [re.sub(r'^Item \d+\.\s*', '', text_of(paras[i].group(0)).split('\t')[0]).strip()
                  for i in toc]

    drift = len(toc) != len(heads) or any(
        t not in text_of(paras[toc[k]].group(0)) for k, t in enumerate(titles[:len(toc)]))

    print(f'headings : {len(heads)}')
    print(f'TOC      : {len(toc)} entries')
    if len(toc) != len(heads):
        print(f'DRIFT    : {len(toc)} entries against {len(heads)} items')

    if check_only:
        return None, drift, titles

    cached = []
    for i in toc:
        m = re.search(r'<w:fldChar w:fldCharType="separate"/></w:r>.*?<w:t>(\d+)</w:t>',
                      paras[i].group(0), re.S)
        cached.append(m.group(1) if m else '1')

    template = paras[toc[0]].group(0)
    toc_start, toc_end = paras[toc[0]].start(), paras[toc[-1]].end()

    xml, n_stripped = strip_punchitem_bookmarks(xml)
    print(f'stripped {n_stripped} existing punchitem bookmarks')

    # Recompute positions: stripping bookmarks shifted every offset.
    paras = list(P_RE.finditer(xml))
    heads = [i for i, m in enumerate(paras) if HEAD_RE.search(m.group(0))]
    toc = [i for i, m in enumerate(paras) if 'PAGEREF punchitem' in m.group(0)]
    titles = [text_of(paras[i].group(0)) for i in heads]

    edits = []
    for k, pi in enumerate(heads, start=1):
        m = paras[pi]
        p = m.group(0)
        bid = 9000 + k          # unique, and clear of anything Word allocated
        p = p.replace('</w:pPr>',
                      f'</w:pPr><w:bookmarkStart w:id="{bid}" w:name="punchitem{k}"/>', 1)
        p = p[:p.rindex('</w:p>')] + f'<w:bookmarkEnd w:id="{bid}"/></w:p>'
        edits.append((m.start(), m.end(), p))

    entries = ''.join(
        build_entry(template, k, t, cached[k - 1] if k - 1 < len(cached) else '1')
        for k, t in enumerate(titles, start=1))
    edits.append((paras[toc[0]].start(), paras[toc[-1]].end(), entries))

    for s, e, rep in sorted(edits, key=lambda x: -x[0]):
        xml = xml[:s] + rep + xml[e:]

    return xml, drift, titles


def set_update_fields(settings):
    s = re.sub(r'<w:updateFields[^>]*/>', '', settings)
    # CT_Settings is an XSD sequence: updateFields must sit immediately before
    # hdrShapeDefaults or Word rejects the document.
    for anchor in ('<w:hdrShapeDefaults', '<w:footnotePr', '<w:compat'):
        if anchor in s:
            return s.replace(anchor, '<w:updateFields w:val="true"/>' + anchor, 1)
    raise SystemExit('ERROR: no insertion point for updateFields in settings.xml')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('docx')
    ap.add_argument('-o', '--out', default=None,
                    help='default: edit in place')
    ap.add_argument('--check', action='store_true',
                    help='report drift, change nothing, exit 1 if the TOC is stale')
    args = ap.parse_args()

    with zipfile.ZipFile(args.docx) as z:
        names = z.namelist()
        blobs = {n: z.read(n) for n in names}

    xml, drift, titles = process(blobs['word/document.xml'].decode('utf8'), args.check)

    if args.check:
        if drift:
            print('\nTOC IS STALE. Run without --check to rebuild.')
            sys.exit(1)
        print('\nTOC matches the headings.')
        return

    blobs['word/document.xml'] = xml.encode('utf8')
    if 'word/settings.xml' in blobs:
        blobs['word/settings.xml'] = set_update_fields(
            blobs['word/settings.xml'].decode('utf8')).encode('utf8')
        print('updateFields set')

    out = args.out or args.docx
    tmp = out + '.tmp'
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as z:
        for name in sorted(names, key=lambda x: x != '[Content_Types].xml'):
            z.writestr(name, blobs[name])
    shutil.move(tmp, out)

    print(f'\nTOC rebuilt with {len(titles)} entries -> {out}')
    for k, t in enumerate(titles, 1):
        print(f'  Item {k}.  {t}')


if __name__ == '__main__':
    main()
