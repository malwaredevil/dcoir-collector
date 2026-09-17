# Provider Review Consolidation Design

## Context

EPIC #550 is consolidating DCOIR Review away from chronology-dependent runtime patch stacking and stored-original wrapper chains. At PR head `6390ab7c6b9993f8fd3b931613e90740d3cd6b15`, the ProgressReporter responsibility is already consolidated and exact-head validated. The next characterized low-count seam is `hardened.openrouter_review`.

The live runtime currently installs three successive `hardened.openrouter_review` wrappers:

1. `dcoir_review.structured_result_provider.patch_provider` wraps the base provider-review loop to report deterministic structured-output recovery.
2. `dcoir_review_required_runtime_patch_v54` wraps that result to project per-call telemetry capture, classify the review stage, drain request telemetry, and preserve per-file telemetry readback.
3. `dcoir_review_required_runtime_patch_v57` wraps the telemetry layer to inject the publication-confidence floor only for the final v35 semantic-adjudication call.

Each layer stores the prior callable, leaving three stored-original `openrouter_review` shims. Production call sites use `hardened.openrouter_review`; there is no active `module.openrouter_review` alias that needs compatibility preservation.

## Problem

These responsibilities are individually legitimate, but their composition is chronology-dependent. A maintainer must understand the order in which the structured-result provider, v54, and v57 happened to patch `hardened.openrouter_review` in order to reason about current behavior. That violates the #550 maintainer-readability standard even though each wrapper is behaviorally justified.

The consolidation must remove runtime wrapper chronology without weakening any of the following contracts:

- provider/model routing and bounded retry behavior;
- structured-result deterministic recovery and its reporter messages;
- request-attempt and run telemetry semantics;
- telemetry fail-soft behavior;
- per-file telemetry projection/readback compatibility;
- final-v35 publication-floor prompt injection and prompt-budget behavior;
- final low-confidence clean disposition behavior;
- provider transport retry ownership;
- exact review-scope enforcement;
- verifier and semantic-adjudication authority;
- existing schema and persisted telemetry fields.

## Chosen Architecture

Introduce stable responsibility owners and one canonical installer for `hardened.openrouter_review`.

### 1. `dcoir_review.provider_review`

This module becomes the only production owner that assigns `hardened.openrouter_review` after the base hardened provider loop is available. It composes provider-review responsibilities explicitly rather than by capturing prior wrappers.

Its call flow is:

1. ask final-adjudication policy whether the prompt/config need projection;
2. prepare telemetry call state and stage metadata fail-soft;
3. invoke the underlying provider-review implementation exactly once;
4. report structured-result recovery status from the completed call;
5. drain/copy telemetry on success, or drain/copy then re-raise on failure;
6. return the provider-review result unchanged.

The canonical owner must preserve the existing callable signature:

```python
openrouter_review(prompt, schema, config, reporter=None)
```

It must not change model stacks, retry counts, ignored-provider handling, provider transport retry behavior, return shape, or exception semantics.

### 2. Stable request/run telemetry responsibility

Move v54's telemetry helpers and data structures into a stable responsibility module, expected to be `dcoir_review.review_telemetry` unless implementation evidence shows a narrower split is required.

This stable telemetry owner will contain the current telemetry schema/version constants, sink management, normalization, stage classification, call preparation/drain helpers, per-file telemetry copy behavior, summary/compact-summary behavior, telemetry error accounting, and terminal `emit_run_telemetry` helper.

`dcoir_review.review_config` and `dcoir_review.progress_reporting` must import the stable telemetry owner instead of importing `dcoir_review_required_runtime_patch_v54`.

Telemetry remains observational. Any telemetry preparation, drain, summary, copy, or terminal-emission failure must not change the underlying review result or mask an underlying provider failure.

### 3. `dcoir_review.final_adjudication_policy`

Move the surviving v57 responsibilities into a stable policy module:

- final-v35 call-site recognition;
- publication-floor prompt injection;
- prompt-budget enforcement and truncation marker behavior;
- final low-confidence terminal disposition classification and recording;
- associated constants/markers that remain runtime compatibility contracts.

This module must not install or wrap `hardened.openrouter_review`. Instead it exposes a helper that projects `(prompt, config)` for the final adjudication call, returning unchanged inputs for every other call.

The module may continue to own the terminal `split_findings_with_review_body_fallback` policy if that remains the smallest cohesive boundary, but that responsibility must be installed directly without storing or wrapping an unrelated provider-review callable.

### 4. Structured-result provider recovery

`dcoir_review.structured_result_provider` remains the canonical request-boundary owner for deterministic structured-output recovery around `openrouter_request_once`.

Its current `openrouter_review` wrapper and `_REVIEW_STORAGE` shim are removed. The small post-call reporter behavior becomes an explicit helper that `dcoir_review.provider_review` invokes after the underlying provider-review returns. Request-boundary recovery and review-level reporter messaging stay separate and testable.

### 5. Historical module retirement

Once all live responsibilities are moved and parity is proven:

- remove `dcoir_review_required_runtime_patch_v54.py` from the production sequence;
- remove `dcoir_review_required_runtime_patch_v57.py` from the production sequence;
- delete those production source files only after no production import depends on them;
- migrate or replace their version-specific selftests with stable responsibility tests;
- preserve only compatibility markers whose external/persisted meaning is demonstrated.

No v59+ production overlay may be introduced.

## Exact Behavioral Ordering

The canonical call ordering must preserve the behavior currently produced by the three-wrapper chain.

For a final-v35 semantic-adjudication call:

1. the publication floor is injected and bounded to `max_prompt_chars`;
2. the staged config is labelled `semantic-adjudicator` before telemetry classification;
3. telemetry capture state is initialized on a shallow config projection;
4. the structured-result provider/base review loop executes;
5. structured-output recovery status is reported to the reporter, when applicable;
6. telemetry is drained as success or failure;
7. per-file telemetry projection is copied back when the caller requested it;
8. underlying provider exceptions are re-raised unchanged.

For ordinary calls, step 1 is a no-op and all other behavior remains equivalent.

## Failure Semantics

The consolidation must preserve defense-in-depth behavior:

- If publication-floor projection fails before a safe projected config exists, fall back to the original prompt/config behavior rather than blocking review.
- If telemetry setup fails, record a telemetry error when possible and invoke the underlying provider review with the original config.
- If the provider review fails, telemetry drain/copy remains best-effort and the original provider exception must be re-raised.
- If recovery-status reporting fails, it must not alter the provider-review result.
- Debug artifact write failures during final-adjudication projection remain best-effort and non-blocking.
- Terminal run telemetry remains unable to block reporter completion/failure.

## Ownership and Structural Acceptance Criteria

Before this slice is credited, exact-head characterization must show:

- `hardened.openrouter_review` has one production installer/final owner: `dcoir_review.provider_review`;
- runtime replacements for `hardened.openrouter_review` are exactly one;
- stored-original `openrouter_review` callables are zero;
- the prior three-layer `openrouter_review` chain is removed;
- no active production import of v54 or v57 remains;
- max numbered production patch version decreases from 57 to at most 56;
- the multi-stage callable-chain count decreases from 20 to at most 19 unless an explicitly documented new stable composition is introduced for a stronger architectural reason;
- no workflow source file is changed;
- no #557 workflow/report lifecycle work is absorbed;
- no provider/model call is needed for deterministic validation.

## File-Level Design

Expected new stable modules:

- `.github/dcoir_review/scripts/dcoir_review/provider_review.py`
- `.github/dcoir_review/scripts/dcoir_review/review_telemetry.py`
- `.github/dcoir_review/scripts/dcoir_review/final_adjudication_policy.py`

Expected modified integration surfaces:

- `.github/dcoir_review/scripts/dcoir_review/entrypoint.py`
- `.github/dcoir_review/scripts/dcoir_review/review_config.py`
- `.github/dcoir_review/scripts/dcoir_review/progress_reporting.py`
- `.github/dcoir_review/scripts/dcoir_review/structured_result_provider.py`
- `.github/dcoir_review/ARCHITECTURE.md`
- runtime loader/architecture inventory tests;
- stable telemetry, structured-result, provider-transport, final-adjudication, and ownership selftests.

Expected retired production sources after parity is proven:

- `.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v54.py`
- `.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v57.py`

Version-specific selftests may be deleted, renamed, or split only after their surviving behavioral assertions are mapped into stable responsibility tests.

## Test Strategy

Implementation follows RED/GREEN discipline.

First, add ownership tests that fail on the current head because there are three `openrouter_review` replacements and three stored-original shims. Add explicit ordering regressions proving final-adjudication projection precedes telemetry classification and proving structured-recovery reporting occurs without changing telemetry/provider results.

Then implement the minimum stable-owner composition to make those tests green. Run the focused contracts for:

- structured-result recovery;
- request/run telemetry;
- final-adjudication prompt-floor and low-confidence disposition;
- provider transport retry;
- review-scope guard;
- ProgressReporter terminal telemetry;
- runtime module loading and architecture inventory.

After focused GREEN, run the complete governed deterministic registry, semantic recall, precision regression, native Windows PowerShell parser validation, static/security validation, secret scan, and `git diff --check`.

Prog performs the implementation pass. Adva performs an adversarial review of call ordering, exception propagation, shallow-copy semantics, telemetry fail-soft behavior, provider-transport interaction, stale historical imports, and compatibility markers. Any valid finding is fixed test-first and the full relevant validation set is rerun.

The frozen candidate is hashed and validated through the existing hosted prepublication lane. Only if that passes is the exact candidate published to PR #553. Exact-head GitHub checks and hosted deterministic validation must then pass before the slice is credited.

## Non-Goals

This slice does not:

- redesign ChatGPT Exec/report lifecycle behavior from #557;
- change workflow YAML;
- request DCOIR self-review;
- request GitHub Copilot review;
- move PR #553 from Draft to Ready;
- merge PR #553;
- change model policy, model stacks, retry budgets, or provider-routing policy;
- enter the high-coupling risk-sentinel/ranking/deduplication family unless this design uncovers a direct dependency that cannot be isolated.

## Rollback Boundary

The slice is one coherent source commit after local validation. If parity cannot be demonstrated without changing provider semantics, retry policy, review-scope authority, or #557 workflow behavior, stop and keep the existing three-wrapper runtime rather than forcing consolidation.
