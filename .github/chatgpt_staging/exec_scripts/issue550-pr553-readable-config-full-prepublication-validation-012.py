from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

EXPECTED_HEAD = "781a480bb306ff7e0bf1fd55302636a0176ad5c5"
EXPECTED_TREE = "ecfe9870cff993695d58c9ee8f35525a0ccd9902"
EXPECTED_PATCH_SHA = "2eec4439b09fd3a20fef8e78f8a502f4bfae03930b0c4c118c8b27a18d178806"
EXPECTED_PARSER_SHA = "7a7bf1b5a842c29a42ede8851cf090ab8019adf74fc2ae7a8bd305839a682d76"
BRANCH = "refactor/issue-550-dcoir-runtime-consolidation"
BASE = "9dc055d81fba2bcd4e840ad1e9c9645bdc6a6a20"
REQUEST_ID = "issue550-pr553-readable-config-full-prepublication-validation-012"

repo = Path(os.environ.get("DCOIR_REPO_ROOT") or os.environ.get("GITHUB_WORKSPACE") or ".").resolve()
downloads = Path(os.environ.get("DCOIR_DOWNLOADS_DIR") or os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()).resolve()
preview = repo / ".github/chatgpt_staging/exec_scripts/issue550-pr553-canonical-config-readable-preview-010.py"
patch = downloads / "issue550-pr553-canonical-config-readable-preview-010.patch"
worktree = downloads / f"{REQUEST_ID}-worktree"
summary_path = downloads / f"{REQUEST_ID}-summary.txt"

for key in (
    "OPENROUTER_API_KEY", "GITHUB_TOKEN", "GH_TOKEN", "DCOIR_GITHUB_FG_TOKEN",
    "DCOIR_GITHUB_CL_TOKEN", "DCOIR_GEMINI_API", "DCOIR_OPENAI_API_KEY",
    "DCOIR_OPENAI_PROJECT_ID", "OPENAI_API_KEY",
):
    os.environ.pop(key, None)
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["PYTHONPYCACHEPREFIX"] = str(downloads / f"{REQUEST_ID}-pycache")


def run(*args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(args, cwd=cwd, text=True, capture_output=True)
    print(completed.stdout, end="")
    print(completed.stderr, end="", file=sys.stderr)
    if check and completed.returncode:
        raise RuntimeError(f"command failed {completed.returncode}: {args}")
    return completed


def check_output(*args: str, cwd: Path | None = None) -> str:
    return run(*args, cwd=cwd).stdout.strip()


# Reproduce the already-proven readable patch under the same exact-head guards.
preview_run = run(sys.executable, str(preview), cwd=repo)
if preview_run.returncode:
    raise SystemExit(preview_run.returncode)
if not patch.is_file():
    raise RuntimeError("readable canonical-config patch missing")
patch_sha = hashlib.sha256(patch.read_bytes()).hexdigest()
if patch_sha != EXPECTED_PATCH_SHA:
    raise RuntimeError(f"readable patch drift: expected {EXPECTED_PATCH_SHA}, observed {patch_sha}")

run("git", "-C", str(repo), "fetch", "--no-tags", "origin", f"+refs/heads/{BRANCH}:refs/remotes/origin/{BRANCH}", "+refs/heads/main:refs/remotes/origin/main")
if check_output("git", "-C", str(repo), "rev-parse", f"refs/remotes/origin/{BRANCH}") != EXPECTED_HEAD:
    raise RuntimeError("PR source head drift")
if check_output("git", "-C", str(repo), "rev-parse", f"{EXPECTED_HEAD}^{{tree}}") != EXPECTED_TREE:
    raise RuntimeError("PR source tree drift")
run("git", "-C", str(repo), "merge-base", "--is-ancestor", BASE, EXPECTED_HEAD)
live_main = check_output("git", "-C", str(repo), "rev-parse", "refs/remotes/origin/main")
run("git", "-C", str(repo), "merge-base", "--is-ancestor", BASE, live_main)
main_delta = check_output("git", "-C", str(repo), "diff", "--name-only", f"{BASE}...{live_main}").splitlines()
non_staging = [path for path in main_delta if path and not path.startswith(".github/chatgpt_staging/")]
if non_staging:
    raise RuntimeError(f"live main product drift detected: {non_staging}")

if worktree.exists():
    run("git", "-C", str(repo), "worktree", "remove", "--force", str(worktree), check=False)
run("git", "-C", str(repo), "worktree", "add", "--detach", str(worktree), EXPECTED_HEAD)
try:
    if check_output("git", "rev-parse", "HEAD", cwd=worktree) != EXPECTED_HEAD:
        raise RuntimeError("wrong isolated worktree head")
    if check_output("git", "rev-parse", "HEAD^{tree}", cwd=worktree) != EXPECTED_TREE:
        raise RuntimeError("wrong isolated worktree tree")
    run("git", "apply", "--check", str(patch), cwd=worktree)
    run("git", "apply", str(patch), cwd=worktree)

    status_lines = check_output("git", "status", "--porcelain", cwd=worktree).splitlines()
    if not any(line.endswith(".github/dcoir_review/scripts/dcoir_review/review_config.py") for line in status_lines):
        raise RuntimeError("review_config.py missing from transformed worktree status")
    changed_paths = []
    for line in status_lines:
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        changed_paths.append(path)
    if any(path.startswith(".github/workflows/") for path in changed_paths):
        raise RuntimeError("workflow source changed in canonical-config slice")
    if any(re.search(r"runtime_patch_v(?:5[9]|[6-9][0-9]|[1-9][0-9]{2,})", path) for path in changed_paths):
        raise RuntimeError("v59+ production patch introduced")

    changed_python = [path for path in changed_paths if path.endswith(".py") and (worktree / path).is_file()]
    if not changed_python:
        raise RuntimeError("no changed Python files found")
    run(sys.executable, "-m", "py_compile", *changed_python, cwd=worktree)
    run("git", "diff", "--check", cwd=worktree)

    python_tests = [
        ".github/dcoir_review/scripts/openrouter_pr_review_pareto_context_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_finding_family_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v16_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_precision_guard_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v20_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_finding_verifier_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_quality_gate_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_normalized_finding_selection_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_verified_finding_render_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_repair_pipeline_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_sentinel_selection_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_anchor_normalization_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_repair_reliability_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_repair_routing_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v30_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v31_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v32_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v33_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_semantic_evidence_hardening_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v35_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v36_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_semantic_adjudication_normalization_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_repair_contract_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_repair_contract_critic_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_semantic_adjudication_confidence_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_per_file_coverage_recovery_v40_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_credit_aware_concurrency_v49_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_incremental_review_frontier_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_incremental_review_provenance_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_semantic_review_ledger_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_semantic_result_reuse_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_semantic_result_reuse_state_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v44_scope_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v44_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_review_context_ledger_integration_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_publication_disposition_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v46_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_verified_finding_gate_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_verified_finding_gate_publication_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_semantic_candidate_identity_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_per_file_routing_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_review_scope_guard_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_structured_result_recovery_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v53_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v54_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_semantic_adjudication_recovery_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v56_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v56_followup_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v57_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_provider_transport_retry_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_architecture_b_benchmark_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_semantic_recall_corpus_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_precision_regression_selftest.py",
        ".github/dcoir_review/scripts/openrouter_pr_review_hardened_selftest.py",
        ".github/dcoir_review/scripts/openrouter_pr_review_quality_recovery_selftest.py",
        ".github/dcoir_review/scripts/openrouter_pr_review_summary_problem_selftest.py",
    ]
    if len(python_tests) != 56:
        raise RuntimeError(f"expected 56 Python registry commands, observed {len(python_tests)}")
    for index, test in enumerate(python_tests, 1):
        print(f"=== Registry {index:02d}/59 {test} ===")
        run(sys.executable, test, cwd=worktree)

    git_exe = Path(check_output("where", "git.exe", cwd=worktree).splitlines()[0])
    git_root = git_exe.parent.parent
    git_bash = git_root / "bin" / "bash.exe"
    if not git_bash.is_file():
        raise RuntimeError(f"Git-for-Windows Bash not found: {git_bash}")
    print("=== Registry 57/59 validate-codex-local ===")
    run(str(git_bash), ".github/dcoir_review/scripts/validate-codex-local.sh", cwd=worktree)

    powershell = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    if not powershell.is_file():
        raise RuntimeError(f"native Windows PowerShell not found: {powershell}")
    print("=== Registry 58/59 native Windows PowerShell 5.1 parser ===")
    parser = run(
        str(powershell), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
        ".github/dcoir_review/scripts/validate-windows-powershell-51.ps1", "-AllowEmpty",
        cwd=worktree,
    )
    parser_text = parser.stdout + parser.stderr
    if "Validating 293 PowerShell file(s)." not in parser_text:
        raise RuntimeError("native Windows parser did not validate expected 293 files")
    if f"ASSEMBLED_HARNESS_SHA256={EXPECTED_PARSER_SHA}" not in parser_text:
        raise RuntimeError("native Windows parser harness SHA mismatch")

    print("=== Registry 59/59 CodeQL workflow config ===")
    run(sys.executable, ".github/dcoir_review/scripts/validate-codeql-security-workflow.py", cwd=worktree)

    semantic = run(sys.executable, ".github/dcoir_review/scripts/dcoir_review_semantic_recall_corpus_selftest.py", cwd=worktree)
    if "12 cases, 10 finding classes, 2 clean classes" not in semantic.stdout + semantic.stderr:
        raise RuntimeError("semantic recall summary drift")
    precision_run = run(sys.executable, ".github/dcoir_review/scripts/dcoir_review_precision_regression_selftest.py", cwd=worktree)
    precision = json.loads(precision_run.stdout)
    if float(precision["false_positive_suppression_rate"]) != 1.0:
        raise RuntimeError("false-positive suppression rate changed")
    if float(precision["true_positive_retention_rate"]) != 1.0:
        raise RuntimeError("true-positive retention rate changed")
    if precision.get("regressions"):
        raise RuntimeError(f"precision regressions detected: {precision['regressions']}")

    inventory_run = run(sys.executable, ".github/dcoir_review/scripts/dcoir_review_architecture_inventory.py", cwd=worktree)
    inventory = json.loads(inventory_run.stdout)
    if inventory.get("missing_modules"):
        raise RuntimeError(f"missing architecture inventory modules: {inventory['missing_modules']}")
    if int(inventory["production_patch_count"]) != 56:
        raise RuntimeError(f"production component count drift: {inventory['production_patch_count']}")
    if int(inventory["max_numbered_version"]) != 57:
        raise RuntimeError(f"max numbered production version drift: {inventory['max_numbered_version']}")

    scripts = worktree / ".github" / "dcoir_review" / "scripts"
    production_config_owners = [
        "dcoir_review_required_runtime_patch_v32.py",
        "dcoir_review_required_runtime_patch_v35.py",
        "dcoir_review_required_runtime_patch_v44.py",
        "dcoir_review/publication_disposition.py",
        "dcoir_review_required_runtime_patch_v46.py",
        "dcoir_review/verified_finding_gate.py",
        "dcoir_review/semantic_candidate_identity.py",
        "dcoir_review/per_file_routing.py",
        "dcoir_review_required_runtime_patch_v54.py",
        "dcoir_review_required_runtime_patch_v56.py",
    ]
    forbidden_storage_literals = (
        "_dcoir_review_v32_original_load_pareto_context_config",
        "_dcoir_review_v35_original_load_pareto_context_config",
        "_dcoir_v44_original_load_pareto_context_config",
        "_dcoir_review_publication_disposition_original_load_pareto_context_config",
        "_dcoir_v46_original_load_pareto_context_config",
        "_dcoir_review_verified_finding_gate_original_load_pareto_context_config",
        "_dcoir_review_semantic_candidate_identity_original_load_pareto_context_config",
        "_dcoir_per_file_routing_original_load_pareto_context_config",
        "_dcoir_review_v54_original_load_pareto_context_config",
    )
    for relative in production_config_owners:
        text = (scripts / relative).read_text(encoding="utf-8")
        if "def _patch_config_loader(" in text or "def _install_config_loader(" in text:
            raise RuntimeError(f"config loader wrapper definition remains in {relative}")
        if any(storage in text for storage in forbidden_storage_literals):
            raise RuntimeError(f"config loader stored-original shim remains in {relative}")

    loader_guard = (
        "import sys;from pathlib import Path;"
        "p=Path('.github/dcoir_review/scripts').resolve();sys.path.insert(0,str(p));"
        "from dcoir_review.entrypoint import DcoirReviewEntrypoint as E;"
        "e=E();m=e.import_module(e.review_module_name);e.apply_runtime_patches(m);"
        "assert m.load_pareto_context_config.__module__==e.review_module_name;"
        "assert not any(k.endswith('original_load_pareto_context_config') and callable(v) for k,v in vars(m).items());"
        "print(m.load_pareto_context_config.__module__)"
    )
    loader_result = run(sys.executable, "-c", loader_guard, cwd=worktree)
    if "openrouter_pr_review_pareto_context" not in loader_result.stdout:
        raise RuntimeError("canonical loader ownership confirmation missing")

    review_config = scripts / "dcoir_review" / "review_config.py"
    if review_config.stat().st_size != 9251:
        raise RuntimeError(f"readable review_config byte-size drift: {review_config.stat().st_size}")
    review_text = review_config.read_text(encoding="utf-8")
    expected_helpers = (
        "_as_string_list", "_optional_string_list", "_positive_int", "_optional_positive_int",
        "_unit_float", "_apply_adversarial_confirmation", "_apply_semantic_adjudication",
        "_apply_candidate_escalation", "_apply_publication_and_context", "_apply_per_file_routing",
        "_initialize_run_telemetry_fail_soft", "_apply_repair_critic_batching", "apply_review_config",
    )
    if sum(1 for name in expected_helpers if f"def {name}(" in review_text) != 13:
        raise RuntimeError("readable review_config helper inventory drift")

    summary_lines = [
        "result=PASS",
        f"exact_head={EXPECTED_HEAD}",
        f"exact_tree={EXPECTED_TREE}",
        f"source_patch_sha256={patch_sha}",
        "registry_commands=59",
        "python_registry_commands=56",
        "production_components=56",
        "max_numbered_version=57",
        "review_config_bytes=9251",
        "review_config_functions=13",
        "removed_runtime_config_wrappers=10",
        "semantic_recall=12/10/2",
        "precision_fp_suppression=1.0",
        "precision_tp_retention=1.0",
        "precision_regressions=0",
        "windows_parser_files=293",
        f"windows_parser_harness_sha256={EXPECTED_PARSER_SHA}",
        "validate_codex_local=pass",
        "codeql_workflow_config=pass",
        "canonical_loader_owner=openrouter_pr_review_pareto_context",
        "stored_original_config_loader_shims=0",
        "workflow_source_changes=0",
        "v59_plus_changes=0",
        "no_inference=true",
        "no_provider_calls=true",
    ]
    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8", newline="\n")
    print(summary_path.read_text(encoding="utf-8"), end="")
    print("ISSUE550_PR553_READABLE_CONFIG_FULL_PREPUBLICATION_VALIDATION_012_PASS")
finally:
    run("git", "-C", str(repo), "worktree", "remove", "--force", str(worktree), check=False)
