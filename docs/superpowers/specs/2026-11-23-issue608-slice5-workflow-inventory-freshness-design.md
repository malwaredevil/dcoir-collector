# Issue #608, Slice 5: Authoritative Workflow Inventory Freshness

**Design status:** Conceptual design approved by operator on November 23, 2026, including one workflow YAML edit in principle. This document is for separate written-spec review. Neither the workflow edit nor code implementation is authorized merely by approving or committing this design.

**Parent:** https://github.com/malwaredevil/dcoir-collector/issues/608

**Verified baseline:** Protected main at 64fb4cc989981bc1088167f54ec3f0f274f46d65, incorporating merged Slice 4 PR #670. Exact-main Main Push Validation #45183721890, Workflow Audit #45183721881 and Documentation Quality #45183721820 all succeeded.

## 1. Problem and updated source audit

Issue #608 originally lists Slice 5 as creating one workflow-file discovery owner, one workflow count owner, a freshness-only inventory check, and a smaller drift-checking tool. That description reflects an older tree. As of the verified main commit:

- The canonical workflow/action discovery implementation already exists at .github/github_actions/tools/lib/workflow_files.py (2,685 bytes). Drift audit, action-version audit, inventory, contract checks and reusable-workflow audits delegate to it. Local compatibility partials are not duplicate implementations.
- The drift audit at .github/github_actions/tools/check_workflow_consistency_drift.py is 14,999 bytes, below the 15,000-byte limit. The old 28,655-byte figure is stale.
- The contract registry at .github/github_actions/workflow_modularization_contracts.json already owns declared primary workflow and composite-action counts. Shared count checks and adversarial regression tests reject contradictory observed counts.
- The inventory generation/check implementation already exists at .github/github_actions/tools/build_workflow_inventory.py, using lib/workflow_inventory_core.py and lib/workflow_inventory_outputs.py. Its --check mode compares both generated artifacts without writing them. Existing test_workflow_inventory_freshness.py verifies positive controls, missing files, stale contents and count changes.
- An actionable integration flaw remains in .github/workflows/reusable-workflow-maintenance-audit.yml. The current lines 52 through 71 execute the writer command in a step named Regenerate workflow inventory *before* the step named Check workflow inventory freshness invokes the reader command with --check. The subsequent git diff --quiet is a secondary guard but cannot replace inspecting the original checked-out artifacts.

The first step overwrites missing or stale checkout artifacts before the freshness operation examines them. The later tracked-file git diff catches many stale tracked-output mutations, so this flaw does not imply every stale file presently passes. An untracked regenerated file following a committed deletion is one distinct bypass scenario for a git diff --quiet-only guard.

**Required outcome:** A workflow maintenance audit must fail closed when either original checked-out inventory artifact is missing, stale or inconsistent with source. CI must not silently regenerate the artifact before the check. Valid artifacts must continue to pass.

## 2. Design choices and decision

**Chosen: a read-only check, without a preceding write.** Delete the existing Regenerate workflow inventory step from the reusable maintenance-audit workflow. Retain the Check workflow inventory freshness step and its invocation of the existing builder with --check. Retain its existing git diff --quiet protection to detect unintended tracked-file changes by other steps. Do not add dependencies or duplicate any Python inventory logic. Maintainers can still deliberately run the same builder *without* --check and commit the resulting JSON/Markdown before pushing changes.

**Alternative: check, then regenerate.** Running --check before write can catch stale artifacts, but a later write in audit CI serves no purpose and risks dirtying the runner workspace. Rejected.

**Alternative: Python tests only.** Leave workflow YAML untouched and improve isolated freshness tests. This does not ensure the actual audit checks the files that were checked out. Rejected.

The chosen design is an explicit amendment to Issue #608's older assertion that Slice 5 needs no workflow YAML edit. It requires separate operator authorization for the actual change before implementation.

## 3. Targeted file and ownership changes

### Proposed single workflow edit

The only workflow file proposed for modification is .github/workflows/reusable-workflow-maintenance-audit.yml.

Remove the entire step named Regenerate workflow inventory, currently lines 52–56, which invokes:

~~~bash
python3 .github/github_actions/tools/build_workflow_inventory.py
~~~

Keep the next step, Check workflow inventory freshness, directly after Check workflow consistency drift. Its existing command must remain:

~~~bash
python3 .github/github_actions/tools/build_workflow_inventory.py --check
~~~

Retain the existing following git diff --quiet check over:

- .github/github_actions/workflow_inventory.json
- .github/github_actions/workflow_inventory.md

Do not move freshness behind any new mutating step. Do not change audit triggers, permissions, concurrency, environment setup, action-version check, contract checks, artifact upload, report content, or dependency pins.

If modifying the workflow changes the generated inventory, regenerate the two outputs deliberately on the *feature branch*, inspect exact before/after data and commit the necessary changed files. Never regenerate as part of CI's checking step.

### Preserved Python interfaces

There is no new discovery API. Keep:

- lib/workflow_files.py as sole workflow/action file discovery implementation, including original ordering, reusable filtering and action metadata semantics.
- workflow_modularization_contracts.json as declared workflow/composite-action count registry; existing contract rules and tests enforce mismatches.
- lib/workflow_inventory_core.py as inventory construction owner.
- lib/workflow_inventory_outputs.py as JSON/Markdown formatter, writer and freshness comparator.
- build_workflow_inventory.py as the only intentional inventory-generation CLI, with --check remaining read-only.
- check_workflow_consistency_drift.py unchanged at 14,999 bytes and with identical current diagnostic output. No new owner is needed.

If tests demonstrate an unavoidable drift-tool change, the implementation must stop, justify a limited decomposition into a cohesive helper, and demonstrate parity before implementation. This design does not grant a license to expand its size or refactor unrelated audit rules.

## 4. Exact acceptance and TDD evidence

Extend the existing .github/github_actions/tools/test_workflow_inventory_freshness.py with tests for the actual shipped maintenance audit wiring, rather than create a second implementation or a mirror of the inventory checker.

The tests should establish:

1. The shipped audit has exactly one active builder invocation and it includes --check; no write-mode inventory generation executes earlier. Guard against false matches on comments, echo messages and documentation strings.
2. The freshness check remains ordered after the drift audit and before modularization and reusable contract checks. The existing git diff guard remains in the audit.
3. Both correctly generated files pass the shipped --check command with return code zero and unchanged output bytes.
4. Missing JSON, missing Markdown and missing both files each cause shipped --check to return nonzero, with an error that mentions the absent output. No missing artifact is recreated.
5. Mutating either output causes fail-closed stale diagnostics and no mutation by --check. Mutating a modeled source count without regenerating outputs also fails. Preserve existing fixture tests.
6. A clean safe control passes. An explicit maintainer-run generation followed by --check passes. No test can pass merely because it creates correct output before it examines an intentionally missing checkout artifact.
7. A disposable checkout with a deliberately removed output must fail the maintenance-audit freshness step before any write. Contrast with the originally shipped write-first logic to demonstrate that the integration change is meaningful.

Required existing direct commands, using the same checked-out commit and without modifying original sources:

~~~bash
python .github/github_actions/tools/test_workflow_inventory_freshness.py -v
python .github/github_actions/tools/build_workflow_inventory.py --check
python .github/github_actions/tools/check_workflow_modularization_contracts.py
python .github/github_actions/tools/audit_reusable_contracts.py
python .github/github_actions/tools/check_workflow_consistency_drift.py
python .github/github_actions/tools/check_workflow_action_versions.py
~~~

Before any Ready claim, validate current-tree and seeded-drift findings against baseline. Require exact-head GitHub Actions Workflow Audit execution of the changed YAML as well as any other required PR validation. A local unit-test pass is not a substitute for workflow-run evidence.

The testing change must be discoverable by the current CI test runner; use the existing inventory test module already included by the modularization contract audit. Do not broaden the CI workflow to add a new redundant runner merely to execute these tests.

## 5. Security, failure handling, and rollback

- The audit is read-only and fail-closed on source/artifact mismatch; never repair stale outputs automatically in CI.
- Preserve required paths, policy thresholds, collector/Gemini/OpenAI build outputs, existing reports, workflow triggers, PSScriptAnalyzer and all current security gates.
- On a missing/stale file, report the affected generated artifact and advise deliberate maintainer regeneration. Fail nonzero without rewriting the checkout artifact.
- On a legitimate new workflow count or source change, regenerate both outputs on the feature branch, inspect their changes and commit them before rerunning the check. A formatter-only difference must be justified, not hidden.
- On any regression or workflow validation failure, keep the PR Draft for repair or revert the exact scoped change on its branch. No direct protected-main mutation, bypassed validation or unsafe automatic retries.
- Preserve anti-freeze batches: one to three operations, explicit main SHA, guarded source writes and GitHub source/CI readback.

**Review controls:** The operator approved the conceptual design and one workflow edit *in principle*, not source implementation. After the written spec is approved, use superpowers:writing-plans and obtain separate plan execution/workflow-edit approval. Copilot and external Codex requests are operator-controlled; paid OpenRouter/DCOIR Review remains opted out. Ready, merge and parent closure are separate operator gates. Prog implementation and internal Adva hostile review precede readiness claims. Do not edit unrelated PRs.

## 6. Done criteria and review gate

Slice 5 is ready for eventual merge consideration only when the actual workflow reads committed inventory *before* any write, missing/stale/negative tests fail closed, safe controls pass, shared discovery/count owners remain unchanged, audit diagnostics preserve their current behavior, and an exact-head Workflow Audit and required PR validation have succeeded.

**Written-spec approval gate:** This document is the approved conceptual design written into a GitHub spec. The operator must separately approve the **committed written specification** before implementation planning or functional workflow/test edits. This specification is documentation only.

**Remaining Issue #608 count:** Seven proposed slices total, with Slices 1 through 4 merged. Slices 5, 6 and 7 remain, approximately three more implementation PRs, subject to current tree evidence. Parent Issue #608 stays open.
