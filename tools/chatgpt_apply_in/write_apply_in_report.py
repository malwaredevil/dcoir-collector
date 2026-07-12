#!/usr/bin/env python3
"""Write native chatgpt-apply-in success and failure reports."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import shutil
from pathlib import Path


def utc_stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_list(path: Path) -> list[str]:
    if not path.is_file() or path.stat().st_size == 0:
        return ["- none"]
    return [f"- {line}" for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line]


def append_file_list(lines: list[str], title: str, path: Path) -> None:
    lines.extend(["", f"## {title}"])
    lines.extend(read_list(path))


def sha256_file(path: Path, output_path: Path) -> None:
    if not path.is_file():
        return
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    output_path.write_text(f"{digest}  {path}\n", encoding="utf-8")


def write_success(args: argparse.Namespace) -> int:
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    native_report = report_dir / "native_apply_in_success_report.md"
    lines = [
        "# ChatGPT workflow report",
        "",
        "## Result",
        "",
        "- workflow: chatgpt-apply-in",
        "- result: success",
        "- phase: bundle-applied-before-commit",
        f"- request_id: {args.request_id}",
        f"- payload_path: {args.payload}",
        "- payload_shape: single payload.zip.b64",
        f"- github_run_id: {args.github_run_id}",
        f"- github_sha: {args.github_sha}",
        f"- github_ref: {args.github_ref}",
        f"- report_created_utc: {utc_stamp()}",
    ]
    append_file_list(lines, "Applied paths", Path(args.applied_paths))
    append_file_list(lines, "Deleted paths", Path(args.deleted_paths))
    hash_warnings = Path(args.hash_warnings)
    if hash_warnings.is_file():
        append_file_list(lines, "Warnings", hash_warnings)
    lines.extend(
        [
            "",
            "## Cleanup guidance",
            "",
            (
                "After ChatGPT verifies the commit/readback and no longer needs this report, "
                f"create a cleanup marker for request id '{args.request_id}' with cleanup_status_reports=true."
            ),
            "",
            "## Next ChatGPT action",
            "",
            (
                "Verify the committed target changes, hash policy outcome, deletion outcome, and apply report. "
                "If readback is good, update Airtable and clean this status report when safe."
            ),
        ]
    )
    native_report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(native_report)
    return 0


def write_failure(args: argparse.Namespace) -> int:
    report_dir = Path(args.report_dir)
    work_dir = Path(args.work_dir)
    artifact_dir = Path(args.artifact_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    native_report = report_dir / "native_apply_in_failure_report.md"
    manifest = work_dir / "extract" / "apply_manifest.json"
    lines = [
        "# ChatGPT workflow report",
        "",
        "## Result",
        "",
        "- workflow: chatgpt-apply-in",
        "- result: failure",
        "- phase: apply-in",
        f"- request_id: {args.request_id}",
        f"- payload_path: {args.payload}",
        "- expected_payload_shape: single chatgpt_staging/in/<request_id>/payload.zip.b64",
        f"- github_run_id: {args.github_run_id}",
        f"- github_ref: {args.github_ref}",
        f"- github_sha: {args.github_sha}",
        f"- artifact_name: {args.artifact_name}",
        "- artifact_retention_days: 7",
        f"- report_created_utc: {utc_stamp()}",
        "",
        "## Troubleshooting context",
        "",
        (
            "The apply-in workflow failed. This workflow only accepts one payload.zip.b64 file. "
            "Parts/chunks, chunk manifests, payload.zip.b64.parts, invalid base64, missing root "
            "apply_manifest.json, missing root files/, unsafe paths, stale hashes, create_only "
            "violations, delete policy violations, or workflow-change policy violations are hard failures."
        ),
    ]
    if manifest.is_file():
        excerpt = manifest.read_text(encoding="utf-8", errors="replace")[:4000]
        lines.extend(["", "### Manifest excerpt", "", "```json", excerpt, "```"])
    lines.extend(
        [
            "",
            "## Next ChatGPT action",
            "",
            (
                "Read this report, inspect the artifact or run log if needed, regenerate a single "
                "payload.zip.b64 with current hashes, then retry. Do not switch to parts/chunks."
            ),
        ]
    )
    native_report.write_text("\n".join(lines) + "\n", encoding="utf-8")

    payload = Path(args.payload)
    zip_path = work_dir / "payload.zip"
    sha256_file(payload, artifact_dir / "payload_b64.sha256")
    sha256_file(zip_path, artifact_dir / "payload_zip.sha256")
    if manifest.is_file():
        shutil.copy2(manifest, artifact_dir / "apply_manifest.json")
    print(native_report)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--github-run-id", default="")
    parser.add_argument("--github-ref", default="")
    parser.add_argument("--github-sha", default="")
    subparsers = parser.add_subparsers(dest="command", required=True)

    success = subparsers.add_parser("success")
    success.add_argument("--request-id", required=True)
    success.add_argument("--payload", required=True)
    success.add_argument("--report-dir", required=True)
    success.add_argument("--applied-paths", required=True)
    success.add_argument("--deleted-paths", required=True)
    success.add_argument("--hash-warnings", required=True)
    success.set_defaults(func=write_success)

    failure = subparsers.add_parser("failure")
    failure.add_argument("--request-id", required=True)
    failure.add_argument("--payload", required=True)
    failure.add_argument("--work-dir", required=True)
    failure.add_argument("--report-dir", required=True)
    failure.add_argument("--artifact-dir", required=True)
    failure.add_argument("--artifact-name", required=True)
    failure.set_defaults(func=write_failure)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
