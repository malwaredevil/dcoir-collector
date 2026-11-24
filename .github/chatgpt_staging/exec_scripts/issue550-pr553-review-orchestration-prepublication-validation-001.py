from __future__ import annotations

import base64
import gzip
import hashlib
import importlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

EXPECTED_HEAD = "f10aa75bbdf54110329409371d7aa86404b6ba65"
EXPECTED_TREE = "91021d85eec18569fe52492c13959cd8b28a0331"
BRANCH = "refactor/issue-550-dcoir-runtime-consolidation"
REQUEST_ID = "issue550-pr553-review-orchestration-prepublication-validation-001"
TERMINAL = "ISSUE550_PR553_REVIEW_ORCHESTRATION_PREPUBLICATION_VALIDATION_001_PASS"
EXPECTED_PATCH_SHA = "6a46b28eb86043e3e9a4dd9b87208f152e38311d3418e0951982f136df0b761e"
EXPECTED_GZIP_SHA = "562b3c663b577c155ad4925d4443ad8765f6b74b4fe9cbf0a5dda8b455d48833"
PAYLOAD_REL = ".github/chatgpt_staging/exec_payloads/issue550-pr553-review-orchestration-prepublication-validation-001.patch.gz.b64"
EXPECTED_PATHS = (
    ".github/dcoir_review/ARCHITECTURE.md",
    ".github/dcoir_review/openrouter-pr-review-pareto.yml",
    ".github/dcoir_review/scripts/dcoir_review/entrypoint.py",
    ".github/dcoir_review/scripts/dcoir_review/quality_gate.py",
    ".github/dcoir_review/scripts/dcoir_review/review_orchestration.py",
    ".github/dcoir_review/scripts/dcoir_review/review_scope_guard_hooks.py",
    ".github/dcoir_review/scripts/dcoir_review/selftests/base_selftest/part_03.py",
    ".github/dcoir_review/scripts/dcoir_review/semantic_adjudication_confidence.py",
    ".github/dcoir_review/scripts/dcoir_review/semantic_result_reuse.py",
    ".github/dcoir_review/scripts/dcoir_review/semantic_review_ledger.py",
    ".github/dcoir_review/scripts/dcoir_review/semantic_review_ledger_hooks.py",
    ".github/dcoir_review/scripts/dcoir_review/structured_result_disposition.py",
    ".github/dcoir_review/scripts/dcoir_review/structured_result_recovery.py",
    ".github/dcoir_review/scripts/dcoir_review_architecture_b_benchmark_contract.py",
    ".github/dcoir_review/scripts/dcoir_review_quality_gate_selftest.py",
    ".github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v16_selftest.py",
    ".github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v32.py",
    ".github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v32_selftest.py",
    ".github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v35.py",
    ".github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v35_selftest.py",
    ".github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v44.py",
    ".github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v44_selftest.py",
    ".github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v46.py",
    ".github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v46_selftest.py",
    ".github/dcoir_review/scripts/dcoir_review_review_scope_guard_selftest.py",
    ".github/dcoir_review/scripts/dcoir_review_review_scope_guard_selftest_support.py",
    ".github/dcoir_review/scripts/dcoir_review_runtime_module_loader_selftest.py",
    ".github/dcoir_review/scripts/dcoir_review_semantic_adjudication_normalization_selftest.py",
    ".github/dcoir_review/scripts/dcoir_review_semantic_result_reuse_selftest.py",
    ".github/dcoir_review/scripts/dcoir_review_semantic_review_ledger_selftest.py",
    ".github/dcoir_review/scripts/dcoir_review_structured_result_recovery_selftest.py",
)
EXPECTED_STAGE_ORDER = (
    "quality-gate",
    "adversarial-confirmation",
    "semantic-adjudication",
    "semantic-adjudication-confidence",
    "semantic-review-ledger",
    "semantic-result-reuse",
    "candidate-scoped-escalation",
    "canonical-semantic-context",
    "review-scope-terminal-translation",
    "structured-result-disposition",
)

repo = Path(os.environ.get("DCOIR_REPO_ROOT") or os.environ.get("GITHUB_WORKSPACE") or ".").resolve()
downloads = Path(os.environ.get("DCOIR_DOWNLOADS_DIR") or os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()).resolve()
worktree = downloads / f"{REQUEST_ID}-worktree"
summary = downloads / f"{REQUEST_ID}-summary.txt"
patch_file = downloads / f"{REQUEST_ID}.patch"

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


def native_powershell(repo_worktree: Path) -> subprocess.CompletedProcess[str]:
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
    return run(str(powershell), "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_command, cwd=repo_worktree)


def independent_secret_scan(root: Path) -> None:
    patterns = (
        re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
        re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"-----BEGIN (?:RSA|OPENSSH|EC|DSA) PRIVATE KEY-----"),
        re.compile(r"(?i)(?:api[_-]?key|secret|token|password)\s*[:=]\s*[\"']?[A-Za-z0-9_./+=-]{16,}"),
    )
    required_token = re.compile(r"REQUIRED_TOKEN\s*=\s*['\"]APPLY_[A-Z0-9_]+['\"]")
    uppercase_symbol = re.compile(r"['\"]?[A-Z][A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|KEY)[A-Z0-9_]*['\"]?")
    findings: list[str] = []
    for rel in EXPECTED_PATHS:
        path = root / rel
        if not path.is_file():
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if not any(p.search(line) for p in patterns):
                continue
            if required_token.search(line) or uppercase_symbol.search(line):
                continue
            findings.append(f"{rel}:{lineno}:{line[:240]}")
    if findings:
        raise RuntimeError("independent secret scan findings: " + " | ".join(findings[:20]))


run("git", "fetch", "--no-tags", "origin", f"+refs/heads/{BRANCH}:refs/remotes/origin/{BRANCH}", "+refs/heads/main:refs/remotes/origin/main", cwd=repo)
actual_head = out("git", "rev-parse", f"refs/remotes/origin/{BRANCH}", cwd=repo)
if actual_head != EXPECTED_HEAD:
    raise RuntimeError(f"PR head drift: expected {EXPECTED_HEAD}, observed {actual_head}")
actual_tree = out("git", "rev-parse", f"{EXPECTED_HEAD}^{{tree}}", cwd=repo)
if actual_tree != EXPECTED_TREE:
    raise RuntimeError(f"PR tree drift: expected {EXPECTED_TREE}, observed {actual_tree}")

payload_path = repo / PAYLOAD_REL
encoded = "".join(payload_path.read_text(encoding="utf-8").split())
compressed = base64.b64decode(encoded, validate=True)
if hashlib.sha256(compressed).hexdigest() != EXPECTED_GZIP_SHA:
    raise RuntimeError("compressed patch payload SHA drift")
patch_bytes = gzip.decompress(compressed)
if hashlib.sha256(patch_bytes).hexdigest() != EXPECTED_PATCH_SHA:
    raise RuntimeError("decompressed patch SHA drift")
patch_file.write_bytes(patch_bytes)
patch_paths = []
for line in patch_bytes.decode("utf-8").splitlines():
    if line.startswith("diff --git a/"):
        patch_paths.append(line.split(" b/", 1)[1])
if tuple(patch_paths) != EXPECTED_PATHS:
    raise RuntimeError(f"patch path inventory drift: {patch_paths!r}")
if any(path.startswith(".github/workflows/") for path in patch_paths):
    raise RuntimeError("patch unexpectedly changes workflows")
if any("runtime_patch_v59" in path for path in patch_paths):
    raise RuntimeError("patch unexpectedly introduces v59+")

if worktree.exists():
    shutil.rmtree(worktree, ignore_errors=True)
run("git", "worktree", "add", "--detach", str(worktree), EXPECTED_HEAD, cwd=repo)
try:
    if out("git", "rev-parse", "HEAD", cwd=worktree) != EXPECTED_HEAD:
        raise RuntimeError("wrong isolated HEAD")
    if out("git", "rev-parse", "HEAD^{tree}", cwd=worktree) != EXPECTED_TREE:
        raise RuntimeError("wrong isolated tree")
    if out("git", "status", "--porcelain", cwd=worktree):
        raise RuntimeError("isolated parent worktree dirty before patch")

    run("git", "apply", "--check", str(patch_file), cwd=worktree)
    run("git", "apply", str(patch_file), cwd=worktree)
    changed = tuple(line.strip()[3:] for line in out("git", "status", "--porcelain", cwd=worktree).splitlines() if line.strip())
    if set(changed) != set(EXPECTED_PATHS) or len(changed) != len(EXPECTED_PATHS):
        raise RuntimeError(f"patched worktree path drift: {changed!r}")
    run("git", "diff", "--check", cwd=worktree)

    scripts = worktree / ".github/dcoir_review/scripts"
    os.environ["PYTHONPATH"] = str(scripts) + (os.pathsep + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else "")
    changed_python = [p for p in EXPECTED_PATHS if p.endswith(".py") and (worktree / p).is_file()]
    run(sys.executable, "-m", "py_compile", *changed_python, cwd=worktree)

    commands = parse_validation_commands(worktree / ".github/dcoir_review/openrouter-pr-review-pareto.yml")
    if len(commands) != 60:
        raise RuntimeError(f"expected 60 governed validation commands, observed {len(commands)}")

    git_exe = shutil.which("git")
    if not git_exe:
        raise RuntimeError("git executable not found")
    git_root = Path(git_exe).resolve().parent.parent
    git_bash = git_root / "bin" / "bash.exe"
    if not git_bash.is_file():
        raise RuntimeError(f"Git-for-Windows bash not found: {git_bash}")

    parser_text = ""
    for index, command in enumerate(commands, 1):
        argv = shlex.split(command, posix=True)
        print(f"=== Registry {index:02d}/60 {command} ===")
        if argv[0] in {"python", "python3"}:
            argv[0] = sys.executable
            run(*argv, cwd=worktree)
        elif argv[0] == "bash":
            argv[0] = str(git_bash)
            run(*argv, cwd=worktree)
        elif argv[0] == "pwsh":
            cp = native_powershell(worktree)
            parser_text = cp.stdout + cp.stderr
        else:
            run(*argv, cwd=worktree)

    if "Validating 293 PowerShell file(s)." not in parser_text:
        raise RuntimeError("Windows parser did not validate 293 files")
    if "ASSEMBLED_HARNESS_SHA256=7a7bf1b5a842c29a42ede8851cf090ab8019adf74fc2ae7a8bd305839a682d76" not in parser_text:
        raise RuntimeError("assembled harness SHA mismatch")

    independent_secret_scan(worktree)

    recall = run(sys.executable, ".github/dcoir_review/scripts/dcoir_review_semantic_recall_corpus_selftest.py", cwd=worktree)
    if "12 cases, 10 finding classes, 2 clean classes" not in recall.stdout + recall.stderr:
        raise RuntimeError("semantic recall summary drift")
    precision_cp = run(sys.executable, ".github/dcoir_review/scripts/dcoir_review_precision_regression_selftest.py", cwd=worktree)
    precision = json.loads(precision_cp.stdout)
    if float(precision["false_positive_suppression_rate"]) != 1.0 or float(precision["true_positive_retention_rate"]) != 1.0:
        raise RuntimeError("precision rate drift")
    if precision.get("regressions"):
        raise RuntimeError(f"precision regressions: {precision['regressions']}")

    inventory = json.loads(run(sys.executable, ".github/dcoir_review/scripts/dcoir_review_architecture_inventory.py", cwd=worktree).stdout)
    if inventory.get("missing_modules"):
        raise RuntimeError(f"missing modules: {inventory['missing_modules']}")
    if int(inventory["production_patch_count"]) != 56 or int(inventory["max_numbered_version"]) != 57:
        raise RuntimeError("architecture inventory count/version drift")

    orchestration = scripts / "dcoir_review/review_orchestration.py"
    if not orchestration.is_file() or orchestration.stat().st_size > 15000:
        raise RuntimeError("canonical review_orchestration.py missing or oversized")
    orchestration_text = orchestration.read_text(encoding="utf-8")
    for label in EXPECTED_STAGE_ORDER:
        if f'"{label}"' not in orchestration_text:
            raise RuntimeError(f"orchestration stage marker missing: {label}")

    participant_paths = (
        "dcoir_review/quality_gate.py",
        "dcoir_review/review_scope_guard_hooks.py",
        "dcoir_review/semantic_adjudication_confidence.py",
        "dcoir_review/semantic_result_reuse.py",
        "dcoir_review/semantic_review_ledger_hooks.py",
        "dcoir_review/structured_result_disposition.py",
        "dcoir_review_required_runtime_patch_v32.py",
        "dcoir_review_required_runtime_patch_v35.py",
        "dcoir_review_required_runtime_patch_v44.py",
        "dcoir_review_required_runtime_patch_v46.py",
    )
    for rel in participant_paths:
        text = (scripts / rel).read_text(encoding="utf-8")
        if "def openrouter_review_with_hybrid_first_pass(" in text:
            raise RuntimeError(f"historical hybrid function definition remains in {rel}")
        if "original_hybrid_first_pass" in text:
            raise RuntimeError(f"historical hybrid storage remains in {rel}")

    sys.path.insert(0, str(scripts))
    entrypoint_module = importlib.import_module("dcoir_review.entrypoint")
    review = importlib.import_module("openrouter_pr_review_pareto_context")
    entrypoint = entrypoint_module.DcoirReviewEntrypoint()
    entrypoint.apply_runtime_patches(review)
    final_hybrid = review.openrouter_review_with_hybrid_first_pass
    if final_hybrid.__module__ != "dcoir_review.review_orchestration":
        raise RuntimeError(f"final hybrid owner drift: {final_hybrid.__module__}")
    if tuple(getattr(review, "DCOIR_REVIEW_ORCHESTRATION_STAGE_ORDER", ())) != EXPECTED_STAGE_ORDER:
        raise RuntimeError("runtime orchestration stage-order drift")
    stored = sorted(name for name, value in vars(review).items() if "original_hybrid_first_pass" in name and callable(value))
    if stored:
        raise RuntimeError(f"stored-original hybrid callables remain: {stored}")

    status_paths = tuple(line.strip()[3:] for line in out("git", "status", "--porcelain", cwd=worktree).splitlines() if line.strip())
    if set(status_paths) != set(EXPECTED_PATHS) or len(status_paths) != len(EXPECTED_PATHS):
        raise RuntimeError(f"validation mutated patched worktree: {status_paths!r}")

    summary.write_text("\n".join([
        "result=PASS",
        f"parent_head={EXPECTED_HEAD}",
        f"parent_tree={EXPECTED_TREE}",
        f"patch_sha256={EXPECTED_PATCH_SHA}",
        f"patch_path_count={len(EXPECTED_PATHS)}",
        "registry_commands=60",
        "production_components=56",
        "max_numbered_version=57",
        "missing_modules=0",
        "canonical_hybrid_owner=dcoir_review.review_orchestration",
        "orchestration_stage_count=10",
        "stored_original_hybrid_callables=0",
        "independent_secret_scan=pass",
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
    ]) + "\n", encoding="utf-8")
    print(summary.read_text(encoding="utf-8"), end="")
    print(TERMINAL)
finally:
    run("git", "worktree", "remove", "--force", str(worktree), cwd=repo, check=False)
    shutil.rmtree(worktree, ignore_errors=True)
