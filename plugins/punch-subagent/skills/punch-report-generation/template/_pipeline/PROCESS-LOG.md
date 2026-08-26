# Process log, <PROJECT> v0.1

The run record. What went in, what was decided, what was changed and why, and how
the result was verified. Written as the run happens, not reconstructed afterwards.

**This is a record of what the code does, not a description of what it should
do.** A previous generation of this pipeline documented four features its shipped
code did not have, and every one of them cost real time later. If you write a
behaviour here, run it first.

---

## Inputs

| Input | Path | Notes |
|---|---|---|
| PlanGrid pull | `<path>` | <N> items, base + delta / base only |
| Task Report PDF | `<path>` | <N> pages, <page size>. Source of the pin clips. |
| Walk notes | `<path or "none">` | <if two near-identical files arrived, which was used> |
| Prior report | `<path or "none">` | <what was reused> |

## Scope decision

<What was included, what was excluded, on whose direction, and what is still open
in PlanGrid.>

## How this data differed from the last run

| | <prior project> | <this project> |
|---|---|---|
| Page size | | |
| Items | | |
| Filler title string | | |
| Authored vs photo-only | | |
| Valid sheet ref | | |

<Anything here that broke a script is a lessons-learned entry, not just a table
row.>

## Scripts changed this run

| Script | Change | Why |
|---|---|---|

## Drafting

- <N> items authored by the engineer, polished to report voice
- <N> drafted from photo evidence, marked as such
- <N> not determinable
- <N> flagged as suspected misfires

## Precedent pass

- <N> of <N> items carry a citation
- Tools used and roughly how many calls
- Any theme the corpus could not cover

## Review rounds

### Round 1, <date>

**Feedback.** <verbatim where possible>

**Root cause.** <the actual cause, not the symptom>

**Fix.** <what changed, and whether it was enforced in code or just corrected>

## Verification

Output of `verify_report.py`, and anything asserted by hand.

```
<paste>
```

## Limitations carried into v0.2

<What is known to be imperfect and was accepted for this revision.>
