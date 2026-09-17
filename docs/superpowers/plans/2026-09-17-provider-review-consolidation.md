# Provider Review Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the chronology-dependent `hardened.openrouter_review` wrapper chain with one canonical provider-review owner while preserving structured-output recovery, request/run telemetry, final-adjudication publication-floor behavior, terminal low-confidence disposition, provider transport retry semantics, and exact failure behavior.

**Architecture:** `dcoir_review.provider_review` becomes the only production installer/final owner of `hardened.openrouter_review`. It explicitly composes `dcoir_review.final_adjudication_policy`, `dcoir_review.review_telemetry`, and `dcoir_review.structured_result_provider` around the pre-existing provider-review loop, while v54/v57 production modules and their stored-original review shims are retired.

**Tech Stack:** Python 3, DCOIR Review runtime modules/selftests, Git/GitHub, Git-for-Windows Bash, native Windows PowerShell 5.1, deterministic offline validation, GitHub Actions exact-head validation.

**Spec:** `docs/superpowers/specs/2026-09-17-provider-review-consolidation-design.md`

## Global Constraints

- Use the existing checkout `C:\GitHub\dcoir-collector`; do not create another clone or worktree.
- PR #553 remains Draft until separately authorized.
- Do not invoke `/dcoir-review`, `/or-review`, or `/openrouter-review`; this PR changes DCOIR Review itself.
- Do not request GitHub Copilot review without explicit operator authorization.
- Do not merge without explicit operator authorization.
- Do not change workflow YAML or absorb #557 workflow/report lifecycle work.
- Do not introduce any v59+ production patch.
- Preserve model stacks, retry counts, provider routing, verifier authority, review-scope authority, return shapes, and provider exception semantics.
- Preserve persisted/externally meaningful telemetry and disposition attribute names even when their current literal values contain historical version identifiers.
- Local validation precedes publication. Publish the source implementation as one coherent validated source commit rather than speculative one-finding commits.
- Before crediting the slice, exact-head evidence must show one `hardened.openrouter_review` production owner, zero stored-original review shims, no production v54/v57 import, max numbered production version at most 56, and multi-stage callable chains at most 19 unless a stronger documented stable composition justifies otherwise.

---

## File Structure

### New stable responsibility modules

- `.github/dcoir_review/scripts/dcoir_review/provider_review.py` — sole installer/final owner for `hardened.openrouter_review`.
- `.github/dcoir_review/scripts/dcoir_review/review_telemetry.py` — request/run telemetry data structures, stage classification, call preparation/completion, summarization, and terminal emission.
- `.github/dcoir_review/scripts/dcoir_review/final_adjudication_policy.py` — final-v35 publication-floor projection plus terminal low-confidence disposition policy.

### Stable selftests

- `.github/dcoir_review/scripts/dcoir_review_provider_review_selftest.py`
- `.github/dcoir_review/scripts/dcoir_review_review_telemetry_selftest.py`
- `.github/dcoir_review/scripts/dcoir_review_final_adjudication_policy_selftest.py`
- `.github/dcoir_review/scripts/dcoir_review_final_adjudication_policy_selftest_prompt.py`
- `.github/dcoir_review/scripts/dcoir_review_final_adjudication_policy_selftest_production.py`

### Modified integration surfaces

- `.github/dcoir_review/scripts/dcoir_review/entrypoint.py`
- `.github/dcoir_review/scripts/dcoir_review/review_config.py`
- `.github/dcoir_review/scripts/dcoir_review/progress_reporting.py`
- `.github/dcoir_review/scripts/dcoir_review/structured_result_provider.py`
- `.github/dcoir_review/scripts/dcoir_review_runtime_module_loader_selftest.py`
- `.github/dcoir_review/scripts/dcoir_review_provider_transport_retry_selftest.py`
- `.github/dcoir_review/ARCHITECTURE.md`

### Retired historical production/test files

- `.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v54.py`
- `.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v54_selftest.py`
- `.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v57.py`
- `.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v57_selftest.py`
- `.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v57_selftest_prompt.py`
- `.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v57_selftest_production.py`

---

### Task 1: Add RED canonical-provider-review ownership and ordering tests

**Files:**
- Create: `.github/dcoir_review/scripts/dcoir_review_provider_review_selftest.py`
- Modify: `.github/dcoir_review/scripts/dcoir_review_runtime_module_loader_selftest.py`

**Interfaces:**
- Consumes: `DcoirReviewEntrypoint.apply_runtime_patches()`.
- Produces: stable regression coverage requiring `dcoir_review.provider_review` to be the sole final `hardened.openrouter_review` owner.

- [ ] **Step 1: Write the failing ownership test**

Create a deterministic selftest that applies production composition and asserts:

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

The same selftest must use a fake provider review and event log to prove final-adjudication success order:

```python
[
    "final-policy-project",
    "telemetry-prepare",
    "provider-call",
    "structured-recovery-report",
    "telemetry-finish-success",
]
```

and failed-provider order:

```python
[
    "final-policy-project",
    "telemetry-prepare",
    "provider-call",
    "telemetry-finish-failed",
]
```

The failed-provider case must re-raise the exact original exception object.

- [ ] **Step 2: Register the three future stable modules in the runtime-loader ownership test**

Add to `DIRECT_IMPORT_MODULES`:

```python
"final_adjudication_policy.py",
"provider_review.py",
"review_telemetry.py",
```

Do not retire v54/v57 assertions yet; this task is intentionally RED.

- [ ] **Step 3: Run RED**

```powershell
python .github/dcoir_review/scripts/dcoir_review_provider_review_selftest.py
```

Expected: non-zero exit because `dcoir_review.provider_review` is absent and the current runtime still exposes three stored-original review shims.

- [ ] **Step 4: Preserve RED evidence without an intermediate published source commit**

Record the command, failure reason, and current head in the active turnover. Keep the source candidate uncommitted and continue to Task 2 so the operator-approved one-coherent-source-commit policy is preserved.

---

### Task 2: Extract v54 telemetry into `dcoir_review.review_telemetry`

**Files:**
- Create: `.github/dcoir_review/scripts/dcoir_review/review_telemetry.py`
- Create: `.github/dcoir_review/scripts/dcoir_review_review_telemetry_selftest.py`
- Modify: `.github/dcoir_review/scripts/dcoir_review/review_config.py`
- Modify: `.github/dcoir_review/scripts/dcoir_review/progress_reporting.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class ReviewTelemetryCall:
    root_config: Any
    staged_config: Any
    sink: RunTelemetrySink
    stage: str


def ensure_sink(config: Any) -> RunTelemetrySink: ...
def note_telemetry_error(config: Any) -> None: ...
def prepare_review_call(prompt: Any, schema: Any, config: Any) -> ReviewTelemetryCall | None: ...
def finish_review_call(state: ReviewTelemetryCall | None, outcome: str) -> None: ...
def summarize_sink(config: Any) -> dict[str, Any]: ...
def compact_summary(summary: dict[str, Any], limit: int = 1800) -> str: ...
def emit_run_telemetry(module: Any, reporter: Any) -> None: ...
```

- [ ] **Step 1: Move telemetry primitives without changing serialized contracts**

Preserve these literal compatibility values:

```python
SINK_ATTR = "_dcoir_v54_run_telemetry_sink"
SUMMARY_ATTR = "_dcoir_v54_run_telemetry_summary"
ERROR_COUNT_ATTR = "_dcoir_v54_telemetry_error_count"
STAGE_LABEL_ATTR = "_dcoir_v54_stage_label"
SCHEMA_VERSION = "dcoir_openrouter_run_telemetry_v1"
```

Move `RunTelemetrySink`, stage classification, normalization, drain/copy, summarization, compact-summary, and terminal-emission behavior from v54 into the stable module without changing their observable outputs.

- [ ] **Step 2: Implement explicit call preparation**

```python
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

- [ ] **Step 3: Implement explicit call completion**

`finish_review_call(state, outcome)` must return immediately when `state is None`; otherwise call the existing drain logic with `outcome` equal to `success` or `failed`. If the root config has `PER_FILE_PROJECTION_ATTR`, copy stage-local telemetry back. Every telemetry error is caught, counted through `note_telemetry_error(root_config)`, and never escapes.

- [ ] **Step 4: Switch canonical config initialization to stable telemetry**

In `review_config._initialize_run_telemetry_fail_soft()` use:

```python
from dcoir_review import review_telemetry as telemetry

try:
    telemetry.ensure_sink(config)
except Exception:
    telemetry.note_telemetry_error(config)
```

The outer config-load path must remain available even if both calls fail.

- [ ] **Step 5: Switch ProgressReporter terminal telemetry to the stable module**

Replace the v54 import in `progress_reporting.py` with:

```python
from dcoir_review import review_telemetry as telemetry
```

Remove dependence on the v54 applied marker. `complete()` and `fail()` call `telemetry.emit_run_telemetry(module, self)` inside the existing whole-call `try/except`, then continue to the original reporter behavior even when telemetry fails.

- [ ] **Step 6: Migrate v54 behavioral tests to stable ownership**

Create `dcoir_review_review_telemetry_selftest.py` from the surviving behavioral assertions in the v54 selftest. Remove tests for v54 patch installation, `PATCH_ERRORS_ATTR`, `REVIEW_STORAGE`, and `_patch_openrouter_review`. Preserve tests for capture compatibility, stage classification, retry/failure attempt telemetry, secret/prompt exclusion, per-file copy-back, missing metadata, shared error counts, terminal emission, and fail-soft drain/summary/terminal behavior.

- [ ] **Step 7: Run focused telemetry tests**

```powershell
python .github/dcoir_review/scripts/dcoir_review_review_telemetry_selftest.py
```

Expected: exit 0. The runtime-loader ownership test may still fail until entrypoint cutover and historical-file retirement in Tasks 5-6.

---

### Task 3: Extract v57 final-adjudication policy into a stable owner

**Files:**
- Create: `.github/dcoir_review/scripts/dcoir_review/final_adjudication_policy.py`
- Create: `.github/dcoir_review/scripts/dcoir_review_final_adjudication_policy_selftest.py`
- Create: `.github/dcoir_review/scripts/dcoir_review_final_adjudication_policy_selftest_prompt.py`
- Create: `.github/dcoir_review/scripts/dcoir_review_final_adjudication_policy_selftest_production.py`

**Interfaces:**

```python
def project_review_call(module: Any, prompt: Any, config: Any) -> tuple[Any, Any]: ...
def apply_pareto_context_module(module: Any) -> None: ...
```

- [ ] **Step 1: Move terminal-disposition logic under stable ownership**

Move the v57 confidence, publication-floor, candidate validation, final-adjudication provenance, provider-envelope, terminal-disposition, and disposition-recording helpers into `final_adjudication_policy.py`.

Preserve compatibility literals:

```python
DISPOSITION_MARKER = "_dcoir_v57_terminal_low_confidence_disposition"
PROMPT_INJECTION_ATTR = "_dcoir_v57_publication_floor_injected"
PROMPT_ARTIFACT_PATH = "prompts/06-semantic-adjudication-prompt.txt"
CLEAN_SUMMARY = "No high confidence findings were found after semantic adjudication."
```

Preserve the persisted disposition payload field `"version": "v57"` unless a deterministic regression demonstrates it is not a compatibility/persisted-output contract.

- [ ] **Step 2: Replace the v57 provider wrapper with a pure projection helper**

```python
def project_review_call(module: Any, prompt: Any, config: Any) -> tuple[Any, Any]:
    injected = _inject_publication_floor(prompt, config)
    if injected is prompt:
        return prompt, config
    try:
        staged = copy.copy(config)
        setattr(staged, review_telemetry.STAGE_LABEL_ATTR, "semantic-adjudicator")
        setattr(staged, PROMPT_INJECTION_ATTR, True)
    except Exception:
        return prompt, config
    try:
        module.hardened.write_debug_text_artifact_safely(
            config, PROMPT_ARTIFACT_PATH, injected
        )
    except Exception:
        pass
    return injected, staged
```

The helper must not call the provider, install `hardened.openrouter_review`, or retain a previous provider-review callable.

- [ ] **Step 3: Install only the terminal split policy**

`apply_pareto_context_module(module)` installs the terminal split responsibility exactly once. The wrapper calls `_terminal_disposition`; when disposition exists it records the disposition and returns `([], [])`; otherwise it invokes the pre-policy split callable. Do not create `REVIEW_STORAGE` and do not capture/store `openrouter_review`.

- [ ] **Step 4: Migrate v57 tests to stable filenames/imports**

Replace v57 imports with:

```python
from dcoir_review import final_adjudication_policy as final_policy
from dcoir_review import review_telemetry
```

Replace historical storage assertions with behavior/idempotence assertions:

```python
final_policy.apply_pareto_context_module(module)
first_split = module.split_findings_with_review_body_fallback
final_policy.apply_pareto_context_module(module)
assert module.split_findings_with_review_body_fallback is first_split
assert not hasattr(module.hardened, "_dcoir_review_v57_original_openrouter_review")
```

Prompt tests call `project_review_call()` directly and assert the projected prompt/config, stage label, prompt budget, debug-artifact fail-soft behavior, and no-op behavior for ordinary calls.

- [ ] **Step 5: Run final-policy tests**

```powershell
python .github/dcoir_review/scripts/dcoir_review_final_adjudication_policy_selftest.py
```

Expected: exit 0, including imported prompt and production regression helpers.

---

### Task 4: Split structured-result request recovery from review-level status reporting

**Files:**
- Modify: `.github/dcoir_review/scripts/dcoir_review/structured_result_provider.py`
- Modify any focused selftest that directly references `_REVIEW_STORAGE` or the historical review wrapper.

**Interfaces:**

```python
def reset_review_recovery(config: Any) -> None: ...
def report_review_recovery(config: Any, reporter: Any) -> None: ...
```

- [ ] **Step 1: Remove the review-wrapper storage contract**

Delete `_REVIEW_STORAGE`, the `current_review` lookup/storage block, the nested review wrapper, and assignments to `hardened.openrouter_review`/`module.openrouter_review`. Keep request-boundary `openrouter_request_once` recovery unchanged.

- [ ] **Step 2: Add explicit review recovery helpers**

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

- [ ] **Step 3: Add focused status-report regressions**

Test `direct`, `balanced-envelope`, and `fenced-object` modes plus a reporter whose `update()` raises. Reporter failure must not alter provider results or provider exceptions.

- [ ] **Step 4: Run the focused recovery tests plus current provider-review RED/GREEN test**

Run the branch’s structured-result/review-orchestration focused selftests that cover `structured_result_provider.patch_provider`, then:

```powershell
python .github/dcoir_review/scripts/dcoir_review_provider_review_selftest.py
```

The provider-review test may remain RED until Task 5 installs the canonical owner; a failure is acceptable only when it is the expected missing-owner failure recorded in Task 1.

---

### Task 5: Implement canonical `dcoir_review.provider_review` and production order

**Files:**
- Create: `.github/dcoir_review/scripts/dcoir_review/provider_review.py`
- Modify: `.github/dcoir_review/scripts/dcoir_review/entrypoint.py`
- Modify: `.github/dcoir_review/scripts/dcoir_review_provider_transport_retry_selftest.py`

**Interfaces:**

```python
final_adjudication_policy.project_review_call(module, prompt, config)
review_telemetry.prepare_review_call(prompt, schema, config)
structured_result_provider.reset_review_recovery(config)
structured_result_provider.report_review_recovery(config, reporter)
review_telemetry.finish_review_call(state, outcome)
```

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
        state = review_telemetry.prepare_review_call(
            projected_prompt, schema, projected_config
        )
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

Do not assign `module.openrouter_review`; current production has no live alias.

- [ ] **Step 2: Replace v54/v57 production registration with stable owners**

In `DcoirReviewEntrypoint` set:

```python
telemetry_patch_module_names: tuple[str, ...] = ()
```

Keep `progress_reporting`, `provider_transport_retry`, `semantic_adjudication_recovery`, and v56 in their current relative order. End `post_telemetry_patch_module_names` with:

```python
"dcoir_review.final_adjudication_policy",
"dcoir_review.provider_review",
```

so provider review is the final `hardened.openrouter_review` owner.

Remove `_emit_telemetry_patch_unavailable()` and the `finally` callback from `run()`; stable telemetry failures are handled by stable helper APIs rather than patch-installation metadata.

- [ ] **Step 3: Remove provider-transport test dependence on v54 storage**

Delete the v54 import and historical `REVIEW_STORAGE` lookup. Use:

```python
retry_loop = review.hardened.openrouter_review
```

For cases that must inspect per-attempt telemetry on the caller config, set:

```python
from dcoir_review.per_file_routing import PER_FILE_PROJECTION_ATTR
setattr(config, PER_FILE_PROJECTION_ATTR, True)
```

before calling `retry_loop`; stable telemetry copy-back must expose the same bounded attempt history.

- [ ] **Step 4: Run canonical-owner GREEN**

```powershell
python .github/dcoir_review/scripts/dcoir_review_provider_review_selftest.py
python .github/dcoir_review/scripts/dcoir_review_provider_transport_retry_selftest.py
python .github/dcoir_review/scripts/dcoir_review_review_telemetry_selftest.py
python .github/dcoir_review/scripts/dcoir_review_final_adjudication_policy_selftest.py
```

Expected: all exit 0.

---

### Task 6: Retire v54/v57 historical production/test surfaces and update architecture inventory/docs

**Files:**
- Delete: `.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v54.py`
- Delete: `.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v54_selftest.py`
- Delete: `.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v57.py`
- Delete: `.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v57_selftest.py`
- Delete: `.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v57_selftest_prompt.py`
- Delete: `.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v57_selftest_production.py`
- Modify: `.github/dcoir_review/scripts/dcoir_review_runtime_module_loader_selftest.py`
- Modify: `.github/dcoir_review/ARCHITECTURE.md`

- [ ] **Step 1: Delete historical sources only after stable focused tests pass**

Delete all six historical files above. Do not retain forwarding wrappers or aliases.

- [ ] **Step 2: Tighten runtime inventory expectations**

Keep the global no-v59 guard `NUMBERED_PRODUCTION_PATCH_VERSION_CEILING = 58`; require actual architecture inventory `max_numbered_version <= 56`, no v54/v57 production registration, and all three stable modules in `DIRECT_IMPORT_MODULES`.

- [ ] **Step 3: Update architecture documentation**

Document this explicit review call order:

```text
final-adjudication projection
-> telemetry preparation
-> structured-result recovery/base provider review
-> structured-recovery status
-> telemetry drain/copy
```

Document stable ownership and state that v54/v57 production sources are retired while `_dcoir_v54_*`/`_dcoir_v57_*` literal values remain only where compatibility/persisted output requires them.

- [ ] **Step 4: Prove no stale production imports/storage names remain**

```powershell
git grep -n "dcoir_review_required_runtime_patch_v54\|dcoir_review_required_runtime_patch_v57" -- .github/dcoir_review/scripts .github/dcoir_review/ARCHITECTURE.md
git grep -n "_dcoir_review_structured_result_provider_prior_openrouter_review\|_dcoir_review_v54_original_openrouter_review\|_dcoir_review_v57_original_openrouter_review" -- .github/dcoir_review/scripts
```

Expected: no active source/test references. A non-zero `git grep` exit caused by zero matches is success for this step.

---

### Task 7: Run focused and full local validation, then Prog/Adva review

**Files:**
- Modify source only when a valid review finding requires a test-first fix.
- Write transient evidence under `.git/` or `C:\GitHub\dcoir-artifacts\`, not tracked source paths.

- [ ] **Step 1: Run focused stable-contract tests**

```powershell
python .github/dcoir_review/scripts/dcoir_review_provider_review_selftest.py
python .github/dcoir_review/scripts/dcoir_review_review_telemetry_selftest.py
python .github/dcoir_review/scripts/dcoir_review_final_adjudication_policy_selftest.py
python .github/dcoir_review/scripts/dcoir_review_provider_transport_retry_selftest.py
python .github/dcoir_review/scripts/dcoir_review_runtime_module_loader_selftest.py
python .github/dcoir_review/scripts/dcoir_review_semantic_recall_corpus_selftest.py
python .github/dcoir_review/scripts/dcoir_review_precision_regression_selftest.py
python .github/dcoir_review/scripts/validate-codeql-security-workflow.py
```

Require semantic text `12 cases, 10 finding classes, 2 clean classes`. Parse precision JSON and require `false_positive_suppression_rate == 1.0`, `true_positive_retention_rate == 1.0`, and `regressions == []`.

- [ ] **Step 2: Compile changed Python**

```powershell
$changedPython = git diff --name-only 6390ab7c6b9993f8fd3b931613e90740d3cd6b15 -- '*.py'
if (-not $changedPython) { throw 'no changed Python files found' }
python -m py_compile $changedPython
if ($LASTEXITCODE -ne 0) { throw "py_compile failed: $LASTEXITCODE" }
```

Use `6390ab7c6b9993f8fd3b931613e90740d3cd6b15` as the source-slice parent because the intervening commits are spec/plan documentation only.

- [ ] **Step 3: Run native Windows PowerShell 5.1 parser validation with the governed command**

```powershell
$powershell = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
if (-not (Test-Path -LiteralPath $powershell)) { throw "native Windows PowerShell not found: $powershell" }
$psCommand = @'
$ErrorActionPreference='Stop';
function Get-FileHash {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory=$true)][string]$LiteralPath,
    [ValidateSet('SHA256')][string]$Algorithm='SHA256'
  )
  $stream=[System.IO.File]::OpenRead($LiteralPath)
  $sha=[System.Security.Cryptography.SHA256]::Create()
  try {
    $hash=([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-','')
    [pscustomobject]@{Algorithm='SHA256';Hash=$hash;Path=[System.IO.Path]::GetFullPath($LiteralPath)}
  } finally {
    $sha.Dispose(); $stream.Dispose()
  }
}
& '.github/dcoir_review/scripts/validate-windows-powershell-51.ps1' -AllowEmpty
'@
& $powershell -NoProfile -ExecutionPolicy Bypass -Command $psCommand
if ($LASTEXITCODE -ne 0) { throw "Windows PowerShell parser validation failed: $LASTEXITCODE" }
```

Require zero parser errors. Record the emitted `Validating N PowerShell file(s).` count; compare it to the prior 293-file baseline but do not hard-code 293 as a new truth if legitimate non-workflow source-file count changed elsewhere.

- [ ] **Step 4: Run the complete governed deterministic registry exactly from current configuration**

Create `.git\run-provider-review-registry.py` with this exact implementation:

```python
from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
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
print(semantic.stdout, end="")
print(semantic.stderr, end="", file=sys.stderr)
if semantic.returncode or "12 cases, 10 finding classes, 2 clean classes" not in semantic.stdout + semantic.stderr:
    raise RuntimeError("semantic recall validation failed or summary drifted")

precision_cp = subprocess.run(
    [sys.executable, ".github/dcoir_review/scripts/dcoir_review_precision_regression_selftest.py"],
    cwd=root, text=True, capture_output=True,
)
print(precision_cp.stdout, end="")
print(precision_cp.stderr, end="", file=sys.stderr)
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

Run:

```powershell
python .git\run-provider-review-registry.py
if ($LASTEXITCODE -ne 0) { throw "governed registry failed: $LASTEXITCODE" }
```

Then run the PowerShell command from Step 3. Count the complete governed registry as the current YAML validation-command count plus `validate-codex-local.sh`, native Windows PowerShell parser validation, and `validate-codeql-security-workflow.py`. The previous credited exact-head total was 61; require the new total to equal 61 because this slice does not modify `validation_commands` or validation wiring. If the computed total differs, stop and inspect the configuration diff rather than silently accepting drift.

- [ ] **Step 5: Run structural ownership readback**

```powershell
python .github/dcoir_review/scripts/dcoir_review_architecture_inventory.py > .git\provider-review-inventory.json
if ($LASTEXITCODE -ne 0) { throw "architecture inventory failed: $LASTEXITCODE" }
```

Then run the existing `.git\inventory_remaining_chains.py` helper from this PR continuation. Require:

```text
hardened.openrouter_review final owner = dcoir_review.provider_review
openrouter_review production replacements = 1
stored-original openrouter_review callables = 0
max numbered production version <= 56
multi-stage callable chains <= 19
missing production modules = 0
```

Also confirm the two-stage `hardened.write_debug_json_artifact_safely` composition remains unchanged unless independent evidence proves it is chronology debt rather than intentional metadata enrichment.

- [ ] **Step 6: Run diff-scope and secret checks**

```powershell
$paths = git diff --name-only 6390ab7c6b9993f8fd3b931613e90740d3cd6b15 --
if ($paths -match '^\.github/workflows/') { throw 'workflow path entered provider-review slice' }
if ($paths -match 'dcoir_review_required_runtime_patch_v(?:59|[6-9][0-9])') { throw 'v59+ production patch detected' }
git diff --check 6390ab7c6b9993f8fd3b931613e90740d3cd6b15 --
if ($LASTEXITCODE -ne 0) { throw "git diff --check failed: $LASTEXITCODE" }
```

Run the same independent secret scanner implementation already used for the preceding #550 source slices against the candidate diff. Its required result is zero secret findings; do not weaken or replace its patterns during this slice.

- [ ] **Step 7: Perform Prog pass**

Review exact approved-spec coverage, explicit composition, stale v54/v57 imports, stored-original review shims, success/failure ordering, and fail-soft behavior. Fix every valid finding test-first and rerun affected focused tests.

- [ ] **Step 8: Perform Adva adversarial pass**

Review independently for projection-before-classification, recovery-status-before-drain, shallow-copy/copy-back correctness, telemetry failures masking provider outcomes, exact provider exception propagation, provider-transport/model-policy drift, historical-test coupling, and workflow/#557 contamination. Fix every valid finding test-first, then rerun all focused tests and the complete registry from Step 4 plus PowerShell Step 3.

- [ ] **Step 9: Freeze the exact candidate**

```powershell
git diff --check 6390ab7c6b9993f8fd3b931613e90740d3cd6b15 --
git diff --binary 6390ab7c6b9993f8fd3b931613e90740d3cd6b15 -- > .git\provider-review-frozen.patch
$hash = (Get-FileHash -LiteralPath .git\provider-review-frozen.patch -Algorithm SHA256).Hash.ToLowerInvariant()
$bytes = (Get-Item -LiteralPath .git\provider-review-frozen.patch).Length
Write-Output "PROVIDER_REVIEW_FROZEN_SHA256=$hash"
Write-Output "PROVIDER_REVIEW_FROZEN_BYTES=$bytes"
```

Record path count, diff bytes, SHA-256, insertion/deletion counts, structural inventory, registry count, semantic/precision results, PowerShell count, and secret-scan result in ircore and the active turnover.

---

### Task 8: Hosted prepublication, one coherent source commit, and exact-head validation

**Files:**
- Source candidate from Tasks 1-7 only.
- Agent-ops request/status artifacts are execution evidence; do not alter #557 lifecycle design.

- [ ] **Step 1: Run hosted prepublication against the frozen candidate**

Use the established ChatGPT Exec prepublication lane for the already-approved #550 execution goal. Stage one request whose validator first verifies the expected frozen SHA-256 and then runs the same focused tests, dynamic governed-registry algorithm, PowerShell validation, semantic/precision checks, inventory checks, secret scan, and source-scope guards from Task 7. It must not make provider/model calls.

Credit the child command only when job logs explicitly contain:

```text
DCOIR_EXEC_RESULT=success
DCOIR_EXEC_EXIT_CODE=0
```

If the outer workflow again fails only in status-report/cleanup because of the known #557 stale-request rebase conflict, record that separately and do not repair #557 in PR #553.

- [ ] **Step 2: Re-read frozen bytes before publication**

```powershell
$current = git diff --binary 6390ab7c6b9993f8fd3b931613e90740d3cd6b15 --
[System.IO.File]::WriteAllText((Join-Path $env:TEMP 'provider-review-current.patch'), $current, [System.Text.UTF8Encoding]::new($false))
```

Compare the exact byte stream used for hosted validation to `.git\provider-review-frozen.patch`. If hashes differ, invalidate hosted prepublication and refreeze/revalidate before committing.

- [ ] **Step 3: Create one coherent source commit**

Stage only the provider-review implementation/test/docs slice. Confirm `git diff --cached --name-only` contains no workflow, agent-ops, or unrelated files. Commit:

```powershell
git commit -m "refactor(dcoir): consolidate provider review ownership"
```

Verify the committed binary diff against parent `6390ab7c6b9993f8fd3b931613e90740d3cd6b15` has the same SHA-256 as the frozen candidate after excluding the already-published spec/plan documentation commits from the source-slice comparison.

- [ ] **Step 4: Push the existing PR branch**

```powershell
git push origin refactor/issue-550-dcoir-runtime-consolidation
```

Do not request review and do not change Draft status.

- [ ] **Step 5: Read back exact GitHub head/checks**

Read PR #553 live and require its head SHA to equal the local source commit. Read current-head CodeQL Security, Dependency Review, Workflow Audit, and any normal push validation associated with that exact SHA.

- [ ] **Step 6: Run hosted exact-head deterministic validation**

Run the exact-head ChatGPT Exec validator against the published SHA using the same deterministic contract as Task 7. Require explicit `DCOIR_EXEC_RESULT=success` and `DCOIR_EXEC_EXIT_CODE=0` in the child job logs.

- [ ] **Step 7: Credit the slice only after exact-head evidence is clean**

Record GitHub/ircore readbacks proving exact head, frozen/committed hash continuity, one final `dcoir_review.provider_review` owner, zero stored-original review shims, retired v54/v57 production sources, max numbered version <=56, chains <=19, full governed registry pass, semantic 12/10/2, precision 1.0/1.0 with zero regressions, PowerShell parser pass, and security/static checks pass.

Keep PR #553 Draft and stop before the operator-controlled GitHub Copilot independent-review gate.

---

## Plan Self-Review Checklist

- [ ] Every approved responsibility has a stable owner.
- [ ] No task introduces a v59+ patch or workflow change.
- [ ] `provider_review` owns exactly one `hardened.openrouter_review` installation.
- [ ] final-adjudication projection precedes telemetry classification.
- [ ] structured-recovery reporting precedes telemetry drain.
- [ ] telemetry remains observational/fail-soft.
- [ ] provider exceptions remain exact.
- [ ] v54/v57 production files are deleted only after parity tests pass.
- [ ] provider-transport tests no longer depend on historical `REVIEW_STORAGE`.
- [ ] runtime-loader ownership includes all three new stable modules.
- [ ] one coherent source commit is preserved despite task-level test checkpoints.
- [ ] full-registry execution is derived from current `validation_commands` and includes exact Bash/PowerShell/CodeQL steps.
- [ ] no placeholder, `TBD`, `TODO`, or unspecified implementation step remains.
