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
| #306 project_sources/collector/powershell_function_reachability_report.json | True | success | dcoir_powershell_function_reachability_report_v1 | 170 |
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
| function_reachability | success | 170 functions; 166 literal referenced; 4 dynamic uncertain; coverage not_collected |
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
- Total PowerShell surfaces: `246`

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
| chatgpt_staging/exec_scripts/exec-20260625-pr312-dcoir-review-fixes-008.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260626-dcoir-review-fix-synthesis-002.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260626-dcoir-review-fix-synthesis-003.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260626-dcoir-review-fix-synthesis-004.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260626-dcoir-review-fix-synthesis-005.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260626-dcoir-review-fix-synthesis-006.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260626-dcoir-review-hybrid-main-001.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260626-dcoir-review-hybrid-main-002.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260626-dcoir-review-hybrid-main-003.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260626-dcoir-review-hybrid-main-004.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260626-dcoir-review-hybrid-main-005.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260626-dcoir-review-hybrid-main-006.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260626-dcoir-review-hybrid-main-007.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260626-dcoir-review-hybrid-main-008.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260627-dcoir-review-summary-negation-main-001.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/exec-20260627-pr316-dcoir-review-gate-fixes-001.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/gemini_generated_prime_migration_001.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/issue197_label_cleanup.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/pr281_escaped_quoted_auth_redaction_002.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/pr281_escaped_quoted_auth_redaction_003.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/pr281_escaped_quoted_auth_redaction_004.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/pr281_escaped_quoted_auth_redaction_005.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| chatgpt_staging/exec_scripts/update_gemini_prime_chunk_checksum_001.ps1 | ChatGPT staging scripts are historical execution artifacts, not maintained source. |

### Reference Paths

| Path | Reason |
| --- | --- |
| .github/actions/assemble-collector-harness/action.yml | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| .github/actions/build-collector-runtime-for-harness/action.yml | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| .github/actions/run-collector-documentation-quality/action.yml | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| .github/actions/run-collector-runtime-package-validation/action.yml | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| .github/actions/run-duplicate-function-check/action.yml | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| .github/actions/run-powershell-review-assist/action.yml | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| .github/actions/run-psscriptanalyzer/action.yml | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| .github/actions/run-validate-dcoir-fixtures/action.yml | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| .github/actions/smoke-build-collector-package/action.yml | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| .github/actions/smoke-build-gemini-bundle/action.yml | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| .github/actions/validate-powershell-syntax/action.yml | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| .github/actions/validate-python-syntax/action.yml | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| .github/actions/verify-required-surfaces/action.yml | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| .github/workflows/reusable-chatgpt-apply-in.yml | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| .github/workflows/reusable-chatgpt-exec.yml | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| .github/workflows/reusable-chatgpt-stage-out.yml | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| .github/workflows/reusable-chatgpt-workflow-run-reporter.yml | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| .github/workflows/reusable-collector-documentation-quality.yml | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| .github/workflows/reusable-collector-runtime-package-build.yml | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| .github/workflows/reusable-collector-validation.yml | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| .github/workflows/reusable-gemini-bundle-build.yml | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| .github/workflows/reusable-manual-collector-optional-exe-build.yml | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| .github/workflows/reusable-manual-github-artifact-readback.yml | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| .github/workflows/reusable-manual-test-framework-validate.yml | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| .github/workflows/reusable-validate-on-pr.yml | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| .github/workflows/reusable-validate-on-push.yml | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| .github/workflows/reusable-windows-powershell-51.yml | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| project_sources/collector/fixtures/powershell_analysis/bad/analyzer_skip_success.ps1 | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| project_sources/collector/fixtures/powershell_analysis/bad/broad_baseline.ps1 | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| project_sources/collector/fixtures/powershell_analysis/bad/fail_row_green_exit.ps1 | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| project_sources/collector/fixtures/powershell_analysis/bad/invoke_expression.ps1 | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| project_sources/collector/fixtures/powershell_analysis/bad/plaintext_password.ps1 | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| project_sources/collector/fixtures/powershell_analysis/bad/plaintext_securestring.ps1 | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| project_sources/collector/fixtures/powershell_analysis/bad/source_part_drift.ps1 | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| project_sources/collector/fixtures/powershell_analysis/bad/state_changing_function.ps1 | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| project_sources/collector/fixtures/powershell_analysis/bad/swallowed_catch.ps1 | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| project_sources/collector/fixtures/powershell_analysis/bad/unbounded_event_query.ps1 | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| project_sources/collector/fixtures/powershell_analysis/bad/unchecked_external_exit.ps1 | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| project_sources/collector/fixtures/powershell_analysis/bad/unsafe_wildcard_delete.ps1 | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| project_sources/collector/fixtures/powershell_analysis/bad/unused_variable.ps1 | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| project_sources/collector/fixtures/powershell_analysis/bad/write_host.ps1 | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| project_sources/collector/fixtures/powershell_analysis/good/clean_control.ps1 | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| project_sources/collector/fixtures/powershell_analysis/good/custom_analyzer_skip_fails_closed.ps1 | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| project_sources/collector/fixtures/powershell_analysis/good/custom_bounded_event_query.ps1 | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| project_sources/collector/fixtures/powershell_analysis/good/custom_catch_rethrows.ps1 | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| project_sources/collector/fixtures/powershell_analysis/good/custom_external_exit_checked.ps1 | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| project_sources/collector/fixtures/powershell_analysis/good/custom_fail_row_fails_command.ps1 | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| project_sources/collector/fixtures/powershell_analysis/good/custom_fingerprint_bound_baseline.ps1 | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| project_sources/collector/fixtures/powershell_analysis/good/custom_safe_root_delete.ps1 | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| project_sources/collector/fixtures/powershell_analysis/good/custom_source_part_current.ps1 | Fixture/example PowerShell is inventoried separately from maintained source targets. |

### Skipped Paths

| Path | Reason |
| --- | --- |
| none | none reported |

## Baseline And Suppression

- Baseline records: `0`
- Matched baseline records: `0`
- Suppressions: `0`
- Matched suppressions: `0`

## Source And Generated Parity

- `compiled_runtime/DCOIR_Collector.ps1`: mapping `available`, parse `True`, parity `pass`
- `project_sources/collector/harness/run_DCOIR_Tests.generated.ps1`: mapping `available`, parse `True`, parity `pass`

## Warnings, Missing Artifacts, And Non-Claims

### Carried Forward Warnings

- #265 `project_sources/collector/powershell_assembly_parity_report.json`: no baseline parity report supplied; shrink checks used current inventory controls only
- #266 `project_sources/collector/powershell_finding_governance_report.json`: optional PowerShell finding report not present: project_sources/collector/powershell_analyzer_report.json
- #267 `project_sources/collector/powershell_engine_pester_boundary_report.json`: workflow readiness remains a later explicit gate; #267 only defines evidence ownership
- #267 `project_sources/collector/powershell_engine_pester_boundary_report.json`: Windows PowerShell 5.1 runtime evidence remains separate from local static report generation
- #267 `project_sources/collector/powershell_engine_pester_boundary_report.json`: engine matrix row powershell-7-psscriptanalyzer artifact is not committed or claimed by this #267 boundary: project_sources/collector/powershell_analyzer_report.json
- #262 `project_sources/collector/powershell_analyzer_report.json`: optional analyzer evidence is absent; #268 does not claim live PSScriptAnalyzer evidence
- #267 `project_sources/collector/powershell_engine_pester_boundary_report.json`: workflow or local Windows PowerShell 5.1 validation report: external_or_future is not claimed by #267/#268
- #267 `project_sources/collector/powershell_engine_pester_boundary_report.json`: project_sources/collector/powershell_analyzer_report.json: not_committed_in_267_boundary is not claimed by #267/#268
- #267 `project_sources/collector/powershell_engine_pester_boundary_report.json`: future Pester test result artifact when a later gate enables it: external_or_future is not claimed by #267/#268
- #263 `project_sources/collector/powershell_rule_risk_fixture_report.json`: This #263 harness uses a deterministic local fixture analyzer through the #262 wrapper. It intentionally does not execute PSScriptAnalyzer, so this fixture report does not claim whether pwsh or the PSScriptAnalyzer module is installed in the current environment.

### Missing Artifacts

- #262 `project_sources/collector/powershell_analyzer_report.json`: optional analyzer evidence is absent; #268 does not claim live PSScriptAnalyzer evidence

### Unclaimed Artifacts

- #267 `workflow or local Windows PowerShell 5.1 validation report`: Declared by #267 boundary but not committed, not claimed, external, or future evidence.
- #267 `project_sources/collector/powershell_analyzer_report.json`: Declared by #267 boundary but not committed, not claimed, external, or future evidence.
- #267 `future Pester test result artifact when a later gate enables it`: Declared by #267 boundary but not committed, not claimed, external, or future evidence.

### Non-Claims

- No workflow YAML was changed by #268.
- No SARIF file is generated or uploaded by #268.
- No GitHub code-scanning alert or required-check behavior is enabled by #268.
- No workflow artifact retention behavior is configured by #268.
- No Pester result is promoted to blocking static-validation evidence by #268.
- No changed-file execution, path-filter behavior, PR-diff coverage, or changed-file gating is claimed by #268.
- No live PSScriptAnalyzer evidence is claimed when the #262 analyzer report is absent.
- No Windows PowerShell 5.1 runtime validation is claimed by #268.
- No #269, #270, PR/workflow readiness, or parent #260 closeability claim is made by #268.
- No function deletion readiness or dead-code removal claim is made by #306 reachability reporting.

## Artifact Contract

- JSON: `project_sources/collector/powershell_review_assist_report.json`
- Markdown: `project_sources/collector/powershell_review_assist_report.md`
- Retention scope: local committed report artifacts only; workflow artifact retention remains a later explicit gate

## Validation

