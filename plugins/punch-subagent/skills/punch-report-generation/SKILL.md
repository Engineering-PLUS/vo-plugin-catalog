---
name: punch-report-generation
description: Use this skill to DRAFT a punch report, field progress report, or site inspection report from raw field material — a PlanGrid project pull, a folder of site photos, an engineer's walk notes, or any combination. Trigger when asked to write up a punch walk, turn photos and notes into a report, produce a draft punch list document, or generate a deliverable from a site visit. Covers intake, consolidating messy source data, drafting descriptions in field-report voice, checking wording against EPLUS precedent, and rendering a branded one-page-per-item Word document with a live table of contents. Distinct from the `punch` skill, which QUERIES the historical corpus; this one PRODUCES a new report.
argument-hint: <folder of field material — e.g. "draft the report from the files in this folder">
---

# Drafting a punch report from field material

Turns a site walk into a reviewable draft. The human finishes and issues it —
the target is ~80% of the way there with every uncertainty surfaced, not a
publishable document.

$ARGUMENTS

**The pipeline is a stampable project template, not a set of loose scripts.**
Copy `template/` into the project folder and work inside it. The template's
`_pipeline/CLAUDE.md` is the operating manual for that project and is the file
a future run reads first — fill it in as you go rather than at the end.

## Step 0 — Intake, before you start drafting

Confirm all four before touching the data. Two of these have been discovered
mid-run before, which costs a restart:

| Input | Required? | Notes |
|---|---|---|
| PlanGrid pull | yes | a directory containing `tasks.json` |
| **PlanGrid Task Report PDF** | for pin clips | **not part of an API pull.** Exported separately. The only source of per-item annotated sheet clips. |
| Scope | yes | which item numbers this report covers, and what a prior report already covered |
| Walk notes | optional | often arrive as two near-identical files |

**Ask for the Task Report and the scope up front.** Both were mid-run
discoveries on the last job. If the Task Report is genuinely unavailable the
pipeline still runs and items render `(no pin clip)`, but say so before drafting
rather than after.

**Use `AskUserQuestion` to get the issuance date.** Do not infer it, do not use
today's date, and do not leave it blank. The issuance date is a contractual fact
about when the report goes out, which is a decision the reviewer makes and often
differs from both the walk date and the date the draft was compiled. Ask it
explicitly as part of intake, alongside the walk date and scope.

**The EP project number is internal tracking and is never rendered.** It lives in
`report.config.json` as `ep_project_no` so runs stay traceable on our side, but it
must not appear anywhere a client, GC or subcontractor reads, including the cover.
`verify_report.py` asserts it is absent from the document text, so this fails the
build rather than shipping.

Then check the tooling actually works:

```bash
bash scripts/smoke_test.sh
```

This exists because a previous generation of this pipeline documented four
features its shipped code did not have. Run it; do not assume.

### Work in the local workspace — a CORRECTNESS rule, not an optimisation

**All intermediate work happens in your own workspace. The project folder is
written to only when a deliverable is finished.** Four field incidents
(2026-08-28 session) make this a correctness requirement:

1. **The share is behind a VPN.** When the VPN dropped mid-session, mounted
   folders read as *empty directories with no error*. A process working in
   place sees its inputs vanish silently; a local process does not care.
2. **Latency turns long copies into silent partial failures.** A 217 MB
   PlanGrid copy exceeded the 120-second tool timeout at 120 of 171 files and
   reported nothing. (Photo normalisation: 3.0s locally vs over two minutes on
   the share.)
3. **A half-written deliverable must never be visible to the reviewer.** A
   render that fails after writing a partial .docx into the project folder can
   be opened by the reviewer. Local-then-copy makes every write atomic.
4. **The share may be reachable by file tools but NOT by bash at all**,
   depending on how the folder was attached — and every pipeline step is a
   shell invocation.

The pattern — use `scripts/sync_project.sh` for every share copy; it verifies
by file count and byte size and refuses an empty source:

1. Copy sources into the workspace, VERIFY the copy. Never trust that a copy
   finished.
2. Stamp `_pipeline/` and run everything locally.
3. Copy back in small batches: the .docx first, then data/, scripts/, build/.
4. **Sync the sources back too, not just the .docx.** A `drafted_items.json`
   edit that lives only locally means the document and the file that generates
   it disagree, and a re-run silently reverts it — a near-miss that has already
   happened.
5. Distinguish "empty" from "unreachable" before treating an empty listing as
   meaningful.

## The premise: the input is always messy

This is the problem being solved, not a problem to complain about:

- **No location data.** PlanGrid's `room` field is typically empty on 100% of
  pins. The only structured location is the drawing sheet number.
- **Many pins have no description.** The photos *are* the record.
- **Notes aren't linked to pins.** Matching a note to a pin is inference from
  photo content, not a lookup. It is the fuzziest step here — treat every match
  as a claim to be checked.
- **Some pins are noise.** Camera misfires, photos of colleagues, blank walls.
- **Some pins bundle several unrelated conditions.**

**Never ask the field to fix this before you can work.** Infer what is
inferable, label what was inferred, and surface what is not determinable.

**Measure this pull rather than assuming it.** Data quality varies widely
between jobs: one recent pull was 80% authored with 100% valid sheet refs, well
above the pessimistic baseline. Read the triage summary from Step 1 and set the
bar from the data in front of you.

## Workflow

### Step 1 — Consolidate

```bash
python3 scripts/consolidate.py <pull_dir> -o data/items.json [--only 11-30]
```

`--only` accepts ranges and comma lists and is **the only place scope lives**.

It emits one record per live item (number, description, sheet ref, pin stamp,
status, photos resolved to files on disk with capture time and photographer)
plus a triage summary. Read the summary first — `photo_only`, `no_photos` and
`with_room` tell you immediately how much of this report must be drafted from
images.

It handles two pull shapes automatically, both of which quietly corrupt a report
if missed:

- **A `delta_<from>_to_<to>/` folder** holds a later, superset `tasks.json` but
  only the **new** photo binaries, and often an empty `sheets.json`. A correct
  read needs the delta's tasks, **both** photo directories, and the base's
  sheets. Reading either half alone loses items or photos.
- **Filler titles.** Field staff reuse a personal marker as a title (`Jim2` on
  one job, `General` on 18 of 20 pins on another). Any title appearing on >=50%
  of pins (min 3) is treated as empty rather than as content.

### Step 2 — Normalise photos

```bash
python3 scripts/normalize_photos.py --items data/items.json \
    --dest build/thumbs_uniform --dims-out data/thumb_dims.json
```

Applies EXIF rotation, letterboxes to a uniform box, and downscales. **PIL does
not apply EXIF orientation on save**, and the originals look upright in every
normal image viewer, so a missed transpose only surfaces as sideways photos in
the rendered document. On the last pull, 34 of 34 photos needed it.

### Step 3 — Read every source document, and diff the duplicates

Walk notes frequently arrive as two near-identical files (`…notes.docx` and
`…notes(update).docx`). **Diff them and use the newer one**; call out only real
conflicts. The update usually fixes typos and adds items.

### Step 3.5 — Ask the user how they want the wording set

Once photos are sorted and itemized and BEFORE drafting any item's content,
ask the user with **AskUserQuestion** (one question, three options):

> Photos are sorted into N items. How do you want to set each item's wording?
> 1. **Walk every item with me** — preview each item, I confirm or adjust the
>    wording before it's locked.
> 2. **Review only the ones you're unsure about** — you draft what's clear, I
>    only see the low-confidence items.
> 3. **You draft it** — produce the document; I'll review the finished draft.

"Unsure" in mode 2 means: every `photo_only` and `no_photos` item from the
consolidate triage, anything whose description is inferred from photo content
alone, and anything you would mark `confidence: low`.

**The per-item review loop (modes 1 and 2), order is mandatory:**

1. **Render the preview FIRST, then ask.** Publish an HTML artifact staging the
   item as close as possible to the Word layout — use
   `templates/item-preview.html` as the reference markup (same fonts, colors,
   two-column photo grid at Word proportions, sheet clip, blank paste-target
   row for photo-less items; photos embedded as data: URIs). Use ONE artifact
   and republish it for each item (same URL updates in place), so the user
   watches the item change as they answer. Never ask about an item the user
   cannot currently see.
2. **Then ask the item's questions with AskUserQuestion** — proposed
   title/description/corrective action (accept or revise), trade or location
   when ambiguous, and anything the photo inference was unsure of. Ask only
   what is genuinely undecidable from the evidence; don't quiz for its own
   sake.
3. Record each decision into `data/drafted_items.json` as you go. Wording the
   user approved or supplied gets `"origin": "user_reviewed"` —
   `build_master.py` treats it as untouchable (no sanitize rewrites, no voice
   guard, no recapitalisation) and FAILS LOUDLY if the text would need
   cleaning, rather than silently altering approved wording.

**Items without photos — always raise it, in every mode.** For each `no_photos`
item, ask (grouped into one AskUserQuestion when there are several):

> Item N has no photos. Options: **(a)** I'll add my own photos in Word — render
> the empty photo grid as a paste target; **(b)** no photos apply — drop the
> grid and the Photos label for this item; **(c)** flag for a follow-up site
> visit — render the empty grid and note it on the issues list.

Record the answer as `"photo_mode": "own_photos" | "none" | "followup"` on the
drafted entry. The renderer honors it: `none` suppresses the photo block
entirely; the other two render one empty grid row sized like a real photo cell
(invisible-hairline rows are a shipped bug this fixed).

### Step 4 — Draft a description for every item

Write into `data/drafted_items.json`, keyed by PlanGrid number.

**Items with an authored description:** the engineer's wording is authoritative.
Polish to report voice; never change technical meaning.

**Photo-only items:** check the walk notes first. Then, **before writing one off
as undeterminable, resolve its sheet name and check the other items on the same
sheet.** This is cheap and it works: a photo-only pin showing a boarded-out room
with no visible work looked like a non-finding until its sheet resolved to *MDF-A1
Enlarged Plans*, which made it a specific, defensible finding tied to a still-open
item from an earlier walk.

#### Describe what is present. Never infer what it is for.

The second fabrication mode, and the one the voice rules made *harder* to spot:
once a description is written in confident field-report voice, a wrong inference
reads exactly like a right one.

A v0.1 draft described *"layout markings set out on the slab at the intended
positions, with no floor box rough-in in place."* The markings were for **overhead
hangers**. The photograph showed marks on a slab; everything after that was
invented, and it was invented fluently.

**The rule: state the physical condition, stop before the purpose.**

| Safe, because it is what is there | Unsafe, because it claims to know why |
|---|---|
| "Conduit stubbed up through the slab at this location." | "Floor box rough-in is missing at the positions laid out on the slab." |
| "Layout markings are set out on the slab." | "Layout markings mark the intended floor box positions." |
| "A junction box is mounted to the door jamb stud with cable present." | "The rough-in is consistent with door position hardware." |

On a photo-only pin, **the purpose is precisely the thing not in evidence.** If
the observer's note states the purpose, use the note and say so. If it does not,
describe the condition and let the reviewer supply the intent.

A related trap: do not invent a *category* either. A pin the engineer logged as a
reference photo is not a deficiency, and writing it up as one manufactures a
finding out of a record shot.

**Four outcomes are all valid:**

1. A specific, defensible deficiency.
2. A description qualified by what could not be confirmed.
3. Condition could not be established during the walk; requires field
   verification.
4. **Authored but unverifiable** — a written note with **no photograph** at all.
   This is its own low-confidence category. An authored note is not high
   confidence just because someone typed a sentence; there is nothing to check it
   against. Flag it as such.

**Forcing a confident description onto an ambiguous photo is the single worst
failure mode available here** — it produces a report that reads well and is
partly fiction.

**Title outcome 3 by what is there, not by what is missing.** Headings of the form
*"Wall Rough-In, Subject Not Identified"* were read by a reviewer as *"what does
this mean?"* — the phrase is pipeline jargon leaking onto the page. Title the item
after the observed condition (*"Wall Rough-In at Gridline C"*, *"Conduit Stub-Up,
Location To Be Confirmed"*) and let the description carry the uncertainty.

**Flag, do not describe, pins with no field content at all.** If the only photo
shows a person, a vehicle, an office interior, or a blank wall, the pin is almost
certainly a camera misfire. Surface it as *"should this item be in the report?"*
Do not delete it silently either — that is the human's call.

#### Field-report voice, enforced

The report is written **by** the field engineer, describing the site. Two things
are banned from descriptions, and `build_master.py` fails the build and names the
offending item if either appears:

**1. Narrating the evidence.** "The photograph shows", "visible in the frame",
"not determinable from this photograph". These describe the evidence rather than
the site and make an otherwise solid write-up look machine-produced. State the
condition directly:

> *"Metal stud wall framing at this location carries a junction box with flexible
> metal conduit whips terminating in open air…"*

For genuinely unclear pins, write *"could not be established during the walk and
requires field verification"* — how an engineer would actually say it.

**2. Third-person self-reference.** "The field engineer recorded this condition as
ongoing progress" reads as somebody else narrating the author. Write *"Work
remained in progress at the time of the walk."*

Editor's Notes are internal, are deleted before issuing, and are exempt from both.

**The verbatim pin note is never rendered**, for the same third-person reason. It
stays on the record as `field_note` and appears in the review spreadsheet.

### Step 5 — Check wording against EPLUS precedent

Use the `punch` skill's tools. **Two steps, always:**

1. `query_hermes_punch` to find candidate precedent.
2. **`get_punch_item` to read the exact wording before citing it.** Never quote
   from a search result. The search tool's item bodies are subject to change and
   are already scheduled to be replaced by short snippets; `get_punch_item` is
   the contract for exact wording. Misquoting an engineer's defect wording is not
   a defect the reviewer will catch.

Cap `limit` at 25 yourself — the server does not clamp it, and a large limit
returns tens of thousands of characters.

**On the `trade` filter:** it is exact SQL on every tool, search included, so it
does not silently break. But **trade labels are single-valued and rule-derived**,
and cross-trade defects get exactly one label. A search for *"missing conduit
bushing"* returns hits labelled both `Security` and `Telecom`, because conduit
serving a security device is labelled `Security`. So an empty filtered search
means *"the matching items are labelled under another trade"*, not *"no such
items exist"*. **Drop the `trade` filter first when a filtered search returns
nothing.** On `punch_stats` / `list_punch` / `export_punch_report` the filter
browses the label space directly and has no text intersection to lose, so it is
reliable there.

**Verify the tool is reachable before starting, and say so loudly if it is not.**
A silently-degraded precedent pass produces a finished-looking report whose
wording was never checked, with the caveat buried where nobody reads it.

**Cap yourself at two or three corpus calls at a time.** Each
`query_hermes_punch` returns roughly 6,400 tokens, so eight parallel calls is
~50k tokens in one turn and it compounds across a long drafting session. Batch
small, and prefer `grep_punch` (~780 tokens) and `punch_stats` (~120) wherever
they answer the question. Aim for a citation on every item that can carry one,
and record the coverage in the process log, but get there in small batches.

#### Precedent governs voice, never content

**This is the rule that matters most, and it has already produced a wrong
statement in an issued draft.**

A precedent item shows you *how EPLUS writes a finding*: the sentence shape, the
level of detail, the way a corrective action is addressed. It does **not** tell
you anything about the project in front of you.

The failure, verbatim from a v0.1 review: an item's corrective action read
*"confirm each floor box has rough-in for data back to the serving MDF as
specified."* The phrase came from an **NVA02E** item. At this project the
rough-in does not go back to the MDF. The sentence was well formed, correctly
voiced, and factually invented, and nothing downstream could catch it because it
reads exactly like a real finding.

So:

- **Never carry a project-specific noun across from a precedent item.** Room
  names, device names, MDF/IDF references, routing, panel numbers, mounting
  heights. If it names a thing, it has to come from *this* project's notes,
  drawings, or photos.
- **Write corrective actions to point at the drawings rather than restate them.**
  *"and required rough-in to the locations identified on the drawings"* is right.
  *"back to the serving MDF as specified"* is a claim about a system you have not
  seen.
- **When precedent and the observer's note disagree, the observer wins.** The
  engineer walked the site. The corpus did not.

Before an item ships, every specific noun in its description and corrective
action should trace to this project's source data. If it traces only to a
precedent citation, cut it or generalise it.

**Known corpus gap:** the corpus is entirely interior fit-out. Underground duct
bank, vault and hand hole work returns nothing. Items of that kind have **no
precedent basis** — write the corrective action from the contractual requirement
and state the gap in the item's Editor's Note rather than hiding it. Do not
invent wording to fill the space.

### Step 6 — Sheet clips

Per-item annotated clips — the drawing with the pin stamp — come only from the
**PlanGrid Task Report PDF**.

```bash
python3 scripts/extract_sheet_clips.py "<Task Report>.pdf" build/sheet_clips_jpg \
    --items-from data/items.json --dims-out build/sheet_clip_dims_jpg.json
```

It handles three traps, all already solved — do not reimplement:

1. **Table of contents.** The first pages repeat every item heading with dot
   leaders and page numbers, so a naive search for `#N` matches the ToC entry.
   Content start is detected, not hardcoded.
2. **The reported image bbox is larger than the visible region.** PlanGrid draws
   the clip through a clip path pymupdf cannot see, so `get_image_info()` reports
   a bbox that can overrun the page edge entirely. **The crop is anchored on the
   clip box's real vector border rectangle** found via `page.get_drawings()`,
   filtered by plausible size and aspect and by sitting below the heading.
   *This replaced tuned pixel offsets from the "Sheet" text label, which were
   geometry-specific and produced silent garbage when a Task Report arrived as A4
   rather than US Letter.* **Anchor on vector geometry the producing tool actually
   drew, never on measured offsets from a text label.**
3. **Overflow.** An item near a page bottom pushes its clip to the next page with
   no repeated heading; detected, with a fallback to the following page.

It reports which items used the fallback and which are missing — read that output
rather than assuming. It also **errors on byte-identical clips for two different
pins**: that has shipped once (two items showing the same drawing, one of them
therefore wrong) and nobody caught it by eye.

**A Task Report only covers the export window it was generated for.** A
multi-visit report needs one Task Report export per visit; clips for items from
an earlier visit are simply absent from a later export. Ask for the missing
export rather than salvaging clips from a previously rendered document.

### Step 7 — Assemble and render

```bash
python3 scripts/build_master.py --items data/items.json \
    --drafted data/drafted_items.json -o build/master_report_items.json
node scripts/gen_report.js build
python3 scripts/verify_report.py build/<output>.docx
```

Or `bash scripts/run_pipeline.sh` for all five steps plus verification.

`build_master.py` merges facts with judgment and enforces what the renderer
should not have to care about: no em or en dashes anywhere, the voice rules,
capitalised corrective actions, photo paths as basenames only (an absolute source
path silently renders the unnormalised, EXIF-sideways original), and a loud
failure on any item with no drafted entry.

Report identity — cover title, subtitle, walk date, prepared-by, footer — lives in
`build/report.config.json`, **not** in the renderer. Change it there.

Read the `docx` skill for mechanics and `eplus-branding-default-fonts` for styling
if you need to modify the renderer. Its defaults are all learned the hard way —
**do not re-derive them**:

**The cover is the issued EPLUS coversheet design.** Two raster pieces are reused
as artwork, because artwork is what they are: `assets/cover/cover_hero.jpg` (stock
brand imagery) and `assets/cover/cover_bands.png` (the EP diagonal band graphic, a
full-page transparent overlay). Both are page-anchored floating images behind the
text; **the hero is emitted first** because docx derives z order from document
order and the bands belong on top. Every piece of cover text is native and comes
from `report.config.json`, so it tracks page size and stays editable.

The **client logo is per project and is not bundled with this skill** — it is the
end client's trademark and changes every job. Drop it at
`build/assets/cover/client_logo.png` to have it render top right; omit it and the
cover renders without it.

The cover is **its own section**, with no letterhead header and no footer, since a
page-number strip across the artwork reads as a mistake. The section break already
starts the following page, so the Table of Contents paragraph must not also carry
`pageBreakBefore` or Word emits a blank page.

**The letterhead is built natively, never pasted in as a bitmap.** This was
raised on two consecutive reports. The root cause is not image size: a
full-page-width strip in a header starts at the **body** left margin, so it
overhangs the right edge and leaves dead space on the left. Rescaling it is
another patch on the same mistake. The header is a two-column table sized to
`USABLE_W`, so it tracks the body margins at any page size and stays crisp at
print resolution. The divider must stay a shaded paragraph, not a border, because
LibreOffice clamps thick borders to hairlines.

**One item per page.** Page break before each item heading, table rows
`cantSplit`. The photo grid is sized *dynamically* so a 1-photo and a 21-photo
item both look intentional: `estimateOverheadDXA()` sums the heading, meta table,
description, flags and labels; `layoutForItem()` walks column counts 3→8 and
picks the first that fits at a minimum thumbnail width. 1- and 2-photo items get
fixed larger sizes so they do not balloon.

**Downscale.** ~700 px wide at quality 72 takes a 160-photo report from >150 MB to
~8 MB with no readability loss.

**Image sizes are in PIXELS.** `ImageRun.transformation.{width,height}` wants
pixels while everything else is twips. Passing DXA straight through renders a
~23-inch image and blows every item onto three pages. Convert:
`px = Math.floor((dxa / 1440) * 96)`. Hit twice, once per image type added.

**`rowSpan` is declared once**, on the first row's cell only.

**Green is for visually distinct callouts** — a box or banner — not an inline
bolded label inside body text.

**Write to new filenames, never overwrite.**

### The pipeline outputs .docx only, and the TOC uses live Word fields

These are linked. Do not undo either.

**No PDF is generated.** The reviewer produces it from Word once markup is done.
Word recalculates fields on open and on export.

**The contents block is a real Word `TOC` field** (` TOC \o "1-1" \h \z \u `)
whose **cached result** is the styled entry list — the exact structure Word
itself saves. On open the cached entries show immediately, so nothing looks
broken; *Update Table* (or Ctrl+A, F9) regenerates titles, page numbers **and
entry count** together. Each cached entry still carries a real `PAGEREF` field
pointing at the item heading's `Bookmark`, wrapped in an `InternalHyperlink`,
with `features: { updateFields: true }` so Word refreshes on open. Regenerated
entries take the `TOC1` paragraph style defined on the document, so the look
survives regeneration.

This replaced two earlier designs, each killed by field evidence:

- a two-pass render that baked **static page numbers** harvested from a
  LibreOffice dry render — **LibreOffice and Word do not paginate
  identically**, so the numbers were wrong and permanently so;
- hand-built entry paragraphs with live `PAGEREF` fields but **static
  titles** — page numbers self-healed on F9 while deleted items stayed in the
  list, so the TOC silently rotted (two reports failed this way on the same
  day, 2026-08-28: one stale after item deletions, one showing 16 entries
  against 9 items with seven `Error! Bookmark not defined.`). The asymmetry —
  the body renumbering correctly while the TOC rots — is what misled reviewers.

Transferable rules: **never display a measurement taken from a different
renderer than the reader will use**; **when a constraint is removed, delete the
workaround it forced**; and **make the whole structure one field so Word owns
all of it**, not just the numbers.

`scripts/fix_bookmark_ids.py` runs after every render (wired into
`run_pipeline.sh`): the docx library emits every bookmark as `w:id="1"` (Word
keys on the id and discards duplicates — the `Error! Bookmark not defined.`
bug that shipped in r4) and non-canonical `PAGEREF` instruction text; it fixes
both. `scripts/fix_toc.py --check` remains as a drift gate for documents
already in circulation that predate the TOC field.

### Step 8 — Verify against the OOXML

`verify_report.py` reads the .docx XML directly — no LibreOffice dependency —
because verification must read the artifact the reader actually opens. It checks
em/en dashes, the voice rules (**scoped to descriptions only**, since Editor's
Notes legitimately discuss photographs), PAGEREF/bookmark integrity, absence of
baked page numbers, `w:updateFields`, page breaks per item, embedded photo count,
and that the letterhead is native rather than a pasted bitmap.

**When writing OOXML text assertions, normalise whitespace first.** Joining
`<w:t>` runs doubles spaces, which produces phantom failures on exact matches.

Anything genuinely pagination-dependent is not asserted; it is delegated to Word
by using fields.

**Visual verification closes the gap OOXML checks can't.** An element existing
in the XML does not mean the page looks right — the empty photo grid once
shipped verified only by a `<w:tc>` cell count, which cannot distinguish a
visible paste target from a collapsed hairline row. For layout changes, run

```bash
python3 scripts/render_preview.py build/report.docx --pages 1,4
```

It rasterises to PNG via a scratch-dir PDF **which it deletes** — no PDF
survives to be mistaken for a deliverable (the PDF-block hook allows this
script by name). Rule: **layout and appearance may be checked in the preview;
anything numeric must be checked in the OOXML** — the preview's pagination is
LibreOffice's, not Word's, so never quote a page number from it. The one thing
neither can prove is Word's own F9 behavior; after any template-level TOC
change, do the manual acceptance test once: delete an item in Word, Ctrl+A F9,
confirm the TOC loses the entry and renumbers.

### Step 9 — Keep the report editable by a human

A rendered .docx is a compiled artifact. Without care the only thing that can
revise it is another model run — a trap, because reports get edited by whoever is
holding them at 5pm. Two escape hatches, both must keep working.

**Small edits: directly in Word.** Item headings use **Word's own numbering**, not
text like `Item #7`. Delete an item and the rest renumber. Do not "fix" this by
writing the number into the heading text.

The PlanGrid ID is deliberately **not** in the heading, and as of v0.7 it is **not
rendered anywhere the contractor sees** — that meta row was removed. It is retained
in `master_report_items.json` as `plangrid_ref` and shown in the review
spreadsheet, which is where anyone reconciling against PlanGrid reads it. The
printed number is presentational and will change; the PlanGrid ref is the
permanent link back to source and is never renumbered.

**Reviewer comments in Word: read them back.** Reviewers comment directly in the
.docx, and a comment the model cannot see is a comment that gets ignored.

```bash
python3 scripts/read_comments.py <reviewed>.docx            # readable
python3 scripts/read_comments.py <reviewed>.docx --json -o comments.json
```

Each comment comes back **with the text it is anchored to and the item heading it
falls under**, because "reword this" is meaningless without the span it points at.
Resolved comments are hidden unless you pass `--include-resolved`. Replies are
linked to their parent.

Work the comments before re-rendering, and treat a comment that says "see comment
above" as applying to every instance of the same pattern, not just its own item.

**Bulk edits: the review spreadsheet.**

```bash
python3 scripts/review_sheet.py export build -o Report-Review.xlsx
#   reviewer edits the yellow columns
python3 scripts/review_sheet.py import build Report-Review.xlsx
node scripts/gen_report.js build
```

Yellow cells editable, grey generated and ignored on import, so photo paths and
sheet clips cannot be corrupted by editing the sheet. `Include? = N` drops an
item, `Order` (spaced by 10) reorders, a row with no PlanGrid ref inserts one. A
timestamped `.bak.json` is written before anything changes.

### Step 10 — Deliver the draft, the issues list, and the handoff

Three deliverables, not one.

**The issues list** (`_pipeline/ISSUES-LIST.md`) is first-class. It carries source
conflicts (report both, never silently pick one), items referencing documents you
were not given, suspected misfires as questions, items where the photo contradicts
the description, multi-condition pins for a split/keep decision, everything
drafted from photos rather than authored, authored-but-photoless items, and any
pattern that belongs above item level. Call out the few that genuinely block
issuance.

**The handoff** (`_pipeline/PROCESS-LOG.md`, `LESSONS-LEARNED.md`,
`handoff/HANDOFF.md`) is how the next run gets better than this one. Fill these in
as you go. Write down what broke, the root cause rather than the symptom, and
whether the fix is enforced in code or only written down — a rule that is only
written down will be broken again.

**Write the process log from what the code does, not what it should do.** The
previous package documented four behaviours its code did not have, and each cost
real time later.

## Revising an existing report — the common case

Almost all real work is a revision (r2…r5 in one week on one project), not a
clean run from a pull, and the revision path has its own rules:

- **The reviewer's Word edits are the senior source.** Rebuilding from scratch
  discards them. To recover approved wording from a reviewed .docx, use
  `scripts/import_reviewed_docx.py` (prototype, assembled from the code that
  actually recovered 16 write-ups): it matches embedded photos to normalised
  thumbnails by **32×32 greyscale pixel signature** — exact, unlike caption
  timestamps, which collide the moment two photos share a minute — and emits
  drafted entries with `"origin": "reviewer_final"`. It also reveals photos the
  reviewer silently deleted.
- **`origin: reviewer_final` and `origin: user_reviewed` text is untouchable.**
  `build_master.py` refuses to sanitize-rewrite it and fails loudly if it would
  have to; the voice guard does not apply to it. Fix source text explicitly or
  not at all.
- **Reviewer pin merges live in the judgment layer.** Record them as a `merges`
  block in `drafted_items.json` — `{"items": [...], "merges": [{"into": 22,
  "from": 23, "drop_photos": ["…"]}]}` — which `build_master.py` applies
  in-memory (photos folded in chronological order, absorbed pin auto-omitted).
  Never mutate `items.json` to represent a human decision; a re-run of
  consolidate would erase it. (`scripts/merge_pins.py` is the older
  items.json-mutating form; prefer the merges block.)
- **New site visits need their own Task Report export** for sheet clips (see
  Step 6); do not salvage clips from the previous render.
- Re-run the wording review (Step 3.5) **only for new or changed items** — a
  revision must never re-ask questions the user already answered. Their
  previous answers are in `drafted_items.json` with `origin: user_reviewed`.

## House policy

Standing decisions. Follow them unless told otherwise for a particular report:

- **Multi-condition pins stay combined in the draft** and are listed for review.
  Splitting changes item numbering, which breaks the link back to PlanGrid.
- **"Not determinable" items ship in the report**, marked as such. They are
  evidence a shot was missed and are worth seeing.
- **Suspected misfire pins are surfaced as questions**, never deleted and never
  force-described.
- **The report is .docx only.** No PDF, no LibreOffice step.

## What good looks like

A report where every item is traceable to its PlanGrid number, every description
is either the engineer's own words or clearly marked as drafted from photos, every
uncertainty appears in the issues list rather than being smoothed over, and the
reviewer's job is confirming judgment calls — not discovering that a
confident-sounding paragraph was invented.
