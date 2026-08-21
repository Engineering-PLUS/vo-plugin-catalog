---
name: aec-verify
description: Use this skill to verify that the eplus-simple-plugin is active and the AEC environment is prepared in the Cowork VM.
---

# AEC Environment Verification

When this skill is invoked, confirm to the user that the **eplus-simple-plugin** is loaded
and running inside the Cowork VM.

Steps:

1. Confirm the plugin is loaded by acknowledging this skill was reachable.
2. Report the current AEC project stage. The `SessionStart` hook injects this as
   additional context at the start of the session (default: `drafting`).
3. If a directory survey is needed, mention that the `project-folder-inspector`
   subagent is available for delegation (read-only inventory and reporting).

Keep the confirmation short — this is a smoke test that the plugin installed and
activated correctly.
