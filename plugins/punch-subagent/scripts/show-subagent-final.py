#!/usr/bin/env python3
"""SubagentStop hook -- surface the subagent's final message to the user.

Cowork shows that a subagent was spawned and running, and the main model relays
a paraphrase, but the subagent's own final message isn't rendered inline. This
hook fixes that: on SubagentStop it reads `last_assistant_message` (provided
directly in the SubagentStop input -- no transcript parsing) and emits it as a
`systemMessage`, which renders as a visible hook block in the chat.

ONLY systemMessage -- no additionalContext, no decision fields. (An imperative
additionalContext on a stop/tool turn reads as prompt injection and can be
blocked by the auto-mode classifier; and on SubagentStop additionalContext also
continues the turn. systemMessage carries no instruction, so it just displays.)

Single `python` command -- no shell polyglot, so no foreign-shell noise.
Disable with EPLUS_NO_SUBAGENT_ECHO=1.
"""
import json
import os
import sys

MAX_CHARS = 6000


def main():
    if os.environ.get("EPLUS_NO_SUBAGENT_ECHO", ""):
        return
    raw = sys.stdin.buffer.read()
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except Exception:
        return
    if not isinstance(data, dict):
        return

    msg = data.get("last_assistant_message")
    if not isinstance(msg, str) or not msg.strip():
        return
    agent = data.get("agent_type") or "subagent"

    body = msg.strip()
    if len(body) > MAX_CHARS:
        body = body[:MAX_CHARS] + "\n… [final message truncated]"

    out = {"systemMessage": "[" + agent + " — final message]\n\n" + body}
    sys.stdout.write(json.dumps(out))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
