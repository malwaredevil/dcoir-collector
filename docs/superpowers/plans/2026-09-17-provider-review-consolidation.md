# Provider Review Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the chronology-dependent `hardened.openrouter_review` wrapper chain with one canonical provider-review owner while preserving structured-output recovery, request/run telemetry, final-adjudication publication-floor behavior, terminal low-confidence disposition, provider transport retry semantics, and exact existing failure behavior.

**Architecture:** `dcoir_review.provider_review` becomes the only production installer/final owner of `hardened.openrouter_review`. It explicitly composes `dcoir_review.final_adjudication_policy`, `dcoir_review.review_telemetry`, and `dcoir_review.structured_result_provider` around the pre-existing provider-review loop, while v54/v57 production modules and their stored-original review shims are retired.

**Tech Stack:** Python 3, existing DCOIR Review runtime modules/selftests, Git/GitHub, Windows PowerShell 5.1 parser validation, deterministic offline validation, GitHub Actions exact-head validation.

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
- `.github/dcoir_review/scripts/dcoir_review/review_telemetry.py` — stable request/run telemetry data structures, stage classification, call preparation/completion, summarization, and terminal emission.
- `.github/dcoir_review/scripts/dcoir_review/final_adjudication_policy.py` — final-v35 publication-floor projection plus terminal low-confidence disposition policy.

### Stable selftests

- `.github/dcoir_review/scripts/dcoir_review_provider_review_selftest.py` — canonical ownership, call ordering, exception propagation, and zero stored-original review shims.
- `.github/dcoir_review/scripts/dcoir_review_review_telemetry_selftest.py` — migrated v54 telemetry behavior under stable ownership.
- `.github/dcoir_review/scripts/dcoir_review_final_adjudication_policy_selftest.py` — migrated v57 terminal disposition behavior.
- `.github/dcoir_review/scripts/dcoir_review_final_adjudication_policy_selftest_prompt.py` — migrated publication-floor/prompt-budget behavior.
- `.github/dcoir_review/scripts/dcoir_review_final_adjudication_policy_selftest_production.py` — migrated production composition regressions.

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
- Consumes: current `DcoirReviewEntrypoint.apply_runtime_patches()` production composition.
- Produces: a stable regression contract requiring `dcoir_review.provider_review` to be the sole final `hardened.openrouter_review` owner.

- [ ] **Step 1: Write the failing ownership test**

Create a deterministic selftest that applies the live production composition and asserts all of the following:

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

The same selftest must include a fake underlying provider review and event log proving canonical call order for a forced final-adjudication call:

```python
[
    "final-policy-project",
    "telemetry-prepare",
    "provider-call",
    "structured-recovery-report",
    "telemetry-finish-success",
]
```

Add the failed-provider variant and require:

```python
[
    "final-policy-project",
    "telemetry-prepare",
    "provider-call",
    "telemetry-finish-failed",
]
```

with the exact original provider exception re-raised.

- [ ] **Step 2: Add runtime-loader expectations for the three future stable modules**

Add these direct-import paths to `DIRECT_IMPORT_MODULES` in `dcoir_review_runtime_module_loader_selftest.py`:

```python
"final_adjudication_policy.py",
"provider_review.py",
"review_telemetry.py",
```

Do not remove v54/v57 production registration assertions yet; this task is RED by design.

- [ ] **Step 3: Run RED and capture the expected failure**

Run:

```powershell
python .github/dcoir_review/scripts/dcoir_review_provider_review_selftest.py
```

Expected: FAIL because `dcoir_review.provider_review` does not exist and the current runtime still exposes three stored-original `openrouter_review` shims.

- [ ] **Step 4: Keep the RED test uncommitted**

Because this PR uses the operator-approved one-coherent-source-commit posture, do not publish an intermediate red-only commit. Record the RED evidence in the active turnover and continue to Task 2.

---

### Task 2: Extract v54 telemetry into `dcoir_review.review_telemetry`

**Files:**
- Create: `.github/dcoir_review/scripts/dcoir_review/review_telemetry.py`
- Create by responsibility-preserving rename/copy: `.github/dcoir_review/scripts/dcoir_review_review_telemetry_selftest.py`
- Modify: `.github/dcoir_review/scripts/dcoir_review/review_config.py`
- Modify: `.github/dcoir_review/scripts/dcoir_review/progress_reporting.py`
- Later delete after parity: `.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v54_selftest.py`

**Interfaces:**
- Consumes: existing v54 telemetry constants, `RunTelemetrySink`, stage classification, normalization, drain/copy, summary, compact summary, and terminal emission behavior.
- Produces:

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

- [ ] **Step 1: Copy the stable telemetry primitives without changing serialized contracts**

Move the v54 constants/data helpers into `review_telemetry.py`, preserving these literal compatibility values:

```python
SINK_ATTR = "_dcoir_v54_run_telemetry_sink"
SUMMARY_ATTR = "_dcoir_v54_run_telemetry_summary"
ERROR_COUNT_ATTR = "_dcoir_v54_telemetry_error_count"
STAGE_LABEL_ATTR = "_dcoir_v54_stage_label"
SCHEMA_VERSION = "dcoir_openrouter_run_telemetry_v1"
```

Keep `RunTelemetrySink`, `classify_stage`, `normalize_event`, `normalize_attempt`, `_drain_call`, `_copy_stage_local_telemetry`, `summarize_sink`, `compact_summary`, and `emit_run_telemetry` behavior byte-for-byte equivalent where practical.

- [ ] **Step 2: Add explicit call preparation/completion APIs**

Implement `prepare_review_call()` to perform the current v54 wrapper preparation:

```python
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

Implement `finish_review_call()` so it never raises. For `outcome in {"success", "failed"}`, call `_drain_call`; then, when `PER_FILE_PROJECTION_ATTR` is true on `root_config`, copy stage-local telemetry from `staged_config` back to `root_config`. Any telemetry failure calls `note_telemetry_error(root_config)` and returns.

- [ ] **Step 3: Switch canonical config initialization to stable telemetry**

Replace the historical import in `_initialize_run_telemetry_fail_soft()` with:

```python
from dcoir_review import review_telemetry as telemetry

try:
    telemetry.ensure_sink(config)
except Exception:
    telemetry.note_telemetry_error(config)
```

Preserve the existing outer fail-soft behavior.

- [ ] **Step 4: Switch canonical ProgressReporter telemetry to the stable module**

Replace the v54 import in `progress_reporting.py` with:

```python
from dcoir_review import review_telemetry as telemetry
```

Remove dependence on the v54 applied marker. `complete()` and `fail()` should call `telemetry.emit_run_telemetry(module, self)` inside the existing whole-call `try/except`, then continue into the original reporter behavior even if telemetry fails.

- [ ] **Step 5: Migrate the v54 selftest to stable names**

Copy the behavioral content of `dcoir_review_required_runtime_patch_v54_selftest.py` into `dcoir_review_review_telemetry_selftest.py`, replace imports/identifiers with `dcoir_review.review_telemetry`, and remove assertions about `telemetry_patch_module_names`, v54 patch application, `PATCH_ERRORS_ATTR`, `REVIEW_STORAGE`, or `_patch_openrouter_review`.

Retain all behavior assertions for:

- capture-on/off provider compatibility;
- stage classification;
- retry/failure attempt telemetry;
- no prompt/response/secret leakage;
- per-file copy-back;
- missing metadata accounting;
- shared error counts;
- terminal telemetry emission;
- terminal telemetry fail-soft behavior;
- summary/drain failure fail-soft behavior.

- [ ] **Step 6: Run focused telemetry GREEN**

Run:

```powershell
python .github/dcoir_review/scripts/dcoir_review_review_telemetry_selftest.py
python .github/dcoir_review/scripts/dcoir_review_runtime_module_loader_selftest.py
```

Expected: telemetry selftest PASS; runtime-loader may remain RED until entrypoint and historical source retirement are completed.

---

### Task 3: Extract v57 final-adjudication policy into a stable owner

**Files:**
- Create: `.github/dcoir_review/scripts/dcoir_review/final_adjudication_policy.py`
- Create by responsibility-preserving rename/copy: `.github/dcoir_review/scripts/dcoir_review_final_adjudication_policy_selftest.py`
- Create by responsibility-preserving rename/copy: `.github/dcoir_review/scripts/dcoir_review_final_adjudication_policy_selftest_prompt.py`
- Create by responsibility-preserving rename/copy: `.github/dcoir_review/scripts/dcoir_review_final_adjudication_policy_selftest_production.py`

**Interfaces:**
- Consumes: v57 publication-floor injection, final-v35 callsite detection, prompt budgeting, terminal low-confidence classification/recording, and terminal split composition.
- Produces:

```python
def project_review_call(module: Any, prompt: Any, config: Any) -> tuple[Any, Any]: ...
def apply_pareto_context_module(module: Any) -> None: ...
```

- [ ] **Step 1: Move terminal disposition logic under stable ownership**

Move `_confidence`, `_publication_floor`, `_complete_subthreshold_candidate`, `_required_sentinels_absent`, `_summary_allows_clean`, `_completed_final_adjudication_matches_result`, `_provider_envelope_matches_schema`, `_terminal_disposition`, and `_record_terminal_disposition` into `final_adjudication_policy.py`.

Preserve the compatibility literals currently consumed by result/debug/status contracts, including:

```python
DISPOSITION_MARKER = "_dcoir_v57_terminal_low_confidence_disposition"
PROMPT_INJECTION_ATTR = "_dcoir_v57_publication_floor_injected"
PROMPT_ARTIFACT_PATH = "prompts/06-semantic-adjudication-prompt.txt"
CLEAN_SUMMARY = "No high confidence findings were found after semantic adjudication."
```

Keep the persisted disposition payload field `"version": "v57"` unless a test proves it is not externally/persistently consumed.

- [ ] **Step 2: Replace the v57 openrouter wrapper with a pure projection helper**

Implement:

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
        module.hardened.write_debug_text_artifact_safely(config, PROMPT_ARTIFACT_PATH, injected)
    except Exception:
        pass
    return injected, staged
```

The helper must not call the provider, install `hardened.openrouter_review`, or store a prior provider-review callable.

- [ ] **Step 3: Install only terminal split policy**

`apply_pareto_context_module(module)` should install the terminal split responsibility exactly once. Capture the pre-policy `split_findings_with_review_body_fallback` in the closure for explicit fallback, but do not create `REVIEW_STORAGE` and do not capture/store an `openrouter_review` callable.

The wrapper behavior remains:

```python
disposition = _terminal_disposition(module, result, config, line_index, risk_sentinels)
if disposition is not None:
    _record_terminal_disposition(module, result, disposition, config)
    return [], []
return original(result, config, line_index, diff, risk_sentinels)
```

- [ ] **Step 4: Migrate the v57 tests to stable filenames/imports**

Rename test responsibility, not behavior. Replace imports of `dcoir_review_required_runtime_patch_v57` with `from dcoir_review import final_adjudication_policy as final_policy` and v54 classification imports with `from dcoir_review import review_telemetry`.

Replace storage/idempotence assertions with stable behavior assertions:

```python
final_policy.apply_pareto_context_module(module)
first_split = module.split_findings_with_review_body_fallback
final_policy.apply_pareto_context_module(module)
assert module.split_findings_with_review_body_fallback is first_split
assert not hasattr(module.hardened, "_dcoir_review_v57_original_openrouter_review")
```

Prompt tests should call `project_review_call()` directly rather than driving the historical v57 provider wrapper.

- [ ] **Step 5: Run final-policy GREEN**

Run:

```powershell
python .github/dcoir_review/scripts/dcoir_review_final_adjudication_policy_selftest.py
```

Expected: PASS for terminal disposition, prompt-floor, budget, fail-closed, and production-composition behavior.

---

### Task 4: Split structured-result request recovery from review-level status reporting

**Files:**
- Modify: `.github/dcoir_review/scripts/dcoir_review/structured_result_provider.py`
- Modify the existing structured-result/review-orchestration focused selftests that reference `_REVIEW_STORAGE` or the review wrapper.

**Interfaces:**
- Consumes: canonical request-boundary recovery around `openrouter_request_once`.
- Produces:

```python
def reset_review_recovery(config: Any) -> None: ...
def report_review_recovery(config: Any, reporter: Any) -> None: ...
```

- [ ] **Step 1: Remove the review-wrapper storage contract**

Delete:

```python
_REVIEW_STORAGE = "_dcoir_review_structured_result_provider_prior_openrouter_review"
```

and remove the `current_review` lookup, stored-original assignment, nested `openrouter_review`, and `hardened.openrouter_review = openrouter_review` block from `patch_provider()`.

Keep request-boundary `openrouter_request_once` recovery unchanged.

- [ ] **Step 2: Add explicit review recovery helpers**

Implement:

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

This intentionally makes reporter status observational/fail-soft as required by the approved spec.

- [ ] **Step 3: Add focused recovery-status regressions**

Test direct, `balanced-envelope`, and `fenced-object` modes, plus a reporter whose `update()` raises. The raising reporter must not change the provider result or exception behavior.

- [ ] **Step 4: Run focused structured-result tests**

Run the current review-orchestration/structured-result focused selftests used by the branch plus:

```powershell
python .github/dcoir_review/scripts/dcoir_review_provider_review_selftest.py
```

The provider-review selftest may still be RED until Task 5 creates the canonical owner.

---

### Task 5: Implement the canonical `dcoir_review.provider_review` owner and integrate production order

**Files:**
- Create: `.github/dcoir_review/scripts/dcoir_review/provider_review.py`
- Modify: `.github/dcoir_review/scripts/dcoir_review/entrypoint.py`
- Modify: `.github/dcoir_review/scripts/dcoir_review_provider_transport_retry_selftest.py`

**Interfaces:**
- Consumes:

```python
final_adjudication_policy.project_review_call(module, prompt, config)
review_telemetry.prepare_review_call(prompt, schema, config)
structured_result_provider.reset_review_recovery(config)
structured_result_provider.report_review_recovery(config, reporter)
review_telemetry.finish_review_call(state, outcome)
```

- Produces: sole production owner `hardened.openrouter_review` marked with `_dcoir_review_provider_review_owner = True`.

- [ ] **Step 1: Implement one explicit provider-review wrapper**

Use this control flow:

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

Do not assign `module.openrouter_review`; current production has no live alias and the approved design requires no compatibility alias.

- [ ] **Step 2: Replace v54/v57 production registration with stable owners**

In `DcoirReviewEntrypoint`:

- set `telemetry_patch_module_names` to `()`;
- keep `progress_reporting`, `provider_transport_retry`, `semantic_adjudication_recovery`, and v56 in their current relative order;
- replace terminal v57 with:

```python
"dcoir_review.final_adjudication_policy",
"dcoir_review.provider_review",
```

at the end of `post_telemetry_patch_module_names` so `provider_review` becomes the final `hardened.openrouter_review` owner.

Remove `_emit_telemetry_patch_unavailable()` and the `finally` callback from `run()` because telemetry is no longer a best-effort patch installation; stable telemetry failures are handled inside the stable helper APIs.

- [ ] **Step 3: Remove provider-transport test dependence on v54 storage**

In `dcoir_review_provider_transport_retry_selftest.py`, delete the v54 import and:

```python
retry_loop = getattr(review.hardened, v54.REVIEW_STORAGE)
```

Use the live canonical review path instead:

```python
retry_loop = review.hardened.openrouter_review
```

For cases that inspect per-attempt telemetry on the caller config, set:

```python
from dcoir_review.per_file_routing import PER_FILE_PROJECTION_ATTR
setattr(config, PER_FILE_PROJECTION_ATTR, True)
```

before invoking `retry_loop`; the stable telemetry copy-back contract then exposes the same bounded attempt history without a historical stored-original testing hook.

- [ ] **Step 4: Run canonical-owner GREEN**

Run:

```powershell
python .github/dcoir_review/scripts/dcoir_review_provider_review_selftest.py
python .github/dcoir_review/scripts/dcoir_review_provider_transport_retry_selftest.py
python .github/dcoir_review/scripts/dcoir_review_review_telemetry_selftest.py
python .github/dcoir_review/scripts/dcoir_review_final_adjudication_policy_selftest.py
```

Expected: all PASS.

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

**Interfaces:**
- Consumes: green stable telemetry/final-policy/provider-review modules.
- Produces: production sequence with max numbered version <= 56 and no v54/v57 source ownership.

- [ ] **Step 1: Delete historical sources only after stable tests pass**

Delete the six files listed above. Do not retain forwarding wrappers or compatibility aliases.

- [ ] **Step 2: Tighten runtime inventory expectations**

Update `dcoir_review_runtime_module_loader_selftest.py` so:

- `DIRECT_IMPORT_MODULES` includes the three new stable modules;
- production inventory contains neither v54 nor v57;
- the max numbered production patch is 56;
- the no-v59 guard remains intact.

Keep the existing `NUMBERED_PRODUCTION_PATCH_VERSION_CEILING = 58` compatibility guard unless a separate issue explicitly changes the global guard; the exact current maximum is asserted through architecture inventory.

- [ ] **Step 3: Update architecture documentation**

Document the explicit call order:

```text
final-adjudication projection
-> telemetry preparation
-> structured-result recovery/base provider review
-> structured-recovery status
-> telemetry drain/copy
```

Document stable ownership:

- `dcoir_review.provider_review` — single `hardened.openrouter_review` owner;
- `dcoir_review.review_telemetry` — telemetry responsibility;
- `dcoir_review.final_adjudication_policy` — publication floor and terminal low-confidence disposition;
- `dcoir_review.structured_result_provider` — request-boundary deterministic recovery only.

State that v54/v57 production sources are retired and that literal `_dcoir_v54_*` / `_dcoir_v57_*` values remain only where compatibility/persisted output requires them.

- [ ] **Step 4: Prove no stale production imports/storage names remain**

Run:

```powershell
git grep -n "dcoir_review_required_runtime_patch_v54\|dcoir_review_required_runtime_patch_v57" -- .github/dcoir_review/scripts .github/dcoir_review/ARCHITECTURE.md
git grep -n "_dcoir_review_structured_result_provider_prior_openrouter_review\|_dcoir_review_v54_original_openrouter_review\|_dcoir_review_v57_original_openrouter_review" -- .github/dcoir_review/scripts
```

Expected: no active production/test references. Historical compatibility literal values in documentation are acceptable only when explicitly described as compatibility data.

---

### Task 7: Run focused and full local validation, then Prog/Adva review

**Files:**
- Modify only if a valid review finding requires a test-first fix.
- Local evidence/logs go under `.git/` or `C:\GitHub\dcoir-artifacts\`, never as source files.

**Interfaces:**
- Consumes: complete uncommitted provider-review consolidation candidate.
- Produces: one locally validated frozen candidate ready for hosted prepublication.

- [ ] **Step 1: Run focused stable-contract tests**

Run:

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

Required semantic output contains:

```text
12 cases, 10 finding classes, 2 clean classes
```

Required precision JSON has false-positive suppression `1.0`, true-positive retention `1.0`, and `regressions: []`.

- [ ] **Step 2: Compile all changed Python source**

Run:

```powershell
python -m py_compile `
  .github/dcoir_review/scripts/dcoir_review/provider_review.py `
  .github/dcoir_review/scripts/dcoir_review/review_telemetry.py `
  .github/dcoir_review/scripts/dcoir_review/final_adjudication_policy.py `
  .github/dcoir_review/scripts/dcoir_review/structured_result_provider.py `
  .github/dcoir_review/scripts/dcoir_review/review_config.py `
  .github/dcoir_review/scripts/dcoir_review/progress_reporting.py `
  .github/dcoir_review/scripts/dcoir_review/entrypoint.py
```

Expected: exit 0.

- [ ] **Step 3: Run native Windows PowerShell parser validation**

Run the same repo-wide Windows PowerShell 5.1 parser validation used for the prior credited #550 slices and require zero parse errors. Record the exact file count; the previous exact-head baseline was 293 files.

- [ ] **Step 4: Run full governed deterministic registry**

Run the branch's complete governed DCOIR Review deterministic command registry, not only the focused commands above. Require every registered command to pass; the previous exact-head baseline was 61/61.

- [ ] **Step 5: Run structural ownership readback**

Use the existing architecture inventory/ownership characterization helper and require:

```text
hardened.openrouter_review final owner = dcoir_review.provider_review
openrouter_review production replacements = 1
stored-original openrouter_review callables = 0
max numbered production version <= 56
multi-stage callable chains <= 19
missing production modules = 0
```

Also confirm the two-stage `hardened.write_debug_json_artifact_safely` composition remains unchanged unless independent evidence proves it is not intentional.

- [ ] **Step 6: Run independent secret and workflow-scope checks**

Require:

- no secret values in the candidate diff;
- no `.github/workflows/` path in the candidate diff;
- no v59+ production path;
- no #557 lifecycle/reporting change;
- no reviewer request, Ready transition, or merge action.

- [ ] **Step 7: Perform Prog pass**

Review the implementation as the builder for:

- exact approved-spec coverage;
- explicit composition instead of hidden wrapper chronology;
- no stale v54/v57 production imports;
- no new stored-original review shim;
- test coverage for success/failure/order/fail-soft behavior.

Fix valid findings test-first.

- [ ] **Step 8: Perform Adva adversarial pass**

Review independently for:

- final-policy projection occurring before telemetry stage classification;
- structured recovery status occurring before telemetry drain;
- shallow-copy behavior and caller-config copy-back;
- telemetry failures never masking provider outcomes;
- provider exceptions re-raised unchanged;
- no transport retry/model/provider-policy drift;
- no stale version-specific test contract forcing retired architecture;
- no workflow/#557 contamination.

Fix every valid finding test-first and rerun all affected focused tests plus the full governed registry.

- [ ] **Step 9: Freeze the exact candidate**

Run:

```powershell
git diff --check
git diff --binary > .git\provider-review-frozen.patch
Get-FileHash .git\provider-review-frozen.patch -Algorithm SHA256
```

Record path count, diff byte count, SHA-256, insertion/deletion counts, structural inventory, semantic/precision results, PowerShell count, and secret-scan result in ircore and the active turnover.

---

### Task 8: Hosted prepublication, one coherent source commit, and exact-head validation

**Files:**
- Source candidate from Tasks 1-7 only.
- Agent-ops request/status artifacts are execution evidence and must not alter #557 lifecycle design.

**Interfaces:**
- Consumes: frozen locally validated patch.
- Produces: one published provider-review source commit followed by exact-head GitHub/hosted evidence.

- [ ] **Step 1: Run hosted prepublication against the frozen candidate**

Use the established ChatGPT Exec prepublication lane for the already-approved EPIC #550 execution goal. The validator must verify the frozen patch hash and rerun the focused/full deterministic checks without provider/model calls.

Credit the child command only when logs explicitly show:

```text
DCOIR_EXEC_RESULT=success
DCOIR_EXEC_EXIT_CODE=0
```

Treat the known #557 status-report/cleanup rebase conflict separately if it recurs; do not repair #557 in PR #553.

- [ ] **Step 2: Re-read frozen local bytes before publication**

Confirm the working-tree diff is byte-identical to `.git\provider-review-frozen.patch` and the SHA-256 has not changed since hosted validation.

- [ ] **Step 3: Create one coherent source commit**

Stage only the provider-review implementation/test/docs slice and commit with:

```powershell
git commit -m "refactor(dcoir): consolidate provider review ownership"
```

Verify the committed binary diff hash matches the frozen candidate before push.

- [ ] **Step 4: Push the existing PR branch**

Push `refactor/issue-550-dcoir-runtime-consolidation`. Do not request review and do not change Draft status.

- [ ] **Step 5: Read back exact GitHub head and checks**

Read PR #553 live and require the published head to equal the local commit SHA. Read exact-head CodeQL Security, Dependency Review, Workflow Audit, and any normal push validation attached to that SHA.

- [ ] **Step 6: Run hosted exact-head deterministic validation**

Run the exact-head ChatGPT Exec validator against the published commit and again require explicit `DCOIR_EXEC_RESULT=success` / `DCOIR_EXEC_EXIT_CODE=0` evidence.

- [ ] **Step 7: Credit the slice only after all exact-head evidence is clean**

Record GitHub/ircore readbacks showing:

- exact published head SHA;
- frozen/committed diff hash continuity;
- one final `dcoir_review.provider_review` owner;
- zero stored-original review shims;
- v54/v57 production sources retired;
- max numbered version <= 56;
- chains <= 19;
- full governed registry pass;
- semantic 12/10/2;
- precision 1.0/1.0, zero regressions;
- PowerShell parser pass;
- security/static checks pass.

Keep PR #553 Draft. Stop before the operator-controlled GitHub Copilot independent review gate.

---

## Plan Self-Review Checklist

Before executing source changes, verify this plan against the approved spec:

- [ ] Every approved responsibility has a stable owner.
- [ ] No task introduces a v59+ patch or workflow change.
- [ ] `provider_review` owns exactly one `hardened.openrouter_review` installation.
- [ ] v57 projection precedes telemetry classification.
- [ ] structured recovery reporting precedes telemetry drain.
- [ ] telemetry is observational/fail-soft.
- [ ] provider exceptions remain exact.
- [ ] v54/v57 production files are deleted only after parity tests pass.
- [ ] provider-transport tests no longer depend on historical `REVIEW_STORAGE`.
- [ ] runtime loader owns all three new stable modules.
- [ ] one coherent source commit is preserved despite task-level test checkpoints.
- [ ] no placeholder/TBD/TODO implementation instruction remains in this plan.
