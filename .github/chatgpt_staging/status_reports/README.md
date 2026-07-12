# ChatGPT status reports

This directory has three report families. Do not mix them.

## Live heartbeat reports

Use these for active ChatGPT-staged jobs while they are running.

Paths:

- `.github/chatgpt_staging/status_reports/chatgpt-exec/<request_id>/workflow_report.md`
- `.github/chatgpt_staging/status_reports/chatgpt-stage-out/<request_id>/workflow_report.md`
- `.github/chatgpt_staging/status_reports/chatgpt-apply-in/<request_id>/workflow_report.md`
- `.github/chatgpt_staging/status_reports/chatgpt-github-artifact-readback/<request_id>/workflow_report.md`

Expected metadata:

- `report_family: live-heartbeat`
- `assistant_polling_target: true`
- `identifier_type: request_id`
- `poll_until_result: success_or_failure`

Operating rule for ChatGPT:

1. Stage the request once.
2. Poll the stable `workflow_report.md` path by `request_id` while the job runs.
3. Keep polling until `result` is `success` or `failure`.
4. Use `progress_history.jsonl` and the report phase history to understand current progress.
5. Do not restage or modify the request while the run may be queued or running.

Common writer:

- `.github/scripts/write_chatgpt_progress_report.py` writes live heartbeat reports, appends `progress_history.jsonl`, and refreshes `latest_progress_marker.json`.
- Current live heartbeat workflows are `chatgpt-exec`, `chatgpt-stage-out`, `chatgpt-apply-in`, and `chatgpt-github-artifact-readback`.

## Completed workflow-run summaries

Use these after a GitHub workflow has completed, especially for bounded failure-log excerpts.

Path pattern:

- `.github/chatgpt_staging/status_reports/repo-workflows/<workflow>/<github_run_id>/workflow_report.md`

Expected metadata:

- `report_family: completed-run-summary`
- `assistant_polling_target: false`
- `identifier_type: github_run_id`
- `do_not_use_for_live_polling: true`

Operating rule for ChatGPT:

Use repo-workflows reports for post-completion diagnostics and failure summaries. Do not use repo-workflows reports to monitor active ChatGPT-staged jobs. For active jobs, use the live heartbeat request-id path instead.

Workflow directory names under `repo-workflows` are normalized by `.github/scripts/write_workflow_report.py`. For example, `Workflow maintenance audit` is written under `Workflow-maintenance-audit`.

### Custom markdown handoff

Completed-run workflows may add concise workflow-specific context to the central reporter by uploading an artifact with this exact shape:

- artifact name: `chatgpt-workflow-report-section`
- file path inside artifact: `chatgpt_workflow_report_section.md`

The central `chatgpt-workflow-run-reporter` appends that markdown to the completed-run `workflow_report.md` after the standard generated report body. Use this for short, high-signal summaries that help ChatGPT read back run-specific results without opening every artifact or log. Do not use this handoff for live heartbeat status; request-scoped ChatGPT workflows should keep using their stable live heartbeat report path.

Current custom markdown producers:

- `run-gemini-behavioral-replay-manual`
- `manual-gemini-model-comparison`
- `chatgpt-workflow-reporting-validation`
- `collector-documentation-quality`
- `manual-collector-optional-exe-build`
- `manual-collector-runtime-package-build`
- `manual-full-validation`
- `manual-gemini-bundle-build`
- `manual-test-framework-validate`
- `validate-gemini-behavioral-replay`
- `validate-on-pr`
- `validate-on-push`
- `Workflow maintenance audit`

The original candidate custom markdown producer set has been evaluated and promoted. Future workflow-specific additions should still stay scoped and require source-run artifact readback plus central reporter readback before readiness claims.

## Standalone committed reports

Use these after cleanup or retention workflows produce their own committed report outside the central repo-workflows reporter.

Path examples:

- `.github/chatgpt_staging/status_reports/chatgpt-staging-cleanup/<request_id-or-run>/workflow_report.md`
- `.github/chatgpt_staging/status_reports/retention-cleanup/<run-id>/workflow_report.md`

Expected metadata:

- `report_family`: workflow-specific cleanup or retention report
- `assistant_polling_target`: false unless the workflow explicitly documents live polling
- `identifier_type`: request id, run id, or retention cleanup id, as documented by the workflow

Operating rule for ChatGPT:

Use standalone committed reports as scoped cleanup or retention evidence. Do not assume these reports came from the central completed-run reporter, and do not use them as live heartbeat targets unless the workflow-specific header says to do so.

Direct final-report URL output producers:

- `chatgpt-staging-cleanup`
- `chatgpt-report-retention-cleanup`

These workflows commit their own reports and write the final report URL to the GitHub Actions run summary after the report path is available. They remain standalone committed-report producers, not central repo-workflows reporter outputs.

## Workflow reporting lane inventory

This inventory is for workflow-reporting ownership only. GitHub workflow files remain source truth for executable behavior.

| Workflow file | Workflow name | Reporting lane | Live heartbeat | Central reporter | Custom markdown | Standalone report | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `.github/workflows/chatgpt-apply-in.yml` | `chatgpt-apply-in` | Live heartbeat | Yes | No | No | No | Uses common heartbeat writer by request id. |
| `.github/workflows/chatgpt-exec.yml` | `chatgpt-exec` | Live heartbeat | Yes | No | No | No | Uses common heartbeat writer by request id. |
| `.github/workflows/chatgpt-report-retention-cleanup.yml` | `chatgpt-report-retention-cleanup` | Standalone committed report | No | No | No | Yes | Outputs direct final retention-report URL after commit. |
| `.github/workflows/chatgpt-stage-out.yml` | `chatgpt-stage-out` | Live heartbeat | Yes | No | No | No | Uses common heartbeat writer by request id. |
| `.github/workflows/chatgpt-staging-cleanup.yml` | `chatgpt-staging-cleanup` | Standalone committed report | No | No | No | Yes | Outputs direct final cleanup-report URL when a report path is available. |
| `.github/workflows/chatgpt-workflow-reporting-validation.yml` | `chatgpt-workflow-reporting-validation` | Completed-run summary | No | Yes | Yes | No | Validates reporter behavior and custom markdown handoff. |
| `.github/workflows/chatgpt-workflow-run-reporter.yml` | `chatgpt-workflow-run-reporter` | Central completed-run reporter | No | Not applicable | Consumes | No | Owns repo-workflows reports and `Output full URL path`. |
| `.github/workflows/collector-documentation-quality.yml` | `collector-documentation-quality` | Completed-run summary | No | Yes | Yes | No | Validation-family custom markdown producer. |
| `.github/workflows/dependabot-auto-merge.yml` | `Dependabot auto-merge` | Excluded generic/dependabot | No | Yes | No | No | Excluded from mandatory heartbeat and migration work. |
| `.github/workflows/dependency-review.yml` | `Dependency Review` | Excluded generic/dependabot | No | Yes | No | No | Excluded from mandatory heartbeat and migration work. |
| `.github/workflows/manual-collector-optional-exe-build.yml` | `manual-collector-optional-exe-build` | Completed-run summary | No | Yes | Yes | No | Manual build-family custom markdown producer. |
| `.github/workflows/manual-collector-runtime-package-build.yml` | `manual-collector-runtime-package-build` | Completed-run summary | No | Yes | Yes | No | Manual build-family custom markdown producer. |
| `.github/workflows/manual-full-validation.yml` | `manual-full-validation` | Completed-run summary | No | Yes | Yes | No | Manual validation-family custom markdown producer. |
| `.github/workflows/manual-gemini-bundle-build.yml` | `manual-gemini-bundle-build` | Completed-run summary | No | Yes | Yes | No | Manual build-family custom markdown producer. |
| `.github/workflows/manual-gemini-model-comparison.yml` | `manual-gemini-model-comparison` | Completed-run summary | No | Yes | Yes | No | Current custom markdown producer. |
| `.github/workflows/manual-github-artifact-readback.yml` | `chatgpt-github-artifact-readback` | Live heartbeat | Yes | Yes | No | No | Uses common heartbeat writer; central reporter also summarizes completed runs. |
| `.github/workflows/manual-test-framework-validate.yml` | `manual-test-framework-validate` | Completed-run summary | No | Yes | Yes | No | Validation-family custom markdown producer. |
| `.github/workflows/ops-apply-zip.yml` | `Ops apply zip request` | Completed-run summary | No | Yes | No | No | No custom markdown need identified yet. |
| `.github/workflows/ops-dispatch-request.yml` | `Ops dispatch request` | Completed-run summary | No | Yes | No | No | No custom markdown need identified yet. |
| `.github/workflows/ops-file-delete.yml` | `Ops file delete request` | Completed-run summary | No | Yes | No | No | No custom markdown need identified yet. |
| `.github/workflows/ops-restructure-map.yml` | `Ops restructure map request` | Completed-run summary | No | Yes | No | No | No custom markdown need identified yet. |
| `.github/workflows/publish_knowledge_to_wiki.yml` | `Publish Knowledge to Wiki` | External publish plus completed-run summary | No | Yes | No | External wiki commit | Publishes to wiki and receives central reporter summary. |
| `.github/workflows/run-gemini-behavioral-replay-manual.yml` | `run-gemini-behavioral-replay-manual` | Completed-run summary | No | Yes | Yes | No | Current custom markdown producer. |
| `.github/workflows/scheduled-health-check.yml` | `scheduled-health-check` | Completed-run summary | No | Yes | No | No | No custom markdown need identified yet. |
| `.github/workflows/validate-gemini-behavioral-replay.yml` | `validate-gemini-behavioral-replay` | Completed-run summary | No | Yes | Yes | No | Validation-family custom markdown producer. |
| `.github/workflows/validate-on-pr.yml` | `validate-on-pr` | Completed-run summary | No | Yes | Yes | No | Validation-family custom markdown producer. |
| `.github/workflows/validate-on-push.yml` | `validate-on-push` | Completed-run summary | No | Yes | Yes | No | Validation-family custom markdown producer. |
| `.github/workflows/workflow-maintenance-audit.yml` | `Workflow maintenance audit` | Completed-run summary | No | Yes | Yes | No | Current custom markdown producer. |
