#!/usr/bin/env python3
"""Resolve the GitHub artifact readback workflow plan."""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess

REQUEST_ROOT = pathlib.Path("chatgpt_staging/requests/github_artifact_readback")
SCHEMA = "dcoir.chatgpt_staging.github_artifact_readback_request.v1"
SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]+$")
INVALID_REQUEST_IDS = {".", ".."}
NUMERIC = re.compile(r"^[0-9]+$")


def append_output(path: pathlib.Path, key: str, value: str) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{key}={value}\n")


def append_outputs(path: pathlib.Path, values: dict[str, str]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def clean(payload: dict[str, object], name: str) -> str:
    value = str(payload.get(name, "")).strip()
    if "\n" in value or "\r" in value:
        raise SystemExit(f"{name} must not contain newlines")
    return value


def validate_request_id(request_id: str) -> None:
    if not SAFE_REQUEST_ID.fullmatch(request_id) or request_id in INVALID_REQUEST_IDS:
        raise SystemExit(f"Unsafe request_id: {request_id!r}")


def validate_artifact_subpath(artifact_subpath: str) -> None:
    if artifact_subpath:
        pure = pathlib.PurePosixPath(artifact_subpath)
        if artifact_subpath.startswith("/") or ".." in pure.parts:
            raise SystemExit("artifact_subpath must be relative and must not contain parent traversal")


def safe_request_path(path: pathlib.Path) -> bool:
    pure = pathlib.PurePosixPath(path.as_posix())
    return (
        len(pure.parts) == 4
        and pure.parts[:3] == ("chatgpt_staging", "requests", "github_artifact_readback")
        and pure.suffix == ".json"
        and pure.name not in {".json", "..json"}
    )


def parse_request(path: pathlib.Path) -> dict[str, str]:
    if not safe_request_path(path):
        raise SystemExit("request_path must match chatgpt_staging/requests/github_artifact_readback/<request_id>.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != SCHEMA:
        raise SystemExit(f"artifact readback request schema must be {SCHEMA}")

    request_id = clean(payload, "request_id")
    source_run_id = clean(payload, "source_run_id")
    artifact_name = clean(payload, "artifact_name")
    artifact_id = clean(payload, "artifact_id")
    artifact_subpath = clean(payload, "artifact_subpath")

    if not request_id:
        raise SystemExit("request_id field is required in the request JSON")
    if not source_run_id:
        raise SystemExit("source_run_id field is required in the request JSON")
    validate_request_id(request_id)
    if not NUMERIC.fullmatch(source_run_id):
        raise SystemExit("source_run_id must be numeric")
    if not artifact_name and not artifact_id:
        raise SystemExit("artifact_name or artifact_id is required")
    if artifact_id and not NUMERIC.fullmatch(artifact_id):
        raise SystemExit("artifact_id must be numeric when provided")
    validate_artifact_subpath(artifact_subpath)
    return {
        "request_path": path.as_posix(),
        "source_run_id": source_run_id,
        "artifact_name": artifact_name,
        "artifact_id": artifact_id,
        "request_id": request_id,
        "artifact_subpath": artifact_subpath,
    }


def changed_paths(before_sha: str, head_sha: str) -> list[str]:
    zero_sha = "0" * 40
    if before_sha and before_sha != zero_sha:
        proc = subprocess.run(
            ["git", "diff", "--name-only", before_sha, head_sha],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    else:
        proc = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", head_sha],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    if proc.returncode != 0:
        return []
    return proc.stdout.splitlines()


def resolve_push_request(before_sha: str, head_sha: str) -> pathlib.Path | None:
    for raw_path in changed_paths(before_sha, head_sha):
        path = pathlib.Path(raw_path)
        if safe_request_path(path) and path.is_file():
            return path
    return None


def next_request_path(current: pathlib.Path) -> str:
    for path in sorted(REQUEST_ROOT.glob("*.json")):
        if path != current:
            return path.as_posix()
    return ""


def clean_input(value: str, name: str) -> str:
    text = str(value or "").strip()
    if "\n" in text or "\r" in text:
        raise SystemExit(f"{name} must not contain newlines")
    return text


def normalize_bool(value: str, name: str) -> str:
    text = clean_input(value, name).lower()
    if text in {"true", "false"}:
        return text
    raise SystemExit(f"{name} must be true or false")


def direct_plan(args: argparse.Namespace) -> dict[str, str]:
    source_run_id = clean_input(args.source_run_id, "source_run_id")
    artifact_name = clean_input(args.artifact_name, "artifact_name")
    artifact_id = clean_input(args.artifact_id, "artifact_id")
    request_id = clean_input(args.request_id, "request_id")
    artifact_subpath = clean_input(args.artifact_subpath, "artifact_subpath")
    if not source_run_id or not NUMERIC.fullmatch(source_run_id):
        raise SystemExit("source_run_id must be numeric")
    if not artifact_name and not artifact_id:
        raise SystemExit("artifact_name or artifact_id is required")
    if artifact_id and not NUMERIC.fullmatch(artifact_id):
        raise SystemExit("artifact_id must be numeric when provided")
    if request_id:
        validate_request_id(request_id)
    validate_artifact_subpath(artifact_subpath)
    return {
        "request_path": "",
        "source_run_id": source_run_id,
        "artifact_name": artifact_name,
        "artifact_id": artifact_id,
        "request_id": request_id,
        "artifact_subpath": artifact_subpath,
    }


def finalize_plan(
    plan: dict[str, str],
    commit_outputs: str,
    next_path: str,
    download_dir: str,
    output: pathlib.Path,
) -> None:
    request_id = plan["request_id"]
    if not request_id:
        raw_id = plan["artifact_name"] or f"artifact-{plan['artifact_id']}"
        safe_id = re.sub(r"[^A-Za-z0-9._-]", "", raw_id.replace(" ", "-")) or "artifact"
        request_id = f"artifact-readback-{plan['source_run_id']}-{safe_id}"
        plan["request_id"] = request_id
    validate_request_id(request_id)
    append_outputs(output, {
        **plan,
        "commit_outputs": commit_outputs,
        "next_request_path": next_path,
        "download_dir": download_dir,
        "out_dir": f"chatgpt_staging/out/{request_id}",
        "report_dir": f"chatgpt_staging/status_reports/chatgpt-github-artifact-readback/{request_id}",
        "skip": "false",
    })


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--request-path-input", default="")
    parser.add_argument("--source-run-id", default="")
    parser.add_argument("--artifact-name", default="")
    parser.add_argument("--artifact-id", default="")
    parser.add_argument("--request-id", default="")
    parser.add_argument("--artifact-subpath", default="")
    parser.add_argument("--commit-outputs", default="true")
    parser.add_argument("--before-sha", default="")
    parser.add_argument("--github-sha", default="")
    parser.add_argument("--runner-temp", default="")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    output_path = pathlib.Path(args.output)
    request_path = pathlib.Path(args.request_path_input) if args.request_path_input else None
    commit_outputs = normalize_bool(args.commit_outputs, "commit_outputs")
    next_path = ""

    if args.event_name == "push":
        request_path = resolve_push_request(args.before_sha, args.github_sha)
        if request_path is None:
            print("No artifact-readback request JSON found in pushed range; exiting successfully.")
            append_output(output_path, "skip", "true")
            return 0
        commit_outputs = "true"
    elif request_path is not None and not request_path.is_file():
        request_path = None

    if request_path is not None:
        next_path = next_request_path(request_path)
        plan = parse_request(request_path)
    else:
        plan = direct_plan(args)

    runner_temp = args.runner_temp.rstrip("/")
    if runner_temp:
        download_dir = f"{runner_temp}/chatgpt_github_artifact_readback_download"
    else:
        download_dir = "chatgpt_github_artifact_readback_download"
    finalize_plan(plan, commit_outputs, next_path, download_dir, output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
