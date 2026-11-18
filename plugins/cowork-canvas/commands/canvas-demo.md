---
description: Open a demo canvas and report whether the panel works on this machine (the field test)
---

Run the Cowork Canvas field test. Do each step in order and keep the results for the report at the end.
If a step fails, record the exact error text and continue with the next step.

The panel tools come from the `cowork-canvas` connector, a hosted server. Nothing runs on this machine.

1. Check whether you have the tool `open_canvas`. If you do not, the connector is not connected in
   this session: write the report (step 8) saying so, and stop. Do not try to reach the server another
   way.

2. Call `canvas_self_check`. Record `ok`, `server_version`, `revision`, `uptime_s`, and every entry of
   `clients` (`at`, `name`, `version`, `declares_mcp_apps`, `user_agent`). Also record the full name of
   the tool you called, exactly as it appears to you, prefix included: it shows which program holds the
   connection.

3. Call `open_canvas` with exactly this:

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

4. Call `await_canvas` with `wait_s: 40`. If the result has `"view_connected": false`, no panel
   appeared: do not wait again, skip to step 6, and say so in the report. Otherwise, if the status is
   `"waiting"`, call it once more. If it is still `"waiting"`, tell the user in one line that the
   questions are in the panel, and end your turn.
   Continue from step 5 when a message starting with `Canvas answer` arrives, or when the user says to
   continue. Record whether the answers arrived through `await_canvas` directly, or only after a
   `Canvas answer` message woke you, and how many seconds the answering `await_canvas` call took.

5. Call `await_canvas` with `wait_s: 0` to read all answers, then call `update_canvas` to set the
   "Answered" tile to the number of answered questions and to move the steps on: "Waiting for your
   answers" to `ok`, "Panel updated by Claude" to `ok`, "Report written" to `run`. Ask the user whether
   the panel changed in place without a second panel appearing.

6. Call `get_canvas` and record the `host` section: `host`, `capabilities`, `display_mode`,
   `available_display_modes`, `viewport`, and everything under `tests` (`tool_call_ms`,
   `six_parallel_calls_ms`, `send_message`, `update_model_context`, `display_mode_request`).
   If `host` is missing, record that the panel never reported.
   Then set "Report written" to `ok` with `update_canvas`, and call `close_canvas`.

7. Call `canvas_self_check` again and record, in full, every entry of `clients` and the
   `panel_page_reads` list (or that it is empty). An empty list after `open_canvas` means the host never
   fetched the panel page; an entry means it did, so if no panel is visible the fault is after that
   point.

8. Write the report in chat as a short table: machine name if you know it, the tool name prefix,
   whether the canvas tools were available, the server version and revision, the `clients` list, the
   `panel_page_reads` list, whether the panel appeared, whether updates arrived in place, how the
   answers arrived and how long the wait took, whether fullscreen, messages and model context were
   accepted, the tool-call timings, and every error you recorded, word for word.
