#!/bin/sh
# POSIX half of the delete gate. Windows is handled by delete-gate.ps1 (hooks
# run on the HOST in Cowork Chat); this half covers VM/CLI surfaces via
# python, which the sandbox VM ships. Fail-open: no python -> no gate, normal
# permission flow (this hook asks for confirmation, it is not a hard deny).

[ "${OS:-}" = "Windows_NT" ] && exit 0
case "$(uname -s 2>/dev/null)" in
  MINGW*|MSYS*|CYGWIN*) exit 0 ;;
esac

script_dir="${CLAUDE_PLUGIN_ROOT:-$(dirname "$0")/..}/scripts"

for candidate in python3 python; do
  if "$candidate" -c '' >/dev/null 2>&1; then
    exec "$candidate" "$script_dir/delete-gate.py"
  fi
done

cat >/dev/null 2>&1
exit 0
