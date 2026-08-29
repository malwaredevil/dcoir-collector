<#
.SYNOPSIS
DCOIR collector cleanup-mode entry helper.

.DESCRIPTION
Runs state-backed cleanup when run state is available and safe no-state cleanup when state is absent, preserving cleanup refusal and summary output behavior.

.FILE NAME
DCOIR_Collector.05C_Main_Entry.ps1

.INPUTS
Collector runtime parameters such as OutRoot, PackageName, RunId, and cleanup state loaded from the selected output root.

.OUTPUTS
Cleanup status key-value lines, removed/skipped/failed/refused target summaries, and quick next-step guidance.
#>

<#
.SYNOPSIS
Runs cleanup mode.

.DESCRIPTION
Contains the cleanup branch previously held in the main switch dispatcher. Keeping it as a function makes the source connector-sized while preserving state-backed cleanup authority checks and no-state cleanup behavior.

.FUNCTION NAME
Invoke-DCOIRCleanupMode

.INPUTS
Collector runtime parameters and script-scoped state resolved by the main entry dispatcher.

.OUTPUTS
Cleanup status key-value lines and target summaries.
#>
function Invoke-DCOIRCleanupMode {
$resolvedOutRoot = if ([System.IO.Path]::IsPathRooted($OutRoot)) {
  [System.IO.Path]::GetFullPath($OutRoot)
} else {
  [System.IO.Path]::GetFullPath((Join-Path (Get-Location).Path $OutRoot))
}
try {
  $loaded = Load-State -Root $resolvedOutRoot -CurrentRunId $RunId
  $cleanupCollectorVersion = if (($loaded.PSObject.Properties.Name -contains 'CollectorVersion') -and -not [string]::IsNullOrWhiteSpace([string]$loaded.CollectorVersion)) {
    [string]$loaded.CollectorVersion
  } else {
    $ScriptVersion
  }
  $cleanupResult = Invoke-Cleanup -StateObject $loaded -Root $resolvedOutRoot -CurrentPackageName $PackageName -SelectedRunId $RunId
  $cleanupRunId = if ([string]::IsNullOrWhiteSpace([string]$RunId)) { [string]$loaded.RunId } else { [string]$RunId }
  Write-Output ("CLEANUP_STATUS={0}" -f $cleanupResult.Status)
  Write-Output ("RUN_ID={0}" -f $cleanupRunId)
  if (-not [string]::Equals([string]$loaded.RunId, [string]$cleanupRunId, [System.StringComparison]::OrdinalIgnoreCase)) {
    Write-Output ("STATE_RUN_ID={0}" -f $loaded.RunId)
  }
  Write-Output ("CLEANUP_TARGET_COUNT={0}" -f $cleanupResult.TargetCount)
  Write-Output ("CLEANUP_REMOVED_COUNT={0}" -f $cleanupResult.RemovedCount)
  Write-Output ("CLEANUP_SKIPPED_COUNT={0}" -f $cleanupResult.SkippedCount)
  Write-Output ("CLEANUP_FAILED_COUNT={0}" -f $cleanupResult.FailedCount)
  if ($cleanupResult.PSObject.Properties.Name -contains 'RefusedCount') { Write-Output ("CLEANUP_REFUSED_COUNT={0}" -f $cleanupResult.RefusedCount) }
  foreach ($target in @($cleanupResult.RemovedTargets)) { Write-Output ("CLEANUP_REMOVED_TARGET={0}" -f $target) }
  foreach ($target in @($cleanupResult.SkippedTargets)) { Write-Output ("CLEANUP_SKIPPED_TARGET={0}" -f $target) }
  foreach ($target in @($cleanupResult.FailedTargets)) { Write-Output ("CLEANUP_FAILED_TARGET={0}" -f $target) }
  foreach ($target in @($cleanupResult.RefusedTargets)) { Write-Output ("CLEANUP_REFUSED_TARGET={0}" -f $target) }
  foreach ($reason in @($cleanupResult.RefusalReasons)) { Write-Output ("CLEANUP_REFUSAL_REASON={0}" -f $reason) }
  Write-Output ("COLLECTOR_VERSION={0}" -f $cleanupCollectorVersion)
  Write-Output ("COLLECTOR_BUILD_IDENTITY={0}" -f (Get-CollectorBuildIdentity -Version $cleanupCollectorVersion))
  Write-Output ("DELETE_SCRIPT_COMMAND={0}" -f (Get-CollectorDeleteScriptCommandText))
  Write-QuickNextSteps -Phase "Cleanup"
} catch {
  $loadError = $_.Exception.Message
  if ($loadError -notmatch 'State file not found|No DCOIR run directories found') { throw }
  $cleanupResult = Invoke-NoStateCleanup -Root $resolvedOutRoot -CurrentRunId $RunId -CurrentPackageName $PackageName
  Write-Output ("CLEANUP_STATUS={0}" -f $cleanupResult.Status)
  if ($RunId) { Write-Output ("RUN_ID={0}" -f $RunId) }
  if ($cleanupResult.RunRoot) { Write-Output ("CLEANUP_ORPHAN_RUN_ROOT={0}" -f $cleanupResult.RunRoot) }
  Write-Output ("CLEANUP_TARGET_COUNT={0}" -f $cleanupResult.TargetCount)
  Write-Output ("CLEANUP_REMOVED_COUNT={0}" -f $cleanupResult.RemovedCount)
  Write-Output ("CLEANUP_SKIPPED_COUNT={0}" -f $cleanupResult.SkippedCount)
  Write-Output ("CLEANUP_FAILED_COUNT={0}" -f $cleanupResult.FailedCount)
  foreach ($target in @($cleanupResult.RemovedTargets)) { Write-Output ("CLEANUP_REMOVED_TARGET={0}" -f $target) }
  foreach ($target in @($cleanupResult.SkippedTargets)) { Write-Output ("CLEANUP_SKIPPED_TARGET={0}" -f $target) }
  foreach ($target in @($cleanupResult.FailedTargets)) { Write-Output ("CLEANUP_FAILED_TARGET={0}" -f $target) }
  Write-Output ("CLEANUP_REASON={0}" -f $loadError)
  Write-Output ("COLLECTOR_VERSION={0}" -f $ScriptVersion)
  Write-Output ("COLLECTOR_BUILD_IDENTITY={0}" -f (Get-CollectorBuildIdentity -Version $ScriptVersion))
  Write-Output ("DELETE_SCRIPT_COMMAND={0}" -f (Get-CollectorDeleteScriptCommandText))
  Write-QuickNextSteps -Phase "Cleanup"
}
}
