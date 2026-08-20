#!/usr/bin/env python3
"""
Systemic hook-lab test suite.

Replays EVERY fixture in hook-testing-plugin/skills/hook-lab/fixtures/ through
whatever handler(s) hooks/hooks.json actually registers for that event -- the
same reconstruction hook-lab's SKILL.md does one event at a time, but for all
31 events in a single run with a pass/fail verdict per event, so a fix can be
regression-tested across the whole hook surface instead of eyeballing one
event at a time.

For each event this checks THREE things independently, then combines them
into a verdict:
  1. Did the configured handler(s) run without unexpectedly blocking/erroring?
     (exit code, stdout, stderr all captured)
  2. Did the generic logger actually persist the payload? (log file grows by
     exactly one line, and that line matches the fixture)
  3. Is anything registered for this event at all? (WorktreeCreate is
     deliberately NOT wired live, per the plugin's own warning -- reported as
     NOT_WIRED, not a failure)

Usage:
  python3 run_hook_suite.py <plugin_root> <report_dir>

<plugin_root>  path to hook-testing-plugin (contains hooks/hooks.json, scripts/,
               skills/hook-lab/fixtures/)
<report_dir>   where to write suite_results.json, suite_report.md, and a
               per-event/ directory with raw stdout/stderr/log captures.

Each run uses a fresh, isolated working directory (a temp dir under
<report_dir>/_workdir/) as $PWD for every handler invocation, so log-growth
checks start from a known-empty state and aren't contaminated by logs from
earlier manual testing or previous suite runs.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def load_hooks_json(plugin_root: Path) -> dict:
    with open(plugin_root / "hooks" / "hooks.json", "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_args(args, plugin_root: Path):
    return [a.replace("${CLAUDE_PLUGIN_ROOT}", str(plugin_root)) for a in args]


def run_one_handler(command, args, fixture_bytes, cwd, env):
    # Exec form (args present): spawn the executable directly, like Claude Code.
    # Shell form (no args): the command string goes to a shell. Claude Code
    # routes shell form to sh -c (POSIX), Git Bash (Windows with git), or
    # PowerShell (Windows without) -- NEVER cmd.exe, so shell=True on Windows
    # (which uses cmd.exe) would test the wrong thing. Emulate the real router.
    if args:
        invocation = [command] + args
    else:
        import shutil
        sh = shutil.which("sh")
        if sh:
            invocation = [sh, "-c", command]
        else:
            pwsh = shutil.which("pwsh") or shutil.which("powershell")
            if not pwsh:
                raise RuntimeError("no sh or powershell available to run shell-form hook")
            invocation = [pwsh, "-NoProfile", "-Command", command]
    proc = subprocess.run(
        invocation,
        input=fixture_bytes,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    return proc.returncode, proc.stdout, proc.stderr


def find_log_file(cwd_root: Path, session_id: str, event_name: str):
    return cwd_root / session_id / f"{event_name}.jsonl"


def main():
    if len(sys.argv) != 3:
        print("usage: run_hook_suite.py <plugin_root> <report_dir>", file=sys.stderr)
        sys.exit(1)

    plugin_root = Path(sys.argv[1]).resolve()
    report_dir = Path(sys.argv[2]).resolve()
    per_event_dir = report_dir / "per-event"
    per_event_dir.mkdir(parents=True, exist_ok=True)

    fixtures_dir = plugin_root / "skills" / "hook-lab" / "fixtures"
    hooks_cfg = load_hooks_json(plugin_root)

    workdir_root = report_dir / "_workdir"
    workdir_root.mkdir(parents=True, exist_ok=True)

    results = []

    fixture_files = sorted(fixtures_dir.glob("*.json"))
    for fixture_path in fixture_files:
        event_name = fixture_path.stem
        fixture_bytes = fixture_path.read_bytes()
        try:
            fixture_obj = json.loads(fixture_bytes)
        except Exception as e:
            results.append({
                "event": event_name,
                "verdict": "FIXTURE_INVALID",
                "detail": f"fixture is not valid JSON: {e}",
            })
            continue

        session_id = fixture_obj.get("session_id", "unknown-session")
        handler_groups = hooks_cfg.get("hooks", {}).get(event_name, [])

        if not handler_groups:
            results.append({
                "event": event_name,
                "verdict": "NOT_WIRED",
                "detail": "no handler registered in hooks.json for this event (expected for WorktreeCreate)",
                "session_id": session_id,
            })
            continue

        # Fresh, isolated cwd per event so log-growth checks start from zero.
        event_workdir = workdir_root / event_name
        event_workdir.mkdir(parents=True, exist_ok=True)

        env = dict(os.environ)
        for var in ("CLAUDE_HOOKLAB_LOG_ROOT", "CLAUDE_PLUGIN_DATA", "CLAUDE_PROJECT_DIR"):
            env.pop(var, None)
        env["PWD"] = str(event_workdir)

        cwd_root = event_workdir / ".hook-lab" / "events"
        log_file = find_log_file(cwd_root, session_id, event_name)
        lines_before = 0
        if log_file.exists():
            lines_before = sum(1 for _ in log_file.open("r", encoding="utf-8"))

        handler_results = []
        overall_ok = True
        for group in handler_groups:
            for handler in group.get("hooks", []):
                if handler.get("type") != "command":
                    continue
                command = handler["command"].replace("${CLAUDE_PLUGIN_ROOT}", str(plugin_root))
                args = resolve_args(handler.get("args", []), plugin_root)
                try:
                    code, out, err = run_one_handler(command, args, fixture_bytes, str(event_workdir), env)
                except subprocess.TimeoutExpired:
                    overall_ok = False
                    handler_results.append({
                        "command": [command] + args,
                        "error": "TIMEOUT (30s)",
                    })
                    continue

                stdout_text = out.decode("utf-8", "replace")
                stderr_text = err.decode("utf-8", "replace")
                stdout_stripped = stdout_text.lstrip()
                looks_like_json = stdout_stripped.startswith("{")

                # stdout must be empty OR a JSON object limited to display/
                # context fields: top-level systemMessage, plus
                # hookSpecificOutput carrying only hookEventName +
                # additionalContext (relay channel) or displayContent
                # (MessageDisplay banner). Decision fields -- decision,
                # permissionDecision, continue, updatedInput, etc. -- or junk
                # text remain defects in a hook that must never influence
                # outcomes. (Channels added per beautiful-vigilant-bohr
                # field report: Cowork never renders systemMessage.)
                stdout_safe = True
                if stdout_text.strip():
                    try:
                        stdout_obj = json.loads(stdout_text)
                        stdout_safe = (
                            isinstance(stdout_obj, dict)
                            and set(stdout_obj.keys()) <= {"systemMessage", "hookSpecificOutput"}
                        )
                        if stdout_safe and "hookSpecificOutput" in stdout_obj:
                            hso = stdout_obj["hookSpecificOutput"]
                            stdout_safe = (
                                isinstance(hso, dict)
                                and set(hso.keys()) <= {
                                    "hookEventName", "additionalContext", "displayContent",
                                    # SessionStart visibility experiments: a user
                                    # turn and a UI title, not decision control.
                                    "initialUserMessage", "sessionTitle",
                                }
                            )
                            if stdout_safe and ("initialUserMessage" in hso or "sessionTitle" in hso):
                                stdout_safe = stdout_obj["hookSpecificOutput"]["hookEventName"] == "SessionStart"
                    except Exception:
                        stdout_safe = False

                handler_ok = (code == 0 and stdout_safe and stderr_text == "")
                if code != 0:
                    overall_ok = False
                elif not stdout_safe:
                    overall_ok = False
                elif stderr_text != "":
                    # non-fatal per docs (stderr on exit 0 never reaches Claude),
                    # but worth surfacing for a display-only hook.
                    pass

                handler_results.append({
                    "command": [command] + args,
                    "exit_code": code,
                    "stdout": stdout_text,
                    "stdout_is_json": looks_like_json,
                    "stdout_safe": stdout_safe,
                    "stderr": stderr_text,
                    "handler_clean": handler_ok,
                })

        lines_after = 0
        last_line_matches = False
        if log_file.exists():
            log_lines = log_file.open("r", encoding="utf-8").readlines()
            lines_after = len(log_lines)
            if log_lines:
                try:
                    last_obj = json.loads(log_lines[-1])
                    last_line_matches = (last_obj == fixture_obj)
                except Exception:
                    last_line_matches = False

        log_grew_by_one = (lines_after == lines_before + 1)

        unsafe_stdout = any(not h.get("stdout_safe", True) for h in handler_results)
        if any(h.get("exit_code", 0) != 0 or "error" in h for h in handler_results):
            verdict = "FAIL_HANDLER_ERROR"
        elif unsafe_stdout:
            verdict = "FAIL_UNSAFE_STDOUT"
        elif not log_file.exists():
            verdict = "FAIL_NO_LOG_WRITTEN"
        elif not log_grew_by_one:
            verdict = "FAIL_LOG_GROWTH_MISMATCH"
        elif not last_line_matches:
            verdict = "FAIL_LOG_CONTENT_MISMATCH"
        else:
            verdict = "PASS"

        results.append({
            "event": event_name,
            "verdict": verdict,
            "session_id": session_id,
            "handlers": handler_results,
            "log_file": str(log_file),
            "lines_before": lines_before,
            "lines_after": lines_after,
            "last_line_matches_fixture": last_line_matches,
        })

        with open(per_event_dir / f"{event_name}.json", "w", encoding="utf-8") as f:
            json.dump(results[-1], f, indent=2)

    # ---- summary ----
    counts = {}
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1

    with open(report_dir / "suite_results.json", "w", encoding="utf-8") as f:
        json.dump({"summary": counts, "results": results}, f, indent=2)

    lines = []
    lines.append("# hook-lab systemic test suite -- results\n")
    lines.append(f"Plugin root tested: `{plugin_root}`\n")
    lines.append(f"Events checked: {len(results)}\n")
    lines.append("## Summary\n")
    lines.append("| Verdict | Count |")
    lines.append("| --- | --- |")
    for verdict, count in sorted(counts.items()):
        lines.append(f"| {verdict} | {count} |")
    lines.append("")
    lines.append("## Per-event detail\n")
    lines.append("| Event | Verdict | Log lines (before -> after) | Notes |")
    lines.append("| --- | --- | --- | --- |")
    for r in results:
        event = r["event"]
        verdict = r["verdict"]
        if verdict == "NOT_WIRED":
            lines.append(f"| {event} | {verdict} | n/a | {r['detail']} |")
            continue
        if verdict == "FIXTURE_INVALID":
            lines.append(f"| {event} | {verdict} | n/a | {r['detail']} |")
            continue
        before_after = f"{r['lines_before']} -> {r['lines_after']}"
        note = ""
        for h in r["handlers"]:
            if "error" in h:
                note = h["error"]
            elif h["exit_code"] != 0:
                note = f"exit={h['exit_code']} stderr={h['stderr'][:120]!r}"
            elif h["stderr"]:
                note = f"stderr (non-blocking): {h['stderr'][:120]!r}"
        lines.append(f"| {event} | {verdict} | {before_after} | {note} |")

    with open(report_dir / "suite_report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(json.dumps({"summary": counts}, indent=2))


if __name__ == "__main__":
    main()
