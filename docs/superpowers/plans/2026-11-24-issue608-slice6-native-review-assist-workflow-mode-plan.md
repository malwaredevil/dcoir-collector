# Issue #608 Slice 6: Native Review-Assist Workflow Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Replace the redundant workflow review-assist metadata wrapper with a single native CLI mode, preserving byte-identical JSON and Markdown output, safe paths, local defaults and fail-closed validation.

**Architecture:** The report generator builds final artifact metadata before rendering/schema validation, then its existing writer emits both final files. The PowerShell action invokes that CLI once and retains the existing function-reachability, artifact presence, metadata and validation gates. Frozen-timestamp full-byte golden fixtures from the legacy wrapper prove compatibility.

**Tech Stack:** Python 3 standard library argparse, unittest, pathlib and mock; Windows PowerShell 5.1 and pwsh; existing GitHub Actions and repository contract tests.

**Spec:** docs/superpowers/specs/2026-11-24-issue608-slice6-native-review-assist-workflow-mode-design.md, operator-approved design committed at 9280cfc1e8fa75f5fd2ffaf53dc3887583668910.

## Global constraints

- **Approval:** The operator's latest Yes approves the committed written specification and authorizes creation of this planning document ONLY. It does not authorize feature source/test edits, deleting the wrapper, changes under .github/actions, opening a Draft PR or requesting reviewers. Obtain explicit separate approval of executing this plan, including the identified .github/actions edits. Reviewer, Ready, merge and closing Issue #608 are further separate gates.
- **Base:** Protected main at planning SHA c8c76c5971b433c4c549c5c1d92740d085ab98a8, following merged Slice 5 PR #671. Re-read actual main at execution; compare the docs branch against it before source writes. Issue #608 remains OPEN for Slices 6 and 7.
- **Status:** Exact-main Main Push Validation #45346645550 succeeded with 42/42 steps; Windows PowerShell 5.1 #45346645647 passed 12/12; Workflow Audit #45346645540 passed.
- **Mode:** --artifact-behavior choices none (default) and caller_uploaded_artifact; optional --retention-scope only with workflow mode; reject blank, newline or control characters. Canonical workflow default: workflow-generated report artifacts uploaded by the caller workflow; retention is configured by the caller upload-artifact step, not by #268.
- **Parity:** Both full JSON and Markdown byte streams must equal legacy baseline at identical source inputs, frozen generated_at_utc, final repo-relative paths, behavior and retention; no field normalization or golden rewriting to achieve green. Default local reports and --no-write remain unchanged.
- **Security:** Keep existing resolve_report_output_path checks for traversal, absolute/outside root, unsafe suffix, reserved path, alias and symlink escape; keep schema and Markdown validation, source-report errors, failed-output persistence and PowerShell failure gates. Do not change analyzer thresholds or collector/Gemini/OpenAI package contents.
- **Source policy:** Keep each source file at or below 15,000 bytes. Current renderer is 13,932 bytes, builder 10,699, existing report tests 12,121, safety tests 10,617. Put workflow-mode tests in a new focused module rather than overgrow existing tests.
- **Governance:** Use 1-3 tool operations per anti-freeze batch with exact SHA/branch checks and independent GitHub readback. Prog implementation, independent internal Adva hostile controls, Draft-first CI, operator-controlled Copilot/external Codex, separate Ready and merge. No paid OpenRouter/DCOIR Review.

## File map

- Modify project_sources/collector/tools/run_powershell_review_assist_report.py: CLI flags, input validation and main entrypoint.
- Modify project_sources/collector/tools/powershell_review_assist_builder.py: define workflow_artifact_contract(args, repo_root) and inject validated contract before existing Markdown/schema parity checks.
- Modify project_sources/collector/tools/powershell_review_assist_rendering.py: one workflow retention constant, canonical artifact contract, conditional Workflow behavior Markdown line.
- Read without modification project_sources/collector/tools/powershell_review_assist_sources.py: already owns safe paths and sorted/indented JSON serialization.
- Create project_sources/collector/tools/test_run_powershell_review_assist_workflow_mode.py: golden byte-parity and hostile behavior.
- Create four immutable fixture files under project_sources/collector/fixtures/powershell_review_assist: issue608_slice6_legacy_local.json, issue608_slice6_legacy_local.md, issue608_slice6_legacy_workflow.json, issue608_slice6_legacy_workflow.md.
- Modify .github/actions/run-powershell-review-assist/DcoirPowerShellReviewAssist.Reports.ps1: single native report invocation and unchanged report assertions.
- Modify .github/actions/run-powershell-review-assist/Invoke-DcoirPowerShellReviewAssist.ps1: remove obsolete -MetadataWrapperScript argument; function reachability remains first.
- Delete .github/actions/run-powershell-review-assist/wrap_review_assist_workflow_report.py once new report passes byte parity.
- Only update .github/actions/run-powershell-review-assist/README.md if inspection confirms an obsolete wrapper reference. Do not edit action.yml, Paths.ps1 or .github/workflows without a newly approved scope amendment.
- Existing test_run_powershell_review_assist_report.py and test_run_powershell_review_assist_safety.py remain regression controls. Existing schema supports behavior none and caller_uploaded_artifact.

## Task 1: Capture deterministic legacy output and write RED parity tests

**Files:** Create new workflow-mode test module and four golden fixtures. Read old CLI and wrapper without modifying them.

**Interfaces:** Existing generator main(argv) and wrap_review_assist_workflow_report.py entrypoint. Freeze powershell_review_assist_builder.datetime.now to 2026-11-24T08:00:00+00:00. Use the same nine source input files copied into a disposable repo as the existing PowerShellReviewAssistReportTests.make_repo fixture.

- [ ] **Step 1: Governed startup and isolation.** Read current main, AGENTS.md, Issue #608, approved spec/plan and ircore work item. Start an exact-SHA feature branch from the docs/spec+plan tip only after receiving the execution approval. Compare against live main: before code changes only spec/plan docs should differ. Do not reuse protected main or an unrelated PR branch.
- [ ] **Step 2: Make the legacy source fixture repeatable.** Copy these current checked-in inputs into a temporary repository rooted at tempfile.TemporaryDirectory(), preserving paths: DEFAULT_SCHEMA_PATH, DEFAULT_SURFACE_INVENTORY, DEFAULT_RULE_RISK_REPORT, DEFAULT_RULE_RISK_MATRIX, DEFAULT_CUSTOM_REPORT, DEFAULT_ASSEMBLY_PARITY_REPORT, DEFAULT_GOVERNANCE_REPORT, DEFAULT_ENGINE_BOUNDARY_REPORT, DEFAULT_FUNCTION_REACHABILITY_REPORT. Do not copy an optional analyzer report unless the corresponding legacy baseline intentionally includes it. Test old generator exit status success on copied inputs.
- [ ] **Step 3: Capture both local and wrapper outputs while OLD wrapper still exists.** Execute original run_powershell_review_assist_report.main in process with the builder clock frozen, --repo-root pointing at the disposable fixture, and --json-output/--markdown-output pointing to safely named repo-relative scratch paths. Copy complete local-mode bytes. For workflow bytes, generate the intermediate JSON with the same clock; invoke the actual old wrapper with REVIEW_ASSIST_GENERATED_JSON set to the absolute temporary source report and REVIEW_ASSIST_TARGET_JSON / REVIEW_ASSIST_TARGET_MARKDOWN set to repo-relative final scratch paths within a disposable **baseline checkout** as CWD, so its dynamic module import resolves. Capture the two actual wrapper output files, including their paths and the exact workflow retention string, as goldens. Remove scratch files in finally. Never overwrite tracked committed local-report artifacts or fake the legacy wrapper in test code.

Use this clock seam around each old/new report-generation invocation:

~~~python
from datetime import datetime, timezone
from unittest.mock import patch
import powershell_review_assist_builder as builder

class FrozenDatetime:
    @staticmethod
    def now(tz=None):
        return datetime(2026, 11, 24, 8, 0, 0, tzinfo=tz or timezone.utc)

with patch.object(builder, "datetime", FrozenDatetime):
    rc = review.main([
        "--repo-root", str(fixture_root),
        "--json-output", "project_sources/collector/.slice6_intermediate.json",
        "--markdown-output", "project_sources/collector/.slice6_intermediate.md",
    ])
assert rc == 0
~~~

Keep all four full golden files as inspectable UTF-8 fixture content; generated_at_utc, finding count, JSON sorting and trailing newline must be explicitly checked before committing. If the legacy wrapper produces errors in the isolated checkout, repair the **fixture setup**, not the legacy source. Do not regenerate goldens after changing production code.

- [ ] **Step 4: Add a new unittest.TestCase that uses the ACTUAL shipped native main.** Provide a make_fixture_root helper that copies the nine inputs. Use FINAL_JSON = "project_sources/collector/.slice6_workflow.json" and FINAL_MARKDOWN = "project_sources/collector/.slice6_workflow.md". Under the same FrozenDatetime patch invoke native main with --artifact-behavior caller_uploaded_artifact and the two final paths. Compare BOTH output read_bytes() directly against the saved old-wrapper golden read_bytes() and assert exact workflow retention/behavior/paths. In another test call native main with no new flags and compare full bytes to both saved local goldens.

~~~python
with patch.object(builder, "datetime", FrozenDatetime):
    rc = review.main([
        "--repo-root", str(fixture_root),
        "--artifact-behavior", "caller_uploaded_artifact",
        "--json-output", FINAL_JSON,
        "--markdown-output", FINAL_MARKDOWN,
    ])
self.assertEqual(rc, 0)
self.assertEqual(
    (fixture_root / FINAL_JSON).read_bytes(),
    (REPO_ROOT / "project_sources/collector/fixtures/powershell_review_assist/issue608_slice6_legacy_workflow.json").read_bytes(),
)
self.assertEqual(
    (fixture_root / FINAL_MARKDOWN).read_bytes(),
    (REPO_ROOT / "project_sources/collector/fixtures/powershell_review_assist/issue608_slice6_legacy_workflow.md").read_bytes(),
)
~~~

- [ ] **Step 5: Run RED and commit tests and immutable goldens.**

~~~bash
python project_sources/collector/tools/test_run_powershell_review_assist_workflow_mode.py -v
git diff --check
git add project_sources/collector/tools/test_run_powershell_review_assist_workflow_mode.py project_sources/collector/fixtures/powershell_review_assist/issue608_slice6_legacy_local.json project_sources/collector/fixtures/powershell_review_assist/issue608_slice6_legacy_local.md project_sources/collector/fixtures/powershell_review_assist/issue608_slice6_legacy_workflow.json project_sources/collector/fixtures/powershell_review_assist/issue608_slice6_legacy_workflow.md
git commit -m "test: capture legacy review-assist bytes and reject absent native mode (#608)"
~~~

Expected RED is native argparse rejecting --artifact-behavior with exit code 2; the old local-mode control should pass. Save exact test failure evidence and GitHub branch/file SHA readbacks.

## Task 2: Implement native artifact behavior in the canonical Python generator

**Files:** Modify run_powershell_review_assist_report.py, powershell_review_assist_builder.py, powershell_review_assist_rendering.py; test new workflow-mode module plus both existing report suites.

**Interfaces:** Retain parse_args(argv: list[str]) -> argparse.Namespace, main(argv=None) -> int, build_report(args) -> (report, errors, warnings), write_outputs(repo_root, report, json_output, markdown_output). Add one helper workflow_artifact_contract(args: argparse.Namespace, repo_root: Path) -> dict[str, Any] in builder. Existing direct build_report callers missing mode fields must continue to work.

- [ ] **Step 1: Write RED argument-security cases first.** Directly exercise review.parse_args. Reject unknown behavior, --retention-scope in default none mode, blank scope, newline, carriage return, DEL and other control bytes; accept legitimate explicit scope and workflow default. Test all hostile failures exit with argparse SystemExit code 2.

~~~python
for scope in ("", "  ", "x\ny", "x\ry", "x\x01y"):
    with self.subTest(scope=repr(scope)):
        with self.assertRaises(SystemExit) as caught:
            review.parse_args([
                "--artifact-behavior", "caller_uploaded_artifact",
                "--retention-scope", scope,
            ])
        self.assertEqual(caught.exception.code, 2)
~~~

Run the test module to capture RED before adding flags.

- [ ] **Step 2: Add the CLI choices and validate interdependent flags.** In existing parse_args add the two arguments. Replace the final return parser.parse_args(argv) with validated args. No new dependency and no user-visible new flag in default-mode report output.

~~~python
parser.add_argument("--artifact-behavior", choices=("none", "caller_uploaded_artifact"), default="none")
parser.add_argument("--retention-scope", default=None)
args = parser.parse_args(argv)
scope = args.retention_scope
if args.artifact_behavior == "none" and scope is not None:
    parser.error("--retention-scope requires --artifact-behavior caller_uploaded_artifact")
if scope is not None and (
    not scope.strip() or any(ord(ch) < 32 or ord(ch) == 127 for ch in scope)
):
    parser.error("--retention-scope cannot be blank or contain control characters")
return args
~~~

- [ ] **Step 3: Add one canonical workflow metadata selector before validation.** In rendering.py define constant WORKFLOW_RETENTION_SCOPE exactly as specified in Global constraints. Keep artifact_contract() unchanged when called without mode. In builder.py import the constant, artifact_contract(), and existing resolve_report_output_path. Implement workflow_artifact_contract(args, repo_root) to take getattr(args, "artifact_behavior", "none") and getattr(args, "retention_scope", None), return the original artifact_contract unchanged for local none, and reject unexpected mode/scope even for direct Namespace callers. For workflow, safe-resolve both Path(args.json_output) and Path(args.markdown_output), reject output aliases, set final relative JSON and Markdown metadata, workflow_behavior caller_uploaded_artifact, and retention_scope override/default. Do not mutate source reports or other contract fields.

~~~python
def workflow_artifact_contract(args: argparse.Namespace, repo_root: Path) -> dict[str, Any]:
    contract = artifact_contract()
    behavior = getattr(args, "artifact_behavior", "none")
    retention = getattr(args, "retention_scope", None)
    if behavior not in ("none", "caller_uploaded_artifact"):
        raise ReviewAssistError("Unsupported artifact behavior")
    if behavior == "none":
        if retention is not None:
            raise ReviewAssistError("Retention override requires workflow artifact behavior")
        return contract
    if retention is not None and (
        not isinstance(retention, str) or not retention.strip()
        or any(ord(ch) < 32 or ord(ch) == 127 for ch in retention)
    ):
        raise ReviewAssistError("Invalid workflow retention scope")
    _, json_relative = resolve_report_output_path(
        repo_root, Path(args.json_output), "PowerShell review-assist JSON report output", ".json"
    )
    _, markdown_relative = resolve_report_output_path(
        repo_root, Path(args.markdown_output), "PowerShell review-assist Markdown report output", ".md"
    )
    if json_relative == markdown_relative:
        raise ReviewAssistError("JSON and Markdown output paths must be different")
    contract["local_artifacts"]["json"] = json_relative
    contract["local_artifacts"]["markdown"] = markdown_relative
    contract["workflow_behavior"] = "caller_uploaded_artifact"
    contract["retention_scope"] = retention if retention is not None else WORKFLOW_RETENTION_SCOPE
    return contract
~~~

In build_report, calculate this contract before render_markdown, validate_markdown_parity and schema validation; on ReviewAssistError append a validation error and do not produce a successful report. Keep write_outputs safe resolution as an independent second safeguard.

- [ ] **Step 4: Render workflow behavior in its exact legacy position.** In render_markdown, immediately after JSON and Markdown artifact lines, append one line only when behavior is caller_uploaded_artifact and before existing retention scope. Add the workflow line to validate_markdown_parity only in workflow mode; preserve all local-mode lines.

~~~python
if report["artifact_contract"]["workflow_behavior"] == "caller_uploaded_artifact":
    lines.append("- Workflow behavior: " + chr(96) + "caller_uploaded_artifact" + chr(96))
~~~

At implementation time prefer ordinary literal Markdown backticks in the actual Python source; the chr(96) spelling here merely keeps the plan document easy to transport. Preserve exact indentation, whitespace, LF line endings and sorted JSON output.

- [ ] **Step 5: Run GREEN on old and new modes and inspect fixture immutability.**

~~~bash
python project_sources/collector/tools/test_run_powershell_review_assist_workflow_mode.py -v
python project_sources/collector/tools/test_run_powershell_review_assist_report.py -v
python project_sources/collector/tools/test_run_powershell_review_assist_safety.py -v
python project_sources/collector/tools/run_powershell_review_assist_report.py --help
git diff --check
~~~

Require full byte equality for both JSON and Markdown golden pairs under fixed time. Confirm no fixture file modified. If the renderer would exceed 15,000 bytes, move only a cohesive pure metadata helper to a small module; do not expand or restructure unrelated report handling.

- [ ] **Step 6: Commit native implementation and read back source.**

~~~bash
git add project_sources/collector/tools/run_powershell_review_assist_report.py project_sources/collector/tools/powershell_review_assist_builder.py project_sources/collector/tools/powershell_review_assist_rendering.py project_sources/collector/tools/test_run_powershell_review_assist_workflow_mode.py
git commit -m "feat: generate workflow review-assist metadata natively (#608)"
git show --name-status --format=fuller HEAD
~~~

The existing wrapper remains in place until the separate Task 3 action-gate migration is GREEN.

## Task 3: Switch the shipped PowerShell action to native mode and delete wrapper

**Files:** Modify .github/actions/run-powershell-review-assist/DcoirPowerShellReviewAssist.Reports.ps1 and Invoke-DcoirPowerShellReviewAssist.ps1; delete wrap_review_assist_workflow_report.py; update README only if needed. Keep action.yml, Paths.ps1 and workflow YAML unchanged.

**Interfaces:** Invoke-PowerShellReviewAssistReportGate now takes only mandatory ReviewAssistJson and ReviewAssistMarkdown. It calls native main once directly into those previously guarded final paths. The separate Invoke-FunctionReachabilityReviewAssistGate remains first.

- [ ] **Step 1: Add a RED shipped-wiring test.** Read the actual two PowerShell script files from the test module and assert the report gate calls --artifact-behavior caller_uploaded_artifact, has no MetadataWrapperScript or REVIEW_ASSIST_GENERATED_JSON/REVIEW_ASSIST_TARGET_JSON/REVIEW_ASSIST_TARGET_MARKDOWN env wrapper calls, and the obsolete wrapper file no longer exists. Check the reachability-gate invocation precedes report-gate invocation. Run RED on current action before changing it.

~~~python
root = REPO_ROOT / ".github/actions/run-powershell-review-assist"
reports = (root / "DcoirPowerShellReviewAssist.Reports.ps1").read_text(encoding="utf-8")
entry = (root / "Invoke-DcoirPowerShellReviewAssist.ps1").read_text(encoding="utf-8")
self.assertIn("--artifact-behavior caller_uploaded_artifact", reports)
self.assertNotIn("MetadataWrapperScript", reports + entry)
self.assertNotIn("& python $MetadataWrapperScript", reports)
self.assertFalse((root / "wrap_review_assist_workflow_report.py").exists())
self.assertLess(entry.index("Invoke-FunctionReachabilityReviewAssistGate"),
                entry.index("Invoke-PowerShellReviewAssistReportGate"))
~~~

- [ ] **Step 2: Replace only the redundant report path in Reports.ps1.** Retain function-reachability helper unmodified. Remove obsolete GeneratedJson, GeneratedMarkdown and MetadataWrapperScript parameters, wrapper existence test, intermediate source outputs, env handoff, wrapper invocation and intermediate deletion in Invoke-PowerShellReviewAssistReportGate. The actual generation becomes:

~~~powershell
& python project_sources/collector/tools/run_powershell_review_assist_report.py --repo-root . --artifact-behavior caller_uploaded_artifact --json-output $ReviewAssistJson --markdown-output $ReviewAssistMarkdown
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
  throw "PowerShell review-assist report generation failed with exit code $exitCode."
}
~~~

Retain the checks for both final files; JSON ConvertFrom-Json, validation.success, metadata workflow behavior, exact JSON/Markdown final paths, retention content, the workflow behavior Markdown fragment, normalized finding count, optional analyzer state, and final path logging. Keep ErrorActionPreference Stop. Do not move the underlying upload steps or relax source schema/validation.

- [ ] **Step 3: Update the existing action entrypoint.** Keep path resolution/cleanup and function-reachability gate order unchanged; only replace its final report-gate call:

~~~powershell
Invoke-PowerShellReviewAssistReportGate -ReviewAssistJson $paths.ReviewAssistJson -ReviewAssistMarkdown $paths.ReviewAssistMarkdown
~~~

Delete wrap_review_assist_workflow_report.py after confirming new tests GREEN. Leave Paths.ps1 intermediate path declarations/cleanup unchanged unless direct call-site evidence proves they break execution; further path-guard refactoring is reserved for Slice 7. Adjust README solely for a verified obsolete wrapper reference. Do NOT change action.yml or any .github/workflows file.

- [ ] **Step 4: Run scoped GREEN, source readback and PowerShell syntax.**

~~~bash
python project_sources/collector/tools/test_run_powershell_review_assist_workflow_mode.py -v
python project_sources/collector/tools/test_run_powershell_review_assist_report.py -v
python project_sources/collector/tools/test_run_powershell_review_assist_safety.py -v
git diff --check
git diff -- .github/actions/run-powershell-review-assist
~~~

Parse and exercise the actual action scripts through a PowerShell host. If a local Windows PowerShell 5.1 executor is unavailable, mark that gap and require the exact-head GitHub Windows 5.1 run before claiming readiness. Python source-string checks alone do not clear shell/quoting or action integration gates.

- [ ] **Step 5: Commit and read back only intended action changes.**

~~~bash
git add .github/actions/run-powershell-review-assist/DcoirPowerShellReviewAssist.Reports.ps1 .github/actions/run-powershell-review-assist/Invoke-DcoirPowerShellReviewAssist.ps1 .github/actions/run-powershell-review-assist/wrap_review_assist_workflow_report.py
git commit -m "refactor: retire review-assist workflow metadata wrapper (#608)"
git show --name-status --format=fuller HEAD
~~~

Stage README separately only if changed. GitHub compare must contain no modifications to action.yml or .github/workflows.

## Task 4: Run novel hostile/safe cases and existing gates

**Files:** Test the new workflow-mode module plus unchanged report/safety tests and action path guards. Modify only specifically failing scoped tests or native code after a valid finding.

- [ ] **Step 1: Verify invalid retention, mode and no-write controls.** Assert local default full bytes against goldens, default workflow full bytes, and valid explicit scope synchronized between JSON and Markdown. Test unsupported modes; scope with none; blank, newline, return, DEL and C0 scope; no-write in both modes leaves pre-existing outputs unchanged. Reject unsafe modes before any successful report write.

- [ ] **Step 2: Test real CLI output-path escapes and valid opposite polarity.** Use disposable fixture paths for ../outside.json, absolute/outside-root target, wrong extension, symlink escape, reserved .github/workflows path, and JSON/Markdown aliases. Demand nonzero without writing a success artifact. Safe repo-relative distinct .json/.md paths must pass. Exercise real resolve_report_output_path rather than a Python mirror.

- [ ] **Step 3: Recheck failed source, schema and write contracts.** Reuse existing missing/malformed required reports, bad schema, and injected Markdown write failure tests; add native-workflow variant checking validation.success is false and failed JSON persistence is attempted when safe. Do not silently use an older leftover report. Assert a missing obsolete wrapper file does not prevent the new action from running.

- [ ] **Step 4: Execute repo tests, audit and action-contract checks.**

~~~bash
python project_sources/collector/tools/test_run_powershell_review_assist_workflow_mode.py -v
python project_sources/collector/tools/test_run_powershell_review_assist_report.py -v
python project_sources/collector/tools/test_run_powershell_review_assist_safety.py -v
python .github/github_actions/tools/test_report_only_static_gate_actions.py -v
python .github/github_actions/tools/check_workflow_modularization_contracts.py
python .github/github_actions/tools/audit_reusable_contracts.py
python .github/github_actions/tools/check_workflow_consistency_drift.py
git diff --check
~~~

Read the *current* collector-tool test discovery command in reusable-validate-on-pr.yml and run it, confirming the newly created workflow-mode test module is picked up. No new workflow runner is needed merely to run one test.

- [ ] **Step 5: Internal Prog/Adva hostile review and commit.** Prog documents scope, exact code paths and test output. Adva tests fresh variants beyond scripted cases: similar-looking aliased output paths, symlink escapes, backtick/control Markdown injection, schema corruption, partial writes, stale intermediates, and a missing wrapper, plus valid opposite-polarity controls. Fix every valid finding in smallest guarded batch, rerun tests and re-review. Commit only tests and approved scoped fixes; no success claim until test output and actual action readback support it.

~~~bash
git add project_sources/collector/tools/test_run_powershell_review_assist_workflow_mode.py
git commit -m "test: harden native workflow report parity and hostile controls (#608)"
git show --name-status --format=fuller HEAD
~~~

## Task 5: Draft PR and exact-head validation handoff

**Files:** Inspect all scoped source/test/fixture files; no additional workflow or package changes.

- [ ] **Step 1: Verify final scope, immutable goldens and guardrails.** Compare main...HEAD, inspect each changed file, verify deletion of wrapper, no executable references, native mode call once, canonical metadata and Markdown owner, no action.yml/other workflow modifications, source files under 15 KB, and unchanged goldens after baseline. Inspect any intentional fixture size changes and explain. Check package and finding-output parity; do not assume it from a successful unit-test import.

~~~bash
git diff --name-status main...HEAD
git diff --check main...HEAD
git grep -n "wrap_review_assist_workflow_report.py" -- .github project_sources/collector/tools
git grep -n "REVIEW_ASSIST_GENERATED_JSON" -- .github/actions/run-powershell-review-assist
~~~

The two git grep calls should return exit 1 for NO MATCHES. Interpret that deliberate negative correctly.

- [ ] **Step 2: Create only a Draft PR after independent remote readback.** Target protected main, link Issue #608 Slice 6, approved design and plan, golden legacy provenance, full JSON/Markdown byte equality, safe/hostile controls, wrapper removal, Python and PowerShell changed-file list, and unresolved gaps. If a connector write is ambiguous, discover existing PR/branch before retrying. Do not request Copilot, external Codex or paid OpenRouter/DCOIR Review.

- [ ] **Step 3: Check exact-head Draft CI and real Windows action.** Read actual run IDs, SHA, jobs/steps and artifacts for Draft fail-fast, Workflow Audit, collector-tool tests, separate Windows PowerShell 5.1/Pester, and actual workflow-action report metadata. If a workflow is default-branch-only or skipped, record an explicit coverage gap rather than infer PASS. Keep Draft during repair.

- [ ] **Step 4: Stop for operator review/Ready gates.** Present Draft PR, current SHA, review findings and test evidence. Reviewer initiation, Ready, full Windows/PSScriptAnalyzer/static/CodeQL/GHAS validations, squash merge and parent issue closure all require distinct approvals. No paid OpenRouter/DCOIR Review. No live external Codex comment without operator approval of exact text.

- [ ] **Step 5: Preserve parent Issue and continuity.** After any later separately approved merge, verify new protected main and postmerge Main Push Validation, Windows PowerShell 5.1 and Workflow Audit before declaring Slice 6 fully landed. Parent Issue #608 remains OPEN for Slice 7. Record governed ircore update/readback and prepend full cumulative turnover checkpoint.

## Final acceptance

- [ ] Written spec approval recorded; separate execution and .github/actions mutation approval obtained.
- [ ] Legacy wrapper golden captures performed before code changes with controlled generated_at_utc, complete bytes archived and never refreshed to hide regressions.
- [ ] RED test proves absence of native flags and action wiring; GREEN shows strict byte equality for local and workflow JSON/Markdown.
- [ ] --artifact-behavior and --retention-scope validated; no-write and legacy Namespace callers unaffected.
- [ ] Final artifact paths/retention/behavior set before schema and Markdown validation, with conditional exact workflow line only in workflow mode.
- [ ] Wrapper deleted and not invoked; reachability, output safety, JSON/Markdown metadata, source validation and fatal failures preserved.
- [ ] Adva novel hostile/safe findings disposition and true Windows PowerShell 5.1 action evidence recorded.
- [ ] Exact-head scoped Draft PR only; reviewer/Ready/merge each explicitly operator-controlled; Issue #608 remains OPEN for Slice 7.
