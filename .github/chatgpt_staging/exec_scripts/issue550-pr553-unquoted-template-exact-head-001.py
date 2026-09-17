from __future__ import annotations
import json, os, re, shlex, shutil, subprocess, sys, tempfile
from pathlib import Path

SOURCE_PARENT = "5d292fa9933960bbde0734503edfc6387986dca3"
EXPECTED_HEAD = "a031364c216e8899e4c7ab4717c478d0c63a3bd0"
REQUEST_ID = "issue550-pr553-unquoted-template-exact-head-001"
TERMINAL = "ISSUE550_PR553_UNQUOTED_TEMPLATE_EXACT_HEAD_001_PASS"
EXPECTED_PATHS = (
    ".github/dcoir_review/scripts/dcoir_review/base/part_03_redaction_shell.py",
    ".github/dcoir_review/scripts/dcoir_review/selftests/base_selftest/part_03.py",
)
repo = Path(os.environ.get("DCOIR_REPO_ROOT") or os.environ.get("GITHUB_WORKSPACE") or ".").resolve()
downloads = Path(os.environ.get("DCOIR_DOWNLOADS_DIR") or os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()).resolve()
worktree = downloads / f"{REQUEST_ID}-worktree"
summary_path = downloads / f"{REQUEST_ID}-summary.txt"
for key in ("OPENROUTER_API_KEY", "GITHUB_TOKEN", "GH_TOKEN", "DCOIR_GITHUB_FG_TOKEN", "DCOIR_GITHUB_CL_TOKEN", "DCOIR_GEMINI_API", "DCOIR_OPENAI_API_KEY", "DCOIR_OPENAI_PROJECT_ID", "OPENAI_API_KEY"):
    os.environ.pop(key, None)
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["CODEX_BASE_REF"] = SOURCE_PARENT
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
    commands, active = [], False
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
    bootstrap = downloads / "dcoir_native_ps5_validation_bootstrap.ps1"
    validator = (root / ".github/dcoir_review/scripts/validate-windows-powershell-51.ps1").resolve()
    bootstrap.write_text(r'''param([Parameter(Mandatory=$true)][string]$ValidatorPath)
$ErrorActionPreference = 'Stop'
$forceFallback = $env:DCOIR_FORCE_FILEHASH_FALLBACK -eq '1'
if ($forceFallback -or -not (Get-Command Get-FileHash -ErrorAction SilentlyContinue)) {
    function Get-FileHash {
        param([Parameter(Mandatory=$true)][string]$LiteralPath,[string]$Algorithm = 'SHA256')
        if ($Algorithm -ne 'SHA256') { throw "Fallback Get-FileHash supports only SHA256, got $Algorithm" }
        $resolved = (Resolve-Path -LiteralPath $LiteralPath).Path
        $stream = [System.IO.File]::OpenRead($resolved)
        $sha = [System.Security.Cryptography.SHA256]::Create()
        try {
            $bytes = $sha.ComputeHash($stream)
            $hash = (($bytes | ForEach-Object { $_.ToString('x2') }) -join '')
            [pscustomobject]@{ Algorithm = 'SHA256'; Hash = $hash; Path = $resolved }
        }
        finally { $sha.Dispose(); $stream.Dispose() }
    }
}
& $ValidatorPath -AllowEmpty
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
''', encoding="utf-8")
    cp = run(str(powershell), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(bootstrap), "-ValidatorPath", str(validator), cwd=root)
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

run("git", "fetch", "--no-tags", "origin", "+refs/heads/refactor/issue-550-dcoir-runtime-consolidation:refs/remotes/origin/refactor/issue-550-dcoir-runtime-consolidation", cwd=repo)
for sha in (SOURCE_PARENT, EXPECTED_HEAD):
    run("git", "cat-file", "-e", f"{sha}^{{commit}}", cwd=repo)
remote_head = out("git", "rev-parse", "refs/remotes/origin/refactor/issue-550-dcoir-runtime-consolidation", cwd=repo)
if remote_head != EXPECTED_HEAD:
    raise RuntimeError(f"source branch head drift: expected {EXPECTED_HEAD}, got {remote_head}")
if worktree.exists():
    shutil.rmtree(worktree, ignore_errors=True)
run("git", "worktree", "add", "--detach", str(worktree), EXPECTED_HEAD, cwd=repo)
try:
    if out("git", "rev-parse", "HEAD", cwd=worktree) != EXPECTED_HEAD:
        raise RuntimeError("detached head drift")
    if out("git", "rev-parse", "HEAD^", cwd=worktree) != SOURCE_PARENT:
        raise RuntimeError("parent drift")
    run("git", "diff", "--check", SOURCE_PARENT, EXPECTED_HEAD, "--", cwd=worktree)
    changed = tuple(filter(None, out("git", "diff", "--name-only", SOURCE_PARENT, EXPECTED_HEAD, "--", cwd=worktree).splitlines()))
    if changed != EXPECTED_PATHS:
        raise RuntimeError(f"changed-path drift: {changed!r}")
    if any(p.startswith(".github/workflows/") or p.startswith(".github/chatgpt_staging/") for p in changed):
        raise RuntimeError("forbidden workflow/staging path entered source slice")
    if any(re.search(r"dcoir_review_required_runtime_patch_v(?:5[9-9]|[6-9][0-9])", p) for p in changed):
        raise RuntimeError("v59+ production patch entered source slice")

    scripts = worktree / ".github/dcoir_review/scripts"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(scripts) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    changed_python = [p for p in changed if p.endswith(".py") and (worktree / p).is_file()]
    if len(changed_python) != 2:
        raise RuntimeError(f"changed Python count drift: {len(changed_python)}")
    run(sys.executable, "-m", "py_compile", *changed_python, cwd=worktree, env=env)
    for path in (
        ".github/dcoir_review/scripts/openrouter_pr_review_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_status_comment_selftest.py",
        ".github/dcoir_review/scripts/dcoir_review_runtime_module_loader_selftest.py",
    ):
        run(sys.executable, path, cwd=worktree, env=env)

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
    if "PowerShell version: 5.1." not in parser_text or "Validating 293 PowerShell file(s)." not in parser_text:
        raise RuntimeError("native PowerShell validation drift")
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
    if inventory.get("missing_modules") or int(inventory["production_patch_count"]) != 56 or int(inventory["max_numbered_version"]) != 56:
        raise RuntimeError(f"architecture inventory drift: {inventory}")

    sys.path.insert(0, str(scripts))
    from dcoir_review.entrypoint import DcoirReviewEntrypoint
    entrypoint = DcoirReviewEntrypoint()
    module = entrypoint.import_module(entrypoint.review_module_name)
    owners = {"review": module, "base": module.base, "hardened": module.hardened}
    previous = {(label, name): value for label, owner in owners.items() for name, value in vars(owner).items() if callable(value)}
    history: dict[tuple[str, str], list[str]] = {}
    review_replacements: list[str] = []
    groups = (
        "patch_module_names", "terminal_patch_module_names", "post_terminal_patch_module_names",
        "candidate_integrity_patch_module_names", "stage_local_patch_module_names",
        "execution_policy_patch_module_names", "telemetry_patch_module_names", "post_telemetry_patch_module_names",
    )
    for group_name in groups:
        for patch_name in getattr(entrypoint, group_name):
            before_review = module.hardened.openrouter_review
            entrypoint._apply_patch_modules(module, (patch_name,))
            after_review = module.hardened.openrouter_review
            if after_review is not before_review:
                review_replacements.append(patch_name)
            for label, owner in owners.items():
                for name, value in vars(owner).items():
                    key = (label, name)
                    if callable(value) and key in previous and previous[key] is not value:
                        history.setdefault(key, []).append(patch_name)
                    if callable(value):
                        previous[key] = value
    final_review = module.hardened.openrouter_review
    if final_review.__module__ != "dcoir_review.provider_review":
        raise RuntimeError(f"provider-review owner drift: {final_review.__module__}")
    if review_replacements != ["dcoir_review.provider_review"]:
        raise RuntimeError(f"provider-review replacement drift: {review_replacements}")
    if callable(getattr(module, "openrouter_review", None)):
        raise RuntimeError("unexpected module.openrouter_review alias")
    for storage in (
        "_dcoir_review_structured_result_provider_prior_openrouter_review",
        "_dcoir_review_v54_original_openrouter_review",
        "_dcoir_review_v57_original_openrouter_review",
    ):
        if callable(getattr(module.hardened, storage, None)):
            raise RuntimeError(f"historical review storage remains: {storage}")
    multi_stage = {key: stages for key, stages in history.items() if len(stages) >= 2}
    if len(multi_stage) != 19:
        raise RuntimeError(f"multi-stage chain count drift: {len(multi_stage)}")
    for retired in (scripts / "dcoir_review_required_runtime_patch_v54.py", scripts / "dcoir_review_required_runtime_patch_v57.py"):
        if retired.exists():
            raise RuntimeError(f"retired source reappeared: {retired.name}")

    summary_path.write_text("\n".join([
        "result=PASS",
        f"source_parent={SOURCE_PARENT}",
        f"exact_head={EXPECTED_HEAD}",
        f"exact_tree={out('git', 'rev-parse', 'HEAD^{tree}', cwd=worktree)}",
        "slice_paths=2",
        "changed_python=2",
        "registry_commands=61",
        "production_components=56",
        "max_numbered_version=56",
        "missing_modules=0",
        "multi_stage_chains=19",
        "provider_review_runtime_replacements=1",
        "canonical_provider_review_owner=dcoir_review.provider_review",
        "stored_original_provider_review_callables=0",
        "retired_v54_v57_sources=true",
        "unquoted_template_redaction_followup=true",
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
    print(summary_path.read_text(encoding="utf-8"), end="")
    print(TERMINAL)
finally:
    run("git", "worktree", "remove", "--force", str(worktree), cwd=repo, check=False)
    shutil.rmtree(worktree, ignore_errors=True)
