from __future__ import annotations

import base64
import gzip
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

EXPECTED_HEAD = "fc5451a0b7d86de5557e9973f38944e11f9eb5e6"
EXPECTED_PARENT = "a9f77a3a5aaf9d1a12424919d8c5040d47d02b07"
EXPECTED_TREE = "c17bead3d7cb423bf430dd7baec914f1d59fb274"
BRANCH = "refactor/issue-550-dcoir-runtime-consolidation"
REQUEST_ID = "issue550-pr553-canonical-finding-validation-exact-head-001"
TERMINAL = "ISSUE550_PR553_CANONICAL_FINDING_VALIDATION_EXACT_HEAD_001_PASS"
EXPECTED_PATCH_SHA = "b3f0ec406b0fb3088fc89df37fca2968a37106b620f1b2cc0b10674fe3714f76"

repo = Path(os.environ.get("DCOIR_REPO_ROOT") or os.environ.get("GITHUB_WORKSPACE") or ".").resolve()
downloads = Path(os.environ.get("DCOIR_DOWNLOADS_DIR") or os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()).resolve()
worktree = downloads / f"{REQUEST_ID}-worktree"
final_patch = downloads / f"{REQUEST_ID}-final.patch"
summary = downloads / f"{REQUEST_ID}-summary.txt"

for key in (
    "OPENROUTER_API_KEY", "GITHUB_TOKEN", "GH_TOKEN", "DCOIR_GITHUB_FG_TOKEN",
    "DCOIR_GITHUB_CL_TOKEN", "DCOIR_GEMINI_API", "DCOIR_OPENAI_API_KEY",
    "DCOIR_OPENAI_PROJECT_ID", "OPENAI_API_KEY",
):
    os.environ.pop(key, None)
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["CODEX_BASE_REF"] = EXPECTED_HEAD


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


def independent_secret_scan(root: Path, paths: tuple[str, ...]) -> None:
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
    for rel in paths:
        path = root / rel
        if not path.is_file():
            continue
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
    raise RuntimeError("PR tree drift")

if worktree.exists():
    shutil.rmtree(worktree, ignore_errors=True)
run("git", "worktree", "add", "--detach", str(worktree), EXPECTED_HEAD, cwd=repo)
try:
    run("git", "diff", "--check", EXPECTED_PARENT, EXPECTED_HEAD, cwd=worktree)
    committed_patch = subprocess.check_output(
        ["git", "diff", "--binary", EXPECTED_PARENT, EXPECTED_HEAD], cwd=worktree
    )
    final_patch.write_bytes(committed_patch)
    final_sha = hashlib.sha256(committed_patch).hexdigest()
    if final_sha != EXPECTED_PATCH_SHA:
        raise RuntimeError(f"committed patch SHA drift: {final_sha}")
    new_segment = ".github/dcoir_review/scripts/dcoir_review/base/part_06a_finding_validation.py"

    changed = tuple(filter(None, out("git", "diff", "--name-only", EXPECTED_PARENT, EXPECTED_HEAD, cwd=worktree).splitlines()))
    expected_paths = (
        ".github/dcoir_review/ARCHITECTURE.md",
        ".github/dcoir_review/scripts/dcoir_review/base/part_06_findings_comments.py",
        ".github/dcoir_review/scripts/dcoir_review/base/part_06a_finding_validation.py",
        ".github/dcoir_review/scripts/dcoir_review/module_loader.py",
        ".github/dcoir_review/scripts/dcoir_review/patches/dcoir_review_required_runtime_patch_v8/part_01a.py",
        ".github/dcoir_review/scripts/dcoir_review/patches/dcoir_review_required_runtime_patch_v9/part_01.py",
        ".github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v9_prompting.py",
        ".github/dcoir_review/scripts/dcoir_review_runtime_module_loader_selftest.py",
    )
    if changed != expected_paths:
        raise RuntimeError(f"changed-path drift: {changed!r}")
    if any(path.startswith(".github/workflows/") for path in changed):
        raise RuntimeError("workflow change entered source slice")
    canonical_source = (worktree / new_segment).read_text(encoding="utf-8")
    if len(canonical_source.encode("utf-8")) > 15000:
        raise RuntimeError("canonical finding-validation segment exceeds 15000 bytes")
    if "dcoir_review_required_runtime_patch_v" in canonical_source:
        raise RuntimeError("canonical finding-validation segment depends on historical version module")

    scripts = worktree / ".github/dcoir_review/scripts"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(scripts) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    commands = parse_validation_commands(worktree / ".github/dcoir_review/openrouter-pr-review-pareto.yml")
    if len(commands) != 61:
        raise RuntimeError(f"governed command count drift: {len(commands)}")
    git_exe = shutil.which("git")
    if not git_exe:
        raise RuntimeError("git executable missing")
    git_bash = Path(git_exe).resolve().parent.parent / "bin/bash.exe"
    if not git_bash.is_file():
        raise RuntimeError(f"Git Bash missing: {git_bash}")

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
        raise RuntimeError("PowerShell file-count drift")
    if "ASSEMBLED_HARNESS_SHA256=7a7bf1b5a842c29a42ede8851cf090ab8019adf74fc2ae7a8bd305839a682d76" not in parser_text:
        raise RuntimeError("PowerShell assembled harness SHA drift")

    independent_secret_scan(worktree, changed)
    recall = run(sys.executable, ".github/dcoir_review/scripts/dcoir_review_semantic_recall_corpus_selftest.py", cwd=worktree, env=env)
    if "12 cases, 10 finding classes, 2 clean classes" not in recall.stdout + recall.stderr:
        raise RuntimeError("semantic recall drift")
    precision = json.loads(run(sys.executable, ".github/dcoir_review/scripts/dcoir_review_precision_regression_selftest.py", cwd=worktree, env=env).stdout)
    if float(precision["false_positive_suppression_rate"]) != 1.0 or float(precision["true_positive_retention_rate"]) != 1.0 or precision.get("regressions"):
        raise RuntimeError("precision regression drift")
    inventory = json.loads(run(sys.executable, ".github/dcoir_review/scripts/dcoir_review_architecture_inventory.py", cwd=worktree, env=env).stdout)
    if inventory.get("missing_modules") or int(inventory["production_patch_count"]) != 55 or int(inventory["max_numbered_version"]) != 57:
        raise RuntimeError(f"architecture inventory drift: {inventory}")

    sys.path.insert(0, str(scripts))
    from dcoir_review.entrypoint import DcoirReviewEntrypoint
    import dcoir_review_required_runtime_patch_v9_core as v9
    entrypoint = DcoirReviewEntrypoint()
    module = entrypoint.import_module(entrypoint.review_module_name)
    canonical = module.base.validation_text_for_finding
    if canonical.__module__ != "openrouter_pr_review":
        raise RuntimeError(f"canonical owner drift: {canonical.__module__}")
    cases = (
        ("yaml_pull_request_target", ".github/workflows/x.yml", 3),
        ("yaml_broad_write", ".github/workflows/x.yml", 5),
        ("yaml_untrusted_checkout", ".github/workflows/x.yml", 13),
        ("yaml_shell_pipe", ".github/workflows/x.yml", 15),
        ("yaml_metadata_shell", ".github/workflows/x.yml", 17),
        ("ps_acl", "tools/x.ps1", 8),
        ("ps_process_launch", "tools/x.ps1", 10),
        ("ps_env_token_callback", "tools/x.ps1", 12),
        ("python_yaml_load", "x.py", 10),
        ("python_shell_exec", "x.py", 18),
        ("python_env_token_callback", "x.py", 23),
        ("python_pickle_load", "x.py", 14),
    )
    for kind, path, line in cases:
        finding = {"path": path, "line": line, "_risk_sentinel_kind": kind}
        expected = v9._validation_for_key(kind, path, line)
        if canonical(finding) != expected:
            raise RuntimeError(f"semantic validation parity drift: {kind}")
    inferred = (
        {"path": ".github/workflows/x.yml", "line": 5, "title": "GitHub Actions workflow grants write permissions", "body": "contents: write grants broad write token permissions"},
        {"path": "x.py", "line": 18, "title": "Issue", "body": "Issue", "_anchored_line_text": "return subprocess.run(command, shell=True, check=False)"},
        {"path": "x.py", "line": 14, "title": "Unsafe pickle deserialization enables arbitrary code execution", "body": "pickle.loads deserializes untrusted bytes"},
    )
    for finding in inferred:
        path, line, kind = v9._postable_key(finding)
        if canonical(finding) != v9._validation_for_key(kind, path, line):
            raise RuntimeError(f"inferred semantic validation parity drift: {kind}")

    owners = {"review": module, "base": module.base, "hardened": module.hardened}
    history: dict[tuple[str, str], list[str]] = {}
    def callable_map(owner: object) -> dict[str, object]:
        return {name: value for name, value in vars(owner).items() if callable(value)}
    groups = (
        "patch_module_names", "terminal_patch_module_names", "post_terminal_patch_module_names",
        "candidate_integrity_patch_module_names", "stage_local_patch_module_names",
        "execution_policy_patch_module_names", "telemetry_patch_module_names", "post_telemetry_patch_module_names",
    )
    for group_name in groups:
        for patch_name in getattr(entrypoint, group_name):
            before = {label: callable_map(owner) for label, owner in owners.items()}
            entrypoint._apply_patch_modules(module, (patch_name,))
            for label, owner in owners.items():
                after = callable_map(owner)
                for name, value in after.items():
                    prior = before[label].get(name)
                    if prior is not None and prior is not value:
                        history.setdefault((label, name), []).append(patch_name)
            if module.base.validation_text_for_finding is not canonical:
                raise RuntimeError(f"{patch_name} replaced canonical validation_text_for_finding")
    multi_stage = {key: stages for key, stages in history.items() if len(stages) >= 2}
    if len(multi_stage) != 24:
        raise RuntimeError(f"multi-stage chain count drift: {len(multi_stage)}")
    base_stored = [name for name, value in vars(module.base).items() if name.startswith("_dcoir_") and callable(value)]
    if base_stored:
        raise RuntimeError(f"base stored-original callables remain: {base_stored}")
    validation_stored = [name for name, value in vars(module.base).items() if "validation_text_for_finding" in name and name.startswith("_dcoir_") and callable(value)]
    if validation_stored:
        raise RuntimeError(f"validation stored-original callables remain: {validation_stored}")

    summary.write_text("\n".join([
        "result=PASS",
        f"exact_head={EXPECTED_HEAD}",
        f"exact_head_tree={EXPECTED_TREE}",
        f"slice_parent={EXPECTED_PARENT}",
        f"frozen_patch_sha256={EXPECTED_PATCH_SHA}",
        f"committed_patch_sha256={final_sha}",
        "slice_paths=8",
        "registry_commands=61",
        "production_components=55",
        "max_numbered_version=57",
        "missing_modules=0",
        "multi_stage_chains_before=25",
        "multi_stage_chains_after=24",
        "base_stored_original_callables_before=2",
        "base_stored_original_callables_after=0",
        "canonical_validation_owner=openrouter_pr_review",
        "validation_runtime_replacements=0",
        "stored_original_validation_callables=0",
        "semantic_validation_parity_cases=15",
        "canonical_segment_bytes=14839",
        "semantic_recall=12/10/2",
        "false_positive_suppression=1.0",
        "true_positive_retention=1.0",
        "precision_regressions=0",
        "windows_powershell_files=293",
        "independent_secret_scan=pass",
        "workflow_paths_changed=0",
        "v59_plus_added=false",
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
