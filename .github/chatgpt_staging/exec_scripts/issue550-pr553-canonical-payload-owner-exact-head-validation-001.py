from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

EXPECTED_HEAD = "c3f718ae226158b9fad09f2b8693740b7d47de4c"
EXPECTED_TREE = "e2e65d5326c38b57d13d94d5da91dcdf5fd6435c"
EXPECTED_PARENT = "f4a6236d1ab6a9c13693fd07a4e702a92d523d77"
BRANCH = "refactor/issue-550-dcoir-runtime-consolidation"
REQUEST_ID = "issue550-pr553-canonical-payload-owner-exact-head-validation-001"
TERMINAL = "ISSUE550_PR553_CANONICAL_PAYLOAD_OWNER_EXACT_HEAD_VALIDATION_001_PASS"
EXPECTED_PATHS = (
    ".github/dcoir_review/ARCHITECTURE.md",
    ".github/dcoir_review/scripts/dcoir_review/per_file_routing.py",
    ".github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v32.py",
    ".github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v32_selftest.py",
    ".github/dcoir_review/scripts/dcoir_review_runtime_module_loader_selftest.py",
)
EXPECTED_BLOBS = {
    ".github/dcoir_review/ARCHITECTURE.md": "e8355f1b67ac23fde3c34189145e6c7d635e200c",
    ".github/dcoir_review/scripts/dcoir_review/per_file_routing.py": "cb43ca6900085d7f097b62c00dd2e59d311004bf",
    ".github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v32.py": "6f22c63986269396a8872916341b4f54693a4c96",
    ".github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v32_selftest.py": "c464e67511a6611dddc91b5e52fd86c509679c66",
    ".github/dcoir_review/scripts/dcoir_review_runtime_module_loader_selftest.py": "43e97ae676229ad769a8bc28437a89713cca883e",
}

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
os.environ["CODEX_BASE_REF"] = EXPECTED_PARENT


def run(*args: str, cwd: Path | None = None, check: bool = True, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    cp = subprocess.run(args, cwd=cwd, text=True, capture_output=True, env=env)
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


def native_powershell(root: Path) -> str:
    powershell = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    if not powershell.is_file():
        raise RuntimeError(f"native Windows PowerShell missing: {powershell}")
    ps_command = (
        "$ErrorActionPreference='Stop'; "
        "function Get-FileHash { [CmdletBinding()] param([Parameter(Mandatory=$true)][string]$LiteralPath,[ValidateSet('SHA256')][string]$Algorithm='SHA256'); "
        "$stream=[System.IO.File]::OpenRead($LiteralPath); $sha=[System.Security.Cryptography.SHA256]::Create(); try { "
        "$hash=([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-',''); "
        "[pscustomobject]@{Algorithm='SHA256';Hash=$hash;Path=[System.IO.Path]::GetFullPath($LiteralPath)} } finally { $sha.Dispose(); $stream.Dispose() } }; "
        "& '.github/dcoir_review/scripts/validate-windows-powershell-51.ps1' -AllowEmpty"
    )
    cp = run(str(powershell), "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_command, cwd=root)
    return cp.stdout + cp.stderr


def independent_secret_scan(root: Path) -> None:
    patterns = (
        re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
        re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"-----BEGIN (?:RSA|OPENSSH|EC|DSA) PRIVATE KEY-----"),
        re.compile(r"(?i)(?:api[_-]?key|secret|token|password)\s*[:=]\s*[\"']?[A-Za-z0-9_./+=-]{16,}"),
    )
    required = re.compile(r"REQUIRED_TOKEN\s*=\s*['\"]APPLY_[A-Z0-9_]+['\"]")
    symbol = re.compile(r"['\"]?[A-Z][A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|KEY)[A-Z0-9_]*['\"]?")
    findings: list[str] = []
    for rel in EXPECTED_PATHS:
        path = root / rel
        for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if any(pattern.search(line) for pattern in patterns) and not required.search(line) and not symbol.search(line):
                findings.append(f"{rel}:{lineno}:{line[:220]}")
    if findings:
        raise RuntimeError("independent secret scan findings: " + " | ".join(findings[:20]))


run("git", "fetch", "--no-tags", "origin", f"+refs/heads/{BRANCH}:refs/remotes/origin/{BRANCH}", cwd=repo)
actual_head = out("git", "rev-parse", f"refs/remotes/origin/{BRANCH}", cwd=repo)
if actual_head != EXPECTED_HEAD:
    raise RuntimeError(f"PR head drift: expected {EXPECTED_HEAD}, observed {actual_head}")
if out("git", "rev-parse", f"{EXPECTED_HEAD}^{{tree}}", cwd=repo) != EXPECTED_TREE:
    raise RuntimeError("exact-head tree drift")
if out("git", "rev-parse", f"{EXPECTED_HEAD}^", cwd=repo) != EXPECTED_PARENT:
    raise RuntimeError("exact-head parent drift")

changed = tuple(filter(None, out("git", "diff", "--name-only", EXPECTED_PARENT, EXPECTED_HEAD, cwd=repo).splitlines()))
if changed != EXPECTED_PATHS:
    raise RuntimeError(f"exact-head changed-path drift: {changed!r}")
if any(path.startswith(".github/workflows/") for path in changed):
    raise RuntimeError("exact-head commit unexpectedly changes workflows")
if any(re.search(r"runtime_patch_v(?:59|[6-9][0-9])", path) for path in changed):
    raise RuntimeError("exact-head commit unexpectedly introduces v59+")
for path, expected_blob in EXPECTED_BLOBS.items():
    actual_blob = out("git", "rev-parse", f"{EXPECTED_HEAD}:{path}", cwd=repo)
    if actual_blob != expected_blob:
        raise RuntimeError(f"blob drift for {path}: {actual_blob}")

if worktree.exists():
    shutil.rmtree(worktree, ignore_errors=True)
run("git", "worktree", "add", "--detach", str(worktree), EXPECTED_HEAD, cwd=repo)
try:
    if out("git", "rev-parse", "HEAD", cwd=worktree) != EXPECTED_HEAD:
        raise RuntimeError("isolated worktree head drift")
    if out("git", "rev-parse", "HEAD^{tree}", cwd=worktree) != EXPECTED_TREE:
        raise RuntimeError("isolated worktree tree drift")
    if run("git", "status", "--porcelain", cwd=worktree).stdout:
        raise RuntimeError("isolated exact-head worktree is dirty")

    run("git", "diff", "--check", EXPECTED_PARENT, EXPECTED_HEAD, cwd=worktree)
    scripts = worktree / ".github/dcoir_review/scripts"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(scripts) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    changed_python = [p for p in EXPECTED_PATHS if p.endswith(".py")]
    run(sys.executable, "-m", "py_compile", *changed_python, cwd=worktree, env=env)

    commands = parse_validation_commands(worktree / ".github/dcoir_review/openrouter-pr-review-pareto.yml")
    if len(commands) != 61:
        raise RuntimeError(f"expected 61 governed validation commands, observed {len(commands)}")
    git_exe = shutil.which("git")
    if not git_exe:
        raise RuntimeError("git executable missing")
    git_bash = Path(git_exe).resolve().parent.parent / "bin/bash.exe"
    if not git_bash.is_file():
        raise RuntimeError(f"Git-for-Windows bash missing: {git_bash}")

    parser_text = ""
    for index, command in enumerate(commands, 1):
        argv = shlex.split(command, posix=True)
        print(f"=== Registry {index:02d}/61 {command} ===")
        if argv[0] in {"python", "python3"}:
            argv[0] = sys.executable
            run(*argv, cwd=worktree, env=env)
        elif argv[0] == "bash":
            argv[0] = str(git_bash)
            run(*argv, cwd=worktree, env=env)
        elif argv[0] == "pwsh":
            parser_text = native_powershell(worktree)
        else:
            run(*argv, cwd=worktree, env=env)

    if "Validating 293 PowerShell file(s)." not in parser_text:
        raise RuntimeError("native PowerShell 5.1 file-count drift")
    if "ASSEMBLED_HARNESS_SHA256=7a7bf1b5a842c29a42ede8851cf090ab8019adf74fc2ae7a8bd305839a682d76" not in parser_text:
        raise RuntimeError("assembled PowerShell harness SHA drift")

    independent_secret_scan(worktree)

    recall = run(sys.executable, ".github/dcoir_review/scripts/dcoir_review_semantic_recall_corpus_selftest.py", cwd=worktree, env=env)
    if "12 cases, 10 finding classes, 2 clean classes" not in recall.stdout + recall.stderr:
        raise RuntimeError("semantic recall summary drift")
    precision = json.loads(run(sys.executable, ".github/dcoir_review/scripts/dcoir_review_precision_regression_selftest.py", cwd=worktree, env=env).stdout)
    if float(precision["false_positive_suppression_rate"]) != 1.0 or float(precision["true_positive_retention_rate"]) != 1.0 or precision.get("regressions"):
        raise RuntimeError("precision regression drift")
    inventory = json.loads(run(sys.executable, ".github/dcoir_review/scripts/dcoir_review_architecture_inventory.py", cwd=worktree, env=env).stdout)
    if inventory.get("missing_modules") or int(inventory["production_patch_count"]) != 56 or int(inventory["max_numbered_version"]) != 57:
        raise RuntimeError("architecture inventory drift")

    v32_source = (scripts / "dcoir_review_required_runtime_patch_v32.py").read_text(encoding="utf-8")
    routing_source = (scripts / "dcoir_review/per_file_routing.py").read_text(encoding="utf-8")
    if "hardened.build_openrouter_payload =" in v32_source or "module.build_openrouter_payload =" in v32_source:
        raise RuntimeError("v32 still installs runtime payload builder")
    if "_dcoir_review_v32_original_build_openrouter_payload" in v32_source:
        raise RuntimeError("v32 stored-original payload shim remains")
    if "def apply_reasoning_payload_policy(" not in v32_source:
        raise RuntimeError("v32 explicit reasoning policy missing")
    if routing_source.count("hardened.build_openrouter_payload = build_openrouter_payload") != 1:
        raise RuntimeError("per-file hardened payload owner assignment drift")
    if routing_source.count("module.build_openrouter_payload = build_openrouter_payload") != 1:
        raise RuntimeError("per-file module payload owner assignment drift")
    if "_dcoir_per_file_routing_original_build_openrouter_payload" in routing_source:
        raise RuntimeError("per-file stored-original payload shim remains")
    if "reasoning_policy.apply_reasoning_payload_policy" not in routing_source:
        raise RuntimeError("per-file routing no longer composes v32 reasoning policy")

    sys.path.insert(0, str(scripts))
    from dcoir_review.entrypoint import DcoirReviewEntrypoint
    from dcoir_review import per_file_routing
    entrypoint = DcoirReviewEntrypoint()
    module = entrypoint.import_module(entrypoint.review_module_name)
    entrypoint.apply_runtime_patches(module)
    canonical = module.hardened.build_openrouter_payload
    if canonical.__module__ != "dcoir_review.per_file_routing":
        raise RuntimeError(f"payload owner drift: {canonical.__module__}")
    if hasattr(module, "build_openrouter_payload") and module.build_openrouter_payload is not canonical:
        raise RuntimeError("module payload export does not share canonical owner")
    stored = sorted(
        name
        for owner in (module, module.hardened)
        for name, value in vars(owner).items()
        if "build_openrouter_payload" in name and name.startswith("_dcoir_") and callable(value)
    )
    if stored:
        raise RuntimeError(f"stored-original payload callables remain: {stored}")
    before = module.hardened.build_openrouter_payload
    per_file_routing.apply_pareto_context_module(module)
    if module.hardened.build_openrouter_payload is not before:
        raise RuntimeError("canonical payload owner is not idempotent")

    summary.write_text("\n".join([
        "result=PASS",
        f"exact_head={EXPECTED_HEAD}",
        f"exact_tree={EXPECTED_TREE}",
        f"exact_parent={EXPECTED_PARENT}",
        "slice_paths=5",
        "workflow_paths_changed=0",
        "v59_plus_added=false",
        "registry_commands=61",
        "production_components=56",
        "max_numbered_version=57",
        "missing_modules=0",
        "canonical_payload_owner=dcoir_review.per_file_routing",
        "stored_original_payload_callables=0",
        "canonical_payload_owner_idempotent=true",
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
