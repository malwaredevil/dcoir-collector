#!/usr/bin/env python3
"""Self-tests for the governed ops apply-patch request tool."""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import tempfile

from lib.apply_patch_request_selftest_helpers import (
    TOOL,
    init_repo,
    make_patch,
    make_patch_set,
    patch_set_request_body,
    request_body,
    run,
    write,
)


def test_happy_path(repo: pathlib.Path) -> None:
    no_global_git_identity = {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}
    request_id = "selftest-good"
    request_dir = repo / "ops/requests/apply_patch" / request_id
    patch_rel = f"ops/requests/apply_patch/{request_id}/change.patch"
    patch_file = repo / patch_rel
    make_patch(repo, "alpha\nBETA\n", patch_file)
    write(request_dir / "request.json", json.dumps(request_body(repo, request_id, patch_rel, patch_file), indent=2) + "\n")

    run([sys.executable, str(TOOL), "validate", "--repo", str(repo), "--request", str(request_dir / "request.json")], repo)
    report_dir = repo / "out/report"
    run(
        [
            sys.executable,
            str(TOOL),
            "apply",
            "--repo",
            str(repo),
            "--request",
            str(request_dir / "request.json"),
            "--local-only",
            "--no-push",
            "--report-dir",
            str(report_dir),
        ],
        repo,
        env=no_global_git_identity,
    )
    assert (repo / "project_sources/large.txt").read_text(encoding="utf-8") == "alpha\nBETA\n"
    assert json.loads((report_dir / "result.json").read_text(encoding="utf-8"))["result"] == "success"
    assert run(["git", "config", "--local", "--get", "user.name"], repo).stdout.strip() == "github-actions[bot]"
    assert run(["git", "config", "--local", "--get", "user.email"], repo).stdout.strip() == "41898282+github-actions[bot]@users.noreply.github.com"


def test_patch_set_happy_path(repo: pathlib.Path) -> None:
    request_id = "selftest-patch-set"
    target_branch = "feature/apply-patch-set-target"
    request_dir = repo / "ops/requests/apply_patch" / request_id
    patch_rel = f"ops/requests/apply_patch/{request_id}/change.diff"
    patch_file = repo / patch_rel
    run(["git", "checkout", "main"], repo)
    run(["git", "branch", "-f", target_branch, "main"], repo)
    make_patch_set(
        repo,
        {
            "project_sources/large.txt": "alpha\nBETA\n",
            "project_sources/other.txt": "two\n",
        },
        patch_file,
    )
    write(request_dir / "request.json", json.dumps(patch_set_request_body(repo, request_id, patch_rel, patch_file, target_branch=target_branch), indent=2) + "\n")

    validate = run([sys.executable, str(TOOL), "validate", "--repo", str(repo), "--request", str(request_dir / "request.json")], repo)
    validate_result = json.loads(validate.stdout)
    assert validate_result["target_path"] is None
    assert validate_result["target_paths"] == ["project_sources/large.txt", "project_sources/other.txt"]
    report_dir = repo / "out/patch-set-report"
    run(
        [
            sys.executable,
            str(TOOL),
            "apply",
            "--repo",
            str(repo),
            "--request",
            str(request_dir / "request.json"),
            "--local-only",
            "--no-push",
            "--report-dir",
            str(report_dir),
        ],
        repo,
    )
    assert (repo / "project_sources/large.txt").read_text(encoding="utf-8") == "alpha\nBETA\n"
    assert (repo / "project_sources/other.txt").read_text(encoding="utf-8") == "two\n"
    result = json.loads((report_dir / "result.json").read_text(encoding="utf-8"))
    assert result["result"] == "success"
    assert result["schema"] == "dcoir.ops.apply_patch_request.v2"
    assert result["mode"] == "patch-set"
    assert result["operation"] == "apply"
    assert len(result["apply_plan"]["files"]) == 2
    assert {item["stale_base_result"] for item in result["apply_plan"]["files"]} == {"pass"}


def test_patch_set_rejects_create(repo: pathlib.Path) -> None:
    request_id = "selftest-patch-set-create"
    target_branch = "feature/apply-patch-set-create"
    request_dir = repo / "ops/requests/apply_patch" / request_id
    patch_rel = f"ops/requests/apply_patch/{request_id}/change.patch"
    patch_file = repo / patch_rel
    run(["git", "checkout", "main"], repo)
    run(["git", "branch", "-f", target_branch, "main"], repo)
    write(repo / "project_sources/new.txt", "created\n")
    patch_file.parent.mkdir(parents=True, exist_ok=True)
    patch_file.write_text(run(["git", "diff", "--no-index", "--", "/dev/null", "project_sources/new.txt"], repo, check=False).stdout, encoding="utf-8")
    (repo / "project_sources/new.txt").unlink()
    body = patch_set_request_body(repo, request_id, patch_rel, patch_file, target_branch=target_branch)
    body["targets"] = [
        {
            "path": "project_sources/new.txt",
            "allowed_roots": ["project_sources"],
            "expected_current_sha256": hashlib.sha256(b"").hexdigest(),
        }
    ]
    write(request_dir / "request.json", json.dumps(body, indent=2) + "\n")
    proc = run([sys.executable, str(TOOL), "validate", "--repo", str(repo), "--request", str(request_dir / "request.json")], repo, check=False)
    assert proc.returncode != 0
    assert "new file mode" in proc.stderr


def test_rejects_default_branch(repo: pathlib.Path) -> None:
    request_id = "selftest-main"
    request_dir = repo / "ops/requests/apply_patch" / request_id
    patch_rel = f"ops/requests/apply_patch/{request_id}/change.patch"
    patch_file = repo / patch_rel
    run(["git", "checkout", "main"], repo)
    make_patch(repo, "alpha\nBETA\n", patch_file)
    body = request_body(repo, request_id, patch_rel, patch_file, target_branch="main")
    write(request_dir / "request.json", json.dumps(body, indent=2) + "\n")
    proc = run([sys.executable, str(TOOL), "validate", "--repo", str(repo), "--request", str(request_dir / "request.json")], repo, check=False)
    assert proc.returncode != 0
    assert "default branch" in proc.stderr


def test_rejects_multifile_patch(repo: pathlib.Path) -> None:
    request_id = "selftest-multifile"
    request_dir = repo / "ops/requests/apply_patch" / request_id
    patch_rel = f"ops/requests/apply_patch/{request_id}/change.patch"
    patch_file = repo / patch_rel
    run(["git", "checkout", "main"], repo)
    write(repo / "project_sources/large.txt", "alpha\nBETA\n")
    write(repo / "project_sources/other.txt", "two\n")
    patch_file.parent.mkdir(parents=True, exist_ok=True)
    patch_file.write_text(run(["git", "diff", "--", "project_sources"], repo).stdout, encoding="utf-8")
    run(["git", "checkout", "--", "project_sources"], repo)
    body = request_body(repo, request_id, patch_rel, patch_file)
    body["expected_new_sha256"] = hashlib.sha256(b"alpha\nBETA\n").hexdigest()
    write(request_dir / "request.json", json.dumps(body, indent=2) + "\n")
    proc = run([sys.executable, str(TOOL), "validate", "--repo", str(repo), "--request", str(request_dir / "request.json")], repo, check=False)
    assert proc.returncode != 0
    assert "patch must touch only target_path" in proc.stderr


def test_rejects_plain_delete_patch(repo: pathlib.Path) -> None:
    request_id = "selftest-delete"
    request_dir = repo / "ops/requests/apply_patch" / request_id
    patch_rel = f"ops/requests/apply_patch/{request_id}/change.patch"
    patch_file = repo / patch_rel
    run(["git", "checkout", "main"], repo)
    patch_file.parent.mkdir(parents=True, exist_ok=True)
    patch_file.write_text(
        "diff --git a/project_sources/large.txt b/project_sources/large.txt\n"
        "--- a/project_sources/large.txt\n"
        "+++ /dev/null\n"
        "@@ -1,2 +0,0 @@\n"
        "-alpha\n"
        "-beta\n",
        encoding="utf-8",
    )
    body = request_body(repo, request_id, patch_rel, patch_file)
    body.pop("expected_new_sha256", None)
    write(request_dir / "request.json", json.dumps(body, indent=2) + "\n")
    proc = run([sys.executable, str(TOOL), "validate", "--repo", str(repo), "--request", str(request_dir / "request.json")], repo, check=False)
    assert proc.returncode != 0
    assert "must not create or delete" in proc.stderr


def test_rejects_non_string_digest(repo: pathlib.Path) -> None:
    request_id = "selftest-nonstring-digest"
    request_dir = repo / "ops/requests/apply_patch" / request_id
    patch_rel = f"ops/requests/apply_patch/{request_id}/change.patch"
    patch_file = repo / patch_rel
    run(["git", "checkout", "main"], repo)
    make_patch(repo, "alpha\nBETA\n", patch_file)
    body = request_body(repo, request_id, patch_rel, patch_file)
    body["expected_target_blob_sha"] = 12345
    write(request_dir / "request.json", json.dumps(body, indent=2) + "\n")
    proc = run([sys.executable, str(TOOL), "validate", "--repo", str(repo), "--request", str(request_dir / "request.json")], repo, check=False)
    assert proc.returncode != 0
    assert "expected_target_blob_sha must be a string" in proc.stderr
    assert "Traceback" not in proc.stderr


def test_rejects_string_boolean_override(repo: pathlib.Path) -> None:
    request_id = "selftest-string-bool"
    request_dir = repo / "ops/requests/apply_patch" / request_id
    patch_rel = f"ops/requests/apply_patch/{request_id}/change.patch"
    patch_file = repo / patch_rel
    run(["git", "checkout", "main"], repo)
    make_patch(repo, "alpha\nBETA\n", patch_file)
    body = request_body(repo, request_id, patch_rel, patch_file, target_branch="main")
    body["allow_default_branch"] = "false"
    body["default_branch_reason"] = "string booleans must not unlock this gate"
    write(request_dir / "request.json", json.dumps(body, indent=2) + "\n")
    proc = run([sys.executable, str(TOOL), "validate", "--repo", str(repo), "--request", str(request_dir / "request.json")], repo, check=False)
    assert proc.returncode != 0
    assert "allow_default_branch must be a boolean" in proc.stderr


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="dcoir-ops-patch-") as tmp:
        repo = pathlib.Path(tmp)
        init_repo(repo)
        test_happy_path(repo)
        test_patch_set_happy_path(repo)
        test_patch_set_rejects_create(repo)
        test_rejects_default_branch(repo)
        test_rejects_multifile_patch(repo)
        test_rejects_plain_delete_patch(repo)
        test_rejects_non_string_digest(repo)
        test_rejects_string_boolean_override(repo)
    print("apply_patch_request selftests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
