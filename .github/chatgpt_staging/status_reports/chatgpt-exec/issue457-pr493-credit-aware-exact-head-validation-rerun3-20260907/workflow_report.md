# ChatGPT workflow report

## Result

- workflow: chatgpt-exec
- report_scope: progressive-in-session
- report_family: live-heartbeat
- assistant_polling_target: true
- identifier_type: request_id
- poll_until_result: success_or_failure
- do_not_use_repo_workflows_for_live_polling: true
- result: success
- phase: final-readback-commit
- request_id: issue457-pr493-credit-aware-exact-head-validation-rerun3-20260907
- request_path: .github/chatgpt_staging/exec_requests/issue457-pr493-credit-aware-exact-head-validation-rerun3-20260907.json
- github_run_id: 34124900724
- github_run_attempt: 1
- github_sha: 22e50f465cc638d36cec94d366c6ccdd59ad4076
- github_ref: refs/heads/main
- workflow_run_url: https://github.com/malwaredevil/dcoir-collector/actions/runs/34124900724
- report_updated_utc: 2026-09-07T13:00:35Z
- progress_history_path: .github/chatgpt_staging/status_reports/chatgpt-exec/issue457-pr493-credit-aware-exact-head-validation-rerun3-20260907/progress_history.jsonl
- latest_progress_marker_path: .github/chatgpt_staging/status_reports/chatgpt-exec/issue457-pr493-credit-aware-exact-head-validation-rerun3-20260907/latest_progress_marker.json
- artifact_name: chatgpt-exec-issue457-pr493-credit-aware-exact-head-validation-rerun3-20260907
- exit_code: 0

## Report routing

This is the live heartbeat report for an active ChatGPT-staged job. Poll this exact request_id path until result is success or failure. Do not use repo-workflows completed-run summaries for live progress polling.

## Current status

Final exec status is being committed with workflow report, progress history, marker, and any tracked summary files already produced by the request/tool. Full output remains in the uploaded GitHub Actions artifact.

## Phase history

- 2026-09-07T13:00:02Z | phase=request-resolved | result=running | Exec request path resolved. The workflow is preparing to run the approved command harness.
- 2026-09-07T13:00:06Z | phase=running-harness | result=running | Approved command harness is about to run. If this report remains in this phase, inspect the GitHub run URL for harness/runtime progress.
- 2026-09-07T13:00:32Z | phase=harness-finished | result=success | Approved command harness finished with exit code 0. Final native exec status commit is next.
- 2026-09-07T13:00:35Z | phase=final-readback-commit | result=success | Final exec status is being committed with workflow report, progress history, marker, and any tracked summary files already produced by the request/tool. Full output remains in the uploaded GitHub Actions artifact.

## Next ChatGPT action

Poll this same report path until result is success or failure. If result is running, use the phase history to decide whether to wait, inspect the run URL, or report a blocker.

## GitHub Actions run

- github_run_id: 34124900724
- github_run_attempt: 1
- github_sha: 22e50f465cc638d36cec94d366c6ccdd59ad4076
- github_ref: refs/heads/main
- workflow_run_url: https://github.com/malwaredevil/dcoir-collector/actions/runs/34124900724

## Output readback contract

- heartbeat_report: committed in this request-scoped status directory
- tracked_summaries: read any concise summary files beside this report when present
- full_output: uploaded GitHub Actions artifact named in this report
- artifact_readback: optional and normally not committed for chatgpt-exec because .gitignore intentionally excludes unzipped artifact_readback trees
