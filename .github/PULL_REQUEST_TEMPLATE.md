## Summary

- what changed
- why it changed

## Linked Issue

- Closes or supports: #

## Scope

- in scope:
- implementation surfaces:

## Non-Scope

- intentionally not changed:
- deferred follow-up:

## Changed Authority Surfaces

- [ ] GitHub source
- [ ] GitHub workflow
- [ ] GitHub issue or PR state
- [ ] Supabase ircore operational record
- [ ] Agent or repository instructions
- [ ] Documentation or knowledge surface
- [ ] None of the above, or not applicable

## Label Discipline

- [ ] The linked issue or PR uses only existing repository labels from the approved `area:*` and `type:*` taxonomy
- [ ] Exactly one `area:*` label and exactly one `type:*` label are present, or the exception is explained
- [ ] No new labels were invented in this PR

## Validation And Readback

- [ ] Relevant validation was run or the validation gap is explained
- [ ] Changed source files were read back after mutation
- [ ] Active path references were checked when files or folders were removed
- [ ] Collector/Gemini behavior was not changed unintentionally
- [ ] Supabase receipts were recorded when governed issue or PR readiness depends on them
- [ ] If collector functions were added, removed, renamed, or materially rerouted, both committed reachability reports (`project_sources/collector/powershell_function_reachability_report.json` and `project_sources/collector/powershell_function_reachability_report.md`) were regenerated with `python project_sources/collector/tools/run_powershell_function_reachability_report.py --repo-root . --no-powershell --json-output project_sources/collector/powershell_function_reachability_report.json --markdown-output project_sources/collector/powershell_function_reachability_report.md`, committed, and verified by the review-assist committed-report parity check, or the validation gap is explained

## Governed Review Gates

- [ ] Prog implementation/fix pass is complete or not applicable
- [ ] Adva adversarial review pass is complete or not applicable
- [ ] Codi review is complete or explicitly waived before external Codex review
- [ ] OpenRouter internal review (`/or-review`, `/dcoir-review`, or `/openrouter-review`) is clear after Codi and before external Codex review, or explicitly not applicable/waived because default-branch or equivalent live-test availability is absent for an OpenRouter workflow/script bootstrap PR
- [ ] Before every `/dcoir-review`, `/or-review`, or `/openrouter-review` invocation or rerun, the exact proposed command was shown to the operator and explicitly approved in the current session; no approval means no internal review request
- [ ] External Codex review request exact text was shown to the operator and explicitly approved before posting, or the external Codex gate is not applicable
- [ ] GitHub Copilot review was requested only after explicit operator approval, or was manually triggered by the operator, or the Copilot gate is not applicable

## Review Request Approval Context

- [ ] No PR comment invoking the literal `@codex` handle was posted or confirmed without operator approval of the exact proposed comment text in the current session
- [ ] No `/dcoir-review`, `/or-review`, or `/openrouter-review` command, including `deep`, `diff`, `debug`, or any other variant, was posted or confirmed without operator approval of the exact proposed command in the current session
- [ ] Every internal review rerun received fresh current-session operator approval; a prior approval was not reused
- [ ] No GitHub Copilot review request was made without explicit operator approval unless the operator manually triggered it
- [ ] Approved external `@codex` requests are top-level PR comments when a Codex action or review is required
- [ ] Approved Codex fix requests include exact scope, files, commands, and finish command when a push is expected
- [ ] Codex PR fix tasks are expected to use `codex-pr-context`, relevant validation, and `codex-pr-finish` when available

## Workflow Boundary

- [ ] Workflow files were not changed
- [ ] Workflow files were changed only with explicit operator approval
- [ ] validate-on-pr is expected to run after this PR is marked ready
- [ ] Windows PowerShell 5.1 workflow is expected to run when PowerShell compatibility is in scope
- [ ] CodeQL/security workflow is expected to run when Python, workflow, action, or security-sensitive validation surfaces are in scope
- [ ] Workflow run IDs, job outcomes, and artifacts are read back when workflow success is claimed

## Remaining Gaps

- unresolved finding or validation gap:
- follow-up issue or operator decision:

## Ready-To-Undraft Gate

Do not mark ready for review until this checklist is complete.

- [ ] Final scope-and-suggestion review completed against the linked issue body, issue comments, PR diff, PR comments, and receipt trail
- [ ] The final scope review explicitly confirms whether every issue acceptance criterion is implemented, intentionally deferred, or no longer applicable
- [ ] Any additional impactful scope suggestions were presented to the operator and either implemented, deferred, or rejected before undrafting
- [ ] Codi is clear on the latest PR head
- [ ] OpenRouter internal review is clear on the latest PR head, including command comment, progress/readback, review output, and finding disposition, or an explicit bootstrap/default-branch availability gap is recorded for OpenRouter workflow/script changes
- [ ] Every `/dcoir-review`, `/or-review`, or `/openrouter-review` invocation used for readiness evidence was operator-approved as an exact current-session request, including each rerun
- [ ] External Codex is clear on the latest PR head after an operator-approved exact-text request, or the gate is explicitly not applicable
- [ ] The PR remains draft until the operator approves the final undraft step

## Notes

- follow-up items, risks, or review guidance
