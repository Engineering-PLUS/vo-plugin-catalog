# <PROJECT> punch report pipeline

Everything needed to rebuild this report from the raw PlanGrid pull. Read this
before touching anything in here.

**Current output:** `<filename>.docx`, <N> items, <N> pages, <N> photos, <N> sheet
clips. Draft for internal review, not issued.

---

## Scope decision, read this first

The PlanGrid pull contains **<N>** items. This report covers **<which>**.
<State what was excluded and by whose direction, and whether the excluded items
are still open. If a prior report covered them, name it.>

Scope lives in exactly one place, the `SCOPE` variable, which becomes
`consolidate.py --only`:

```bash
SCOPE=11-30 bash scripts/run_pipeline.sh
```

Nothing else in the pipeline hardcodes it. Unset `SCOPE` to include every item.

---

## Working rule: the project folder is on a network share

EPLUS project folders live on `\\ep-file-01...` (a mapped drive, usually `G:`).
Large batches of small file operations against it are the single biggest time
sink in this workflow, and the most common cause of a step that looks hung.
Photo normalisation over 34 files has taken **over two minutes on the share and
2.6 seconds on local disk**, a >45x difference on 14 MB.

**Copy the pipeline to local disk, run there, copy finished artifacts back in
small batches.** Copying ~35 files back in one command has also timed out, so
split it. The share may also refuse deletes ("Operation not permitted").

**Then sync the sources back, not just the outputs.** This has already produced
one near-miss: a `drafted_items.json` edit was made in the local working copy,
the report was rendered from it, and the share's copy was never updated. The
shipped .docx and the file that supposedly generates it disagreed, and a re-run
would have silently reverted the change. `verify_report.py` now checks the
rendered document against the master JSON for exactly this reason, but the habit
matters more than the check: **sync sources back before calling the run
finished.**

---

## The source data, and where it hides

The pull is `<pull folder>/`. Two shapes to check for, every time:

1. **A `delta_<from>_to_<to>/` folder may hold the authoritative task list.**
   When a pull is taken across more than one session, the delta holds a later,
   **superset** `tasks.json` but only the **new** photo binaries, and often an
   **empty** `sheets.json`. A correct read needs the delta's tasks, **both**
   photo directories, and the base's sheets. Reading either half alone quietly
   loses either items or photos. `consolidate.py` handles this.

2. **The Task Report PDF is not in the pull.** It is exported separately from
   PlanGrid and is the ONLY source of the per-item annotated sheet clips (the
   drawing with the pin stamp). A pull's `sheet_packets/*.pdf` holds raw drawings
   with **no pin stamps**. If no Task Report is present, ask for one before
   drafting rather than discovering it mid-run.

Data quality for this pull, from the triage summary:

- <N> items in scope, <N> with an authored description, <N> photo-only
- <N> photos, all resolved to files on disk, shot <date> by <photographer>
- `room` is empty on <N>% of pins. The drawing sheet is the only location data.
  Reports print `Not recorded in PlanGrid, see sheet reference`.
- <N> of <N> items resolve to a valid sheet
- `title` is the literal string `<filler>` on <N> of <N> pins. It is a field
  marker, not content. `consolidate.py` auto-detects and drops any title
  appearing on >=50% of pins (min 3).

---

## Pipeline, in order

Run from `_pipeline/`. Node deps: `npm install docx@^9.7.1`.
Python deps: `pip install pymupdf openpyxl pillow --break-system-packages`.

Check the tooling before the first run:

```bash
bash scripts/smoke_test.sh
```

Then:

```bash
bash scripts/run_pipeline.sh
```

That runs all five steps and verifies. The individual steps, if you need one:

```bash
# 1. consolidate the pull -> the factual layer
python3 scripts/consolidate.py "<pull>" -o data/items.json --only <scope>

# 2. normalise photos (EXIF rotate + letterbox + downscale)
python3 scripts/normalize_photos.py --items data/items.json \
    --dest build/thumbs_uniform --dims-out data/thumb_dims.json

# 3. sheet clips from the PlanGrid Task Report PDF
python3 scripts/extract_sheet_clips.py "<Task Report>.pdf" \
    build/sheet_clips_jpg --items-from data/items.json \
    --dims-out build/sheet_clip_dims_jpg.json

# 4. assemble the render-ready JSON (facts + judgment)
python3 scripts/build_master.py --items data/items.json \
    --drafted data/drafted_items.json -o build/master_report_items.json

# 5. render and verify
node scripts/gen_report.js build
python3 scripts/verify_report.py build/<filename>.docx
```

`data/items.json` is **facts**, regenerated from the pull.
`data/drafted_items.json` is **judgment**, written during the drafting step.
Only the second is yours to edit by hand.

### No PDF is generated here, and the TOC uses real Word fields

These two facts are linked. Do not undo either.

**We output .docx only.** The reviewer generates the PDF from Word when markup
is finished. Word recalculates fields on open and on PDF export.

**TOC page numbers are `PAGEREF` fields**, one per item, pointing at a bookmark
on each item heading, with `features: { updateFields: true }` so Word refreshes
them on open. Ctrl+A then F9 forces it.

This replaced a two-pass render that computed page numbers by converting to PDF
with LibreOffice and harvesting them in as **static text**. **LibreOffice
paginates differently from Word**, so the harvested numbers were wrong the moment
the file opened in Word, and being plain text they never recalculated. The only
reason for that design was that a field renders blank when LibreOffice makes the
PDF. Since we no longer make the PDF, that constraint is gone.

**Consequence to be aware of:** entry *titles* are still static text, so deleting
an item in Word renumbers the headings but not the TOC labels. Page numbers
self-heal, labels do not. For anything beyond a small edit, use the review
spreadsheet and re-render.

---

## Editing the report after it is rendered

A rendered .docx is a compiled artifact. Two supported paths, both must keep
working.

**Small edits: directly in Word.** Item headings use Word's own numbering, so
deleting an item renumbers the rest automatically. Do not write the number into
the heading text. Every item is exactly one page and self-contained, so inserting
an item by hand is copy a page, paste, edit.

The PlanGrid ID is deliberately **not** in the heading. The printed item number
is presentational and will change; the PlanGrid ref is the permanent link back to
source. It is carried in `master_report_items.json` as `plangrid_ref` and shown
in the review spreadsheet.

**Reviewer comments in Word: read them back** rather than reading the document
and guessing what changed.

```bash
python3 scripts/read_comments.py <reviewed>.docx
```

Each comment is reported with the text it is anchored to and the item heading it
sits under. Resolved comments are hidden unless `--include-resolved` is passed.

**Bulk edits: the review spreadsheet.**

```bash
python3 scripts/review_sheet.py export build -o Report-Review.xlsx
#   reviewer edits the YELLOW columns only
python3 scripts/review_sheet.py import build Report-Review.xlsx
node scripts/gen_report.js build
```

Yellow = editable, grey = generated and ignored on import, so photo paths and
sheet clips cannot be corrupted by editing the sheet. `Include? = N` drops an
item, `Order` reorders, a new row with a blank PlanGrid ref inserts an item. A
timestamped `.bak.json` is written before anything changes.

---

## Rules the renderer bakes in, do not re-derive

- **The letterhead is built natively, never pasted in as a bitmap.** A
  full-page-width strip in a header starts at the *body* left margin, so it
  overhangs right and leaves dead space left. The header is a two-column table
  sized to `USABLE_W`, so it tracks the body margins at any page size and stays
  crisp at print resolution. The divider must stay a shaded paragraph, not a
  border, because LibreOffice clamps thick borders to hairlines.
- **Item descriptions are in field-report voice.** The report is written *by* the
  field engineer, describing the site. Banned from descriptions and asserted
  against in `build_master.py`: narrating the evidence ("the photograph shows",
  "not visible in the frame") and third-person self-reference ("the field
  engineer recorded"). Editor's Notes are internal and exempt.
- **The verbatim pin note is not rendered.** Quoting the engineer's own shorthand
  back at them reads as third person. It is carried as `field_note` for
  traceability and appears in the review spreadsheet. If you re-add it, also
  restore its allowance in `estimateOverheadDXA()` or the photo grid under-packs.
- **The cover is the issued EPLUS coversheet design, rebuilt natively.** Two raster
  pieces are reused as artwork because that is what they are:
  `assets/cover/cover_hero.jpg` (stock brand imagery) and
  `assets/cover/cover_bands.png` (the EP diagonal band graphic, a full-page
  transparent overlay). Both are placed as page-anchored floating images behind the
  text, at the geometry taken from the reference document: bands 8.49 x 10.98in at
  (0.00, 0.01), hero 8.53 x 6.37in at (0.00, 1.01). **The hero must be emitted
  first**, because docx derives z order from document order and the bands sit on
  top. All cover text is native and comes from `report.config.json`.
- **The client logo is per project and is not bundled.** It is the end client's
  trademark and changes every job. Drop it at
  `build/assets/cover/client_logo.png` and it renders top right; leave it out and
  the cover renders without it.
- **The cover is its own section**, with no letterhead header and no page footer.
  A "Page 1 of N" strip across the artwork reads as a mistake. Because the section
  break already starts the next page, the Table of Contents paragraph must NOT also
  carry `pageBreakBefore`, or Word emits a blank page between them.
- **The meta table is two rows: Drawing Sheet and Date Recorded.** Location was
  removed because PlanGrid's `room` is empty on every pin, so the row only ever
  printed a placeholder, which reads as noise. The Photos count went with it: the
  photos are directly below. If real location data becomes available (photo EXIF
  geotags), add the row back rather than reviving the placeholder.
- **The pin clip is rendered at double width** (about 3.17in). With no location
  data it is the only thing on the page that says where the item is. Display width
  and extraction `--zoom` must move together, or the clip just gets bigger and
  blurrier; the extractor defaults to 6x for this reason.
- **The photo grid is visibly gridded and photos are numbered.** This document
  gets edited in Word and the commonest edit is adding or swapping a photo;
  borderless cells give the reviewer nothing to aim at. Empty slots are drawn but
  carry no placeholder text, because the file is exported to PDF as-is and hint
  text would print.
- **Sheet designators are normalised `TO` to `T0`.** PlanGrid's sheet-name OCR
  reads the character after a leading T as a letter O rather than a zero at upload
  time. The upstream fix is to correct each sheet name by hand when uploading
  drawings; the report cannot rely on that having happened.
- **On-page editor instructions are red and marked DELETE PRIOR TO PRINTING.**
  Anything addressed to the person editing the file, rather than to the reader,
  must be unmistakable, because otherwise it prints in the issued PDF.
- **One item per page.** `pageBreakBefore` on each heading, rows `cantSplit`.
- **No em or en dashes, anywhere, ever.** Swept in `build_master.py`, asserted in
  `verify_report.py`. Standing EPLUS rule.
- **Image sizes are in PIXELS.** `ImageRun.transformation` wants px while
  everything else is twips. `px = Math.floor((dxa / 1440) * 96)`. Getting this
  wrong renders a 23-inch image. Hit twice historically.
- **`rowSpan` is declared once**, on the first row's cell only.
- **EXIF orientation must be applied before resize.**
- **Photos are 1.90 inch, fill-and-continue pagination.** Tuned to cut blank
  space. Do not change without asking.
- **Green is for visually distinct callouts only**, not inline bold labels.
- **Write to new filenames, never overwrite.**

## Report identity

Cover and footer strings are **not** hardcoded. They live in
`build/report.config.json`. Change them there, not in the renderer.

Two rules about that file:

- **`ep_project_no` is internal tracking and is never rendered.** It is there so
  runs stay traceable on our side. It must not appear anywhere a client, GC or
  subcontractor reads, the cover included. `verify_report.py` asserts it is absent
  from the document text and fails the build if it is not.
- **The issuance date is asked for, never inferred.** It is a contractual fact
  about when the report goes out, decided by the reviewer, and it routinely
  differs from both the walk date and the compile date. A draft that is not yet
  being issued does not get a guessed date.

## Precedent

Item wording is checked against the EPLUS punch corpus via the
`eplus-punch-engine` tools, using the `punch` skill. Search to find candidates,
then `get_punch_item` to read the exact wording before citing it.

<Record this project's precedent coverage here: how many items carry a citation,
and any theme the corpus could not cover.>
