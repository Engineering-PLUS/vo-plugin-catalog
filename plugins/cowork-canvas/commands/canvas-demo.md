---
description: Open a demo canvas and report what this machine and this host support (the Phase 0 field test)
---

Run the Cowork Canvas field test. Do each step in order and keep the results for the report at the end.
If a step fails, record the exact error text and continue with the next step.

1. Call `canvas_self_check`. Record `ok`, `runtime`, `total_ms`, `server_instance`, and `pdf_render`
   (including any `error_type` and `error`). Also record the full name of the tool you called: a name
   starting with `mcp__canvas__` means the app manages the server; a name starting with `mcp__plugin_`
   means a plugin started it, and no panel will appear.

2. Call `open_canvas` with exactly this:

```json
{
  "title": "Canvas field test",
  "blocks": [
    { "type": "text", "text": "This panel checks that Cowork Canvas works on this machine. Please answer the three questions, then press the two buttons under \"Host report\" at the bottom, and Expand if it is shown." },
    { "type": "tiles", "id": "numbers", "items": [ { "label": "Questions", "value": 3 }, { "label": "Answered", "value": 0 } ] },
    { "type": "steps", "id": "progress", "items": [
      { "label": "Panel opened", "state": "ok" },
      { "label": "Waiting for your answers", "state": "wait" },
      { "label": "Panel updated by Claude" },
      { "label": "Report written" } ] },
    { "type": "question", "id": "see", "kind": "single", "prompt": "How does this panel look?", "options": [ "Clear and readable", "Readable but cramped", "Something is wrong" ] },
    { "type": "question", "id": "go", "kind": "confirm", "prompt": "Approve the test change?", "detail": "Nothing will be changed. This only tests the Approve and Reject buttons." },
    { "type": "question", "id": "note", "kind": "text", "prompt": "Anything that looked wrong? Leave empty if nothing." },
    { "type": "actions", "id": "buttons", "items": [ { "label": "Send Claude a request", "prompt": "Canvas field test: the action button works." } ] }
  ]
}
```

3. Call `await_canvas` with `wait_s: 40`. If the result has `"view_connected": false`, no panel
   appeared: do not wait again, skip to step 5, and say so in the report. Otherwise, if the status is
   `"waiting"`, call it once more. If it is still `"waiting"`, tell the user in one line that the
   questions are in the panel, and end your turn.
   Continue from step 4 when a message starting with `Canvas answer` arrives, or when the user says to
   continue. Record whether the answers arrived through `await_canvas` directly, or only after a
   `Canvas answer` message woke you.

4. Call `await_canvas` with `wait_s: 0` to read all answers, then call `update_canvas` to set the
   "Answered" tile to the number of answered questions and to move the steps on: "Waiting for your
   answers" to `ok`, "Panel updated by Claude" to `ok`, "Report written" to `run`. Ask the user whether
   the panel changed in place without a second panel appearing.

5. Call `get_canvas` and record the `host` section: `host`, `capabilities`, `display_mode`,
   `available_display_modes`, `viewport`, and everything under `tests` (`tool_call_ms`,
   `six_parallel_calls_ms`, `send_message`, `update_model_context`, `display_mode_request`).
   If `host` is missing, record that the panel never reported.

6. Set "Report written" to `ok` with `update_canvas`, then call `close_canvas`.

7. Write the report in chat as a short table: machine name if you know it, self-check result and time,
   whether the panel appeared, whether updates arrived in place, how the answers arrived, whether
   fullscreen, messages and model context were accepted, the tool-call timings, and every error you
   recorded, word for word.
