---
name: document-extraction
description: Use this skill whenever a task needs enterprise-level document extraction or analysis — pulling structured data, text, tables, or metadata out of PDFs, Word documents, spreadsheets, scanned drawing sets, submittal packages, or spec books via the EPLUS Document Analysis engine. The engine is driven by the bundled eplus_docs_client.py script (submit → wait → result), not MCP tools. Encodes the shell-out workflow, the no-base64 rule, delegation to the doc-extractor subagent, and the failure/egress protocol. Always load it before running the client.
---

# EPLUS enterprise document extraction (eplus_docs_client.py)

Rules for running document extraction through the EPLUS Document
Analysis engine. All access goes through the bundled stdlib-only client
script — there are no MCP tools for this engine:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/eplus_docs_client.py" <command> ...
```

Every command prints exactly one JSON object to stdout. A non-zero exit
code means that JSON has `status: "error"` — read its `message`.

## Backend

The Document Analysis engine is an enterprise extraction service on a
dedicated VM (port 8651 — sibling of the Hermes RFI engine). It ingests
PDFs, Office documents, scanned drawings, and submittal packages, and
runs asynchronous extraction jobs: submission returns a `job_id`
immediately; results are fetched when the job completes. Jobs take
anywhere from 30 seconds to 10 minutes.

**Egress requirement:** the deployment must have `20.9.42.66` in its
allowed egress hosts. If the client errors with "cannot reach server",
say exactly that to the user and stop — that is an egress configuration
issue for the deployment admin, **not a retry case**.

## Client commands

- `submit <file_path> [--note TEXT]` — uploads the raw file bytes and
  starts a job; returns `{status, job_id, ...}`. The path must be a
  real local file; `--note` is one line of extraction intent.
- `status <job_id>` — single progress check.
- `wait <job_id> [--timeout 720]` — polls every 20s until the job
  leaves `queued`/`running` or the timeout (default 12 min) expires.
  On timeout the job **keeps running server-side** — report the
  `job_id` so it can be checked later; nothing is lost.
- `result <job_id> [--out FILE]` — fetches the finished extraction.
  Always pass `--out` with a sandbox/scratchpad path: the extracted
  markdown is written to that file and kept out of the transcript;
  stdout carries the remaining metadata (including `pages`).
- `report --message TEXT [...]` — files a fire-and-forget issue report
  to the EPLUS error-reporting engine (see failure protocol).

## The workflow

1. **Submit** — one `submit` per file, with a `--note`. **Never
   base64-encode file content** — into the client, into a transcript,
   anywhere; the client uploads raw bytes itself. Never open the
   document with Read to "help".
2. **Wait** — `wait <job_id>` for each submitted job. For multi-file
   batches, submit ALL files first, then wait on each job in turn: the
   server runs jobs concurrently, so wall time is the slowest job, not
   the sum.
3. **Fetch** — `result <job_id> --out <scratchpad_path>.md`, then work
   from the saved markdown (Read it, selectively). Check the `pages`
   field against the document's size as a sanity signal that the whole
   document was covered.

## Delegate bulk work to the doc-extractor subagent

For any real extraction job — and especially multi-document batches or
large results — dispatch the `doc-extractor` agent (Haiku) with the
file path(s) and the extraction goal. It runs submit → wait → result
and returns a distilled report, keeping raw engine output out of the
parent context. Reserve direct client calls in the main conversation
for quick one-offs like a `status` check on a known `job_id`.

## Failure protocol

- Work only from what the engine actually returned. If a job fails or
  the result is empty/placeholder content, report the status verbatim —
  **never fabricate extracted data, tables, or citations**, and never
  substitute your own reading of the document for engine output while
  presenting it as such. If the engine is down, you may offer a plain
  best-effort read of the document, clearly labeled as NOT
  engine-verified.
- On a real failure (job error, malformed result, clearly wrong
  output), file one report via the client:
  `report --message "..." --category tool_failure --server-name
  document-analysis --details "<exact error JSON, job_id, what was
  tried>"` — one report per distinct issue, no secrets or file contents
  in the report, and never let reporting block the user's task.
- "cannot reach server" is the exception: it is an egress configuration
  issue — tell the user and stop. Do not retry, and do not attempt to
  file a report (the reporting engine sits on the same host and is
  equally unreachable).
