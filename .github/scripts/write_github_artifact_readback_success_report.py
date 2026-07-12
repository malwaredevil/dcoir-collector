#!/usr/bin/env python3
"""Write the final GitHub artifact readback success report."""
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
OUT_ROOT = pathlib.Path("chatgpt_staging/out")


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def clean(value: str, name: str) -> str:
    text = str(value or "").strip()
    if "\n" in text or "\r" in text:
        raise SystemExit(f"{name} must not contain newlines")
    return text


def validate_request_id(request_id: str) -> str:
    request_id = clean(request_id, "request_id")
    if request_id in {".", ".."} or not SAFE_REQUEST_ID.fullmatch(request_id):
        raise SystemExit(f"Unsafe request_id: {request_id!r}")
    return request_id


def validate_report_paths(request_id: str, out_dir: pathlib.Path, report_dir: pathlib.Path) -> None:
    resolved_out_dir = out_dir.resolve(strict=False)
    resolved_report_dir = report_dir.resolve(strict=False)
    if resolved_out_dir.parent != OUT_ROOT.resolve(strict=False) or resolved_out_dir.name != request_id:
        raise SystemExit(f"Refusing unsafe out_dir outside {OUT_ROOT}: {out_dir}")
    if resolved_report_dir.parent != REPORT_ROOT.resolve(strict=False) or resolved_report_dir.name != request_id:
        raise SystemExit(f"Refusing unsafe report_dir outside {REPORT_ROOT}: {report_dir}")


def write_progress(args: argparse.Namespace) -> None:
    subprocess.run(
        [
            sys.executable,
            ".github/scripts/write_chatgpt_progress_report.py",
            "--workflow",
            "chatgpt-github-artifact-readback",
            "--request-id",
            args.request_id,
            "--request-path",
            args.request_path,
            "--phase",
            "artifact-staged",
            "--result",
            "success",
            "--artifact-name",
            args.artifact_name,
            "--message",
            "The artifact was downloaded, extracted, and staged successfully for ChatGPT readback.",
            "--extra",
            f"source_run_id: {args.source_run_id}",
            "--extra",
            f"artifact_id: {args.artifact_id}",
            "--extra",
            f"artifact_subpath: {args.artifact_subpath or '.'}",
            "--extra",
            f"staged_manifest_md: {args.out_dir}/artifact_manifest.md",
        ],
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--request-path", default="")
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--artifact-name", default="")
    parser.add_argument("--artifact-id", default="")
    parser.add_argument("--artifact-subpath", default="")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--report-dir", required=True)
    args = parser.parse_args()

    args.request_id = validate_request_id(args.request_id)
    args.request_path = clean(args.request_path, "request_path")
    args.source_run_id = clean(args.source_run_id, "source_run_id")
    args.artifact_name = clean(args.artifact_name, "artifact_name")
    args.artifact_id = clean(args.artifact_id, "artifact_id")
    args.artifact_subpath = clean(args.artifact_subpath, "artifact_subpath")
    out_dir = pathlib.Path(args.out_dir)
    report_dir = pathlib.Path(args.report_dir)
    validate_report_paths(args.request_id, out_dir, report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    write_progress(args)

    report_path = report_dir / "workflow_report.md"
    native_report_path = report_dir / "native_artifact_readback_report.md"
    lines = [
        "# Native artifact readback report",
        "",
        "## Result",
        "",
        "- workflow: chatgpt-github-artifact-readback",
        "- result: success",
        "- phase: artifact-staged",
        f"- request_id: {args.request_id}",
        f"- request_path: {args.request_path or '(direct dispatch inputs)'}",
        f"- source_run_id: {args.source_run_id}",
        f"- artifact_name: {args.artifact_name}",
        f"- artifact_id: {args.artifact_id}",
        f"- artifact_subpath: {args.artifact_subpath or '.'}",
        f"- out_dir: {args.out_dir}",
        f"- github_run_id: {os.environ.get('GITHUB_RUN_ID', '')}",
        f"- github_run_attempt: {os.environ.get('GITHUB_RUN_ATTEMPT', '')}",
        f"- github_sha: {os.environ.get('GITHUB_SHA', '')}",
        f"- github_ref: {os.environ.get('GITHUB_REF', '')}",
        f"- report_created_utc: {utc_now()}",
        "",
        "## Readback",
        "",
        f"- heartbeat_report: {report_path.as_posix()}",
        f"- progress_history: {(report_dir / 'progress_history.jsonl').as_posix()}",
        f"- latest_progress_marker: {(report_dir / 'latest_progress_marker.json').as_posix()}",
        f"- staged_manifest_json: {(out_dir / 'artifact_manifest.json').as_posix()}",
        f"- staged_manifest_md: {(out_dir / 'artifact_manifest.md').as_posix()}",
        f"- staged_files_root: {args.out_dir}",
        "",
        "## Cleanup guidance",
        "",
        f"After ChatGPT reads the needed files, create a cleanup marker for request id '{args.request_id}' with cleanup_out_bundles=true and cleanup_status_reports=true.",
        "",
        "## Next ChatGPT action",
        "",
        f"Read artifact_manifest.md and the staged files under {args.out_dir}. Record evidence, then request cleanup when safe.",
    ]
    native_report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with report_path.open("a", encoding="utf-8") as handle:
        handle.write("\n## Native artifact readback report\n\n")
        handle.write(native_report_path.read_text(encoding="utf-8"))
    print(native_report_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
