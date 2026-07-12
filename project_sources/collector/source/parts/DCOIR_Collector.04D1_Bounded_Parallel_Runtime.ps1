<#
.SYNOPSIS
DCOIR collector bounded parallel runtime helpers.

.DESCRIPTION
Implements the bounded Windows PowerShell 5.1-safe parallel baseline runtime, including
worker definitions, cache initialization, overlap proof generation, and serial fallback
behavior for steps that are not safely satisfied by worker output.

.FILE NAME
DCOIR_Collector.04D1_Bounded_Parallel_Runtime.ps1

.INPUTS
Collector state hashtable, baseline worker definitions, command strings, step names,
and allowed exit-code lists.

.OUTPUTS
Worker proof artifacts, cached command output text, collector notes/errors, and serial
or cached command text returned to the caller.
#>

$Global:ParallelBaselineCommandCache = @{}
$Global:ParallelBaselineWorkerArtifacts = New-Object System.Collections.ArrayList
$Global:ParallelExecutionProofPath = $null

<#
.SYNOPSIS
Resets all bounded parallel runtime caches and proof paths.

.DESCRIPTION
Clears the worker command cache, worker artifact list, and proof path so a collect run
starts with a clean bounded-parallel-runtime state.

.FUNCTION NAME
Reset-ParallelBaselineCache

.INPUTS
No direct parameters.

.OUTPUTS
No direct output. Resets global parallel-runtime state.
#>
function Reset-ParallelBaselineCache {
  $Global:ParallelBaselineCommandCache = @{}
  $Global:ParallelBaselineWorkerArtifacts = New-Object System.Collections.ArrayList
  $Global:ParallelExecutionProofPath = $null
}

<#
.SYNOPSIS
Runs one command serially and returns its combined text output.

.DESCRIPTION
Calls the standard cmd capture helper for a single step and returns the combined stdout,
stderr, command, and exit-code text surface.

.FUNCTION NAME
Get-SerialCmdText

.INPUTS
Command string, StepName string, optional allowed exit-code list, and optional timeout
seconds.

.OUTPUTS
String containing the combined captured process output.
#>
function Get-SerialCmdText {
  param(
    [string]$Command,
    [string]$StepName,
    [int[]]$AllowedExitCodes = @(0),
    [int]$TimeoutSeconds = 0
  )
  $result = Invoke-CmdCapture -Command $Command -StepName $StepName -AllowedExitCodes $AllowedExitCodes -TimeoutSeconds $TimeoutSeconds
  return (Get-CombinedProcessOutput -Result $result)
}

<#
.SYNOPSIS
Returns the bounded parallel baseline worker definitions.

.DESCRIPTION
Defines the small, read-only worker groups that can run in parallel during collect mode,
including their step names, command strings, and allowed exit codes.

.FUNCTION NAME
Get-ParallelBaselineWorkerDefinitions

.INPUTS
No direct parameters.

.OUTPUTS
Array of ordered worker-definition hashtables.
#>
function Get-ParallelBaselineWorkerDefinitions {
  # Start-Job runs each worker in a separate PowerShell job context. Keep worker
  # scriptblocks self-contained, or explicitly pass/import every dependency they
  # need; worker code must not assume collector part-file helper functions are
  # loaded in the job process.
  return @(
    [ordered]@{
      Name = 'host_baseline'
      Steps = @(
        [ordered]@{ StepName = 'HOST_DATE_TIME_HOSTNAME'; Command = 'date /t & time /t & hostname & ver'; AllowedExitCodes = @(0) },
        [ordered]@{ StepName = 'HOST_SYSTEMINFO'; Command = 'systeminfo'; AllowedExitCodes = @(0) }
      )
    },
    [ordered]@{
      Name = 'identity_context'
      Steps = @(
        [ordered]@{ StepName = 'IDENTITY_WHOAMI_ALL'; Command = 'whoami /all'; AllowedExitCodes = @(0) },
        [ordered]@{ StepName = 'IDENTITY_QUERY_USER_QWINSTA'; Command = 'query user & qwinsta'; AllowedExitCodes = @(0,1) }
      )
    },
    [ordered]@{
      Name = 'network_light'
      Steps = @(
        [ordered]@{ StepName = 'NETWORK_IPCONFIG'; Command = 'ipconfig /all'; AllowedExitCodes = @(0) },
        [ordered]@{ StepName = 'NETWORK_DNS_CACHE'; Command = 'ipconfig /displaydns'; AllowedExitCodes = @(0) },
        [ordered]@{ StepName = 'NETWORK_ROUTE_PRINT'; Command = 'route print'; AllowedExitCodes = @(0) },
        [ordered]@{ StepName = 'NETWORK_ARP_A'; Command = 'arp -a'; AllowedExitCodes = @(0) }
      )
    },
    [ordered]@{
      Name = 'security_posture'
      Steps = @(
        [ordered]@{ StepName = 'SECURITY_FIREWALL_PROFILES'; Command = 'netsh advfirewall show allprofiles'; AllowedExitCodes = @(0) }
      )
    }
  )
}

<#
.SYNOPSIS
Calculates a bounded wait for the parallel worker job group.

.DESCRIPTION
Uses each worker step's optional timeout, or the default process-capture timeout, to
calculate the longest expected worker duration and adds a small grace period. This keeps
the parent collector bounded even when a worker job itself fails to return.

.FUNCTION NAME
Get-ParallelBaselineWorkerTimeoutSeconds

.INPUTS
Worker definitions and default per-step timeout seconds.

.OUTPUTS
Positive integer timeout in seconds for the parent Wait-Job call.
#>
function Get-ParallelBaselineWorkerTimeoutSeconds {
  param(
    [object[]]$WorkerDefinitions,
    [int]$DefaultStepTimeoutSeconds
  )

  $defaultTimeout = Get-CollectorProcessCaptureTimeoutSeconds -TimeoutSeconds $DefaultStepTimeoutSeconds
  $longestWorkerSeconds = 0
  foreach ($workerDefinition in @($WorkerDefinitions)) {
    $workerSeconds = 0
    foreach ($stepDefinition in @($workerDefinition.Steps)) {
      $stepTimeout = $defaultTimeout
      try {
        if ($stepDefinition.Contains('TimeoutSeconds') -and [int]$stepDefinition.TimeoutSeconds -gt 0) {
          $stepTimeout = [int]$stepDefinition.TimeoutSeconds
        }
      } catch { }
      $workerSeconds += $stepTimeout
    }
    if ($workerSeconds -gt $longestWorkerSeconds) {
      $longestWorkerSeconds = $workerSeconds
    }
  }

  if ($longestWorkerSeconds -lt $defaultTimeout) {
    $longestWorkerSeconds = $defaultTimeout
  }
  return [int][Math]::Min(($longestWorkerSeconds + 30), 86400)
}
