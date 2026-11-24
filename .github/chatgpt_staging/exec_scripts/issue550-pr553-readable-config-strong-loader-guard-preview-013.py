from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

EXPECTED_HEAD = "781a480bb306ff7e0bf1fd55302636a0176ad5c5"
EXPECTED_TREE = "ecfe9870cff993695d58c9ee8f35525a0ccd9902"
INPUT_PATCH_SHA = "2eec4439b09fd3a20fef8e78f8a502f4bfae03930b0c4c118c8b27a18d178806"
BRANCH = "refactor/issue-550-dcoir-runtime-consolidation"
REQUEST_ID = "issue550-pr553-readable-config-strong-loader-guard-preview-013"

repo = Path(os.environ.get("DCOIR_REPO_ROOT") or os.environ.get("GITHUB_WORKSPACE") or ".").resolve()
downloads = Path(os.environ.get("DCOIR_DOWNLOADS_DIR") or os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()).resolve()
preview = repo / ".github/chatgpt_staging/exec_scripts/issue550-pr553-canonical-config-readable-preview-010.py"
input_patch = downloads / "issue550-pr553-canonical-config-readable-preview-010.patch"
out_patch = downloads / f"{REQUEST_ID}.patch"
summary = downloads / f"{REQUEST_ID}-summary.txt"
worktree = downloads / f"{REQUEST_ID}-worktree"

for key in (
    "OPENROUTER_API_KEY", "GITHUB_TOKEN", "GH_TOKEN", "DCOIR_GITHUB_FG_TOKEN",
    "DCOIR_GITHUB_CL_TOKEN", "DCOIR_GEMINI_API", "DCOIR_OPENAI_API_KEY",
    "DCOIR_OPENAI_PROJECT_ID", "OPENAI_API_KEY",
):
    os.environ.pop(key, None)
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"


def run(*args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(args, cwd=cwd, text=True, capture_output=True)
    print(completed.stdout, end="")
    print(completed.stderr, end="", file=sys.stderr)
    if check and completed.returncode:
        raise RuntimeError(f"command failed {completed.returncode}: {args}")
    return completed


run(sys.executable, str(preview), cwd=repo)
if not input_patch.is_file():
    raise RuntimeError("readable input patch missing")
input_sha = hashlib.sha256(input_patch.read_bytes()).hexdigest()
if input_sha != INPUT_PATCH_SHA:
    raise RuntimeError(f"readable input patch drift: {input_sha}")

run("git", "-C", str(repo), "fetch", "--no-tags", "origin", f"+refs/heads/{BRANCH}:refs/remotes/origin/{BRANCH}")
head = run("git", "-C", str(repo), "rev-parse", f"refs/remotes/origin/{BRANCH}").stdout.strip()
if head != EXPECTED_HEAD:
    raise RuntimeError(f"source head drift: {head}")
tree = run("git", "-C", str(repo), "rev-parse", f"{EXPECTED_HEAD}^{{tree}}").stdout.strip()
if tree != EXPECTED_TREE:
    raise RuntimeError(f"source tree drift: {tree}")

if worktree.exists():
    run("git", "-C", str(repo), "worktree", "remove", "--force", str(worktree), check=False)
run("git", "-C", str(repo), "worktree", "add", "--detach", str(worktree), EXPECTED_HEAD)
try:
    run("git", "apply", "--check", str(input_patch), cwd=worktree)
    run("git", "apply", str(input_patch), cwd=worktree)

    test_path = worktree / ".github/dcoir_review/scripts/dcoir_review_runtime_module_loader_selftest.py"
    text = test_path.read_text(encoding="utf-8")
    old = '''def assert_canonical_config_loader_ownership() -> None:\n    base=(SCRIPTS/"dcoir_review"/"pareto_context"/"part_01_config_payload.py").read_text(encoding="utf-8")\n    assert "review_config.apply_review_config(config, data, hardened)" in base\n    for r in ("dcoir_review_required_runtime_patch_v32.py","dcoir_review_required_runtime_patch_v35.py","dcoir_review_required_runtime_patch_v44.py","dcoir_review/publication_disposition.py","dcoir_review_required_runtime_patch_v46.py","dcoir_review/verified_finding_gate.py","dcoir_review/semantic_candidate_identity.py","dcoir_review/per_file_routing.py","dcoir_review_required_runtime_patch_v54.py","dcoir_review_required_runtime_patch_v56.py"):\n        x=(SCRIPTS/r).read_text(encoding="utf-8"); assert "def _patch_config_loader(" not in x,r; assert "def _install_config_loader(" not in x,r\n    e=DcoirReviewEntrypoint(); m=e.import_module(e.review_module_name); e.apply_runtime_patches(m); assert m.load_pareto_context_config.__module__==e.review_module_name\n'''
    new = '''def assert_canonical_config_loader_ownership() -> None:\n    base = (\n        SCRIPTS / "dcoir_review" / "pareto_context" / "part_01_config_payload.py"\n    ).read_text(encoding="utf-8")\n    assert "review_config.apply_review_config(config, data, hardened)" in base\n\n    former_config_owners = (\n        "dcoir_review_required_runtime_patch_v32.py",\n        "dcoir_review_required_runtime_patch_v35.py",\n        "dcoir_review_required_runtime_patch_v44.py",\n        "dcoir_review/publication_disposition.py",\n        "dcoir_review_required_runtime_patch_v46.py",\n        "dcoir_review/verified_finding_gate.py",\n        "dcoir_review/semantic_candidate_identity.py",\n        "dcoir_review/per_file_routing.py",\n        "dcoir_review_required_runtime_patch_v54.py",\n        "dcoir_review_required_runtime_patch_v56.py",\n    )\n    for relative in former_config_owners:\n        source = (SCRIPTS / relative).read_text(encoding="utf-8")\n        assert "def _patch_config_loader(" not in source, relative\n        assert "def _install_config_loader(" not in source, relative\n\n    entrypoint = DcoirReviewEntrypoint()\n    module = entrypoint.import_module(entrypoint.review_module_name)\n    canonical_loader = module.load_pareto_context_config\n    assert canonical_loader.__module__ == entrypoint.review_module_name\n\n    production_groups = (\n        "patch_module_names",\n        "terminal_patch_module_names",\n        "post_terminal_patch_module_names",\n        "candidate_integrity_patch_module_names",\n        "stage_local_patch_module_names",\n        "execution_policy_patch_module_names",\n        "telemetry_patch_module_names",\n        "post_telemetry_patch_module_names",\n    )\n    for group_name in production_groups:\n        for patch_name in getattr(entrypoint, group_name):\n            entrypoint._apply_patch_modules(module, (patch_name,))\n            assert module.load_pareto_context_config is canonical_loader, (\n                f"{patch_name} replaced canonical load_pareto_context_config"\n            )\n\n    stored_originals = [\n        name\n        for name, value in vars(module).items()\n        if name.endswith("original_load_pareto_context_config") and callable(value)\n    ]\n    assert stored_originals == [], stored_originals\n'''
    if text.count(old) != 1:
        raise RuntimeError(f"weak canonical-loader guard anchor count={text.count(old)}")
    test_path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")

    run(sys.executable, ".github/dcoir_review/scripts/dcoir_review_runtime_module_loader_selftest.py", cwd=worktree)
    run(sys.executable, ".github/dcoir_review/scripts/dcoir_review_architecture_b_benchmark_selftest.py", cwd=worktree)
    run("git", "diff", "--check", cwd=worktree)

    review_config = ".github/dcoir_review/scripts/dcoir_review/review_config.py"
    run("git", "add", "-N", review_config, cwd=worktree)
    patch_bytes = subprocess.check_output(["git", "diff", "--binary"], cwd=worktree)
    out_patch.write_bytes(patch_bytes)
    patch_sha = hashlib.sha256(patch_bytes).hexdigest()
    patch_text = patch_bytes.decode("utf-8", errors="replace")
    if "replaced canonical load_pareto_context_config" not in patch_text:
        raise RuntimeError("strong stage-by-stage canonical-loader guard missing from emitted patch")
    if "production_groups = (" not in patch_text:
        raise RuntimeError("production-group loader guard missing from emitted patch")

    lines = [
        "result=PASS",
        f"exact_head={EXPECTED_HEAD}",
        f"exact_tree={EXPECTED_TREE}",
        f"input_patch_sha256={input_sha}",
        f"source_patch_sha256={patch_sha}",
        "strong_loader_stage_guard=true",
        "former_config_owners=10",
        "runtime_module_loader_selftest=pass",
        "architecture_b_benchmark_selftest=pass",
        "no_inference=true",
        "no_provider_calls=true",
    ]
    summary.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(summary.read_text(encoding="utf-8"), end="")
    print("ISSUE550_PR553_READABLE_CONFIG_STRONG_LOADER_GUARD_PREVIEW_013_PASS")
finally:
    run("git", "-C", str(repo), "worktree", "remove", "--force", str(worktree), check=False)
