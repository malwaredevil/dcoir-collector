from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

EXPECTED_HEAD = "781a480bb306ff7e0bf1fd55302636a0176ad5c5"
EXPECTED_TREE = "ecfe9870cff993695d58c9ee8f35525a0ccd9902"
BRANCH = "refactor/issue-550-dcoir-runtime-consolidation"
EXPECTED_PATCH_SHA = "923ffd839b1bacb4cf2a2801a0916bae783d7470e2c320cf1804740b48302cb1"
EXPECTED_PATH_COUNT = 18
COMMIT_MESSAGE = "refactor(dcoir): consolidate review configuration"

repo = Path(os.environ.get("DCOIR_REPO_ROOT") or os.environ.get("GITHUB_WORKSPACE") or ".").resolve()
downloads = Path(os.environ.get("DCOIR_DOWNLOADS_DIR") or os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()).resolve()
preview = repo / ".github/chatgpt_staging/exec_scripts/issue550-pr553-readable-config-strong-loader-guard-preview-013.py"
patch = downloads / "issue550-pr553-readable-config-strong-loader-guard-preview-013.patch"
summary = downloads / "issue550-pr553-publish-canonical-review-config-001-summary.txt"
worktree = downloads / "issue550-pr553-publish-canonical-review-config-001-worktree"


def run(*args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(args, cwd=cwd, text=True, capture_output=True)
    print(completed.stdout, end="")
    print(completed.stderr, end="", file=sys.stderr)
    if check and completed.returncode:
        raise RuntimeError(f"command failed {completed.returncode}: {args}")
    return completed


def output(*args: str, cwd: Path | None = None) -> str:
    return run(*args, cwd=cwd).stdout.strip()


run("git", "fetch", "--no-tags", "origin", f"+refs/heads/{BRANCH}:refs/remotes/origin/{BRANCH}", "+refs/heads/main:refs/remotes/origin/main", cwd=repo)
remote_head = output("git", "rev-parse", f"refs/remotes/origin/{BRANCH}", cwd=repo)
if remote_head != EXPECTED_HEAD:
    raise RuntimeError(f"PR head drift before publication: expected {EXPECTED_HEAD}, observed {remote_head}")
actual_tree = output("git", "rev-parse", f"{EXPECTED_HEAD}^{{tree}}", cwd=repo)
if actual_tree != EXPECTED_TREE:
    raise RuntimeError(f"PR tree drift before publication: expected {EXPECTED_TREE}, observed {actual_tree}")

run(sys.executable, str(preview), cwd=repo)
if not patch.is_file():
    raise RuntimeError("strong-guard candidate patch was not generated")
patch_sha = hashlib.sha256(patch.read_bytes()).hexdigest()
if patch_sha != EXPECTED_PATCH_SHA:
    raise RuntimeError(f"candidate patch SHA drift: expected {EXPECTED_PATCH_SHA}, observed {patch_sha}")

patch_paths: list[str] = []
for line in patch.read_text(encoding="utf-8").splitlines():
    if line.startswith("diff --git a/"):
        right = line.split(" b/", 1)[1]
        patch_paths.append(right)
if len(patch_paths) != EXPECTED_PATH_COUNT or len(set(patch_paths)) != EXPECTED_PATH_COUNT:
    raise RuntimeError(f"candidate path inventory drift: {len(patch_paths)} paths")
if any(path.startswith(".github/workflows/") for path in patch_paths):
    raise RuntimeError("candidate unexpectedly changes workflows")
if any("runtime_patch_v59" in path for path in patch_paths):
    raise RuntimeError("candidate unexpectedly introduces v59+")

if worktree.exists():
    shutil.rmtree(worktree, ignore_errors=True)
run("git", "worktree", "add", "--detach", str(worktree), EXPECTED_HEAD, cwd=repo)
try:
    if output("git", "rev-parse", "HEAD", cwd=worktree) != EXPECTED_HEAD:
        raise RuntimeError("publication worktree is not on expected head")
    if output("git", "rev-parse", "HEAD^{tree}", cwd=worktree) != EXPECTED_TREE:
        raise RuntimeError("publication worktree is not on expected tree")

    run("git", "apply", "--check", str(patch), cwd=worktree)
    run("git", "apply", str(patch), cwd=worktree)
    changed = [line.strip() for line in output("git", "status", "--porcelain", cwd=worktree).splitlines() if line.strip()]
    if len(changed) != EXPECTED_PATH_COUNT:
        raise RuntimeError(f"publication worktree changed-path count drift: {len(changed)}")
    run("git", "diff", "--check", cwd=worktree)

    run("git", "add", "--all", cwd=worktree)
    run("git", "diff", "--cached", "--check", cwd=worktree)
    staged_paths = [line.strip() for line in output("git", "diff", "--cached", "--name-only", cwd=worktree).splitlines() if line.strip()]
    if staged_paths != patch_paths:
        raise RuntimeError(f"staged path order/inventory drift: {staged_paths!r}")

    run("git", "config", "user.name", "Malware Devil", cwd=worktree)
    run("git", "config", "user.email", "34285973+malwaredevil@users.noreply.github.com", cwd=worktree)
    run("git", "commit", "-m", COMMIT_MESSAGE, cwd=worktree)
    new_head = output("git", "rev-parse", "HEAD", cwd=worktree)
    new_tree = output("git", "rev-parse", "HEAD^{tree}", cwd=worktree)
    parent = output("git", "rev-parse", "HEAD^", cwd=worktree)
    if parent != EXPECTED_HEAD:
        raise RuntimeError(f"publication parent drift: expected {EXPECTED_HEAD}, observed {parent}")

    run("git", "fetch", "--no-tags", "origin", f"+refs/heads/{BRANCH}:refs/remotes/origin/{BRANCH}", cwd=repo)
    remote_head_before_push = output("git", "rev-parse", f"refs/remotes/origin/{BRANCH}", cwd=repo)
    if remote_head_before_push != EXPECTED_HEAD:
        raise RuntimeError(f"PR head raced before push: expected {EXPECTED_HEAD}, observed {remote_head_before_push}")

    run("git", "push", "origin", f"HEAD:refs/heads/{BRANCH}", cwd=worktree)
    ls_remote = output("git", "ls-remote", "origin", f"refs/heads/{BRANCH}", cwd=worktree)
    pushed_head = ls_remote.split()[0] if ls_remote else ""
    if pushed_head != new_head:
        raise RuntimeError(f"post-push branch readback mismatch: expected {new_head}, observed {pushed_head}")

    summary.write_text(
        "\n".join(
            [
                "result=PASS",
                f"previous_head={EXPECTED_HEAD}",
                f"previous_tree={EXPECTED_TREE}",
                f"source_patch_sha256={patch_sha}",
                f"path_count={len(patch_paths)}",
                f"new_head={new_head}",
                f"new_tree={new_tree}",
                f"branch={BRANCH}",
                f"commit_message={COMMIT_MESSAGE}",
                "push=non-force",
                "copilot_triggered=false",
                "dcoir_self_review_triggered=false",
                "draft_to_ready=false",
                "merge=false",
            ]
        ) + "\n",
        encoding="utf-8",
    )
    print(summary.read_text(encoding="utf-8"), end="")
    print("ISSUE550_PR553_PUBLISH_CANONICAL_REVIEW_CONFIG_001_PASS")
finally:
    run("git", "worktree", "remove", "--force", str(worktree), cwd=repo, check=False)
    shutil.rmtree(worktree, ignore_errors=True)
