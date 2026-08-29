<#
.SYNOPSIS
DCOIR collector enrich-mode entry helper.

.DESCRIPTION
Runs the enrich-mode state load, session resolution, action execution, optional session finalization, state save, and enrich-mode status output.

.FILE NAME
DCOIR_Collector.05B_Main_Entry.ps1

.INPUTS
Collector runtime parameters such as OutRoot, RunId, Action, EnrichSessionId, NewEnrichSession, FinalizeEnrichSession, and WhatIf/ShouldProcess context.

.OUTPUTS
Enrich-mode status key-value lines, report or bundle paths, and quick next-step guidance.
#>

<#
.SYNOPSIS
Runs enrich mode.

.DESCRIPTION
Contains the enrich branch previously held in the main switch dispatcher. Keeping it as a function makes the source connector-sized while preserving the compiled runtime behavior and output contract.

.FUNCTION NAME
Invoke-DCOIREnrichMode

.INPUTS
Collector runtime parameters and script-scoped state resolved by the main entry dispatcher.

.OUTPUTS
Enrich-mode status key-value lines and artifact paths.
#>
function Invoke-DCOIREnrichMode {
$loaded = Load-State -Root $OutRoot -CurrentRunId $RunId
$state = Convert-StateObjectToHashtable -InputObject $loaded
$Global:CurrentRunId = [string]$state.RunId

if (-not $Action -and -not $FinalizeEnrichSession) {
  throw "Enrich mode requires -Action or -FinalizeEnrichSession."
}

$requireOpenSessionForFinalize = [bool]($FinalizeEnrichSession -and -not $Action -and [string]::IsNullOrWhiteSpace($EnrichSessionId))
$session = Initialize-EnrichSession -State $state -RequestedSessionId $EnrichSessionId -ForceNew:$NewEnrichSession -RequireExistingOpenSession:$requireOpenSessionForFinalize
if ($session -and $session.ContainsKey('CreationSkipped') -and [bool]$session.CreationSkipped) {
  $deleteScriptCommand = Get-CollectorDeleteScriptCommandText
  Write-Output "STATUS=SKIPPED"
  Write-Output ("RUN_ID={0}" -f $state.RunId)
  Write-Output ("COLLECTOR_VERSION={0}" -f [string]$state.CollectorVersion)
  Write-Output ("COLLECTOR_BUILD_IDENTITY={0}" -f (Get-CollectorBuildIdentity -Version ([string]$state.CollectorVersion)))
  Write-Output ("PLANNED_ENRICH_SESSION_ID={0}" -f $session.SessionId)
  Write-Output ("SESSION_RESOLUTION_MODE={0}" -f $session.SessionResolutionMode)
  Write-Output "SESSION_STATUS=CREATE_SKIPPED"
  Write-Output "NEXT_OPTIONS=Re-run without -WhatIf to create the enrich session, or provide an existing -EnrichSessionId."
  Write-Output ("DELETE_SCRIPT_COMMAND={0}" -f $deleteScriptCommand)
  return
}

$logStamp = Get-Date -Format "yyyyMMdd_HHmmss"
$actionLabel = if ($Action) { $Action } else { "FinalizeSession" }
$Global:ExecutionTxtPath = Join-Path $session.LogsDir ("enrich_{0}_{1}_execution_log.txt" -f $actionLabel, $logStamp)
$Global:ExecutionJsonlPath = Join-Path $session.LogsDir ("enrich_{0}_{1}_execution_log.jsonl" -f $actionLabel, $logStamp)
$Global:ErrorsLogPath = Join-Path $session.LogsDir ("enrich_{0}_{1}_errors.log" -f $actionLabel, $logStamp)
$enrichLogsInitialized = $false
if ($PSCmdlet.ShouldProcess($session.LogsDir, ("Initialize enrich execution logs for {0}" -f $actionLabel))) {
  Set-Content -Path $Global:ExecutionTxtPath -Value ("DCOIR Enrich Execution Log`r`nRunId={0}`r`nEnrichSessionId={1}`r`nAction={2}`r`nSessionResolutionMode={3}" -f $state.RunId, $session.SessionId, $actionLabel, $session.SessionResolutionMode) -Encoding UTF8 -ErrorAction Stop
  Set-Content -Path $Global:ExecutionJsonlPath -Value "" -Encoding UTF8 -ErrorAction Stop
  Set-Content -Path $Global:ErrorsLogPath -Value "" -Encoding UTF8 -ErrorAction Stop
  $enrichLogsInitialized = $true
}
if (-not $enrichLogsInitialized) {
  $deleteScriptCommand = Get-CollectorDeleteScriptCommandText
  Write-Output "STATUS=SKIPPED"
  Write-Output ("RUN_ID={0}" -f $state.RunId)
  Write-Output ("COLLECTOR_VERSION={0}" -f [string]$state.CollectorVersion)
  Write-Output ("COLLECTOR_BUILD_IDENTITY={0}" -f (Get-CollectorBuildIdentity -Version ([string]$state.CollectorVersion)))
  Write-Output ("ENRICH_SESSION_ID={0}" -f $session.SessionId)
  Write-Output ("SESSION_RESOLUTION_MODE={0}" -f $session.SessionResolutionMode)
  if ($Action) { Write-Output "ACTION_STATUS=SKIPPED" }
  if ($FinalizeEnrichSession) { Write-Output "FINALIZE_STATUS=SKIPPED" }
  Write-Output "ENRICH_LOG_STATUS=SKIPPED"
  Write-Output "SESSION_STATUS=OPEN"
  Write-Output "NEXT_OPTIONS=Re-run without -WhatIf and confirm enrich log initialization to run the requested enrich work."
  Write-Output ("DELETE_SCRIPT_COMMAND={0}" -f $deleteScriptCommand)
  return
}

$toolMap = Get-ToolMap -ToolsDir $state.ToolsDir

$result = $null
if ($Action) {
  $result = Invoke-EnrichmentAction -State $state -Session $session -ToolMap $toolMap
}
$resultIsDictionary = ($result -is [System.Collections.IDictionary])
$actionSkipped = [bool]($resultIsDictionary -and $result.ContainsKey('ActionSkipped') -and [bool]$result.ActionSkipped)
$actionCompleted = [bool]($Action -and -not $actionSkipped -and $result)

$bundlePath = $null
$sessionStatus = "OPEN"
if ($FinalizeEnrichSession) {
  $bundlePath = Finalize-EnrichSession -State $state -Session $session -ToolMap $toolMap
  $sessionStatus = if ($bundlePath) { "FINALIZED" } else { "FINALIZE_SKIPPED" }
}
$finalizeSkipped = [bool]($FinalizeEnrichSession -and -not $bundlePath)
$finalizeCompleted = [bool]($FinalizeEnrichSession -and $bundlePath)

$stateSavePath = Save-State -State $state
$stateSaveSkipped = -not $stateSavePath

$status = "SUCCESS"
if ($actionSkipped -or $finalizeSkipped) {
  if ($actionCompleted -or $finalizeCompleted) { $status = "PARTIAL_SUCCESS" }
  else { $status = "SKIPPED" }
}
if ($status -eq "SUCCESS" -and $stateSaveSkipped) { $status = "PARTIAL_SUCCESS" }
if ($status -eq "SUCCESS" -and @($Global:CollectorErrors).Count -gt 0) { $status = "PARTIAL_SUCCESS" }

$deleteScriptCommand = Get-CollectorDeleteScriptCommandText

Write-Output ("STATUS={0}" -f $status)
Write-Output ("RUN_ID={0}" -f $state.RunId)
Write-Output ("COLLECTOR_VERSION={0}" -f [string]$state.CollectorVersion)
Write-Output ("COLLECTOR_BUILD_IDENTITY={0}" -f (Get-CollectorBuildIdentity -Version ([string]$state.CollectorVersion)))
Write-Output ("ENRICH_SESSION_ID={0}" -f $session.SessionId)
Write-Output ("SESSION_RESOLUTION_MODE={0}" -f $session.SessionResolutionMode)
if ($result) {
  if ($resultIsDictionary -and $result.ContainsKey('ActionStatus') -and $result.ActionStatus) { Write-Output ("ACTION_STATUS={0}" -f $result.ActionStatus) }
  if ($result.ReportPath) { Write-Output ("ENRICH_REPORT_PATH={0}" -f $result.ReportPath) }
  if ($result.ActionArtifactPath) { Write-Output ("ACTION_ARTIFACT_PATH={0}" -f $result.ActionArtifactPath) }
  if ($result.StagedPath) { Write-Output ("STAGED_PATH={0}" -f $result.StagedPath) }
} else {
  if ($session.SummaryPath -and (Test-Path -LiteralPath $session.SummaryPath)) { Write-Output ("ENRICH_REPORT_PATH={0}" -f $session.SummaryPath) }
}
Write-Output ("SESSION_STATUS={0}" -f $sessionStatus)
if ($finalizeSkipped) { Write-Output "FINALIZE_STATUS=SKIPPED" }
if ($stateSaveSkipped) { Write-Output "STATE_SAVE_STATUS=SKIPPED" }
if ($bundlePath) {
  Write-Output ("ENRICH_BUNDLE_PATH={0}" -f $bundlePath)
  Write-Output ('NEXT_GET_FILE=get-file --path "{0}" --comment "Retrieve DCOIR enrich bundle"' -f $bundlePath)
} elseif ($actionSkipped -or $finalizeSkipped) {
  Write-Output "NEXT_OPTIONS=Re-run without -WhatIf and confirm the skipped enrich action or finalization writes to persist the requested work."
} else {
  Write-Output ("NEXT_OPTIONS=Continue current session with -EnrichSessionId {0} or finalize it with -FinalizeEnrichSession" -f $session.SessionId)
}
Write-Output ("DELETE_SCRIPT_COMMAND={0}" -f $deleteScriptCommand)
if ($sessionStatus -eq "FINALIZED") {
  Write-QuickNextSteps -Phase "EnrichFinalized"
} else {
  Write-QuickNextSteps -Phase "EnrichOpen"
}
}
