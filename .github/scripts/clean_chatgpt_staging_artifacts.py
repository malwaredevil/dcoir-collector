#!/usr/bin/env python3
"""Clean selected ChatGPT staging artifacts and write the cleanup report."""
from __future__ import annotations

import argparse
import datetime as dt
import os
import pathlib
import re
import subprocess

SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
INVALID_IDS = {".", ".."}
SCAFFOLD_PATHS = {
    "chatgpt_staging/requests/.gitkeep",
    "chatgpt_staging/requests/github_artifact_readback/.gitkeep",
    "chatgpt_staging/in/.gitkeep",
    "chatgpt_staging/out/.gitkeep",
    "chatgpt_staging/apply_reports/.gitkeep",
    "chatgpt_staging/failure_reports/.gitkeep",
    "chatgpt_staging/cleanup_requests/.gitkeep",
    "chatgpt_staging/status_reports/.gitkeep",
    "chatgpt_staging/testdata/source/.gitkeep",
}


def bool_arg(value: str, name: str) -> bool:
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    raise SystemExit(f"{name} must be true or false")


def validate_filter(value: str) -> str:
    text = str(value or "").strip()
    if text and (text in INVALID_IDS or not SAFE_ID_RE.fullmatch(text)):
        raise SystemExit(f"Unsafe request_id_filter: {text}")
    return text


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def is_scaffold_path(path: pathlib.Path) -> bool:
    posix = path.as_posix()
    return posix in SCAFFOLD_PATHS or path.name == ".gitkeep"


def ensure_safe_cleanup_path(path: pathlib.Path) -> None:
    posix = path.as_posix()
    pure = pathlib.PurePosixPath(posix)
    if not posix or posix.startswith("/tmp/") or pure.is_absolute() or ".." in pure.parts:
        raise SystemExit(f"Refusing unsafe cleanup path: {posix}")


def git_path_is_tracked(path: pathlib.Path) -> bool:
    proc = subprocess.run(
        ["git", "ls-files", "--error-unmatch", path.as_posix()],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc.returncode == 0


class Cleaner:
    def __init__(self, request_filter: str, report_dir: pathlib.Path) -> None:
        self.request_filter = request_filter
        self.report_dir = report_dir
        self.removed: list[str] = []
        self.retained: list[str] = []

    def match_filter(self, name: str) -> bool:
        return not self.request_filter or name == self.request_filter or name.startswith(self.request_filter)

    def remove_path(self, path: pathlib.Path) -> None:
        ensure_safe_cleanup_path(path)
        posix = path.as_posix()
        if is_scaffold_path(path):
            self.retained.append(posix)
            print(f"Skipping scaffold path: {posix}")
            return
        if path == self.report_dir or self.report_dir in path.parents:
            self.retained.append(posix)
            print(f"Skipping current cleanup report path: {posix}")
            return
        if git_path_is_tracked(path):
            subprocess.run(["git", "rm", "-r", "-f", posix], check=True)
            self.removed.append(posix)


def iter_child_dirs(path: pathlib.Path) -> list[pathlib.Path]:
    return sorted(child for child in path.glob("*") if child.is_dir())


def write_report(report_path: pathlib.Path, request_filter: str, removed: list[str], retained: list[str]) -> None:
    lines = [
        "# ChatGPT workflow report",
        "",
        "## Result",
        "",
        "- workflow: chatgpt-staging-cleanup",
        "- result: success",
        "- phase: cleanup",
        f"- request_id_filter: {request_filter}",
        f"- github_run_id: {os.environ.get('GITHUB_RUN_ID', '')}",
        f"- github_sha: {os.environ.get('GITHUB_SHA', '')}",
        f"- github_ref: {os.environ.get('GITHUB_REF', '')}",
        f"- removed_count: {len(removed)}",
        f"- report_created_utc: {utc_now()}",
        "",
        "## Removed paths",
    ]
    lines.extend(f"- {path}" for path in removed)
    if not removed:
        lines.append("- none")
    lines.extend(["", "## Retained or skipped paths"])
    lines.extend(f"- {path}" for path in retained)
    if not retained:
        lines.append("- none")
    lines.extend([
        "",
        "## Cleanup guidance",
        "",
        "This cleanup report can be removed by a future cleanup marker with cleanup_status_reports=true after ChatGPT reads it.",
        "",
        "## Next ChatGPT action",
        "",
        "Verify scoped deletion by GitHub readback, update Airtable evidence if material, then remove this report when safe.",
    ])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def append_env(path: pathlib.Path, values: dict[str, str]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request-id-filter", default="")
    parser.add_argument("--cleanup-requests", required=True)
    parser.add_argument("--cleanup-in-payloads", required=True)
    parser.add_argument("--cleanup-out-bundles", required=True)
    parser.add_argument("--cleanup-apply-reports", required=True)
    parser.add_argument("--cleanup-failure-reports", required=True)
    parser.add_argument("--cleanup-status-reports", required=True)
    parser.add_argument("--cleanup-marker-path", default="")
    parser.add_argument("--delete-marker-after-success", required=True)
    parser.add_argument("--github-env", default=os.environ.get("GITHUB_ENV", ""))
    args = parser.parse_args()

    request_filter = validate_filter(args.request_id_filter)
    report_id = request_filter or f"manual_cleanup_{os.environ.get('GITHUB_RUN_ID', '')}"
    if report_id in INVALID_IDS or not SAFE_ID_RE.fullmatch(report_id):
        raise SystemExit(f"Unsafe cleanup report id: {report_id}")
    report_dir = pathlib.Path("chatgpt_staging/status_reports/chatgpt-staging-cleanup") / report_id
    report_path = report_dir / "workflow_report.md"
    report_dir.mkdir(parents=True, exist_ok=True)
    cleaner = Cleaner(request_filter, report_dir)

    if bool_arg(args.cleanup_requests, "cleanup_requests"):
        for path in sorted(pathlib.Path("chatgpt_staging/requests").rglob("*.json")):
            if path.exists() and cleaner.match_filter(path.stem):
                cleaner.remove_path(path)
    if bool_arg(args.cleanup_in_payloads, "cleanup_in_payloads"):
        for path in iter_child_dirs(pathlib.Path("chatgpt_staging/in")):
            if cleaner.match_filter(path.name):
                cleaner.remove_path(path)
    if bool_arg(args.cleanup_out_bundles, "cleanup_out_bundles"):
        for path in iter_child_dirs(pathlib.Path("chatgpt_staging/out")):
            if cleaner.match_filter(path.name):
                cleaner.remove_path(path)
    if bool_arg(args.cleanup_apply_reports, "cleanup_apply_reports"):
        for path in sorted(pathlib.Path("chatgpt_staging/apply_reports").glob("*.md")):
            if path.exists() and cleaner.match_filter(path.name):
                cleaner.remove_path(path)
    if bool_arg(args.cleanup_failure_reports, "cleanup_failure_reports"):
        for path in iter_child_dirs(pathlib.Path("chatgpt_staging/failure_reports")):
            if cleaner.match_filter(path.name):
                cleaner.remove_path(path)
    if bool_arg(args.cleanup_status_reports, "cleanup_status_reports"):
        for workflow_dir in iter_child_dirs(pathlib.Path("chatgpt_staging/status_reports")):
            if is_scaffold_path(workflow_dir):
                continue
            for path in iter_child_dirs(workflow_dir):
                if cleaner.match_filter(path.name):
                    cleaner.remove_path(path)
    if bool_arg(args.delete_marker_after_success, "delete_marker_after_success") and args.cleanup_marker_path:
        cleaner.remove_path(pathlib.Path(args.cleanup_marker_path))

    write_report(report_path, request_filter, cleaner.removed, cleaner.retained)
    if args.github_env:
        append_env(pathlib.Path(args.github_env), {
            "removed": str(len(cleaner.removed)),
            "REPORT_DIR": report_dir.as_posix(),
            "REPORT_PATH": report_path.as_posix(),
            "REPORT_PUSHED": "false",
        })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
