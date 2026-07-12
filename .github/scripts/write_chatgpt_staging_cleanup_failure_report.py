#!/usr/bin/env python3
"""Write the ChatGPT staging cleanup failure report and export report paths."""
from __future__ import annotations

import argparse
import datetime as dt
import os
import pathlib
import re

SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def safe_report_id(request_filter: str) -> str:
    report_id = request_filter or f"cleanup_failure_{os.environ.get('GITHUB_RUN_ID', '')}"
    if not report_id or not SAFE_ID_RE.fullmatch(report_id) or report_id in {".", ".."}:
        return "unsafe_or_unknown"
    return report_id


def append_env(path: pathlib.Path, values: dict[str, str]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request-id-filter", default="")
    parser.add_argument("--github-env", default=os.environ.get("GITHUB_ENV", ""))
    args = parser.parse_args()

    report_id = safe_report_id(args.request_id_filter)
    report_dir = pathlib.Path("chatgpt_staging/status_reports/chatgpt-staging-cleanup") / report_id
    report_path = report_dir / "workflow_report.md"
    report_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "# ChatGPT workflow report",
        "",
        "## Result",
        "",
        "- workflow: chatgpt-staging-cleanup",
        "- result: failure",
        "- phase: cleanup",
        f"- request_id_filter: {args.request_id_filter}",
        f"- github_run_id: {os.environ.get('GITHUB_RUN_ID', '')}",
        f"- github_sha: {os.environ.get('GITHUB_SHA', '')}",
        f"- github_ref: {os.environ.get('GITHUB_REF', '')}",
        f"- report_created_utc: {utc_now()}",
        "",
        "## Troubleshooting notes",
        "",
        "Cleanup failed or failed closed. Inspect the GitHub Actions run log for malformed marker details, wrong/missing schema, invalid boolean fields, request_id validation, or unsafe path validation errors.",
        "",
        "## Next ChatGPT action",
        "",
        "Read this report, inspect run logs if needed, fix or regenerate the cleanup marker, and update Airtable.",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if args.github_env:
        append_env(pathlib.Path(args.github_env), {
            "REPORT_DIR": report_dir.as_posix(),
            "REPORT_PATH": report_path.as_posix(),
            "REPORT_PUSHED": "false",
        })
    print(report_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
