from __future__ import annotations

import hashlib
import os
import pathlib
import subprocess
from collections.abc import Mapping

TOOL = pathlib.Path(__file__).resolve().parents[1] / "apply_patch_request.py"


def run(
    cmd: list[str],
    cwd: pathlib.Path,
    *,
    check: bool = True,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(cmd, cwd=cwd, check=check, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=merged_env)


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def init_repo(repo: pathlib.Path) -> None:
    run(["git", "init", "-b", "main"], repo)
    run(["git", "config", "user.email", "dcoir-selftest@example.invalid"], repo)
    run(["git", "config", "user.name", "DCOIR Selftest"], repo)
    write(repo / "project_sources/large.txt", "alpha\nbeta\n")
    write(repo / "project_sources/other.txt", "one\n")
    run(["git", "add", "project_sources"], repo)
    run(["git", "commit", "-m", "seed"], repo)
    run(["git", "checkout", "-b", "feature/apply-patch-target"], repo)
    run(["git", "checkout", "main"], repo)
    run(["git", "config", "--unset", "user.name"], repo, check=False)
    run(["git", "config", "--unset", "user.email"], repo, check=False)


def make_patch(repo: pathlib.Path, new_text: str, patch_path: pathlib.Path) -> None:
    target = repo / "project_sources/large.txt"
    original = target.read_text(encoding="utf-8")
    target.write_text(new_text, encoding="utf-8")
    patch = run(["git", "diff", "--", "project_sources/large.txt"], repo).stdout
    target.write_text(original, encoding="utf-8")
    write(patch_path, patch)


def make_patch_set(repo: pathlib.Path, changes: dict[str, str], patch_path: pathlib.Path) -> None:
    original: dict[str, str] = {}
    for rel_path, new_text in changes.items():
        target = repo / rel_path
        original[rel_path] = target.read_text(encoding="utf-8")
        target.write_text(new_text, encoding="utf-8")
    patch = run(["git", "diff", "--", *sorted(changes)], repo).stdout
    for rel_path, old_text in original.items():
        (repo / rel_path).write_text(old_text, encoding="utf-8")
    write(patch_path, patch)


def git_blob(repo: pathlib.Path, rel_path: str) -> str:
    return run(["git", "ls-files", "-s", "--", rel_path], repo).stdout.split()[1]


def request_body(repo: pathlib.Path, request_id: str, patch_rel: str, patch_file: pathlib.Path, *, target_branch: str = "feature/apply-patch-target") -> dict[str, object]:
    return {
        "schema": "dcoir.ops.apply_patch_request.v1",
        "request_id": request_id,
        "mode": "apply",
        "target_branch": target_branch,
        "target_path": "project_sources/large.txt",
        "allowed_roots": ["project_sources"],
        "patch_path": patch_rel,
        "expected_patch_sha256": sha256(patch_file),
        "expected_target_blob_sha": git_blob(repo, "project_sources/large.txt"),
        "expected_current_sha256": sha256(repo / "project_sources/large.txt"),
        "expected_new_sha256": hashlib.sha256(b"alpha\nBETA\n").hexdigest(),
        "commit_message": f"Apply selftest patch {request_id}",
    }


def patch_set_request_body(repo: pathlib.Path, request_id: str, patch_rel: str, patch_file: pathlib.Path, *, target_branch: str) -> dict[str, object]:
    return {
        "schema": "dcoir.ops.apply_patch_request.v2",
        "request_id": request_id,
        "mode": "patch-set",
        "operation": "apply",
        "target_branch": target_branch,
        "patch_path": patch_rel,
        "expected_patch_sha256": sha256(patch_file),
        "targets": [
            {
                "path": "project_sources/large.txt",
                "allowed_roots": ["project_sources"],
                "expected_target_blob_sha": git_blob(repo, "project_sources/large.txt"),
                "expected_current_sha256": sha256(repo / "project_sources/large.txt"),
                "expected_new_sha256": hashlib.sha256(b"alpha\nBETA\n").hexdigest(),
            },
            {
                "path": "project_sources/other.txt",
                "allowed_roots": ["project_sources"],
                "expected_target_blob_sha": git_blob(repo, "project_sources/other.txt"),
                "expected_current_sha256": sha256(repo / "project_sources/other.txt"),
                "expected_new_sha256": hashlib.sha256(b"two\n").hexdigest(),
            },
        ],
        "commit_message": f"Apply selftest patch set {request_id}",
    }
