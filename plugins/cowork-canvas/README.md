# cowork-canvas

An interactive panel for Claude. Claude opens one panel inside the conversation, keeps it up to date
while it works, and collects what the user answers in it.

> **Published from `plugin/` in the cowork-canvas-mcp repository by `scripts/publish-plugin.ps1`;
> edit there.**

This plugin is the skill and the field-test command. The panel itself comes from the
**`cowork-canvas` connector**, a server hosted on vm-hermes that every seat reaches with a token in
its managed configuration. Nothing runs on the seat and nothing is installed.

## Why the server is not in the plugin

Tested in Cowork on 2026-11-18 (Claude Desktop 5.11492.5, Claude Code 2.1.325): a server that a
plugin declares, local or remote, is connected by Claude Code, which does not show panels. A panel
appears only for a connector the desktop app itself holds. Versions 0.1.0 to 0.3.0 of this plugin
carried a local server and never showed a panel for that reason.

## Skill and command

| Name | Use it for |
|---|---|
| `canvas-rules` (skill) | Start here: when a panel is worth opening, one panel per task, the block types, asking and collecting an answer, what to do when no panel appears |
| `/canvas-demo` (command) | The field test: opens a demo panel and reports who connected, whether the panel appeared and what the host supports |

## Tools (from the connector)

| Tool | Called by | Does |
|---|---|---|
| `open_canvas` | Claude | Opens a panel from a title and blocks; returns a `canvas_id`. The only tool with a panel. |
| `update_canvas` | Claude | Changes an open panel: set, patch or remove a block, change the title, reopen a question. |
| `await_canvas` | Claude | Waits up to 40 s for the user's answers and button clicks. |
| `get_canvas` | Claude | What a panel shows now, the answers so far, and what the host reported about itself. |
| `close_canvas` | Claude | Marks a panel finished. |
| `canvas_self_check` | Claude | The server's version, who connected and whether each can show panels, recent fetches of the panel page. |
| `canvas_sync` | the panel | Long poll for changes, up to 25 s. |
| `canvas_event` | the panel | Stores an answer, a button click or the host report. |

## Coming from 0.3.0

Only the one test seat ran 0.3.0. On that seat the background `dotnet` process ends when you sign
out of Windows, and the folder `%LOCALAPPDATA%\cowork-canvas` (about 25 MB) can be deleted.
