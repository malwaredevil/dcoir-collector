from __future__ import annotations

import argparse
import json
import pathlib
import shlex
import tempfile
from typing import Any

from lib.apply_patch_request_contract import (
    BOT_USER_EMAIL,
    BOT_USER_NAME,
    FORBIDDEN_PATCH_MARKERS,
    PatchRequest,
    RequestError,
    SCHEMA_V1,
    TargetSpec,
    git_blob_sha,
    load_request,
    normalize_repo_path,
    path_under,
    run,
    sha256_bytes,
    sha256_file,
)

def patch_path_token(raw: str) -> str | None:
    path = raw.strip()
    if not path or path == "/dev/null":
        return None
    if "\t" in path:
        path = path.split("\t", 1)[0]
    if path.startswith(("a/", "b/")):
        path = path[2:]
    return normalize_repo_path(path.strip('"'), field="patch path")

def extract_patch_paths(patch_text: str) -> dict[str, str]:
    paths: dict[str, str] = {}
    for line in patch_text.splitlines():
        if line.startswith(("--- ", "+++ ")):
            if line[4:].strip().split("\t", 1)[0] == "/dev/null":
                raise RequestError("patch must not create or delete the target file")
            token = patch_path_token(line[4:])
            if token:
                paths[token] = "modify"
        elif line.startswith("diff --git "):
            try:
                parts = shlex.split(line)
            except ValueError:
                continue
            for token in parts[2:4]:
                parsed = patch_path_token(token)
                if parsed:
                    paths[parsed] = "modify"
    return paths

def target_plan(target: TargetSpec, operation: str, request: PatchRequest) -> dict[str, Any]:
    root_policy = "pass" if path_under(target.path, target.allowed_roots) else "fail"
    if target.path.startswith(".github/workflows/"):
        workflow_policy = "explicitly_allowed" if request.allow_workflow_changes else "fail"
    else:
        workflow_policy = "not_workflow"
    return {
        "path": target.path,
        "operation": operation,
        "allowed_roots": list(target.allowed_roots),
        "root_policy_result": root_policy,
        "workflow_policy_result": workflow_policy,
        "expected_target_blob_sha": target.expected_target_blob_sha,
        "expected_current_sha256": target.expected_current_sha256,
        "expected_new_sha256": target.expected_new_sha256,
        "stale_base_result": "pending",
    }

def build_apply_plan(patch_text: str, request: PatchRequest) -> dict[str, Any]:
    if "\x00" in patch_text:
        raise RequestError("patch contains NUL bytes")
    for marker in FORBIDDEN_PATCH_MARKERS:
        if marker in patch_text:
            raise RequestError(f"patch contains forbidden marker: {marker.strip()}")
    paths = extract_patch_paths(patch_text)
    expected_paths = set(request.target_paths)
    found_paths = set(paths)
    if found_paths != expected_paths:
        if request.schema == SCHEMA_V1:
            raise RequestError(f"patch must touch only target_path {request.target_path}; found {sorted(found_paths)}")
        raise RequestError(f"patch paths must match targets; expected {sorted(expected_paths)}, found {sorted(found_paths)}")
    if request.schema == SCHEMA_V1 and len(found_paths) != 1:
        raise RequestError("v1 patch requests must touch exactly one target_path")
    branch_policy = "not_default_branch"
    if request.allow_default_branch:
        branch_policy = "explicitly_allowed" if request.default_branch_reason.strip() else "fail"
    return {
        "schema": request.schema,
        "request_id": request.request_id,
        "mode": request.mode,
        "operation": request.operation,
        "target_branch": request.target_branch,
        "patch_path": request.patch_path,
        "default_branch_policy_result": branch_policy,
        "allow_workflow_changes": request.allow_workflow_changes,
        "files": [target_plan(target, paths[target.path], request) for target in request.targets],
    }

def prepare_patch(repo: pathlib.Path, request: PatchRequest) -> tuple[bytes, dict[str, Any]]:
    patch_file = repo / request.patch_path
    patch_bytes = patch_file.read_bytes()
    actual = sha256_bytes(patch_bytes)
    if actual != request.expected_patch_sha256:
        raise RequestError(f"patch SHA-256 mismatch: expected {request.expected_patch_sha256}, got {actual}")
    patch_text = patch_bytes.decode("utf-8")
    return patch_bytes, build_apply_plan(patch_text, request)

def checkout_target(repo: pathlib.Path, branch: str, *, local_only: bool) -> None:
    if not local_only:
        refspec = f"refs/heads/{branch}:refs/remotes/origin/{branch}"
        run(["git", "fetch", "--no-tags", "origin", refspec], cwd=repo)
        run(["git", "checkout", "-B", "ops-apply-patch-target", f"origin/{branch}"], cwd=repo)
    else:
        run(["git", "checkout", branch], cwd=repo)

def plan_file_by_path(plan: dict[str, Any], path: str) -> dict[str, Any]:
    for item in plan.get("files", []):
        if item.get("path") == path:
            return item
    return {}

def validate_current_targets(repo: pathlib.Path, request: PatchRequest, plan: dict[str, Any]) -> None:
    for target_spec in request.targets:
        path = target_spec.path
        plan_file = plan_file_by_path(plan, path)
        target = repo / path
        if not target.is_file():
            if plan_file:
                plan_file["stale_base_result"] = "fail"
            raise RequestError(f"target_path is missing or not a file on target branch: {path}")
        blob_sha = git_blob_sha(repo, path)
        if plan_file:
            plan_file["current_target_blob_sha"] = blob_sha
        if not blob_sha:
            if plan_file:
                plan_file["stale_base_result"] = "fail"
            raise RequestError(f"target_path is not tracked on target branch: {path}")
        if target_spec.expected_target_blob_sha and blob_sha != target_spec.expected_target_blob_sha:
            if plan_file:
                plan_file["stale_base_result"] = "fail"
            raise RequestError(f"target blob mismatch for {path}: expected {target_spec.expected_target_blob_sha}, got {blob_sha}")
        current_sha = sha256_file(target)
        if plan_file:
            plan_file["current_sha256"] = current_sha
        if target_spec.expected_current_sha256 and current_sha != target_spec.expected_current_sha256:
            if plan_file:
                plan_file["stale_base_result"] = "fail"
            raise RequestError(f"target SHA-256 mismatch for {path}: expected {target_spec.expected_current_sha256}, got {current_sha}")
        if plan_file:
            plan_file["stale_base_result"] = "pass"

def apply_patch(repo: pathlib.Path, patch_bytes: bytes, *, dry_run: bool) -> None:
    with tempfile.NamedTemporaryFile(prefix="dcoir-ops-patch-", suffix=".patch", delete=False) as handle:
        handle.write(patch_bytes)
        temp_patch = pathlib.Path(handle.name)
    try:
        run(["git", "apply", "--check", "--", str(temp_patch)], cwd=repo)
        if not dry_run:
            run(["git", "apply", "--", str(temp_patch)], cwd=repo)
    finally:
        temp_patch.unlink(missing_ok=True)

def ensure_git_identity(repo: pathlib.Path) -> None:
    name = run(["git", "config", "--get", "user.name"], cwd=repo, check=False).stdout.strip()
    email = run(["git", "config", "--get", "user.email"], cwd=repo, check=False).stdout.strip()
    if not name:
        run(["git", "config", "user.name", BOT_USER_NAME], cwd=repo)
    if not email:
        run(["git", "config", "user.email", BOT_USER_EMAIL], cwd=repo)

def commit_and_push(repo: pathlib.Path, request: PatchRequest, *, local_only: bool, no_push: bool) -> str:
    expected = sorted(request.target_paths)
    changed = sorted(run(["git", "diff", "--name-only"], cwd=repo).stdout.splitlines())
    if changed != expected:
        raise RequestError(f"patch changed unexpected paths: {changed}")
    for target in request.targets:
        if not (repo / target.path).is_file():
            raise RequestError(f"patch must leave target_path as an existing file: {target.path}")
        if target.expected_new_sha256:
            actual_new = sha256_file(repo / target.path)
            if actual_new != target.expected_new_sha256:
                raise RequestError(f"new target SHA-256 mismatch for {target.path}: expected {target.expected_new_sha256}, got {actual_new}")
    ensure_git_identity(repo)
    run(["git", "add", "--", *request.target_paths], cwd=repo)
    run(["git", "commit", "-m", request.commit_message], cwd=repo)
    commit_sha = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()
    if not (local_only or no_push):
        run(["git", "push", "origin", f"HEAD:refs/heads/{request.target_branch}"], cwd=repo)
    return commit_sha

def write_report(report_dir: pathlib.Path, result: dict[str, Any]) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = ["# Ops apply-patch report", ""]
    for key in ("result", "request_id", "schema", "mode", "operation", "target_branch", "target_path", "commit_sha", "message"):
        if key in result and result[key] is not None:
            lines.append(f"- {key}: `{result[key]}`")
    if result.get("target_paths"):
        lines.append("- target_paths:")
        for path in result["target_paths"]:
            lines.append(f"  - `{path}`")
    plan = result.get("apply_plan")
    if isinstance(plan, dict) and plan.get("files"):
        lines.extend(["", "## Apply plan", ""])
        for item in plan["files"]:
            lines.append(
                "- `{path}`: operation `{operation}`, root policy `{root}`, workflow policy `{workflow}`, stale-base `{stale}`".format(
                    path=item.get("path"),
                    operation=item.get("operation"),
                    root=item.get("root_policy_result"),
                    workflow=item.get("workflow_policy_result"),
                    stale=item.get("stale_base_result"),
                )
            )
    (report_dir / "workflow_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

def apply_request(args: argparse.Namespace) -> int:
    repo = pathlib.Path(args.repo).resolve()
    request_path = (repo / args.request).resolve() if not pathlib.Path(args.request).is_absolute() else pathlib.Path(args.request).resolve()
    report_dir = pathlib.Path(args.report_dir).resolve() if args.report_dir else None
    result: dict[str, Any] = {
        "result": "failure",
        "request_id": None,
        "schema": None,
        "mode": None,
        "operation": None,
        "target_branch": None,
        "target_path": None,
        "target_paths": None,
        "commit_sha": None,
        "apply_plan": None,
    }
    try:
        request = load_request(repo, request_path, args.default_branch)
        patch_bytes, apply_plan = prepare_patch(repo, request)
        result.update(
            {
                "result": "success",
                "request_id": request.request_id,
                "schema": request.schema,
                "mode": request.mode,
                "operation": request.operation,
                "target_branch": request.target_branch,
                "target_path": request.target_path,
                "target_paths": list(request.target_paths),
                "apply_plan": apply_plan,
            }
        )
        checkout_target(repo, request.target_branch, local_only=args.local_only)
        validate_current_targets(repo, request, apply_plan)
        dry_run = request.operation == "dry-run"
        apply_patch(repo, patch_bytes, dry_run=dry_run)
        if dry_run:
            result["message"] = "patch passed validation and git apply --check; no commit was made"
        else:
            result["commit_sha"] = commit_and_push(repo, request, local_only=args.local_only, no_push=args.no_push)
            result["message"] = "patch applied, committed, and pushed" if not (args.local_only or args.no_push) else "patch applied and committed locally"
    except Exception as exc:
        result["result"] = "failure"
        result["message"] = str(exc)
        if report_dir:
            write_report(report_dir, result)
        raise
    if report_dir:
        write_report(report_dir, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0

def validate_request(args: argparse.Namespace) -> int:
    repo = pathlib.Path(args.repo).resolve()
    request_path = (repo / args.request).resolve() if not pathlib.Path(args.request).is_absolute() else pathlib.Path(args.request).resolve()
    request = load_request(repo, request_path, args.default_branch)
    _, apply_plan = prepare_patch(repo, request)
    print(json.dumps({"result": "success", "request_id": request.request_id, "target_path": request.target_path, "target_paths": list(request.target_paths), "apply_plan": apply_plan}, sort_keys=True))
    return 0
