---
name: canvas-rules
description: This skill should be used before the first Cowork Canvas tool call of a session (open_canvas, update_canvas, await_canvas, get_canvas, close_canvas, canvas_self_check, canvas_host_status), and whenever the user asks to "show me a panel", "put that in the panel", "ask me in the panel", "open the control panel", "show progress while you work", or when a choice, an approval or a set of results would be clearer on screen than in chat. It covers when a panel is worth opening, the one-panel-per-task rule, the block types, how to ask a question and collect the answer, and what to do when the host shows no panel.
---

# Cowork Canvas: rules for using the panel

Cowork Canvas shows the user an interactive panel inside the conversation. You describe the panel as a
list of blocks, change it as the work goes on, and collect what the user answers in it.

## When to open a panel

Open one when the user has to choose, approve or follow something:

- a choice between options, or several questions at once
- an approval after a dry run, with the numbers that matter beside it
- progress of work that takes more than a few steps
- a handful of results the user will act on

Do not open one for a single sentence, a plain answer, or anything the user only reads once. Chat is
better for that.

## The loop

1. **`open_canvas` once per task.** Give it a title and the blocks. It returns a `canvas_id`.
2. **`update_canvas` for every later change** to that panel. Never call `open_canvas` again for the
   same task: each call makes a second panel in the conversation, which confuses the user. When a
   new panel really must take over from an older one of yours, pass `"replaces": "<old canvas_id>"`
   to `open_canvas`; the older panel then tells the user to look at the new one and takes no more
   answers.
3. **To ask something, add a `question` block, then call `await_canvas`.** It waits up to 40 seconds
   and returns `status: "answered"` with the events, or `status: "waiting"`.
4. **On `"waiting"`**, call `await_canvas` once more if the question is quick. Otherwise end your turn
   and tell the user, in one line, that the question is in the panel. When they answer, the panel
   sends you a message that starts with `Canvas answer`. Then call `await_canvas` with `wait_s: 0` to
   read the full answers.
5. **`close_canvas` when the task is done**, so the panel shows that it is finished.

Each event is returned by `await_canvas` once. The `answers` field in every result holds all answers
so far, keyed by question id.

## Blocks

Every block is an object with a `type`. Give a block an `id` when you will change it later or when it
is a question; ids must be unique in a canvas.

| type | fields | notes |
|---|---|---|
| `text` | `text`, `style?` (`"heading"` or `"note"`) | Plain text. A blank line starts a new paragraph. No Markdown or HTML. |
| `tiles` | `items: [{label, value}]` | Two to five headline numbers. |
| `steps` | `items: [{label, state?}]` | `state` is `todo` (default), `run`, `ok`, `wait` or `fail`. |
| `question` | `prompt`, `detail?`, `kind?`, `options?` | See below. |
| `actions` | `items: [{label, prompt}]` | Buttons. A click sends `prompt` to you as a user message. |

Question kinds:

| `kind` | the user sees | the answer value |
|---|---|---|
| `single` (default) | radio buttons and Submit; needs 2 to 12 `options` | `{"choice": "<label>"}` |
| `multi` | checkboxes and Submit; needs 2 to 12 `options` | `{"choices": ["<label>", ...]}` |
| `confirm` | Approve and Reject; `options` are optional and, when given, one must be picked to approve | `{"verdict": "approved" \| "rejected", "choice"?: "<label>"}` |
| `text` | a text box and Submit | `{"text": "..."}` |

An option is a string, or `{"label": "...", "detail": "..."}` for a second line of small text.

## Example

```json
{
  "title": "Remove fittings from Rack Row A",
  "blocks": [
    { "type": "text", "text": "The dry run finished. Nothing has been changed in the model yet." },
    { "type": "tiles", "items": [ { "label": "Fittings to remove", "value": 148 }, { "label": "Group copies", "value": 12 } ] },
    { "type": "steps", "id": "progress", "items": [
      { "label": "Ownership check", "state": "ok" },
      { "label": "Dry run", "state": "ok" },
      { "label": "Your go-ahead", "state": "wait" },
      { "label": "Real run" } ] },
    { "type": "question", "id": "go", "kind": "confirm", "prompt": "Remove the 148 fittings?",
      "options": [ { "label": "All 148", "detail": "Elbows, couplings and end caps" }, { "label": "Couplings only", "detail": "96 elements" } ] }
  ]
}
```

After the answer, show progress with one call:

```json
{ "canvas_id": "c-1a2b3c", "ops": [
  { "op": "patch", "id": "progress", "fields": { "items": [
    { "label": "Ownership check", "state": "ok" }, { "label": "Dry run", "state": "ok" },
    { "label": "Your go-ahead", "state": "ok" }, { "label": "Real run", "state": "run" } ] } }
] }
```

`update_canvas` operations: `set` (replace the block with the same id, or append; `"after": "<id>"`
places a new block), `patch` (change some fields of a block), `remove`, `title`, and `clear_answer`
(lets the user answer a question again). If one operation is wrong, none is applied and the error
says which one.

## Rules

- **An approval in the panel is the user's go-ahead in chat, nothing more.** It does not replace any
  other rule you are working under. For Revit, the ownership check and the dry run still come first,
  and Revit still shows its own approval prompt before the real change.
- **Buttons are requests from the user.** When a message arrives that matches the `prompt` of an
  `actions` button, act on it as if the user had typed it.
- **Keep the panel true.** When a step finishes or fails, update the `steps` block. Do not leave a
  spinner on a step that has ended.
- **Put nothing secret in a panel**: no passwords, tokens or keys.
- **Errors are instructions.** A refused call names the block and the field. Fix that and call again.

## When no panel appears

Some hosts do not show panels. If `await_canvas` returns `"view_connected": false`, or `get_canvas`
shows it a few seconds after opening, tell the user the panel is not available here and ask the
question in chat instead. Do not call `await_canvas` a second time: one wait with no view connected
is the answer.

Whether a panel appears depends on how the plugin was installed, not on anything you do. If none
appears, say so plainly and carry on in chat; do not suggest the user change their setup unless they
ask why.

Canvases are kept on disk for two weeks after their last use, so a panel in an older conversation
still works, and an answer given there is collected by the next `await_canvas` for that `canvas_id`.

## When the canvas tools are missing

The panel tools come from a small server on this machine that the plugin keeps running. In the first
session after sign-in it may not have been running yet when the session started, and then `open_canvas`
and the other tools are not there. Call `canvas_host_status`: it says whether the server runs now. If
it does, tell the user the panel will be available in the next new session, and carry on in chat.

## Checking a new machine

`canvas_self_check` reports whether this machine can run the server's native parts (it renders a PDF
page to an image) and how long that took. Call it when the plugin was just installed, or when a canvas
tool fails with an error that is not about your input.
