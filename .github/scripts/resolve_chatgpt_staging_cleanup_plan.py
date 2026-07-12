#!/usr/bin/env python3
"""Resolve the ChatGPT staging cleanup plan for the reusable workflow."""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess

SCHEMA = "dcoir.chatgpt_staging.cleanup_request.v1"
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
INVALID_IDS = {".", ".."}


def append_outputs(path: pathlib.Path, values: dict[str, str]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def normalize_bool(value: object, name: str, default: bool = False) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "true" if default else "false"
    if isinstance(value, str) and value.lower() in {"true", "false"}:
        return value.lower()
    raise SystemExit(f"Cleanup marker field {name} must be boolean")


def validate_request_id(value: str, label: str) -> str:
    request_id = str(value or "").strip()
    if not request_id or request_id in INVALID_IDS or not SAFE_ID_RE.fullmatch(request_id):
        raise SystemExit(f"Unsafe or missing {label}: {request_id!r}")
    return request_id


def validate_optional_filter(value: str) -> str:
    text = str(value or "").strip()
    if text and (text in INVALID_IDS or not SAFE_ID_RE.fullmatch(text)):
        raise SystemExit(f"Unsafe request_id_filter: {text}")
    return text


def find_cleanup_marker(head_sha: str) -> pathlib.Path | None:
    proc = subprocess.run(
        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", head_sha],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        return None
    for raw_path in proc.stdout.splitlines():
        path = pathlib.Path(raw_path)
        pure = pathlib.PurePosixPath(raw_path)
        if (
            len(pure.parts) == 3
            and pure.parts[:2] == ("chatgpt_staging", "cleanup_requests")
            and pure.suffix == ".json"
            and path.is_file()
        ):
            return path
    return None


def outputs_from_marker(marker: pathlib.Path) -> dict[str, str]:
    if marker.is_absolute() or ".." in pathlib.PurePosixPath(marker.as_posix()).parts:
        raise SystemExit(f"Unsafe cleanup marker path: {marker}")
    data = json.loads(marker.read_text(encoding="utf-8"))
    schema = data.get("schema")
    if schema != SCHEMA:
        raise SystemExit(f"cleanup marker schema must be {SCHEMA}, got {schema!r}")
    request_id = validate_request_id(str(data.get("request_id", "")), "request_id in cleanup marker")
    return {
        "skip": "false",
        "cleanup_requests": normalize_bool(data.get("cleanup_requests"), "cleanup_requests", True),
        "cleanup_in_payloads": normalize_bool(data.get("cleanup_in_payloads"), "cleanup_in_payloads", True),
        "cleanup_out_bundles": normalize_bool(data.get("cleanup_out_bundles"), "cleanup_out_bundles", False),
        "cleanup_apply_reports": normalize_bool(data.get("cleanup_apply_reports"), "cleanup_apply_reports", False),
        "cleanup_failure_reports": normalize_bool(data.get("cleanup_failure_reports"), "cleanup_failure_reports", False),
        "cleanup_status_reports": normalize_bool(data.get("cleanup_status_reports"), "cleanup_status_reports", False),
        "delete_marker_after_success": normalize_bool(data.get("delete_marker_after_success"), "delete_marker_after_success", True),
        "request_id_filter": request_id,
        "cleanup_marker_path": marker.as_posix(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--caller-event-name", required=True)
    parser.add_argument("--cleanup-requests", required=True)
    parser.add_argument("--cleanup-in-payloads", required=True)
    parser.add_argument("--cleanup-out-bundles", required=True)
    parser.add_argument("--cleanup-apply-reports", required=True)
    parser.add_argument("--cleanup-failure-reports", required=True)
    parser.add_argument("--cleanup-status-reports", required=True)
    parser.add_argument("--request-id-filter", default="")
    parser.add_argument("--github-sha", default="")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    output_path = pathlib.Path(args.output)
    if args.caller_event_name == "workflow_dispatch":
        request_id_filter = validate_optional_filter(args.request_id_filter)
        append_outputs(output_path, {
            "skip": "false",
            "cleanup_requests": normalize_bool(args.cleanup_requests, "cleanup_requests"),
            "cleanup_in_payloads": normalize_bool(args.cleanup_in_payloads, "cleanup_in_payloads"),
            "cleanup_out_bundles": normalize_bool(args.cleanup_out_bundles, "cleanup_out_bundles"),
            "cleanup_apply_reports": normalize_bool(args.cleanup_apply_reports, "cleanup_apply_reports"),
            "cleanup_failure_reports": normalize_bool(args.cleanup_failure_reports, "cleanup_failure_reports"),
            "cleanup_status_reports": normalize_bool(args.cleanup_status_reports, "cleanup_status_reports"),
            "request_id_filter": request_id_filter,
            "cleanup_marker_path": "",
            "delete_marker_after_success": "false",
        })
        return 0

    marker = find_cleanup_marker(args.github_sha)
    if marker is None:
        print("No cleanup request marker found in triggering commit; exiting successfully.")
        append_outputs(output_path, {"skip": "true"})
        return 0
    append_outputs(output_path, outputs_from_marker(marker))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
