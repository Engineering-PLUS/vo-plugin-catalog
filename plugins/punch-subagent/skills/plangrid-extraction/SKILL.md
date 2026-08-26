---
name: plangrid-punch-extraction
description: >
  Extract drawings, photos, and marked-up views from PlanGrid-generated punch
  report PDFs. Use whenever a punch report, punch list, field progress report,
  or site inspection PDF created with PlanGrid is shared in chat (footer says
  "Created with PlanGrid") and the task involves pulling out images, the full
  drawing behind a markup clip, correctly-oriented photos, or the rendered
  view of a sheet. Also use when embedded images from any PlanGrid PDF come
  out rotated or as a whole drawing instead of the visible clip.
---

# PlanGrid Punch Report Extraction

PlanGrid punch PDFs hide far more data than the page displays. Three
non-obvious storage behaviors matter; get all three right or extractions will
be rotated, cropped-wrong, or missing markup.

## Dependencies

```bash
pip install pypdf pillow pypdfium2
```

- `pypdf` + `pillow` — embedded-image extraction and rotation fixing
- `pypdfium2` — rendering pages as displayed (the only way to see markup)

## How PlanGrid stores data (the three traps)

### 1. The FULL drawing is embedded on every issue page

An issue page that displays a small clip of a drawing around a markup pin
actually embeds the **entire original drawing bitmap at full resolution**
(e.g. 2100x1500). The page's content stream scales/clips it so only the pin
area is visible. Extracting the raw image XObject therefore yields the whole
drawing — strictly more information than the page shows.

- The full drawing is normally the **largest embedded image on the page**.
- The same drawing bitmap is **re-embedded on every issue page pinned to
  it** — dedupe by content hash (`sha1(img.data)`) if that matters.

### 2. Markup lives in vector annotations, not the bitmap

Pins, clouds, and issue tags are PDF `/Annots` drawn over the page. They are
NOT part of any embedded image. The only way to obtain the marked-up view a
human sees is to **render the page**:

```python
import pypdfium2 as pdfium
pdf = pdfium.PdfDocument("report.pdf")
page = pdf[page_index]
img = page.render(scale=2.0, draw_annots=True).to_pil()  # 2.0 = 144 DPI
img.convert("RGB").save("render.jpg", quality=85)
```

So each sheet has two complementary visuals: the raw embedded drawing (full
extent, no markup) and the render (clipped view, markup included). Keep both.

### 3. Photos are stored camera-native and rotated at DISPLAY time

Site photos are embedded in the orientation the camera saved (usually
512x384 landscape) with **no EXIF orientation and no page `/Rotate`**. The
rotation to the displayed portrait view exists only in the page's
transformation matrix (`cm`) at the moment the image is drawn (`Do`). A raw
extraction is silently rotated 90° from what the page shows.

Recover the rotation with a small content-stream state machine and bake it
into the saved file:

```python
import io, math, re
from pathlib import Path
from pypdf import PdfReader
from PIL import Image

TOKEN = re.compile(r"(?P<q>\bq\b)|(?P<Q>\bQ\b)|"
                   r"(?P<cm>([-\d.]+\s+){6}cm\b)|(?P<Do>/(\w+)\s+Do\b)")

def _mul(m, n):
    a1,b1,c1,d1,e1,f1 = m; a2,b2,c2,d2,e2,f2 = n
    return [a1*a2+b1*c2, a1*b2+b1*d2, c1*a2+d1*c2, c1*b2+d1*d2,
            e1*a2+f1*c2+e2, e1*b2+f1*d2+f2]

def image_rotations(page):
    """{xobject_name: 0|90|180|270} rotation applied at draw time."""
    content = page.get_contents().get_data().decode("latin-1")
    rot, stack, ctm = {}, [], [1.0,0,0,1.0,0,0]
    for m in TOKEN.finditer(content):
        if m.group("q"): stack.append(ctm[:])
        elif m.group("Q"): ctm = stack.pop() if stack else [1.0,0,0,1.0,0,0]
        elif m.group("cm"):
            ctm = _mul([float(x) for x in m.group("cm").split()[:6]], ctm)
        elif m.group("Do"):
            name = m.group("Do").split()[0].lstrip("/")
            rot[name] = round(math.degrees(math.atan2(ctm[1], ctm[0]))/90)*90 % 360
    return rot

# ctm angle -> PIL transpose reproducing the DISPLAYED orientation
# (PDF y-axis points up, image y-down flips apparent direction:
#  ctm 270 means "shown rotated 90 deg clockwise" -> PIL ROTATE_270)
PIL_ROT = {90: Image.Transpose.ROTATE_90, 180: Image.Transpose.ROTATE_180,
           270: Image.Transpose.ROTATE_270}

def extract_page_images(page, out_dir: Path, min_dim=200):
    rotations = image_rotations(page)
    n = 0
    for img in page.images:
        pil = img.image
        if pil is None or pil.width < min_dim or pil.height < min_dim:
            continue  # skips logos/icons; header banners fail min_dim too
        angle = rotations.get(Path(img.name).stem, 0)
        n += 1
        if angle in PIL_ROT:
            pil = pil.transpose(PIL_ROT[angle])
            buf = io.BytesIO()
            pil.convert("RGB").save(buf, format="JPEG", quality=90)
            (out_dir / f"img_{n:02d}.jpg").write_bytes(buf.getvalue())
        else:  # unrotated: keep original bytes, no recompression
            ext = (Path(img.name).suffix or ".jpg").lower()
            (out_dir / f"img_{n:02d}{ext}").write_bytes(img.data)
    return n
```

## Page anatomy (consistent across PlanGrid punch reports)

- Header: project code (e.g. `Stack - NVA05A (NVA13) - 26991`) + company logo
- `#<issue number> <location code>` (e.g. `#680 IDF-NVA13:1:4`)
- `Status` (Open/Closed) and `Sheet` (drawing number, e.g. `T02-01D`)
- `Description` — the issue text; the highest-value retrieval content
- `Photos` — the site photos (trap 3) and/or the drawing clip (traps 1-2)
- Footer: `Prepared by <author>`, page number, `Created with PlanGrid`

## The per-item annotated sheet clip (Task Report PDF only)

Distinct from — and fiddlier than — the three photo traps above. The clip
showing a drawing with the item's pin stamp exists **only in the PlanGrid
Task Report PDF export**. `sheet_packets/*.pdf` from an API pull contains the
raw drawings with **no pin stamps**; do not look there.

Three traps, all field-hit:

1. **Skip the Table of Contents.** The first ~3 pages repeat every item
   heading with dot leaders and page numbers, so a naive text search for an
   item's `#N` heading matches the ToC entry before the real block.
2. **The reported image bbox is bigger than what is visible.** A clip path in
   the content stream is not exposed through `get_image_info`, so cropping to
   the reported bounds captures far too much. Anchor the crop off the
   position of the "Sheet" text label instead — an empirically tuned offset,
   not a derivable one.
3. **Clips overflow to the next page.** When an item's block sits near the
   bottom of a page its clip is pushed onto the following page with no
   repeated heading. Detect it (no image near the expected crop region) and
   fall back to taking the image off the next page.

Also note: photos exported through the **API** carry EXIF orientation, so
trap 3 above applies to them too — `ImageOps.exif_transpose()` before any
resize, not just for images pulled out of PDFs.

## Caveats

- Filter images under ~200 px on either side: repeated logos and icons.
- Some older punch reports are plain Word exports (footer has no PlanGrid
  mark): none of the traps apply; images extract normally.
- `PdfReader(..., strict=False)` — PlanGrid files often have minor spec
  violations that strict mode rejects.
- pypdf emits harmless console warnings on some pages; ignore them.
