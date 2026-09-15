from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

EXPECTED_HEAD = "1210e9689200c7a97a8b48c0d6a1dc792675700d"
EXPECTED_TREE = "72b50e19e9da8eaaf566a79726a6615442c9c94c"
BASE = "9dc055d81fba2bcd4e840ad1e9c9645bdc6a6a20"
BRANCH = "refactor/issue-550-dcoir-runtime-consolidation"
REQUEST_ID = "issue550-pr553-canonical-review-config-validation-001"
TERMINAL = "ISSUE550_PR553_CANONICAL_REVIEW_CONFIG_VALIDATION_001_PASS"

repo = Path(os.environ.get("DCOIR_REPO_ROOT") or os.environ.get("GITHUB_WORKSPACE") or ".").resolve()
downloads = Path(os.environ.get("DCOIR_DOWNLOADS_DIR") or os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()).resolve()
worktree = downloads / f"{REQUEST_ID}-worktree"
summary = downloads / f"{REQUEST_ID}-summary.txt"

for key in (
    "OPENROUTER_API_KEY", "GITHUB_TOKEN", "GH_TOKEN", "DCOIR_GITHUB_FG_TOKEN",
    "DCOIR_GITHUB_CL_TOKEN", "DCOIR_GEMINI_API", "DCOIR_OPENAI_API_KEY",
    "DCOIR_OPENAI_PROJECT_ID", "OPENAI_API_KEY",
):
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


def parse_validation_commands(path: Path) -> list[str]:
    commands: list[str] = []
    active = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw == "validation_commands:":
            active = True
            continue
        if active:
            if raw.startswith("  - "):
                commands.append(raw[4:].strip())
                continue
            if raw and not raw.startswith(" ") and not raw.startswith("#"):
                break
    return commands

run("git", "fetch", "--no-tags", "origin", f"+refs/heads/{BRANCH}:refs/remotes/origin/{BRANCH}", "+refs/heads/main:refs/remotes/origin/main", cwd=repo)
actual_head = out("git", "rev-parse", f"refs/remotes/origin/{BRANCH}", cwd=repo)
if actual_head != EXPECTED_HEAD:
    raise RuntimeError(f"PR head drift: expected {EXPECTED_HEAD}, observed {actual_head}")
actual_tree = out("git", "rev-parse", f"{EXPECTED_HEAD}^{{tree}}", cwd=repo)
if actual_tree != EXPECTED_TREE:
    raise RuntimeError(f"PR tree drift: expected {EXPECTED_TREE}, observed {actual_tree}")
run("git", "merge-base", "--is-ancestor", BASE, EXPECTED_HEAD, cwd=repo)
live_main = out("git", "rev-parse", "refs/remotes/origin/main", cwd=repo)
run("git", "merge-base", "--is-ancestor", BASE, live_main, cwd=repo)
main_delta = [p for p in out("git", "diff", "--name-only", f"{BASE}...{live_main}", cwd=repo).splitlines() if p]
non_staging = [p for p in main_delta if not p.startswith(".github/chatgpt_staging/")]
if non_staging:
    raise RuntimeError(f"live main product drift detected: {non_staging}")

if worktree.exists():
    shutil.rmtree(worktree, ignore_errors=True)
run("git", "worktree", "add", "--detach", str(worktree), EXPECTED_HEAD, cwd=repo)
try:
    if out("git", "rev-parse", "HEAD", cwd=worktree) != EXPECTED_HEAD:
        raise RuntimeError("wrong isolated HEAD")
    if out("git", "rev-parse", "HEAD^{tree}", cwd=worktree) != EXPECTED_TREE:
        raise RuntimeError("wrong isolated tree")
    if out("git", "status", "--porcelain", cwd=worktree):
        raise RuntimeError("exact-head worktree is dirty before validation")

    scripts = worktree / ".github" / "dcoir_review" / "scripts"
    os.environ["PYTHONPATH"] = str(scripts) + (os.pathsep + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else "")

    changed_python = [
        p for p in out("git", "diff", "--name-only", f"{BASE}...{EXPECTED_HEAD}", cwd=worktree).splitlines()
        if p.endswith(".py") and (worktree / p).is_file()
    ]
    if not changed_python:
        raise RuntimeError("no changed Python files found")
    run(sys.executable, "-m", "py_compile", *changed_python, cwd=worktree)

    commands = parse_validation_commands(worktree / ".github/dcoir_review/openrouter-pr-review-pareto.yml")
    if len(commands) != 56:
        raise RuntimeError(f"expected 56 governed Python commands, observed {len(commands)}")
    for index, command in enumerate(commands, 1):
        argv = shlex.split(command, posix=True)
        if argv[0] in {"python", "python3"}:
            argv[0] = sys.executable
        print(f"=== Registry {index:02d}/59 {command} ===")
        run(*argv, cwd=worktree)

    git_exe = shutil.which("git")
    if not git_exe:
        raise RuntimeError("git executable not found")
    git_root = Path(git_exe).resolve().parent.parent
    bash = git_root / "bin" / "bash.exe"
    if not bash.is_file():
        raise RuntimeError(f"Git-for-Windows bash not found: {bash}")
    print("=== Registry 57/59 validate-codex-local ===")
    run(str(bash), ".github/dcoir_review/scripts/validate-codex-local.sh", cwd=worktree)

    powershell = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    if not powershell.is_file():
        raise RuntimeError(f"native Windows PowerShell not found: {powershell}")
    ps_command = (
        "$ErrorActionPreference='Stop'; "
        "function Get-FileHash { [CmdletBinding()] param([Parameter(Mandatory=$true)][string]$LiteralPath,[ValidateSet('SHA256')][string]$Algorithm='SHA256'); "
        "$stream=[System.IO.File]::OpenRead($LiteralPath); $sha=[System.Security.Cryptography.SHA256]::Create(); try { "
        "$hash=([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-',''); "
        "[pscustomobject]@{Algorithm='SHA256';Hash=$hash;Path=[System.IO.Path]::GetFullPath($LiteralPath)} } finally { $sha.Dispose(); $stream.Dispose() } }; "
        "& '.github/dcoir_review/scripts/validate-windows-powershell-51.ps1' -AllowEmpty"
    )
    print("=== Registry 58/59 native Windows PowerShell 5.1 parser ===")
    parser = run(str(powershell), "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_command, cwd=worktree)
    parser_text = parser.stdout + parser.stderr
    if "Validating 293 PowerShell file(s)." not in parser_text:
        raise RuntimeError("Windows parser did not validate 293 files")
    if "ASSEMBLED_HARNESS_SHA256=7a7bf1b5a842c29a42ede8851cf090ab8019adf74fc2ae7a8bd305839a682d76" not in parser_text:
        raise RuntimeError("assembled harness SHA mismatch")

    print("=== Registry 59/59 CodeQL workflow config ===")
    run(sys.executable, ".github/dcoir_review/scripts/validate-codeql-security-workflow.py", cwd=worktree)

    recall = run(sys.executable, ".github/dcoir_review/scripts/dcoir_review_semantic_recall_corpus_selftest.py", cwd=worktree)
    if "12 cases, 10 finding classes, 2 clean classes" not in recall.stdout + recall.stderr:
        raise RuntimeError("semantic recall summary drift")
    precision_cp = run(sys.executable, ".github/dcoir_review/scripts/dcoir_review_precision_regression_selftest.py", cwd=worktree)
    precision = json.loads(precision_cp.stdout)
    if float(precision["false_positive_suppression_rate"]) != 1.0:
        raise RuntimeError("false-positive suppression drift")
    if float(precision["true_positive_retention_rate"]) != 1.0:
        raise RuntimeError("true-positive retention drift")
    if precision.get("regressions"):
        raise RuntimeError(f"precision regressions: {precision['regressions']}")

    inventory = json.loads(run(sys.executable, ".github/dcoir_review/scripts/dcoir_review_architecture_inventory.py", cwd=worktree).stdout)
    if inventory.get("missing_modules"):
        raise RuntimeError(f"missing modules: {inventory['missing_modules']}")
    if int(inventory["production_patch_count"]) != 56 or int(inventory["max_numbered_version"]) != 57:
        raise RuntimeError("architecture inventory count/version drift")

    review_config = scripts / "dcoir_review" / "review_config.py"
    if not review_config.is_file():
        raise RuntimeError("canonical review_config.py missing")
    if review_config.stat().st_size > 12000:
        raise RuntimeError(f"review_config.py exceeds 12 KB: {review_config.stat().st_size}")
    base_loader = scripts / "dcoir_review/pareto_context/part_01_config_payload.py"
    if "review_config.apply_review_config(config, data, hardened)" not in base_loader.read_text(encoding="utf-8"):
        raise RuntimeError("base Pareto loader does not delegate to canonical review_config")

    former_owners = [
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
    for rel in former_owners:
        text = (scripts / rel).read_text(encoding="utf-8")
        if "def _patch_config_loader(" in text or "def _install_config_loader(" in text:
            raise RuntimeError(f"historical config-loader wrapper reintroduced in {rel}")
        if "original_load_pareto_context_config" in text:
            raise RuntimeError(f"historical config-loader storage reintroduced in {rel}")

    loader_test = (scripts / "dcoir_review_runtime_module_loader_selftest.py").read_text(encoding="utf-8")
    for marker in (
        "canonical_loader = module.load_pareto_context_config",
        "replaced canonical load_pareto_context_config",
        "original_load_pareto_context_config",
        "review_config.apply_review_config(config, data, hardened)",
    ):
        if marker not in loader_test:
            raise RuntimeError(f"strong loader guard marker missing: {marker}")
    run(sys.executable, ".github/dcoir_review/scripts/dcoir_review_runtime_module_loader_selftest.py", cwd=worktree)

    if out("git", "status", "--porcelain", cwd=worktree):
        raise RuntimeError("validation mutated exact-head worktree")

    summary.write_text(
        "\n".join([
            "result=PASS",
            f"exact_head={EXPECTED_HEAD}",
            f"exact_tree={EXPECTED_TREE}",
            "registry_commands=59",
            "production_components=56",
            "max_numbered_version=57",
            "missing_modules=0",
            "canonical_review_config=true",
            f"canonical_review_config_bytes={review_config.stat().st_size}",
            "former_config_owners=10",
            "strong_stage_loader_guard=true",
            "semantic_recall=12/10/2",
            "false_positive_suppression=1.0",
            "true_positive_retention=1.0",
            "precision_regressions=0",
            "windows_powershell_files=293",
            "assembled_harness_sha256=7a7bf1b5a842c29a42ede8851cf090ab8019adf74fc2ae7a8bd305839a682d76",
            "no_inference=true",
            "no_provider_calls=true",
            "dcoir_self_review_triggered=false",
            "copilot_triggered=false",
            "draft_to_ready=false",
            "merge=false",
        ]) + "\n",
        encoding="utf-8",
    )
    print(summary.read_text(encoding="utf-8"), end="")
    print(TERMINAL)
finally:
    run("git", "worktree", "remove", "--force", str(worktree), cwd=repo, check=False)
    shutil.rmtree(worktree, ignore_errors=True)
