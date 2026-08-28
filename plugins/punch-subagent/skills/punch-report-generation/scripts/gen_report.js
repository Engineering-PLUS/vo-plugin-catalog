/*
 * gen_report_v7.js, EPLUS punch report generator (v0.7 rule set)
 *
 * Changes from v0.6, per Victor's second pass of comments:
 *   1. Letterhead: reuses the EPLUS Technology System Punch List letterhead from
 *      Legacy Walk Thru Report as a full width image header on every page. No more
 *      hand rolled bar with an icon + right aligned title. Only the header is used;
 *      the legacy footer artwork is not carried over.
 *   2. Summary section removed. Replaced with a Word Table of Contents (real TOC field,
 *      updates on open) built from the item headings.
 *   3. PlanGrid ref meta row removed. plangrid_ref is retained in data for our own
 *      traceability but is NEVER rendered anywhere the contractor sees.
 *   4. "Reviewer Flag" renamed to "Editor's Note" everywhere.
 *   5. Zero em/en dashes anywhere in this file OR the data (data is pre swept).
 *   6. Corrective Action absorbs the field engineer's walk note cross reference; the
 *      separate Cross reference block is gone. Merge already done upstream in
 *      precedent_merged.json and materialised into master_report_items_v7.json.
 *   7. Photo size trimmed to close the dead space that showed up at the bottom of
 *      items with a short write up: PHOTO_W_DXA drops from 2.50" to 2.10", which also
 *      reclaims horizontal room in the meta table for the pin clip.
 *
 * GOTCHAS carried over from v0.6:
 *   - ImageRun.transformation.{width,height} are PIXELS while everything else is twips.
 *   - TableCell rowSpan is declared ONCE on the first row's cell.
 *   - Always render to a NEW filename; the scratch workspace refuses overwrite.
 */
const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  WidthType, BorderStyle, ShadingType, ImageRun, AlignmentType,
  Header, Footer, PageNumber, VerticalAlign, LevelFormat, HeadingLevel,
  TabStopType, LeaderType, Tab, Bookmark, InternalHyperlink, PageReference,
  HorizontalPositionRelativeFrom, VerticalPositionRelativeFrom, TextWrappingType,
  TableAnchorType, OverlapType, ImportedXmlComponent,
} = require('docx');

const BUILD = process.argv[2] || path.join(__dirname, '..');
const CFG = JSON.parse(fs.readFileSync(path.join(BUILD, 'report.config.json')));
const OUT = process.argv[3] || path.join(BUILD, CFG.output_filename);

const master = JSON.parse(fs.readFileSync(path.join(BUILD, CFG.master_file || 'master_report_items.json')));
const clipDims = JSON.parse(fs.readFileSync(path.join(BUILD, 'sheet_clip_dims_jpg.json')));
const PHOTO_DIR = path.join(BUILD, 'thumbs_uniform');

// ---------------------------------------------------------------- page + brand constants
const PAGE_W = 12240, PAGE_H = 15840;
const MARGIN_LR = 1080;
const MARGIN_TOP = 1800;                              // 1.25", leaves room for the letterhead
const MARGIN_BOTTOM = 1080;
const HEADER_MARGIN = 360;                            // 0.25" from paper edge to letterhead
const USABLE_W = PAGE_W - 2 * MARGIN_LR;              // 10080 dxa = 7.0"
const CONTENT_H = PAGE_H - MARGIN_TOP - MARGIN_BOTTOM - 400;

const BLUE = '44546A';                                // legacy letterhead blue
const DARKGREY = '58595B';
const LIGHTGREY = 'A6A6A5';
const BLUE_TINT = 'E7E9EE';
const ALERT_RED = 'B00000';
const RED_TINT = 'FBE9E9';
const FONT = 'Arial';

// Letterhead is rebuilt natively from its component assets, NOT pasted in as a
// bitmap strip. The strip approach was wrong twice: it is sized to the full page
// (8.0in) but a header paragraph begins at the BODY left margin (0.75in), so it
// overhung the right edge and left dead space on the left. A native table sized to
// USABLE_W lines up with the body margins exactly, at any page size, and stays
// crisp at print resolution. Do not go back to pasting letterhead_strip.png.
const EP_LOGO = fs.readFileSync(path.join(BUILD, 'assets/logos/ep_logo.jpg'));
const EP_URL = fs.readFileSync(path.join(BUILD, 'assets/logos/ep_url.png'));
// native letterhead geometry, all anchored to USABLE_W so it tracks the body margins
const LH_LOGO_W = 2520;                               // ep_logo.jpg  700x141
const LH_LOGO_H = Math.round(LH_LOGO_W * 141 / 700);
const LH_URL_W = 1560;                                // ep_url.png  1416x191
const LH_URL_H = Math.round(LH_URL_W * 191 / 1416);
const LH_LEFT_W = 4600;
const LH_RIGHT_W = USABLE_W - LH_LEFT_W;

// ------------------------------------------------------------------ uniform photo sizing
// Photos live on one 700 x 933 (3:4) canvas so each embedded image is exactly the same size.
// v0.7 shrinks the render width by 0.40" from v0.6 (2.50 -> 2.10). Effect measured across
// all 50 items in this set:
//   2.50" -> 33/50 items self contained, 81 pages
//   2.25" -> 38/50 items self contained, 78 pages
//   2.10" -> 41/50 items self contained, 76 pages   <-- chosen, closes the dead space
//   1.90" -> 42/50 items self contained, 76 pages   (return diminishes below ~2.1")
// If the field set or the text blocks change materially, re run scripts/tune_layout.js.
const PHOTO_COLS = 2;
const PHOTO_W_DXA = 2736;                              // 1.90"
const PHOTO_H_DXA = Math.round(PHOTO_W_DXA * 933 / 700); // 3:4 canvas => 2.53"
const PHOTO_ROW_H = PHOTO_H_DXA + 300;                 // caption + cell pad
const PHOTO_COL_W = Math.floor(USABLE_W / PHOTO_COLS);
const CONT_HEADER_H = 620;

// Meta table is deliberately minimal: Drawing Sheet and Date Recorded, nothing else.
// The Location row was removed because PlanGrid's `room` is empty on every pin, so it
// only ever printed a placeholder, which reads as noise rather than information. The
// Photos count row went with it: the photos are visible directly below it. If real
// location data ever becomes available (photo EXIF geotags, say), add the row back
// rather than reviving the placeholder.
//
// The pin clip column is DOUBLE its previous width. With no location data, the clip is
// the only thing on the page that says where this item is, so it earns the space.
const META_LABEL_W = 1650;
const CLIP_COL_W = 4800;
const META_VALUE_W = USABLE_W - META_LABEL_W - CLIP_COL_W;
const CLIP_IMG_W = CLIP_COL_W - 240;

const dxaToPx = (dxa) => Math.floor((dxa / 1440) * 96);

function fmtTimestamp(title) {
  const m = String(title || '').match(/^(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})/);
  if (!m) return title || '';
  const [, yyyy, mm, dd, HH, MM] = m;
  return `${mm}/${dd}/${yyyy} ${HH}:${MM}`;
}

function run(text, opts = {}) {
  return new TextRun({ text, font: FONT, ...opts });
}

function noBorders() {
  const none = { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' };
  return { top: none, bottom: none, left: none, right: none };
}

function thinBorders(color = LIGHTGREY) {
  const b = { style: BorderStyle.SINGLE, size: 4, color };
  return { top: b, bottom: b, left: b, right: b };
}

function estimateTextHeightDXA(text, sizeHalfPt, widthDXA) {
  if (!text) return 0;
  const pt = sizeHalfPt / 2;
  const charsPerLine = Math.max(15, Math.floor((widthDXA / 20) / (0.5 * pt)));
  const lines = Math.max(1, Math.ceil(String(text).length / charsPerLine));
  return lines * Math.round(pt * 23);
}

// --------------------------------------------------------------------------- meta table
function sheetClipPathFor(item) {
  const pg = item.plangrid_ref.replace('#', '');
  return path.join(BUILD, 'sheet_clips_jpg', `item_${pg}.jpg`);
}

function metaRowsData(item) {
  // PlanGrid ref is NOT rendered here. It is internal traceability only.
  // Two rows only. See the CLIP_COL_W comment for why Location and Photos are gone.
  const shots = (item.photo_titles || []).map(fmtTimestamp).filter(Boolean).sort();
  const recorded = shots.length ? shots[0].split(' ')[0] : 'N/A';
  return [
    ['Drawing Sheet', item.sheet_display || 'N/A'],
    ['Date Recorded', recorded],
  ];
}

function metaTable(item) {
  const rowsData = metaRowsData(item);
  const clipPath = sheetClipPathFor(item);

  let clipCellChildren;
  if (fs.existsSync(clipPath)) {
    const clipBase = path.basename(clipPath);
    const [cw, ch] = clipDims[clipBase] || [800, 800];
    const clipH = Math.round(CLIP_IMG_W * (ch / cw));
    clipCellChildren = [
      new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [new ImageRun({
          type: 'jpg',
          data: fs.readFileSync(clipPath),
          transformation: { width: dxaToPx(CLIP_IMG_W), height: dxaToPx(clipH) },
        })],
      }),
    ];
  } else {
    clipCellChildren = [new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [run('(no pin clip)', { italics: true, size: 15, color: LIGHTGREY })],
    })];
  }

  const rows = rowsData.map(([label, value], i) => {
    const cells = [
      new TableCell({
        width: { size: META_LABEL_W, type: WidthType.DXA },
        shading: { type: ShadingType.CLEAR, color: 'auto', fill: BLUE_TINT },
        margins: { top: 60, bottom: 60, left: 100, right: 100 },
        borders: thinBorders(),
        children: [new Paragraph({ children: [run(label, { bold: true, size: 19, color: BLUE })] })],
      }),
      new TableCell({
        width: { size: META_VALUE_W, type: WidthType.DXA },
        margins: { top: 60, bottom: 60, left: 100, right: 100 },
        borders: thinBorders(),
        children: [new Paragraph({ children: [run(String(value), { size: 19, color: DARKGREY })] })],
      }),
    ];
    if (i === 0) {
      cells.push(new TableCell({
        width: { size: CLIP_COL_W, type: WidthType.DXA },
        rowSpan: rowsData.length,
        verticalAlign: VerticalAlign.CENTER,
        margins: { top: 60, bottom: 60, left: 60, right: 60 },
        borders: thinBorders(),
        children: clipCellChildren,
      }));
    }
    return new TableRow({ cantSplit: true, children: cells });
  });

  return new Table({
    width: { size: USABLE_W, type: WidthType.DXA },
    columnWidths: [META_LABEL_W, META_VALUE_W, CLIP_COL_W],
    rows,
  });
}

// -------------------------------------------------------------------------- photo grid
// The photo grid is a VISIBLE grid, on purpose. This report gets edited in Word after
// it is generated, and the single most common edit is adding or swapping a photo. With
// borderless cells there is nothing to aim at: the reviewer cannot see where a photo
// would land. Hairline cell borders make the slots legible, and the numbering gives
// every photo a name that can be cited in a comment or a covering email.
//
// Empty slots are drawn but carry NO placeholder text, because this document is
// exported to PDF as-is and any hint text would print in the issued copy.
function photoCaption(item, idx) {
  const stamp = fmtTimestamp(item.photo_titles[idx]);
  return `Photo ${idx + 1}${stamp ? '  |  ' + stamp : ''}`;
}

function photoCell(item, idx) {
  const base = path.basename(item.photo_paths[idx]);
  const file = path.join(PHOTO_DIR, base);
  const children = [];
  try {
    children.push(new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new ImageRun({
        type: 'jpg',
        data: fs.readFileSync(file),
        transformation: { width: dxaToPx(PHOTO_W_DXA), height: dxaToPx(PHOTO_H_DXA) },
      })],
    }));
  } catch (e) {
    children.push(new Paragraph({ children: [run('[image unavailable]', { italics: true, size: 16 })] }));
  }
  children.push(new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [run(photoCaption(item, idx), { size: 15, color: LIGHTGREY })],
  }));
  return new TableCell({
    width: { size: PHOTO_COL_W, type: WidthType.DXA },
    margins: { top: 40, bottom: 40, left: 40, right: 40 },
    borders: thinBorders(),
    children,
  });
}

// Sized to match a filled cell so the grid stays square when a row is part full, and
// so a pasted photo lands in a slot of the right height rather than growing the row.
function emptyCell() {
  return new TableCell({
    width: { size: PHOTO_COL_W, type: WidthType.DXA },
    margins: { top: 40, bottom: 40, left: 40, right: 40 },
    borders: thinBorders(),
    verticalAlign: VerticalAlign.CENTER,
    // An empty cell holding an empty paragraph collapses to a single text line,
    // so the slot is invisible as a paste target. Give it the height of a
    // filled cell.
    children: [new Paragraph({
      spacing: { before: Math.round(PHOTO_H_DXA / 2), after: Math.round(PHOTO_H_DXA / 2) },
      children: [run('')],
    })],
  });
}

function emptyPhotoRow() {
  return new Table({
    width: { size: USABLE_W, type: WidthType.DXA },
    columnWidths: Array(PHOTO_COLS).fill(PHOTO_COL_W),
    rows: [new TableRow({
      cantSplit: true,
      children: Array.from({ length: PHOTO_COLS }, emptyCell),
    })],
  });
}

function photoTable(item, start, end) {
  const rows = [];
  for (let i = start; i < end; i += PHOTO_COLS) {
    const cells = [];
    for (let c = 0; c < PHOTO_COLS; c++) {
      cells.push(i + c < end ? photoCell(item, i + c) : emptyCell());
    }
    rows.push(new TableRow({ cantSplit: true, children: cells }));
  }
  return new Table({
    width: { size: USABLE_W, type: WidthType.DXA },
    columnWidths: Array(PHOTO_COLS).fill(PHOTO_COL_W),
    rows,
  });
}

// ------------------------------------------------------------------------ item overhead
const NOTE_SIZE = 17;

function estimateOverheadDXA(item) {
  let h = 400;
  h += estimateTextHeightDXA(item.title, 26, USABLE_W - 1200);

  const textRows = metaRowsData(item)
    .reduce((s, [, v]) => s + estimateTextHeightDXA(String(v), 19, META_VALUE_W) + 100, 0);
  const clipBase = path.basename(sheetClipPathFor(item));
  const [cw, ch] = clipDims[clipBase] || [800, 800];
  const clipH = Math.round(CLIP_IMG_W * (ch / cw)) + 280;
  h += Math.max(textRows, clipH) + 100;

  h += 300 + estimateTextHeightDXA(item.description, 20, USABLE_W) + 80;
  h += 300 + estimateTextHeightDXA(item.corrective_action, 20, USABLE_W) + 80;
  // An item with no photos now renders one empty grid row, so reserve it --
  // unless photo_mode "none" says no photos apply to this item at all.
  if (!item.photo_paths.length && item.photo_mode !== 'none') h += PHOTO_ROW_H;
  // no allowance for jim_original_text: that block is no longer rendered (see itemSection)
  if (item.editor_note || item.precedent_note) {
    if (item.editor_note) h += estimateTextHeightDXA(item.editor_note, NOTE_SIZE, USABLE_W - 400) + 60;
    if (item.precedent_note) h += estimateTextHeightDXA(item.precedent_note, NOTE_SIZE, USABLE_W - 400) + 60;
    h += 280;
  }
  h += 300;
  return h;
}

function labelPara(text) {
  return new Paragraph({
    keepNext: true,
    spacing: { after: 50 },
    children: [run(text, { bold: true, size: 21, color: BLUE })],
  });
}

function bodyPara(text) {
  return new Paragraph({
    keepNext: true, keepLines: true,
    spacing: { after: 100 },
    children: [run(text, { size: 20, color: DARKGREY })],
  });
}

/**
 * Editor's Note (formerly Reviewer Flag): boxed red callout, internal only.
 * Carries: the note text, then optional supporting EPLUS precedent basis.
 */
function editorNoteBlock(lines) {
  return new Table({
    width: { size: USABLE_W, type: WidthType.DXA },
    columnWidths: [USABLE_W],
    rows: [new TableRow({
      cantSplit: true,
      children: [new TableCell({
        width: { size: USABLE_W, type: WidthType.DXA },
        shading: { type: ShadingType.CLEAR, color: 'auto', fill: RED_TINT },
        margins: { top: 90, bottom: 90, left: 140, right: 140 },
        borders: {
          top: { style: BorderStyle.SINGLE, size: 4, color: ALERT_RED },
          bottom: { style: BorderStyle.SINGLE, size: 4, color: ALERT_RED },
          left: { style: BorderStyle.SINGLE, size: 18, color: ALERT_RED },
          right: { style: BorderStyle.SINGLE, size: 4, color: ALERT_RED },
        },
        children: [
          new Paragraph({
            spacing: { after: 30 },
            children: [run("EDITOR'S NOTE, internal only, delete before issuing", { bold: true, size: 18, color: ALERT_RED })],
          }),
          ...lines.map(([label, text]) => new Paragraph({
            spacing: { after: 30 },
            children: [
              run(`${label}: `, { bold: true, size: 18, color: ALERT_RED }),
              run(text, { size: 18, color: ALERT_RED }),
            ],
          })),
        ],
      })],
    })],
  });
}

// ------------------------------------------------------------------------- item section
function itemSection(item) {
  const children = [];
  const n = item.photo_paths.length;

  // Item heading. Uses Heading 1 style so the Word TOC picks it up automatically, AND uses
  // Word's native numbering so deleting an item renumbers the rest.
  children.push(new Paragraph({
    heading: HeadingLevel.HEADING_1,
    numbering: { reference: 'punch-items', level: 0 },
    pageBreakBefore: true,
    keepNext: true,
    spacing: { before: 0, after: 120 },
    children: [new Bookmark({
      id: bookmarkFor(item),
      children: [run(item.title, { bold: true, size: 26, color: BLUE })],
    })],
  }));

  children.push(metaTable(item));
  children.push(new Paragraph({ text: '', spacing: { after: 80 }, keepNext: true }));

  children.push(labelPara('Item Description'));
  children.push(bodyPara(item.description || '(no description available)'));

  children.push(labelPara('Corrective Action'));
  children.push(bodyPara(item.corrective_action));

  // The verbatim pin note is NOT rendered. This report is written BY the field
  // engineer, so quoting their own note back at them reads as third person. The
  // text is still carried on the record (field_note in data/drafted_items.json and
  // jim_original_text here) for traceability and for the review spreadsheet.

  const internal = [];
  if (item.editor_note) internal.push(['Note', item.editor_note]);
  if (item.precedent_note) internal.push(['EPLUS precedent basis', item.precedent_note]);
  if (internal.length) {
    children.push(editorNoteBlock(internal));
    children.push(new Paragraph({ text: '', spacing: { after: 60 }, keepNext: true }));
  }

  // Photo pagination.
  // Rule for small sets (n <= 4): always try to place them all on the item page. Word's
  // pagination will either fit them or push the whole photo block to the following page,
  // which reads as a natural page break. Do NOT use keepNext on the "Photos (n)" label,
  // so it does not drag the photo table forward and force a "Photos (n), see following
  // page" ghost. A page break, if forced, is clean: whole block moves together.
  // Rule for large sets (n > 4): fill whatever room is left on the item page (down to
  // one row of photos if that is all that will fit), then spill onto headed continuation
  // pages. This mirrors the v0.6 behavior for the 13, 14, and 21 photo items.
  const remaining = CONTENT_H - estimateOverheadDXA(item);
  const rowsOnFirst = Math.max(0, Math.floor(remaining / PHOTO_ROW_H));
  const rowsPerCont = Math.max(1, Math.floor((CONTENT_H - CONT_HEADER_H) / PHOTO_ROW_H));
  const GRID = PHOTO_COLS * 2;
  const capacityFirst = rowsOnFirst * PHOTO_COLS;
  // Priority is "no blank space". For every item, fill the room on the item page with as
  // many complete 2-column rows as will fit, then spill the rest onto headed continuation
  // pages. Every page still reads as a clean 2-column grid; a 4-photo item that will not
  // fit as a full 2x2 alongside the write-up shows 2 photos on the item page and 2 on the
  // continuation page rather than blanking out the item page. n <= 2 special-cases to
  // "always try" since Word can push the whole label + row block when it is really tight.
  const firstCount = n === 0 ? 0
    : n <= PHOTO_COLS ? n
    : Math.max(0, Math.min(n, capacityFirst));

  // photo_mode "none" (set during the wording review) means no photos apply to
  // this item: no label, no grid, nothing to paste into. Any other value on a
  // photo-less item renders the blank paste-target grid below.
  const suppressPhotos = n === 0 && item.photo_mode === 'none';

  if (!suppressPhotos) {
    children.push(new Paragraph({
      spacing: { after: 60 },
      // No count in the label. The count goes stale the moment anyone adds or
      // removes a photo in Word, nothing downstream reads it, and the photos are
      // visible immediately below. Standing rule, not a per-report tweak.
      children: [run(
        firstCount >= n ? 'Photos'
          : firstCount === 0 ? 'Photos, see following page'
          : 'Photos',
        { bold: true, size: 20, color: BLUE })],
    }));

    // An item with no photos still gets one empty row. Pins logged without a
    // photo are the ones most likely to have one added by hand later, so the slot
    // has to be there to paste into.
    children.push(n === 0 ? emptyPhotoRow() : photoTable(item, 0, firstCount));
  }

  let idx = firstCount;
  while (idx < n) {
    const end = Math.min(n, idx + rowsPerCont * PHOTO_COLS);
    children.push(new Paragraph({
      pageBreakBefore: true,
      keepNext: true,
      spacing: { after: 40 },
      children: [
        run(`Item ${item.display_number} (continued): `, { bold: true, size: 22, color: BLUE }),
        run(item.title, { bold: true, size: 22, color: BLUE }),
      ],
    }));
    children.push(new Paragraph({
      keepNext: true,
      spacing: { after: 80 },
      border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: LIGHTGREY, space: 2 } },
      children: [run('Photos (continued)', { size: 17, color: DARKGREY })],
    }));
    children.push(photoTable(item, idx, end));
    idx = end;
  }

  children.push(new Paragraph({
    spacing: { before: 160, after: 0 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: LIGHTGREY, space: 1 } },
    children: [run('')],
  }));
  return children;
}

// --------------------------------------------------------------- cover + TOC (no summary)
const withPrecedent = master.filter(m => m.precedent_note).length;
const editorNoted = master.filter(m => m.editor_note).length;
const totalPhotos = master.reduce((s, m) => s + m.photo_paths.length, 0);

// ------------------------------------------------------------------------------- cover
// Rebuilt from the issued STACK coversheet (Bldg A), which is the design EPLUS has been
// putting on these reports. The two raster pieces ARE the artwork and are reused as
// shipped: cover_hero.jpg is stock brand imagery and cover_bands.png is the EP diagonal
// band graphic, a full-page transparent overlay. Everything else, all the text and all
// the geometry, is native, so it tracks page size and is editable in Word.
//
// Geometry is taken from the reference document's own anchors, converted to page
// relative offsets:
//     bands   8.49 x 10.98in at (0.00, 0.01)   full bleed, drawn OVER the hero
//     hero    8.53 x  6.37in at (0.00, 1.01)   leaves a white band at top for the logos
// The reference gives bands a higher relativeHeight than the hero, so the bands sit on
// top. docx derives z order from document order, so the hero must be emitted FIRST.
//
// The client logo is deliberately NOT bundled with this skill: it is the end client's
// trademark and it changes per project. Supply it per project as
// build/assets/cover/client_logo.png and it renders top right; omit it and the cover
// simply renders without it.
const EMU_PER_IN = 914400;
const inEMU = (n) => Math.round(n * EMU_PER_IN);
const INCLUDE_COVER = CFG.include_cover !== false;
const COVER_DIR = path.join(BUILD, 'assets/cover');
// 0.25in from the paper edge, the same inset as the body pages' letterhead
// (HEADER_MARGIN), so the cover logos and the interior letterhead line up.
const COVER_LOGO_Y = HEADER_MARGIN;

function coverBackgroundRuns() {
  const runs = [];
  const layers = [
    { file: 'cover_hero.jpg', type: 'jpg', w: 8.53, h: 6.37, x: 0.0, y: 1.01 },
    { file: 'cover_bands.png', type: 'png', w: 8.49, h: 10.98, x: 0.0, y: 0.01 },
  ];
  for (const l of layers) {
    const p = path.join(COVER_DIR, l.file);
    if (!fs.existsSync(p)) continue;
    runs.push(new ImageRun({
      type: l.type,
      data: fs.readFileSync(p),
      transformation: { width: Math.round(l.w * 96), height: Math.round(l.h * 96) },
      floating: {
        horizontalPosition: { relative: HorizontalPositionRelativeFrom.PAGE, offset: inEMU(l.x) },
        verticalPosition: { relative: VerticalPositionRelativeFrom.PAGE, offset: inEMU(l.y) },
        behindDocument: true,
        allowOverlap: true,
        wrap: { type: TextWrappingType.NONE },
      },
    }));
  }
  return runs;
}

function coverLogoRow() {
  const clientLogo = path.join(COVER_DIR, 'client_logo.png');
  const left = [
    new Paragraph({
      spacing: { before: 0, after: 60 },
      children: [new ImageRun({
        type: 'jpg', data: EP_LOGO,
        transformation: { width: dxaToPx(LH_LOGO_W), height: dxaToPx(LH_LOGO_H) },
      })],
    }),
    new Paragraph({
      spacing: { before: 0, after: 0 },
      children: [new ImageRun({
        type: 'png', data: EP_URL,
        transformation: { width: dxaToPx(LH_URL_W), height: dxaToPx(LH_URL_H) },
      })],
    }),
  ];
  const right = fs.existsSync(clientLogo)
    ? [new Paragraph({
        alignment: AlignmentType.RIGHT,
        children: [new ImageRun({
          type: 'png', data: fs.readFileSync(clientLogo),
          transformation: { width: dxaToPx(2900), height: dxaToPx(Math.round(2900 * 0.225)) },
        })],
      })]
    : [new Paragraph({ text: '' })];

  // Page anchored, like the other two cover blocks, so the logo row sits at a known
  // distance from the paper edge instead of wherever the section's top margin and the
  // image heights happen to put it. COVER_LOGO_Y matches HEADER_MARGIN, the body pages'
  // letterhead inset, so the cover and the interior pages start at the same height.
  return new Table({
    float: {
      horizontalAnchor: TableAnchorType.PAGE,
      verticalAnchor: TableAnchorType.PAGE,
      absoluteHorizontalPosition: MARGIN_LR,
      absoluteVerticalPosition: COVER_LOGO_Y,
      overlap: OverlapType.OVERLAP,
    },
    width: { size: USABLE_W, type: WidthType.DXA },
    columnWidths: [LH_LEFT_W, LH_RIGHT_W],
    borders: noBorders(),
    rows: [new TableRow({
      cantSplit: true,
      children: [
        new TableCell({
          width: { size: LH_LEFT_W, type: WidthType.DXA }, borders: noBorders(),
          margins: { top: 0, bottom: 0, left: 0, right: 0 },
          verticalAlign: VerticalAlign.TOP, children: left,
        }),
        new TableCell({
          width: { size: LH_RIGHT_W, type: WidthType.DXA }, borders: noBorders(),
          margins: { top: 0, bottom: 0, left: 0, right: 0 },
          verticalAlign: VerticalAlign.TOP, children: right,
        }),
      ],
    })],
  });
}

// Cover text blocks are ABSOLUTELY POSITIONED against the page, not pushed down the
// page with spacer paragraphs. The first attempt used spacers and the text landed on
// the wrong part of the artwork: the diagonal band runs down the LEFT side for almost
// the full page, so left aligned blocks near the bottom sat on dark blue and were
// unreadable. Stacked spacers also depend on how tall the logo images and each line of
// text happen to render, which is not knowable here.
//
// The reference coversheet solves this with positioned text boxes, so this does the
// same, using floating tables anchored to the page. Positions are now a stated fact
// about the artwork rather than the result of accumulated guesses:
//
//   TITLE  x 0.75in  y 4.75in  w 2.20in   over the solid dark band, text is WHITE
//   INFO   x 3.54in  y 7.95in  w 4.21in   right of the diagonal, white panel, DARK text
//
// These are measured, not eyeballed. The band is a DIAGONAL, so the usable dark width
// shrinks steadily down the page: sampling the composited artwork gives 3.65in of safe
// width at y=4.25 but only 2.35in by y=7.00. A tall block therefore runs off the band at
// its BOTTOM corner, which is exactly what went wrong first time round: the title was
// placed lower and wider and measured 1.7:1 against a pale #c5c8d9, i.e. unreadable.
//
// The position below is the LOWEST one, closest to the original composition, at which
// white text holds 4.5:1 across the whole box. Measured worst case here is 4.8:1.
// Widening or lowering the box trades directly against contrast:
//     w 2.60in -> lowest y 3.95in     w 2.20in -> lowest y 4.75in
//     w 2.40in -> lowest y 4.35in     w 2.00in -> lowest y 5.15in
// If cover_subtitle grows much beyond "Building A" it will wrap, making the box taller
// and pushing its bottom corner into the pale zone. Re-run the contrast sampling in
// that case rather than nudging values by eye.
//
// The info panel is explicitly filled white. The artwork behind it is already white
// (verified by sampling), so the fill is invisible here and matches the reference; if a
// future artwork revision changes that, the fill is what keeps the text readable.
const COVER_TITLE_X = 1080, COVER_TITLE_Y = 6836, COVER_TITLE_W = 3168;
const COVER_INFO_X = 5100, COVER_INFO_Y = 11448, COVER_INFO_W = 6060;

function floatingBlock(x, y, w, children, fill) {
  return new Table({
    float: {
      horizontalAnchor: TableAnchorType.PAGE,
      verticalAnchor: TableAnchorType.PAGE,
      absoluteHorizontalPosition: x,
      absoluteVerticalPosition: y,
      overlap: OverlapType.OVERLAP,
    },
    width: { size: w, type: WidthType.DXA },
    columnWidths: [w],
    borders: noBorders(),
    rows: [new TableRow({
      cantSplit: true,
      children: [new TableCell({
        width: { size: w, type: WidthType.DXA },
        borders: noBorders(),
        margins: { top: 80, bottom: 80, left: 80, right: 80 },
        ...(fill ? { shading: { type: ShadingType.CLEAR, color: 'auto', fill } } : {}),
        children,
      })],
    })],
  });
}

const metaLine = (label, value) => new Paragraph({
  spacing: { before: 0, after: 20 },
  children: [
    run(`${label}: `, { bold: true, size: 19, color: BLUE }),
    run(value, { size: 19, color: DARKGREY }),
  ],
});

const coverTitleBlock = floatingBlock(COVER_TITLE_X, COVER_TITLE_Y, COVER_TITLE_W, [
  new Paragraph({
    spacing: { before: 0, after: 40 },
    // 11pt, not 12: "Technology Site Inspection" is about 2.17in at 12pt Arial, which
    // exactly fills the 2.20in box and would wrap on any longer eyebrow.
    children: [run(CFG.cover_eyebrow || 'Technology Site Inspection', { size: 22, color: 'FFFFFF' })],
  }),
  new Paragraph({
    spacing: { before: 0, after: 110 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 10, color: 'FFFFFF', space: 1 } },
    indent: { right: Math.round(COVER_TITLE_W * 0.45) },
    children: [run('', { size: 2 })],
  }),
  new Paragraph({
    spacing: { before: 0, after: 0 },
    children: [run(CFG.cover_subtitle, { bold: true, size: 44, color: 'FFFFFF' })],
  }),
]);

const coverInfoBlock = floatingBlock(COVER_INFO_X, COVER_INFO_Y, COVER_INFO_W, [
  new Paragraph({
    spacing: { before: 0, after: 30 },
    children: [run(CFG.cover_title, { bold: true, size: 26, color: BLUE })],
  }),
  ...(CFG.site_address || []).map((line) => new Paragraph({
    spacing: { before: 0, after: 10 },
    children: [run(line, { size: 20, color: DARKGREY })],
  })),
  new Paragraph({ spacing: { before: 0, after: 0, line: 200, lineRule: 'exact' }, children: [run('', { size: 2 })] }),
  // EP project number is INTERNAL and is never rendered here. verify_report.py asserts it.
  ...(CFG.walk_date ? [metaLine('Inspection Date', String(CFG.walk_date).replace(/^Site walk:\s*/i, ''))] : []),
  ...(CFG.issuance_date ? [metaLine('Issuance Date', CFG.issuance_date)] : []),
  ...(CFG.inspector ? [metaLine('Inspector', CFG.inspector)] : []),
  new Paragraph({ spacing: { before: 0, after: 0, line: 200, lineRule: 'exact' }, children: [run('', { size: 2 })] }),
  new Paragraph({
    spacing: { before: 0, after: 30 },
    children: [run('DRAFT, FOR INTERNAL REVIEW ONLY', { bold: true, color: ALERT_RED, size: 20 })],
  }),
  new Paragraph({
    spacing: { before: 0, after: 0 },
    children: [run(CFG.draft_warning, { italics: true, size: 15, color: ALERT_RED })],
  }),
], 'FFFFFF');

const coverPage = [
  new Paragraph({ children: coverBackgroundRuns(), spacing: { before: 0, after: 0 } }),
  coverLogoRow(),
  coverTitleBlock,
  coverInfoBlock,
  // A floating table must be followed by an anchor paragraph in the flow, or Word has
  // nothing to hang the section's final properties on.
  new Paragraph({ spacing: { before: 0, after: 0 }, children: [run('', { size: 2 })] }),
];

const cover = [
  // ----- Table of Contents -----
  // No pageBreakBefore: the cover is its own section, so the section break already
  // starts this page. Adding a break here would emit a blank page between them.
  new Paragraph({
    children: [run('Table of Contents', { bold: true, size: 28, color: BLUE })],
    border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: BLUE, space: 2 } },
    spacing: { after: 160 },
  }),
  // This is an INSTRUCTION TO THE EDITOR, not report content, and it would otherwise
  // print in the issued PDF looking like part of the document. Styled as a red
  // delete-before-printing callout so it is unmistakably not for the reader, matching
  // the Editor's Note treatment used on each item.
  new Paragraph({
    spacing: { after: 200 },
    children: [
      run('DELETE PRIOR TO PRINTING, ', { bold: true, size: 17, color: ALERT_RED }),
      run('click any entry to jump to that item. Page numbers update automatically in Word; press Ctrl+A then F9 to refresh them manually.', { italics: true, size: 17, color: ALERT_RED })],
  }),
];

// The contents block is a REAL Word TOC field whose CACHED RESULT is the styled
// entry list below (the exact structure Word itself saves). On open the cached
// entries show immediately -- nothing looks broken -- and Update Table / Ctrl+A F9
// regenerates titles, page numbers AND entry count together, which is what the
// hand-built hybrid could never do: deleting an item used to renumber the body
// while the TOC silently rotted (field evidence 2026-08-28, two reports same day).
// Regenerated entries take the TOC1 paragraph style defined on the Document, so
// the look survives regeneration.
function bookmarkFor(item) {
  return `punchitem${item.display_number}`;
}

function tocEntry(item) {
  const anchor = bookmarkFor(item);
  const label = `Item ${item.display_number}.  ${item.title}`;
  // The page number is a REAL Word PAGEREF FIELD, not static text.
  //
  // It used to be static text harvested from a LibreOffice dry render. Word
  // paginates differently from LibreOffice (font metrics, image scaling), so those
  // numbers were wrong as soon as the file was opened in Word, and being plain text
  // they never recalculated. The old two-pass render existed only because a field
  // renders blank when LibreOffice converts to PDF without updating fields. We no
  // longer produce the PDF here, Word does, and Word updates fields on export, so
  // the field approach is now strictly correct.
  //
  // Paired with `features: { updateFields: true }` on the Document, which makes Word
  // refresh these on open. Ctrl+A then F9 forces it manually.
  //
  // Both halves are wrapped in an InternalHyperlink so the entry is clickable.
  return new Paragraph({
    spacing: { after: 40 },
    tabStops: [{ type: TabStopType.RIGHT, position: USABLE_W, leader: LeaderType.DOT }],
    children: [
      new InternalHyperlink({ anchor, children: [run(label, { size: 19, color: DARKGREY })] }),
      new TextRun({ children: [new Tab()], font: FONT, size: 19, color: LIGHTGREY }),
      new InternalHyperlink({
        anchor,
        children: [
          run('p. ', { size: 19, color: DARKGREY, bold: true }),
          new PageReference(anchor, { font: FONT, size: 19, color: DARKGREY, bold: true }),
        ],
      }),
    ],
  });
}

const W_NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"';
const fldChar = (type) => ImportedXmlComponent.fromXmlString(`<w:r ${W_NS}><w:fldChar w:fldCharType="${type}"/></w:r>`);
// Canonical instruction form: leading/trailing space, \h for hyperlinked entries,
// \z (no leader in web view), \u (outline levels). \o "1-1" collects Heading 1,
// which is what every item heading uses.
const tocInstr = () => ImportedXmlComponent.fromXmlString(`<w:r ${W_NS}><w:instrText xml:space="preserve"> TOC \\o "1-1" \\h \\z \\u </w:instrText></w:r>`);

cover.push(new Paragraph({ spacing: { after: 0 }, children: [fldChar('begin'), tocInstr(), fldChar('separate')] }));
for (const item of master) cover.push(tocEntry(item));
cover.push(new Paragraph({ spacing: { after: 0 }, children: [fldChar('end')] }));

// ------------------------------------------------------------------------------ assemble
const children = [...cover];
for (const item of master) children.push(...itemSection(item));

// The letterhead is one page wide image. It sits inside the header space and renders on
// every page. No first page override, no distinction between the cover/TOC and item pages.
const letterheadHeader = new Header({
  children: [
    new Table({
      width: { size: USABLE_W, type: WidthType.DXA },
      columnWidths: [LH_LEFT_W, LH_RIGHT_W],
      borders: noBorders(),
      rows: [
        new TableRow({
          cantSplit: true,
          children: [
            new TableCell({
              width: { size: LH_LEFT_W, type: WidthType.DXA },
              borders: noBorders(),
              margins: { top: 0, bottom: 0, left: 0, right: 0 },
              verticalAlign: VerticalAlign.TOP,
              children: [
                new Paragraph({
                  spacing: { before: 0, after: 60 },
                  children: [new ImageRun({
                    type: 'jpg', data: EP_LOGO,
                    transformation: { width: dxaToPx(LH_LOGO_W), height: dxaToPx(LH_LOGO_H) },
                  })],
                }),
                new Paragraph({
                  spacing: { before: 0, after: 0 },
                  children: [new ImageRun({
                    type: 'png', data: EP_URL,
                    transformation: { width: dxaToPx(LH_URL_W), height: dxaToPx(LH_URL_H) },
                  })],
                }),
              ],
            }),
            new TableCell({
              width: { size: LH_RIGHT_W, type: WidthType.DXA },
              borders: noBorders(),
              margins: { top: 0, bottom: 0, left: 0, right: 0 },
              verticalAlign: VerticalAlign.TOP,
              children: [
                new Paragraph({
                  alignment: AlignmentType.RIGHT,
                  spacing: { before: 40, after: 0 },
                  children: [run('Technology System', { size: 40, color: BLUE })],
                }),
                new Paragraph({
                  alignment: AlignmentType.RIGHT,
                  spacing: { before: 0, after: 0 },
                  children: [run('Punch List', { size: 40, color: BLUE })],
                }),
              ],
            }),
          ],
        }),
      ],
    }),
    // Divider is a SHADED PARAGRAPH, not a border: LibreOffice clamps thick
    // borders to hairlines when converting to PDF, so a border would vanish.
    new Paragraph({
      spacing: { before: 100, after: 0, line: 120, lineRule: 'exact' },
      shading: { type: ShadingType.CLEAR, fill: BLUE, color: 'auto' },
      children: [run('', { size: 2 })],
    }),
  ],
});

const footer = new Footer({
  children: [new Paragraph({
    alignment: AlignmentType.CENTER,
    border: { top: { style: BorderStyle.SINGLE, size: 4, color: LIGHTGREY, space: 4 } },
    children: [
      run(`${CFG.footer_text}  •  Page `, { size: 14, color: LIGHTGREY }),
      new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 14, color: LIGHTGREY }),
      run(' of ', { size: 14, color: LIGHTGREY }),
      new TextRun({ children: [PageNumber.TOTAL_PAGES], font: FONT, size: 14, color: LIGHTGREY }),
    ],
  })],
});

const doc = new Document({
  features: { updateFields: true },     // prompts Word to update the TOC page numbers on open
  styles: {
    default: { document: { run: { font: FONT, color: DARKGREY, size: 21 } } },
    paragraphStyles: [{
      id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
      run: { bold: true, size: 26, color: BLUE, font: FONT },
      paragraph: { spacing: { before: 0, after: 120 } },
    }, {
      // Style Word applies to entries it regenerates inside the TOC field. Matches
      // tocEntry(): dot-leader right tab at the text edge, same size and colour.
      id: 'TOC1', name: 'TOC 1', basedOn: 'Normal', next: 'Normal',
      run: { size: 19, color: DARKGREY, font: FONT },
      paragraph: {
        spacing: { after: 40 },
        tabStops: [{ type: TabStopType.RIGHT, position: USABLE_W, leader: LeaderType.DOT }],
      },
    }],
  },
  numbering: {
    config: [{
      reference: 'punch-items',
      levels: [{
        level: 0,
        format: LevelFormat.DECIMAL,
        text: 'Item %1.',
        alignment: AlignmentType.LEFT,
        style: {
          run: { bold: true, size: 26, color: BLUE, font: FONT },
          paragraph: { indent: { left: 1260, hanging: 1260 } },
        },
      }],
    }],
  },
  sections: [
    // The cover is its own section: no letterhead header and no page footer, because
    // the cover carries its own branding and a "Page 1 of N" strip across the artwork
    // reads as a mistake. Its top margin is small so the logo row sits in the white
    // band above the photo.
    //
    // Set "include_cover": false in report.config.json to omit it. Some clients
    // issue their own coversheet and combine PDFs by hand, in which case a
    // generated cover is a page they delete every time. Dropping the section is
    // safe: the Table of Contents paragraph carries no pageBreakBefore, so it
    // simply becomes page 1.
    ...(INCLUDE_COVER ? [{
      properties: {
        page: {
          size: { width: PAGE_W, height: PAGE_H },
          margin: {
            top: 720, bottom: 720,
            left: MARGIN_LR, right: MARGIN_LR,
            header: 0, footer: 0,
          },
        },
      },
      children: coverPage,
    }] : []),
    {
      properties: {
        page: {
          size: { width: PAGE_W, height: PAGE_H },
          margin: {
            top: MARGIN_TOP, bottom: MARGIN_BOTTOM,
            left: MARGIN_LR, right: MARGIN_LR,
            header: HEADER_MARGIN, footer: 500,
          },
        },
      },
      headers: { default: letterheadHeader },
      footers: { default: footer },
      children,
    },
  ],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(OUT, buf);
  console.log('wrote', OUT, (buf.length / 1048576).toFixed(1), 'MB');
  const undetermined = master.filter(m => m.corrective_action.startsWith('N/A')).length;
  console.log(`items=${master.length} precedent=${withPrecedent} editor_notes=${editorNoted} undetermined=${undetermined} photos=${totalPhotos}`);
});
