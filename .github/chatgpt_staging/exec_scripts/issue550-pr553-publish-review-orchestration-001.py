from __future__ import annotations

import base64
import gzip
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

EXPECTED_HEAD = "f10aa75bbdf54110329409371d7aa86404b6ba65"
EXPECTED_TREE = "91021d85eec18569fe52492c13959cd8b28a0331"
PRODUCT_BASE = "9dc055d81fba2bcd4e840ad1e9c9645bdc6a6a20"
BRANCH = "refactor/issue-550-dcoir-runtime-consolidation"
EXPECTED_PATCH_SHA = "6a46b28eb86043e3e9a4dd9b87208f152e38311d3418e0951982f136df0b761e"
EXPECTED_GZIP_SHA = "562b3c663b577c155ad4925d4443ad8765f6b74b4fe9cbf0a5dda8b455d48833"
EXPECTED_PATH_COUNT = 31
PAYLOAD_REL = ".github/chatgpt_staging/exec_payloads/issue550-pr553-review-orchestration-prepublication-validation-001.patch.gz.b64"
COMMIT_MESSAGE = "refactor(dcoir): consolidate hybrid review orchestration"
REQUEST_ID = "issue550-pr553-publish-review-orchestration-001"
TERMINAL = "ISSUE550_PR553_PUBLISH_REVIEW_ORCHESTRATION_001_PASS"

repo = Path(os.environ.get("DCOIR_REPO_ROOT") or os.environ.get("GITHUB_WORKSPACE") or ".").resolve()
downloads = Path(os.environ.get("DCOIR_DOWNLOADS_DIR") or os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()).resolve()
patch_path = downloads / f"{REQUEST_ID}.patch"
worktree = downloads / f"{REQUEST_ID}-worktree"
summary = downloads / f"{REQUEST_ID}-summary.txt"


def run(*args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    cp = subprocess.run(args, cwd=cwd, text=True, capture_output=True)
    print(cp.stdout, end="")
    print(cp.stderr, end="", file=sys.stderr)
    if check and cp.returncode:
        raise RuntimeError(f"command failed {cp.returncode}: {args}")
    return cp


def out(*args: str, cwd: Path | None = None) -> str:
    return run(*args, cwd=cwd).stdout.strip()


run("git", "fetch", "--no-tags", "origin", f"+refs/heads/{BRANCH}:refs/remotes/origin/{BRANCH}", "+refs/heads/main:refs/remotes/origin/main", cwd=repo)
remote_head = out("git", "rev-parse", f"refs/remotes/origin/{BRANCH}", cwd=repo)
if remote_head != EXPECTED_HEAD:
    raise RuntimeError(f"PR head drift before publication: expected {EXPECTED_HEAD}, observed {remote_head}")
if out("git", "rev-parse", f"{EXPECTED_HEAD}^{{tree}}", cwd=repo) != EXPECTED_TREE:
    raise RuntimeError("PR tree drift before publication")

live_main = out("git", "rev-parse", "refs/remotes/origin/main", cwd=repo)
non_staging = [p for p in out("git", "diff", "--name-only", f"{PRODUCT_BASE}...{live_main}", cwd=repo).splitlines() if p and not p.startswith(".github/chatgpt_staging/")]
if non_staging:
    raise RuntimeError(f"live main product drift before publication: {non_staging}")

encoded = "".join((repo / PAYLOAD_REL).read_text(encoding="utf-8").split())
compressed = base64.b64decode(encoded, validate=True)
if hashlib.sha256(compressed).hexdigest() != EXPECTED_GZIP_SHA:
    raise RuntimeError("compressed payload SHA drift")
patch_bytes = gzip.decompress(compressed)
if hashlib.sha256(patch_bytes).hexdigest() != EXPECTED_PATCH_SHA:
    raise RuntimeError("patch SHA drift")
patch_path.write_bytes(patch_bytes)
patch_paths = [line.split(" b/", 1)[1] for line in patch_bytes.decode("utf-8").splitlines() if line.startswith("diff --git a/")]
if len(patch_paths) != EXPECTED_PATH_COUNT or len(set(patch_paths)) != EXPECTED_PATH_COUNT:
    raise RuntimeError(f"patch path inventory drift: {len(patch_paths)}")
if any(p.startswith(".github/workflows/") for p in patch_paths):
    raise RuntimeError("workflow change unexpectedly present")
if any("runtime_patch_v59" in p for p in patch_paths):
    raise RuntimeError("v59+ unexpectedly present")

if worktree.exists():
    shutil.rmtree(worktree, ignore_errors=True)
run("git", "worktree", "add", "--detach", str(worktree), EXPECTED_HEAD, cwd=repo)
try:
    if out("git", "rev-parse", "HEAD", cwd=worktree) != EXPECTED_HEAD:
        raise RuntimeError("publication worktree wrong head")
    if out("git", "rev-parse", "HEAD^{tree}", cwd=worktree) != EXPECTED_TREE:
        raise RuntimeError("publication worktree wrong tree")
    run("git", "apply", "--check", str(patch_path), cwd=worktree)
    run("git", "apply", str(patch_path), cwd=worktree)
    run("git", "diff", "--check", cwd=worktree)
    run("git", "add", "--all", cwd=worktree)
    run("git", "diff", "--cached", "--check", cwd=worktree)
    staged_paths = [p for p in out("git", "diff", "--cached", "--name-only", cwd=worktree).splitlines() if p]
    if staged_paths != patch_paths:
        raise RuntimeError(f"staged path inventory/order drift: {staged_paths!r}")

    run("git", "config", "user.name", "Malware Devil", cwd=worktree)
    run("git", "config", "user.email", "34285973+malwaredevil@users.noreply.github.com", cwd=worktree)
    run("git", "commit", "-m", COMMIT_MESSAGE, cwd=worktree)
    new_head = out("git", "rev-parse", "HEAD", cwd=worktree)
    new_tree = out("git", "rev-parse", "HEAD^{tree}", cwd=worktree)
    if out("git", "rev-parse", "HEAD^", cwd=worktree) != EXPECTED_HEAD:
        raise RuntimeError("publication parent drift")

    run("git", "fetch", "--no-tags", "origin", f"+refs/heads/{BRANCH}:refs/remotes/origin/{BRANCH}", cwd=repo)
    if out("git", "rev-parse", f"refs/remotes/origin/{BRANCH}", cwd=repo) != EXPECTED_HEAD:
        raise RuntimeError("PR head raced before push")
    run("git", "push", "origin", f"HEAD:refs/heads/{BRANCH}", cwd=worktree)
    readback = out("git", "ls-remote", "origin", f"refs/heads/{BRANCH}", cwd=worktree).split()[0]
    if readback != new_head:
        raise RuntimeError(f"post-push branch readback mismatch: {readback}")

    summary.write_text("\n".join([
        "result=PASS",
        f"previous_head={EXPECTED_HEAD}",
        f"previous_tree={EXPECTED_TREE}",
        f"source_patch_sha256={EXPECTED_PATCH_SHA}",
        f"path_count={EXPECTED_PATH_COUNT}",
        f"new_head={new_head}",
        f"new_tree={new_tree}",
        f"branch={BRANCH}",
        f"commit_message={COMMIT_MESSAGE}",
        "push=non-force",
        "copilot_triggered=false",
        "dcoir_self_review_triggered=false",
        "draft_to_ready=false",
        "merge=false",
    ]) + "\n", encoding="utf-8")
    print(summary.read_text(encoding="utf-8"), end="")
    print(TERMINAL)
finally:
    run("git", "worktree", "remove", "--force", str(worktree), cwd=repo, check=False)
    shutil.rmtree(worktree, ignore_errors=True)
