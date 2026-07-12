#!/usr/bin/env python3
"""Write the GitHub artifact readback failure report."""
from __future__ import annotations

import argparse
import datetime as dt
import os
import pathlib
import re
import subprocess
import sys

SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]+$")
REPORT_ROOT = pathlib.Path("chatgpt_staging/status_reports/chatgpt-github-artifact-readback")


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def clean(value: str, name: str) -> str:
    text = str(value or "").strip()
    if "\n" in text or "\r" in text:
        raise SystemExit(f"{name} must not contain newlines")
    return text


def safe_request_id(value: str) -> str:
    request_id = clean(value, "request_id") or f"artifact_readback_failure_{os.environ.get('GITHUB_RUN_ID', '')}"
    if request_id in {".", ".."} or not SAFE_REQUEST_ID.fullmatch(request_id):
        return "artifact_readback_failure_unknown"
    return request_id


def write_progress(args: argparse.Namespace, request_id: str) -> None:
    subprocess.run(
        [
            sys.executable,
            ".github/scripts/write_chatgpt_progress_report.py",
            "--workflow",
            "chatgpt-github-artifact-readback",
            "--request-id",
            request_id,
            "--request-path",
            args.request_path,
            "--phase",
            "artifact-readback-failure",
            "--result",
            "failure",
            "--artifact-name",
            args.artifact_name,
            "--message",
            "The artifact could not be downloaded, validated, or staged. Read the native failure report and inspect the run URL if needed.",
            "--extra",
            f"source_run_id: {args.source_run_id}",
            "--extra",
            f"artifact_id: {args.artifact_id}",
            "--extra",
            f"artifact_subpath: {args.artifact_subpath or '.'}",
        ],
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request-id", default="")
    parser.add_argument("--request-path", default="")
    parser.add_argument("--source-run-id", default="")
    parser.add_argument("--artifact-name", default="")
    parser.add_argument("--artifact-id", default="")
    parser.add_argument("--artifact-subpath", default="")
    args = parser.parse_args()

    request_id = safe_request_id(args.request_id)
    args.request_path = clean(args.request_path, "request_path")
    args.source_run_id = clean(args.source_run_id, "source_run_id")
    args.artifact_name = clean(args.artifact_name, "artifact_name")
    args.artifact_id = clean(args.artifact_id, "artifact_id")
    args.artifact_subpath = clean(args.artifact_subpath, "artifact_subpath")

    report_dir = REPORT_ROOT / request_id
    report_path = report_dir / "workflow_report.md"
    native_report_path = report_dir / "native_artifact_readback_failure_report.md"
    report_dir.mkdir(parents=True, exist_ok=True)

    write_progress(args, request_id)

    lines = [
        "# Native artifact readback failure report",
        "",
        "## Result",
        "",
        "- workflow: chatgpt-github-artifact-readback",
        "- result: failure",
        "- phase: artifact-readback",
        f"- request_id: {request_id}",
        f"- request_path: {args.request_path or '(direct dispatch inputs)'}",
        f"- source_run_id: {args.source_run_id}",
        f"- artifact_name: {args.artifact_name}",
        f"- artifact_id: {args.artifact_id}",
        f"- artifact_subpath: {args.artifact_subpath or '.'}",
        f"- github_run_id: {os.environ.get('GITHUB_RUN_ID', '')}",
        f"- github_run_attempt: {os.environ.get('GITHUB_RUN_ATTEMPT', '')}",
        f"- github_sha: {os.environ.get('GITHUB_SHA', '')}",
        f"- github_ref: {os.environ.get('GITHUB_REF', '')}",
        f"- report_created_utc: {utc_now()}",
        "",
        "## Troubleshooting notes",
        "",
        "The artifact could not be downloaded, validated, or staged into chatgpt_staging/out. Common causes include wrong run id, wrong artifact name/id, missing artifact_subpath, malformed request JSON, or a permissions/download failure.",
        "",
        "## Next ChatGPT action",
        "",
        "Read this report, inspect the run URL or logs if needed, correct the bounded inputs, and retry with the same source run if appropriate.",
    ]
    native_report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with report_path.open("a", encoding="utf-8") as handle:
        handle.write("\n## Native artifact readback failure report\n\n")
        handle.write(native_report_path.read_text(encoding="utf-8"))
    print(native_report_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
