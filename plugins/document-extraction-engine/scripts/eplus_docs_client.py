#!/usr/bin/env python3
"""EPLUS document-analysis + error-reporting client (stdlib only).

Ships inside the Cowork plugin; the model runs it via Bash. Talks plain HTTP
to the EPLUS VM (requires 20.9.42.66 in the deployment's allowed egress
hosts). Every command prints one JSON object to stdout.

Usage:
  eplus_docs_client.py submit <file_path> [--note TEXT]
  eplus_docs_client.py status <job_id>
  eplus_docs_client.py wait <job_id> [--timeout 720]   # poll until done
  eplus_docs_client.py result <job_id> [--out FILE]    # markdown to stdout or FILE
  eplus_docs_client.py report --message TEXT [--category tool_failure]
        [--tool-name X] [--server-name X] [--severity medium] [--details TEXT]
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

DOCS_BASE = "http://20.9.42.66:8651"
REPORT_BASE = "http://20.9.42.66:8652"
# Bearer token is read from the environment, never hardcoded, so this script
# can live in any repo without carrying the shared EPLUS credential. Provide it
# via EPLUS_API_TOKEN (e.g. a SessionStart hook writing to CLAUDE_ENV_FILE, or
# the deployment's environment).
TOKEN = os.environ.get("EPLUS_API_TOKEN", "")
POLL_S = 20


def call(url: str, data: bytes | None = None, headers: dict | None = None,
         method: str = "GET", timeout: int = 310) -> dict:
    if not TOKEN:
        return {"status": "error",
                "message": "EPLUS_API_TOKEN is not set in the environment; the "
                           "document-extraction client cannot authenticate to "
                           "the EPLUS VM. Set EPLUS_API_TOKEN and retry."}
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Authorization": "Bearer " + TOKEN, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8"))
        except Exception:  # noqa: BLE001
            return {"status": "error", "message": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:  # noqa: BLE001
        return {"status": "error",
                "message": f"cannot reach server ({e}). If this is a sandbox, "
                           "20.9.42.66 may be missing from allowed egress hosts."}


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("submit")
    p.add_argument("file_path")
    p.add_argument("--note", default="")
    p = sub.add_parser("status")
    p.add_argument("job_id")
    p = sub.add_parser("wait")
    p.add_argument("job_id")
    p.add_argument("--timeout", type=int, default=720)
    p = sub.add_parser("result")
    p.add_argument("job_id")
    p.add_argument("--out", default="")
    p = sub.add_parser("report")
    p.add_argument("--message", required=True)
    p.add_argument("--category", default="tool_failure")
    p.add_argument("--tool-name", default="")
    p.add_argument("--server-name", default="")
    p.add_argument("--severity", default="medium")
    p.add_argument("--details", default="")
    args = ap.parse_args()

    if args.cmd == "submit":
        if not os.path.isfile(args.file_path):
            out = {"status": "error", "message": f"file not found: {args.file_path}"}
        else:
            with open(args.file_path, "rb") as f:
                data = f.read()
            out = call(f"{DOCS_BASE}/upload", data=data, method="POST", headers={
                "X-Filename": os.path.basename(args.file_path),
                "X-Note": args.note,
                "Content-Type": "application/octet-stream"})
    elif args.cmd == "status":
        out = call(f"{DOCS_BASE}/status/{args.job_id}")
    elif args.cmd == "wait":
        start = time.monotonic()
        out = call(f"{DOCS_BASE}/status/{args.job_id}")
        while (out.get("status") in ("queued", "running")
               and time.monotonic() - start < args.timeout):
            time.sleep(POLL_S)
            out = call(f"{DOCS_BASE}/status/{args.job_id}")
        if out.get("status") in ("queued", "running"):
            out["message"] = (f"still {out['status']} after {args.timeout}s — job "
                              "continues server-side; check again later with 'status'.")
    elif args.cmd == "result":
        out = call(f"{DOCS_BASE}/result/{args.job_id}")
        if args.out and "markdown" in out:
            with open(args.out, "w", encoding="utf-8") as f:
                f.write(out.pop("markdown"))
            out["saved_to"] = args.out
    else:  # report
        body = json.dumps({
            "message": args.message, "category": args.category,
            "tool_name": args.tool_name, "server_name": args.server_name,
            "severity": args.severity, "details": args.details}).encode("utf-8")
        out = call(f"{REPORT_BASE}/report", data=body, method="POST",
                   headers={"Content-Type": "application/json"})

    print(json.dumps(out, ensure_ascii=False))
    return 0 if out.get("status") not in ("error",) else 1


if __name__ == "__main__":
    sys.exit(main())
