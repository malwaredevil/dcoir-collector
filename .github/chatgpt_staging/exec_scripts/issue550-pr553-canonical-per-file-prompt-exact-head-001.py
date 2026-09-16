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

EXPECTED_HEAD = "155237587cd8998d8ff5da8fad3daa2d7885e474"
EXPECTED_TREE = "f3aa2c3e46c5a87e34ce666145bdcb8f1256b778"
BRANCH = "refactor/issue-550-dcoir-runtime-consolidation"
REQUEST_ID = "issue550-pr553-canonical-per-file-prompt-exact-head-001"
TERMINAL = "ISSUE550_PR553_CANONICAL_PER_FILE_PROMPT_EXACT_HEAD_001_PASS"
EXPECTED_PARENT = "1275b8e7338bdf5f9677d1d0e0ab3a0ba8dbbb57"
EXPECTED_COMMIT_PATCH_SHA = "7694a4ba7a6457b10f88ad13227a688c92ca7ba60c7eba42c660ef6f2ab70502"

repo = Path(os.environ.get("DCOIR_REPO_ROOT") or os.environ.get("GITHUB_WORKSPACE") or ".").resolve()
downloads = Path(os.environ.get("DCOIR_DOWNLOADS_DIR") or os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()).resolve()
worktree = downloads / f"{REQUEST_ID}-worktree"
commit_patch = downloads / f"{REQUEST_ID}-commit.patch"
summary = downloads / f"{REQUEST_ID}-summary.txt"

for key in (
    "OPENROUTER_API_KEY", "GITHUB_TOKEN", "GH_TOKEN", "DCOIR_GITHUB_FG_TOKEN",
    "DCOIR_GITHUB_CL_TOKEN", "DCOIR_GEMINI_API", "DCOIR_OPENAI_API_KEY",
    "DCOIR_OPENAI_PROJECT_ID", "OPENAI_API_KEY",
):
    os.environ.pop(key, None)
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["CODEX_BASE_REF"] = EXPECTED_PARENT
os.environ["GITHUB_REPOSITORY"] = "malwaredevil/dcoir-collector"


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

if out("git", "rev-parse", f"{EXPECTED_HEAD}^", cwd=repo) != EXPECTED_PARENT:
    raise RuntimeError("PR parent drift")

if worktree.exists():
    shutil.rmtree(worktree, ignore_errors=True)
run("git", "worktree", "add", "--detach", str(worktree), EXPECTED_HEAD, cwd=repo)
try:
    if out("git", "rev-parse", "HEAD", cwd=worktree) != EXPECTED_HEAD:
        raise RuntimeError("detached exact-head worktree drift")
    run("git", "diff", "--check", EXPECTED_PARENT, EXPECTED_HEAD, cwd=worktree)
    changed = tuple(filter(None, out("git", "diff", "--name-only", EXPECTED_PARENT, EXPECTED_HEAD, cwd=worktree).splitlines()))
    expected_paths = (
        ".github/dcoir_review/ARCHITECTURE.md",
        ".github/dcoir_review/scripts/dcoir_review/adversarial_prompt_policy.py",
        ".github/dcoir_review/scripts/dcoir_review/pareto_context/part_05_ranking_per_file_review.py",
        ".github/dcoir_review/scripts/dcoir_review/semantic_evidence_hardening.py",
        ".github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v32.py",
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

    import copy
    sys.path.insert(0, str(scripts))
    from dcoir_review.entrypoint import DcoirReviewEntrypoint
    from dcoir_review import adversarial_prompt_policy as prompt_policy
    import dcoir_review_required_runtime_patch_v32 as v32

    entrypoint = DcoirReviewEntrypoint()
    module = entrypoint.import_module(entrypoint.review_module_name)
    config_path = worktree / ".github/dcoir_review/openrouter-pr-review-pareto.yml"
    base_config = module.load_pareto_context_config(str(config_path))
    canonical = module.build_per_file_review_prompt
    if v32.ADVERSARIAL_SEMANTIC_BLOCK != prompt_policy.ADVERSARIAL_SEMANTIC_BLOCK:
        raise RuntimeError("v32 adversarial prompt alias drift")
    if v32.INDEPENDENT_CONFIRMATION_BLOCK != prompt_policy.INDEPENDENT_CONFIRMATION_BLOCK:
        raise RuntimeError("v32 independent confirmation alias drift")

    pr = {"number": 553, "title": "Prompt ownership characterization"}
    item = {
        "filename": "probe.py",
        "patch": "@@ -0,0 +1,4 @@\n+value = 1\n+if value:\n+    run()\n+print(value)",
    }
    file_text = ("value = 1\nif value:\n    run()\nprint(value)\n" * 120)
    diff = "diff --git a/probe.py b/probe.py\n" + item["patch"] + "\n"
    initial_cfg = copy.copy(base_config)
    initial_cfg.max_prompt_chars = 120000
    initial_cfg.per_file_review_max_file_chars = min(
        getattr(initial_cfg, "per_file_review_max_file_chars", 12000), 8000
    )
    initial_prompt = canonical(pr, item, file_text, diff, initial_cfg, [], "deep-forced")
    if "Adversarial semantic falsification requirements:" not in initial_prompt:
        raise RuntimeError("canonical per-file prompt is missing adversarial policy before patches")
    if "Predicate and call-site audit requirements:" not in initial_prompt:
        raise RuntimeError("canonical per-file prompt is missing predicate audit before patches")

    owners = {"review": module, "base": module.base, "hardened": module.hardened}
    previous = {
        (label, name): value
        for label, owner in owners.items()
        for name, value in vars(owner).items()
        if callable(value)
    }
    history: dict[tuple[str, str], list[str]] = {}
    replacements: list[str] = []
    groups = (
        "patch_module_names", "terminal_patch_module_names", "post_terminal_patch_module_names",
        "candidate_integrity_patch_module_names", "stage_local_patch_module_names",
        "execution_policy_patch_module_names", "telemetry_patch_module_names", "post_telemetry_patch_module_names",
    )
    for group_name in groups:
        for patch_name in getattr(entrypoint, group_name):
            before_prompt = module.build_per_file_review_prompt
            before_blocks = (v32.ADVERSARIAL_SEMANTIC_BLOCK, v32.INDEPENDENT_CONFIRMATION_BLOCK)
            entrypoint._apply_patch_modules(module, (patch_name,))
            after_prompt = module.build_per_file_review_prompt
            if after_prompt is not before_prompt:
                replacements.append(patch_name)
            if patch_name == "dcoir_review_required_runtime_patch_v32" and after_prompt is not before_prompt:
                raise RuntimeError("v32 still replaces per-file prompt")
            if patch_name == "dcoir_review.semantic_evidence_hardening":
                if after_prompt is not before_prompt:
                    raise RuntimeError("semantic evidence still replaces per-file prompt")
                if before_blocks != (v32.ADVERSARIAL_SEMANTIC_BLOCK, v32.INDEPENDENT_CONFIRMATION_BLOCK):
                    raise RuntimeError("semantic evidence still mutates v32 prompt globals")
            for label, owner in owners.items():
                for name, value in vars(owner).items():
                    key = (label, name)
                    if callable(value) and key in previous and previous[key] is not value:
                        history.setdefault(key, []).append(patch_name)
                    if callable(value):
                        previous[key] = value

    if replacements != ["dcoir_review_required_runtime_patch_v46"]:
        raise RuntimeError(f"per-file prompt replacement drift: {replacements}")
    final_prompt = module.build_per_file_review_prompt
    if final_prompt.__module__ != "dcoir_review_required_runtime_patch_v46":
        raise RuntimeError(f"final per-file prompt owner drift: {final_prompt.__module__}")
    multi_stage = {key: stages for key, stages in history.items() if len(stages) >= 2}
    if len(multi_stage) != 21:
        raise RuntimeError(f"multi-stage chain count drift: {len(multi_stage)}")
    stored = {
        label: [name for name, value in vars(owner).items() if name.startswith("_dcoir_") and callable(value)]
        for label, owner in owners.items()
    }
    if len(stored["base"]) != 0 or len(stored["review"]) != 46 or len(stored["hardened"]) != 54:
        raise RuntimeError(f"stored-original callable drift: { {k: len(v) for k, v in stored.items()} }")
    if callable(getattr(module, "_dcoir_review_v32_original_build_per_file_review_prompt", None)):
        raise RuntimeError("v32 per-file prompt stored-original shim remains")

    v32_source = (scripts / "dcoir_review_required_runtime_patch_v32.py").read_text(encoding="utf-8")
    if "def _patch_per_file_prompt(" in v32_source:
        raise RuntimeError("v32 per-file prompt wrapper remains in source")
    if "_dcoir_review_v32_original_build_per_file_review_prompt" in v32_source:
        raise RuntimeError("v32 prompt storage marker remains in source")
    evidence_source = (scripts / "dcoir_review/semantic_evidence_hardening.py").read_text(encoding="utf-8")
    if "def _patch_v32_prompt_blocks(" in evidence_source:
        raise RuntimeError("semantic-evidence v32 prompt mutation helper remains")
    if "v32.ADVERSARIAL_SEMANTIC_BLOCK =" in evidence_source or "v32.INDEPENDENT_CONFIRMATION_BLOCK =" in evidence_source:
        raise RuntimeError("semantic-evidence still mutates v32 prompt globals")
    policy_path = scripts / "dcoir_review/adversarial_prompt_policy.py"
    policy_bytes = len(policy_path.read_bytes().replace(b"\r\n", b"\n"))
    if policy_bytes > 15000:
        raise RuntimeError(f"prompt policy source too large: {policy_bytes}")

    expected_prompts = {
        120000: (9982, "bea52cf9b6a89a9e4ab20872611aaecac1d423343199d61adc6cf57281a796e9"),
        9000: (9000, "376d2ee2f9827b714b489d0f80076f26287533186a86d6c46a9667682ce426b7"),
        6000: (6000, "671b23ae5be6b6b225a6f0424193a411f1e885c3762c819204bee29fbce4df96"),
        4500: (4500, "4c9d1917d84a83b922ca7fec909a5dd695c5579e2e99e2f0c676a00128587187"),
        3000: (3000, "f421c37c439d4bd131729806ba74b089879e02fb2072ba73f77bf7e23d14f2e6"),
        1800: (1800, "7c8e71d758537c0a9dda33b1cb172c557afb1c305b606097f49145381ceeac20"),
        1000: (1000, "69454a4a028e760d41943c1afe99764f4207c38a791b5010a6d23339e7c4810c"),
        700: (700, "2db2747b2bfdd3378f2a108c96b5df17d3634a05923e2738707f45b45e0b5ae5"),
    }
    for limit, (expected_len, expected_sha) in expected_prompts.items():
        cfg = copy.copy(base_config)
        cfg.max_prompt_chars = limit
        cfg.per_file_review_max_file_chars = min(
            getattr(cfg, "per_file_review_max_file_chars", 12000), 8000
        )
        rendered = final_prompt(pr, item, file_text, diff, cfg, [], "deep-forced")
        actual_sha = hashlib.sha256(rendered.encode()).hexdigest()
        if len(rendered) != expected_len or actual_sha != expected_sha:
            raise RuntimeError(
                f"prompt parity drift at {limit}: len={len(rendered)} sha={actual_sha}"
            )

    final_bytes = subprocess.check_output(["git", "diff", "--binary", EXPECTED_PARENT, EXPECTED_HEAD], cwd=worktree)
    commit_patch.write_bytes(final_bytes)
    final_sha = hashlib.sha256(final_bytes).hexdigest()
    if final_sha != EXPECTED_COMMIT_PATCH_SHA:
        raise RuntimeError(f"commit patch SHA drift: {final_sha}")

    summary.write_text("\n".join([
        "result=PASS",
        f"exact_head={EXPECTED_HEAD}",
        f"exact_head_tree={EXPECTED_TREE}",
        f"exact_parent={EXPECTED_PARENT}",
        f"commit_patch_sha256={final_sha}",
        "slice_paths=6",
        "registry_commands=61",
        "production_components=55",
        "max_numbered_version=57",
        "missing_modules=0",
        "multi_stage_chains_before=22",
        "multi_stage_chains_after=21",
        "base_stored_original_callables=0",
        "review_stored_original_callables=46",
        "hardened_stored_original_callables=54",

        "canonical_adversarial_prompt_policy=dcoir_review.adversarial_prompt_policy",
        "final_per_file_prompt_owner=dcoir_review_required_runtime_patch_v46",
        "per_file_prompt_runtime_replacements=1",
        "stored_original_per_file_prompt_callables=0",
        "per_file_prompt_parity_cases=8",
        f"prompt_policy_source_bytes={policy_bytes}",
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
