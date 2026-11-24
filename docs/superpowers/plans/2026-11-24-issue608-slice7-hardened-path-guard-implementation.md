# Issue #608 Slice 7 Hardened Path Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans, test-driven-development, verification-before-completion, using-git-worktrees where available. Inline execution with small checkpoints; no autonomous agent dispatch authorized.

**Goal:** Replace the duplicate-function test mirror with direct shipped PowerShell tests and fix the confirmed static Windows containment defect.

**Architecture:** A definitions-only sibling owns the two public functions and one private metadata helper. The resolver enforces collector-root containment, Windows syntax and actual component metadata; the entrypoint validates both outputs before writes and rechecks around literal directory creation. Reuse the existing Python contract and Windows jobs.

**Tech Stack:** Windows pwsh 7, built-in Win32 metadata via lazy Add-Type, Python unittest/subprocess, Windows PowerShell 5.1 parser, pinned PSScriptAnalyzer 1.25.0, GitHub Actions.

**Spec:** Original design at 89d97bbd34662379061a70331c0a25f101af333b plus [approved amendment](../specs/2026-11-24-issue608-slice7-path-containment-amendment.md) at 2800009d42a5356a3e8449f96ff2f9940592e07a; operator approved amendment on 2026-11-24.

**Required companion documents:** Original [implementation plan](2026-11-24-issue608-slice7-shipped-path-guard-implementation.md) at 476c03f39458d405ec668f9c9b3f094948f2d700, original [test appendix](2026-11-24-issue608-slice7-native-test-appendix.md) at 36e3a0092f72d40fcd262df71a589a845599f953, [amended native tests](2026-11-24-issue608-slice7-containment-native-appendix.md) at 7051d9f9491b1baa52ce4f17879b1cf786687d04, and [proposed metadata and write-boundary code](2026-11-24-issue608-slice7-containment-metadata-appendix.md) at 6a8f6b092de727d9b82d8b9397f161d4e5637583. Read actual immutable contents. This plan supersedes conflicting extraction-only steps, exact-body requirement for the resolver, old marker counts and confirmed junction stop gate. Original plan Task 4's generator/validation commands and Task 5's parent acceptance checklist remain required in full.

## Global constraints

- One to three related operations per batch; exact head/blob guards, separate readback/checkpoint, no force push or unauthorized main changes, no blind retries. Prefer authorized isolated native Windows workspace; otherwise existing ChatGPT Exec with separate exact-command approval, current publisher, unique request and actual report/artifact readback.
- Baseline main 80d56fd1d6ef666eefe804be7f38de4742dcec43; original action blob 6ba6bcc1b8f028399fa91d53f24901a7d20ae905. Verified main e0e151273971f673145bfea2a23bcd2109174d1a adds only four diagnostic reports. Preserve docs/history and integrate current main ancestry before edits.
- Run 45387205486, job 138421144320, artifact 14915929174: pwsh 7.6.10, safe/reject controls PASS, actual original resolver accepted junction, no outside report write. Diagnostic execution PASS, containment FAIL; not a fixed defect.
- Preserve public signatures, original legitimate path results and prior rejection diagnostics/order, verbatim Markdown escaping, report schema/encoding, defaults, scan/gate, independent post-hoc validator. Only approved security tightening changes behavior. No workflow/action YAML changes, collector runtime edits, unrelated actions, dependencies, suppressions or policy relaxation. Every governed file at most 15,000 bytes.
- Windows pwsh 7 is supported production behavioral runtime; verify callers. Fail closed on unavailable metadata/fixtures, no Linux substitute, no elevation. Existing ordinary regular files, literal safe names and missing descendants remain valid. No writes through links; metadata-only handle, no outside path or content opened. No race-proof containment claim.
- No Copilot, paid OpenRouter/DCOIR Review, unapproved external Codex comment or autonomous agents. Prog/Adva and independent operator-controlled review, Ready, merge and parent closure remain separate gates. Canonical ircore receipts required.

## Files and interfaces

- Modify .github/actions/run-duplicate-function-check/Invoke-DcoirDuplicateFunctionCheck.ps1 (root initialization, shared helper load, write rechecks).
- Create .github/actions/run-duplicate-function-check/DuplicateFunctionCheck.Paths.ps1 (Resolve-CollectorReportPath([string]$pathValue,[string]$label,[string]$expectedSuffix) -> FullPath/RelativePath or throws; ConvertTo-MarkdownTableCell([object]$value) -> string; private Get-DuplicateReportPathMetadata([string]$fullPath) -> Attributes/NumberOfLinks or genuine absence/throw).
- Create .github/scripts/Test-DuplicateFunctionCheckPaths.ps1 (12 safe, 54 rejected, 9 Markdown plus mandatory fixture/failure controls).
- Modify .github/github_actions/tools/test_duplicate_function_action_contract.py (static contract + fail-closed Windows child).
- Modify .github/actions/run-duplicate-function-check/README.md (supported runtime, direct-test owner, intentional security policy and race limitation).
- Conditional generated files: project_sources/collector/powershell_surface_inventory.json and .md, powershell_analyzer_baseline.json and affected shards. No other generated changes without evidence. Independent .github/github_actions/tools/lib/duplicate_function_report_contract.py stays unchanged (blob 2fcdb9fe151f1e4c35ec215d40511ca92786d7c8).

## Task 1: Re-anchor and capture baseline (no executable changes)

- [ ] Read live #608, AGENTS.md, ircore context, exact main/docs heads and compare. Verify original action/validator and Python blob aa7f52b45ab63411db13a659eb7c973e95f73c71; main drift must be report-only or stop. Verify every live duplicate-action caller uses Windows.
- [ ] After execution approval create isolated refactor/issue608-slice7-shipped-path-guard-20261124 with current main ancestry and exact approved docs, via non-forcing two-parent integration or native merge on isolated branch. Check parents/tree/compare: only approved docs ahead of current main, no source change, reports preserved, no request replay. No protected-main write. Check Windows availability and clean workspace. For ChatGPT Exec, verify agent-ops current publisher/main ancestry, exact-command approval, fresh ID, request/readback, then actual job/artifact; no blind retry.
- [ ] Confirm native fixture capability for missing/ordinary entries, junction, file/directory/dangling symlink and same-volume hardlink. Use amended native appendix's owned scratch fixtures. Parse exact original AST definitions; run each new hostile input separately with original resolver, record acceptance or actual rejection, no outside data reads/writes. Confirmed junction RED already recorded; other alias classes need actual evidence. Capture all safe controls; do not treat unrelated exception as intended rejection or preserve unsafe behavior. Stop if fixture capability or legitimate input behavior is unverified.
- [ ] Capture clean/seeded duplicate/parse-failure original actual report statuses/bytes using original plan Task 4's identical tracked fixture inputs, relative outputs and pwsh version. Keep SHA256 evidence; never run original action on unsafe output paths. Checkpoint before executable edits.

## Task 2: Direct Windows red/green and guard

- [ ] Write native test first: original appendix A + amended native appendix A–C. Run `pwsh -NoProfile -NonInteractive -File .github/scripts/Test-DuplicateFunctionCheckPaths.ps1`; RED must be Missing production path helper, not missing pwsh. Scratch-extract exact original definitions, demonstrate targeted RED for newly prohibited legacy acceptance; keep already-rejected cases' actual evidence. Test no unsafe writes.
- [ ] Extract original definitions to sibling and remove inline definitions. After Get-RepoRelativePath and before first invocation, dot-source:
  
  ```powershell
  . (Join-Path -Path $PSScriptRoot -ChildPath 'DuplicateFunctionCheck.Paths.ps1')
  ```
- [ ] Implement metadata appendix's private function, lazy Win32 bridge and resolver replacement exactly as specified (preserve original lexical checks through suffix). Require actual Windows compilation, error 2 genuine missing-child behavior, correct reparse attributes and hardlink count; stop for evidence/design correction if assumptions fail. No broad catch, no Test-Path false as absence. Root/collector directories exist, only missing descendants permitted. Preserve Markdown function verbatim.
- [ ] Run native command; exit 0 and exact single `DCOIR_DUPLICATE_PATH_TEST_PASS positive=12 rejected=54 markdown=9`. Require fixture verification, uncounted metadata exception/zero-link checks. Scratch mutation tests remove reparse, ambiguous component, hardlink, control and escaping guards separately, require each fails, restore and rerun green. No negative mutation in production. Check definitions-only helper with exactly one public owner each; no side effects at load; check size and syntax.
- [ ] Implement metadata appendix's revalidation at each original directory/write boundary; initial two-path validation remains before scan or writes, literal IO.Directory.CreateDirectory between rechecks, original Set-Content -LiteralPath serialization unchanged. Test actual action hostile/safe pair polarities, outside sentinel unchanged; ordinary file and literal bracket directory positive controls. Commit coherent helper/entrypoint/native suite only with actual native green and write-boundary evidence; read back exact diff.

## Task 3: Driver and README

- [ ] Write original appendix B NativeDriverContractTests first with module-safe patch.object(sys.modules[__name__], field, absent) and amended marker/mocks (positive=12, rejected=54, markdown=9). Run `python .github/github_actions/tools/test_duplicate_function_action_contract.py -v`; RED must concern missing driver.
- [ ] Implement original appendix B run_native_contract() -> str, NATIVE_TEST/HELPER_PATH, new exact PASS_RECORD. Fixed argument list, pwsh -NoProfile -NonInteractive -File, 120-second timeout, no shell interpolation or environment bypass. Missing helper/test/exe, nonzero, timeout, absent/zero/wrong/duplicate marker fail; actual stdout visible. Remove Python behavioral mirrors and function_block assertions; preserve defaults, dispatch, schema, discovery, workflow ordering and distinct-output structural check. Verify public ownership, dot-source ordering and both initial resolutions before writes.
- [ ] Run Python command on Windows, require actual native marker, no native skip; Linux same command and existing `python .github/github_actions/tools/run_pr_draft_fail_fast.py` when available, explicit native skip only. Mocked tests not native proof. README records supported Windows runtime, single owner, literal path/reparse/hardlink policy, direct test command, non-Windows behavior and race limit. Commit/read back.

## Task 4: Parity, generated evidence and qualification

- [ ] Execute original plan Task 4 parity command/fixture instructions in full, using original immutable baseline and hardened candidate on same Windows version and identical fixture source. Require clean/duplicate exit 0, positive duplicate count in seeded fixture, parse failure nonzero with report. Compare JSON/Markdown bytes and hashes; investigate any differences. Independent post-hoc validator and central gate tests retained.
- [ ] Run both hostile/valid output polarities against actual candidate in owned linked-component fixtures; fail before either report write, intended error, unchanged outside sentinel. Test safe existing regular file and literal bracket nested creation and output. No parity for intentionally rejected unsafe paths. No outside target access.
- [ ] Execute original plan Task 4's exact inventory/analyzer/gate commands (canonical generators and verification, pinned analyzer 1.25.0, only matched existing fingerprints, no suppression additions). Include original plan full collector unittest discovery, reusable-contract/modularization/drift audits, workflow inventory --check, actual Windows PS5.1 validation. Verify no unexpected generated outputs, unchanged action/workflow YAML and independent validator, size limits. Commit only affected generated evidence; read back. Record unavailable tests as gaps, not passes.

## Task 5: Draft review, Ready, merge, parent audit

- [ ] Execute original plan Task 5's Draft-first exact-head review and lifecycle sequence; Prog implementation and single Adva pass include new path aliases, root/ancestor/leaf, metadata failure, safe controls, caller rechecks, driver bypass and parity. Disposition findings before independent review; no paid review/Copilot; operator-controlled Codex/Claude only. Exact invoking text approval required. Verify Draft/readback/fast checks, reviewed head and findings.
- [ ] Separate Ready approval and actual native marker/full exact-head PR checks, PS5.1, audit/docs/security/artifacts. Separate merge approval and exact-main postmerge checks. No scope or validation bypass.
- [ ] Execute original plan's nine-criterion parent audit against current main and immutable evidence; record all SHA/run links or gaps. Separate issue closure approval only if all criteria supported.

## Handoff

The amended design is approved; this plan and both exact appendices are documentation only and pending execution approval. Request inline execution approval including scoped .github/actions edits. No independent agent dispatch. Exact Exec command approval remains separate if required. First checkpoint: branch/source integration and native baseline/parity/capability evidence. Do not claim new tests have run or defect fixed.
