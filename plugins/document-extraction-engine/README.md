# document-extraction-engine

Enterprise document extraction for the EPLUS fleet. The backend is the
**Document Analysis engine** — an HTTP service on port 8651 of the same
Azure VM that hosts the Hermes RFI engine (8650) and the Error
Reporting engine (8652), same bearer token. Jobs are asynchronous:
submission returns a `job_id` immediately (jobs take 30 seconds to 10
minutes), results are fetched when the job completes.

Unlike the SSE-based RFI and error-reporting plugins, this plugin has
**no MCP server and no hooks**: all engine access goes through a
bundled stdlib-only Python client that the model shells out to. Raw
file bytes go straight from disk to the engine and extracted markdown
lands in a scratchpad file — nothing bulky ever enters the model
transcript.

> **Egress requirement:** the deployment must allow outbound traffic to
> `20.9.42.66`. If the client reports "cannot reach server", that is an
> egress configuration issue to fix in the deployment settings — the
> skill instructs the model to say so and stop, not retry.

## Contents

| Component | Path | Purpose |
|-----------|------|---------|
| Manifest  | [`.claude-plugin/plugin.json`](.claude-plugin/plugin.json) | Plugin identity and metadata |
| Client    | [`scripts/eplus_docs_client.py`](scripts/eplus_docs_client.py) | Stdlib-only HTTP client: submit / status / wait / result / report |
| Skill     | [`skills/document-extraction/SKILL.md`](skills/document-extraction/SKILL.md) | Extraction doctrine: shell-out workflow, no-base64 rule, subagent delegation, failure/egress protocol |
| Agent     | [`agents/doc-extractor.md`](agents/doc-extractor.md) | Haiku subagent that runs submit → wait → result and returns a distilled report |

## Client usage

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/eplus_docs_client.py" submit <file_path> [--note TEXT]
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/eplus_docs_client.py" status <job_id>
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/eplus_docs_client.py" wait <job_id> [--timeout 720]
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/eplus_docs_client.py" result <job_id> [--out FILE]
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/eplus_docs_client.py" report --message TEXT [--category ...] [--details ...]
```

Every command prints exactly one JSON object to stdout; a non-zero exit
code means the JSON carries `status: "error"`. `submit` uploads raw
bytes (never base64); `wait` polls every 20s up to a default 12-minute
timeout, after which the job continues server-side; `result --out`
writes the extracted markdown to a file and keeps only metadata
(including `pages`) on stdout; `report` files a fire-and-forget issue
to the Error Reporting engine (8652).

## Agent tool policy

The `doc-extractor` agent is restricted to `Bash, Glob, Read`. Earlier
versions inherited all tools because a `tools` allowlist would have had
to name both MCP tool-name variants and a mismatch silently blinded the
agent; with the MCP server gone that rationale is gone too, so the
agent now holds only what the shell-out workflow needs.

## Versioning

Explicit semver in `plugin.json` — bump `version` whenever a change
should reach installed machines. v0.2.0 was the restructure from
MCP+hook to the bundled client script; v0.3.0 externalizes the bearer
token to the environment.

> **Auth:** the client reads its bearer token from the `EPLUS_API_TOKEN`
> environment variable — it is **not** hardcoded, so this plugin carries
> no credential in source and is safe to relocate between repos. Provide
> `EPLUS_API_TOKEN` at runtime (e.g. a SessionStart hook writing to
> `CLAUDE_ENV_FILE`, or the deployment environment). Without it the
> client returns a clear "EPLUS_API_TOKEN is not set" error instead of
> calling the VM.
>
> **Security note:** `EPLUS_API_TOKEN` is the shared static credential
> used by all three EPLUS engines (8650/8651/8652), sent over plain HTTP.
> Rotate them together if it leaks, and prefer fronting the VM with HTTPS
> before wide deployment.

## Installation

From the `eplus-claude-plugins` marketplace:

```bash
claude plugin install document-extraction-engine@eplus-claude-plugins
```

Verify: the skills list shows `document-extraction`, the agents list
shows `doc-extractor`, and submitting a local PDF via the client's
`submit` command returns `{status, job_id, ...}` with the follow-up
`wait`/`result --out` producing a markdown file in the scratchpad.
