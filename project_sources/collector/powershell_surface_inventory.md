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
| `collector_harness_source_part` | 18 |
| `collector_runtime_source_part` | 43 |
| `collector_runtime_wrapper` | 1 |
| `collector_validation_tooling` | 2 |
| `fixture_or_example` | 23 |
| `generated_or_assembled_output` | 1 |
| `github_workflow_support_script` | 23 |
| `invalid_workflow_surface` | 0 |
| `missing_authoritative_surface` | 0 |
| `missing_changed_powershell_surface` | 0 |
| `missing_changed_workflow_surface` | 0 |
| `operator_tooling` | 40 |
| `staging_artifact` | 196 |
| `unclassified_powershell_surface` | 0 |
| `validation_tooling` | 2 |
| `workflow_embedded_powershell` | 30 |

## Counts By Source Type

| Source Type | Count |
| --- | ---: |
| `.ps1` | 334 |
| `.ps1.txt` | 0 |
| `.ps1xml` | 0 |
| `.psd1` | 9 |
| `.psm1` | 10 |
| `workflow_yaml` | 30 |

## Counts By Inclusion Decision

| Decision | Count |
| --- | ---: |
| `exclude` | 196 |
| `include` | 133 |
| `reference` | 54 |

## Control Totals

- Collector manifest expected paths: `44`
- Collector manifest present paths: `44`
- Harness source parts: `18`
- Profile-required harness source parts: `18`
- Profile-required harness source parts present: `18`
- Embedded workflow/action snippets: `120`

## Reference And Excluded Surfaces

| Path | Category | Decision | Reason |
| --- | --- | --- | --- |
| `.github/actions/assemble-collector-harness/action.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `.github/actions/build-collector-runtime-for-harness/action.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `.github/actions/run-collector-documentation-quality/action.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `.github/actions/run-collector-runtime-package-validation/action.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `.github/actions/run-dcoir-pester/action.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `.github/actions/run-duplicate-function-check/action.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `.github/actions/run-path-safety-selftests/action.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `.github/actions/run-powershell-review-assist/action.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `.github/actions/run-psscriptanalyzer/action.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `.github/actions/run-validate-dcoir-fixtures/action.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `.github/actions/smoke-build-collector-package/action.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `.github/actions/smoke-build-gemini-bundle/action.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `.github/actions/validate-powershell-syntax/action.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `.github/actions/validate-python-syntax/action.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `.github/actions/verify-required-surfaces/action.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `.github/chatgpt_staging/exec_scripts/airtable-total-count-corrected-20260521T100417Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/chatgpt-exec-failure-semantics-validation-20260831T132700Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/chatgpt-exec-powershell-exit-diagnostic-20260831T140800Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/dcoir-review-fix-guidance-normalization-20260627T120800Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/dcoir-review-fix-guidance-normalization-20260627T121000Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/dcoir-review-fix-guidance-normalization-20260627T121700Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/dcoir-review-fix-guidance-normalization-20260627T122700Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/dcoir-review-fix-guidance-normalization-20260627T123500Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/dcoir-review-fix-guidance-normalization-20260627T124000Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/dcoir-review-v30-validation-20260830T141500Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/dcoir-review-v39-codeql-dispatch-20260831T123800Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/dcoir-review-v39-focused-validation-20260831T123200Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/dcoir-review-v39-full-validation-20260831T123600Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/dcoir-review-v40-focused-validation-20260831T132100Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/dcoir-review-v40-full-validation-20260831T132300Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260519-wbs04-four-table-export-002.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260519-wbs04-four-table-export-003.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260519-wbs04-merge-delete-batch1-export-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260519-wbs04-next-cleanup-export-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260519-wbs04-post-first-four-export-002.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260519-wbs04-remaining-normalization-export-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260520-wbs04-merge-delete-batch2-export-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260520-wbs04-merge-delete-batch3-export-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260520-wbs06-aggressive-rename-candidates-batch2-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260520-wbs06-aggressive-rename-candidates-batch3-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260520-wbs06-field-rename-apply-batch1-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260520-wbs06-field-rename-apply-batch2-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260520-wbs06-final-verify-retirement-packet-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260520-wbs06-rename-ledger-dryrun-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260618-pr281-codex-p1-redaction-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260618-pr281-codex-p1-redaction-002.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260618-pr281-codex-p1-redaction-003.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260618-pr281-codex-p1-redaction-004.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260618-pr281-codex-p1-redaction-005.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260618-pr281-codex-p1-redaction-006.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260618-pr281-codex-p1-redaction-008.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260618-pr281-codex-p1-redaction-009.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260618-pr281-codex-p1-redaction-010.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260618-pr281-codex-p1-redaction-011.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260624-issue306-function-reachability-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260624-issue306-function-reachability-002.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260625-pr312-dcoir-review-fixes-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260625-pr312-dcoir-review-fixes-002.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260625-pr312-dcoir-review-fixes-003.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260625-pr312-dcoir-review-fixes-004.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260625-pr312-dcoir-review-fixes-005.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260625-pr312-dcoir-review-fixes-006.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260625-pr312-dcoir-review-fixes-007.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260625-pr312-dcoir-review-fixes-008.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260626-dcoir-review-fix-synthesis-002.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260626-dcoir-review-fix-synthesis-003.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260626-dcoir-review-fix-synthesis-004.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260626-dcoir-review-fix-synthesis-005.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260626-dcoir-review-fix-synthesis-006.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260626-dcoir-review-hybrid-main-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260626-dcoir-review-hybrid-main-002.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260626-dcoir-review-hybrid-main-003.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260626-dcoir-review-hybrid-main-004.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260626-dcoir-review-hybrid-main-005.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260626-dcoir-review-hybrid-main-006.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260626-dcoir-review-hybrid-main-007.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260626-dcoir-review-hybrid-main-008.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260627-dcoir-review-summary-negation-main-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260627-pr316-dcoir-review-gate-fixes-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260701-issue349-harness-part004-evidence-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260701-issue349-harness-part004-evidence-002.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/exec-20260701-issue349-harness-part004-evidence-003.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/gemini_generated_prime_migration_001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue197_label_cleanup.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue421_dcoir_path_hardening.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue421_delivery_root_safety_fix.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue421_delivery_root_safety_fix_v2.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue421_openai_bundle_governance_and_validation.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue421_openai_bundle_governance_and_validation_v2.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue421_openai_bundle_governance_and_validation_v3.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue428_openai_version_paste_safe.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue428_openai_version_paste_safe_v2.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue428_openai_version_paste_safe_v3.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue457-obsolete-branch-cleanup-20260907.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue457-pr493-credit-aware-exact-head-validation-20260907.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue457-pr493-credit-aware-exact-head-validation-rerun1-20260907.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue457-pr493-credit-aware-exact-head-validation-rerun2-20260907.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue457-pr493-credit-aware-exact-head-validation-rerun3-20260907.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue480-postmerge-validation-20260905.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue482-pr483-exact-head-validation-20260905.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue484-pr501-codi-boundary-hardening-20260908T0955Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue484-pr501-codi-exclusion-fix-20260908T0950Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue484-pr501-dcoir-findings-fix-v2.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue484-pr501-dcoir-findings-fix-v3.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue484-pr501-postdcoir-exact-head-validation-v1.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue485-pr486-corpus-fix-validation-20260905.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue485-pr486-exact-head-validation-20260905.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue485-pr486-paid-screen-20260905.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue496-pr498-verified-gate-exact-head-validation-v2-20260907.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue496-pr498-verified-gate-exact-head-validation-v3-20260907.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue496-pr498-verified-gate-exact-head-validation-v4-20260907.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue496-pr498-verified-gate-exact-head-validation-v5-20260907.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue496-pr498-verified-gate-exact-head-validation-v6-20260907.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue496-pr498-verified-gate-exact-head-validation-v7-20260907.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue497-pr499-candidate-identity-exact-head-validation-v1-20260907.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue515-pr516-exact-head-validation-v1-20260909T1048Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue515-pr516-exact-head-validation-v2-20260909T1057Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue515-pr516-exact-head-validation-v3-20260909T1141Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue517-pr518-exact-head-validation-v1-20260909T1248Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue517-pr518-exact-head-validation-v2-20260909T1303Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue517-pr518-exact-head-validation-v3-20260909T1310Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue517-pr518-fix-regressions-v3-20260909T1306Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue517-pr518-fix-v52-ordering-20260909T1253Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue517-pr518-fix-v52-ordering-v2-20260909T1258Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue517-pr518-v53-composition-diagnostic-20260909T1302Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue519-pr520-copilot-final-fixes-v1-20260910T0600Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue519-pr520-exact-head-validation-v1-20260909T1825Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue519-pr520-exact-head-validation-v2-20260909T1855Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue519-pr520-exact-head-validation-v3-20260909T1858Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue519-pr520-exact-head-validation-v4-20260909T1903Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue519-pr520-exact-head-validation-v5-20260909T1906Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue519-pr520-exact-head-validation-v6-20260910T0610Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue519-pr520-exact-head-validation-v7-20260910T0613Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue519-pr520-exact-head-validation-v8-20260910T0710Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue519-pr520-failsoft-hardening-v1-20260909T1852Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue519-pr520-ghas-empty-except-fix-v1-20260909T1902Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue519-targeted-validation-v1-20260909T1809Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue519-targeted-validation-v2-20260909T1822Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue524-pr525-exact-head-validation-v1-20260910T0918Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue524-pr525-exact-head-validation-v3-20260910T1032Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue526-pr527-round2-exact-head-validation-20260910T1318Z.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue546-pr547-exact-head-validation-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue546-pr547-exact-head-validation-002.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue548-pr549-exact-head-validation-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue548-pr549-exact-head-validation-002.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue548-pr549-http-error-body-validation-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue548-pr549-http-error-body-validation-002.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue548-pr549-response-read-regression-fix-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue548-pr549-response-read-regression-fix-002.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue548-pr549-v55-ordering-repair-validation-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue550-pr553-first-patch-retirement-validation-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue550-pr553-first-patch-retirement-validation-002.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue550-pr553-first-patch-retirement-validation-003.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue550-pr553-first-patch-retirement-validation-004.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue550-pr553-function-ownership-audit-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue550-pr553-function-ownership-audit-002.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue550-pr553-ghas-review-scope-cycle-validation-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue550-pr553-repair-consolidation-validation-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue550-pr553-repair-consolidation-validation-002.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue550-pr553-repair-consolidation-validation-003.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue550-pr553-repair-consolidation-validation-004.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue550-pr553-repair-consolidation-validation-005.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue550-pr553-status-cutover-validation-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue550-pr553-v15-finding-family-validation-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue550-pr553-v19-precision-guard-validation-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue550-pr553-v19-recovery-exact-head-validation-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue550-pr553-v19-recovery-exact-head-validation-002.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue550-pr553-v21-finding-verifier-validation-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue550-pr553-v22-quality-gate-validation-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue550-pr553-v23-normalized-finding-selection-validation-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue550-pr553-v24-verified-finding-render-validation-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue550-pr553-v26-sentinel-selection-validation-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue550-pr553-v28-retirement-validation-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue550-pr553-v28-retirement-validation-002.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue550-pr553-v34-semantic-evidence-hardening-validation-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue550-pr553-v37-semantic-adjudication-normalization-validation-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue550-pr553-v37-semantic-adjudication-normalization-validation-002.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue550-pr553-v38-repair-contract-validation-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue550-pr553-v39-semantic-adjudication-confidence-validation-002.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue550-pr553-v41-incremental-review-frontier-validation-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue550-pr553-v42-semantic-review-ledger-validation-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue550-pr553-v43-semantic-result-reuse-validation-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue550-pr553-v45-publication-disposition-validation-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue550-pr553-v47-per-file-routing-validation-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue550-pr553-v48-prompt-review-scope-guard-validation-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue550-pr553-v48-review-scope-guard-validation-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue550-pr553-v50-verified-finding-gate-validation-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue550-pr553-v51-semantic-candidate-identity-validation-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue550-pr553-v52-structured-result-recovery-validation-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue550-pr553-v55-semantic-adjudication-validation-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue550-pr553-v55-semantic-adjudication-validation-002.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue550-pr553-v55-semantic-adjudication-validation-003.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue550-pr553-v58-provider-transport-retry-validation-001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/issue550-pr553-v58-provider-transport-retry-validation-003.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/openrouter-analytics-issue464-cache-potential.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/openrouter-analytics-issue464-enhanced.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/openrouter-analytics-issue464-generation-cache.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/openrouter-analytics-issue464-grouped.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/openrouter-analytics-issue464.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/openrouter-analytics-issue478-live-benchmark.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/openrouter-analytics-issue478-successful-replay.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/pr281_escaped_quoted_auth_redaction_002.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/pr281_escaped_quoted_auth_redaction_003.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/pr281_escaped_quoted_auth_redaction_004.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/pr281_escaped_quoted_auth_redaction_005.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/pr423_exact_head_validation_017.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/pr423_exact_head_validation_018.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/pr423_resolver_symlink_hardening_014.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/pr423_resolver_symlink_hardening_015.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/pr423_resolver_symlink_hardening_016.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
| `.github/chatgpt_staging/exec_scripts/update_gemini_prime_chunk_checksum_001.ps1` | `staging_artifact` | `exclude` | ChatGPT staging scripts are historical execution artifacts, not maintained source. |
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
| `.github/workflows/reusable-openai-gpt-deployment-package-build.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `.github/workflows/reusable-validate-on-pr.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `.github/workflows/reusable-validate-on-push.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
| `.github/workflows/reusable-windows-powershell-51.yml` | `workflow_embedded_powershell` | `reference` | Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling. |
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
