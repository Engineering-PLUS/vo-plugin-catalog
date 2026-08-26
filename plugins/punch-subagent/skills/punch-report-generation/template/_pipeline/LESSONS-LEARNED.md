# Lessons learned, <PROJECT> v0.1

What broke on this run, why, and what should change in the skill as a result.
**This is the learning data.** The process log records what happened; this file
records what it means for the next run.

Write an entry when something cost real time, produced a wrong result that looked
right, or would have been avoided by a rule. Do not write entries for things that
merely went well.

---

## Entry format

Each entry states the symptom, the root cause (not the symptom restated), the
fix, and whether the fix is **enforced in code** or only **written down**. A rule
that is only written down will be broken again.

---

## 1. <Short title of what broke>

**Symptom.** <what was observed>

**Root cause.** <the actual mechanism>

**Fix.** <what changed>

**Enforced by.** <a check in build_master.py / verify_report.py / a hook, or
"documented only">

**Generalises to.** <what class of future problem this covers, if any>

---

## Recommended skill updates

Numbered, specific, and phrased as a change to make, not an observation. These
are what a future session will act on.

1.
2.
3.

---

## Known-good baselines carried in from prior runs

Do not re-derive these; they are already settled. Listed here so a future run can
tell the difference between a settled rule and an open question.

- **Anchor image crops on vector geometry the producing tool actually drew**, not
  on measured offsets from a text label. Offsets are geometry-specific and break
  silently on a page-size change.
- **Never display a measurement taken from a different renderer than the reader
  will use.** Either compute it in the target renderer or let the target compute
  it with a field.
- **When a constraint is removed, delete the workaround it forced** rather than
  bypassing it.
- **Verify documented behaviour by running it.** A previous package documented
  four features its code did not have.
- **Resolve a pin's sheet name and description before declaring it
  undeterminable.** It has converted a non-finding into a specific one.
- **Work on local disk, sync sources and outputs back at the end.** The project
  share is >45x slower and has already caused a source/render mismatch.
