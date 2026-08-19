# ChatGPT workflow report

## Result

- workflow: chatgpt-report-retention-cleanup
- report_scope: retention-cleanup
- report_family: retention-cleanup-summary
- assistant_polling_target: false
- identifier_type: cleanup_run_id
- do_not_use_for_live_polling: true
- result: success
- mode: delete
- success_retention_days: 1
- failure_retention_days: 7
- cleanup_retention_days: 2
- request_retention_days: 1
- bundle_retention_days: 2
- keep_latest_per_workflow: true
- workflow_filter: 
- candidate_count: 1
- retained_count: 60
- github_run_id: 32307696724
- github_sha: 3558fe26e5191d068c68b71acad3dcb739547926
- report_created_utc: 2026-08-19T22:12:19Z

## Paths selected for cleanup
- `.github/chatgpt_staging/status_reports/retention-cleanup/retention-cleanup-32074815587/workflow_report.md` | kind=success | age_days=2.0 | reason=age 2.0d >= 2d

## Paths retained or skipped
- `.github/chatgpt_staging/status_reports/repo-workflows/ChatGPT-Exec-28e18b9a88c1b7d688b4a44e2cebd297d5d45f1b/26898641870/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/ChatGPT-Exec-2cc59fbd5b585801175d4170ec7574d3aeed431b/26897926567/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/ChatGPT-Exec-bf0763394df48db74fa3e2872e562e00d5a5eb83/26899437653/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/Collector-Documentation-Quality/26997648751/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/Collector-Runtime-Bundle-default-version/26968617568/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/Dependabot-Auto-Merge-malwaredevil/26997648628/workflow_report.md` | kind=cleanup | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/Dependabot-auto-merge/26878217958/workflow_report.md` | kind=cleanup | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/Dependency-Review/26878217985/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/Dependency-Review-199/26881657577/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/Dependency-Review-200/26890449634/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/Dependency-Review-201/26894531331/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/Dependency-Review-202/26905621495/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/Dependency-Review-205/26933425228/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/Dependency-Review-206/26934880043/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/Dependency-Review-207/26943198706/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/Dependency-Review-221/26951433215/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/Dependency-Review-222/26965078218/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/Dependency-Review-228/26997648611/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/Full-Validation-FullRegression/26968628691/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/Full-Validation-Tier2BoundedCollect/27004618005/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/Gemini-Agent-Bundle-default-version-skip_validation-false/26968608438/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/Gemini-Production-Like-Harness-event-default/26944338731/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/Main-Push-Validation-codex-204-knowledge-index-boundary/26933420799/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/Main-Push-Validation-issue-194-bundled-workflow-modularization/26881656322/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/Main-Push-Validation-issue-194-direct-delivery-zip-artifact/26890478883/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/Main-Push-Validation-issue-194-post-merge-validate-on-pr/26894519874/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/Main-Push-Validation-issue-204-redo-knowledge-index-removal/26943197078/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/Main-Push-Validation-issue-209-override-manifest/26951363209/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/Main-Push-Validation-issue-209-single-definition-refactor-clean/26965076675/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/Main-Push-Validation-issue-210-runtime-error-handling/26997647224/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/Main-Push-Validation-issue197-intake-normalization/26905622810/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/Main-Push-Validation-main/26968541093/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/Main-Push-Validation-revert-pr-205-restore-pre-codex-fix/26934879055/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/Publish-Knowledge-to-Wiki/26839826167/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/Publish-Knowledge-to-Wiki-main/26944338164/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/Pull-Request-Validation-PR/26997648621/workflow_report.md` | kind=cleanup | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/Report-Retention-Cleanup-dry_run-false/26983351778/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/Test-Framework-Validation/26880366232/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/Validate-Gemini-Behavioral-Replay-pull_request/26881657448/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/Validate-Gemini-Behavioral-Replay-push/26880366256/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/Workflow-Audit-pull_request/26967098685/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/Workflow-Audit-push/26968541119/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/Workflow-Reporting-Validation-pull_request/26881657432/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/Workflow-Reporting-Validation-push/26881574394/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/Workflow-maintenance-audit/26878217939/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/chatgpt-github-artifact-readback/26597897521/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/chatgpt-workflow-reporting-validation/26878217912/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/collector-documentation-quality/26878217941/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/manual-collector-runtime-package-build/26877665423/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/manual-full-validation/26836396823/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/manual-gemini-bundle-build/26877763489/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/manual-gemini-model-comparison/26574890838/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/manual-test-framework-validate/26869677123/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/run-gemini-behavioral-replay-manual/26720756206/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/scheduled-health-check/26743095072/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/validate-gemini-behavioral-replay/26878217962/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/validate-gemini-production-like-harness/26878217914/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/validate-on-pr/26878217933/workflow_report.md` | kind=cleanup | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/repo-workflows/validate-on-push/26872108138/workflow_report.md` | kind=success | age_days=37.7 | reason=latest report for workflow
- `.github/chatgpt_staging/status_reports/retention-cleanup/retention-cleanup-32191396436/workflow_report.md` | kind=success | age_days=1.0 | reason=age 1.0d < 2d

## Next ChatGPT action

Read this cleanup report, verify scoped deletion/readback when cleanup was not a dry run, then record governed work-item evidence if material. Do not use retention-cleanup reports for live workflow polling.
