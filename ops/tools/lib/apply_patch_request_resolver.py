"""Resolver helpers for governed ops apply-patch requests."""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import subprocess
import sys
import time
from collections.abc import Iterable

REQUEST_ROOT = pathlib.Path("ops/requests/apply_patch")
SAFE_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
INVALID_REQUEST_IDS = {".", ".."}


def write_outputs(output_path: pathlib.Path, values: dict[str, str]) -> None:
    with output_path.open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def validate_request_id(request_id: str) -> None:
    if not request_id or request_id in INVALID_REQUEST_IDS or not SAFE_REQUEST_ID_RE.fullmatch(request_id):
        raise SystemExit(f"Unsafe request id: {request_id}")


def safe_request_path(path: str) -> bool:
    pure = pathlib.PurePosixPath(path)
    return (
        len(pure.parts) == 5
        and pure.parts[:3] == ("ops", "requests", "apply_patch")
        and pure.name == "request.json"
        and pure.parts[3] not in INVALID_REQUEST_IDS
        and SAFE_REQUEST_ID_RE.fullmatch(pure.parts[3]) is not None
    )


def request_path_for_patch(path: str) -> str | None:
    pure = pathlib.PurePosixPath(path)
    if (
        len(pure.parts) == 5
        and pure.parts[:3] == ("ops", "requests", "apply_patch")
        and pure.suffix in {".patch", ".diff"}
        and pure.parts[3] not in INVALID_REQUEST_IDS
        and SAFE_REQUEST_ID_RE.fullmatch(pure.parts[3])
    ):
        return pathlib.PurePosixPath(*pure.parts[:4], "request.json").as_posix()
    return None


def git_stdout(args: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        args,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return proc.returncode, proc.stdout


def request_commit_time(path: pathlib.Path) -> int:
    returncode, stdout = git_stdout(["git", "log", "-1", "--format=%ct", "--", path.as_posix()])
    if returncode != 0 or not stdout.strip():
        return 0
    try:
        return int(stdout.strip())
    except ValueError:
        return 0


def scan_pending_requests(max_age_hours: float) -> list[tuple[int, str]]:
    now = time.time()
    records: list[tuple[int, str]] = []
    for request_path in sorted(REQUEST_ROOT.glob("*/request.json")):
        if not request_path.is_file():
            continue
        request_dir = request_path.parent
        if (request_dir / ".apply-patch-failed.json").exists():
            continue
        commit_time = request_commit_time(request_path)
        if max_age_hours > 0 and commit_time and now - commit_time > max_age_hours * 3600:
            continue
        if safe_request_path(request_path.as_posix()):
            records.append((commit_time, request_path.as_posix()))
    return sorted(records, key=lambda item: (item[0] or 0, item[1]))


def add_name_status_line(changed: dict[str, str], line: str) -> None:
    parts = line.split("\t")
    if len(parts) < 2:
        return
    status = parts[0]
    if status.startswith(("R", "C")) and len(parts) >= 3:
        path = parts[2]
    else:
        path = parts[1]
    if path:
        changed[path] = status


def collect_changed_records(event_path: pathlib.Path, head_sha: str) -> list[tuple[str, str]]:
    zero_sha = "0" * 40
    changed: dict[str, str] = {}
    try:
        event = json.loads(event_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        event = {}

    for commit in event.get("commits", []):
        if not isinstance(commit, dict):
            continue
        for path in commit.get("added", []):
            if isinstance(path, str) and path:
                changed[path] = "A"
        for path in commit.get("modified", []):
            if isinstance(path, str) and path:
                changed[path] = "M"
        for path in commit.get("removed", []):
            if isinstance(path, str) and path:
                changed[path] = "D"

    before = event.get("before")
    after = event.get("after") or head_sha
    if isinstance(before, str) and isinstance(after, str) and before and after and before != zero_sha:
        returncode, stdout = git_stdout(["git", "diff", "--name-status", f"{before}..{after}"])
        if returncode == 0:
            for line in stdout.splitlines():
                add_name_status_line(changed, line)

    if not changed:
        returncode, stdout = git_stdout(["git", "diff-tree", "--no-commit-id", "--name-status", "-r", "-m", head_sha])
        if returncode == 0:
            for line in stdout.splitlines():
                add_name_status_line(changed, line)

    return [(changed[path], path) for path in sorted(changed)]


def directory_tree_sha256(root: pathlib.Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def resolve_from_changed_records(records: Iterable[tuple[str, str]], caller_event_name: str) -> tuple[str | None, bool]:
    request_paths: dict[str, None] = {}
    removed_request_path_count = 0
    for status, changed_path in records:
        if not changed_path:
            continue
        if safe_request_path(changed_path):
            if status.startswith("D"):
                removed_request_path_count += 1
            else:
                request_paths[changed_path] = None
            continue
        request_path = request_path_for_patch(changed_path)
        if request_path:
            if status.startswith("D"):
                removed_request_path_count += 1
            else:
                request_paths[request_path] = None

    if not request_paths:
        if removed_request_path_count > 0:
            print("Only removed apply-patch request files were found; treating this as cleanup and skipping.")
            return None, True
        if caller_event_name == "push":
            raise SystemExit("Apply-patch workflow was triggered by push, but no request path could be resolved from the push range.")
        print("No apply-patch request found in triggering event; exiting successfully.")
        return None, True

    if len(request_paths) > 1:
        print("Only one apply-patch request may be staged per triggering commit. Found:", file=sys.stderr)
        for request_path in sorted(request_paths):
            print(request_path, file=sys.stderr)
        raise SystemExit(1)
    return next(iter(request_paths)), False


def resolve(args) -> int:
    output_path = pathlib.Path(args.output)
    if args.caller_event_name == "workflow_dispatch" and args.input_request_path:
        request_path = args.input_request_path
        if not safe_request_path(request_path):
            raise SystemExit("request_path must match ops/requests/apply_patch/<request_id>/request.json")
    elif args.caller_event_name == "workflow_dispatch":
        try:
            max_age_hours = float(args.pending_request_max_age_hours or "0")
        except ValueError:
            max_age_hours = 48.0
        pending_records = scan_pending_requests(max_age_hours)
        if not pending_records:
            print("No unmarked apply-patch requests were found under ops/requests/apply_patch within the scan window.")
            write_outputs(output_path, {"skip": "true"})
            return 0
        if len(pending_records) > 1:
            print("Multiple pending apply-patch requests found; processing the oldest and leaving the rest queued:")
            for commit_time, request_path in pending_records:
                print(f"{commit_time}\t{request_path}")
        request_path = pending_records[0][1]
    else:
        records = collect_changed_records(pathlib.Path(args.event_path), args.head_sha)
        request_path, skip = resolve_from_changed_records(records, args.caller_event_name)
        if skip:
            write_outputs(output_path, {"skip": "true"})
            return 0
        if request_path is None:
            raise SystemExit("Failed to resolve apply-patch request path")

    if not safe_request_path(request_path):
        raise SystemExit(f"resolved request_path must match ops/requests/apply_patch/<request_id>/request.json: {request_path}")
    path = pathlib.Path(request_path)
    if not path.is_file():
        raise SystemExit(f"Request file not found: {request_path}")
    request_id = path.parent.name
    validate_request_id(request_id)
    request_dir = path.parent
    write_outputs(output_path, {
        "request_path": request_path,
        "request_dir": request_dir.as_posix(),
        "request_dir_tree_sha256": directory_tree_sha256(request_dir),
        "request_id": request_id,
        "skip": "false",
    })
    return 0


def should_cleanup(args) -> int:
    result_path = pathlib.Path(args.result_json)
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        print("false")
        return 0
    operation = result.get("operation") or result.get("mode")
    print("true" if result.get("result") == "success" and operation == "apply" else "false")
    return 0
