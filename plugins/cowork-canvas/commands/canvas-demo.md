---
description: Open a demo canvas and report what this machine and this host support (the field test)
---

Run the Cowork Canvas field test. Do each step in order and keep the results for the report at the end.
If a step fails, record the exact error text and continue with the next step.

The plugin has two servers. `canvas` has the panel tools (`open_canvas` and the others) and is reached
over HTTP on this machine. `canvas-host` has one tool, `canvas_host_status`, and keeps `canvas` running.

1. Call `canvas_host_status`. Record `start`, `running`, the whole `server` object, `this_client`, and
   every entry of `http_clients` (`at`, `name`, `version`, `declares_mcp_apps`, `user_agent`, `origin`).
   Also record the full name of the tool you called, exactly as it appears to you, prefix included.

2. Check whether you have the tool `open_canvas`. If you do not have it, the `canvas` server did not
   connect in this session: skip to step 8 and say so in the report. Do not try to reach the server
   another way.

3. Call `canvas_self_check`. Record `ok`, `runtime`, `total_ms`, `transport`, `base_directory`, the whole
   `client` object (`name`, `version`, `declares_mcp_apps`, `mcp_apps_capability`), and `pdf_render`
   (including any `error_type` and `error`). Record the full name of this tool too, prefix included: it
   shows which program holds the connection to `canvas`.

4. Call `open_canvas` with exactly this:

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

5. Call `await_canvas` with `wait_s: 40`. If the result has `"view_connected": false`, no panel
   appeared: do not wait again, skip to step 7, and say so in the report. Otherwise, if the status is
   `"waiting"`, call it once more. If it is still `"waiting"`, tell the user in one line that the
   questions are in the panel, and end your turn.
   Continue from step 6 when a message starting with `Canvas answer` arrives, or when the user says to
   continue. Record whether the answers arrived through `await_canvas` directly, or only after a
   `Canvas answer` message woke you.

6. Call `await_canvas` with `wait_s: 0` to read all answers, then call `update_canvas` to set the
   "Answered" tile to the number of answered questions and to move the steps on: "Waiting for your
   answers" to `ok`, "Panel updated by Claude" to `ok`, "Report written" to `run`. Ask the user whether
   the panel changed in place without a second panel appearing.

7. Call `get_canvas` and record the `host` section: `host`, `capabilities`, `display_mode`,
   `available_display_modes`, `viewport`, and everything under `tests` (`tool_call_ms`,
   `six_parallel_calls_ms`, `send_message`, `update_model_context`, `display_mode_request`).
   If `host` is missing, record that the panel never reported.
   Then set "Report written" to `ok` with `update_canvas`, and call `close_canvas`.

8. Call `canvas_host_status` again and record, in full: every entry of `http_clients`, the
   `panel_page_reads` list (or that it is empty), and from `http_requests` every entry whose `rpc` is
   `initialize` or `resources/read`, plus any entry with an `error` or a `status` that is not 200 or 202.

9. Write the report in chat as a short table: machine name if you know it, the two tool name prefixes,
   whether the `canvas` tools were available, the `server` object, the `http_clients` list, the `client`
   object and `transport` from the self-check, the self-check result and time, the `panel_page_reads`
   list, whether the panel appeared, whether updates arrived in place, how the answers arrived, whether
   fullscreen, messages and model context were accepted, the tool-call timings, and every error you
   recorded, word for word.
