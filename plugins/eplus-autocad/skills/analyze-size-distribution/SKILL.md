---
name: analyze-size-distribution
description: Use when choosing drawing-cleanup thresholds, analyzing entity length or area distributions, counting entities under a candidate size cutoff, or deciding what is safe to delete from a DWG. Calls the autocad MCP analyze_size_distribution tool. Data-driven cutoffs, never guesses.
---

# Analyze size distribution

Call the `analyze_size_distribution` tool on the `autocad` MCP server
(tool name `mcp__autocad__analyze_size_distribution`; use the
plugin-scoped variant if that is the one available).

**What it does:** computes length/area distributions over a drawing clone —
percentiles, a cumulative histogram, and counts under candidate
thresholds — so cleanup cutoffs are chosen from data instead of guessed.

**Iterating cheaply:** pass `reuse_job` with a previous job's identifier
to re-filter an earlier scan in seconds instead of re-cloning and
re-scanning the drawing. Prefer this during threshold tuning.

**Workflow:** present the distribution to the user and let them pick the
cutoff; never delete or modify anything yourself — this tool only
measures. Pair with `select-in-session` to show the user what a candidate
threshold would capture.

**On failure:** if the tool is missing or errors, tell the user the
`autocad` connector is not connected or failed, quote the exact error, and
suggest checking the connector in the Claude desktop settings. Do not
invent statistics.
