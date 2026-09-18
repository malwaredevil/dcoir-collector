# Provider Review Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the chronology-dependent `hardened.openrouter_review` wrapper chain with one canonical provider-review owner while preserving structured-output recovery, request/run telemetry, final-adjudication publication-floor behavior, terminal low-confidence disposition, provider transport retry semantics, and exact failure behavior.

**Architecture:** `dcoir_review.provider_review` becomes the only production installer/final owner of `hardened.openrouter_review`. It explicitly composes `dcoir_review.final_adjudication_policy`, `dcoir_review.review_telemetry`, and `dcoir_review.structured_result_provider` around the pre-existing provider-review loop. Historical v54/v57 production modules and all three stored-original `openrouter_review` shims are retired.

**Tech Stack:** Python 3, DCOIR Review runtime modules/selftests, Git/GitHub, Git-for-Windows Bash, native Windows PowerShell 5.1, deterministic offline validation, GitHub Actions exact-head validation.

**Spec:** `docs/superpowers/specs/2026-09-17-provider-review-consolidation-design.md`

## Global Constraints

- Use only `C:\GitHub\dcoir-collector`; do not create another clone or worktree for implementation.
- At implementation start, record `SOURCE_PARENT` from `git rev-parse HEAD`. It must equal this plan’s final committed head. All source-candidate freeze/hash comparisons use `SOURCE_PARENT`, not the older credited source head `6390ab7c6b9993f8fd3b931613e90740d3cd6b15`.
- PR #553 remains Draft until separately authorized.
- Never invoke `/dcoir-review`, `/or-review`, or `/openrouter-review`; this PR changes DCOIR Review itself.
- Do not request GitHub Copilot review without explicit operator authorization.
- Do not merge without explicit operator authorization.
- Do not change workflow YAML or absorb #557 workflow/report lifecycle work.
- Do not introduce any v59+ production patch.
- Preserve model stacks, retry counts, provider routing, verifier authority, review-scope authority, return shapes, and exact provider exception semantics.
- Preserve persisted/externally meaningful telemetry/disposition literals even where they contain historical v54/v57 identifiers.
- Local validation precedes publication. Publish the implementation as one coherent validated source commit rather than speculative one-finding commits.
- Before crediting the slice, exact-head evidence must show one `hardened.openrouter_review` production owner, zero stored-original review shims, no production v54/v57 import, max numbered production version <=56, and multi-stage callable chains <=19 unless a stronger documented stable composition justifies otherwise.

## File Structure

**Create:**
- `.github/dcoir_review/scripts/dcoir_review/provider_review.py`
- `.github/dcoir_review/scripts/dcoir_review/review_telemetry.py`
- `.github/dcoir_review/scripts/dcoir_review/final_adjudication_policy.py`
- `.github/dcoir_review/scripts/dcoir_review_provider_review_selftest.py`
- `.github/dcoir_review/scripts/dcoir_review_review_telemetry_selftest.py`
- `.github/dcoir_review/scripts/dcoir_review_final_adjudication_policy_selftest.py`
- `.github/dcoir_review/scripts/dcoir_review_final_adjudication_policy_selftest_prompt.py`
- `.github/dcoir_review/scripts/dcoir_review_final_adjudication_policy_selftest_production.py`

**Modify:**
- `.github/dcoir_review/scripts/dcoir_review/entrypoint.py`
- `.github/dcoir_review/scripts/dcoir_review/review_config.py`
- `.github/dcoir_review/scripts/dcoir_review/progress_reporting.py`
- `.github/dcoir_review/scripts/dcoir_review/structured_result_provider.py`
- `.github/dcoir_review/scripts/dcoir_review_runtime_module_loader_selftest.py`
- `.github/dcoir_review/scripts/dcoir_review_provider_transport_retry_selftest.py`
- `.github/dcoir_review/ARCHITECTURE.md`

**Delete after parity is proven:**
- `.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v54.py`
- `.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v54_selftest.py`
- `.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v57.py`
- `.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v57_selftest.py`
- `.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v57_selftest_prompt.py`
- `.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v57_selftest_production.py`

---

### Task 1: Establish RED canonical ownership/order tests

**Files:** create `dcoir_review_provider_review_selftest.py`; modify `dcoir_review_runtime_module_loader_selftest.py`.

**Produces:** a stable test contract for one final provider-review owner, zero historical review storages, exact call order, and exact exception propagation.

- [ ] **Step 1: Capture the source-parent baseline before any source mutation**

```powershell
$sourceParent = (git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Unable to read source parent' }
if (git status --porcelain) { throw 'Working tree must be clean before implementation' }
Set-Content -LiteralPath .git\provider-review-source-parent.txt -Value $sourceParent -NoNewline -Encoding ascii
Write-Output "SOURCE_PARENT=$sourceParent"
```

Record this SHA in the active turnover and ircore. It is the only baseline used for candidate diff/hash continuity.

- [ ] **Step 2: Write the failing ownership/order selftest**

After normal production composition, require:

```python
review = importlib.import_module("openrouter_pr_review_pareto_context")
DcoirReviewEntrypoint().apply_runtime_patches(review)
owner = review.hardened.openrouter_review
assert owner.__module__ == "dcoir_review.provider_review"
assert getattr(owner, "_dcoir_review_provider_review_owner", False) is True
for storage in (
    "_dcoir_review_structured_result_provider_prior_openrouter_review",
    "_dcoir_review_v54_original_openrouter_review",
    "_dcoir_review_v57_original_openrouter_review",
):
    assert not hasattr(review.hardened, storage), storage
```

Use fake stable helpers plus a fake underlying provider to require success order:

```python
[
    "final-policy-project",
    "telemetry-prepare",
    "provider-call",
    "structured-recovery-report",
    "telemetry-finish-success",
]
```

and provider-failure order:

```python
[
    "final-policy-project",
    "telemetry-prepare",
    "provider-call",
    "telemetry-finish-failed",
]
```

The failure case must assert the exact exception object identity is preserved.

- [ ] **Step 3: Register future stable modules in runtime-loader ownership**

Add to `DIRECT_IMPORT_MODULES`:

```python
"final_adjudication_policy.py",
"provider_review.py",
"review_telemetry.py",
```

- [ ] **Step 4: Run RED**

```powershell
python .github/dcoir_review/scripts/dcoir_review_provider_review_selftest.py
if ($LASTEXITCODE -eq 0) { throw 'RED test unexpectedly passed before implementation' }
```

Record the expected missing-owner/storage failure. Do not publish an intermediate red-only source commit.

---

### Task 2: Extract v54 telemetry into `dcoir_review.review_telemetry`

**Files:** create `dcoir_review/review_telemetry.py` and `dcoir_review_review_telemetry_selftest.py`; modify `review_config.py` and `progress_reporting.py`.

**Produces these stable interfaces:** `ReviewTelemetryCall`, `ensure_sink(config) -> RunTelemetrySink`, `note_telemetry_error(config) -> None`, `prepare_review_call(prompt, schema, config) -> ReviewTelemetryCall | None`, `finish_review_call(state, outcome) -> None`, `summarize_sink(config) -> dict[str, Any]`, `compact_summary(summary, limit=1800) -> str`, and `emit_run_telemetry(module, reporter) -> None`.

- [ ] **Step 1: Move telemetry primitives while preserving compatibility literals**

Preserve exactly:

```python
SINK_ATTR = "_dcoir_v54_run_telemetry_sink"
SUMMARY_ATTR = "_dcoir_v54_run_telemetry_summary"
ERROR_COUNT_ATTR = "_dcoir_v54_telemetry_error_count"
STAGE_LABEL_ATTR = "_dcoir_v54_stage_label"
SCHEMA_VERSION = "dcoir_openrouter_run_telemetry_v1"
```

Move the current `RunTelemetrySink`, classification, normalization, drain/copy, summary, compact-summary, and terminal-emission logic without changing observable output.

- [ ] **Step 2: Add the stable call-state type and fail-soft preparation**

```python
@dataclass(frozen=True)
class ReviewTelemetryCall:
    root_config: Any
    staged_config: Any
    sink: RunTelemetrySink
    stage: str


def prepare_review_call(prompt: Any, schema: Any, config: Any) -> ReviewTelemetryCall | None:
    try:
        sink = ensure_sink(config)
        stage = classify_stage(prompt, schema, config)
        staged = copy.copy(config)
        setattr(staged, SINK_ATTR, sink)
        staged.openrouter_capture_request_telemetry = True
        staged._openrouter_request_telemetry_events = []
        staged._openrouter_request_attempt_telemetry_events = []
        staged._openrouter_request_telemetry_error_count = 0
        staged._openrouter_request_attempt_count = 0
        staged._openrouter_last_request_telemetry = {}
        return ReviewTelemetryCall(config, staged, sink, stage)
    except Exception:
        note_telemetry_error(config)
        return None
```

- [ ] **Step 3: Implement non-raising call completion**

`finish_review_call(state, outcome)` returns when `state is None`; otherwise it calls the migrated drain logic with `success` or `failed`, then copies stage-local telemetry back when `PER_FILE_PROJECTION_ATTR` is true on `root_config`. Every drain/copy failure is caught, increments telemetry error state when possible, and returns without raising.

- [ ] **Step 4: Switch canonical config initialization**

`review_config._initialize_run_telemetry_fail_soft()` imports `dcoir_review.review_telemetry`, calls `ensure_sink(config)`, and on failure calls `note_telemetry_error(config)` inside the existing fail-soft boundary.

- [ ] **Step 5: Switch terminal ProgressReporter telemetry**

`progress_reporting.py` imports the stable telemetry module. `complete()` and `fail()` call `telemetry.emit_run_telemetry(module, self)` inside the current whole-call `try/except`; remove dependence on v54’s applied marker.

- [ ] **Step 6: Migrate v54 behavior tests to stable ownership**

Create `dcoir_review_review_telemetry_selftest.py`. Preserve tests for capture-on/off compatibility, stage classification, retries/failures, prompt/secret exclusion, per-file copy-back, missing metadata, error counts, terminal emission, and drain/summary/terminal fail-soft behavior. Remove v54 patch-installation, `PATCH_ERRORS_ATTR`, `REVIEW_STORAGE`, and `_patch_openrouter_review` assertions.

- [ ] **Step 7: Run telemetry GREEN**

```powershell
python .github/dcoir_review/scripts/dcoir_review_review_telemetry_selftest.py
if ($LASTEXITCODE -ne 0) { throw "stable telemetry selftest failed: $LASTEXITCODE" }
```

---

### Task 3: Extract v57 final-adjudication policy

**Files:** create `final_adjudication_policy.py` plus the three stable final-policy selftest files.

**Produces:** `project_review_call(module, prompt, config) -> tuple[Any, Any]` and `apply_pareto_context_module(module) -> None`.

- [ ] **Step 1: Move terminal-disposition behavior**

Move v57 confidence/floor validation, candidate validation, final-v35 provenance checks, provider-envelope checks, terminal disposition, and disposition recording. Preserve:

```python
DISPOSITION_MARKER = "_dcoir_v57_terminal_low_confidence_disposition"
PROMPT_INJECTION_ATTR = "_dcoir_v57_publication_floor_injected"
PROMPT_ARTIFACT_PATH = "prompts/06-semantic-adjudication-prompt.txt"
CLEAN_SUMMARY = "No high confidence findings were found after semantic adjudication."
```

Preserve disposition payload `"version": "v57"` as compatibility data.

- [ ] **Step 2: Replace the v57 review wrapper with fail-soft pure projection**

```python
def project_review_call(module: Any, prompt: Any, config: Any) -> tuple[Any, Any]:
    try:
        injected = _inject_publication_floor(prompt, config)
    except Exception:
        return prompt, config
    if injected is prompt:
        return prompt, config
    try:
        staged = copy.copy(config)
        setattr(staged, review_telemetry.STAGE_LABEL_ATTR, "semantic-adjudicator")
        setattr(staged, PROMPT_INJECTION_ATTR, True)
    except Exception:
        return prompt, config
    try:
        module.hardened.write_debug_text_artifact_safely(config, PROMPT_ARTIFACT_PATH, injected)
    except Exception:
        pass
    return injected, staged
```

Add a deterministic regression that forces `_inject_publication_floor()` to raise and requires `(prompt, config)` object identity to be returned unchanged. This helper never calls or stores `openrouter_review`.

- [ ] **Step 3: Install only terminal split policy**

`apply_pareto_context_module(module)` is idempotent and wraps only `split_findings_with_review_body_fallback`: disposition -> record -> `([], [])`; otherwise call the captured pre-policy split callable. No `REVIEW_STORAGE` exists.

- [ ] **Step 4: Migrate v57 tests**

Use `from dcoir_review import final_adjudication_policy as final_policy` and `from dcoir_review import review_telemetry`. Prompt tests exercise `project_review_call()` directly. Replace historical storage assertions with split-policy idempotence and absence of `_dcoir_review_v57_original_openrouter_review`.

- [ ] **Step 5: Run final-policy GREEN**

```powershell
python .github/dcoir_review/scripts/dcoir_review_final_adjudication_policy_selftest.py
if ($LASTEXITCODE -ne 0) { throw "final adjudication policy selftest failed: $LASTEXITCODE" }
```

---

### Task 4: Split structured-result request recovery from review status reporting

**Files:** modify `dcoir_review/structured_result_provider.py` and focused tests.

**Produces:** `reset_review_recovery(config) -> None` and `report_review_recovery(config, reporter) -> None`.

- [ ] **Step 1: Remove review-wrapper storage**

Delete `_REVIEW_STORAGE`, current-review capture/storage, nested `openrouter_review`, and assignments to `hardened.openrouter_review`/`module.openrouter_review`. Keep request-boundary `openrouter_request_once` recovery unchanged.

- [ ] **Step 2: Add explicit status helpers**

```python
def reset_review_recovery(config: Any) -> None:
    setattr(config, RECOVERY_ATTR, "")


def report_review_recovery(config: Any, reporter: Any) -> None:
    if reporter is None:
        return
    mode = str(getattr(config, RECOVERY_ATTR, "") or "")
    try:
        if mode == "balanced-envelope":
            reporter.update(
                "structured-output-recovery",
                "mode=balanced-envelope; deterministic recovery avoided provider/model retry",
            )
        elif mode == "fenced-object":
            reporter.update(
                "structured-output-recovery",
                "mode=fenced-object; existing fenced-object recovery used",
            )
    except Exception:
        return
```

- [ ] **Step 3: Add direct/fenced/balanced/reporter-failure regressions**

A raising `reporter.update()` must not change provider results or exceptions.

- [ ] **Step 4: Run exact focused recovery tests**

```powershell
python .github/dcoir_review/scripts/dcoir_review_structured_result_recovery_selftest.py
if ($LASTEXITCODE -ne 0) { throw "structured-result recovery selftest failed: $LASTEXITCODE" }
python .github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v52_selftest.py
if ($LASTEXITCODE -ne 0) { throw "v52 compatibility selftest failed: $LASTEXITCODE" }
python .github/dcoir_review/scripts/dcoir_review_provider_review_selftest.py
```

The last command remains allowed to fail only for the known missing canonical provider owner until Task 5.

---

### Task 5: Implement canonical `dcoir_review.provider_review` and production order

**Files:** create `provider_review.py`; modify `entrypoint.py` and provider-transport selftest.

- [ ] **Step 1: Implement one explicit provider-review owner**

```python
APPLIED_MARKER = "_dcoir_review_provider_review_applied"
OWNER_MARKER = "_dcoir_review_provider_review_owner"


def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, APPLIED_MARKER, False):
        return
    hardened = module.hardened
    underlying = getattr(hardened, "openrouter_review", None)
    if not callable(underlying):
        raise RuntimeError("DCOIR provider review could not locate hardened openrouter_review")

    def openrouter_review(prompt, schema, config, reporter=None):
        projected_prompt, projected_config = final_adjudication_policy.project_review_call(
            module, prompt, config
        )
        state = review_telemetry.prepare_review_call(projected_prompt, schema, projected_config)
        active_config = state.staged_config if state is not None else projected_config
        structured_result_provider.reset_review_recovery(active_config)
        try:
            result = underlying(projected_prompt, schema, active_config, reporter)
        except Exception:
            review_telemetry.finish_review_call(state, "failed")
            raise
        structured_result_provider.report_review_recovery(active_config, reporter)
        review_telemetry.finish_review_call(state, "success")
        return result

    openrouter_review.__module__ = __name__
    setattr(openrouter_review, OWNER_MARKER, True)
    hardened.openrouter_review = openrouter_review
    setattr(module, APPLIED_MARKER, True)
```

Do not assign `module.openrouter_review`.

- [ ] **Step 2: Cut entrypoint over to stable owners**

Set `telemetry_patch_module_names = ()`. Keep `progress_reporting`, `provider_transport_retry`, `semantic_adjudication_recovery`, and v56 in their current relative order. End `post_telemetry_patch_module_names` with:

```python
"dcoir_review.final_adjudication_policy",
"dcoir_review.provider_review",
```

Remove `_emit_telemetry_patch_unavailable()` and its `finally` callback.

- [ ] **Step 3: Remove provider-transport selftest dependence on v54 storage**

Use `retry_loop = review.hardened.openrouter_review`. Where the test reads per-attempt telemetry from the caller config, set `PER_FILE_PROJECTION_ATTR = True` first so stable copy-back exposes the history without a historical storage hook.

- [ ] **Step 4: Run canonical-owner GREEN**

```powershell
$tests = @(
  '.github/dcoir_review/scripts/dcoir_review_provider_review_selftest.py',
  '.github/dcoir_review/scripts/dcoir_review_provider_transport_retry_selftest.py',
  '.github/dcoir_review/scripts/dcoir_review_review_telemetry_selftest.py',
  '.github/dcoir_review/scripts/dcoir_review_final_adjudication_policy_selftest.py'
)
foreach ($test in $tests) {
  python $test
  if ($LASTEXITCODE -ne 0) { throw "focused test failed: $test" }
}
```

---

### Task 6: Retire v54/v57 historical surfaces and update architecture docs/inventory

- [ ] **Step 1: Delete all six v54/v57 production/test files listed in File Structure**

Do not retain forwarding wrappers or aliases.

- [ ] **Step 2: Tighten runtime-loader/inventory assertions**

Keep `NUMBERED_PRODUCTION_PATCH_VERSION_CEILING = 58` as the global no-v59 guard. Require actual inventory max <=56, no v54/v57 production registration, and all three stable modules under `DIRECT_IMPORT_MODULES`.

- [ ] **Step 3: Update `ARCHITECTURE.md`**

Document:

```text
final-adjudication projection
-> telemetry preparation
-> structured-result recovery/base provider review
-> structured-recovery status
-> telemetry drain/copy
```

State that `provider_review`, `review_telemetry`, `final_adjudication_policy`, and `structured_result_provider` own the four stable responsibilities and that v54/v57 production sources are retired. Historical v54/v57 names may appear in this documentation only to explain retirement/compatibility history.

- [ ] **Step 4: Run a production-only stale-import/storage scan**

Create `.git\provider-review-production-scan.py`:

```python
from __future__ import annotations
import re
from pathlib import Path

root = Path.cwd()
scripts = root / ".github/dcoir_review/scripts"
historical_import = re.compile(r"dcoir_review_required_runtime_patch_v(?:54|57)")
storages = (
    "_dcoir_review_structured_result_provider_prior_openrouter_review",
    "_dcoir_review_v54_original_openrouter_review",
    "_dcoir_review_v57_original_openrouter_review",
)
findings: list[str] = []
for path in scripts.rglob("*.py"):
    rel = path.relative_to(root).as_posix()
    if "selftest" in path.name or "/selftests/" in f"/{rel}":
        continue
    text = path.read_text(encoding="utf-8", errors="replace")
    if historical_import.search(text):
        findings.append(f"historical-import:{rel}")
    for storage in storages:
        if storage in text:
            findings.append(f"stored-review:{rel}:{storage}")
if findings:
    raise RuntimeError("production chronology residue: " + " | ".join(findings))
print("PROVIDER_REVIEW_PRODUCTION_SCAN=PASS")
```

Run it and separately assert the deleted historical production files do not exist. New selftests are intentionally allowed to name retired storages when proving they are absent.

---

### Task 7: Validate locally, perform Prog/Adva, and freeze exact raw candidate bytes

- [ ] **Step 1: Run focused stable-contract tests**

```powershell
$tests = @(
  '.github/dcoir_review/scripts/dcoir_review_provider_review_selftest.py',
  '.github/dcoir_review/scripts/dcoir_review_review_telemetry_selftest.py',
  '.github/dcoir_review/scripts/dcoir_review_final_adjudication_policy_selftest.py',
  '.github/dcoir_review/scripts/dcoir_review_provider_transport_retry_selftest.py',
  '.github/dcoir_review/scripts/dcoir_review_structured_result_recovery_selftest.py',
  '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v52_selftest.py',
  '.github/dcoir_review/scripts/dcoir_review_runtime_module_loader_selftest.py'
)
foreach ($test in $tests) {
  python $test
  if ($LASTEXITCODE -ne 0) { throw "focused validation failed: $test" }
}
python .git\provider-review-production-scan.py
if ($LASTEXITCODE -ne 0) { throw "production chronology scan failed: $LASTEXITCODE" }
```

- [ ] **Step 2: Compile every changed Python file relative to `SOURCE_PARENT`**

```powershell
$sourceParent = (Get-Content -Raw .git\provider-review-source-parent.txt).Trim()
$changedPython = @(git diff --name-only $sourceParent -- '*.py' | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) })
if (-not $changedPython) { throw 'no changed Python files found' }
python -m py_compile $changedPython
if ($LASTEXITCODE -ne 0) { throw "py_compile failed: $LASTEXITCODE" }
```

- [ ] **Step 3: Run native Windows PowerShell 5.1 parser validation**

```powershell
$powershell = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
if (-not (Test-Path -LiteralPath $powershell)) { throw "native Windows PowerShell not found: $powershell" }
$psCommand = @'
$ErrorActionPreference='Stop';
function Get-FileHash {
  [CmdletBinding()]
  param([Parameter(Mandatory=$true)][string]$LiteralPath,[ValidateSet('SHA256')][string]$Algorithm='SHA256')
  $stream=[System.IO.File]::OpenRead($LiteralPath); $sha=[System.Security.Cryptography.SHA256]::Create()
  try {
    $hash=([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-','')
    [pscustomobject]@{Algorithm='SHA256';Hash=$hash;Path=[System.IO.Path]::GetFullPath($LiteralPath)}
  } finally { $sha.Dispose(); $stream.Dispose() }
}
& '.github/dcoir_review/scripts/validate-windows-powershell-51.ps1' -AllowEmpty
'@
& $powershell -NoProfile -ExecutionPolicy Bypass -Command $psCommand
if ($LASTEXITCODE -ne 0) { throw "Windows PowerShell parser validation failed: $LASTEXITCODE" }
```

Record the emitted PowerShell file count; compare to the prior 293-file baseline without silently redefining the baseline.

- [ ] **Step 4: Run the complete governed deterministic registry from current configuration**

Create `.git\run-provider-review-registry.py`:

```python
from __future__ import annotations
import json, os, shlex, shutil, subprocess, sys
from pathlib import Path

root = Path.cwd()
config = root / ".github/dcoir_review/openrouter-pr-review-pareto.yml"
commands: list[str] = []
active = False
for raw in config.read_text(encoding="utf-8").splitlines():
    if raw == "validation_commands:":
        active = True
        continue
    if active:
        if raw.startswith("  - "):
            commands.append(raw[4:].strip())
            continue
        if raw and not raw.startswith(" ") and not raw.startswith("#"):
            break
for key in (
    "OPENROUTER_API_KEY", "GITHUB_TOKEN", "GH_TOKEN", "DCOIR_GITHUB_FG_TOKEN",
    "DCOIR_GITHUB_CL_TOKEN", "DCOIR_GEMINI_API", "DCOIR_OPENAI_API_KEY",
    "DCOIR_OPENAI_PROJECT_ID", "OPENAI_API_KEY",
):
    os.environ.pop(key, None)
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

def run(argv: list[str]) -> None:
    print("RUN:", " ".join(argv))
    cp = subprocess.run(argv, cwd=root, text=True)
    if cp.returncode:
        raise SystemExit(cp.returncode)

for index, command in enumerate(commands, 1):
    argv = shlex.split(command, posix=True)
    if argv[0] in {"python", "python3"}:
        argv[0] = sys.executable
    print(f"=== YAML registry {index:02d}/{len(commands)} ===")
    run(argv)
git_exe = shutil.which("git")
if not git_exe:
    raise RuntimeError("git executable not found")
bash = Path(git_exe).resolve().parent.parent / "bin" / "bash.exe"
if not bash.is_file():
    raise RuntimeError(f"Git-for-Windows bash not found: {bash}")
run([str(bash), ".github/dcoir_review/scripts/validate-codex-local.sh"])
run([sys.executable, ".github/dcoir_review/scripts/validate-codeql-security-workflow.py"])
semantic = subprocess.run(
    [sys.executable, ".github/dcoir_review/scripts/dcoir_review_semantic_recall_corpus_selftest.py"],
    cwd=root, text=True, capture_output=True,
)
print(semantic.stdout, end=""); print(semantic.stderr, end="", file=sys.stderr)
if semantic.returncode or "12 cases, 10 finding classes, 2 clean classes" not in semantic.stdout + semantic.stderr:
    raise RuntimeError("semantic recall validation failed or summary drifted")
precision_cp = subprocess.run(
    [sys.executable, ".github/dcoir_review/scripts/dcoir_review_precision_regression_selftest.py"],
    cwd=root, text=True, capture_output=True,
)
print(precision_cp.stdout, end=""); print(precision_cp.stderr, end="", file=sys.stderr)
if precision_cp.returncode:
    raise RuntimeError("precision regression command failed")
precision = json.loads(precision_cp.stdout)
if float(precision["false_positive_suppression_rate"]) != 1.0:
    raise RuntimeError("false-positive suppression drift")
if float(precision["true_positive_retention_rate"]) != 1.0:
    raise RuntimeError("true-positive retention drift")
if precision.get("regressions"):
    raise RuntimeError(f"precision regressions: {precision['regressions']}")
print(f"YAML_VALIDATION_COMMANDS={len(commands)}")
print(f"GOVERNED_NON_PS_COMMANDS={len(commands) + 2}")
```

Run it, then run Step 3. The total governed registry is YAML command count + Bash + PowerShell + CodeQL. Require total `61`; this slice does not modify `validation_commands` or validation wiring. Any other total is a drift investigation, not a new accepted baseline.

- [ ] **Step 5: Run architecture ownership readback**

```powershell
python .github/dcoir_review/scripts/dcoir_review_architecture_inventory.py > .git\provider-review-inventory.json
if ($LASTEXITCODE -ne 0) { throw "architecture inventory failed: $LASTEXITCODE" }
python .git\inventory_remaining_chains.py > .git\provider-review-chains.txt
if ($LASTEXITCODE -ne 0) { throw "chain inventory failed: $LASTEXITCODE" }
```

Require final owner `dcoir_review.provider_review`, exactly one production replacement of `hardened.openrouter_review`, zero stored-original review callables, max numbered production version <=56, chains <=19, and zero missing production modules. Preserve the two-stage debug JSON writer composition unless evidence independently shows it is chronology debt.

- [ ] **Step 6: Run exact diff-scope and independent secret scan**

```powershell
$sourceParent = (Get-Content -Raw .git\provider-review-source-parent.txt).Trim()
$paths = @(git diff --name-only $sourceParent --)
if ($paths -match '^\.github/workflows/') { throw 'workflow path entered provider-review slice' }
if ($paths -match 'dcoir_review_required_runtime_patch_v(?:59|[6-9][0-9])') { throw 'v59+ production patch detected' }
git diff --check $sourceParent --
if ($LASTEXITCODE -ne 0) { throw "git diff --check failed: $LASTEXITCODE" }
```

Create `.git\provider-review-secret-scan.py`:

```python
from __future__ import annotations
import re, subprocess
from pathlib import Path

root = Path.cwd()
source_parent = (root / ".git/provider-review-source-parent.txt").read_text(encoding="ascii").strip()
paths = subprocess.check_output(
    ["git", "diff", "--name-only", source_parent, "--"], cwd=root, text=True
).splitlines()
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
for rel in paths:
    path = root / rel
    if not path.is_file():
        continue
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        continue
    for lineno, line in enumerate(lines, 1):
        if not any(pattern.search(line) for pattern in patterns):
            continue
        if required_token.search(line) or uppercase_symbol.search(line):
            continue
        findings.append(f"{rel}:{lineno}:{line[:240]}")
if findings:
    raise RuntimeError("independent secret scan findings: " + " | ".join(findings[:20]))
print(f"INDEPENDENT_SECRET_SCAN=PASS paths={len(paths)}")
```

Run it and require exit 0.

- [ ] **Step 7: Perform Prog pass**

Check exact spec coverage, explicit composition, stale v54/v57 imports, zero review storages, success/failure ordering, fail-soft behavior, and no scope expansion. Fix every valid finding test-first and rerun affected focused tests.

- [ ] **Step 8: Perform Adva adversarial pass**

Check projection-before-classification, recovery-status-before-drain, shallow-copy/copy-back, telemetry failures masking provider outcomes, exact provider exception propagation, provider-transport/model-policy drift, historical-test coupling, and workflow/#557 contamination. Fix every valid finding test-first, then rerun Steps 1-6.

- [ ] **Step 9: Freeze exact raw Git diff bytes**

Create `.git\freeze-provider-review.py`:

```python
from __future__ import annotations
import hashlib, subprocess
from pathlib import Path

root = Path.cwd()
source_parent = (root / ".git/provider-review-source-parent.txt").read_text(encoding="ascii").strip()
patch = subprocess.check_output(["git", "diff", "--binary", source_parent, "--"], cwd=root)
out = root / ".git/provider-review-frozen.patch"
out.write_bytes(patch)
print(f"PROVIDER_REVIEW_FROZEN_SHA256={hashlib.sha256(patch).hexdigest()}")
print(f"PROVIDER_REVIEW_FROZEN_BYTES={len(patch)}")
```

Record SHA-256, bytes, path count, insertion/deletion counts, ownership inventory, registry count, semantic/precision results, PowerShell count, and secret-scan result in ircore and turnover.

---

### Task 8: Hosted prepublication, coherent source commit, and exact-head validation

- [ ] **Step 1: Run hosted prepublication against the frozen raw patch**

Use the established ChatGPT Exec prepublication lane for the already-approved #550 execution goal. The validator first verifies the expected frozen SHA-256, applies that exact patch to `SOURCE_PARENT`, and runs Task 7’s focused tests, dynamic governed registry, native PowerShell validation, semantic/precision checks, inventory/chain checks, production chronology scan, secret scan, and scope guards without provider/model calls.

Credit the child command only when logs explicitly show:

```text
DCOIR_EXEC_RESULT=success
DCOIR_EXEC_EXIT_CODE=0
```

If only the known #557 status-report/cleanup rebase conflict makes the outer run red, record it separately and do not repair #557 here.

- [ ] **Step 2: Recompute raw working-tree diff and prove byte identity**

Create `.git\verify-provider-review-freeze.py`:

```python
from __future__ import annotations
import hashlib, subprocess
from pathlib import Path

root = Path.cwd()
source_parent = (root / ".git/provider-review-source-parent.txt").read_text(encoding="ascii").strip()
frozen = (root / ".git/provider-review-frozen.patch").read_bytes()
current = subprocess.check_output(["git", "diff", "--binary", source_parent, "--"], cwd=root)
if current != frozen:
    raise RuntimeError(
        f"candidate drift: frozen={hashlib.sha256(frozen).hexdigest()} current={hashlib.sha256(current).hexdigest()}"
    )
print(f"PROVIDER_REVIEW_FREEZE_VERIFIED={hashlib.sha256(current).hexdigest()}")
```

Run it immediately before staging.

- [ ] **Step 3: Stage and commit exactly the frozen source candidate**

```powershell
git add .github/dcoir_review
$unexpected = @(git diff --cached --name-only | Where-Object { $_ -like '.github/workflows/*' -or $_ -like '.github/chatgpt_staging/*' })
if ($unexpected) { throw "unexpected staged paths: $($unexpected -join ', ')" }
git commit -m "refactor(dcoir): consolidate provider review ownership"
if ($LASTEXITCODE -ne 0) { throw "source commit failed: $LASTEXITCODE" }
```

The spec/plan docs are already committed before `SOURCE_PARENT` and therefore are not part of this source candidate.

- [ ] **Step 4: Verify committed raw diff equals frozen raw diff**

Create `.git\verify-provider-review-commit.py`:

```python
from __future__ import annotations
import hashlib, subprocess
from pathlib import Path

root = Path.cwd()
source_parent = (root / ".git/provider-review-source-parent.txt").read_text(encoding="ascii").strip()
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
frozen = (root / ".git/provider-review-frozen.patch").read_bytes()
committed = subprocess.check_output(["git", "diff", "--binary", source_parent, head, "--"], cwd=root)
if committed != frozen:
    raise RuntimeError(
        f"commit/freeze mismatch: frozen={hashlib.sha256(frozen).hexdigest()} committed={hashlib.sha256(committed).hexdigest()}"
    )
print(f"PROVIDER_REVIEW_COMMITTED_SHA256={hashlib.sha256(committed).hexdigest()}")
print(f"PROVIDER_REVIEW_COMMIT={head}")
```

Require exact byte equality before push.

- [ ] **Step 5: Push the existing PR branch**

```powershell
git push origin refactor/issue-550-dcoir-runtime-consolidation
```

Do not request review and do not change Draft status.

- [ ] **Step 6: Read back exact GitHub head/checks**

Read PR #553 live and require its head SHA to equal the local source commit. Read current-head CodeQL Security, Dependency Review, Workflow Audit, and normal push validation associated with that exact SHA.

- [ ] **Step 7: Run hosted exact-head deterministic validation**

Run the exact-head ChatGPT Exec validator against the published SHA with the same deterministic contract as Task 7. Require explicit `DCOIR_EXEC_RESULT=success` and `DCOIR_EXEC_EXIT_CODE=0` in child logs.

- [ ] **Step 8: Credit the slice only after exact-head evidence is clean**

Record GitHub/ircore evidence for exact head, frozen/committed raw hash continuity, one final `dcoir_review.provider_review` owner, zero stored-original review shims, retired v54/v57 sources, max numbered version <=56, chains <=19, full registry 61/61, semantic 12/10/2, precision 1.0/1.0 with zero regressions, PowerShell parser pass, independent secret scan pass, and exact-head security/static checks.

Keep PR #553 Draft and stop before the operator-controlled GitHub Copilot independent-review gate.

---

## Plan Self-Review Checklist

- [ ] Every approved responsibility has a stable owner.
- [ ] No v59+ patch, workflow edit, #557 lifecycle edit, review request, Ready transition, or merge is authorized by this plan.
- [ ] `provider_review` owns exactly one `hardened.openrouter_review` installation.
- [ ] Final-adjudication projection precedes telemetry classification.
- [ ] Publication-floor projection itself fails soft to the original prompt/config.
- [ ] Structured-recovery reporting precedes telemetry drain.
- [ ] Telemetry remains observational/fail-soft.
- [ ] Provider exceptions remain exact.
- [ ] v54/v57 production files are deleted only after parity tests pass.
- [ ] Provider-transport tests no longer depend on historical `REVIEW_STORAGE`.
- [ ] Production-only chronology scan excludes selftests that intentionally name retired storages.
- [ ] Runtime-loader ownership includes all three new stable modules.
- [ ] Focused structured-result tests are named explicitly.
- [ ] Full-registry execution is derived from current `validation_commands` and includes exact Bash/PowerShell/CodeQL steps.
- [ ] Independent secret scanning has an exact implementation.
- [ ] `SOURCE_PARENT` is the final plan head, so spec/plan commits cannot contaminate the source freeze.
- [ ] Frozen and committed candidate hashes are computed from raw `git diff --binary` bytes, not shell text redirection.
- [ ] One coherent source commit is preserved despite task-level RED/GREEN checkpoints.
- [ ] No placeholder, `TBD`, `TODO`, or unspecified execution step remains.
