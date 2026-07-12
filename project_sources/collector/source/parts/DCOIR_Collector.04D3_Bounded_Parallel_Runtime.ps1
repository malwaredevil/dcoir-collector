<#
.SYNOPSIS
DCOIR collector bounded parallel worker orchestration helpers.

.DESCRIPTION
Defines the bounded parallel worker execution scriptblock, initializes worker jobs,
harvests cached command output, writes overlap proof artifacts, and exposes cached or
serial command text to baseline collection callers.

.FILE NAME
DCOIR_Collector.04D3_Bounded_Parallel_Runtime.ps1

.INPUTS
Collector state hashtable, baseline worker definitions, command strings, step names,
and allowed exit-code lists.

.OUTPUTS
Worker proof artifacts, cached command output text, collector notes/errors, and serial
or cached command text returned to the caller.
#>

<#
.SYNOPSIS
Returns the bounded parallel worker execution scriptblock.

.DESCRIPTION
Runs inside each Start-Job worker after Get-ParallelBaselineWorkerInitializationScript
loads worker-local helper functions into the job context.

.FUNCTION NAME
Get-ParallelBaselineWorkerScript

.INPUTS
No direct parameters.

.OUTPUTS
Scriptblock that captures all steps for one worker definition and writes its JSON result.
#>
function Get-ParallelBaselineWorkerScript {
  return {
    param([hashtable]$WorkerDefinition,[string]$ParallelWorkerDir,[int]$DefaultStepTimeoutSeconds)

    $started = Get-Date
    $stepResults = New-Object System.Collections.ArrayList
    foreach ($stepDefinition in @($WorkerDefinition.Steps)) {
      [void]$stepResults.Add((Invoke-WorkerCommandCapture -StepDefinition $stepDefinition))
    }
    $ended = Get-Date

    $status = 'OK'
    if (@($stepResults | Where-Object { -not $_.within_allowed_exit_codes }).Count -gt 0) {
      $status = 'PARTIAL_SUCCESS'
    }

    $workerResult = [ordered]@{
      worker_name = [string]$WorkerDefinition.Name
      status = $status
      start_time_utc = $started.ToUniversalTime().ToString('o')
      end_time_utc = $ended.ToUniversalTime().ToString('o')
      duration_ms = [int][Math]::Round(($ended - $started).TotalMilliseconds)
      worker_pid = $PID
      step_results = @($stepResults)
    }

    $resultPath = Join-Path $ParallelWorkerDir ('parallel_worker_{0}.json.txt' -f [string]$WorkerDefinition.Name)
    $workerJson = $workerResult | ConvertTo-Json -Depth 20 -ErrorAction Stop
    $workerJsonObject = $workerJson | ConvertFrom-Json -ErrorAction Stop
    if (Test-WorkerJsonContainsEllipsisSentinel -InputObject $workerJsonObject) {
      throw ('Parallel worker result JSON for [{0}] appears truncated; ConvertTo-Json emitted an ellipsis sentinel.' -f [string]$WorkerDefinition.Name)
    }
    Set-Content -Path $resultPath -Value ($workerJson + [Environment]::NewLine) -Encoding UTF8 -ErrorAction Stop
    return $resultPath
  }
}

<#
.SYNOPSIS
Initializes the bounded parallel baseline runtime for a collect run.

.DESCRIPTION
Resets the global cache, starts the bounded worker jobs during collect mode, enforces a
bounded parent wait, harvests successful worker output into the cache, writes the
overlap-proof artifact, records fallback notes for unsuccessful worker steps, and cleans
up the background jobs.

.FUNCTION NAME
Initialize-ParallelBaselineCache

.INPUTS
Collector state hashtable used to locate the artifacts directory and store the proof
artifact path.

.OUTPUTS
No direct return value. Updates global cache state, proof artifacts, and collector
notes/errors.
#>
function Initialize-ParallelBaselineCache {
  [CmdletBinding(SupportsShouldProcess=$true)]
  param([hashtable]$State)

  Reset-ParallelBaselineCache

  if ($Mode -ne 'Collect') { return }

  if ($WhatIfPreference) {
    Add-CollectorNote 'Parallel baseline runtime workers were skipped because WhatIf is active.'
    return
  }

  $workerDefinitions = @(Get-ParallelBaselineWorkerDefinitions)
  if (@($workerDefinitions).Count -lt 2) {
    Add-CollectorNote 'Parallel baseline runtime definitions were insufficient; collector will remain serial for this run.'
    return
  }

  if (-not $PSCmdlet.ShouldProcess('bounded parallel baseline runtime', 'Start collector baseline worker jobs')) {
    Add-CollectorNote 'Parallel baseline runtime workers were skipped because worker startup was not confirmed.'
    return
  }

  $workerDir = Join-Path $State.ArtifactsDir 'parallel_workers'
  Ensure-Directory -Path $workerDir

  $defaultWorkerStepTimeoutSeconds = Get-CollectorProcessCaptureTimeoutSeconds
  $parallelWorkerTimeoutSeconds = Get-ParallelBaselineWorkerTimeoutSeconds -WorkerDefinitions $workerDefinitions -DefaultStepTimeoutSeconds $defaultWorkerStepTimeoutSeconds
  $workerInitializationScript = Get-ParallelBaselineWorkerInitializationScript
  $workerScript = Get-ParallelBaselineWorkerScript

  $jobs = @()
  $workerTimeoutCount = 0
  try {
    foreach ($definition in $workerDefinitions) {
      $jobs += Start-Job -Name ('DCOIR_{0}' -f $definition.Name) -InitializationScript $workerInitializationScript -ScriptBlock $workerScript -ArgumentList $definition, $workerDir, $defaultWorkerStepTimeoutSeconds
    }

    if (@($jobs).Count -eq 0) {
      Add-CollectorNote 'Parallel baseline runtime could not start any workers; collector will remain serial for this run.'
      return
    }

    Wait-Job -Job $jobs -Timeout $parallelWorkerTimeoutSeconds | Out-Null
    $timedOutJobs = @($jobs | Where-Object { $_.State -eq 'Running' -or $_.State -eq 'NotStarted' })
    $workerTimeoutCount = @($timedOutJobs).Count
    foreach ($job in @($timedOutJobs)) {
      Add-CollectorError ('Parallel baseline worker job [{0}] timed out after {1} seconds; worker output will be skipped and affected steps will fall back to serial execution when needed.' -f $job.Name, $parallelWorkerTimeoutSeconds)
      try { Stop-Job -Job $job -ErrorAction SilentlyContinue } catch { }
      try { Wait-Job -Job $job -Timeout 5 | Out-Null } catch { }
      try {
        if ($job.State -eq 'Running' -or $job.State -eq 'NotStarted') {
          Add-CollectorError ('Parallel baseline worker job [{0}] remained [{1}] after stop attempt; cleanup will remove the job handle.' -f $job.Name, $job.State)
        }
      } catch { }
    }

    $workerObjects = New-Object System.Collections.ArrayList
    foreach ($job in @($jobs)) {
      try {
        $jobOutput = @(Receive-Job -Job $job -ErrorAction Stop)
        foreach ($resultPath in $jobOutput) {
          if (-not [string]::IsNullOrWhiteSpace([string]$resultPath) -and (Test-Path -LiteralPath $resultPath)) {
            [void]$Global:ParallelBaselineWorkerArtifacts.Add([string]$resultPath)
            $workerObject = Get-Content -LiteralPath $resultPath -Raw -ErrorAction Stop | ConvertFrom-Json
            [void]$workerObjects.Add($workerObject)
            foreach ($stepResult in @($workerObject.step_results)) {
              if ($stepResult.within_allowed_exit_codes -and -not ([bool]$stepResult.timed_out)) {
                $Global:ParallelBaselineCommandCache[[string]$stepResult.step_name] = [string]$stepResult.text
              } elseif ([bool]$stepResult.timed_out) {
                Add-CollectorError ('Parallel worker [{0}] timed out step [{1}] after {2} seconds; that step will fall back to serial execution when needed.' -f $workerObject.worker_name, $stepResult.step_name, $stepResult.timeout_seconds)
              } else {
                Add-CollectorNote ('Parallel worker [{0}] captured step [{1}] with exit code [{2}]; that step will fall back to serial execution when needed.' -f $workerObject.worker_name, $stepResult.step_name, $stepResult.exit_code)
              }
            }
          }
        }
      } catch {
        Add-CollectorError ('Parallel baseline worker job [{0}] failed: {1}' -f $job.Name, $_.Exception.Message)
      }
    }

    $workerResults = @($workerObjects | Sort-Object start_time_utc, worker_name)
    $overlaps = New-Object System.Collections.ArrayList
    for ($i = 0; $i -lt @($workerResults).Count; $i++) {
      for ($j = $i + 1; $j -lt @($workerResults).Count; $j++) {
        $left = $workerResults[$i]
        $right = $workerResults[$j]
        $leftStart = [datetime]::Parse([string]$left.start_time_utc)
        $leftEnd = [datetime]::Parse([string]$left.end_time_utc)
        $rightStart = [datetime]::Parse([string]$right.start_time_utc)
        $rightEnd = [datetime]::Parse([string]$right.end_time_utc)
        if (($leftStart -lt $rightEnd) -and ($rightStart -lt $leftEnd)) {
          [void]$overlaps.Add([ordered]@{
            left_worker = [string]$left.worker_name
            right_worker = [string]$right.worker_name
            left_start_utc = [string]$left.start_time_utc
            left_end_utc = [string]$left.end_time_utc
            right_start_utc = [string]$right.start_time_utc
            right_end_utc = [string]$right.end_time_utc
          })
        }
      }
    }

    $workerStepTimeoutCount = @($workerResults.step_results | Where-Object { [bool]$_.timed_out }).Count
    $proofStatus = if ($workerTimeoutCount -gt 0 -or $workerStepTimeoutCount -gt 0) {
      'DEGRADED_TIMEOUT'
    } elseif (@($workerResults).Count -ge 2 -and @($overlaps).Count -gt 0) {
      'OVERLAP_CONFIRMED'
    } else {
      'NO_OVERLAP_OBSERVED'
    }
    $proofObject = [ordered]@{
      proof_status = $proofStatus
      implementation_mode = 'bounded_parallel_jobs'
      deterministic_post_processing = 'Parent waits for parallel worker completion or the bounded worker timeout before baseline report assembly continues.'
      parent_wait_timeout_seconds = [int]$parallelWorkerTimeoutSeconds
      worker_timeout_count = [int]$workerTimeoutCount
      worker_step_timeout_count = [int]$workerStepTimeoutCount
      worker_count = @($workerResults).Count
      cached_step_count = @($Global:ParallelBaselineCommandCache.Keys).Count
      worker_artifact_paths = @($Global:ParallelBaselineWorkerArtifacts)
      worker_results = $workerResults
      overlapping_pairs = @($overlaps)
    }

    $proofPath = Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section 'PARALLEL_EXECUTION' -Name 'parallel_execution_proof.json.txt' -Text (Convert-ToSafeJsonText -InputObject $proofObject)
    $Global:ParallelExecutionProofPath = $proofPath
    $State.ParallelExecutionProofPath = $proofPath

    if ($proofStatus -eq 'OVERLAP_CONFIRMED') {
      Add-CollectorNote ('Bounded parallel baseline workers executed with observed overlap across {0} worker pair(s).' -f @($overlaps).Count)
    } elseif ($proofStatus -eq 'DEGRADED_TIMEOUT') {
      Add-CollectorError ('Bounded parallel baseline workers completed with timeout degradation. WorkerJobTimeouts={0}; WorkerStepTimeouts={1}; affected steps will use serial fallback when requested.' -f $workerTimeoutCount, $workerStepTimeoutCount)
    } else {
      Add-CollectorNote 'Bounded parallel baseline workers ran, but explicit timing overlap was not observed in this run.'
    }
  } catch {
    Add-CollectorError ('Failed to initialize bounded parallel baseline runtime: {0}' -f $_.Exception.Message)
  } finally {
    foreach ($job in @($jobs)) {
      try { Remove-Job -Job $job -Force -ErrorAction SilentlyContinue } catch { }
    }
  }
}

<#
.SYNOPSIS
Returns cached worker output when available or runs the command serially.

.DESCRIPTION
Looks for the requested step name in the bounded parallel baseline command cache and
returns that cached text when present. If no cached result exists, it falls back to the
standard serial command capture path.

.FUNCTION NAME
Get-CmdText

.INPUTS
Command string, StepName string, optional allowed exit-code list, and optional timeout
seconds.

.OUTPUTS
String containing cached worker text or combined serial command output.
#>
function Get-CmdText {
  param(
    [string]$Command,
    [string]$StepName,
    [int[]]$AllowedExitCodes = @(0),
    [int]$TimeoutSeconds = 0
  )

  if ($Global:ParallelBaselineCommandCache -and $StepName -and $Global:ParallelBaselineCommandCache.ContainsKey($StepName)) {
    return [string]$Global:ParallelBaselineCommandCache[$StepName]
  }

  return (Get-SerialCmdText -Command $Command -StepName $StepName -AllowedExitCodes $AllowedExitCodes -TimeoutSeconds $TimeoutSeconds)
}
