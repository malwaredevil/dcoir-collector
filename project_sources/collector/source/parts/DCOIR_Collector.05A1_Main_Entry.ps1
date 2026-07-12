<#
.SYNOPSIS
DCOIR collector collect-mode entry helpers.

.DESCRIPTION
Provides connector-sized helper routines used by the collect-mode entry function loaded after the 05A2 helper part.

.FILE NAME
DCOIR_Collector.05A1_Main_Entry.ps1

.INPUTS
Collector runtime state, run identifiers, artifact paths, and collect-mode status values.

.OUTPUTS
Helper return values and early collect-mode skipped status key-value lines.
#>

<#
.SYNOPSIS
Writes a common collect-mode skipped status block.

.DESCRIPTION
Centralizes the repeated early collect-mode skip output for package purge, package preparation, WhatIf setup, and tool expansion branches while preserving output order.

.FUNCTION NAME
Write-DCOIRCollectSkippedStatus

.INPUTS
Run identifier, collector version, additional status lines, optional skip reason, and next-option guidance.

.OUTPUTS
Collect-mode skipped status key-value lines.
#>
function Write-DCOIRCollectSkippedStatus {
  param(
    [string]$RunId,
    [string]$CollectorVersion,
    [string[]]$AdditionalStatusLines = @(),
    [string]$SkipReason,
    [string]$NextOptions
  )

  $Global:CurrentRunId = $RunId
  $collectorCommandBase = Get-CollectorResponseActionCommandBase
  $deleteScriptCommand = Get-CollectorDeleteScriptCommandText

  Write-Output "STATUS=SKIPPED"
  Write-Output "COLLECT_PREP_STATUS=SKIPPED"
  foreach ($statusLine in @($AdditionalStatusLines)) {
    if (-not [string]::IsNullOrWhiteSpace([string]$statusLine)) {
      Write-Output $statusLine
    }
  }
  if (-not [string]::IsNullOrWhiteSpace($SkipReason)) {
    Write-Output ("COLLECT_PREP_SKIP_REASON={0}" -f $SkipReason)
  }
  Write-Output ("RUN_ID={0}" -f $RunId)
  Write-Output ("COLLECTOR_VERSION={0}" -f $CollectorVersion)
  Write-Output ("COLLECTOR_BUILD_IDENTITY={0}" -f (Get-CollectorBuildIdentity -Version $CollectorVersion))
  Write-Output ("NEXT_OPTIONS={0}" -f $NextOptions)
  Write-Output ('CLEANUP_COMMAND=execute --command "{0} -Quick cleanup" --comment "Running Cleanup on DCOIR_Collector"' -f $collectorCommandBase)
  Write-Output ("DELETE_SCRIPT_COMMAND={0}" -f $deleteScriptCommand)
}

<#
.SYNOPSIS
Creates the initial collect-mode state table.

.DESCRIPTION
Builds the state structure shared by baseline collection, upload guidance, manifest finalization, bundling, and later enrich runs.

.FUNCTION NAME
New-DCOIRCollectState

.INPUTS
Run identifier, resolved output root, initialized run directories, prepared package path, metadata report path, and collector version.

.OUTPUTS
Hashtable representing the collect run state.
#>
function New-DCOIRCollectState {
  param(
    [string]$RunId,
    [string]$ResolvedOutRoot,
    [object]$Dirs,
    [string]$PackagePath,
    [string]$MetadataReportPath,
    [string]$CollectorVersion
  )

  return @{
    RunId = $RunId
    Host = $env:COMPUTERNAME
    OutRoot = $ResolvedOutRoot
    RunRoot = $Dirs.RunRoot
    ToolsDir = $Dirs.ToolsDir
    ReportsDir = $Dirs.ReportsDir
    ArtifactsDir = $Dirs.ArtifactsDir
    EnrichSessionsDir = $Dirs.EnrichSessionsDir
    LogsDir = $Dirs.LogsDir
    BundlesDir = $Dirs.BundlesDir
    StatePath = $Dirs.StatePath
    PackagePath = $PackagePath
    MetadataReportPath = $MetadataReportPath
    BaselineReportPath = $null
    UploadSummaryPath = $null
    UploadBudgetManifestPath = $null
    AnalystOverviewPath = $null
    ParallelExecutionProofPath = $null
    ExecutionContextPath = $null
    SecurityAuditPolicyPath = $null
    AuditPolicyAccessStatus = $null
    SecurityFilteredPath = $null
    SecurityHighSignalSummaryPath = $null
    NetstatPidOnlyPath = $null
    NetstatOwnerAwareStatus = $null
    IsElevated = $null
    DefaultGeminiUploadSetStatus = $null
    CollectBundlePath = $null
    CollectionScopePath = $null
    ParallelismAssessmentPath = $null
    TargetedCollectionPlanPath = $null
    SyntheticOversizeSourcePath = $null
    ChunkManifestPath = $null
    UploadSafeChunkManifestPath = $null
    EnrichSessions = @()
    EnrichSessionCounter = 0
    OpenEnrichSessionId = $null
    LastSessionResolutionMode = $null
    CreatedLocal = (Get-Date).ToString("o")
    CreatedUTC = (Get-Date).ToUniversalTime().ToString("o")
    CollectorVersion = $CollectorVersion
  }
}
