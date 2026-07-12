<#
.SYNOPSIS
DCOIR collector bounded parallel worker initialization helpers.

.DESCRIPTION
Defines the self-contained worker helper scriptblock used to initialize each bounded
parallel Start-Job worker context before the worker execution scriptblock runs.

.FILE NAME
DCOIR_Collector.04D2_Bounded_Parallel_Runtime.ps1

.INPUTS
No direct parameters. The returned initialization scriptblock resolves worker-scope
values such as DefaultStepTimeoutSeconds when invoked inside the worker job.

.OUTPUTS
Scriptblock that installs bounded parallel worker helper functions in the job context.
#>
function Get-ParallelBaselineWorkerInitializationScript {
  return {
    <#
    .SYNOPSIS
    Returns the timeout for one bounded-parallel worker step.

    .DESCRIPTION
    Uses the step-specific timeout when present, then the default timeout passed into
    the worker job, and finally the conservative collector timeout default.

    .FUNCTION NAME
    Get-WorkerStepTimeoutSeconds

    .INPUTS
    Worker step definition hashtable.

    .OUTPUTS
    Positive integer timeout in seconds.
    #>
    function Get-WorkerStepTimeoutSeconds {
      param([hashtable]$StepDefinition)

      $defaultTimeout = 600
      if ($DefaultStepTimeoutSeconds -gt 0) {
        $defaultTimeout = [int][Math]::Min($DefaultStepTimeoutSeconds, 86400)
      }
      try {
        if ($StepDefinition.Contains('TimeoutSeconds') -and [int]$StepDefinition.TimeoutSeconds -gt 0) {
          return [int][Math]::Min([int]$StepDefinition.TimeoutSeconds, 86400)
        }
      } catch { }
      return $defaultTimeout
    }

    <#
    .SYNOPSIS
    Stops one timed-out bounded-parallel worker process tree when possible.

    .DESCRIPTION
    Attempts a Windows taskkill process-tree stop first, then falls back to the .NET
    process kill method so child processes do not keep the worker job alive.

    .FUNCTION NAME
    Stop-WorkerProcessTree

    .INPUTS
    Process object to stop.

    .OUTPUTS
    No direct output. Stops the process as a side effect when possible.
    #>
    function Stop-WorkerProcessTree {
      param([System.Diagnostics.Process]$Process)

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
          } else {
            try { [void]$taskkillProcess.WaitForExit() } catch { }
          }

          [void](Get-WorkerProcessOutputTaskText -Task $taskkillStdoutTask -StreamName 'taskkill stdout' -WaitMilliseconds 1000)
          [void](Get-WorkerProcessOutputTaskText -Task $taskkillStderrTask -StreamName 'taskkill stderr' -WaitMilliseconds 1000)

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
        }
      } catch { }
    }

    <#
    .SYNOPSIS
    Reads one asynchronous worker-output task with a bounded wait.

    .DESCRIPTION
    Returns captured stdout or stderr text when the async read completes, or a visible
    warning string when the stream cannot be harvested after the worker process exits.

    .FUNCTION NAME
    Get-WorkerProcessOutputTaskText

    .INPUTS
    Async task, stream name, and bounded wait in milliseconds.

    .OUTPUTS
    Captured stream text or a warning string.
    #>
    function Get-WorkerProcessOutputTaskText {
      param(
        [System.Threading.Tasks.Task]$Task,
        [string]$StreamName,
        [int]$WaitMilliseconds = 10000
      )

      if ($null -eq $Task) { return '' }
      try {
        if (-not $Task.Wait($WaitMilliseconds)) {
          return ('[DCOIR_CAPTURE_WARNING] {0} capture did not complete within {1}ms after process exit.' -f $StreamName, $WaitMilliseconds)
        }
        return [string]$Task.Result
      } catch {
        return ('[DCOIR_CAPTURE_WARNING] {0} capture failed: {1}' -f $StreamName, $_.Exception.Message)
      }
    }

    <#
    .SYNOPSIS
    Captures one bounded-parallel worker step inside the background job.

    .DESCRIPTION
    Starts cmd.exe for the provided worker step definition, captures stdout and stderr
    concurrently, enforces a per-step timeout, evaluates the exit code against the
    allowed list, and returns the normalized step-result object that is later written
    into the worker proof artifact.

    .FUNCTION NAME
    Invoke-WorkerCommandCapture

    .INPUTS
    StepDefinition hashtable containing StepName, Command, and AllowedExitCodes.

    .OUTPUTS
    Ordered hashtable describing the captured step output, exit code, timeout state,
    allowed-exit-code evaluation, and combined text surface.
    #>
    function Invoke-WorkerCommandCapture {
      param([hashtable]$StepDefinition)

      $stepName = [string]$StepDefinition.StepName
      $command = [string]$StepDefinition.Command
      $allowed = @($StepDefinition.AllowedExitCodes)
      if (@($allowed).Count -eq 0) { $allowed = @(0) }
      $timeoutSeconds = Get-WorkerStepTimeoutSeconds -StepDefinition $StepDefinition
      $timeoutMilliseconds = [int][Math]::Min(([double]$timeoutSeconds * 1000), [double][int]::MaxValue)
      $started = Get-Date
      $proc = $null
      $timedOut = $false

      try {
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = 'cmd.exe'
        $psi.Arguments = ('/c ' + $command)
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
          Stop-WorkerProcessTree -Process $proc
          try { [void]$proc.WaitForExit(5000) } catch { }
        } else {
          [void]$proc.WaitForExit()
        }

        $stdout = Get-WorkerProcessOutputTaskText -Task $stdoutTask -StreamName 'stdout'
        $stderr = Get-WorkerProcessOutputTaskText -Task $stderrTask -StreamName 'stderr'
        $ended = Get-Date
        $exitCode = -1
        if (-not $timedOut) {
          $exitCode = [int]$proc.ExitCode
        }
        $withinAllowed = ((-not $timedOut) -and (@($allowed) -contains $exitCode))
        $status = if ($timedOut) { 'TIMEOUT' } elseif ($withinAllowed) { 'OK' } else { 'ERROR' }

        $lines = New-Object System.Collections.ArrayList
        [void]$lines.Add(('COMMAND={0}' -f $command))
        [void]$lines.Add(('EXIT_CODE={0}' -f $exitCode))
        [void]$lines.Add(('STATUS={0}' -f $status))
        [void]$lines.Add(('TIMED_OUT={0}' -f [bool]$timedOut))
        [void]$lines.Add(('TIMEOUT_SECONDS={0}' -f [int]$timeoutSeconds))
        [void]$lines.Add('')
        [void]$lines.Add('STDOUT:')
        [void]$lines.Add($stdout)
        [void]$lines.Add('')
        [void]$lines.Add('STDERR:')
        [void]$lines.Add($stderr)

        return [ordered]@{
          step_name = $stepName
          command = $command
          exit_code = $exitCode
          status = $status
          timed_out = [bool]$timedOut
          timeout_seconds = [int]$timeoutSeconds
          duration_ms = [int][Math]::Round(($ended - $started).TotalMilliseconds)
          allowed_exit_codes = @($allowed)
          within_allowed_exit_codes = [bool]$withinAllowed
          text = ($lines -join [Environment]::NewLine)
        }
      } catch {
        $ended = Get-Date
        $message = $_.Exception.Message
        $status = if ($timedOut) { 'TIMEOUT' } else { 'EXCEPTION' }

        $lines = New-Object System.Collections.ArrayList
        [void]$lines.Add(('COMMAND={0}' -f $command))
        [void]$lines.Add('EXIT_CODE=-1')
        [void]$lines.Add(('STATUS={0}' -f $status))
        [void]$lines.Add(('TIMED_OUT={0}' -f [bool]$timedOut))
        [void]$lines.Add(('TIMEOUT_SECONDS={0}' -f [int]$timeoutSeconds))
        [void]$lines.Add('')
        [void]$lines.Add('STDOUT:')
        [void]$lines.Add('')
        [void]$lines.Add('')
        [void]$lines.Add('STDERR:')
        [void]$lines.Add($message)

        return [ordered]@{
          step_name = $stepName
          command = $command
          exit_code = -1
          status = $status
          timed_out = [bool]$timedOut
          timeout_seconds = [int]$timeoutSeconds
          duration_ms = [int][Math]::Round(($ended - $started).TotalMilliseconds)
          allowed_exit_codes = @($allowed)
          within_allowed_exit_codes = $false
          text = ($lines -join [Environment]::NewLine)
        }
      } finally {
        if ($null -ne $proc) {
          try { $proc.Dispose() } catch { }
        }
      }
    }

    <#
    .SYNOPSIS
    Detects exact ellipsis-string values in a worker JSON object.

    .DESCRIPTION
    Runs inside the isolated Start-Job worker scriptblock where parent helper functions
    are not loaded. Worker result objects are collector-controlled, so an exact "..."
    string in emitted JSON is treated as a ConvertTo-Json depth truncation sentinel. The
    recursive scan is bounded so unexpected object graphs fail visibly instead of relying
    on engine recursion behavior.

    .FUNCTION NAME
    Test-WorkerJsonContainsEllipsisSentinel

    .INPUTS
    InputObject, optional max traversal depth, current recursion depth, and current path.

    .OUTPUTS
    Boolean.
    #>
    function Test-WorkerJsonContainsEllipsisSentinel {
      param(
        [object]$InputObject,
        [int]$MaxDepth = 25,
        [int]$CurrentDepth = 0,
        [string]$Path = '$'
      )

      if ($null -eq $InputObject) { return $false }
      if ([string]::IsNullOrWhiteSpace($Path)) { $Path = '$' }
      if ($InputObject -is [string]) { return ([string]$InputObject -eq '...') }
      if ($CurrentDepth -ge $MaxDepth) {
        throw ('Parallel worker result JSON sentinel scan exceeded configured depth {0} at path {1}.' -f $MaxDepth, $Path)
      }
      if (($InputObject -is [System.Collections.IEnumerable]) -and -not ($InputObject -is [string])) {
        $index = 0
        foreach ($item in @($InputObject)) {
          $childPath = ('{0}[{1}]' -f $Path, $index)
          if (Test-WorkerJsonContainsEllipsisSentinel -InputObject $item -MaxDepth $MaxDepth -CurrentDepth ($CurrentDepth + 1) -Path $childPath) { return $true }
          $index += 1
        }
        return $false
      }
      foreach ($prop in @($InputObject.PSObject.Properties)) {
        $childPath = ('{0}.{1}' -f $Path, [string]$prop.Name)
        if (Test-WorkerJsonContainsEllipsisSentinel -InputObject $prop.Value -MaxDepth $MaxDepth -CurrentDepth ($CurrentDepth + 1) -Path $childPath) { return $true }
      }
      return $false
    }
  }
}
