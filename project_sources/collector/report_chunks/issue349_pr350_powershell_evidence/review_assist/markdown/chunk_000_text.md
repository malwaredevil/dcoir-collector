# PowerShell Review-Assist Report

- Schema: `dcoir_powershell_review_assist_report_v1`
- Issue: #268
- Parent issue: #260
- Validation: `pass`
- Normalized findings: `22`
- Optional analyzer state: `optional_missing`

## Summary

| Metric | Value |
| --- | ---: |
| required_source_report_count | 8 |
| required_source_reports_present | 8 |
| optional_source_reports_missing | 1 |
| normalized_finding_count | 22 |
| carried_forward_warning_count | 10 |
| missing_artifact_count | 1 |
| unclaimed_artifact_count | 3 |
| non_claim_count | 10 |

## Source Reports

| Report | Required | Status | Schema | Findings |
| --- | --- | --- | --- | ---: |
| #261 project_sources/collector/powershell_surface_inventory.json | True | success | dcoir_powershell_surface_inventory_v1 |  |
| #263 project_sources/collector/powershell_rule_risk_fixture_report.json | True | success | dcoir_powershell_rule_risk_fixture_report_v1 | 14 |
| #263 project_sources/collector/powershell_rule_risk_matrix.json | True | schema_only_success | dcoir_powershell_rule_risk_matrix_v1 |  |
| #264 project_sources/collector/powershell_custom_check_report.json | True | success | dcoir_powershell_custom_check_report_v1 | 8 |
| #265 project_sources/collector/powershell_assembly_parity_report.json | True | success | dcoir_powershell_assembly_parity_report_v1 |  |
| #266 project_sources/collector/powershell_finding_governance_report.json | True | success | dcoir_powershell_finding_governance_report_v1 | 22 |
| #267 project_sources/collector/powershell_engine_pester_boundary_report.json | True | success | dcoir_powershell_engine_pester_boundary_report_v1 |  |
| #306 project_sources/collector/powershell_function_reachability_report.json | True | success | dcoir_powershell_function_reachability_report_v1 | 171 |
| #262 project_sources/collector/powershell_analyzer_report.json | False | optional_missing | not present | 0 |

## Evidence Channels

| Channel | State | Key Evidence |
| --- | --- | --- |
| analyzer | optional_missing | live PSScriptAnalyzer evidence is not claimed unless this report is present and valid |
| deterministic_fixture_analyzer | success | 14 findings; This #263 harness uses a deterministic local fixture analyzer through the #262 wrapper. It intentionally does not execute PSScriptAnalyzer, so this fixture report does not claim whether pwsh or the PSScriptAnalyzer module is installed in the current environment. |
| custom_checks | success | 8 findings |
| assembly_parity | success | 2 generated outputs; pass |
| finding_governance | success | 0 baseline records; 0 suppressions |
| engine_boundary | success | 2 unclaimed blocking artifacts |
| function_reachability | success | 171 functions; 167 literal referenced; 4 dynamic uncertain; coverage not_collected |
| pester_boundary | supporting_non_blocking | Pester may support later runtime or wrapper evidence but is not blocking static-validation evidence in #268. |

## Findings

| Evidence | Severity | Rule/check | Path | Line | Governance |
| --- | --- | --- | --- | ---: | --- |
| deterministic_fixture_analyzer | Error | DCOIR.NoAnalyzerSkipSuccess | project_sources/collector/fixtures/powershell_analysis/bad/analyzer_skip_success.ps1 | 1 | advisory |
| deterministic_fixture_analyzer | Error | DCOIR.BaselineSuppressionMustBeFingerprintBound | project_sources/collector/fixtures/powershell_analysis/bad/broad_baseline.ps1 | 1 | advisory |
| deterministic_fixture_analyzer | Error | DCOIR.FailOutputMustFailValidation | project_sources/collector/fixtures/powershell_analysis/bad/fail_row_green_exit.ps1 | 2 | advisory |
| deterministic_fixture_analyzer | Warning | PSAvoidUsingInvokeExpression | project_sources/collector/fixtures/powershell_analysis/bad/invoke_expression.ps1 | 2 | advisory |
| deterministic_fixture_analyzer | Warning | PSAvoidUsingPlainTextForPassword | project_sources/collector/fixtures/powershell_analysis/bad/plaintext_password.ps1 | 2 | advisory |
| deterministic_fixture_analyzer | Warning | PSAvoidUsingConvertToSecureStringWithPlainText | project_sources/collector/fixtures/powershell_analysis/bad/plaintext_securestring.ps1 | 2 | advisory |
| deterministic_fixture_analyzer | Error | DCOIR.SourcePartAssemblyDrift | project_sources/collector/fixtures/powershell_analysis/bad/source_part_drift.ps1 | 2 | advisory |
| deterministic_fixture_analyzer | Warning | PSUseShouldProcessForStateChangingFunctions | project_sources/collector/fixtures/powershell_analysis/bad/state_changing_function.ps1 | 1 | advisory |
| deterministic_fixture_analyzer | Error | DCOIR.NoSwallowedCatch | project_sources/collector/fixtures/powershell_analysis/bad/swallowed_catch.ps1 | 4 | advisory |
| deterministic_fixture_analyzer | Error | DCOIR.BoundedEventQueryRequired | project_sources/collector/fixtures/powershell_analysis/bad/unbounded_event_query.ps1 | 2 | advisory |
| deterministic_fixture_analyzer | Error | DCOIR.CheckExternalCommandExit | project_sources/collector/fixtures/powershell_analysis/bad/unchecked_external_exit.ps1 | 2 | advisory |
| deterministic_fixture_analyzer | Error | DCOIR.NoUnsafeWildcardDeletion | project_sources/collector/fixtures/powershell_analysis/bad/unsafe_wildcard_delete.ps1 | 2 | advisory |
| deterministic_fixture_analyzer | Warning | PSUseDeclaredVarsMoreThanAssignments | project_sources/collector/fixtures/powershell_analysis/bad/unused_variable.ps1 | 2 | advisory |
| deterministic_fixture_analyzer | Warning | PSAvoidUsingWriteHost | project_sources/collector/fixtures/powershell_analysis/bad/write_host.ps1 | 2 | advisory |
| dcoir_custom_static_check | Error | DCOIR.NoAnalyzerSkipSuccess | project_sources/collector/fixtures/powershell_analysis/bad/analyzer_skip_success.ps1 | 1 | advisory |
| dcoir_custom_static_check | Error | DCOIR.BaselineSuppressionMustBeFingerprintBound | project_sources/collector/fixtures/powershell_analysis/bad/broad_baseline.ps1 | 1 | advisory |
| dcoir_custom_static_check | Error | DCOIR.FailOutputMustFailValidation | project_sources/collector/fixtures/powershell_analysis/bad/fail_row_green_exit.ps1 | 2 | advisory |
| dcoir_custom_static_check | Error | DCOIR.SourcePartAssemblyDrift | project_sources/collector/fixtures/powershell_analysis/bad/source_part_drift.ps1 | 2 | advisory |
| dcoir_custom_static_check | Error | DCOIR.NoSwallowedCatch | project_sources/collector/fixtures/powershell_analysis/bad/swallowed_catch.ps1 | 4 | advisory |
| dcoir_custom_static_check | Error | DCOIR.BoundedEventQueryRequired | project_sources/collector/fixtures/powershell_analysis/bad/unbounded_event_query.ps1 | 2 | advisory |
| dcoir_custom_static_check | Error | DCOIR.CheckExternalCommandExit | project_sources/collector/fixtures/powershell_analysis/bad/unchecked_external_exit.ps1 | 2 | advisory |
| dcoir_custom_static_check | Error | DCOIR.NoUnsafeWildcardDeletion | project_sources/collector/fixtures/powershell_analysis/bad/unsafe_wildcard_delete.ps1 | 2 | advisory |

## Inventory Decisions

- Full-scope inventory mode: `full`
- Total PowerShell surfaces: `249`

### Excluded Paths

| Path | Reason |
| --- | --- |
| chatgpt_staging/exec_scripts/airtable-total-count-corrected-20260521T100417Z.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/dcoir-review-fix-guidance-normalization-20260627T120800Z.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/dcoir-review-fix-guidance-normalization-20260627T121000Z.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/dcoir-review-fix-guidance-normalization-20260627T121700Z.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/dcoir-review-fix-guidance-normalization-20260627T122700Z.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/dcoir-review-fix-guidance-normalization-20260627T123500Z.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/dcoir-review-fix-guidance-normalization-20260627T124000Z.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260519-wbs04-four-table-export-002.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260519-wbs04-four-table-export-003.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260519-wbs04-merge-delete-batch1-export-001.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260519-wbs04-next-cleanup-export-001.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260519-wbs04-post-first-four-export-002.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260519-wbs04-remaining-normalization-export-001.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260520-wbs04-merge-delete-batch2-export-001.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260520-wbs04-merge-delete-batch3-export-001.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260520-wbs06-aggressive-rename-candidates-batch2-001.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260520-wbs06-aggressive-rename-candidates-batch3-001.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260520-wbs06-field-rename-apply-batch1-001.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260520-wbs06-field-rename-apply-batch2-001.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260520-wbs06-final-verify-retirement-packet-001.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260520-wbs06-rename-ledger-dryrun-001.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260618-pr281-codex-p1-redaction-001.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260618-pr281-codex-p1-redaction-002.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260618-pr281-codex-p1-redaction-003.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260618-pr281-codex-p1-redaction-004.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260618-pr281-codex-p1-redaction-005.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260618-pr281-codex-p1-redaction-006.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260618-pr281-codex-p1-redaction-008.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260618-pr281-codex-p1-redaction-009.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260618-pr281-codex-p1-redaction-010.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260618-pr281-codex-p1-redaction-011.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260624-issue306-function-reachability-001.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260624-issue306-function-reachability-002.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260625-pr312-dcoir-review-fixes-001.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260625-pr312-dcoir-review-fixes-002.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260625-pr312-dcoir-review-fixes-003.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260625-pr312-dcoir-review-fixes-004.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260625-pr312-dcoir-review-fixes-005.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260625-pr312-dcoir-review-fixes-006.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260625-pr312-dcoir-review-fixes-007.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
