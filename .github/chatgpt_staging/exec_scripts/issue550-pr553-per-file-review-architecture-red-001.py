from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

EXPECTED_HEAD = "c3f718ae226158b9fad09f2b8693740b7d47de4c"
BRANCH = "refactor/issue-550-dcoir-runtime-consolidation"
REQUEST_ID = "issue550-pr553-per-file-review-architecture-red-001"

repo = Path(os.environ.get("GITHUB_WORKSPACE") or ".").resolve()
temp_root = Path(os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()).resolve()
worktree = temp_root / f"{REQUEST_ID}-worktree"


def run(*args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    cp = subprocess.run(args, cwd=cwd, text=True, capture_output=True)
    print(cp.stdout, end="")
    print(cp.stderr, end="", file=sys.stderr)
    if check and cp.returncode:
        raise RuntimeError(f"command failed {cp.returncode}: {args}")
    return cp


def out(*args: str, cwd: Path | None = None) -> str:
    return run(*args, cwd=cwd).stdout.strip()


run("git", "fetch", "--no-tags", "origin", f"+refs/heads/{BRANCH}:refs/remotes/origin/{BRANCH}", cwd=repo)
actual_head = out("git", "rev-parse", f"refs/remotes/origin/{BRANCH}", cwd=repo)
assert actual_head == EXPECTED_HEAD, f"PR head drift: expected {EXPECTED_HEAD}, observed {actual_head}"

if worktree.exists():
    shutil.rmtree(worktree, ignore_errors=True)
run("git", "worktree", "add", "--detach", str(worktree), EXPECTED_HEAD, cwd=repo)
try:
    scripts = worktree / ".github/dcoir_review/scripts"
    canonical_path = scripts / "dcoir_review/per_file_review.py"
    assert canonical_path.is_file(), (
        "RED: expected one canonical dcoir_review/per_file_review.py owner for the per-file review pipeline"
    )

    semantic_source = (scripts / "dcoir_review/semantic_result_reuse.py").read_text(encoding="utf-8")
    routing_source = (scripts / "dcoir_review/per_file_routing.py").read_text(encoding="utf-8")
    canonical_source = canonical_path.read_text(encoding="utf-8")

    assert "module.review_single_file_context =" not in semantic_source, (
        "semantic_result_reuse still replaces review_single_file_context"
    )
    assert "module.review_single_file_context =" not in routing_source, (
        "per_file_routing still replaces review_single_file_context"
    )
    assert "_dcoir_per_file_routing_original_review_single_file_context" not in routing_source, (
        "per_file_routing still stores the prior per-file review callable"
    )
    assert "semantic_result_reuse" in canonical_source
    assert "per_file_routing" in canonical_source

    sys.path.insert(0, str(scripts))
    from dcoir_review.entrypoint import DcoirReviewEntrypoint
    from dcoir_review import per_file_review

    entrypoint = DcoirReviewEntrypoint()
    assert "dcoir_review.semantic_result_reuse" not in entrypoint.terminal_patch_module_names
    assert entrypoint.stage_local_patch_module_names == ("dcoir_review.per_file_review",)

    module = entrypoint.import_module(entrypoint.review_module_name)
    entrypoint.apply_runtime_patches(module)
    canonical = module.review_single_file_context
    assert canonical.__module__ == "dcoir_review.per_file_review", canonical.__module__

    stored = sorted(
        name
        for name, value in vars(module).items()
        if "review_single_file_context" in name
        and name.startswith("_dcoir_")
        and callable(value)
    )
    assert stored == [], f"stored-original per-file callables remain: {stored}"

    before = module.review_single_file_context
    per_file_review.apply_pareto_context_module(module)
    assert module.review_single_file_context is before, "canonical per-file owner is not idempotent"

    print("unexpectedly green: canonical per-file review architecture already present")
finally:
    run("git", "worktree", "remove", "--force", str(worktree), cwd=repo, check=False)
    shutil.rmtree(worktree, ignore_errors=True)
