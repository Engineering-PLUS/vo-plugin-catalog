# error-reporting-managed  (vo test plugin)

A copy of the production `error-reporting` plugin with its **`.mcp.json`
removed**, used to test the *managed MCP server* delivery route: the
error-reporting engine is declared once in the bootstrap `managedMcpServers`
config instead of being bundled in the plugin, so no bearer token ever lives in
a repo.

This plugin ships **only a skill and a hook** — no MCP server. It's the
autocad-style pattern (server delivered via managed connection; plugin carries
the skills/hooks that reference it by name).

## The experiment: does the tool name change?

| Delivery route | Expected `report_issue` tool name |
|---|---|
| Bundled in a plugin's `.mcp.json` (production error-reporting) | `mcp__plugin_error-reporting_error-reporting__report_issue` |
| Bootstrap `managedMcpServers` (this test) | `mcp__error-reporting__report_issue` |

The `tool-name-probe` `PreToolUse` hook prints the **exact** tool name whenever
`report_issue` is invoked, as a **`systemMessage`** — which renders directly in
the chat as a hook code block. Disable it with `EPLUS_NO_TOOLNAME_PROBE=1`.

> **Why systemMessage and not additionalContext:** an earlier version injected
> an imperative `additionalContext` ("quote this verbatim…"). On a PreToolUse
> turn that reads as prompt injection: the **auto-mode classifier blocked the
> `report_issue` call outright** ("Blocked by classifier"), and the model
> independently flagged it as an injected instruction (observed 2026-08-25, two
> session exports). `systemMessage` carries no instruction to the model, so it
> is safe and still visible.

> **Single-interpreter command:** the hook runs `python <script>` directly, not
> a `powershell …; sh …` polyglot. PowerShell 5.1 can't suppress a
> "command not found" for the foreign interpreter, so a polyglot leaves a
> `'sh' is not recognized` line on every call on a Windows host. One `python`
> command avoids that entirely (requires python on PATH — host and VM).

## Bootstrap config to add (managedMcpServers)

Add the error-reporting engine as a managed server. Static-header form first
(token lives in the managed config, never a repo):

```json
{
  "managedMcpServers": [
    {
      "name": "error-reporting",
      "transport": "sse",
      "url": "http://20.9.42.66:8652/sse",
      "headers": { "Authorization": "Bearer <the-shared-bearer-token>" }
    }
  ],
  "coworkEgressAllowedHosts": ["20.9.42.66"]
}
```

- **`name: "error-reporting"`** is what makes the tool resolve as
  `mcp__error-reporting__report_issue`. Change the name and the tool namespace
  changes with it.
- `coworkEgressAllowedHosts` must include `20.9.42.66` or the SSE connection
  can't leave the sandbox.
- Later, swap `headers` for `headersHelper` (a command that returns the header
  dynamically) so the token isn't static in the config either — your schema
  supports it.

## Test procedure (Cowork machine)

1. Add the `managedMcpServers` block above to the bootstrap config; ensure
   `20.9.42.66` is in `coworkEgressAllowedHosts`.
2. Enable `error-reporting-managed` (it's `defaultEnabled: false`).
3. Confirm the managed `error-reporting` server connects and its
   `report_issue` tool is available.
4. Call `report_issue` with `category: "other"`,
   `message: "managed-server tool-name probe"`.
5. Read the reply: the `tool-name-probe` hook will have surfaced the exact tool
   name. **Compare it** against the production plugin's bundled form.
   - Managed → `mcp__error-reporting__report_issue`
   - Bundled → `mcp__plugin_error-reporting_error-reporting__report_issue`

If the names differ, any skill/hook that hardcodes one form needs to tolerate
both (the production skill already does) — that's the key thing this test
confirms before we strip `.mcp.json` from the real plugins.
