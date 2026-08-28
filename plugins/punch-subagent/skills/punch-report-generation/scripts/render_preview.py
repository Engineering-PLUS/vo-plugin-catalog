#!/usr/bin/env python3
"""
render_preview.py, rasterise a report to PNG pages for visual spot checks.

Why this is not "generate the PDF"
----------------------------------
The pipeline deliberately never ships a PDF: Word recalculates TOC page-number
fields on open and on export, LibreOffice does not, and it paginates
differently, so a LibreOffice PDF carries wrong page numbers. That ban is
correct and stays.

This is a different need. Verifying the OOXML tells you an element exists; it
does not tell you the page LOOKS right. An empty photo grid can pass a cell
count and still render as an invisible hairline. This converts to PDF in a
scratch directory, rasterises to PNG, and DELETES THE PDF, so no PDF can ever
be mistaken for a deliverable.

READ THE OUTPUT AS LAYOUT ONLY. Page numbers, page counts and page breaks in
this render are LibreOffice's, not Word's. Never quote a page number from it.

Usage:
    python3 render_preview.py <report.docx> [-o review/pages] [--pages 4,19-21]
                              [--dpi 110] [--contact]
"""
import argparse
import glob
import os
import shutil
import subprocess
import sys
import tempfile


def parse_pages(spec):
    if not spec:
        return None
    keep = set()
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            lo, hi = chunk.split("-", 1)
            keep.update(range(int(lo), int(hi) + 1))
        else:
            keep.add(int(chunk))
    return keep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("docx")
    ap.add_argument("-o", "--out-dir", default="review/pages")
    ap.add_argument("--pages", default=None, help='1-based, e.g. "4,19-21"')
    ap.add_argument("--dpi", type=int, default=110)
    ap.add_argument("--contact", action="store_true",
                    help="also write contact_sheet.png, all pages tiled")
    args = ap.parse_args()

    if not os.path.isfile(args.docx):
        sys.exit(f"ERROR: no such file: {args.docx}")

    import pymupdf
    from PIL import Image

    os.makedirs(args.out_dir, exist_ok=True)
    scratch = tempfile.mkdtemp(prefix="preview_")
    try:
        r = subprocess.run(
            ["soffice", "--headless", "--convert-to", "pdf",
             "--outdir", scratch, args.docx],
            capture_output=True, text=True, timeout=600)
        hits = glob.glob(os.path.join(scratch, "*.pdf"))
        if not hits:
            sys.exit(f"ERROR: conversion produced no PDF.\n{r.stdout}\n{r.stderr}")

        doc = pymupdf.open(hits[0])
        keep = parse_pages(args.pages)
        written = []
        for i in range(doc.page_count):
            n = i + 1
            if keep is not None and n not in keep:
                continue
            pix = doc[i].get_pixmap(dpi=args.dpi)
            path = os.path.join(args.out_dir, f"page_{n:02d}.png")
            pix.pil_save(path, format="PNG")
            written.append(path)
        doc.close()
    finally:
        # The PDF never outlives this function. That is the whole point.
        shutil.rmtree(scratch, ignore_errors=True)

    print(f"rendered {len(written)} page(s) at {args.dpi} dpi -> {args.out_dir}")

    if args.contact and written:
        thumbs = [Image.open(p) for p in written]
        tw = 300
        th = int(tw * thumbs[0].height / thumbs[0].width)
        cols = min(6, len(thumbs))
        rows = (len(thumbs) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * tw, rows * th), "white")
        for k, im in enumerate(thumbs):
            sheet.paste(im.resize((tw, th)), ((k % cols) * tw, (k // cols) * th))
        cs = os.path.join(args.out_dir, "contact_sheet.png")
        sheet.save(cs)
        print(f"contact sheet -> {cs}")

    print("LAYOUT CHECK ONLY. Page numbers and pagination here are LibreOffice's, "
          "not Word's. Do not quote a page number from this render.")


if __name__ == "__main__":
    main()
