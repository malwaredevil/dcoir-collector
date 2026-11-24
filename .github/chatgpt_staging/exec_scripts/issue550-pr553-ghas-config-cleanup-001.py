from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

EXPECTED_HEAD = "1210e9689200c7a97a8b48c0d6a1dc792675700d"
EXPECTED_TREE = "72b50e19e9da8eaaf566a79726a6615442c9c94c"
BRANCH = "refactor/issue-550-dcoir-runtime-consolidation"
COMMIT_MESSAGE = "fix(dcoir): address canonical config CodeQL findings"

repo = Path(os.environ.get("DCOIR_REPO_ROOT") or os.environ.get("GITHUB_WORKSPACE") or ".").resolve()
downloads = Path(os.environ.get("DCOIR_DOWNLOADS_DIR") or os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()).resolve()
worktree = downloads / "issue550-pr553-ghas-config-cleanup-001-worktree"
summary = downloads / "issue550-pr553-ghas-config-cleanup-001-summary.txt"

for key in ("OPENROUTER_API_KEY", "DCOIR_GEMINI_API", "DCOIR_OPENAI_API_KEY", "DCOIR_OPENAI_PROJECT_ID", "OPENAI_API_KEY"):
    os.environ.pop(key, None)
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"


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
if out("git", "rev-parse", f"refs/remotes/origin/{BRANCH}", cwd=repo) != EXPECTED_HEAD:
    raise RuntimeError("PR head drift before GHAS cleanup")
if out("git", "rev-parse", f"{EXPECTED_HEAD}^{{tree}}", cwd=repo) != EXPECTED_TREE:
    raise RuntimeError("PR tree drift before GHAS cleanup")

if worktree.exists():
    shutil.rmtree(worktree, ignore_errors=True)
run("git", "worktree", "add", "--detach", str(worktree), EXPECTED_HEAD, cwd=repo)
try:
    scripts = worktree / ".github/dcoir_review/scripts"
    review_config = scripts / "dcoir_review/review_config.py"
    v32 = scripts / "dcoir_review_required_runtime_patch_v32.py"

    config_text = review_config.read_text(encoding="utf-8")
    old_block = """        telemetry._note_telemetry_error(config)\n        except Exception:\n            pass\n"""
    new_block = """        telemetry._note_telemetry_error(config)\n        except Exception:\n            # Telemetry is observational only; config loading must remain available\n            # even when recording the telemetry failure also fails.\n            return\n"""
    if config_text.count(old_block) != 1:
        raise RuntimeError(f"review_config fail-soft anchor count={config_text.count(old_block)}")
    review_config.write_text(config_text.replace(old_block, new_block, 1), encoding="utf-8", newline="\n")

    v32_text = v32.read_text(encoding="utf-8")
    for dead_import in (
        "from dcoir_review import finding_verifier as v21\n",
        "from dcoir_review import repair_pipeline as repair\n",
    ):
        if v32_text.count(dead_import) != 1:
            raise RuntimeError(f"v32 dead-import anchor count for {dead_import!r}: {v32_text.count(dead_import)}")
        v32_text = v32_text.replace(dead_import, "", 1)
    v32.write_text(v32_text, encoding="utf-8", newline="\n")

    changed = [p for p in out("git", "status", "--porcelain", cwd=worktree).splitlines() if p]
    if len(changed) != 2:
        raise RuntimeError(f"unexpected GHAS cleanup path count: {changed}")
    run("git", "diff", "--check", cwd=worktree)

    os.environ["PYTHONPATH"] = str(scripts) + (os.pathsep + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else "")
    run(sys.executable, "-m", "py_compile", str(review_config), str(v32), cwd=worktree)
    focused = [
        ".github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v32_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v54_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_runtime_module_loader_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_architecture_b_benchmark_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_semantic_recall_corpus_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_precision_regression_selftest.py",
    ]
    for test in focused:
        run(sys.executable, test, cwd=worktree)

    after_config = review_config.read_text(encoding="utf-8")
    after_v32 = v32.read_text(encoding="utf-8")
    if "telemetry._note_telemetry_error(config)\n        except Exception:\n            pass" in after_config:
        raise RuntimeError("silent telemetry except remains")
    if "Telemetry is observational only" not in after_config or "even when recording the telemetry failure also fails" not in after_config:
        raise RuntimeError("fail-soft telemetry explanation missing")
    if "from dcoir_review import finding_verifier as v21" in after_v32:
        raise RuntimeError("unused v21 import remains")
    if "from dcoir_review import repair_pipeline as repair" in after_v32:
        raise RuntimeError("unused repair import remains")

    run("git", "add", "--all", cwd=worktree)
    run("git", "diff", "--cached", "--check", cwd=worktree)
    staged = [p for p in out("git", "diff", "--cached", "--name-only", cwd=worktree).splitlines() if p]
    expected_paths = [
        ".github/dcoir_review/scripts/dcoir_review/review_config.py",
        ".github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v32.py",
    ]
    if staged != expected_paths:
        raise RuntimeError(f"staged GHAS cleanup inventory drift: {staged}")

    run("git", "config", "user.name", "Malware Devil", cwd=worktree)
    run("git", "config", "user.email", "34285973+malwaredevil@users.noreply.github.com", cwd=worktree)
    run("git", "commit", "-m", COMMIT_MESSAGE, cwd=worktree)
    new_head = out("git", "rev-parse", "HEAD", cwd=worktree)
    new_tree = out("git", "rev-parse", "HEAD^{tree}", cwd=worktree)
    if out("git", "rev-parse", "HEAD^", cwd=worktree) != EXPECTED_HEAD:
        raise RuntimeError("GHAS cleanup parent drift")

    run("git", "fetch", "--no-tags", "origin", f"+refs/heads/{BRANCH}:refs/remotes/origin/{BRANCH}", cwd=repo)
    if out("git", "rev-parse", f"refs/remotes/origin/{BRANCH}", cwd=repo) != EXPECTED_HEAD:
        raise RuntimeError("PR head raced before GHAS cleanup push")
    run("git", "push", "origin", f"HEAD:refs/heads/{BRANCH}", cwd=worktree)
    pushed = out("git", "ls-remote", "origin", f"refs/heads/{BRANCH}", cwd=worktree).split()[0]
    if pushed != new_head:
        raise RuntimeError("GHAS cleanup post-push readback mismatch")

    summary.write_text(
        "\n".join([
            "result=PASS",
            f"previous_head={EXPECTED_HEAD}",
            f"new_head={new_head}",
            f"new_tree={new_tree}",
            "changed_paths=2",
            "codeql_631=fail_soft_telemetry_explained",
            "codeql_632=unused_v21_import_removed",
            "codeql_633=unused_repair_import_removed",
            "focused_tests=6_passed",
            "push=non-force",
            "no_inference=true",
            "no_provider_calls=true",
            "copilot_triggered=false",
            "dcoir_self_review_triggered=false",
            "draft_to_ready=false",
            "merge=false",
        ]) + "\n",
        encoding="utf-8",
    )
    print(summary.read_text(encoding="utf-8"), end="")
    print("ISSUE550_PR553_GHAS_CONFIG_CLEANUP_001_PASS")
finally:
    run("git", "worktree", "remove", "--force", str(worktree), cwd=repo, check=False)
    shutil.rmtree(worktree, ignore_errors=True)
