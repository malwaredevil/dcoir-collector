<#
.SYNOPSIS
DCOIR collector enrich-mode retrieval action handlers.

.DESCRIPTION
Implements the retrieval-oriented enrichment actions that stage files or raw event-log
exports for analyst pickup after baseline collection. These helpers stage the selected
targets, write analyst guidance into the active enrich-session summary, and return the
paths needed for follow-on retrieval.

.FILE NAME
DCOIR_Collector.03C_Enrich_Actions_Retrieval.ps1

.INPUTS
Collector state, active enrichment session, resolved tool map, and action-specific
parameters such as Path, ServiceName, LogName, Hours, EventId, and TargetPid.

.OUTPUTS
Hashtable containing the enrich summary path, action artifact path, and any staged path
produced by the selected retrieval action.
#>

<#
.SYNOPSIS
Runs one retrieval-style enrichment action and stages the requested artifact.

.DESCRIPTION
Selects the requested retrieval action, validates required parameters, stages the target
artifact or EVTX export, builds analyst-facing interpretation guidance, writes the
session artifact, appends the result to the session summary, and increments the session
action count.

.FUNCTION NAME
Invoke-EnrichmentAction-Retrieval

.INPUTS
Collector state hashtable, active enrichment-session hashtable, and ToolMap hashtable.
The function also relies on current enrich action parameters already bound in the wider
collector runtime, including Action, Path, ServiceName, LogName, Hours, and EventId.

.OUTPUTS
Hashtable containing ReportPath, ActionArtifactPath, and StagedPath values for the
executed retrieval action.
#>
function Invoke-EnrichmentAction-Retrieval {
  [CmdletBinding(SupportsShouldProcess=$true)]
  param(
    [hashtable]$State,
    [hashtable]$Session,
    [hashtable]$ToolMap
  )

  $sessionArtifactsDir = $Session.ArtifactsDir
  $sessionStagedDir = $Session.StagedDir
  $sessionSummaryPath = $Session.SummaryPath
  $sessionLogsDir = $Session.LogsDir

  $stagedPath = $null
  $reason = $null
  $targetDetails = $null
  $outputText = $null
  $interpretation = $null
  $nextStep = $null

  $actionTarget = $Action
  switch ($Action) {
    "LogRaw" {
      if (-not $LogName) { throw "LogRaw requires -LogName" }
      $actionTarget = $LogName
    }
    "PullSuspiciousFile" {
      if (-not $Path) { throw "PullSuspiciousFile requires -Path" }
      $actionTarget = $Path
    }
    "PullScriptOrConfig" {
      if (-not $Path) { throw "PullScriptOrConfig requires -Path" }
      $actionTarget = $Path
    }
    "PullTaskXml" {
      if (-not $Path) { throw "PullTaskXml requires -Path with the task name, for example \Microsoft\Windows\TaskName" }
      $actionTarget = $Path
    }
    "PullServiceBinary" {
      if (-not $ServiceName) { throw "PullServiceBinary requires -ServiceName" }
      $actionTarget = $ServiceName
    }
    "PullWmiReferencedFile" {
      if (-not $Path) { throw "PullWmiReferencedFile requires -Path" }
      $actionTarget = $Path
    }
    default {
      throw "Unsupported enrichment action: $Action"
    }
  }

  if (-not $PSCmdlet.ShouldProcess($actionTarget, ("Run enrich retrieval action {0}" -f $Action))) {
    return @{
      ReportPath = $null
      ActionArtifactPath = $null
      StagedPath = $null
      ActionSkipped = $true
      ActionStatus = 'SKIPPED'
    }
  }

  switch ($Action) {
    "LogRaw" {
      if (-not $LogName) { throw "LogRaw requires -LogName" }
      $reason = "Raw EVTX export for analyst workstation review."
      $rawEvtxFilterText = "Raw EVTX filter scope: LogName, effective event window, and optional EventId values. MaxEvents does not limit raw EVTX export size."
      $rawEvtxFilters = @('LogName','EffectiveEventWindow')
      if ($EventId -and @($EventId).Count -gt 0) { $rawEvtxFilters += 'EventIds' }
      $rawEvtxFiltersText = ($rawEvtxFilters -join ',')
      $targetDetails = Get-CollectorEventWindowTargetDetails -LogName $LogName -Hours $Hours -Ids $EventId
      $safeLogName = ($LogName -replace '[\\/:*?"<>|]','_')
      $plannedStagedPath = Join-Path $sessionStagedDir (New-StageName -Prefix ("STAGED_LogRaw_" + $safeLogName) -Extension ".evtx")
      Export-FilteredEvtx -LogChannel $LogName -WindowHours $Hours -Ids $EventId -OutPath $plannedStagedPath -ScratchDir $sessionLogsDir
      if (Test-Path -LiteralPath $plannedStagedPath) {
        $stagedPath = $plannedStagedPath
        $outputText = "Raw EVTX exported and staged for retrieval.`r`nRAW_EVTX_FILTERS=$rawEvtxFiltersText`r`nRAW_EVTX_EVENT_COUNT_CAP=NotApplied`r`nSTAGED_PATH=$stagedPath"
      } else {
        $outputText = "Raw EVTX export was skipped or did not create a staged artifact.`r`nRAW_EVTX_FILTERS=$rawEvtxFiltersText`r`nRAW_EVTX_EVENT_COUNT_CAP=NotApplied"
      }
      $interpretation = "Open the EVTX in Event Viewer on the analyst workstation with Action > Open Saved Log. $rawEvtxFilterText"
      $nextStep = "Retrieve the EVTX with get-file and review it in Event Viewer. If the file is too large, narrow LogName, Hours or explicit WindowStart/WindowEnd, or EventId before exporting again."
    }
    "PullSuspiciousFile" {
      if (-not $Path) { throw "PullSuspiciousFile requires -Path" }
      $reason = "Stage a suspicious file for analyst retrieval."
      $targetDetails = "Path=$Path"
      $stagedPath = Stage-PathCopy -SourcePath $Path -StagedDir $sessionStagedDir
      $outputText = if ($stagedPath) { "Suspicious file staged for retrieval.`r`nSTAGED_PATH=$stagedPath" } else { "Suspicious file staging was skipped; no staged artifact was created." }
      $interpretation = "Retrieve the file with get-file, then review locally with sigcheck and strings or upload to a sandbox if policy allows."
      $nextStep = "After retrieval, run sigcheck and strings on the analyst workstation."
    }
    "PullScriptOrConfig" {
      if (-not $Path) { throw "PullScriptOrConfig requires -Path" }
      $reason = "Stage a script or configuration file for analyst review."
      $targetDetails = "Path=$Path"
      $stagedPath = Stage-PathCopy -SourcePath $Path -StagedDir $sessionStagedDir
      $outputText = if ($stagedPath) { "Script or config staged for retrieval.`r`nSTAGED_PATH=$stagedPath" } else { "Script or config staging was skipped; no staged artifact was created." }
      $interpretation = "Retrieve the file, open it in a text editor, and upload plain text to the AFRICOM SOC IR AI."
      $nextStep = "If the file references other paths or URLs, follow the next most suspicious reference."
    }
    "PullTaskXml" {
      if (-not $Path) { throw "PullTaskXml requires -Path with the task name, for example \Microsoft\Windows\TaskName" }
      $reason = "Export scheduled task XML for analyst review."
      $targetDetails = "TaskName=$Path"
      $taskXml = Get-TaskXml -TaskName $Path
      $plannedStagedPath = Join-Path $sessionStagedDir (New-StageName -Prefix "STAGED_TASK_XML" -Extension ".xml")
      Set-Content -Path $plannedStagedPath -Value $taskXml -Encoding UTF8 -ErrorAction Stop
      if (Test-Path -LiteralPath $plannedStagedPath) {
        $stagedPath = $plannedStagedPath
      }
      $outputText = if ($stagedPath) { "Task XML exported and staged for retrieval.`r`nSTAGED_PATH=$stagedPath" } else { "Task XML staging was skipped; no staged artifact was created." }
      $interpretation = "Review author, principal, triggers, actions, working directory, and command arguments."
      $nextStep = "If the action points to a file path, stage that file next."
    }
    "PullServiceBinary" {
      if (-not $ServiceName) { throw "PullServiceBinary requires -ServiceName" }
      $reason = "Stage the binary referenced by a suspicious service."
      $targetDetails = "ServiceName=$ServiceName"
      $svcPath = Get-ServiceBinaryPath -Name $ServiceName
      if (-not $svcPath) { throw "Unable to resolve service binary path for service [$ServiceName]." }
      $stagedPath = Stage-PathCopy -SourcePath $svcPath -StagedDir $sessionStagedDir
      $outputText = if ($stagedPath) { "Service binary staged for retrieval.`r`nSERVICE_BINARY_PATH=$svcPath`r`nSTAGED_PATH=$stagedPath" } else { "Service binary staging was skipped; no staged artifact was created.`r`nSERVICE_BINARY_PATH=$svcPath" }
      $interpretation = "Retrieve the binary, then review locally with sigcheck and strings or upload to a sandbox if policy allows."
      $nextStep = "If the binary is unsigned or suspicious, correlate with service creation or modification events."
    }
    "PullWmiReferencedFile" {
      if (-not $Path) { throw "PullWmiReferencedFile requires -Path" }
      $reason = "Stage a file referenced by suspicious WMI persistence."
      $targetDetails = "Path=$Path"
      $stagedPath = Stage-PathCopy -SourcePath $Path -StagedDir $sessionStagedDir
      $outputText = if ($stagedPath) { "WMI-referenced file staged for retrieval.`r`nSTAGED_PATH=$stagedPath" } else { "WMI-referenced file staging was skipped; no staged artifact was created." }
      $interpretation = "Review the referenced script or binary as a persistence payload."
      $nextStep = "Correlate the file with WMI filter and consumer details in Tier 2 output."
    }
    default {
      throw "Unsupported enrichment action: $Action"
    }
  }

  $targetLabel = $Action
  if ($Path) { $targetLabel = $Path }
  elseif ($ServiceName) { $targetLabel = $ServiceName }
  elseif ($RegistryPath) { $targetLabel = $RegistryPath }
  elseif ($LogName) { $targetLabel = $LogName }
  elseif ($TargetPid) { $targetLabel = "PID_$TargetPid" }

  $actionBuilder = New-Object System.Text.StringBuilder
  Add-Section -Builder $actionBuilder -Name "ENRICHMENT_METADATA" -Text (
    @(
      "CollectorVersion=$ScriptVersion"
      "Mode=Enrich"
      "Action=$Action"
      "Host=$env:COMPUTERNAME"
      "RunId=$($State.RunId)"
      "EnrichSessionId=$($Session.SessionId)"
      "TimeLocal=$(Get-Date -Format o)"
      "TimeUTC=$((Get-Date).ToUniversalTime().ToString('o'))"
      "SessionRoot=$($Session.SessionRoot)"
    ) -join [Environment]::NewLine
  )
  Add-Section -Builder $actionBuilder -Name "TRIGGER_REASON" -Text $reason
  Add-Section -Builder $actionBuilder -Name "TARGET_DETAILS" -Text $targetDetails
  Add-Section -Builder $actionBuilder -Name "ACTION_OUTPUT" -Text $outputText
  Add-Section -Builder $actionBuilder -Name "ANALYST_INTERPRETATION_GUIDE" -Text $interpretation
  Add-Section -Builder $actionBuilder -Name "NEXT_BEST_STEP" -Text $nextStep
  if (@($Global:CollectorErrors).Count -gt 0) {
    Add-Section -Builder $actionBuilder -Name "ERRORS" -Text ($Global:CollectorErrors -join [Environment]::NewLine)
  }

  $artifactPath = Write-SessionArtifactText -SessionArtifactsDir $sessionArtifactsDir -ActionName $Action -TargetLabel $targetLabel -Text $actionBuilder.ToString() -Confirm:$false
  $summaryAppended = $false
  if ($artifactPath) {
    Add-Content -Path $sessionSummaryPath -Value $actionBuilder.ToString() -Encoding UTF8 -ErrorAction Stop
    $summaryAppended = $true
  }
  $reportPath = if ($summaryAppended) { $sessionSummaryPath } else { $null }

  if (-not $stagedPath -or -not $artifactPath -or -not $summaryAppended) {
    return @{
      ReportPath = $reportPath
      ActionArtifactPath = $artifactPath
      StagedPath = $stagedPath
      ActionSkipped = $true
      ActionStatus = 'SKIPPED'
    }
  }

  $Session.ActionCount = [int]$Session.ActionCount + 1

  return @{
    ReportPath = $reportPath
    ActionArtifactPath = $artifactPath
    StagedPath = $stagedPath
    ActionSkipped = $false
    ActionStatus = 'RECORDED'
  }
}
