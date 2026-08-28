#!/usr/bin/env python3
"""
import_reviewed_docx.py, recover a reviewer's edited report back into the pipeline.

STATUS: prototype. Assembled from the ad hoc code that actually produced Miner
Building A r4 and r5, where it recovered 16 approved write-ups and mapped every
one to its PlanGrid pin. Packaged here as the starting point for a first-class
script. Not yet run as a single program end to end.

The gap this fills
------------------
The real workflow is:

    pipeline drafts  ->  reviewer edits heavily in Word  ->  more site visits
    happen  ->  the report must be rebuilt with the reviewer's wording intact

The pipeline has no answer for this. It can only draft from scratch, which
discards the reviewer's approved text. On Miner Building A the reviewer had also
deleted two items, merged two pins into one, retyped several headings (destroying
their bookmarks) and silently dropped one photo. None of that is recorded
anywhere except in the document itself.

The hard part is not parsing the docx. It is working out WHICH REPORT ITEM
CORRESPONDS TO WHICH PLANGRID PIN, because the document does not record it.

Matching strategy, and why
--------------------------
First attempt was photo caption timestamps: the report prints
`Photo 1  |  08/20/2026 16:23` and the source filenames are
`<uid>__20260820_162337_photo.jpg`. This is ambiguous the moment two photos share
a minute, and three did.

What works is PIXEL MATCHING. Compare a 32x32 greyscale signature of each image
embedded in the reviewer's document against each normalised thumbnail. On the
real data all 27 photos matched at distance 0.0, because the embedded image IS
the normalised thumbnail, byte for byte. It also identified, for free, the one
photo the reviewer had deleted.

Guard rail that must not be dropped
-----------------------------------
build_master.py's sanitize() rewrites " - " to ", " and collapses runs of
whitespace. Run it against the reviewer's recovered strings BEFORE loading them
and FAIL LOUDLY on any difference, rather than silently altering approved
wording. That check is implemented below and it is the reason verbatim lifting
was safe on this project.

Usage:
    python3 import_reviewed_docx.py <reviewed.docx> \
        --items data/items.json \
        --thumbs build/thumbs_uniform \
        -o data/drafted_items.json \
        [--report-map]
"""
import argparse
import json
import os
import re
import zipfile

P_RE = re.compile(r'<w:p[ >].*?</w:p>', re.S)
HEAD_RE = re.compile(r'<w:pStyle w:val="Heading1"/>')

# Mirrors build_master.py. Keep in sync, or import it directly once this script
# lives beside it in scripts/.
DASH_RE = re.compile(r"[–—]")


def sanitize(s):
    s = DASH_RE.sub(",", s)
    s = re.sub(r" - ", ", ", s)
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip()


# ----------------------------------------------------------------- docx parsing
def parse_reviewed(path):
    """Pull one record per Heading1 out of a rendered punch report."""
    with zipfile.ZipFile(path) as z:
        doc = z.read('word/document.xml').decode('utf8')
        rels = z.read('word/_rels/document.xml.rels').decode('utf8')
    rel_map = dict(re.findall(r'Id="([^"]+)"[^>]*Target="media/([^"]+)"', rels))

    paras = list(P_RE.finditer(doc))
    heads = [i for i, m in enumerate(paras) if HEAD_RE.search(m.group(0))]
    bounds = heads + [len(paras)]

    def txt(p):
        return ''.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', p))

    out = []
    for k in range(len(heads)):
        lo, hi = bounds[k], bounds[k + 1]
        chunk = [paras[i].group(0) for i in range(lo, hi)]
        texts = [txt(p).strip() for p in chunk]

        media = []
        for p in chunk:
            for rid in re.findall(r'r:embed="([^"]+)"', p):
                if rel_map.get(rid):
                    media.append(rel_map[rid])

        def after(label):
            for i, t in enumerate(texts):
                if t == label:
                    for j in range(i + 1, len(texts)):
                        if texts[j]:
                            return texts[j]
            return None

        out.append({
            'item_number': k + 1,
            'title': texts[0],
            'description': after('Item Description'),
            'corrective_action': after('Corrective Action'),
            'sheet_field': after('Drawing Sheet'),
            # The FIRST embedded image in an item is the sheet clip; the rest are
            # photos. Relied on by the renderer's layout and stable in practice.
            'clip_media': media[0] if media else None,
            'photo_media': media[1:],
            'captions': [t for t in texts if re.match(r'^Photo \d+', t)],
        })
    return out, path


# ------------------------------------------------------------- pixel matching
def signature(path):
    from PIL import Image
    import numpy as np
    im = Image.open(path).convert('L').resize((32, 32))
    a = np.asarray(im, dtype=float)
    return a / (a.std() or 1)


def match_photos(reviewed, docx_path, thumbs_dir, items):
    import tempfile

    thumbs = {}
    for f in os.listdir(thumbs_dir):
        if f.lower().endswith('.jpg'):
            thumbs[os.path.splitext(f)[0]] = signature(os.path.join(thumbs_dir, f))

    uid_to_pin = {}
    for it in items:
        for p in it['photos']:
            uid_to_pin[p['uid']] = it['number']

    scratch = tempfile.mkdtemp(prefix='reviewed_media_')
    with zipfile.ZipFile(docx_path) as z:
        for name in z.namelist():
            if name.startswith('word/media/'):
                with open(os.path.join(scratch, os.path.basename(name)), 'wb') as fh:
                    fh.write(z.read(name))

    for rec in reviewed:
        hits = []
        for m in rec['photo_media']:
            sig = signature(os.path.join(scratch, m))
            best = min(((uid, float(((sig - t) ** 2).mean()))
                        for uid, t in thumbs.items()), key=lambda x: x[1])
            hits.append({'media': m, 'uid': best[0], 'distance': round(best[1], 4),
                         'pin': uid_to_pin.get(best[0])})
        rec['photo_matches'] = hits
        rec['pins'] = sorted({h['pin'] for h in hits if h['pin'] is not None})
    return reviewed


# ------------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('reviewed_docx')
    ap.add_argument('--items', default='data/items.json')
    ap.add_argument('--thumbs', default='build/thumbs_uniform')
    ap.add_argument('-o', '--out', default='data/drafted_items.json')
    ap.add_argument('--report-map', action='store_true',
                    help='print the item to pin mapping and exit without writing')
    ap.add_argument('--max-distance', type=float, default=0.05,
                    help='refuse a photo match worse than this')
    args = ap.parse_args()

    items = json.load(open(args.items))
    reviewed, path = parse_reviewed(args.reviewed_docx)
    reviewed = match_photos(reviewed, path, args.thumbs, items)

    print(f'{len(reviewed)} items recovered from {os.path.basename(path)}\n')
    problems = []
    for rec in reviewed:
        bad = [h for h in rec['photo_matches'] if h['distance'] > args.max_distance]
        flag = '  <-- CHECK' if (bad or len(rec['pins']) != 1) else ''
        print(f"  item {rec['item_number']:>2} -> pins {rec['pins']}  "
              f"{len(rec['photo_matches'])} photo(s){flag}")
        if bad:
            problems.append(f"item {rec['item_number']}: weak photo match "
                            f"{[(h['media'], h['distance']) for h in bad]}")
        if len(rec['pins']) > 1:
            problems.append(f"item {rec['item_number']}: spans pins {rec['pins']}, "
                            f"the reviewer merged them. Encode with merge_pins.py "
                            f"and omit the absorbed pin.")
        if not rec['pins']:
            problems.append(f"item {rec['item_number']}: no pin matched, "
                            f"possibly an item the reviewer wrote by hand.")

    # Photos present in the pull but absent from the reviewed document were
    # deliberately deleted by the reviewer. Surface, never silently restore.
    used = {h['uid'] for rec in reviewed for h in rec['photo_matches']}
    dropped = [(it['number'], p['title']) for it in items
               for p in it['photos'] if p['uid'] not in used]
    if dropped:
        print(f'\nphotos in the pull but NOT in the reviewed document '
              f'(reviewer deleted these, do not restore): {dropped}')

    if problems:
        print('\nNEEDS A DECISION:')
        for p in problems:
            print('  ' + p)

    if args.report_map:
        return

    drafted, unsafe = [], []
    for rec in reviewed:
        if len(rec['pins']) != 1:
            continue
        pin = rec['pins'][0]
        for field in ('title', 'description', 'corrective_action'):
            v = rec[field] or ''
            if sanitize(v) != v:
                unsafe.append(f"item {rec['item_number']} {field}: build_master's "
                              f"sanitizer would alter approved wording")
        drafted.append({
            'number': pin,
            'title': rec['title'],
            'description': rec['description'],
            'corrective_action': rec['corrective_action'],
            # build_master.py must treat this as untouchable.
            'origin': 'reviewer_final',
            'confidence': 'reviewer approved',
        })

    if unsafe:
        raise SystemExit('REFUSING TO WRITE. The sanitizer would change the '
                         "reviewer's text:\n  " + '\n  '.join(unsafe))

    drafted.sort(key=lambda d: d['number'])
    json.dump(drafted, open(args.out, 'w'), indent=2)
    print(f'\nwrote {len(drafted)} reviewer_final items -> {args.out}')
    print('Items spanning multiple pins were SKIPPED and must be handled with '
          'merge_pins.py before re-running.')


if __name__ == '__main__':
    main()
