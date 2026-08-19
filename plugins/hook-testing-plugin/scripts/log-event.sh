#!/bin/sh
# POSIX half of the logger pair. hooks.json runs BOTH this and log-event.ps1
# from one shell-form command; exactly one does the work per platform:
#   - Windows (any shell): log-event.ps1 handles it; this script exits 0
#     immediately via the OS guard below, BEFORE reading stdin, so Git Bash
#     machines don't double-log and the .ps1 gets the whole payload.
#   - POSIX (Cowork VM, Linux/macOS CLI): this script forwards stdin to
#     log-event.py via whichever python exists (VM ships python3 AND python).
# Never exits non-zero; hooks.json also appends `; exit 0` as a backstop.

# Windows guard: $OS is set to Windows_NT by the OS and inherited by Git Bash.
[ "${OS:-}" = "Windows_NT" ] && exit 0
case "$(uname -s 2>/dev/null)" in
  MINGW*|MSYS*|CYGWIN*) exit 0 ;;
esac

script_dir="${CLAUDE_PLUGIN_ROOT:-$(dirname "$0")/..}/scripts"

for candidate in python3 python; do
  if "$candidate" -c '' >/dev/null 2>&1; then
    exec "$candidate" "$script_dir/log-event.py"
  fi
done

# No python at all: swallow stdin so the hook runner isn't left with a broken
# pipe, and exit clean. The event simply isn't logged on this machine.
cat >/dev/null 2>&1
exit 0
