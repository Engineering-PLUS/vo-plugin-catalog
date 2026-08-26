---
description: Draft a punch report from a PlanGrid pull — stamps the pipeline into the project folder, consolidates, drafts, checks precedent, renders and verifies.
argument-hint: [project folder, or leave blank to use the current one]
---

Draft a punch report from field material.

Target folder: $ARGUMENTS (if blank, use the current working folder).

Load the `punch-report-generation` skill and follow it. This command is the
intake and scaffolding front end for that workflow; the skill is the authority
on every step.

## 1. Intake, before anything else

Inspect the target folder and report what you found, then confirm the four
inputs with the user in **one** message rather than discovering them mid-run:

- **The PlanGrid pull** — a directory containing `tasks.json`. Say how many
  items it holds, and whether a `delta_<from>_to_<to>/` folder is present (if
  so, the delta is the authoritative task list and you need both photo
  directories plus the base's `sheets.json`).
- **The PlanGrid Task Report PDF** — **not part of an API pull**, exported
  separately, and the only source of the per-item annotated sheet clips. If it
  is absent, ask for it. The pipeline still runs without it, but every item
  renders `(no pin clip)`, so this is the user's call to make knowingly.
- **Scope** — which item numbers this report covers. If the pull spans more
  than one walk date, say so and propose a split; do not assume. Whatever is
  agreed becomes `SCOPE`, and that is the only place scope lives.
- **Report identity** — project name, building/area, walk date, who walked it,
  and who reviews it. These fill `build/report.config.json`.
- **Issuance date** — ask this one with `AskUserQuestion`. Never infer it, never
  default to today. It is a contractual fact about when the report goes out, it is
  the reviewer's decision, and it routinely differs from both the walk date and
  the compile date.
- **EP project number** — capture it into `report.config.json` as `ep_project_no`
  for our own traceability, and make sure it is **not rendered**. It is internal
  tracking, not client-facing, including on the cover. `verify_report.py` fails the
  build if it reaches the document text.

Ask about anything genuinely ambiguous here. Everything after this point is
expensive to redo.

## 2. Stamp the template

Copy `${CLAUDE_PLUGIN_ROOT}/skills/punch-report-generation/template/` into the
project folder, then copy
`${CLAUDE_PLUGIN_ROOT}/skills/punch-report-generation/scripts/` into
`_pipeline/scripts/`.

Fill in `_pipeline/build/report.config.json` from the identity answers, and
replace the `<PLACEHOLDER>` fields in `_pipeline/CLAUDE.md` with this project's
real values as you learn them. That file is what the next run reads first.

If a `_pipeline/` already exists, do not overwrite it — this is a re-run.
Report what is already there and ask whether to refresh the scripts.

## 3. Check the tooling

```bash
cd _pipeline && bash scripts/smoke_test.sh
```

Fix or report anything that fails before drafting. Missing dependencies are
`npm install docx@^9.7.1` and
`pip install pymupdf openpyxl pillow --break-system-packages`.

## 4. Work on local disk

The project folder is on a network share and is >45x slower than local disk for
the many-small-files steps. Copy `_pipeline/` to a local scratch directory, run
there, and copy back in small batches — **sources as well as outputs**, so the
rendered document and the file that generates it cannot disagree.

## 5. Run the workflow

Follow the skill: consolidate, normalise photos, read the sources, draft every
item in field-report voice, check precedent (two-step: search, then
`get_punch_item` before quoting), extract sheet clips, build master, render,
verify.

`bash scripts/run_pipeline.sh` runs steps 1 through 5 plus verification once
`data/drafted_items.json` exists.

## 6. Deliver three things

The draft `.docx`, the issues list, and the handoff (process log,
lessons learned, HANDOFF.md). The issues list is not an appendix — it is where
the reviewer's attention gets directed.

Do not generate a PDF. The reviewer produces it from Word, which recalculates
the page-number fields on export.
