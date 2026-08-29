<#
.SYNOPSIS
DCOIR collector enrich-mode review action handlers.

.DESCRIPTION
Implements the analyst-review style enrichment actions that operate on already-collected
targets, such as signature review, loaded-module inspection, access review, strings,
alternate data stream inspection, refreshed TCP connection review, and event-log text
export. The file packages the action output into session artifacts and appends the
results to the active enrich-session summary.

.FILE NAME
DCOIR_Collector.03B_Enrich_Actions_Review.ps1

.INPUTS
Collector state, active enrichment session, resolved tool map, and action-specific
parameters such as Path, ServiceName, RegistryPath, LogName, TargetPid, Hours, EventId,
and MaxEvents.

.OUTPUTS
Hashtable containing the enrich summary path, action artifact path, and any staged path
produced by the selected action.
#>

<#
.SYNOPSIS
Runs one enrich-mode review action and writes the result into the active session.

.DESCRIPTION
Selects the requested enrich action, validates required parameters and tool presence,
collects the action output, wraps it in analyst-facing interpretation text, writes the
per-action artifact, appends the result to the session summary, and increments the
session action count. Retrieval-oriented actions are delegated to the retrieval helper
file when the action does not match one of the local review cases.

.FUNCTION NAME
Invoke-EnrichmentAction

.INPUTS
Collector state hashtable, active enrichment-session hashtable, and ToolMap hashtable.
The function also relies on current enrich action parameters already bound in the wider
collector runtime, including Action, Path, ServiceName, RegistryPath, LogName,
TargetPid, Hours, EventId, and MaxEvents.

.OUTPUTS
Hashtable containing ReportPath, ActionArtifactPath, and StagedPath values for the
executed enrich action.
#>
function Invoke-EnrichmentAction {
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
  if ($Path) { $actionTarget = $Path }
  elseif ($ServiceName) { $actionTarget = $ServiceName }
  elseif ($RegistryPath) { $actionTarget = $RegistryPath }
  elseif ($LogName) { $actionTarget = $LogName }
  elseif ($TargetPid) { $actionTarget = "PID_$TargetPid" }

  switch ($Action) {
    "SigcheckPath" {
      if (-not $Path) { throw "SigcheckPath requires -Path" }
      if (-not $ToolMap.sigcheck) { throw "sigcheck tool not found in staged tools directory." }
    }
    "ListDllsPid" {
      if (-not $TargetPid) { throw "ListDllsPid requires -TargetPid" }
      if (-not $ToolMap.listdlls) { throw "listdlls tool not found in staged tools directory." }
    }
    "AccessChkFile" {
      if (-not $Path) { throw "AccessChkFile requires -Path" }
      if (-not $ToolMap.accesschk) { throw "accesschk tool not found in staged tools directory." }
    }
    "AccessChkService" {
      if (-not $ServiceName) { throw "AccessChkService requires -ServiceName" }
      if (-not $ToolMap.accesschk) { throw "accesschk tool not found in staged tools directory." }
    }
    "AccessChkReg" {
      if (-not $RegistryPath) { throw "AccessChkReg requires -RegistryPath" }
      if (-not $ToolMap.accesschk) { throw "accesschk tool not found in staged tools directory." }
    }
    "StringsPath" {
      if (-not $Path) { throw "StringsPath requires -Path" }
      if (-not $ToolMap.strings) { throw "strings tool not found in staged tools directory." }
    }
    "StreamsPath" {
      if (-not $Path) { throw "StreamsPath requires -Path" }
      if (-not $ToolMap.streams) { throw "streams tool not found in staged tools directory." }
    }
    "TcpvconRefresh" {
      if (-not $ToolMap.tcpvcon) { throw "tcpvcon tool not found in staged tools directory." }
    }
    "LogText" {
      if (-not $LogName) { throw "LogText requires -LogName" }
    }
    default {
      return Invoke-EnrichmentAction-Retrieval -State $State -Session $Session -ToolMap $ToolMap
    }
  }

  if (-not $PSCmdlet.ShouldProcess($actionTarget, ("Run enrich review action {0}" -f $Action))) {
    return @{
      ReportPath = $null
      ActionArtifactPath = $null
      StagedPath = $null
      ActionSkipped = $true
      ActionStatus = 'SKIPPED'
    }
  }

  switch ($Action) {
    "SigcheckPath" {
      if (-not $Path) { throw "SigcheckPath requires -Path" }
      if (-not $ToolMap.sigcheck) { throw "sigcheck tool not found in staged tools directory." }
      $reason = "Signature and hash review for a suspicious path."
      $targetDetails = "Path=$Path"
      $outputText = Invoke-ToolToText -ToolPath $ToolMap.sigcheck -Arguments @("-accepteula","-nobanner","-h",$Path) -StepName "ENRICH_SIGCHECK_PATH"
      $interpretation = "Review signer, hashes, version data, and whether the signer matches the expected vendor."
      $nextStep = "If signer or path looks suspicious, stage the file with PullSuspiciousFile."
    }
    "ListDllsPid" {
      if (-not $TargetPid) { throw "ListDllsPid requires -TargetPid" }
      if (-not $ToolMap.listdlls) { throw "listdlls tool not found in staged tools directory." }
      $reason = "Loaded module review for a suspicious process."
      $targetDetails = "Pid=$TargetPid"
      $outputText = Invoke-ToolToText -ToolPath $ToolMap.listdlls -Arguments @("-accepteula","-nobanner","-v",$TargetPid.ToString()) -StepName "ENRICH_LISTDLLS_PID"
      $interpretation = "Review unexpected DLL paths, unsigned DLLs, and DLLs loaded from user-writable paths."
      $nextStep = "If a suspicious DLL path is present, stage it with PullSuspiciousFile."
    }
    "AccessChkFile" {
      if (-not $Path) { throw "AccessChkFile requires -Path" }
      if (-not $ToolMap.accesschk) { throw "accesschk tool not found in staged tools directory." }
      $reason = "Effective access review for a suspicious file or directory."
      $targetDetails = "Path=$Path"
      $outputText = Invoke-ToolToText -ToolPath $ToolMap.accesschk -Arguments @("-accepteula","-nobanner","-v",$Path) -StepName "ENRICH_ACCESSCHK_FILE"
      $interpretation = "Review whether broad write access or weak ACLs explain persistence or tampering risk."
      $nextStep = "If write access is too broad, document the ACL issue for remediation."
    }
    "AccessChkService" {
      if (-not $ServiceName) { throw "AccessChkService requires -ServiceName" }
      if (-not $ToolMap.accesschk) { throw "accesschk tool not found in staged tools directory." }
      $reason = "Effective access review for a suspicious service."
      $targetDetails = "ServiceName=$ServiceName"
      $outputText = Invoke-ToolToText -ToolPath $ToolMap.accesschk -Arguments @("-accepteula","-nobanner","-c",$ServiceName) -StepName "ENRICH_ACCESSCHK_SERVICE"
      $interpretation = "Review whether low-privilege principals can change or control the service."
      $nextStep = "If service rights are weak, stage the service binary or review the service path."
    }
    "AccessChkReg" {
      if (-not $RegistryPath) { throw "AccessChkReg requires -RegistryPath" }
      if (-not $ToolMap.accesschk) { throw "accesschk tool not found in staged tools directory." }
      $reason = "Effective access review for a suspicious registry location."
      $targetDetails = "RegistryPath=$RegistryPath"
      $outputText = Invoke-ToolToText -ToolPath $ToolMap.accesschk -Arguments @("-accepteula","-nobanner","-k","-u","-v",$RegistryPath) -StepName "ENRICH_ACCESSCHK_REG"
      $interpretation = "Review whether the registry key has weak write permissions."
      $nextStep = "If write access is weak, capture the exact principal and registry path for remediation."
    }
    "StringsPath" {
      if (-not $Path) { throw "StringsPath requires -Path" }
      if (-not $ToolMap.strings) { throw "strings tool not found in staged tools directory." }
      $reason = "Readable string extraction for a suspicious file."
      $targetDetails = "Path=$Path"
      $outputText = Invoke-ToolToText -ToolPath $ToolMap.strings -Arguments @("-accepteula","-nobanner","-n","4",$Path) -StepName "ENRICH_STRINGS_PATH"
      $interpretation = "Review URLs, domains, IPs, command lines, registry keys, mutex names, and suspicious paths."
      $nextStep = "If strings show a second-stage file path or URL, follow that thread next."
    }
    "StreamsPath" {
      if (-not $Path) { throw "StreamsPath requires -Path" }
      if (-not $ToolMap.streams) { throw "streams tool not found in staged tools directory." }
      $reason = "Alternate data stream review for a suspicious path."
      $targetDetails = "Path=$Path"
      $outputText = Invoke-ToolToText -ToolPath $ToolMap.streams -Arguments @("-accepteula",$Path) -StepName "ENRICH_STREAMS_PATH"
      $interpretation = "Review named streams that could hide payloads or mark file-of-origin data."
      $nextStep = "If a suspicious stream is present, stage the parent file for offline review."
    }
    "TcpvconRefresh" {
      if (-not $ToolMap.tcpvcon) { throw "tcpvcon tool not found in staged tools directory." }
      $reason = "Fresh command-line TCPView snapshot for network review."
      $targetDetails = "Action=TcpvconRefresh"
      $outputText = Invoke-ToolToText -ToolPath $ToolMap.tcpvcon -Arguments @("-accepteula","-nobanner") -StepName "ENRICH_TCPVCON_REFRESH"
      $interpretation = "Review owning processes and endpoint pairs against netstat output."
      $nextStep = "If a suspicious owning process is present, inspect that PID next."
    }
    "LogText" {
      if (-not $LogName) { throw "LogText requires -LogName" }
      $reason = "Text export for a Windows event channel."
      $targetDetails = Get-CollectorEventWindowTargetDetails -LogName $LogName -Hours $Hours -Ids $EventId -Take $MaxEvents
      $outputText = Get-EventText -Channel $LogName -WindowHours $Hours -Ids $EventId -Take $MaxEvents
      $interpretation = "Review exact timestamps, Event IDs, process names, accounts, and error details."
      $nextStep = "If text volume is too high or message fidelity is not enough, use LogRaw."
    }
    default {
      return Invoke-EnrichmentAction-Retrieval -State $State -Session $Session -ToolMap $ToolMap
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

  if (-not $artifactPath -or -not $summaryAppended) {
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
