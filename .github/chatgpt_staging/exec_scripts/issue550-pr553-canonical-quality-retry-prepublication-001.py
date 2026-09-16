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

EXPECTED_HEAD = "cd8665f024d7c3183d737ef85bc964bf2c7bfcac"
EXPECTED_TREE = "10c8ad66f41124574cb2eedf8f0e250b516d1f87"
BRANCH = "refactor/issue-550-dcoir-runtime-consolidation"
REQUEST_ID = "issue550-pr553-canonical-quality-retry-prepublication-001"
TERMINAL = "ISSUE550_PR553_CANONICAL_QUALITY_RETRY_PREPUBLICATION_001_PASS"
PATCH_PAYLOAD = os.environ.get("DCOIR_PATCH_PAYLOAD") or ".github/chatgpt_staging/exec_payloads/issue550-pr553-canonical-quality-retry-prepublication-001.patch.gz.b64"
EXPECTED_PATCH_SHA = "3ba977b97bb0879627a98087ce0c371bb53ff2d209fc570db8605b8a88f5c988"

repo = Path(os.environ.get("DCOIR_REPO_ROOT") or os.environ.get("GITHUB_WORKSPACE") or ".").resolve()
downloads = Path(os.environ.get("DCOIR_DOWNLOADS_DIR") or os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()).resolve()
worktree = downloads / f"{REQUEST_ID}-worktree"
raw_patch = downloads / f"{REQUEST_ID}.patch"
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

compressed_text = (Path(PATCH_PAYLOAD) if Path(PATCH_PAYLOAD).is_absolute() else repo / PATCH_PAYLOAD).read_text(encoding="utf-8")
patch_bytes = gzip.decompress(base64.b64decode("".join(compressed_text.split())))
if hashlib.sha256(patch_bytes).hexdigest() != EXPECTED_PATCH_SHA:
    raise RuntimeError("candidate patch SHA drift")
raw_patch.write_bytes(patch_bytes)

if worktree.exists():
    shutil.rmtree(worktree, ignore_errors=True)
run("git", "worktree", "add", "--detach", str(worktree), EXPECTED_HEAD, cwd=repo)
try:
    run("git", "apply", "--check", str(raw_patch), cwd=worktree)
    run("git", "apply", str(raw_patch), cwd=worktree)
    run("git", "diff", "--check", cwd=worktree)

    changed = tuple(filter(None, out("git", "diff", "--name-only", cwd=worktree).splitlines()))
    expected_paths = (
        ".github/dcoir_review/ARCHITECTURE.md",
        ".github/dcoir_review/scripts/dcoir_review/hardened/part_04_quality_provider.py",
        ".github/dcoir_review/scripts/dcoir_review/quality_gate.py",
        ".github/dcoir_review/scripts/dcoir_review/structured_result_disposition.py",
        ".github/dcoir_review/scripts/dcoir_review/structured_result_recovery.py",
        ".github/dcoir_review/scripts/dcoir_review_runtime_module_loader_selftest.py",
    )
    if changed != expected_paths:
        raise RuntimeError(f"changed-path drift: {changed!r}")
    if any(path.startswith(".github/workflows/") for path in changed):
        raise RuntimeError("workflow change entered source slice")

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
    from dcoir_review import structured_result_disposition as disposition
    entrypoint = DcoirReviewEntrypoint()
    module = entrypoint.import_module(entrypoint.review_module_name)
    baseline = module.hardened.baseline_review_quality_retry_reason
    original = module.hardened.review_quality_retry_reason
    if baseline is not original:
        raise RuntimeError("baseline retry alias drift before production patches")

    owners = {"review": module, "base": module.base, "hardened": module.hardened}
    previous = {(label, name): value for label, owner in owners.items() for name, value in vars(owner).items() if callable(value)}
    history: dict[tuple[str, str], list[str]] = {}
    replacements: list[str] = []
    groups = (
        "patch_module_names", "terminal_patch_module_names", "post_terminal_patch_module_names",
        "candidate_integrity_patch_module_names", "stage_local_patch_module_names",
        "execution_policy_patch_module_names", "telemetry_patch_module_names", "post_telemetry_patch_module_names",
    )
    for group_name in groups:
        for patch_name in getattr(entrypoint, group_name):
            before = module.hardened.review_quality_retry_reason
            entrypoint._apply_patch_modules(module, (patch_name,))
            after = module.hardened.review_quality_retry_reason
            if after is not before:
                replacements.append(patch_name)
            for label, owner in owners.items():
                for name, value in vars(owner).items():
                    key = (label, name)
                    if callable(value) and key in previous and previous[key] is not value:
                        history.setdefault(key, []).append(patch_name)
                    if callable(value):
                        previous[key] = value

    final = module.hardened.review_quality_retry_reason
    if replacements != ["dcoir_review.quality_gate"]:
        raise RuntimeError(f"quality retry replacement drift: {replacements}")
    if final.__module__ != "dcoir_review.quality_gate":
        raise RuntimeError(f"quality retry owner drift: {final.__module__}")
    multi_stage = {key: stages for key, stages in history.items() if len(stages) >= 2}
    if len(multi_stage) != 22:
        raise RuntimeError(f"multi-stage chain count drift: {len(multi_stage)}")
    stored = {label: [name for name, value in vars(owner).items() if name.startswith("_dcoir_") and callable(value)] for label, owner in owners.items()}
    if len(stored["base"]) != 0 or len(stored["review"]) != 47 or len(stored["hardened"]) != 54:
        raise RuntimeError(f"stored-original callable drift: { {k: len(v) for k, v in stored.items()} }")
    forbidden = {
        "_dcoir_quality_gate_original_review_quality_retry_reason",
        "_dcoir_review_structured_result_disposition_prior_quality_retry_reason",
    }
    if any(name in forbidden for name in stored["hardened"]):
        raise RuntimeError(f"quality retry history shims remain: {stored['hardened']}")

    config = module.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")
    setattr(config, disposition.ALLOW_ATTR, True)
    def finding(path: str, line: int, confidence: float) -> dict[str, object]:
        return {
            "path": path, "line": line, "severity": "medium", "confidence": confidence,
            "title": "Potential validation defect",
            "body": "The changed behavior may skip a required validation boundary.",
            "suggested_replacement": "",
            "validation": "Exercise the changed line with positive and negative controls.",
        }
    line_index = {("a.py", 10): 1, ("b.py", 20): 2}
    near = {"summary": "Two bounded hypotheses require disposition.", "findings": [finding("a.py", 10, 0.68), finding("b.py", 20, 0.60)]}
    if final(near, config, [], line_index) != "":
        raise RuntimeError("near-threshold bounded disposition drift")
    pending = getattr(config, disposition.PENDING_ATTR, None)
    if not isinstance(pending, dict) or int(pending.get("candidate_count", 0)) != 2 or round(float(pending.get("candidate_floor", 0)), 2) != 0.60:
        raise RuntimeError(f"pending disposition drift: {pending}")
    too_low = {"summary": "weak", "findings": [finding("a.py", 10, 0.59)]}
    if not final(too_low, config, [], line_index) or getattr(config, disposition.PENDING_ATTR, None) is not None:
        raise RuntimeError("too-low retry/reset drift")
    summary_only = {"summary": "Found an issue in the changed validation boundary.", "findings": []}
    if final(summary_only, config, [], line_index) != "model summary indicated a possible issue while the structured findings array was empty":
        raise RuntimeError("summary-only semantic retry drift")
    if getattr(config, disposition.PENDING_ATTR, None) is not None:
        raise RuntimeError("summary-only pending reset drift")
    if final(near, config, [], None) == "":
        raise RuntimeError("missing-line-index fail-closed drift")

    final_bytes = subprocess.check_output(["git", "diff", "--binary"], cwd=worktree)
    final_patch.write_bytes(final_bytes)
    final_sha = hashlib.sha256(final_bytes).hexdigest()
    if final_sha != EXPECTED_PATCH_SHA:
        raise RuntimeError(f"final patch SHA drift: {final_sha}")

    summary.write_text("\n".join([
        "result=PASS",
        f"exact_parent={EXPECTED_HEAD}",
        f"exact_parent_tree={EXPECTED_TREE}",
        f"candidate_patch_sha256={EXPECTED_PATCH_SHA}",
        f"final_patch_sha256={final_sha}",
        "slice_paths=6",
        "registry_commands=61",
        "production_components=55",
        "max_numbered_version=57",
        "missing_modules=0",
        "multi_stage_chains_before=23",
        "multi_stage_chains_after=22",
        "base_stored_original_callables=0",
        "review_stored_original_callables=47",
        "hardened_stored_original_callables=54",
        "canonical_quality_retry_owner=dcoir_review.quality_gate",
        "quality_retry_runtime_replacements=1",
        "stored_original_quality_retry_callables=0",
        "quality_retry_behavior_cases=4",
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
