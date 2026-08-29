<#
.SYNOPSIS
DCOIR collector collect-mode entry function.

.DESCRIPTION
Runs the collect-mode package preparation, run-structure initialization, baseline collection, upload guidance artifact creation, manifest finalization, bundle creation, and collect-mode status output.

.FILE NAME
DCOIR_Collector.05A3_Main_Entry.ps1

.INPUTS
Collector runtime parameters such as OutRoot, PackageName, RunId, Tier, targeted-collection flags, and WhatIf/ShouldProcess context.

.OUTPUTS
Collect-mode status key-value lines, output artifact paths, quick next-step guidance, and persisted run state.
#>

<#
.SYNOPSIS
Runs collect mode.

.DESCRIPTION
Contains the collect branch previously held in the main switch dispatcher. Keeping it as a function makes the source connector-sized while preserving the compiled runtime behavior and output contract.

.FUNCTION NAME
Invoke-DCOIRCollectMode

.INPUTS
Collector runtime parameters and script-scoped state resolved by the main entry dispatcher.

.OUTPUTS
Collect-mode status key-value lines and artifact paths.
#>
function Invoke-DCOIRCollectMode {
$resolvedOutRoot = if ([System.IO.Path]::IsPathRooted($OutRoot)) {
  [System.IO.Path]::GetFullPath($OutRoot)
} else {
  [System.IO.Path]::GetFullPath((Join-Path (Get-Location).Path $OutRoot))
}

$purgeCompleted = Purge-PreviousRuns -Root $resolvedOutRoot -CurrentPackageName $PackageName
if (-not $purgeCompleted) {
  $prepSkipReason = if ($script:CollectPrepSkipReason) { [string]$script:CollectPrepSkipReason } else { 'PACKAGE_PURGE_SKIPPED' }
  $purgeStatusLine = if ($prepSkipReason -eq 'CUSTOM_RUN_PURGE_SKIPPED') { 'CUSTOM_RUN_PURGE_STATUS=SKIPPED' } else { 'PACKAGE_PURGE_STATUS=SKIPPED' }
  Write-DCOIRCollectSkippedStatus -RunId $RunId -CollectorVersion $ScriptVersion -AdditionalStatusLines @($purgeStatusLine) -SkipReason $prepSkipReason -NextOptions "Re-run without -WhatIf and confirm previous package cleanup to continue collect mode."
  return
}

$packagePath = Move-PackageToOutRoot -Root $resolvedOutRoot -CurrentPackageName $PackageName
if (-not $packagePath) {
  Write-DCOIRCollectSkippedStatus -RunId $RunId -CollectorVersion $ScriptVersion -AdditionalStatusLines @('COLLECT_PACKAGE_STATUS=SKIPPED') -NextOptions "Re-run without -WhatIf and confirm package preparation to continue collect mode."
  return
}

if ($WhatIfPreference) {
  Write-DCOIRCollectSkippedStatus -RunId $RunId -CollectorVersion $ScriptVersion -AdditionalStatusLines @('COLLECT_SETUP_STATUS=SKIPPED') -NextOptions "Re-run without -WhatIf to create the collect run structure and continue collect mode."
  return
}

$dirs = Initialize-RunStructure -Root $resolvedOutRoot -CurrentRunId $RunId
$Global:CurrentRunId = $RunId
$Global:ExecutionTxtPath = Join-Path $dirs.LogsDir "collect_execution_log.txt"
$Global:ExecutionJsonlPath = Join-Path $dirs.LogsDir "collect_execution_log.jsonl"
$Global:ErrorsLogPath = Join-Path $dirs.LogsDir "errors.log"
Set-Content -Path $Global:ExecutionTxtPath -Value ("DCOIR Collect Execution Log`r`nRunId={0}" -f $RunId) -Encoding UTF8 -ErrorAction Stop
Set-Content -Path $Global:ExecutionJsonlPath -Value "" -Encoding UTF8 -ErrorAction Stop
Set-Content -Path $Global:ErrorsLogPath -Value "" -Encoding UTF8 -ErrorAction Stop

$toolsExpanded = Expand-PackageToTools -PackagePath $packagePath -ToolsDir $dirs.ToolsDir
if (-not $toolsExpanded) {
  Write-DCOIRCollectSkippedStatus -RunId $RunId -CollectorVersion $ScriptVersion -AdditionalStatusLines @('TOOL_EXPANSION_STATUS=SKIPPED') -NextOptions "Re-run without -WhatIf and confirm tool expansion to continue collect mode."
  return
}

$toolMap = Get-ToolMap -ToolsDir $dirs.ToolsDir
$metadataReportPath = Join-Path $dirs.ReportsDir ("DCOIR_METADATA_{0}_{1}.txt" -f $env:COMPUTERNAME, $RunId)

$state = New-DCOIRCollectState -RunId $RunId -ResolvedOutRoot $resolvedOutRoot -Dirs $dirs -PackagePath $packagePath -MetadataReportPath $metadataReportPath -CollectorVersion $ScriptVersion

Initialize-ParallelBaselineCache -State $state

$baseline = New-BaselineReport -State $state -ToolMap $toolMap
Apply-FeatureWaveCollectEnhancements -State $state -Baseline $baseline
$targetedPlanExpected = [bool]($Targeted -or (-not [string]::IsNullOrWhiteSpace($FocusProcess)) -or (-not [string]::IsNullOrWhiteSpace($FocusPath)) -or (-not [string]::IsNullOrWhiteSpace($FocusIndicator)) -or (-not [string]::IsNullOrWhiteSpace($UserReport)) -or (-not [string]::IsNullOrWhiteSpace($WindowStart)) -or (-not [string]::IsNullOrWhiteSpace($WindowEnd)))

$uploadArtifacts = New-CollectUploadArtifactsWithLateMetadataReport -State $state -Baseline $baseline
$state.UploadSummaryPath = $uploadArtifacts.UploadSummaryPath
$state.UploadBudgetManifestPath = $uploadArtifacts.UploadManifestPath
$state.DefaultGeminiUploadSetStatus = $uploadArtifacts.DefaultSetStatus
$state.UploadSafeChunkManifestPath = $uploadArtifacts.UploadSafeChunkManifestPath
$state.AnalystOverviewPath = New-AnalystOverviewArtifactWithLateMetadataReport -State $state -Baseline $baseline

$uploadSafeChunkCompanionSkipped = [bool]($state.ContainsKey('UploadSafeChunkCompanionSkipped') -and [bool]$state.UploadSafeChunkCompanionSkipped)
$uploadSafeChunkManifestExpected = [bool](($uploadArtifacts.ContainsKey('UploadSafeChunkCompanionCount') -and ([int]$uploadArtifacts.UploadSafeChunkCompanionCount -gt 0)) -or $uploadSafeChunkCompanionSkipped)
$uploadSummarySkipped = -not $state.UploadSummaryPath
$attachmentBudgetManifestSkipped = -not $state.UploadBudgetManifestPath
$uploadSafeChunkManifestSkipped = [bool]($uploadSafeChunkManifestExpected -and -not $state.UploadSafeChunkManifestPath)
$analystOverviewSkipped = -not $state.AnalystOverviewPath
$collectionScopeSkipped = -not $state.CollectionScopePath
$parallelismAssessmentSkipped = -not $state.ParallelismAssessmentPath
$targetedCollectionPlanSkipped = [bool]($targetedPlanExpected -and -not $state.TargetedCollectionPlanPath)
$collectGuidanceSkipped = [bool]($uploadSummarySkipped -or $attachmentBudgetManifestSkipped -or $uploadSafeChunkManifestSkipped -or $analystOverviewSkipped -or $collectionScopeSkipped -or $parallelismAssessmentSkipped -or $targetedCollectionPlanSkipped)

$bundleName = ("DCOIR_COLLECT_BUNDLE_{0}_{1}.zip" -f $env:COMPUTERNAME, $RunId)
$bundlePath = Join-Path $state.BundlesDir $bundleName
$state.CollectBundlePath = $bundlePath
$bundleCreationApproved = $PSCmdlet.ShouldProcess($bundlePath, 'Create collector ZIP bundle')
$collectManifestSkipped = -not $bundleCreationApproved
$collectManifestFinalized = $false
$metadataReportSkipped = -not $bundleCreationApproved
$collectManifest = $null

if ($bundleCreationApproved) {
  # Write metadata once after late-bound collect fields are populated and before manifest/bundle packaging.
  $metadataText = New-MetadataReport -State $state -ToolMap $toolMap
  $metadataReportPath = Write-ReportFile -Path $metadataReportPath -Text $metadataText
  $metadataReportSkipped = -not $metadataReportPath
  $state.MetadataReportPath = $metadataReportPath

  if ($metadataReportPath) {
    $collectManifestInputs = New-DCOIRCollectManifestInputSet -State $state -Baseline $baseline -MetadataReportPath $metadataReportPath -TargetedMode ([bool]$Targeted) -TargetProfileName $TargetProfile
    $collectManifest = New-Manifest -ManifestPath (Join-Path $state.RunRoot "manifest_collect.json") -State $state -ModeName "Collect" -TierName $Tier -Files $collectManifestInputs.Files -ToolMap $toolMap -Extra $collectManifestInputs.Extra
    $collectManifestSkipped = -not $collectManifest
    $collectManifestFinalized = [bool]$collectManifest
  }

  if ($collectManifest) {
    $bundlePath = New-BundleZip -BundlesDir $state.BundlesDir -BundleName $bundleName -Confirm:$false -Paths @(
      $metadataReportPath,
      $state.AnalystOverviewPath,
      $state.ParallelExecutionProofPath,
      $state.ExecutionContextPath,
      $state.SecurityAuditPolicyPath,
      $state.SecurityFilteredPath,
      $state.SecurityHighSignalSummaryPath,
      $state.NetstatPidOnlyPath,
      $state.UploadSummaryPath,
      $state.UploadBudgetManifestPath,
      $state.UploadSafeChunkManifestPath,
      $state.ArtifactsDir,
      $Global:ExecutionTxtPath,
      $Global:ExecutionJsonlPath,
      $Global:ErrorsLogPath,
      $collectManifest
    )
  } else {
    $bundlePath = $null
  }

  if ($bundlePath) {
    $state.CollectBundlePath = $bundlePath
  } else {
    Reset-DCOIRCollectBundleStateAfterFailure -State $state
    $metadataReportPath = $null
    $metadataReportSkipped = $true
    $uploadSummarySkipped = $true
    $attachmentBudgetManifestSkipped = $true
    $uploadSafeChunkManifestSkipped = [bool]$uploadSafeChunkManifestExpected
    $analystOverviewSkipped = $true
    $collectionScopeSkipped = $true
    $parallelismAssessmentSkipped = $true
    $targetedCollectionPlanSkipped = [bool]$targetedPlanExpected
    $collectGuidanceSkipped = $true
  }
} else {
  Reset-DCOIRCollectBundleStateAfterFailure -State $state
  $metadataReportPath = $null
  $bundlePath = $null
  $uploadSummarySkipped = $true
  $attachmentBudgetManifestSkipped = $true
  $uploadSafeChunkManifestSkipped = [bool]$uploadSafeChunkManifestExpected
  $analystOverviewSkipped = $true
  $collectionScopeSkipped = $true
  $parallelismAssessmentSkipped = $true
  $targetedCollectionPlanSkipped = [bool]$targetedPlanExpected
  $collectGuidanceSkipped = $true
}

$stateSavePath = Save-State -State $state
$collectPackageSkipped = -not $bundlePath
$collectManifestFinalizationSkipped = -not $collectManifestFinalized
$stateSaveSkipped = -not $stateSavePath

$status = "SUCCESS"
if ($collectPackageSkipped -or $collectManifestFinalizationSkipped -or $metadataReportSkipped -or $stateSaveSkipped -or $collectGuidanceSkipped) { $status = "PARTIAL_SUCCESS" }
if ($status -eq "SUCCESS" -and @($Global:CollectorErrors).Count -gt 0) { $status = "PARTIAL_SUCCESS" }

Write-DCOIRCollectFinalStatus -State $state -RunId $RunId -Status $status -BundlePath $bundlePath -MetadataReportPath $metadataReportPath -CollectPackageSkipped $collectPackageSkipped -CollectManifestSkipped $collectManifestSkipped -CollectManifestFinalizationSkipped $collectManifestFinalizationSkipped -MetadataReportSkipped $metadataReportSkipped -StateSaveSkipped $stateSaveSkipped -UploadSummarySkipped $uploadSummarySkipped -AttachmentBudgetManifestSkipped $attachmentBudgetManifestSkipped -UploadSafeChunkManifestSkipped $uploadSafeChunkManifestSkipped -AnalystOverviewSkipped $analystOverviewSkipped -CollectionScopeSkipped $collectionScopeSkipped -ParallelismAssessmentSkipped $parallelismAssessmentSkipped -TargetedCollectionPlanSkipped $targetedCollectionPlanSkipped -CollectGuidanceSkipped $collectGuidanceSkipped
}
# DCOIR_REVIEW_AUDIT_BATCH_2H5_MARKER
