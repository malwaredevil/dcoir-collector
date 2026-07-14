<#
.SYNOPSIS
Writes collector capability coverage artifacts.

.DESCRIPTION
Serializes the accumulated capability coverage rows to reusable JSON and Markdown files
for #187 audit readback and future drift checks.

.FUNCTION NAME
Write-CapabilityCoverageFiles

.INPUTS
No direct parameters; reads script-level coverage rows and output paths.

.OUTPUTS
No direct output. Writes collector_capability_coverage.json and .md.
#>
function Write-CapabilityCoverageFiles {
  $obj = [pscustomobject]@{
    schema_version = 'dcoir_collector_capability_coverage_v1'
    suite = $Suite
    generated_at = (Get-Date).ToString('o')
    collector_path = $CollectorFullPath
    test_run_output = $RunOutputRoot
    coverage_classes = @('covered_end_to_end_by_fullregression','covered_by_harness_not_manual','covered_by_package_validation_not_manual','covered_synthetically_only','partial','not_covered','out_of_scope_with_reason')
    rows = @($script:CoverageRows)
  }
  $obj | ConvertTo-Json -Depth 8 | Set-Content -Path $CoverageJsonPath -Encoding UTF8

  $lines = @('# DCOIR Collector Capability Coverage', '', ('Suite: {0}' -f $Suite), ('Generated: {0}' -f (Get-Date).ToString('o')), '', '| Capability | Coverage | Status | Risk | Operator Value | Evidence | Remaining Gap |', '| --- | --- | --- | --- | --- | --- | --- |')
  foreach ($row in @($script:CoverageRows)) {
    $evidence = (@($row.evidence_artifacts) -join '<br>')
    $gap = if ([string]::IsNullOrWhiteSpace($row.remaining_gap)) { '' } else { $row.remaining_gap }
    $lines += ('| `{0}` | {1} | {2} | {3} | {4} | {5} | {6} |' -f $row.capability_id, $row.coverage_class, $row.status, $row.risk, $row.operator_value, $evidence, ($gap -replace '\|','/'))
  }
  Set-Content -Path $CoverageMdPath -Value $lines -Encoding UTF8
}

<#
.SYNOPSIS
Finalizes and saves collector capability coverage output.

.DESCRIPTION
Builds coverage rows, writes coverage artifacts, then rechecks the coverage-matrix row
after artifacts exist so the matrix artifact can be marked covered when valid.

.FUNCTION NAME
Save-CapabilityCoverage

.INPUTS
No direct parameters.

.OUTPUTS
No direct output. Writes coverage artifacts and updates in-memory coverage rows.
#>
function Save-CapabilityCoverage {
  Add-CollectorCapabilityCoverageRows
  Write-CapabilityCoverageFiles
  foreach ($row in @($script:CoverageRows)) {
    if ($row.capability_id -eq 'collector.coverage.matrix_artifact' -and (Test-CoverageArtifactEvidence -CapabilityId $row.capability_id)) {
      $row.status = 'covered'
      $row.remaining_gap = ''
    }
  }
  Write-CapabilityCoverageFiles
}

<#
.SYNOPSIS
Writes the suite summary text and JSON files.

.DESCRIPTION
Builds the final summary text and JSON objects from the accumulated harness results and
writes them into the current test-run output directory.

.FUNCTION NAME
Save-Summary

.INPUTS
No direct parameters.

.OUTPUTS
No direct output. Writes summary.txt and summary.json.
#>
function Save-Summary {
  Ensure-Directory -Path $RunOutputRoot
  $summaryTxtPath = Join-Path $RunOutputRoot "summary.txt"
  $summaryJsonPath = Join-Path $RunOutputRoot "summary.json"
  $lines = @()
  $lines += ("SUITE={0}" -f $Suite)
  $lines += ("LIVE_RESPONSE_MODE={0}" -f $LiveResponseMode)
  $lines += ("PROJECT_ROOT={0}" -f $ProjectRoot)
  $lines += ("COLLECTOR_PATH={0}" -f $CollectorFullPath)
  $lines += ("COLLECTOR_INVOCATION_MODE={0}" -f $script:ResolvedCollectorInvocationMode)
  $lines += ("MASTER_ZIP={0}" -f $MasterZipFullPath)
  $lines += ("WORKING_ZIP={0}" -f $WorkingZipPath)
  $lines += ("TEST_RUN_OUTPUT={0}" -f $RunOutputRoot)
  $lines += ("LATEST_RUN_ID={0}" -f $script:CollectorRunId)
  Save-CapabilityCoverage
  $lines += ("LATEST_ENRICH_SESSION_ID={0}" -f $script:CollectorSessionId)
  $lines += ("PROGRESS_JSONL_PATH={0}" -f $ProgressJsonlPath)
  $lines += ("PROGRESS_TXT_PATH={0}" -f $ProgressTxtPath)
  $lines += ("EVIDENCE_ROOT={0}" -f $EvidenceRoot)
  $lines += ("CAPABILITY_COVERAGE_JSON_PATH={0}" -f $CoverageJsonPath)
  $lines += ("CAPABILITY_COVERAGE_MD_PATH={0}" -f $CoverageMdPath)
  $lines += ""
  foreach ($r in $script:Results) {
    if ($r.CollectorReportedStatus) {
      $lines += ("STEP={0} STATUS={1} EXIT_CODE={2} COLLECTOR_STATUS={3} LOG={4}" -f $r.StepName, $r.Status, $r.ExitCode, $r.CollectorReportedStatus, $r.LogPath)
    } else {
      $lines += ("STEP={0} STATUS={1} EXIT_CODE={2} LOG={3}" -f $r.StepName, $r.Status, $r.ExitCode, $r.LogPath)
    }
  }
  Set-Content -Path $summaryTxtPath -Value $lines -Encoding UTF8
  $summaryObj = [pscustomobject]@{
    Suite = $Suite
    LiveResponseMode = [bool]$LiveResponseMode
    ProjectRoot = $ProjectRoot
    CollectorPath = $CollectorFullPath
    CollectorInvocationMode = $script:ResolvedCollectorInvocationMode
    MasterZip = $MasterZipFullPath
    WorkingZip = $WorkingZipPath
    TestRunOutput = $RunOutputRoot
    LatestRunId = $script:CollectorRunId
    LatestEnrichSessionId = $script:CollectorSessionId
    ProgressJsonlPath = $ProgressJsonlPath
    ProgressTxtPath = $ProgressTxtPath
    EvidenceRoot = $EvidenceRoot
    CapabilityCoverageJsonPath = $CoverageJsonPath
    CapabilityCoverageMdPath = $CoverageMdPath
    Results = @($script:Results)
    CapabilityCoverage = @($script:CoverageRows)
  }
  $summaryObj | ConvertTo-Json -Depth 6 | Set-Content -Path $summaryJsonPath -Encoding UTF8
}

<#
.SYNOPSIS
Runs the core validation suite.

.DESCRIPTION
Exercises the standard collect, enrich, finalize, and optional cleanup path plus the
collect and finalized enrich output-contract verifiers.

.FUNCTION NAME
Run-CoreSuite

.INPUTS
No direct parameters.

.OUTPUTS
No direct output. Executes the suite and writes harness results.
#>
function Run-CoreSuite {
  Restore-WorkingZip -Reason "Core"
  $collect = Invoke-CollectorStep -StepName "01_CollectT1" -CollectorArgs @("-Quick","collect-t1")
  Assert-CollectorStepSucceeded -StepName "01_CollectT1" -CollectorStep $collect
  Invoke-CollectOutputContractVerification -StepName "ZZ_CollectOutputContract" -CollectStep $collect
  if ($collect.AttachmentBudgetManifestPath) { Invoke-AttachmentBudgetVerification -StepName "ZZ_AttachmentBudget_Collect" -ManifestPath $collect.AttachmentBudgetManifestPath }
  [void](Invoke-CollectorStep -StepName "02_EnrichStartTcp" -CollectorArgs @("-Quick","enrich-start-tcp"))
  [void](Invoke-CollectorStep -StepName "03_EnrichAddLogTextSecurity" -CollectorArgs @("-Quick","enrich-add-logtext","-Target","Security"))
  $finalize = Invoke-CollectorStep -StepName "04_EnrichFinalize" -CollectorArgs @("-Quick","enrich-finalize")
  Assert-CollectorStepSucceeded -StepName "04_EnrichFinalize" -CollectorStep $finalize
  Invoke-EnrichFinalizedOutputContractVerification -StepName "ZZ_EnrichFinalizedOutputContract" -EnrichStep $finalize
  if (-not $SkipCleanup) {
    $cleanup = Invoke-CollectorStep -StepName "05_Cleanup" -CollectorArgs @("-Quick","cleanup")
    Assert-CollectorStepSucceeded -StepName "05_Cleanup" -CollectorStep $cleanup
    Invoke-CleanupOutputContractVerification -StepName "ZZ_CleanupOutputContract" -CleanupStep $cleanup
  }
}

<#
.SYNOPSIS
Runs the retrieval validation suite.

.DESCRIPTION
Exercises collect, raw-log enrich retrieval, finalize, and optional cleanup behavior.

.FUNCTION NAME
Run-RetrievalSuite

.INPUTS
No direct parameters.

.OUTPUTS
No direct output. Executes the suite and writes harness results.
#>
function Run-RetrievalSuite {
  Restore-WorkingZip -Reason "Retrieval"
  $collect = Invoke-CollectorStep -StepName "11_CollectT1" -CollectorArgs @("-Quick","collect-t1")
  Assert-CollectorStepSucceeded -StepName "11_CollectT1" -CollectorStep $collect
  if ($collect.AttachmentBudgetManifestPath) { Invoke-AttachmentBudgetVerification -StepName "ZZ_AttachmentBudget_RetrievalCollect" -ManifestPath $collect.AttachmentBudgetManifestPath }
  [void](Invoke-CollectorStep -StepName "12_EnrichStartLogRawSecurity" -CollectorArgs @("-Quick","enrich-start-lograw"))
  [void](Invoke-CollectorStep -StepName "13_EnrichFinalize" -CollectorArgs @("-Quick","enrich-finalize"))
  if (-not $SkipCleanup) { [void](Invoke-CollectorStep -StepName "14_Cleanup" -CollectorArgs @("-Quick","cleanup")) }
}

<#
.SYNOPSIS
Runs the quick-alias validation suite.

.DESCRIPTION
Exercises the supported quick enrich aliases against representative file, PID, service,
registry, task, and pull-action inputs plus optional cleanup.

.FUNCTION NAME
Run-QuickAliasesSuite

.INPUTS
No direct parameters.

.OUTPUTS
No direct output. Executes the suite and writes harness results.
#>
function Run-QuickAliasesSuite {
  $sampleScriptPath = $CollectorFullPath
  $sampleBinaryPath = "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
  $sampleService = "EventLog"
  $sampleRegistry = "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon"
  $sampleTask = "\Microsoft\Windows\Defrag\ScheduledDefrag"
  Restore-WorkingZip -Reason "QuickAliases"
  $collect = Invoke-CollectorStep -StepName "21_CollectT1" -CollectorArgs @("-Quick","collect-t1")
  Assert-CollectorStepSucceeded -StepName "21_CollectT1" -CollectorStep $collect
  if ($collect.AttachmentBudgetManifestPath) { Invoke-AttachmentBudgetVerification -StepName "ZZ_AttachmentBudget_QuickAliasesCollect" -ManifestPath $collect.AttachmentBudgetManifestPath }
