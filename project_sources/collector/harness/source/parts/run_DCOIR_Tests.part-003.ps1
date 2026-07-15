    [Parameter(Mandatory=$true)]
    [AllowEmptyString()]
    [string[]]$CollectorArgs,
    [Parameter(Mandatory=$true)][hashtable]$EnvOverrides
  )

  $previous = @{}
  $effectiveEnvOverrides = @{}
  foreach ($name in $EnvOverrides.Keys) {
    $effectiveEnvOverrides[$name] = $EnvOverrides[$name]
  }
  if (-not $effectiveEnvOverrides.ContainsKey('DCOIR_COLLECTOR_TEST_MODE')) {
    $effectiveEnvOverrides['DCOIR_COLLECTOR_TEST_MODE'] = '1'
  }

  try {
    foreach ($name in $effectiveEnvOverrides.Keys) {
      $previous[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
      [Environment]::SetEnvironmentVariable($name, [string]$effectiveEnvOverrides[$name], 'Process')
    }
    return Invoke-CollectorStep -StepName $StepName -CollectorArgs $CollectorArgs
  } finally {
    foreach ($name in $effectiveEnvOverrides.Keys) {
      [Environment]::SetEnvironmentVariable($name, $previous[$name], 'Process')
    }
  }
}

<#
.SYNOPSIS
Runs one harness step that is expected to fail in a specific way.

.DESCRIPTION
Runs the collector directly, captures stdout and stderr, compares the result to the
expected bind-reject or runtime-error outcome, checks for required text patterns, logs
the result, and returns the harness result object.

.FUNCTION NAME
Invoke-ExpectedFailureStep

.INPUTS
Mandatory StepName, CollectorArgs, and ExpectedOutcome, plus optional ExpectedPatterns.

.OUTPUTS
PSCustomObject containing the observed failure behavior and harness log path.
#>
function Invoke-ExpectedFailureStep {
  param(
    [Parameter(Mandatory=$true)][string]$StepName,
    [Parameter(Mandatory=$true)]
    [AllowEmptyString()]
    [string[]]$CollectorArgs,
    [Parameter(Mandatory=$true)][ValidateSet('BIND_REJECT','RUNTIME_ERROR')][string]$ExpectedOutcome,
    [string[]]$ExpectedPatterns
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

  $missingPatterns = New-Object System.Collections.ArrayList
  foreach ($pattern in @($ExpectedPatterns)) {
    if (-not [string]::IsNullOrWhiteSpace($pattern) -and -not [regex]::IsMatch($stdout, [regex]::Escape($pattern))) {
      [void]$missingPatterns.Add($pattern)
    }
  }

  $status = 'FAIL'
  $message = ''
  if ($processResult.TimedOut) {
    $message = 'Collector process timed out before expected failure behavior was observed.'
  } else {
    switch ($ExpectedOutcome) {
      'BIND_REJECT' {
        $observedNativeBindReject = $exitCode -ne 0 -and [string]::IsNullOrWhiteSpace($collectorReportedStatus) -and @($missingPatterns).Count -eq 0
        $observedExecutableRuntimeReject = $script:ResolvedCollectorInvocationMode -eq 'Executable' -and $exitCode -ne 0 -and @($missingPatterns).Count -eq 0
        if ($observedNativeBindReject -or $observedExecutableRuntimeReject) {
          $status = 'PASS'
          if ($observedExecutableRuntimeReject) {
            $message = 'Observed expected executable nonzero reject behavior for bind-reject gate.'
          } else {
            $message = 'Observed expected bind-reject behavior.'
          }
        } else {
          $message = 'Expected bind-reject behavior was not observed.'
        }
      }
      'RUNTIME_ERROR' {
        if ($exitCode -ne 0 -and $collectorReportedStatus -eq 'ERROR' -and @($missingPatterns).Count -eq 0) {
          $status = 'PASS'
          $message = 'Observed expected runtime-error behavior.'
        } else {
          $message = 'Expected runtime-error behavior was not observed.'
        }
      }
    }
  }

  if (@($missingPatterns).Count -gt 0) {
    $message = ($message + ' Missing patterns: ' + (@($missingPatterns) -join '; ')).Trim()
  }

  $logLines = New-Object System.Collections.ArrayList
  [void]$logLines.Add("STEP=$StepName")
  [void]$logLines.Add("START=$($start.ToString('o'))")
  [void]$logLines.Add("END=$($end.ToString('o'))")
  [void]$logLines.Add(("DURATION_MS={0}" -f [int][Math]::Round(($end - $start).TotalMilliseconds)))
  [void]$logLines.Add("EXPECTED_OUTCOME=$ExpectedOutcome")
  [void]$logLines.Add("EXIT_CODE=$exitCode")
  [void]$logLines.Add("TIMED_OUT=$($processResult.TimedOut)")
  [void]$logLines.Add("TIMEOUT_SECONDS=$CollectorStepTimeoutSeconds")
  if ($collectorReportedStatus) { [void]$logLines.Add("COLLECTOR_STATUS=$collectorReportedStatus") }
  [void]$logLines.Add("STATUS=$status")
  if ($message) { [void]$logLines.Add("MESSAGE=$message") }
  [void]$logLines.Add(("COMMAND={0}" -f $invocation.DisplayCommand))
  [void]$logLines.Add("")
  [void]$logLines.Add("STDOUT:")
  [void]$logLines.Add($stdoutText)
  [void]$logLines.Add("")
  [void]$logLines.Add("STDERR:")
  [void]$logLines.Add($stderrText)
  $logPath = Write-HarnessLog -StepName $StepName -Lines $logLines
  Add-Result -StepName $StepName -Status $status -ExitCode $exitCode -RunId $null -EnrichSessionId $null -CollectorReportedStatus $collectorReportedStatus -LogPath $logPath -Start $start -End $end
  if ($status -ne 'PASS' -and -not $ContinueOnError) { throw $message }
  return [pscustomobject]@{
    StepName = $StepName
    Status = $status
    ExitCode = $exitCode
    CollectorReportedStatus = $collectorReportedStatus
    StdOut = $stdout
    LogPath = $logPath
  }
}

<#
.SYNOPSIS
Asserts that one collector step succeeded well enough for downstream verification.

.DESCRIPTION
Accepts PASS or PARTIAL_SUCCESS with exit code 0 and throws a detailed harness message
otherwise.

.FUNCTION NAME
Assert-CollectorStepSucceeded

.INPUTS
StepName string and CollectorStep result object.

.OUTPUTS
No direct output. Throws when the collector step is not acceptable for downstream use.
#>
function Assert-CollectorStepSucceeded {
  param(
    [string]$StepName,
    [object]$CollectorStep
  )

  if ($CollectorStep.ExitCode -eq 0 -and ($CollectorStep.Status -eq 'PASS' -or $CollectorStep.Status -eq 'PARTIAL_SUCCESS')) {
    return
  }

  $message = @(
    ("Collector step failed before downstream verification: {0}" -f $StepName),
    ("Collector harness status: {0}" -f $CollectorStep.Status),
    ("Collector reported status: {0}" -f $CollectorStep.CollectorReportedStatus),
    ("Collector step log: {0}" -f $CollectorStep.LogPath),
    "Collector stdout follows:",
    $CollectorStep.StdOut
  ) -join [Environment]::NewLine

  throw $message
}

<#
.SYNOPSIS
Asserts that one collector step degraded in the expected partial-success way.

.DESCRIPTION
Requires exit code 0, collector-reported PARTIAL_SUCCESS, and the expected diagnostic
patterns in stdout. Throws a detailed message when the degraded behavior is absent.

.FUNCTION NAME
Assert-CollectorStepDegradedPartial

.INPUTS
StepName string, CollectorStep result object, and ExpectedPatterns string array.

.OUTPUTS
No direct output. Throws when the expected degraded behavior is absent.
#>
function Assert-CollectorStepDegradedPartial {
  param(
    [string]$StepName,
    [object]$CollectorStep,
    [string[]]$ExpectedPatterns
  )

  $missingPatterns = New-Object System.Collections.ArrayList
  foreach ($pattern in @($ExpectedPatterns)) {
    if (-not [string]::IsNullOrWhiteSpace($pattern) -and -not [regex]::IsMatch($CollectorStep.StdOut, [regex]::Escape($pattern))) {
      [void]$missingPatterns.Add($pattern)
    }
  }

  if ($CollectorStep.ExitCode -eq 0 -and $CollectorStep.CollectorReportedStatus -eq 'PARTIAL_SUCCESS' -and @($missingPatterns).Count -eq 0) {
    return
  }

  $message = @(
    ("Collector step did not show the expected degraded partial behavior: {0}" -f $StepName),
    ("Collector harness status: {0}" -f $CollectorStep.Status),
    ("Collector reported status: {0}" -f $CollectorStep.CollectorReportedStatus),
    ("Collector step log: {0}" -f $CollectorStep.LogPath),
    ("Missing patterns: {0}" -f (@($missingPatterns) -join '; ')),
    "Collector stdout follows:",
    $CollectorStep.StdOut
  ) -join [Environment]::NewLine

  throw $message
}

<#
.SYNOPSIS
Verifies the collect output contract fields.

.DESCRIPTION
