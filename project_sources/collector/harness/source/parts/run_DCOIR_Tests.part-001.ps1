    @{ Label='execution_context'; Path=$CollectorStep.ExecutionContextPath },
    @{ Label='security_audit_policy'; Path=$CollectorStep.SecurityAuditPolicyPath },
    @{ Label='security_filtered'; Path=$CollectorStep.SecurityFilteredPath },
    @{ Label='security_high_signal'; Path=$CollectorStep.SecurityHighSignalSummaryPath },
    @{ Label='netstat_pid_only'; Path=$CollectorStep.NetstatPidOnlyPath },
    @{ Label='analyst_overview'; Path=$CollectorStep.AnalystOverviewPath },
    @{ Label='parallel_execution_proof'; Path=$CollectorStep.ParallelExecutionProofPath },
    @{ Label='upload_summary'; Path=$CollectorStep.UploadSummaryPath },
    @{ Label='attachment_budget_manifest'; Path=$CollectorStep.AttachmentBudgetManifestPath },
    @{ Label='upload_safe_chunk_manifest'; Path=$CollectorStep.UploadSafeChunkManifestPath },
    @{ Label='collection_scope'; Path=$CollectorStep.CollectionScopePath },
    @{ Label='parallelism_assessment'; Path=$CollectorStep.ParallelismAssessmentPath },
    @{ Label='targeted_collection_plan'; Path=$CollectorStep.TargetedCollectionPlanPath },
    @{ Label='synthetic_oversize_source'; Path=$CollectorStep.SyntheticOversizeSourcePath },
    @{ Label='synthetic_chunk_manifest'; Path=$CollectorStep.ChunkManifestPath },
    @{ Label='collect_bundle'; Path=$CollectorStep.CollectBundlePath }
  )) {
    [void](Add-HarnessEvidenceFile -StepName $StepName -Path $row.Path -Label $row.Label)
  }
}

<#
.SYNOPSIS
Adds one result row to the harness results collection.

.DESCRIPTION
Normalizes the supplied execution metadata into one PSCustomObject and appends it to the
in-memory results list used by the suite summary outputs.

.FUNCTION NAME
Add-Result

.INPUTS
StepName, Status, ExitCode, RunId, EnrichSessionId, CollectorReportedStatus, LogPath,
Start, and End values.

.OUTPUTS
No direct output. Appends one result object to the in-memory results list.
#>
function Add-Result {
  param(
    [string]$StepName,
    [string]$Status,
    [int]$ExitCode,
    [string]$RunId,
    [string]$EnrichSessionId,
    [string]$CollectorReportedStatus,
    [string]$LogPath,
    [datetime]$Start,
    [datetime]$End
  )
  [void]$script:Results.Add([pscustomobject]@{
    StepName = $StepName
    Status = $Status
    ExitCode = $ExitCode
    RunId = $RunId
    EnrichSessionId = $EnrichSessionId
    CollectorReportedStatus = $CollectorReportedStatus
    LogPath = $LogPath
    Start = $Start.ToString("o")
    End = $End.ToString("o")
    DurationMs = [int][Math]::Round(($End - $Start).TotalMilliseconds)
  })
  Write-HarnessProgress -StepName $StepName -Phase 'completed' -Status $Status -RunId $RunId -SessionId $EnrichSessionId -LogPath $LogPath -Message ("ExitCode={0}; CollectorStatus={1}" -f $ExitCode, $CollectorReportedStatus)
}

<#
.SYNOPSIS
Quotes one argument value for process invocation display.

.DESCRIPTION
Returns an empty quoted string for null or empty input and quotes values containing
whitespace or quotes.

.FUNCTION NAME
Quote-Arg

.INPUTS
Value string.

.OUTPUTS
String safe-for-display argument token.
#>
function Quote-Arg {
  param([string]$Value)
  if ($null -eq $Value) { return '""' }
  if ($Value.Length -eq 0) { return '""' }
  if ($Value -match '[\s"]') {
    return '"' + ($Value -replace '"','\"') + '"'
  }
  return $Value
}

<#
.SYNOPSIS
Builds one display argument string from an argument array.

.DESCRIPTION
Quotes each argument with Quote-Arg and joins the resulting tokens with spaces.

.FUNCTION NAME
Build-ArgumentString

.INPUTS
ArgumentValues string array.

.OUTPUTS
String joined argument list.
#>
function Build-ArgumentString {
  param([string[]]$ArgumentValues)
  $parts = New-Object System.Collections.ArrayList
  foreach ($a in $ArgumentValues) {
    [void]$parts.Add((Quote-Arg -Value $a))
  }
  return ($parts -join ' ')
}

<#
.SYNOPSIS
Builds the collector process invocation for PS1 or optional EXE collector runtimes.

.DESCRIPTION
Returns the executable path, argument array, and display command used by harness steps.
PowerShell-file mode runs powershell.exe -File against the collector script. Executable
mode invokes the optional collector EXE directly while preserving the same collector
argument surface used by the PS1 runtime.

.FUNCTION NAME
New-CollectorInvocation

.INPUTS
CollectorArgs string array.

.OUTPUTS
PSCustomObject containing FileName, Arguments, and DisplayCommand.
#>
function New-CollectorInvocation {
  param([string[]]$CollectorArgs)
  if ($script:ResolvedCollectorInvocationMode -eq "Executable") {
    return [pscustomobject]@{
      FileName = $CollectorFullPath
      Arguments = @($CollectorArgs)
      DisplayCommand = ("{0} {1}" -f (Quote-Arg -Value $CollectorFullPath), (Build-ArgumentString -ArgumentValues $CollectorArgs)).Trim()
    }
  }

  $invokeArgs = @("-NoProfile","-ExecutionPolicy","Bypass","-File",$CollectorFullPath) + $CollectorArgs
  return [pscustomobject]@{
    FileName = 'powershell.exe'
    Arguments = $invokeArgs
    DisplayCommand = ("powershell.exe {0}" -f (Build-ArgumentString -ArgumentValues $invokeArgs))
  }
}

<#
.SYNOPSIS
Restores the working collector ZIP from the master ZIP.

.DESCRIPTION
Copies the master ZIP into the working ZIP path, logs the operation as a harness result,
and throws if the master ZIP is missing.

.FUNCTION NAME
Restore-WorkingZip

.INPUTS
Reason string used in the harness step name.

.OUTPUTS
No direct output. Copies the ZIP and logs the result.
#>
function Restore-WorkingZip {
  param([string]$Reason)
  $stepName = "ZZ_RestoreWorkingZip_{0}" -f ($Reason -replace '[^A-Za-z0-9_-]','_')
  $start = Get-Date
  if (-not (Test-Path -LiteralPath $MasterZipFullPath)) {
    $end = Get-Date
    $logPath = Write-HarnessLog -StepName $stepName -Lines @("STEP=$stepName","STATUS=FAIL","MESSAGE=Master zip not found.","MASTER_ZIP=$MasterZipFullPath","WORKING_ZIP=$WorkingZipPath")
    Add-Result -StepName $stepName -Status "FAIL" -ExitCode 1 -RunId $null -EnrichSessionId $null -CollectorReportedStatus $null -LogPath $logPath -Start $start -End $end
    throw ("Master zip not found: {0}" -f $MasterZipFullPath)
  }
  Copy-Item -LiteralPath $MasterZipFullPath -Destination $WorkingZipPath -Force
  $status = "PASS"
  $end = Get-Date
  $logPath = Write-HarnessLog -StepName $stepName -Lines @("STEP=$stepName","STATUS=$status","MASTER_ZIP=$MasterZipFullPath","WORKING_ZIP=$WorkingZipPath")
  Add-Result -StepName $stepName -Status $status -ExitCode 0 -RunId $null -EnrichSessionId $null -CollectorReportedStatus $null -LogPath $logPath -Start $start -End $end
}

<#
.SYNOPSIS
Maps collector process status into harness step status.

.DESCRIPTION
Returns FAIL on nonzero exit code, PARTIAL_SUCCESS when the collector reported that
status, and PASS otherwise.

.FUNCTION NAME
Resolve-CollectorStepStatus

.INPUTS
ExitCode integer and CollectorReportedStatus string.

.OUTPUTS
String harness status value.
#>
function Resolve-CollectorStepStatus {
  param([int]$ExitCode,[string]$CollectorReportedStatus)
  if ($ExitCode -ne 0) { return "FAIL" }
  if ($CollectorReportedStatus -eq "PARTIAL_SUCCESS") { return "PARTIAL_SUCCESS" }
  return "PASS"
}

<#
.SYNOPSIS
Runs one collector process with a bounded timeout.

.DESCRIPTION
Starts the prepared collector invocation, captures stdout and stderr asynchronously,
kills the process tree if it exceeds the configured timeout, bounds pipe-drain waits,
and emits live start/end markers for workflow-log readback.

.FUNCTION NAME
Invoke-CollectorProcess

.INPUTS
Mandatory StepName string and prepared Invocation object.

.OUTPUTS
PSCustomObject containing start/end timestamps, exit code, stdout, stderr, and timeout flag.
#>
function Invoke-CollectorProcess {
  param(
    [Parameter(Mandatory=$true)][string]$StepName,
    [Parameter(Mandatory=$true)][object]$Invocation
  )

  $start = Get-Date
  $commandDisplay = ("{0} {1}" -f $Invocation.FileName, (Build-ArgumentString -ArgumentValues @($Invocation.Arguments))).Trim()
  Write-Host ("HARNESS_STEP_START step={0} timeout_seconds={1}" -f $StepName, $CollectorStepTimeoutSeconds)
  Write-HarnessProgress -StepName $StepName -Phase 'starting' -Status 'STARTED' -Command $commandDisplay -TimeoutSeconds $CollectorStepTimeoutSeconds
  $process = New-Object System.Diagnostics.Process
  $process.StartInfo = New-Object System.Diagnostics.ProcessStartInfo
  $process.StartInfo.FileName = $Invocation.FileName
  $process.StartInfo.UseShellExecute = $false
  $process.StartInfo.RedirectStandardOutput = $true
