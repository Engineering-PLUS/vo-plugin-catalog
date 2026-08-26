# Session handoff, <PROJECT> v0.1

Everything a future run needs in order to be better than this one. Start here.

---

## What to read, in order

| # | File | Why |
|---|---|---|
| 1 | `../CLAUDE.md` | How the pipeline works and the rules it enforces. Read before touching any script. |
| 2 | `../LESSONS-LEARNED.md` | What broke, why, and the recommended skill updates. **This is the learning data.** |
| 3 | `../PROCESS-LOG.md` | The run record: inputs, decisions, review rounds, verification. |
| 4 | `../ISSUES-LIST.md` | Open questions on the report content, for the reviewer. |
| 5 | `memory/` | Agent memory snapshots written this session. |

## Memory snapshots

Point-in-time exports of the agent's persistent memory, so the learning travels
with the project rather than living only in the agent's memory store.

| File | Type | Carries |
|---|---|---|

**Which entries matter on re-import:** <name them. Standing decisions outrank
per-report preferences.>

---

## The changes most worth carrying into the skill

Condensed from `LESSONS-LEARNED.md`. Keep this to the ones that cost real time.

1.
2.
3.

---

## State of the deliverables

| File | Status |
|---|---|
| `<report>.docx` | |
| `<report>-Review.xlsx` | |

## Reproducing this report

```bash
cd _pipeline
bash scripts/smoke_test.sh     # tooling check
bash scripts/run_pipeline.sh   # five steps + verify
```

Outputs .docx only. Deps: `npm install docx@^9.7.1` and
`pip install pymupdf openpyxl pillow --break-system-packages`.

Scope lives in exactly one place, `SCOPE` in `run_pipeline.sh`. Cover and footer
strings live in `build/report.config.json`, not in the renderer.

## Not carried forward, and why

<Walk notes, excluded items, anything deliberately left out and the reason. If
excluded items relate to included ones, say which.>
