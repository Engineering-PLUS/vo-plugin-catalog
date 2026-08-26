#!/usr/bin/env python3
"""
normalize_photos.py, letterbox every site photo onto one identical canvas.

Why letterbox: the report renders all photos at the exact same size. A source set
mixes portrait and landscape. Scaling each to a common *width* still leaves
different heights, which breaks both the uniform-grid rule and the row-height math
that pagination depends on. Letterboxing onto a single canvas makes every embedded
image byte-for-byte identical in dimensions, so rows are predictable.

CRITICAL: PIL does NOT apply EXIF orientation on save. ImageOps.exif_transpose()
must be called BEFORE resize or every portrait photo renders sideways in the docx,
while still looking correct in every normal image viewer. Easy to miss until the
document is built. Do not remove that call.

Changed from the NVA06B version: this reads data/items.json and pulls photos from
wherever they live (base and delta folders both), rather than globbing one source
directory. It also picks the canvas orientation from the actual set instead of
assuming portrait, and names outputs by photo uid so items.json paths stay valid.

Usage:
    python3 normalize_photos.py --items data/items.json --dest images/thumbs_uniform
"""
import argparse
import json
import os
from collections import Counter

from PIL import Image, ImageOps

PORTRAIT = (700, 933)
LANDSCAPE = (933, 700)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", default="data/items.json")
    ap.add_argument("--dest", default="images/thumbs_uniform")
    ap.add_argument("--dims-out", default="data/thumb_dims.json")
    ap.add_argument("--quality", type=int, default=72)
    args = ap.parse_args()

    items = json.load(open(args.items))
    photos = [p for i in items for p in i["photos"]]
    os.makedirs(args.dest, exist_ok=True)

    # Decide canvas orientation from the majority of the set, after EXIF correction.
    orients = Counter()
    for p in photos:
        with Image.open(p["path"]) as im:
            im = ImageOps.exif_transpose(im)
            orients["portrait" if im.height >= im.width else "landscape"] += 1
    canvas_w, canvas_h = PORTRAIT if orients["portrait"] >= orients["landscape"] else LANDSCAPE
    print(f"orientation mix: {dict(orients)} -> canvas {canvas_w}x{canvas_h}")

    dims, rotated = {}, 0
    for p in photos:
        with Image.open(p["path"]) as raw:
            before = raw.size
            im = ImageOps.exif_transpose(raw)   # MUST precede resize
            if im.size != before:
                rotated += 1
            im = im.convert("RGB")

            scale = min(canvas_w / im.width, canvas_h / im.height)
            new = (max(1, round(im.width * scale)), max(1, round(im.height * scale)))
            im = im.resize(new, Image.LANCZOS)

            canvas = Image.new("RGB", (canvas_w, canvas_h), "white")
            canvas.paste(im, ((canvas_w - new[0]) // 2, (canvas_h - new[1]) // 2))

            name = f"{p['uid']}.jpg"
            canvas.save(os.path.join(args.dest, name), "JPEG",
                        quality=args.quality, optimize=True)
            dims[name] = [canvas_w, canvas_h]

    os.makedirs(os.path.dirname(os.path.abspath(args.dims_out)) or ".", exist_ok=True)
    json.dump(dims, open(args.dims_out, "w"), indent=1)

    total_mb = sum(os.path.getsize(os.path.join(args.dest, n)) for n in dims) / 1e6
    print(f"normalized {len(dims)} photos ({rotated} EXIF-rotated) -> {args.dest}")
    print(f"total embedded size: {total_mb:.1f} MB")
    print(f"wrote {args.dims_out}")


if __name__ == "__main__":
    main()
