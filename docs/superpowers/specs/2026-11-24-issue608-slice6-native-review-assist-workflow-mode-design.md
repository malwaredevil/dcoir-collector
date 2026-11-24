# Issue #608, Slice 6: Native PowerShell Review-Assist Workflow Mode

**Design status:** Conceptual approach approved by the operator on November 24, 2026, including changes under .github/actions in principle. This is a documentation-only written specification for independent operator review. Its commitment does NOT authorize implementation of Python, PowerShell, GitHub Actions, test sources, reviewer invocations, a PR, or a merge.

**Parent:** https://github.com/malwaredevil/dcoir-collector/issues/608

**Canonical baseline:** protected main at c8c76c5971b433c4c549c5c1d92740d085ab98a8, the verified squash merge of Slice 5 PR #671. Exact-main post-merge Main Push Validation #45346645550 (42 successful steps), Windows PowerShell 5.1 #45346645647 (12 successful steps), and Workflow Audit #45346645540 all succeeded. Parent Issue #608 stays OPEN for Slices 6 and 7.

## 1. Motivation and current behavior

The remaining Slice 6 requirement in Issue #608 is "Native review-assist workflow mode. CLI flags --artifact-behavior/--retention-scope; delete the wrapper. Parity: byte-identical JSON and Markdown."

The currently shipped executable flow is:

1. .github/actions/run-powershell-review-assist/action.yml invokes Invoke-DcoirPowerShellReviewAssist.ps1, which dot-sources the existing Paths.ps1 and Reports.ps1 helpers.
2. The action validates output paths and performs the separate function-reachability gate first. Reports.ps1 calls project_sources/collector/tools/run_powershell_review_assist_report.py for intermediate workflow-source JSON and Markdown.
3. .github/actions/run-powershell-review-assist/wrap_review_assist_workflow_report.py dynamically imports the CLI through importlib, sys.modules and sys.path mutation. It reads intermediate JSON, rewrites artifact_contract.local_artifacts.json and .markdown to the final caller-uploaded artifact paths, rewrites artifact_contract.retention_scope and .workflow_behavior, writes final JSON, re-renders Markdown and patches one exact retention line by str.replace to inject Workflow behavior.
4. Reports.ps1 deletes the intermediate outputs, checks final report presence, generator result, validation.success, workflow_behavior, both metadata paths, and the JSON/Markdown metadata fragments. Workflow callers upload the final outputs.

This is a second owner for output serialization and metadata. It is fragile to Markdown text changes and bypasses the canonical generator's ownership of the final workflow artifact contract. Its wrapper is 2,370 bytes and cannot be retired until the native CLI reproduces its exact output.

The canonical generation implementation is already factored into run_powershell_review_assist_report.py (CLI, 4,320 bytes), powershell_review_assist_builder.py (report model and writer, 10,699 bytes), powershell_review_assist_rendering.py (artifact contract, Markdown and schema validation, 13,932 bytes), and powershell_review_assist_sources.py (safe path resolution and JSON serialization). The renderer currently emits no Workflow behavior Markdown line, and default artifact_contract.workflow_behavior is "none".

A subtle parity constraint: the builder sets generated_at_utc using the current time. A test must freeze or share that value between legacy and native paths. Comparing reports from unrelated wall-clock seconds does NOT demonstrate byte parity or a genuine difference.

## 2. Options and decision

**A. Native CLI artifact mode (chosen).** Add two narrowly typed arguments to the existing CLI. Have the canonical builder select the artifact contract before its Markdown/schema validation and its writer generate the final JSON and Markdown directly. Change the existing PowerShell review-assist action helper to invoke the native mode and remove the wrapper. Preserve its existing checks and upload contract.

**B. Retain Python wrapper with fewer import tricks.** Reduces one failure mode but retains a second report serialization and Markdown mutation owner, contrary to Issue #608. Rejected.

**C. Move metadata and Markdown rewriting into PowerShell.** Deletes Python wrapper but adds another competing renderer, separate quoting/encoding behavior, and weaker JSON/Markdown byte guarantees. Rejected.

Option A changes the CLI's interface and the action's implementation but does not change what collector/Gemini/OpenAI packages contain, finding classifications, thresholds, schema version, report meanings, workflow upload policy, or action callers.

## 3. Proposed interfaces and ownership

### 3.1 CLI modes

Add to project_sources/collector/tools/run_powershell_review_assist_report.py:

- --artifact-behavior with explicit choices "none" and "caller_uploaded_artifact"; default "none".
- --retention-scope as an optional explicit string, only valid when behavior is "caller_uploaded_artifact". Reject an empty/whitespace-only value and control/newline characters so the Markdown structure cannot be injected through this parameter.
- When workflow behavior is selected and no --retention-scope is supplied, use exactly one canonical workflow retention default:
  "workflow-generated report artifacts uploaded by the caller workflow; retention is configured by the caller upload-artifact step, not by #268"
- With no flags, retain every existing local-mode default, including local_artifacts paths, retention text, workflow_behavior "none", JSON and Markdown bytes, validation outcome, and --no-write behavior.
- Existing in-process build_report callers may construct argparse.Namespace without these two new attributes. Preserve compatibility with those callers, for example using safe mode defaults when the attributes are absent rather than assuming new fields always exist.

The action should invoke the report CLI with --artifact-behavior caller_uploaded_artifact and explicit --json-output / --markdown-output final paths. It should NOT need to copy the long workflow retention string into a second PowerShell constant; the CLI owns the canonical default while still exposing the requested explicit override flag.

### 3.2 One artifact-contract owner

Use powershell_review_assist_rendering.py as the authoritative creator/renderer of artifact_contract. In local mode, artifact_contract() continues to return the current unchanged defaults. In workflow mode, its model must contain, before rendering or validation:

- artifact_contract.local_artifacts.json = the validated final repo-relative JSON output path
- artifact_contract.local_artifacts.markdown = the validated final repo-relative Markdown output path
- artifact_contract.workflow_behavior = "caller_uploaded_artifact"
- artifact_contract.retention_scope = the canonical default above or a validated explicit override

The rest of artifact_contract, including schema path, issue 268, and future handoff consumers, remains unchanged. The schema at project_sources/collector/powershell_review_assist_report.schema.json already permits "none" and "caller_uploaded_artifact"; only change the schema if a new direct test proves it is necessary.

Ensure that metadata is populated BEFORE build_report invokes render_markdown, validate_markdown_parity and validate_against_schema_contract, and BEFORE write_outputs serializes either final file. Never implement native mode by generating a local report and then rewriting it or editing Markdown with string replacement.

Preserve safe output resolution in powershell_review_assist_sources.py: reject paths outside repository, traversal, wrong output suffix, symlinks escaping root, JSON/Markdown aliasing, and reserved/unsafe outputs. Validate final paths before creating final output files or claiming workflow success; errors remain visible and nonzero. No relaxation of the existing safety boundaries.

### 3.3 Canonical Markdown ordering

Change render_markdown only for workflow mode. Its Artifact Contract section must serialize the same lines, in the same order, as today's wrapper:

    - JSON: [existing final path with backticks]
    - Markdown: [existing final path with backticks]
    - Workflow behavior: [caller_uploaded_artifact with backticks]
    - Retention scope: workflow-generated report artifacts uploaded by the caller workflow; retention is configured by the caller upload-artifact step, not by #268

The actual Markdown output uses existing backtick formatting for file paths and workflow_behavior; the bracketed values above are explanatory placeholders, NOT literal output strings. There must be no inserted Workflow behavior line in local mode, whose existing Markdown output must stay byte-identical. Preserve all existing headers, spaces, indentation, newline endings and file ordering.

The canonical JSON serializer already uses json.dumps(data, indent=2, sort_keys=True) plus one final newline, matching the legacy wrapper's JSON writer. Do not introduce different JSON keys, alternate serializers, new timestamp fields, different finding counts, or metadata refactoring.

### 3.4 Composite action integration

Scope only the existing run-powershell-review-assist action unless the implementation discovers and separately reports a genuine dependency:

- Modify .github/actions/run-powershell-review-assist/DcoirPowerShellReviewAssist.Reports.ps1. Preserve Invoke-FunctionReachabilityReviewAssistGate and its fail-closed checks. In Invoke-PowerShellReviewAssistReportGate, stop generating an intermediate report for the wrapper; call the CLI once, directly into the already-validated final ReviewAssistJson and ReviewAssistMarkdown paths with workflow mode enabled. Preserve exact validation.success, behavior, local paths, retention, JSON/Markdown fragment and nonzero-exit checks.
- Modify .github/actions/run-powershell-review-assist/Invoke-DcoirPowerShellReviewAssist.ps1 to remove the obsolete -MetadataWrapperScript argument. Preserve existing Paths.ps1 gate/cleanup and reachability-before-review-assist order.
- Delete .github/actions/run-powershell-review-assist/wrap_review_assist_workflow_report.py. Remove imports, environment variables and documentation references to it. Do not keep a hidden compatibility shim in production.
- Keep action.yml inputs json-output and markdown-output, the existing pwsh entrypoint, caller upload semantics, and pinned action/runtime versions unchanged. Review the existing README and adjust solely where the removed wrapper is explicitly described.
- Preserve the existing temporary path declarations and cleanup in Paths.ps1 if other code or expected output cleanup still requires them. Remove only genuinely unreachable temporary declarations after a separate call-site check, with parity tests. Do not broaden into a different path-guard refactor; that belongs to Slice 7.

The script may stop printing old intermediate-path success messages if those files no longer exist, but must keep final artifact paths, finding count, analyzer state, validation result and action error semantics grounded in actual reports.

## 4. Test-first behavior and byte parity

**Golden baseline, before changes:** On a disposable checkout at protected main c8c76c5971b433c4c549c5c1d92740d085ab98a8, run the current CLI and legacy wrapper through their actual supported entrypoints with fixed source fixtures and the current final output names. Capture complete JSON and Markdown byte streams, not just semantic fields. Freeze generated_at_utc, or feed the same explicitly controlled timestamp into both paths, so the baseline is deterministic. If exact timestamp control needs a small test-only seam, make it explicit and bounded. Do not normalize away unexpected differences during comparison.

**RED first:** Add a narrow regression that exercises the requested CLI flags (fails before implementation) and a wiring test that requires the actual PowerShell action to call the native mode without the wrapper (fails on current source). Keep a safe local-mode positive control.

**GREEN parity:** After code changes, compare bytes of both complete native workflow outputs with the stored/generated old wrapper outputs at identical source input, timestamp, output paths, retention and workflow behavior. Assert exactly equal JSON bytes and exactly equal Markdown bytes. The baseline uses the old code in an isolated fixture or immutable exact SHA, not a reimplementation of wrapper logic that could share the same defect.

**Minimum hostile and safe controls:**

1. Local default mode: identical JSON and Markdown, same artifact_contract fields, CLI exit, schema and parity validation, with no workflow behavior line.
2. Workflow mode with default retention: identical to old wrapper, including all final paths, one Workflow behavior line directly before Retention scope, JSON ordering and trailing newlines.
3. Workflow mode with a legitimate explicit retention override: schema/parity checks remain valid; override appears consistently in JSON and Markdown.
4. Unsupported --artifact-behavior value, --retention-scope used with "none", blank/embedded-newline retention, malicious escape/control content: reject nonzero without writing a successful report.
5. Hostile final JSON/Markdown output paths: traversal, absolute/outside root, wrong suffix, symlink escape, aliased outputs and reserved target files; preserve fail-closed path behavior.
6. Missing/malformed required upstream artifact, invalid schema, existing finding validation failures, injected writer failure: preserve nonzero results and existing failed-report persistence semantics where allowed and possible.
7. Safe opposite-polarity fixtures and the exact shipped PowerShell caller on Windows PowerShell 5.1: pass for legitimate final paths, reject malformed paths, enforce no wrapper invocation or stale temporary report reuse.
8. Show no change to #268 local-mode fixtures, finding summaries, generated report schema version, workflow upload paths, PSScriptAnalyzer or static analysis gate findings.

Tests should extend the existing project_sources/collector/tools/test_run_powershell_review_assist_report.py and test_run_powershell_review_assist_safety.py where space allows, and add one narrowly scoped workflow-mode contract test file only if the existing modules would exceed the 15,000-byte per-source policy. New tests must be discovered by existing CI test runners, not just runnable manually. Include a genuine Windows-side PowerShell action invocation; Python-only tests cannot validate shell quoting or environment passing.

### Required check commands at implementation time

    python project_sources/collector/tools/test_run_powershell_review_assist_report.py -v
    python project_sources/collector/tools/test_run_powershell_review_assist_safety.py -v
    python project_sources/collector/tools/run_powershell_review_assist_report.py --help

Also run the repository's actual collector/tool unittest discovery command, workflow consistency/modularization audit commands, and report-only action contract tests read from the then-current main source. Validate exact-head Draft Workflow Audit, PR validation, Windows PowerShell 5.1 Pester, and full Ready Windows/PSScriptAnalyzer/static analysis under the normal operator gates.

## 5. Error contracts and rollout safety

- Preserve workflow behavior assertions, schema-contract validation, Markdown parity checks and fail-closed nonzero exits. In particular, do not let a successful wrapper removal conceal an upstream report generation failure or remove the PS report validation gate.
- Preserve clean failure report persistence when a final output write fails, where the output path is safe; never publish a successful stale report as a substitute. Existing Paths.ps1 cleanup runs before the report gates and must not inadvertently remove input source reports.
- Keep output paths repo-relative under project_sources/collector/ as enforced today. No new external dependencies or unpinned modules. No additional GitHub Actions permission, event or upload changes.
- Respect the 15 KB source-size policy, existing CLI behavior, source report compatibility, local tool usage and any existing schema/contract fixtures.
- Keep the draft-first anti-freeze process: one to three operations per batch, blob-SHA-guarded writes, exact-head GitHub readbacks, internal Prog implementation and Adva hostile cases, then operator-controlled Copilot/External Codex, Ready, CI and merge.
- Paid OpenRouter/DCOIR Review remains opted out. Do not post slash review commands or any literal live @codex invocation without fresh explicit operator approval of its exact proposed text.
- No change to protected main outside a separately approved merge. Parent Issue #608 stays OPEN for its final Slice 7 even after Slice 6 merges.

## 6. Written-spec approval gate and next phase

This design is complete for review when it explicitly defines one native source of truth for metadata and Markdown, the exact optional CLI flags/default behavior, the final artifact paths and workflow integration, the legacy-wrapper byte-for-byte golden comparison, safe/hostile fixtures, and all approval and rollback boundaries.

**Approval so far:** Operator answered "Yes" to the conceptual Slice 6 design and to changes under .github/actions **in principle** on November 24, 2026. That authorizes committing this written design specification to a docs-only branch, not implementation.

**Next approval required:** Operator must separately review and approve this committed written specification. Only then use superpowers:writing-plans to create a test-first implementation plan. Implementation of .github/actions and Python source needs further explicit operator permission after plan review. Draft PR, formal review requests, Ready, merge and closing Issue #608 are separate later gates.

**Remaining project:** Issue #608 contains seven planned slices; Slices 1 through 5 are merged. Slice 6 is the current design-only scope, and Slice 7 shipped PowerShell path-guard tests remains to be planned.
