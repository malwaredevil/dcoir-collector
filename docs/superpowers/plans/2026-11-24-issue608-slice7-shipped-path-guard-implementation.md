# Issue #608 Slice 7 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans, test-driven-development and verification-before-completion task by task; use using-git-worktrees where available. Steps use checkbox syntax. Inline execution is recommended; no independent agent dispatch authorized.

**Goal:** Replace the duplicate-function Python behavioral mirror with tests of the shipped PowerShell functions.

**Architecture:** Extract the exact two existing definitions into a sibling script dot-sourced by the action and native tests. Reuse the existing Python contract and full Windows CI step; no YAML changes.

**Tech Stack:** Windows pwsh 7, Windows PowerShell 5.1 parser, Python 3.11 unittest/subprocess, GitHub Actions, pinned PSScriptAnalyzer 1.25.0.

**Spec:** [Slice 7 specification](../specs/2026-11-24-issue608-slice7-shipped-path-guard-design.md) at 89d97bbd34662379061a70331c0a25f101af333b, approved 2026-11-24. Baseline main 80d56fd1d6ef666eefe804be7f38de4742dcec43.

**Code appendix:** [Native test and Python driver implementation examples](2026-11-24-issue608-slice7-native-test-appendix.md), commit 36e3a0092f72d40fcd262df71a589a845599f953. Read both documents. This plan does not authorize execution.

## Global constraints

- One to three related operations per batch; exact-head readback; no blind retries, concurrent writers, force push or protected-main mutation.
- Preserve production signatures, messages, behavior, report formats, scan/gate rules and defaults. Keep action.yml/workflow YAML, collector runtime/package and independent duplicate_function_report_contract.py unchanged. No new dependencies, suppression expansion or files above the 15,000-byte source limit.
- Windows native tests must run; Linux Draft skip is not behavioral evidence. A confirmed existing containment defect is a hard stop for separate approval, not a pass.
- No automated Copilot (tokens exhausted), paid OpenRouter/DCOIR Review or external Codex comment/agent without operator authorization. Review, Ready, merge and parent closure remain separate approvals. Record canonical ircore receipts.

## Files and interfaces

- Modify .github/actions/run-duplicate-function-check/Invoke-DcoirDuplicateFunctionCheck.ps1: existing entrypoint and root initialization.
- Create .github/actions/run-duplicate-function-check/DuplicateFunctionCheck.Paths.ps1: definitions only. Resolve-CollectorReportPath([string]$pathValue,[string]$label,[string]$expectedSuffix) returns FullPath and RelativePath or throws. ConvertTo-MarkdownTableCell([object]$value) returns string.
- Create .github/scripts/Test-DuplicateFunctionCheckPaths.ps1: actual native assertions, nonzero on failure and count-bearing success.
- Modify .github/github_actions/tools/test_duplicate_function_action_contract.py: remove mirrors, preserve structural checks, mandatory Windows child test.
- Modify .github/actions/run-duplicate-function-check/README.md: describe direct testing.
- Conditional generated files: project_sources/collector/powershell_surface_inventory.json and .md, powershell_analyzer_baseline.json and affected existing shards. Other evidence only on proven impact.

## Task 1: Preflight and legacy containment probe

- [ ] Read live issue, AGENTS.md, protected main, approved docs tip, work-item context and compare. Create isolated feature branch from approved documentation tip after confirming main ancestry. If main changed, inspect and stop for scope drift. Verify clean worktree and no concurrent writer. No docs-only PR.
- [ ] Verify authorized Windows runtime: pwsh -NoProfile -NonInteractive -Command '$PSVersionTable.PSVersion; $IsWindows'. If unavailable, report gap and obtain a permitted Windows lane before source edits. Do not install dependencies or dispatch agents.
- [ ] Parse immutable original entrypoint (blob 6ba6bcc1b8f028399fa91d53f24901a7d20ae905) using PowerShell Parser.ParseFile; reject errors/missing/duplicate names. For baseline comparison only, write the exact two FunctionDefinitionAst extents verbatim to a disposable definitions-only file. This is not the committed native test target. Set cwd to a GUID-owned synthetic repo with project_sources/collector and a sibling outside directory; initialize the exact original repoRoot expression and dot-source the baseline fixture. Exercise ordinary safe/rejected cases from appendix A.
- [ ] Create a directory junction inside synthetic collector to the owned sibling directory (New-Item -ItemType Junction); inspect literal link and target with Get-Item. Call actual baseline guard for a hypothetical report under the junction; never open/write the returned path. Probe Windows trailing-space/dot segments, device/stream alias classes without opening them. Record lexical return or exception, actual physical target, and safe control. Remove only the owned link itself without recursive traversal before cleaning fixture; restore cwd. Missing fixture capability is an evidence gap. If actual outside-subtree acceptance or dangerous alias is confirmed, STOP before production edits, report exact evidence and request separately approved bounded hardening. No false security PASS or scope widening.
- [ ] Capture immutable baseline report bytes/statuses for Task 4's three scenarios before production changes. Record probe results and checkpoint.

## Task 2: Native red/green extraction

- [ ] Write appendix A's native script to .github/scripts/Test-DuplicateFunctionCheckPaths.ps1. Run pwsh -NoProfile -NonInteractive -File .github/scripts/Test-DuplicateFunctionCheckPaths.ps1 on baseline. Require nonzero with Missing production path helper, not missing runtime.
- [ ] Move the two existing function definitions verbatim to DuplicateFunctionCheck.Paths.ps1. Replace old definitions with this line after Get-RepoRelativePath and before first invocation; preserve all other entrypoint lines.

~~~powershell
. (Join-Path -Path $PSScriptRoot -ChildPath 'DuplicateFunctionCheck.Paths.ps1')
~~~

- [ ] Rerun the native command. Require exit 0 and exact DCOIR_DUPLICATE_PATH_TEST_PASS positive=7 rejected=20 markdown=9. Verify helper contains only two top-level definitions and neither remains in caller. Compare bodies to baseline extents, root setup precedes calls. In scratch copies only, remove a control-character guard and an escaping replacement separately; require each direct test to fail, restore original bytes and require green. No committed negative mutation. Commit coherent helper, entrypoint and native suite only after actual green, then read back exact diff.

## Task 3: Python driver fail-closed red/green

- [ ] Add appendix B's driver tests first, using patch.object(sys.modules[__name__], field, absent) in missing-surface tests; run python .github/github_actions/tools/test_duplicate_function_action_contract.py -v and verify red for missing driver.
- [ ] Implement appendix B's run_native_contract() -> str and NativeWindowsBehaviorTests. Remove normalize_report_path, markdown_table_cell and their mirror assertions. Keep defaults, dispatch, schema, shared discovery, ordering and distinct-output structural checks. Prove helper exists, both functions defined once in action/helper, dot-source before invocation. Missing helper/test/pwsh, timeout, nonzero or absent/zero/duplicate marker fail. No environment bypass.
- [ ] Repeat Python command on Windows; require actual native marker, no native skip, no errors. Run same on Ubuntu if available and python .github/github_actions/tools/run_pr_draft_fail_fast.py; require explicit Windows-native skip and all structural/driver tests pass. Distinguish mocked unit evidence from real execution. Update README with direct-test ownership, Windows command and Ubuntu skip. Commit and read back.

## Task 4: Report parity and generated evidence

- [ ] In isolated disposable fixtures of exact baseline tracked collector inputs and Get-CollectorSourcePartFiles.ps1, run baseline then candidate actual entrypoint with identical inputs, relative paths and pwsh version. Use git archive or isolated worktree; never edit actual collector. Set DUPLICATE_FUNCTION_OUTPUT_JSON=project_sources/collector/powershell_duplicate_function_report.json and DUPLICATE_FUNCTION_OUTPUT_MARKDOWN=project_sources/collector/powershell_duplicate_function_report.md. Invoke pwsh -NoProfile -NonInteractive -File with absolute entrypoint and fixture cwd. For clean case, seeded identical unique synthetic function in two scanned fixture files, and incomplete synthetic function in one file, record exit status, JSON and Markdown bytes before replacing outputs. Require clean/duplicate exit 0, duplicate report count > 0, parse failure nonzero with report; compare baseline and candidate read_bytes and SHA-256. Investigate nondeterministic differences rather than normalize away. Run independent report validator and existing central gate tests with required companion evidence; assert hostile JSON with safe Markdown and converse fails before any report write. Verify distinct default paths.
- [ ] Stage new files for tracked discovery. Run python project_sources/collector/tools/build_powershell_surface_inventory.py --repo-root . ; verify python project_sources/collector/tools/verify_powershell_surface_inventory_ci.py --repo-root . --inventory project_sources/collector/powershell_surface_inventory.json. Inspect new support scripts, exact old/new hash/size/line facts, no unexplained shrink; commit canonical generated outputs only.
- [ ] Use pinned installed analyzer as in action: python project_sources/collector/tools/run_powershell_analyzer.py --repo-root . --json-output project_sources/collector/powershell_analyzer_report.json --markdown-output project_sources/collector/powershell_analyzer_report.md --baseline-json project_sources/collector/powershell_analyzer_baseline.json --fail-on-severity Warning --allow-findings. Review validation and stale fingerprints. Refresh only existing matched rule/path/diagnostic/reason fingerprints; verify affected shard SHA-256/manifest. Fix new warnings without suppression expansion. Run python project_sources/collector/tools/verify_powershell_analyzer_policy_ci.py. No transient reports committed. Reachability scans only manifest runtime source; verify unchanged via existing review-assist gate, regenerate only on canonical evidence.
- [ ] Run python -m unittest discover -s project_sources/collector/tools -p 'test_*.py'; python .github/github_actions/tools/audit_reusable_contracts.py; python .github/github_actions/tools/check_workflow_modularization_contracts.py; python .github/github_actions/tools/check_workflow_consistency_drift.py; python .github/github_actions/tools/build_workflow_inventory.py --check; powershell.exe -NoProfile -File .github/dcoir_review/scripts/validate-windows-powershell-51.ps1. Check exits and generated diffs. Record unavailable tests as gaps. Verify changed source size limits, unchanged YAML and independent validator. Commit only affected generated evidence; read back.

## Task 5: Draft review, exact-head CI, parent acceptance

- [ ] Read back source and commits; create Draft PR only after guarded publication. Verify Draft state, head and fast checks. Prog/Adva cover novel hostile and safe controls, malformed inputs, containment, driver bypass, parity and cross-file wiring; fix/re-review findings. Record native evidence or gap. Operator-controlled independent Codex/Claude review/fix only; obtain exact-text approval before any invoking comment. No paid review/Copilot. Verify review findings and reviewed head, distinguish formal approval from comments.
- [ ] Stop for explicit Ready approval. Require real Windows native counts, all exact-head full PR checks, central gate/report artifacts, Windows PS5.1, Workflow Audit, docs and security evidence. Distinguish skipped/disabled. Return to Draft only with approval if fixes needed. Stop for separate squash merge approval; guard exact head. Read merged main SHA and all postmerge workflow/job outcomes; record receipts.
- [ ] Audit all nine #608 criteria: input removal and seeded blocking; action callers/count; shared scan/harness ownership; missing-manifest failure and expanded profile parity; one workflow iterator and size; deleted wrapper and byte parity; actual Windows hostile test; regenerated inventory and all audit commands. Use live git grep, canonical tests and immutable prior evidence, documenting each SHA/run/link or gap. Seek separate parent closure approval only after every criterion supported.

## Coverage and approval

Task 1 covers containment and baseline; Tasks 2–3 direct tests and driver failure controls; Task 4 parity and generated evidence; Task 5 review, CI and parent acceptance. Appendix supplies exact native case tables and driver code. This is documentation only. Next: operator approval of inline plan execution including scoped .github/actions changes. First execution checkpoint is the baseline Windows probe, not a production edit.
