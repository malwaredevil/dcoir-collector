# Issue #608 Slice 3: Authoritative Collector Part Discovery

**Date:** 2026-11-19
**Status:** Operator separately approved the conceptual design/workflow scope and reviewed the written specification on 2026-11-19. Implementation is in a Draft PR; no Ready, review-request, or merge authorization is implied.
**Issue:** https://github.com/malwaredevil/dcoir-collector/issues/608
**Base commit:** `5ecd3d11cd37c5de205573f5cf70417155e6d79e` (Slice 2 PR #655 merged; five main-push checks passed).

## Goal and invariants

Use one fail-closed, dot-sourced PowerShell discovery helper for the duplicate-function checker and PowerShell syntax validator. The authoritative order and membership come only from the literal `$collectorPartFiles` assignment in `project_sources/collector/source/DCOIR_Collector.ps1`, extracted via PowerShell AST **without invoking the collector**. Existing successful scans, findings, reports, analyzer policy, and packaging outputs must remain equivalent. Avoid redundant assembly of the documentation-quality harness within the same validation job.

At the base commit, the runtime wrapper contains **43 load-list entries** and throws if a listed part is absent. The parts folder contains **44 `.ps1` files**: those 43 plus `DCOIR_Collector.02_Baseline_Collection_And_Reports.ps1`, a checked-in **non-executable compatibility marker** that existing validation scans still include. The duplicate-function action uses `Get-ChildItem -Recurse`, while the syntax action uses a nonrecursive glob; they disagree with the runtime load list and lack an explicit marker exception. The current `run-psscriptanalyzer` action uses the **Python inventory-backed analyzer**, not the previously removed `Invoke-DcoirPSScriptAnalyzer.ps1`; do not recreate that removed PowerShell wrapper.

## Options considered

1. **Selected: single AST-backed PowerShell helper.** Directly matches what the runtime loads without running it, supports hostile-input tests, and removes two independent glob-based discovery rules. A small shared helper is an additional maintained file but becomes the sole discovery implementation for its PowerShell consumers.
2. **Use the generated Python inventory as the only discovery source.** Simpler for Python tooling but not an independent check of the real runtime load list; a stale inventory could hide omissions. Keep it for analyzer targeting, and cross-check it against the AST helper instead.
3. **Retain and normalize globbing.** Smallest edit but still accepts unlisted files and can miss a required part. Rejected.

## Source changes

### 1. Shared AST discovery contract

Create `.github/scripts/Get-CollectorSourcePartFiles.ps1`, dot-sourceable without side effects. Its exported `Get-CollectorSourcePartFiles` function accepts an explicit repository root and optionally a wrapper path for negative tests. It must:

- Resolve the canonical runtime wrapper **within** the repository, parse it with `[System.Management.Automation.Language.Parser]::ParseFile`, and throw on any parse error.
- Find exactly one top-level assignment to variable `collectorPartFiles`; require a PowerShell `@(...)` array containing only static, nonempty quoted string literals. Reject missing or duplicate assignments and computed elements (`$variable`, calls, subexpressions).
- Require each element to be a *bare filename* (no absolute paths, separators, `..`, drive prefixes, or control characters), ending in `.ps1`; reject duplicate names case-insensitively.
- Resolve each name against `project_sources/collector/source/parts`, verify it is a direct child inside that directory and a regular file. Missing/symlink-escape paths fail closed.
- Expose the **43 runtime-loaded part paths** in load order and a validation-scan set that additionally includes the one explicit non-runtime compatibility marker. Keep the marker excluded from runtime assembly but included in the duplicate-function and syntax scans to preserve the clean-tree **44-file** scan set. No execution, dot-sourcing of runtime parts, wildcard expansion of list elements, or evaluation of collector code is permitted.
- Detect unlisted directly located `*.ps1` source parts and unexpected nested source parts as a fail-closed mismatch **except** the single explicitly named compatibility marker above. Validate that marker is a regular file within the same root; reject additional marker-like names. The explicit exception preserves the known-good 44-file scan set without broadening runtime load.

### 2. Replace consumer-local discovery

- `.github/actions/run-duplicate-function-check/Invoke-DcoirDuplicateFunctionCheck.ps1`: dot-source the shared helper, retain the wrapper as a scanned target, replace recursive `Get-ChildItem` logic with the authoritative **validation-scan set** (43 runtime parts plus one compatibility marker). Preserve deterministic names, path normalization, parse/finding shape, report schema, and central-gate responsibilities.
- `.github/actions/validate-powershell-syntax/action.yml`: within the existing PowerShell validator, when `include-collector-parts` is true, invoke the same helper's **validation-scan set** (44 files, including marker). Do not skip validation just because the parts directory is absent. Preserve unrelated input paths, harness-fragment handling, PowerShell 5.1 compatibility, and `require-files` behavior.
- `.github/actions/run-psscriptanalyzer/action.yml` and the Python analyzer stay on their existing owner/target selection. Add parity tests that compare AST-list paths against inventory coverage; **do not** add a second analyzer discovery implementation or weaken the inventory freshness check.

### 3. Harness assembly ownership

- The initially reviewed callers `.github/workflows/reusable-validate-on-pr.yml`, `reusable-validate-on-push.yml`, and `reusable-collector-documentation-quality.yml` already invoke `.github/actions/assemble-collector-harness` before documentation quality. Canonical source inspection also identified **two additional callers**: `reusable-collector-validation.yml` (assembly was conditional on unrelated harness flags) and `reusable-collector-runtime-package-build.yml` (no preceding assembler). Preserve both flows by extending the former assembler condition to `run_documentation_quality` and adding one assembly step to the latter before documentation quality.
- Remove unconditional reassembly inside `.github/actions/run-collector-documentation-quality/action.yml`. Instead **require** the generated harness at its established canonical output path; error if absent (do not silently regenerate). Check the ordering and conditional execution for **all five** callers before the edit. Preserve standalone documentation-quality and runtime-package-build workflow behavior, report artifacts, and validator inputs.
- Avoid changing harness concatenation, generated content, collector source, or package outputs.

## Validation and test design (Draft first)

- Baseline: capture the exact 43-part ordered source list, current inventory selected paths, and duplicate-function/docs report outputs for comparison; verify current main-push gate success.
- TDD red/green: test a missing listed source part, a duplicate entry, a nonliteral expression, traversal, a symlink escape, an extra unlisted root/nested part, and a malformed wrapper AST. Each must fail; an ordinary literal list matching existing files must pass without executing any runtime statements.
- Test both consumers against the helper, including the `include-collector-parts=false` control; a clean checkout must select the **same 44 validation part paths** (43 runtime-loaded plus one compatibility marker), with the runtime wrapper included where originally scanned. Separately assert that only the 43 literal AST paths are runtime-loaded. Run hostile tests against the **shipped PowerShell helper** on Windows, not a Python-only behavioral mirror.
- Verify preassembled harness is reused and missing harness fails the docs action; compare generated harness hashes and documentation-quality JSON/Markdown or equivalently normalized reports to baseline. Check all **five** caller workflows invoke the assembler before the documentation action, including the conditional `run_documentation_quality` selection.
- Regenerate and check repository-owned workflow/action and PowerShell inventory JSON/Markdown as required; **do not** edit inventory facts by hand. Run Workflow Audit, Python tests, PowerShell syntax, analyzer/static gate, docs quality and relevant Windows suites on the same exact head.
- Internally perform Prog implementation and independent Adva-style hostile review with positive and negative controls, document valid findings and fixes. Create only a **Draft PR**. The operator controls requests for Copilot or other independent review. Separate approvals are mandatory for Ready, merge and Issue #608 closure; paid OpenRouter/DCOIR Review remains opted out.

## Rollback and boundaries

A failed inventory parity, report difference, missing required part or invalid AST must stop the Draft PR until fixed; do not bypass required CI. Roll back only the Slice 3 branch if parity cannot be established. Do not touch governance PR #654, parent issue status, unrelated modules, analyzer thresholds, static gate criteria, required-surface profiles, or package/runtime output.

## Written-spec review gate

The operator approved the conceptual design and workflow/action-change scope on 2026-11-19, then separately **approved the written specification** in the next chat turn. During implementation, source readback identified the two additional documentation-quality callers above; those minimal ordering/precondition changes are required to preserve existing behavior. Independent Copilot review, Ready transition, merge and parent issue closure each still require separate operator authorization.
