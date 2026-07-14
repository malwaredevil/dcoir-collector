  $process.StartInfo.RedirectStandardError = $true
  $process.StartInfo.CreateNoWindow = $true
  $process.StartInfo.Arguments = Build-ArgumentString -ArgumentValues @($Invocation.Arguments)
  [void]$process.Start()
  Write-HarnessProgress -StepName $StepName -Phase 'process_started' -Status 'RUNNING' -Command $commandDisplay -TimeoutSeconds $CollectorStepTimeoutSeconds -ProcessId $process.Id
  $stdoutTask = $process.StandardOutput.ReadToEndAsync()
  $stderrTask = $process.StandardError.ReadToEndAsync()
  $timedOut = -not $process.WaitForExit($script:CollectorStepTimeoutMilliseconds)
  if ($timedOut) {
    try {
      Start-Process -FilePath 'taskkill.exe' -ArgumentList @('/PID', $process.Id.ToString(), '/T', '/F') -NoNewWindow -Wait -ErrorAction SilentlyContinue | Out-Null
    } catch {
      try { $process.Kill() } catch { }
    }
    try { [void]$process.WaitForExit(5000) } catch { }
  }
  $stdoutText = if ($stdoutTask.Wait(5000)) { $stdoutTask.GetAwaiter().GetResult() } else { '[HARNESS_TIMEOUT_STDOUT_DRAIN_INCOMPLETE]' }
  $stderrText = if ($stderrTask.Wait(5000)) { $stderrTask.GetAwaiter().GetResult() } else { '[HARNESS_TIMEOUT_STDERR_DRAIN_INCOMPLETE]' }
  $exitCode = if ($timedOut) { -1001 } else { $process.ExitCode }
  $end = Get-Date
  Write-Host ("HARNESS_STEP_END step={0} exit_code={1} timed_out={2} duration_ms={3}" -f $StepName, $exitCode, $timedOut, [int][Math]::Round(($end - $start).TotalMilliseconds))
  $processStatus = if ($timedOut) { 'TIMED_OUT' } elseif ($exitCode -eq 0) { 'SUCCESS' } else { 'NONZERO_EXIT' }
  Write-HarnessProgress -StepName $StepName -Phase 'process_completed' -Status $processStatus -Command $commandDisplay -TimeoutSeconds $CollectorStepTimeoutSeconds -ProcessId $process.Id -Message ("ExitCode={0}; TimedOut={1}" -f $exitCode, $timedOut)

  return [pscustomobject]@{
    Start = $start
    End = $end
    ExitCode = $exitCode
    StdOutText = $stdoutText
    StdErrText = $stderrText
    TimedOut = [bool]$timedOut
  }
}

<#
.SYNOPSIS
Runs one collector step and captures its contract surface.

.DESCRIPTION
Builds the collector invocation, runs it through Invoke-CollectorProcess, writes a
per-step harness log, updates the tracked run/session identifiers, records the harness
result, and returns the parsed collector contract values used by downstream verifiers.

.FUNCTION NAME
Invoke-CollectorStep

.INPUTS
Mandatory StepName string and CollectorArgs string array.

.OUTPUTS
PSCustomObject containing harness status, parsed collector contract fields, stdout text,
and the step log path.
#>
function Invoke-CollectorStep {
  param(
    [Parameter(Mandatory=$true)][string]$StepName,
    [Parameter(Mandatory=$true)]
    [AllowEmptyString()]
    [string[]]$CollectorArgs
  )
  Ensure-Directory -Path $LogsDir
  $invocation = New-CollectorInvocation -CollectorArgs $CollectorArgs
  $processResult = Invoke-CollectorProcess -StepName $StepName -Invocation $invocation
  $start = $processResult.Start
  $end = $processResult.End
  $stdoutText = $processResult.StdOutText
  $stderrText = $processResult.StdErrText
  $exitCode = $processResult.ExitCode
  $stdout = @($stdoutText, $stderrText | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }) -join [Environment]::NewLine
  $collectorReportedStatus = Parse-OutputValue -Text $stdout -Key "STATUS"
  $logLines = New-Object System.Collections.ArrayList
  [void]$logLines.Add("STEP=$StepName")
  [void]$logLines.Add("START=$($start.ToString('o'))")
  [void]$logLines.Add("END=$($end.ToString('o'))")
  [void]$logLines.Add(("DURATION_MS={0}" -f [int][Math]::Round(($end - $start).TotalMilliseconds)))
  [void]$logLines.Add("EXIT_CODE=$exitCode")
  [void]$logLines.Add("TIMED_OUT=$($processResult.TimedOut)")
  [void]$logLines.Add("TIMEOUT_SECONDS=$CollectorStepTimeoutSeconds")
  if ($collectorReportedStatus) { [void]$logLines.Add("COLLECTOR_STATUS=$collectorReportedStatus") }
  [void]$logLines.Add(("COMMAND={0}" -f $invocation.DisplayCommand))
  [void]$logLines.Add("")
  [void]$logLines.Add("STDOUT:")
  [void]$logLines.Add($stdout)
  $logPath = Write-HarnessLog -StepName $StepName -Lines $logLines
  $status = if ($processResult.TimedOut) { 'FAIL' } else { Resolve-CollectorStepStatus -ExitCode $exitCode -CollectorReportedStatus $collectorReportedStatus }
  $runId = Parse-OutputValue -Text $stdout -Key "RUN_ID"
  $sessionId = Parse-OutputValue -Text $stdout -Key "ENRICH_SESSION_ID"
  if ($runId) { $script:CollectorRunId = $runId }
  if ($sessionId) { $script:CollectorSessionId = $sessionId }
  Add-Result -StepName $StepName -Status $status -ExitCode $exitCode -RunId $runId -EnrichSessionId $sessionId -CollectorReportedStatus $collectorReportedStatus -LogPath $logPath -Start $start -End $end
  if ($processResult.TimedOut -and -not $ContinueOnError) {
    throw ("Collector step '{0}' timed out after {1} seconds." -f $StepName, $CollectorStepTimeoutSeconds)
  }
  $result = [pscustomobject]@{
    StepName = $StepName
    Status = $status
    ExitCode = $exitCode
    RunId = $runId
    EnrichSessionId = $sessionId
    CollectorReportedStatus = $collectorReportedStatus
    StdOut = $stdout
    LogPath = $logPath
    BaselineReportPath = Parse-OutputValue -Text $stdout -Key "BASELINE_REPORT_PATH"
    MetadataReportPath = Parse-OutputValue -Text $stdout -Key "METADATA_REPORT_PATH"
    ExecutionContextPath = Parse-OutputValue -Text $stdout -Key "EXECUTION_CONTEXT_PATH"
    SecurityAuditPolicyPath = Parse-OutputValue -Text $stdout -Key "SECURITY_AUDIT_POLICY_PATH"
    SecurityFilteredPath = Parse-OutputValue -Text $stdout -Key "SECURITY_FILTERED_PATH"
    NetstatPidOnlyPath = Parse-OutputValue -Text $stdout -Key "NETSTAT_PID_ONLY_PATH"
    AnalystOverviewPath = Parse-OutputValue -Text $stdout -Key "ANALYST_OVERVIEW_PATH"
    ParallelExecutionProofPath = Parse-OutputValue -Text $stdout -Key "PARALLEL_EXECUTION_PROOF_PATH"
    UploadSummaryPath = Parse-OutputValue -Text $stdout -Key "UPLOAD_SUMMARY_PATH"
    AttachmentBudgetManifestPath = Parse-OutputValue -Text $stdout -Key "ATTACHMENT_BUDGET_MANIFEST_PATH"
    UploadSafeChunkManifestPath = Parse-OutputValue -Text $stdout -Key "UPLOAD_SAFE_CHUNK_MANIFEST_PATH"
    CollectionScopePath = Parse-OutputValue -Text $stdout -Key "COLLECTION_SCOPE_PATH"
    ParallelismAssessmentPath = Parse-OutputValue -Text $stdout -Key "PARALLELISM_ASSESSMENT_PATH"
    TargetedCollectionPlanPath = Parse-OutputValue -Text $stdout -Key "TARGETED_COLLECTION_PLAN_PATH"
    SecurityHighSignalSummaryPath = Parse-OutputValue -Text $stdout -Key "SECURITY_HIGH_SIGNAL_SUMMARY_PATH"
    SyntheticOversizeSourcePath = Parse-OutputValue -Text $stdout -Key "SYNTHETIC_OVERSIZE_SOURCE_PATH"
    ChunkManifestPath = Parse-OutputValue -Text $stdout -Key "CHUNK_MANIFEST_PATH"
    DefaultGeminiUploadSetStatus = Parse-OutputValue -Text $stdout -Key "DEFAULT_GEMINI_UPLOAD_SET_STATUS"
    CollectBundlePath = Parse-OutputValue -Text $stdout -Key "COLLECT_BUNDLE_PATH"
    EnrichBundlePath = Parse-OutputValue -Text $stdout -Key "ENRICH_BUNDLE_PATH"
    SessionResolutionMode = Parse-OutputValue -Text $stdout -Key "SESSION_RESOLUTION_MODE"
    SessionStatus = Parse-OutputValue -Text $stdout -Key "SESSION_STATUS"
    NextGetFile = Parse-OutputValue -Text $stdout -Key "NEXT_GET_FILE"
    NextOptions = Parse-OutputValue -Text $stdout -Key "NEXT_OPTIONS"
    CleanupCommand = Parse-OutputValue -Text $stdout -Key "CLEANUP_COMMAND"
    DeleteScriptCommand = Parse-OutputValue -Text $stdout -Key "DELETE_SCRIPT_COMMAND"
    GeminiUploadGuidance = Parse-OutputValue -Text $stdout -Key "GEMINI_UPLOAD_GUIDANCE"
    CleanupStatus = Parse-OutputValue -Text $stdout -Key "CLEANUP_STATUS"
    HasQuickCommands = [regex]::IsMatch($stdout, '(?m)^NEXT_QUICK_COMMANDS$')
  }
  Add-CollectorStepEvidence -StepName $StepName -CollectorStep $result
  return $result
}

<#
.SYNOPSIS
Runs one collector step with temporary environment overrides.

.DESCRIPTION
Applies the supplied process-scope environment overrides plus the harness test-mode flag,
invokes one collector step, and restores the previous environment values afterward.

.FUNCTION NAME
Invoke-CollectorStepWithEnvOverride

.INPUTS
Mandatory StepName string, CollectorArgs string array, and EnvOverrides hashtable.

.OUTPUTS
Collector step result object returned by Invoke-CollectorStep.
#>
function Invoke-CollectorStepWithEnvOverride {
  param(
    [Parameter(Mandatory=$true)][string]$StepName,
