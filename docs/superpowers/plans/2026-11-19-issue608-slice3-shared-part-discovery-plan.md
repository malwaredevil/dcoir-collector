# Issue #608 Slice 3: Shared Collector Part Discovery Implementation Plan

> For agentic workers: Execute these small tasks sequentially with test-first red/green evidence and readback checkpoints. Use the approved branch and the Draft-first PR lifecycle.

**Goal:** Remove conflicting PowerShell glob discovery rules, follow the actual collector runtime part list without executing the collector, retain all 44 validation-scanned files, and avoid unnecessary second harness assembly.

**Architecture:** One dot-sourced .github/scripts/Get-CollectorSourcePartFiles.ps1 exports a function returning the 43 runtime-loaded files (in load order) or a 44-file validation scan set containing the explicit compatibility marker. The duplicate-function and syntax actions invoke it; the Python inventory/analyzer remains canonical and independent. Documentation quality consumes the harness assembled by its workflow caller.

**Tech Stack:** Windows PowerShell 5.1, pwsh, PowerShell AST, GitHub Actions YAML, Python 3.11, GitHub Contents API.

**Spec:** docs/superpowers/specs/2026-11-19-issue608-slice3-shared-part-discovery-design.md (operator reviewed and approved 2026-11-19).

## Global Constraints

- Work only on branch refactor/issue608-slice3-shared-part-discovery-20261119 from validated base commit 5ecd3d11cd37c5de205573f5cf70417155e6d79e.
- At baseline project_sources/collector/source/DCOIR_Collector.ps1 has 43 literal collectorPartFiles entries, while source/parts has 44 ps1 files including the non-runtime compatibility marker DCOIR_Collector.02_Baseline_Collection_And_Reports.ps1.
- Scan **all 44** validation part files but **only 43** runtime entries; no runtime source execution in discovery.
- Keep the existing PSScriptAnalyzer Python inventory owner, static gate thresholds, report contracts, required surfaces, packaging outputs, and fail-closed behavior unchanged.
- Never touch PR #654, merge, Ready transition, parent Issue #608 closure, or request Copilot/paid OpenRouter/external Codex review without a separate operator approval.
- Stop on any validation failure; no blind reruns or green claims without exact-head logs. Work in 1 to 3 related tool operations per batch.

---

### Task 1: Baseline, executable behavioral tests, and red evidence

**Files**
- Create: .github/scripts/tests/Test-CollectorSourcePartFiles.ps1
- Read: project_sources/collector/source/DCOIR_Collector.ps1, project_sources/collector/powershell_surface_inventory.json, .github/actions/run-duplicate-function-check/Invoke-DcoirDuplicateFunctionCheck.ps1, .github/actions/validate-powershell-syntax/action.yml
- Optional CI wiring: .github/workflows/reusable-windows-powershell-51.yml (if needed to execute the shipped PowerShell tests on GitHub Actions).

**Interfaces**
- Consumes: repository root and optional temporary synthetic wrapper/parts fixtures.
- Produces: a shipped-function behavior test executable with powershell.exe -NoProfile -File and pwsh -NoProfile -File.

- [ ] Step 1. Capture the exact ordered runtime names and complete 44-file scan list (including the explicit compatibility marker). Capture existing report schemas and successful main-push validation run 44487022356 as baseline evidence.
- [ ] Step 2. Write a test that dot-sources .github/scripts/Get-CollectorSourcePartFiles.ps1 and calls Get-CollectorSourcePartFiles -RepositoryRoot $root. Assert the result is 43 items in the original runtime order, all exist, and the wrapper is not executed. Add a second call with -ForValidation that returns 44 paths, including the compatibility marker exactly once.
- [ ] Step 3. Use a temporary repository-like fixture containing a literal collectorPartFiles assignment, a parts directory, two files and the named compatibility marker. Add data-driven tests for duplicate case-insensitive names, missing part, unexpected extra ps1 file at root, unexpected nested ps1 file, nonliteral interpolation, command expressions, missing/duplicate assignments, traversal, absolute/drive paths, invalid extension, malformed PowerShell, and symlink/reparse point where supported. Each rejected case must throw.
- [ ] Step 4. Run on Windows PowerShell 5.1 or pwsh. At this point the script under test does not yet exist; require a **RED** result with the expected missing-helper/function failure, not a malformed-test error. If there is no executable Windows lane, commit test-first and wire it into the existing Windows CI path to observe the red check before creating production code.
- [ ] Step 5. Commit and independently read back the test file and changed-file list; document the red run ID/logs before advancing.

Test harness skeleton:

~~~powershell
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
. (Join-Path $repo '.github/scripts/Get-CollectorSourcePartFiles.ps1')
$runtime = @(Get-CollectorSourcePartFiles -RepositoryRoot $repo)
$scan = @(Get-CollectorSourcePartFiles -RepositoryRoot $repo -ForValidation)
if ($runtime.Count -ne 43 -or $scan.Count -ne 44) {
    throw "Unexpected part counts: runtime=$($runtime.Count) scan=$($scan.Count)"
}
if (@($scan | Where-Object { $_ -like '*DCOIR_Collector.02_Baseline_Collection_And_Reports.ps1' }).Count -ne 1) {
    throw 'The validation-only compatibility marker is missing.'
}
~~~

### Task 2: Minimal fail-closed AST discovery implementation

**Files**
- Create: .github/scripts/Get-CollectorSourcePartFiles.ps1
- Test: .github/scripts/tests/Test-CollectorSourcePartFiles.ps1

**Interfaces**
- Function: Get-CollectorSourcePartFiles -RepositoryRoot [string] -WrapperPath [optional string] -ForValidation [switch]
- Output: absolute path strings; 43 runtime paths in load order, or 44 scan paths with the compatibility marker.
- Failure: throws on missing/malformed/unsafe wrapper, invalid AST expression, absent/duplicate part or unexpected unlisted source file.

- [ ] Step 1. Parse the runtime wrapper using [System.Management.Automation.Language.Parser]::ParseFile and throw on parse errors. Inspect top-level assignment AST nodes and require **exactly one** assignment to collectorPartFiles with an ArrayExpressionAst containing only static StringConstantExpressionAst entries. Do not use Invoke-Expression, SafeGetValue on arbitrary AST nodes, or dot-source runtime code.
- [ ] Step 2. Validate bare ps1 names, no parent/path separators/control characters/drive roots; reject duplicates case-insensitively. Resolve repository root and parts root as real directories; reject reparse point entry files and any path resolving outside. Fail on missing entries.
- [ ] Step 3. Enumerate direct child/nested ps1 files **only for consistency checking**, not for choosing runtime membership. Reject all unlisted files except the one explicit non-runtime compatibility marker, which must exist as a safe regular file. Return the validation scan set in deterministic filename order; preserve the runtime output order separately.
- [ ] Step 4. Run red/green PowerShell tests from Task 1 on Windows. Verify the known-good fixture and repository source set pass and each hostile variant fails closed. Correct implementation bugs before other consumers change.
- [ ] Step 5. Commit and read back helper/test contents and changed-file list.

Core AST contract (not an instruction to execute collector code):

~~~powershell
$tokens = $null
$parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    $wrapperFullPath, [ref]$tokens, [ref]$parseErrors
)
if ($parseErrors.Count -gt 0) {
    throw 'Collector wrapper has PowerShell parse errors.'
}
# Inspect AST AssignmentStatementAst/ArrayExpressionAst and
# StringConstantExpressionAst nodes only; reject everything dynamic.
~~~

### Task 3: Replace consumer-local part discovery without changing report contracts

**Files**
- Modify: .github/actions/run-duplicate-function-check/Invoke-DcoirDuplicateFunctionCheck.ps1
- Modify: .github/actions/validate-powershell-syntax/action.yml
- Test: .github/scripts/tests/Test-CollectorSourcePartFiles.ps1, .github/github_actions/tools/test_duplicate_function_action_contract.py

**Interfaces**
- Existing duplicate-function checker returns unchanged JSON/Markdown schemas and central-gate report-only behavior.
- Existing syntax action honors paths, include-collector-parts, require-files, use-windows-powershell, and harness-fragment special handling.

- [ ] Step 1. Add failing consumer contract tests: no remaining independent Get-ChildItem part-discovery blocks; both consumers dot-source the shared helper; scan paths include exactly the 44 validation files plus the wrapper where applicable; include-collector-parts=false leaves the syntax action's normal tracked-file behavior intact.
- [ ] Step 2. Run test(s) RED against the existing action source; assert the intended negative is discovery still being globbed rather than a test-harness crash.
- [ ] Step 3. In the duplicate-function checker replace only lines selecting part files (currently around 60-75), preserving all later AST parsing, sorting, report encoding, finding schema and path guards.
- [ ] Step 4. In the syntax action replace the optional part-directory Get-ChildItem branch with a call to the same helper, ensuring the helper runs inside the PowerShell 5.1 or pwsh validator process so quoting and env forwarding remain unchanged.
- [ ] Step 5. Run positive and hostile consumer tests, parse/syntax tests and static reports GREEN, compare output rows and schema with baseline, then commit/read back both files.

Consumer call shape:

~~~powershell
. (Join-Path (Get-Location).Path '.github/scripts/Get-CollectorSourcePartFiles.ps1')
$selectedPartPaths = @(Get-CollectorSourcePartFiles -RepositoryRoot (Get-Location).Path -ForValidation)
# Append selectedPartPaths to the already existing scanner target collection.
~~~

### Task 4: Reuse the preassembled documentation harness

**Files**
- Modify: .github/actions/run-collector-documentation-quality/action.yml
- Test: .github/github_actions/tools/test_report_only_static_gate_actions.py or a dedicated adjacent test
- Read: .github/workflows/reusable-validate-on-pr.yml, reusable-validate-on-push.yml, reusable-collector-documentation-quality.yml

- [ ] Step 1. Add a failing contract test that finds the existing repeated assembler invocation inside the documentation-quality action, and asserts all three caller workflows first invoke assemble-collector-harness.
- [ ] Step 2. Run RED. Change the action to check the existing canonical generated harness path using Test-Path -PathType Leaf. Throw a missing-harness error rather than executing the assembler. Keep step names, input/output paths, validator invocation, errors and artifact behavior consistent.
- [ ] Step 3. Run positive prebuilt-harness control and negative missing-harness control on Windows; confirm identical canonical generated-harness SHA and unchanged normalized documentation-quality report output.
- [ ] Step 4. Run GREEN tests, then commit and read back exact changed files.

Minimal action step:

~~~powershell
$generatedHarnessPath = Join-Path (Get-Location) 'project_sources/collector/harness/run_DCOIR_Tests.generated.ps1'
if (-not (Test-Path -LiteralPath $generatedHarnessPath -PathType Leaf)) {
    throw "Preassembled collector harness missing: $generatedHarnessPath"
}
~~~

### Task 5: Inventory regeneration, hostile review and Draft PR

**Files**
- Regenerate with existing repository tooling, when required: .github/github_actions/workflow_inventory.json, workflow_inventory.md, project_sources/collector/powershell_surface_inventory.json and markdown.
- Existing tests and CI (do not weaken): .github/github_actions/tools/test_workflow_composite_action_count.py, tools/build_workflow_inventory.py --check, tools/verify_powershell_surface_inventory_ci.py, validation/static gate.
- Draft PR from branch refactor/issue608-slice3-shared-part-discovery-20261119 to main.

- [ ] Step 1. Determine which inventory files changed and run the **canonical generators**, not manual fact replacements. Verify generated JSON/Markdown consistency and actual inventory sources for both new helper and tests.
- [ ] Step 2. Run targeted source tests and full applicable Windows/Python tools: audit_reusable_contracts.py, check_workflow_modularization_contracts.py, check_workflow_consistency_drift.py, collector syntax, PowerShell analyzer/static gate, documentation-quality tests, shared runtime and no-overrides regression checks.
- [ ] Step 3. Run a distinct **Adva adversarial pass** against shipped PowerShell: an injected runtime statement that must never execute, malicious filenames, duplicate/missing/unlisted entries, reparse/symlink escape, missing harness, compatibility-marker absence, line-encoding variants, and safe controls. Fix valid findings and repeat until clear; record limitations if Windows executor is unavailable.
- [ ] Step 4. Check exact current branch head, changed-file list, all CI statuses and zero security gate relaxations. Open a **Draft PR** only after a verified small source update and initial validation evidence. Keep source/report scope accurate in PR body with issue link and known gaps.
- [ ] Step 5. Hand off Draft PR to operator for manually initiated Copilot review/fix cycle. **Do not** request Copilot, OpenRouter/DCOIR Review, external Codex, mark Ready, merge, or close Issue #608 without their respective explicit approvals.

## Stop conditions and review handoff

Do not claim that tests passed without a real test run on the exact branch head. Do not claim report parity without comparing existing and changed output facts. The user approved written design and governed workflow/action scope; this does not authorize Ready, independent review requests, merge, or closing Issue #608. Governance PR #654 must remain untouched.
