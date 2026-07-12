<#
.SYNOPSIS
DCOIR collector process-capture helpers.

.DESCRIPTION
Provides timeout selection, process-tree stop, asynchronous output harvesting, and
external command capture helpers used across collector runtime paths.

.FILE NAME
DCOIR_Collector.01A2_Core_Logging_And_Process_Capture.ps1

.INPUTS
Collector runtime globals, command details, process objects, and timeout settings.

.OUTPUTS
Command-capture objects, captured process text, execution logs, and collector error state.
#>
<#
.SYNOPSIS
Returns the timeout used for external process capture.

.DESCRIPTION
Uses an explicit per-call timeout when provided, then an optional in-memory collector
override, and finally the conservative default. This is intentionally not an
environment variable so collector runtime behavior does not depend on undeclared host
configuration.

.FUNCTION NAME
Get-CollectorProcessCaptureTimeoutSeconds

.INPUTS
Optional timeout value in seconds.

.OUTPUTS
Positive integer timeout in seconds.
#>
function Get-CollectorProcessCaptureTimeoutSeconds {
  param([int]$TimeoutSeconds = 0)

  $defaultTimeoutSeconds = 600
  try {
    if ($TimeoutSeconds -gt 0) {
      return [int][Math]::Min($TimeoutSeconds, 86400)
    }

    $override = Get-Variable -Name CollectorProcessCaptureTimeoutSeconds -Scope Global -ErrorAction SilentlyContinue
    if ($override -and $null -ne $override.Value) {
      $overrideValue = [int]$override.Value
      if ($overrideValue -gt 0) {
        return [int][Math]::Min($overrideValue, 86400)
      }
    }
  } catch { }

  return $defaultTimeoutSeconds
}

<#
.SYNOPSIS
Stops one timed-out process and its child process tree when possible.

.DESCRIPTION
Attempts a Windows taskkill process-tree stop first, then falls back to the .NET process
kill method. Failure to stop is recorded as a collector error rather than hidden.

.FUNCTION NAME
Stop-CollectorProcessTree

.INPUTS
Process object and display command text.

.OUTPUTS
No direct output. Stops the process as a side effect when possible.
#>
function Stop-CollectorProcessTree {
  param(
    [System.Diagnostics.Process]$Process,
    [string]$CommandText
  )

  if ($null -eq $Process) { return }
  try {
    if ($Process.HasExited) { return }
  } catch { }

  $stopped = $false
  $taskkillStopMilliseconds = 10000
  try {
    $taskkillPath = 'taskkill.exe'
    if (-not [string]::IsNullOrWhiteSpace($env:SystemRoot)) {
      $candidate = Join-Path $env:SystemRoot 'System32\taskkill.exe'
      if (Test-Path -LiteralPath $candidate) {
        $taskkillPath = $candidate
      }
    }

    $taskkillProcess = $null
    try {
      $taskkillStartInfo = New-Object System.Diagnostics.ProcessStartInfo
      $taskkillStartInfo.FileName = $taskkillPath
      $taskkillStartInfo.Arguments = ('/PID {0} /T /F' -f [int]$Process.Id)
      $taskkillStartInfo.UseShellExecute = $false
      $taskkillStartInfo.RedirectStandardOutput = $true
      $taskkillStartInfo.RedirectStandardError = $true
      $taskkillStartInfo.CreateNoWindow = $true

      $taskkillProcess = New-Object System.Diagnostics.Process
      $taskkillProcess.StartInfo = $taskkillStartInfo
      [void]$taskkillProcess.Start()

      $taskkillStdoutTask = $taskkillProcess.StandardOutput.ReadToEndAsync()
      $taskkillStderrTask = $taskkillProcess.StandardError.ReadToEndAsync()
      $taskkillCompleted = $taskkillProcess.WaitForExit($taskkillStopMilliseconds)
      if (-not $taskkillCompleted) {
        try {
          $taskkillProcess.Kill()
          [void]$taskkillProcess.WaitForExit(1000)
        } catch { }
        Add-CollectorError ("taskkill timed out while stopping process [{0}] for command [{1}]; falling back to direct process kill." -f $Process.Id, $CommandText)
      } else {
        try { [void]$taskkillProcess.WaitForExit() } catch { }
      }

      [void](Get-CollectorProcessOutputTaskText -Task $taskkillStdoutTask -StreamName 'taskkill stdout' -WaitMilliseconds 1000)
      [void](Get-CollectorProcessOutputTaskText -Task $taskkillStderrTask -StreamName 'taskkill stderr' -WaitMilliseconds 1000)

      if ($taskkillCompleted -and $taskkillProcess.ExitCode -eq 0) {
        $stopped = $true
      }
      if (-not $stopped) {
        try {
          if ($Process.HasExited) { $stopped = $true }
        } catch { }
      }
    } finally {
      if ($null -ne $taskkillProcess) {
        try { $taskkillProcess.Dispose() } catch { }
      }
    }
  } catch { }

  try {
    if (-not $Process.HasExited -and -not $stopped) {
      $Process.Kill()
      $stopped = $true
    }
  } catch {
    Add-CollectorError ("Failed to stop timed-out process [{0}] for command [{1}]: {2}" -f $Process.Id, $CommandText, $_.Exception.Message)
  }
}

<#
.SYNOPSIS
Reads one asynchronous process-output task with a bounded wait.

.DESCRIPTION
Returns captured stream text when the async read task completes, or a visible warning
string when the stream cannot be harvested after the process has exited or been stopped.

.FUNCTION NAME
Get-CollectorProcessOutputTaskText

.INPUTS
Async task, stream name, and bounded wait in milliseconds.

.OUTPUTS
Captured stream text or a warning string.
#>
function Get-CollectorProcessOutputTaskText {
  param(
    [System.Threading.Tasks.Task]$Task,
    [string]$StreamName,
    [int]$WaitMilliseconds = 10000
  )

  if ($null -eq $Task) { return "" }
  try {
    if (-not $Task.Wait($WaitMilliseconds)) {
      return ("[DCOIR_CAPTURE_WARNING] {0} capture did not complete within {1}ms after process exit." -f $StreamName, $WaitMilliseconds)
    }
    return [string]$Task.Result
  } catch {
    return ("[DCOIR_CAPTURE_WARNING] {0} capture failed: {1}" -f $StreamName, $_.Exception.Message)
  }
}

<#
.SYNOPSIS
Runs one external process and captures its output.

.DESCRIPTION
Builds the process start info, captures stdout and stderr, validates the exit code
against the allowed list, writes the execution-step log entry, and returns one capture
object describing the result.

.FUNCTION NAME
Invoke-ProcessCapture

.INPUTS
Mandatory FilePath and StepName, optional argument array, optional allowed exit-code
list, and optional timeout seconds.

.OUTPUTS
PSCustomObject containing StdOut, StdErr, ExitCode, Command, Status, TimedOut, and
TimeoutSeconds.
#>
function Invoke-ProcessCapture {
  param(
    [Parameter(Mandatory=$true)][string]$FilePath,
    [string[]]$Arguments,
    [Parameter(Mandatory=$true)][string]$StepName,
    [int[]]$AllowedExitCodes = @(0),
    [int]$TimeoutSeconds = 0
  )

  $startTime = Get-Date
  $commandText = $FilePath
  if ($Arguments) {
    $commandText = "$FilePath $(Join-ArgString -Arguments $Arguments)"
  }

  $effectiveTimeoutSeconds = Get-CollectorProcessCaptureTimeoutSeconds -TimeoutSeconds $TimeoutSeconds
  $timeoutMilliseconds = [int][Math]::Min(([double]$effectiveTimeoutSeconds * 1000), [double][int]::MaxValue)
  $proc = $null
  $timedOut = $false

  try {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $FilePath
    $psi.Arguments = (Join-ArgString -Arguments $Arguments)
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true

    $proc = New-Object System.Diagnostics.Process
    $proc.StartInfo = $psi
    [void]$proc.Start()
    $stdoutTask = $proc.StandardOutput.ReadToEndAsync()
    $stderrTask = $proc.StandardError.ReadToEndAsync()

    $timedOut = -not $proc.WaitForExit($timeoutMilliseconds)
    if ($timedOut) {
      Stop-CollectorProcessTree -Process $proc -CommandText $commandText
      try { [void]$proc.WaitForExit(5000) } catch { }
    } else {
      [void]$proc.WaitForExit()
    }

    $stdout = Get-CollectorProcessOutputTaskText -Task $stdoutTask -StreamName 'stdout'
    $stderr = Get-CollectorProcessOutputTaskText -Task $stderrTask -StreamName 'stderr'

    $endTime = Get-Date
    $status = "OK"
    $message = ""
    $exitCode = -1
    if (-not $timedOut) {
      $exitCode = [int]$proc.ExitCode
    }

    if ($timedOut) {
      $status = "TIMEOUT"
      $message = ("TimedOut=True TimeoutSeconds={0}" -f $effectiveTimeoutSeconds)
      Add-CollectorError ("Step [{0}] timed out after {1} seconds. Command: {2}" -f $StepName, $effectiveTimeoutSeconds, $commandText)
    } elseif (@($AllowedExitCodes) -notcontains $exitCode) {
      $status = "ERROR"
      $message = ("ExitCode={0}" -f $exitCode)
      Add-CollectorError ("Step [{0}] failed. {1}. Command: {2}" -f $StepName, $message, $commandText)
    }

    Write-StepLog -StepName $StepName -Status $status -StartTime $startTime -EndTime $endTime -ExitCode $exitCode -Command $commandText -ArtifactPath "" -Message $message

    return [pscustomobject]@{
      StdOut = $stdout
      StdErr = $stderr
      ExitCode = $exitCode
      Command = $commandText
      Status = $status
      TimedOut = [bool]$timedOut
      TimeoutSeconds = [int]$effectiveTimeoutSeconds
    }
  } catch {
    $endTime = Get-Date
    $message = $_.Exception.Message
    Add-CollectorError ("Step [{0}] raised an exception. {1}. Command: {2}" -f $StepName, $message, $commandText)
    $status = if ($timedOut) { "TIMEOUT" } else { "EXCEPTION" }
    Write-StepLog -StepName $StepName -Status $status -StartTime $startTime -EndTime $endTime -ExitCode -1 -Command $commandText -ArtifactPath "" -Message $message
    return [pscustomobject]@{
      StdOut = ""
      StdErr = $message
      ExitCode = -1
      Command = $commandText
      Status = $status
      TimedOut = [bool]$timedOut
      TimeoutSeconds = [int]$effectiveTimeoutSeconds
    }
  } finally {
    if ($null -ne $proc) {
      try { $proc.Dispose() } catch { }
    }
  }
}

<#
.SYNOPSIS
Runs one cmd.exe command and captures its output.

.DESCRIPTION
Wraps Invoke-ProcessCapture for cmd.exe /c execution of the supplied command string.

.FUNCTION NAME
Invoke-CmdCapture

.INPUTS
Mandatory Command and StepName, optional allowed exit-code list, and optional timeout
seconds.

.OUTPUTS
PSCustomObject containing the captured cmd.exe result.
#>
function Invoke-CmdCapture {
  param(
    [Parameter(Mandatory=$true)][string]$Command,
    [Parameter(Mandatory=$true)][string]$StepName,
    [int[]]$AllowedExitCodes = @(0),
    [int]$TimeoutSeconds = 0
  )
  return (Invoke-ProcessCapture -FilePath "cmd.exe" -Arguments @("/c", $Command) -StepName $StepName -AllowedExitCodes $AllowedExitCodes -TimeoutSeconds $TimeoutSeconds)
}
