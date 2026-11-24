from __future__ import annotations

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

EXPECTED_HEAD = "f4a6236d1ab6a9c13693fd07a4e702a92d523d77"
EXPECTED_TREE = "fc59254aab2ae29f0abc16d1795782e1824d5d94"
EXPECTED_PARENT = "e0021f4126308a12545a417170d5e773bf3b88f9"
BRANCH = "refactor/issue-550-dcoir-runtime-consolidation"
REQUEST_ID = "issue550-pr553-finding-comment-render-exact-head-validation-001"
TERMINAL = "ISSUE550_PR553_FINDING_COMMENT_RENDER_EXACT_HEAD_VALIDATION_001_PASS"
FORMER_RENDERER_OWNERS = (
    "dcoir_review/patches/dcoir_review_runtime_patches/part_02.py",
    "dcoir_review/patches/dcoir_review_strict_runtime_patches/part_02a.py",
    "dcoir_review/patches/dcoir_review_required_runtime_patches/part_02a.py",
    "dcoir_review/patches/dcoir_review_required_runtime_patch_v2/part_02.py",
    "dcoir_review/patches/dcoir_review_required_runtime_patch_v3/part_02.py",
    "dcoir_review/patches/dcoir_review_required_runtime_patch_v4_apply/part_01.py",
    "dcoir_review/patches/dcoir_review_required_runtime_patch_v5_apply/part_01.py",
    "dcoir_review/patches/dcoir_review_required_runtime_patch_v8/part_01a.py",
    "dcoir_review_required_runtime_patch_v9_prompting.py",
    "dcoir_review/patches/dcoir_review_required_runtime_patch_v13/part_02a.py",
    "dcoir_review/patches/dcoir_review_required_runtime_patch_v16/part_02.py",
    "dcoir_review_required_runtime_patch_v20.py",
    "dcoir_review/verified_finding_render.py",
    "dcoir_review/repair_pipeline.py",
    "dcoir_review_required_runtime_patch_v30.py",
)

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


def run(*args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    cp = subprocess.run(args, cwd=cwd, text=True, capture_output=True)
    print(cp.stdout, end="")
    print(cp.stderr, end="", file=sys.stderr)
    if check and cp.returncode:
        raise RuntimeError(f"command failed {cp.returncode}: {args}")
    return cp


def out(*args: str, cwd: Path | None = None) -> str:
    return run(*args, cwd=cwd).stdout.strip()


def commands(path: Path) -> list[str]:
    result: list[str] = []
    active = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw == "validation_commands:":
            active = True
            continue
        if active:
            if raw.startswith("  - "):
                result.append(raw[4:].strip())
                continue
            if raw and not raw.startswith(" ") and not raw.startswith("#"):
                break
    return result


def native_ps(root: Path) -> str:
    powershell = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    if not powershell.is_file():
        raise RuntimeError(f"native PS5.1 missing: {powershell}")
    command = (
        "$ErrorActionPreference='Stop'; "
        "function Get-FileHash { [CmdletBinding()] param([Parameter(Mandatory=$true)][string]$LiteralPath,[ValidateSet('SHA256')][string]$Algorithm='SHA256'); "
        "$stream=[System.IO.File]::OpenRead($LiteralPath); $sha=[System.Security.Cryptography.SHA256]::Create(); try { "
        "$hash=([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-',''); "
        "[pscustomobject]@{Algorithm='SHA256';Hash=$hash;Path=[System.IO.Path]::GetFullPath($LiteralPath)} } finally { $sha.Dispose(); $stream.Dispose() } }; "
        "& '.github/dcoir_review/scripts/validate-windows-powershell-51.ps1' -AllowEmpty"
    )
    cp = run(str(powershell), "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command, cwd=root)
    return cp.stdout + cp.stderr


def secret_scan(root: Path, paths: list[str]) -> None:
    patterns = (
        re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
        re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"-----BEGIN (?:RSA|OPENSSH|EC|DSA) PRIVATE KEY-----"),
        re.compile(r"(?i)(?:api[_-]?key|secret|token|password)\s*[:=]\s*[\"']?[A-Za-z0-9_./+=-]{16,}"),
    )
    required = re.compile(r"REQUIRED_TOKEN\s*=\s*['\"]APPLY_[A-Z0-9_]+['\"]")
    symbol = re.compile(r"['\"]?[A-Z][A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|KEY)[A-Z0-9_]*['\"]?")
    hits: list[str] = []
    for rel in paths:
        path = root / rel
        if not path.is_file():
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if any(pattern.search(line) for pattern in patterns) and not required.search(line) and not symbol.search(line):
                hits.append(f"{rel}:{lineno}:{line[:220]}")
    if hits:
        raise RuntimeError("independent secret scan findings: " + " | ".join(hits[:20]))


run("git", "fetch", "--no-tags", "origin", f"+refs/heads/{BRANCH}:refs/remotes/origin/{BRANCH}", cwd=repo)
if out("git", "rev-parse", f"refs/remotes/origin/{BRANCH}", cwd=repo) != EXPECTED_HEAD:
    raise RuntimeError("exact-head branch drift")
if out("git", "rev-parse", f"{EXPECTED_HEAD}^{{tree}}", cwd=repo) != EXPECTED_TREE:
    raise RuntimeError("exact-head tree drift")
if out("git", "rev-parse", f"{EXPECTED_HEAD}^", cwd=repo) != EXPECTED_PARENT:
    raise RuntimeError("exact-head parent drift")

if worktree.exists():
    shutil.rmtree(worktree, ignore_errors=True)
run("git", "worktree", "add", "--detach", str(worktree), EXPECTED_HEAD, cwd=repo)
try:
    if out("git", "status", "--porcelain", cwd=worktree):
        raise RuntimeError("exact-head worktree dirty")
    changed = [path for path in out("git", "diff", "--name-only", f"{EXPECTED_PARENT}..{EXPECTED_HEAD}", cwd=worktree).splitlines() if path]
    if len(changed) != 28:
        raise RuntimeError(f"expected 28 renderer slice paths, observed {len(changed)}")
    if any(path.startswith(".github/workflows/") for path in changed):
        raise RuntimeError("unexpected workflow change")
    if any("runtime_patch_v59" in path for path in changed):
        raise RuntimeError("unexpected v59+")
    secret_scan(worktree, changed)

    scripts = worktree / ".github/dcoir_review/scripts"
    os.environ["PYTHONPATH"] = str(scripts) + (os.pathsep + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else "")
    cmdlist = commands(worktree / ".github/dcoir_review/openrouter-pr-review-pareto.yml")
    if len(cmdlist) != 61:
        raise RuntimeError(f"governed command count drift: {len(cmdlist)}")
    git_exe = shutil.which("git")
    if not git_exe:
        raise RuntimeError("git missing")
    gitbash = Path(git_exe).resolve().parent.parent / "bin/bash.exe"
    if not gitbash.is_file():
        raise RuntimeError(f"Git Bash missing: {gitbash}")
    parser = ""
    for index, command in enumerate(cmdlist, 1):
        argv = shlex.split(command, posix=True)
        print(f"=== Registry {index:02d}/61 {command} ===")
        if argv[0] in {"python", "python3"}:
            argv[0] = sys.executable
            run(*argv, cwd=worktree)
        elif argv[0] == "bash":
            argv[0] = str(gitbash)
            run(*argv, cwd=worktree)
        elif argv[0] == "pwsh":
            parser = native_ps(worktree)
        else:
            run(*argv, cwd=worktree)
    if "Validating 293 PowerShell file(s)." not in parser:
        raise RuntimeError("PS5.1 file count drift")
    if "ASSEMBLED_HARNESS_SHA256=7a7bf1b5a842c29a42ede8851cf090ab8019adf74fc2ae7a8bd305839a682d76" not in parser:
        raise RuntimeError("PS harness SHA drift")

    recall = run(sys.executable, ".github/dcoir_review/scripts/dcoir_review_semantic_recall_corpus_selftest.py", cwd=worktree)
    if "12 cases, 10 finding classes, 2 clean classes" not in recall.stdout + recall.stderr:
        raise RuntimeError("recall summary drift")
    precision = json.loads(run(sys.executable, ".github/dcoir_review/scripts/dcoir_review_precision_regression_selftest.py", cwd=worktree).stdout)
    if float(precision["false_positive_suppression_rate"]) != 1.0 or float(precision["true_positive_retention_rate"]) != 1.0 or precision.get("regressions"):
        raise RuntimeError("precision drift")
    inventory = json.loads(run(sys.executable, ".github/dcoir_review/scripts/dcoir_review_architecture_inventory.py", cwd=worktree).stdout)
    if inventory.get("missing_modules") or int(inventory["production_patch_count"]) != 56 or int(inventory["max_numbered_version"]) != 57:
        raise RuntimeError("inventory drift")

    canonical = scripts / "dcoir_review/finding_comment_render.py"
    if not canonical.is_file() or canonical.stat().st_size > 15000:
        raise RuntimeError("canonical renderer missing or oversized")
    for rel in FORMER_RENDERER_OWNERS:
        text = (scripts / rel).read_text(encoding="utf-8")
        if re.search(r"\bbuild_inline_comment\s*=", text):
            raise RuntimeError(f"historical renderer installation remains in {rel}")
        if "original_build_inline_comment" in text:
            raise RuntimeError(f"historical renderer storage remains in {rel}")

    parity = run(sys.executable, ".github/dcoir_review/scripts/dcoir_review_finding_comment_render_selftest.py", cwd=worktree)
    if "dcoir_review_finding_comment_render_selftest passed" not in parity.stdout + parity.stderr:
        raise RuntimeError("renderer parity summary missing")

    sys.path.insert(0, str(scripts))
    entrypoint = importlib.import_module("dcoir_review.entrypoint").DcoirReviewEntrypoint()
    review = importlib.import_module("openrouter_pr_review_pareto_context")
    entrypoint.apply_runtime_patches(review)
    renderer = review.base.build_inline_comment
    if renderer.__module__ != "dcoir_review.finding_comment_render":
        raise RuntimeError(f"renderer owner drift: {renderer.__module__}")
    stored = sorted(name for name, value in vars(review.base).items() if "original_build_inline_comment" in name and callable(value))
    if stored:
        raise RuntimeError(f"stored original renderer callables remain: {stored}")
    before = review.base.build_inline_comment
    renderer_module = importlib.import_module("dcoir_review.finding_comment_render")
    renderer_module.apply_pareto_context_module(review)
    if review.base.build_inline_comment is not before:
        raise RuntimeError("canonical renderer is not idempotent")
    if out("git", "status", "--porcelain", cwd=worktree):
        raise RuntimeError("validation mutated source")

    summary.write_text("\n".join([
        "result=PASS",
        f"exact_head={EXPECTED_HEAD}",
        f"exact_tree={EXPECTED_TREE}",
        f"parent={EXPECTED_PARENT}",
        "slice_paths=28",
        "registry_commands=61",
        "production_components=56",
        "max_numbered_version=57",
        "missing_modules=0",
        "canonical_renderer_owner=dcoir_review.finding_comment_render",
        "former_renderer_installations=0",
        "stored_original_renderer_callables=0",
        "renderer_parity_selftest=pass",
        "canonical_renderer_idempotent=true",
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
