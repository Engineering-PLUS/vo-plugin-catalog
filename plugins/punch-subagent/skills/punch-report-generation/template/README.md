# <Project>, <Building / area>, punch report

Draft punch report for the <date> site walk, plus the pipeline that generates it.

## Deliverables

| File | What it is |
|---|---|
| `<report>-DRAFT-v0.1.docx` | **The draft.** <N> items, <N> pages, <N> photos. Open in Word; TOC page numbers populate on open (Ctrl+A then F9 to force). |
| `<report>-Review.xlsx` | Bulk-edit sheet. Edit the yellow columns, re-import, re-render. |

The report is a **draft for internal review**, not for issuance. Each item carries
a red `EDITOR'S NOTE` box marked *delete before issuing*.

**No PDF is produced by the pipeline, by design.** Generate it from Word when your
markup is done; Word recalculates the page-number fields on export.

## Scope

<What this report covers, what was excluded, and whether the excluded items are
still open.>

## Where to start

- **Reviewing the report content** to `_pipeline/ISSUES-LIST.md`. Every judgment
  call, ambiguity and gap, with the ones that should be resolved before issuing
  called out.
- **Regenerating or changing the report** to `_pipeline/CLAUDE.md`.
- **Improving the next report run** to `_pipeline/handoff/HANDOFF.md`.

## Editing

**Small edits:** directly in Word. Item headings use Word's own numbering, so
deleting an item renumbers the rest. Every item is exactly one page and
self-contained, so inserting one is copy a page, paste, edit. Note that TOC page
numbers self-heal but TOC *titles* do not.

**Bulk edits:** use the review spreadsheet rather than hand-editing the .docx.

```bash
cd _pipeline
python3 scripts/review_sheet.py import build ../<report>-Review.xlsx
node scripts/gen_report.js build
```

## Regenerating from scratch

```bash
cd _pipeline
bash scripts/run_pipeline.sh
```

## Folder map

```
<report>-DRAFT-v0.1.docx      the draft
<report>-Review.xlsx          bulk-edit sheet
<Task Report>.pdf             source for the drawing pin clips
<pull folder>/                raw PlanGrid pull (base + delta)
_pipeline/
  CLAUDE.md              how the pipeline works, read first
  PROCESS-LOG.md         this run: inputs, decisions, review rounds, verification
  LESSONS-LEARNED.md     what broke and the recommended skill updates
  ISSUES-LIST.md         open questions for the reviewer
  handoff/               session handoff + agent memory snapshots
  scripts/               the pipeline
  data/                  items.json (facts) + drafted_items.json (judgment)
  build/                 everything the renderer reads, plus the rendered .docx
  review/                contact sheets and rendered pages used for checking
```
