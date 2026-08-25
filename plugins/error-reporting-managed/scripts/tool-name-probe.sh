#!/bin/sh
# POSIX half of the tool-name probe (see tool-name-probe.py). Windows is handled
# by tool-name-probe.ps1 (hooks run on the HOST in Cowork Chat); this half
# covers VM/CLI via python. Fail-open: no python -> no output, normal flow.

# Windows guard: exit before reading stdin so the .ps1 (runs first in the
# polyglot command) gets the full payload and this half never double-fires.
[ "${OS:-}" = "Windows_NT" ] && exit 0
case "$(uname -s 2>/dev/null)" in
  MINGW*|MSYS*|CYGWIN*) exit 0 ;;
esac

script_dir="${CLAUDE_PLUGIN_ROOT:-$(dirname "$0")/..}/scripts"

for candidate in python3 python; do
  if "$candidate" -c '' >/dev/null 2>&1; then
    exec "$candidate" "$script_dir/tool-name-probe.py"
  fi
done

cat >/dev/null 2>&1
exit 0
