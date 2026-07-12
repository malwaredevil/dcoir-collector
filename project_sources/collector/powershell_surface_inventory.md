# PowerShell Surface Inventory

- Schema: `dcoir_powershell_surface_inventory_v1`
- Issue: #261
- Mode: `full`
- Source of truth: `git ls-files -z`
- File facts policy: `text_bytes_with_line_endings_normalized_to_lf`
- Discovery command: `python project_sources/collector/tools/build_powershell_surface_inventory.py --repo-root . --json-output project_sources/collector/powershell_surface_inventory.json --markdown-output project_sources/collector/powershell_surface_inventory.md`
- JSON artifact: `project_sources/collector/powershell_surface_inventory.json`
- Validation: `pass`

## Counts By Category

| Category | Count |
| --- | ---: |
| `archive_temp_vendor_artifact` | 0 |
| `collector_harness_script` | 4 |
| `collector_harness_source_part` | 17 |
| `collector_runtime_source_part` | 43 |
| `collector_runtime_wrapper` | 1 |
| `collector_validation_tooling` | 2 |
| `fixture_or_example` | 23 |
| `generated_or_assembled_output` | 1 |
| `github_workflow_support_script` | 20 |
| `invalid_workflow_surface` | 0 |
| `missing_authoritative_surface` | 0 |
| `missing_changed_powershell_surface` | 0 |
| `missing_changed_workflow_surface` | 0 |
| `operator_tooling` | 36 |
| `staging_artifact` | 66 |
| `unclassified_powershell_surface` | 0 |
| `validation_tooling` | 3 |
| `workflow_embedded_powershell` | 27 |

## Counts By Source Type

| Source Type | Count |
| --- | ---: |
| `.ps1` | 180 |
| `.ps1.txt` | 17 |
| `.ps1xml` | 0 |
| `.psd1` | 9 |
| `.psm1` | 10 |
| `workflow_yaml` | 27 |

## Counts By Inclusion Decision

| Decision | Count |
| --- | ---: |
| `exclude` | 66 |
| `include` | 126 |
| `reference` | 51 |

## Control Totals

- Collector manifest expected paths: `44`
- Collector manifest present paths: `44`
- Harness source parts: `17`
- Profile-required harness source parts: `17`
- Profile-required harness source parts present: `17`
- Embedded workflow/action snippets: `80`

## Reference And Excluded Surfaces

| Path | Category | Decision | Reason |
| --- | --- | --- | --- |
| `.github/actions/assemble-collector-harness/action.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `.github/actions/build-collector-runtime-for-harness/action.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `.github/actions/run-collector-documentation-quality/action.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `.github/actions/run-collector-runtime-package-validation/action.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `.github/actions/run-duplicate-function-check/action.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `.github/actions/run-powershell-review-assist/action.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `.github/actions/run-psscriptanalyzer/action.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `.github/actions/run-validate-dcoir-fixtures/action.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `.github/actions/smoke-build-collector-package/action.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `.github/actions/smoke-build-gemini-bundle/action.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `.github/actions/validate-powershell-syntax/action.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `.github/actions/validate-python-syntax/action.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `.github/actions/verify-required-surfaces/action.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `.github/workflows/reusable-chatgpt-apply-in.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `.github/workflows/reusable-chatgpt-exec.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `.github/workflows/reusable-chatgpt-stage-out.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `.github/workflows/reusable-chatgpt-workflow-run-reporter.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `.github/workflows/reusable-collector-documentation-quality.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `.github/workflows/reusable-collector-runtime-package-build.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `.github/workflows/reusable-collector-validation.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `.github/workflows/reusable-gemini-bundle-build.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `.github/workflows/reusable-manual-collector-optional-exe-build.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `.github/workflows/reusable-manual-github-artifact-readback.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `.github/workflows/reusable-manual-test-framework-validate.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `.github/workflows/reusable-validate-on-pr.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `.github/workflows/reusable-validate-on-push.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `.github/workflows/reusable-windows-powershell-51.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `chatgpt_staging/exec_scripts/airtable-total-count-corrected-20260521T100417Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/dcoir-review-fix-guidance-normalization-20260627T120800Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/dcoir-review-fix-guidance-normalization-20260627T121000Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/dcoir-review-fix-guidance-normalization-20260627T121700Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/dcoir-review-fix-guidance-normalization-20260627T122700Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/dcoir-review-fix-guidance-normalization-20260627T123500Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/dcoir-review-fix-guidance-normalization-20260627T124000Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260519-wbs04-four-table-export-002.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260519-wbs04-four-table-export-003.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260519-wbs04-merge-delete-batch1-export-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260519-wbs04-next-cleanup-export-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260519-wbs04-post-first-four-export-002.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260519-wbs04-remaining-normalization-export-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260520-wbs04-merge-delete-batch2-export-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260520-wbs04-merge-delete-batch3-export-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260520-wbs06-aggressive-rename-candidates-batch2-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260520-wbs06-aggressive-rename-candidates-batch3-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260520-wbs06-field-rename-apply-batch1-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260520-wbs06-field-rename-apply-batch2-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260520-wbs06-final-verify-retirement-packet-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260520-wbs06-rename-ledger-dryrun-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260618-pr281-codex-p1-redaction-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260618-pr281-codex-p1-redaction-002.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260618-pr281-codex-p1-redaction-003.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260618-pr281-codex-p1-redaction-004.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260618-pr281-codex-p1-redaction-005.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260618-pr281-codex-p1-redaction-006.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260618-pr281-codex-p1-redaction-008.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260618-pr281-codex-p1-redaction-009.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260618-pr281-codex-p1-redaction-010.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260618-pr281-codex-p1-redaction-011.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260624-issue306-function-reachability-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260624-issue306-function-reachability-002.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260625-pr312-dcoir-review-fixes-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260625-pr312-dcoir-review-fixes-002.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260625-pr312-dcoir-review-fixes-003.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260625-pr312-dcoir-review-fixes-004.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260625-pr312-dcoir-review-fixes-005.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260625-pr312-dcoir-review-fixes-006.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260625-pr312-dcoir-review-fixes-007.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260625-pr312-dcoir-review-fixes-008.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260626-dcoir-review-fix-synthesis-002.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260626-dcoir-review-fix-synthesis-003.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260626-dcoir-review-fix-synthesis-004.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260626-dcoir-review-fix-synthesis-005.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260626-dcoir-review-fix-synthesis-006.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260626-dcoir-review-hybrid-main-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260626-dcoir-review-hybrid-main-002.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260626-dcoir-review-hybrid-main-003.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260626-dcoir-review-hybrid-main-004.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260626-dcoir-review-hybrid-main-005.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260626-dcoir-review-hybrid-main-006.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260626-dcoir-review-hybrid-main-007.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260626-dcoir-review-hybrid-main-008.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260627-dcoir-review-summary-negation-main-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260627-pr316-dcoir-review-gate-fixes-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260701-issue349-harness-part004-evidence-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260701-issue349-harness-part004-evidence-002.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/exec-20260701-issue349-harness-part004-evidence-003.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/gemini_generated_prime_migration_001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/issue197_label_cleanup.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/pr281_escaped_quoted_auth_redaction_002.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/pr281_escaped_quoted_auth_redaction_003.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/pr281_escaped_quoted_auth_redaction_004.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/pr281_escaped_quoted_auth_redaction_005.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `chatgpt_staging/exec_scripts/update_gemini_prime_chunk_checksum_001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `project_sources/collector/fixtures/powershell_analysis/bad/analyzer_skip_success.ps1` | `fixture_or_example` | `reference` | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| `project_sources/collector/fixtures/powershell_analysis/bad/broad_baseline.ps1` | `fixture_or_example` | `reference` | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| `project_sources/collector/fixtures/powershell_analysis/bad/fail_row_green_exit.ps1` | `fixture_or_example` | `reference` | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| `project_sources/collector/fixtures/powershell_analysis/bad/invoke_expression.ps1` | `fixture_or_example` | `reference` | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| `project_sources/collector/fixtures/powershell_analysis/bad/plaintext_password.ps1` | `fixture_or_example` | `reference` | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| `project_sources/collector/fixtures/powershell_analysis/bad/plaintext_securestring.ps1` | `fixture_or_example` | `reference` | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| `project_sources/collector/fixtures/powershell_analysis/bad/source_part_drift.ps1` | `fixture_or_example` | `reference` | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| `project_sources/collector/fixtures/powershell_analysis/bad/state_changing_function.ps1` | `fixture_or_example` | `reference` | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| `project_sources/collector/fixtures/powershell_analysis/bad/swallowed_catch.ps1` | `fixture_or_example` | `reference` | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| `project_sources/collector/fixtures/powershell_analysis/bad/unbounded_event_query.ps1` | `fixture_or_example` | `reference` | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| `project_sources/collector/fixtures/powershell_analysis/bad/unchecked_external_exit.ps1` | `fixture_or_example` | `reference` | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| `project_sources/collector/fixtures/powershell_analysis/bad/unsafe_wildcard_delete.ps1` | `fixture_or_example` | `reference` | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| `project_sources/collector/fixtures/powershell_analysis/bad/unused_variable.ps1` | `fixture_or_example` | `reference` | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| `project_sources/collector/fixtures/powershell_analysis/bad/write_host.ps1` | `fixture_or_example` | `reference` | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| `project_sources/collector/fixtures/powershell_analysis/good/clean_control.ps1` | `fixture_or_example` | `reference` | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| `project_sources/collector/fixtures/powershell_analysis/good/custom_analyzer_skip_fails_closed.ps1` | `fixture_or_example` | `reference` | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| `project_sources/collector/fixtures/powershell_analysis/good/custom_bounded_event_query.ps1` | `fixture_or_example` | `reference` | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| `project_sources/collector/fixtures/powershell_analysis/good/custom_catch_rethrows.ps1` | `fixture_or_example` | `reference` | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| `project_sources/collector/fixtures/powershell_analysis/good/custom_external_exit_checked.ps1` | `fixture_or_example` | `reference` | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| `project_sources/collector/fixtures/powershell_analysis/good/custom_fail_row_fails_command.ps1` | `fixture_or_example` | `reference` | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| `project_sources/collector/fixtures/powershell_analysis/good/custom_fingerprint_bound_baseline.ps1` | `fixture_or_example` | `reference` | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| `project_sources/collector/fixtures/powershell_analysis/good/custom_safe_root_delete.ps1` | `fixture_or_example` | `reference` | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| `project_sources/collector/fixtures/powershell_analysis/good/custom_source_part_current.ps1` | `fixture_or_example` | `reference` | Fixture/example PowerShell is inventoried separately from maintained source targets. |
| `project_sources/collector/source/parts/DCOIR_Collector.02_Baseline_Collection_And_Reports.ps1` | `generated_or_assembled_output` | `reference` | Superseded monolithic Part 02 pointer is documentation, not manifest-loaded runtime source. |

## Validation Findings

- No validation errors.
