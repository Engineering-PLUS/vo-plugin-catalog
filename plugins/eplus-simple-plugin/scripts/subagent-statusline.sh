#!/bin/sh
# Renders one row per visible subagent in the agent panel below the prompt.
#
# stdin  : a single JSON object with a `tasks` array (plus `columns` and the
#          base hook fields). Each task carries id, name, type, status,
#          description, label, startTime, model, effort, contextWindowSize,
#          tokenCount, tokenSamples, cwd.
# stdout : one JSON line per row to override, {"id": ..., "content": ...}.
#          Rows we don't emit keep their default rendering.
#
# Runs once per refresh tick, so it must stay cheap and must never block.
# If no JSON parser is available we exit silently and every row falls back to
# the default `name - description - token count` rendering.

set -u

payload=$(cat)

render_py='
import json, sys

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)

for task in data.get("tasks", []):
    task_id = task.get("id")
    if not task_id:
        continue

    parts = [task.get("name") or task.get("type") or "subagent"]

    status = task.get("status")
    if status:
        parts.append(str(status))

    desc = (task.get("description") or "").strip().replace("\n", " ")
    if desc:
        parts.append(desc[:47] + "…" if len(desc) > 48 else desc)

    tokens = task.get("tokenCount")
    window = task.get("contextWindowSize")
    if isinstance(tokens, int):
        if isinstance(window, int) and window > 0:
            parts.append("{:,} tok ({}%)".format(tokens, round(100.0 * tokens / window)))
        else:
            parts.append("{:,} tok".format(tokens))

    model = task.get("model")
    if model:
        parts.append(str(model))

    print(json.dumps({"id": task_id, "content": " · ".join(parts)}))
'

# Probe by executing, not by `command -v`: on some hosts python3 resolves to a
# stub that is present on PATH but fails when run.
if python3 -c '' >/dev/null 2>&1; then
  printf '%s' "$payload" | python3 -c "$render_py"
elif command -v jq >/dev/null 2>&1; then
  printf '%s' "$payload" | jq -c '
    .tasks[]?
    | select(.id)
    | {
        id: .id,
        content: (
          [ (.name // .type // "subagent")
          , (.status // empty)
          , (.description // empty)
          , (if .tokenCount then "\(.tokenCount) tok" else empty end)
          , (.model // empty)
          ] | join(" · ")
        )
      }'
fi

exit 0
