<#
.SYNOPSIS
DCOIR collector collect-mode finalization helpers.

.DESCRIPTION
Provides connector-sized helper routines used by the collect-mode entry function loaded in the following 05A3 part.

.FILE NAME
DCOIR_Collector.05A2_Main_Entry.ps1

.INPUTS
Collector runtime state, baseline artifact paths, metadata paths, targeted-collection flags, and collect-mode status values.

.OUTPUTS
Helper return values and final collect-mode status key-value lines.
#>

<#
.SYNOPSIS
Builds the collect-mode manifest inputs.

.DESCRIPTION
Centralizes the late-bound collect manifest file list and extra metadata after upload guidance artifacts and the final metadata report path are known.

.FUNCTION NAME
New-DCOIRCollectManifestInputSet

.INPUTS
Collect run state, baseline report object, metadata report path, targeted-mode flag, and target profile name.

.OUTPUTS
Hashtable containing Files and Extra values for New-Manifest.
#>
function New-DCOIRCollectManifestInputSet {
  param(
    [hashtable]$State,
    [object]$Baseline,
    [string]$MetadataReportPath,
    [bool]$TargetedMode,
    [string]$TargetProfileName
  )

  $files = @(
    $MetadataReportPath,
    $State.AnalystOverviewPath,
    $State.ParallelExecutionProofPath,
    $State.ExecutionContextPath,
    $State.SecurityAuditPolicyPath,
    $State.SecurityFilteredPath,
    $State.SecurityHighSignalSummaryPath,
    $State.NetstatPidOnlyPath,
    $State.UploadSummaryPath,
    $State.UploadBudgetManifestPath,
    $State.UploadSafeChunkManifestPath,
    $State.CollectionScopePath,
    $State.ParallelismAssessmentPath,
    $State.TargetedCollectionPlanPath,
    $Global:ExecutionTxtPath,
    $Global:ExecutionJsonlPath,
    $Global:ErrorsLogPath
  ) + $Baseline.ArtifactPaths

  $extra = @{
    collect_bundle = $State.CollectBundlePath
    analyst_overview = $State.AnalystOverviewPath
    parallel_execution_proof = $State.ParallelExecutionProofPath
    execution_context = $State.ExecutionContextPath
    security_audit_policy = $State.SecurityAuditPolicyPath
    audit_policy_access_status = $State.AuditPolicyAccessStatus
    security_filtered = $State.SecurityFilteredPath
    security_high_signal_summary = $State.SecurityHighSignalSummaryPath
    netstat_owner_aware_status = $State.NetstatOwnerAwareStatus
    netstat_pid_only = $State.NetstatPidOnlyPath
    is_elevated = $State.IsElevated
    upload_summary = $State.UploadSummaryPath
    attachment_budget_manifest = $State.UploadBudgetManifestPath
    default_gemini_upload_set_status = $State.DefaultGeminiUploadSetStatus
    collection_scope = $State.CollectionScopePath
    parallelism_assessment = $State.ParallelismAssessmentPath
    targeted_collection_plan = $State.TargetedCollectionPlanPath
    targeted_mode = [bool]$TargetedMode
    target_profile = $TargetProfileName
    synthetic_oversize_source = $State.SyntheticOversizeSourcePath
    chunk_manifest = $State.ChunkManifestPath
    upload_safe_chunk_manifest = $State.UploadSafeChunkManifestPath
  }

  return @{
    Files = $files
    Extra = $extra
  }
}

<#
.SYNOPSIS
Clears collect artifact paths after bundle creation is skipped or fails.

.DESCRIPTION
Keeps state cleanup consistent across the manifest/bundle failure path and the ShouldProcess skip path.

.FUNCTION NAME
Reset-DCOIRCollectBundleStateAfterFailure

.INPUTS
Collect run state.

.OUTPUTS
None. The state hashtable is updated in place.
#>
function Reset-DCOIRCollectBundleStateAfterFailure {
  param([hashtable]$State)

  foreach ($key in @(
    'CollectBundlePath',
    'MetadataReportPath',
    'UploadSummaryPath',
    'UploadBudgetManifestPath',
    'UploadSafeChunkManifestPath',
    'AnalystOverviewPath',
    'CollectionScopePath',
    'ParallelismAssessmentPath',
    'TargetedCollectionPlanPath'
  )) {
    $State[$key] = $null
  }
}

<#
.SYNOPSIS
Writes the final collect-mode status block.

.DESCRIPTION
Preserves the existing collect-mode output ordering while keeping the entry function connector-sized.

.FUNCTION NAME
Write-DCOIRCollectFinalStatus

.INPUTS
Collect run state, run identifier, final status, bundle and metadata paths, and skip flags.

.OUTPUTS
Collect-mode status key-value lines, artifact paths, Gemini upload guidance, collector errors, and quick next-step guidance.
#>
function Write-DCOIRCollectFinalStatus {
  param(
    [hashtable]$State,
    [string]$RunId,
    [string]$Status,
    [string]$BundlePath,
    [string]$MetadataReportPath,
    [bool]$CollectPackageSkipped,
    [bool]$CollectManifestSkipped,
    [bool]$CollectManifestFinalizationSkipped,
    [bool]$MetadataReportSkipped,
    [bool]$StateSaveSkipped,
    [bool]$UploadSummarySkipped,
    [bool]$AttachmentBudgetManifestSkipped,
    [bool]$UploadSafeChunkManifestSkipped,
    [bool]$AnalystOverviewSkipped,
    [bool]$CollectionScopeSkipped,
    [bool]$ParallelismAssessmentSkipped,
    [bool]$TargetedCollectionPlanSkipped,
    [bool]$CollectGuidanceSkipped
  )

  $collectorCommandBase = Get-CollectorResponseActionCommandBase
  $deleteScriptCommand = Get-CollectorDeleteScriptCommandText

  Write-Output ("STATUS={0}" -f $Status)
  if ($CollectPackageSkipped) {
    Write-Output "COLLECT_PACKAGE_STATUS=SKIPPED"
    Write-Output "COLLECT_BUNDLE_STATUS=SKIPPED"
  } elseif ($BundlePath) {
    Write-Output "COLLECT_PACKAGE_STATUS=CREATED"
    Write-Output "COLLECT_BUNDLE_STATUS=CREATED"
  }
  if ($CollectManifestSkipped) { Write-Output "COLLECT_MANIFEST_STATUS=SKIPPED" }
  elseif ($CollectManifestFinalizationSkipped) { Write-Output "COLLECT_MANIFEST_STATUS=PARTIAL" }
  if ($MetadataReportSkipped) { Write-Output "METADATA_REPORT_STATUS=SKIPPED" }
  if ($StateSaveSkipped) { Write-Output "STATE_SAVE_STATUS=SKIPPED" }
  if ($UploadSummarySkipped) { Write-Output "UPLOAD_SUMMARY_STATUS=SKIPPED" }
  if ($AttachmentBudgetManifestSkipped) { Write-Output "ATTACHMENT_BUDGET_MANIFEST_STATUS=SKIPPED" }
  if ($UploadSafeChunkManifestSkipped) { Write-Output "UPLOAD_SAFE_CHUNK_MANIFEST_STATUS=SKIPPED" }
  if ($AnalystOverviewSkipped) { Write-Output "ANALYST_OVERVIEW_STATUS=SKIPPED" }
  if ($CollectionScopeSkipped) { Write-Output "COLLECTION_SCOPE_STATUS=SKIPPED" }
  if ($ParallelismAssessmentSkipped) { Write-Output "PARALLELISM_ASSESSMENT_STATUS=SKIPPED" }
  if ($TargetedCollectionPlanSkipped) { Write-Output "TARGETED_COLLECTION_PLAN_STATUS=SKIPPED" }
  Write-Output ("RUN_ID={0}" -f $RunId)
  Write-Output ("COLLECTOR_VERSION={0}" -f $State.CollectorVersion)
  Write-Output ("COLLECTOR_BUILD_IDENTITY={0}" -f (Get-CollectorBuildIdentity -Version $State.CollectorVersion))
  if ($MetadataReportPath) { Write-Output ("METADATA_REPORT_PATH={0}" -f $MetadataReportPath) }
  if ($State.ExecutionContextPath) { Write-Output ("EXECUTION_CONTEXT_PATH={0}" -f $State.ExecutionContextPath) }
  if ($State.SecurityAuditPolicyPath) { Write-Output ("SECURITY_AUDIT_POLICY_PATH={0}" -f $State.SecurityAuditPolicyPath) }
  Write-Output ("AUDIT_POLICY_ACCESS_STATUS={0}" -f $State.AuditPolicyAccessStatus)
  if ($State.SecurityFilteredPath) { Write-Output ("SECURITY_FILTERED_PATH={0}" -f $State.SecurityFilteredPath) }
  if ($State.SecurityHighSignalSummaryPath) { Write-Output ("SECURITY_HIGH_SIGNAL_SUMMARY_PATH={0}" -f $State.SecurityHighSignalSummaryPath) }
  Write-Output ("IS_ELEVATED={0}" -f $State.IsElevated)
  Write-Output ("NETSTAT_OWNER_AWARE_STATUS={0}" -f $State.NetstatOwnerAwareStatus)
  if ($State.NetstatPidOnlyPath) { Write-Output ("NETSTAT_PID_ONLY_PATH={0}" -f $State.NetstatPidOnlyPath) }
  if ($State.AnalystOverviewPath) { Write-Output ("ANALYST_OVERVIEW_PATH={0}" -f $State.AnalystOverviewPath) }
  if ($State.ParallelExecutionProofPath) { Write-Output ("PARALLEL_EXECUTION_PROOF_PATH={0}" -f $State.ParallelExecutionProofPath) }
  if ($State.UploadSummaryPath) { Write-Output ("UPLOAD_SUMMARY_PATH={0}" -f $State.UploadSummaryPath) }
  if ($State.UploadBudgetManifestPath) { Write-Output ("ATTACHMENT_BUDGET_MANIFEST_PATH={0}" -f $State.UploadBudgetManifestPath) }
  if ($State.UploadSafeChunkManifestPath) { Write-Output ("UPLOAD_SAFE_CHUNK_MANIFEST_PATH={0}" -f $State.UploadSafeChunkManifestPath) }
  if ($State.CollectionScopePath) { Write-Output ("COLLECTION_SCOPE_PATH={0}" -f $State.CollectionScopePath) }
  if ($State.ParallelismAssessmentPath) { Write-Output ("PARALLELISM_ASSESSMENT_PATH={0}" -f $State.ParallelismAssessmentPath) }
  if ($State.TargetedCollectionPlanPath) { Write-Output ("TARGETED_COLLECTION_PLAN_PATH={0}" -f $State.TargetedCollectionPlanPath) }
  if ($State.SyntheticOversizeSourcePath) { Write-Output ("SYNTHETIC_OVERSIZE_SOURCE_PATH={0}" -f $State.SyntheticOversizeSourcePath) }
  if ($State.ChunkManifestPath) { Write-Output ("CHUNK_MANIFEST_PATH={0}" -f $State.ChunkManifestPath) }
  Write-Output ("DEFAULT_GEMINI_UPLOAD_SET_STATUS={0}" -f $State.DefaultGeminiUploadSetStatus)
  if ($BundlePath) {
    Write-Output ("COLLECT_BUNDLE_PATH={0}" -f $BundlePath)
    Write-Output ('NEXT_GET_FILE=get-file --path "{0}" --comment "Retrieve DCOIR collect bundle"' -f $BundlePath)
  }
  Write-Output ('CLEANUP_COMMAND=execute --command "{0} -Quick cleanup" --comment "Running Cleanup on DCOIR_Collector"' -f $collectorCommandBase)
  Write-Output ("DELETE_SCRIPT_COMMAND={0}" -f $deleteScriptCommand)
  if (-not $CollectGuidanceSkipped -and -not $MetadataReportSkipped) {
    Write-Output ('GEMINI_UPLOAD_GUIDANCE=Prefer ANALYST_OVERVIEW_PATH, UPLOAD_SUMMARY_PATH, ATTACHMENT_BUDGET_MANIFEST_PATH, COLLECTION_SCOPE_PATH, PARALLELISM_ASSESSMENT_PATH, and representative final_artifacts slices. If UPLOAD_SAFE_CHUNK_MANIFEST_PATH exists, use it for full-fidelity oversized text artifacts after triage summaries. If TARGETED_COLLECTION_PLAN_PATH exists, include it for narrow incidents.')
  } else {
    Write-Output "GEMINI_UPLOAD_GUIDANCE_STATUS=SKIPPED"
  }
  foreach ($collectorError in @($Global:CollectorErrors)) {
    if (-not [string]::IsNullOrWhiteSpace([string]$collectorError)) {
      Write-Output ("COLLECTOR_ERROR={0}" -f $collectorError)
    }
  }
  Write-QuickNextSteps -Phase "Collect"
}
