<#
.SYNOPSIS
DCOIR collector core logging, runtime-path, and step-log helpers.

.DESCRIPTION
Provides the core logging, filesystem, runtime-path, command-capture, and process-capture
helpers used across collect, enrich, cleanup, validation, and bundle-generation paths.

.FILE NAME
DCOIR_Collector.01A1_Core_Logging_And_Process_Capture.ps1

.INPUTS
Collector runtime globals, filesystem paths, command details, process details, and
runtime-location candidates.

.OUTPUTS
Collector notes/errors/recommendations, command-capture objects and text, runtime paths,
and supporting helper return values.
#>

<#
.SYNOPSIS
Adds one collector error to the in-memory error list and optional error log.

.DESCRIPTION
Validates the supplied message, appends it to the global collector error list, and
writes a timestamped entry to the durable errors log when that log path is configured.

.FUNCTION NAME
Add-CollectorError

.INPUTS
Message string.

.OUTPUTS
No direct output. Updates global error state and optional log file.
#>
function Add-CollectorError {
  [CmdletBinding()]
  param([string]$Message)
  if ([string]::IsNullOrWhiteSpace($Message)) { return }
  [void]$Global:CollectorErrors.Add($Message)
  if ($Global:ErrorsLogPath) {
    try {
      Add-Content -Path $Global:ErrorsLogPath -Value ("[{0}] ERROR {1}" -f ((Get-Date).ToUniversalTime().ToString("o")), $Message) -Encoding UTF8 -ErrorAction Stop
    } catch {
      [void]$Global:CollectorNotes.Add(("Failed to append collector error log: {0}" -f $_.Exception.Message))
    }
  }
}

<#
.SYNOPSIS
Adds one collector note to the in-memory notes list.

.DESCRIPTION
Ignores blank input and appends a note to the global collector notes collection.

.FUNCTION NAME
Add-CollectorNote

.INPUTS
Message string.

.OUTPUTS
No direct output. Updates global note state.
#>
function Add-CollectorNote {
  param([string]$Message)
  if ([string]::IsNullOrWhiteSpace($Message)) { return }
  [void]$Global:CollectorNotes.Add($Message)
}

<#
.SYNOPSIS
Adds one analyst recommendation to the in-memory recommendation list.

.DESCRIPTION
Ignores blank input and appends the supplied recommendation to the global follow-up
queue used by metadata and analyst review artifacts.

.FUNCTION NAME
Add-Recommendation

.INPUTS
Message string.

.OUTPUTS
No direct output. Updates global recommendation state.
#>
function Add-Recommendation {
  param([string]$Message)
  if ([string]::IsNullOrWhiteSpace($Message)) { return }
  [void]$Global:RecommendedActions.Add($Message)
}

<#
.SYNOPSIS
Ensures that one directory exists.

.DESCRIPTION
Creates the requested directory path when it does not already exist.

.FUNCTION NAME
Ensure-Directory

.INPUTS
Mandatory Path string.

.OUTPUTS
No direct output. Creates the directory as a side effect when needed.
#>
function Ensure-Directory {
  param([Parameter(Mandatory=$true)][string]$Path)
  if (-not (Test-Path -LiteralPath $Path)) {
    New-Item -Path $Path -ItemType Directory -Force -ErrorAction Stop | Out-Null
  }
}

<#
.SYNOPSIS
Deletes one path when it exists.

.DESCRIPTION
Silently removes the supplied file or directory path when it is nonblank and present.

.FUNCTION NAME
Remove-IfExists

.INPUTS
LiteralPath string.

.OUTPUTS
No direct output. Removes the target as a side effect when present.
#>
function Remove-IfExists {
  [CmdletBinding(SupportsShouldProcess=$true)]
  param([string]$LiteralPath)
  if (-not [string]::IsNullOrWhiteSpace($LiteralPath) -and (Test-Path -LiteralPath $LiteralPath)) {
    if ($PSCmdlet.ShouldProcess($LiteralPath, 'Remove item recursively')) {
      Remove-Item -LiteralPath $LiteralPath -Recurse -Force -ErrorAction SilentlyContinue
    }
  }
}

<#
.SYNOPSIS
Joins argument tokens into one safe process-argument string.

.DESCRIPTION
Skips null values and quotes arguments that contain whitespace or quotes so downstream
process-start calls receive a stable command-line string.

.FUNCTION NAME
Join-ArgString

.INPUTS
String array of arguments.

.OUTPUTS
String containing the joined argument list.
#>
function Join-ArgString {
  param([string[]]$Arguments)
  if (-not $Arguments) { return "" }
  $parts = foreach ($arg in $Arguments) {
    if ($null -eq $arg) { continue }
    if ($arg -match '[\s"]') {
      '"' + ($arg -replace '"', '\"') + '"'
    } else {
      $arg
    }
  }
  return ($parts -join ' ')
}

<#
.SYNOPSIS
Checks whether one collector runtime path candidate is usable.

.DESCRIPTION
Rejects blank paths and PowerShell host executable paths so the primary PS1 lane keeps
using the collector script path, while the optional EXE lane can still use a real EXE
runtime path when appropriate.

.FUNCTION NAME
Test-CollectorRuntimePathCandidate

.INPUTS
Path string.

.OUTPUTS
Boolean indicating whether the candidate is a usable collector runtime path.
#>
function Test-CollectorRuntimePathCandidate {
  param([string]$Path)

  if ([string]::IsNullOrWhiteSpace($Path)) { return $false }

  try {
    $leaf = [System.IO.Path]::GetFileName($Path)
    if ($leaf -in @("powershell.exe", "pwsh.exe", "powershell", "pwsh")) { return $false }
    return $true
  } catch {
    return $false
  }
}

<#
.SYNOPSIS
Returns the absolute path to the active collector runtime.

.DESCRIPTION
Resolves the collector path by preferring the script path for PowerShell execution,
checking safe MyInvocation metadata without strict-mode property failures, and falling
back to the optional EXE process path only when the process itself is the collector
runtime rather than powershell.exe or pwsh.exe.

.FUNCTION NAME
Get-CollectorAbsolutePath

.INPUTS
No direct parameters.

.OUTPUTS
String absolute path to the active collector script or optional EXE runtime.
#>
function Get-CollectorAbsolutePath {
  foreach ($candidate in @($ScriptFilePath, $PSCommandPath, $MyInvocation.PSCommandPath)) {
    if (Test-CollectorRuntimePathCandidate -Path $candidate) {
      return [System.IO.Path]::GetFullPath([string]$candidate)
    }
  }

  try {
    $cmd = $MyInvocation.MyCommand
    if ($null -ne $cmd) {
      $pathProperty = $cmd.PSObject.Properties['Path']
      if ($pathProperty -and (Test-CollectorRuntimePathCandidate -Path ([string]$pathProperty.Value))) {
        return [System.IO.Path]::GetFullPath([string]$pathProperty.Value)
      }
      $sourceProperty = $cmd.PSObject.Properties['Source']
      if ($sourceProperty -and (Test-CollectorRuntimePathCandidate -Path ([string]$sourceProperty.Value))) {
        return [System.IO.Path]::GetFullPath([string]$sourceProperty.Value)
      }
    }
  } catch { }

  try {
    $processPath = [System.Diagnostics.Process]::GetCurrentProcess().MainModule.FileName
    if (Test-CollectorRuntimePathCandidate -Path $processPath) {
      return [System.IO.Path]::GetFullPath($processPath)
    }
  } catch { }

  return [System.IO.Path]::GetFullPath((Join-Path (Get-Location).Path "DCOIR_Collector.ps1"))
}

<#
.SYNOPSIS
Builds the reusable PowerShell command base for the collector.

.DESCRIPTION
Returns the standard powershell.exe invocation string used in workflow guidance and
operator-facing next-step output.

.FUNCTION NAME
Get-CollectorPowerShellCommandBase

.INPUTS
No direct parameters.

.OUTPUTS
String command base for running the collector script.
#>
function Get-CollectorPowerShellCommandBase {
  $collectorPath = Get-CollectorAbsolutePath
  return ("powershell.exe -NoProfile -ExecutionPolicy Bypass -File '{0}'" -f $collectorPath)
}

<#
.SYNOPSIS
Writes one execution-step log record.

.DESCRIPTION
Builds the text and JSONL execution-log entries for a step, including timing, exit code,
command text, artifact path, and message, then appends them to the configured execution
logs when those paths are present.

.FUNCTION NAME
Write-StepLog

.INPUTS
StepName, Status, StartTime, EndTime, ExitCode, Command, ArtifactPath, and Message.

.OUTPUTS
No direct output. Appends to execution text and JSONL logs as a side effect.
#>
function Write-StepLog {
  [CmdletBinding()]
  param(
    [string]$StepName,
    [string]$Status,
    [datetime]$StartTime,
    [datetime]$EndTime,
    [int]$ExitCode,
    [string]$Command,
    [string]$ArtifactPath,
    [string]$Message
  )

  $durationMs = [int]([TimeSpan]($EndTime - $StartTime)).TotalMilliseconds
  $txtLine = "[{0}] {1} {2} duration_ms={3} exit_code={4}" -f $EndTime.ToUniversalTime().ToString("o"), $Status, $StepName, $durationMs, $ExitCode
  if ($ArtifactPath) { $txtLine += (" artifact={0}" -f $ArtifactPath) }
  if ($Message) { $txtLine += (" message={0}" -f $Message) }

  if ($Global:ExecutionTxtPath) {
    Add-Content -Path $Global:ExecutionTxtPath -Value $txtLine -Encoding UTF8 -ErrorAction Stop
    if ($Command) {
      Add-Content -Path $Global:ExecutionTxtPath -Value ("  COMMAND={0}" -f $Command) -Encoding UTF8 -ErrorAction Stop
    }
  }

  if ($Global:ExecutionJsonlPath) {
    $obj = [ordered]@{
      ts_utc = $EndTime.ToUniversalTime().ToString("o")
      run_id = $Global:CurrentRunId
      step = $StepName
      status = $Status
      duration_ms = $durationMs
      exit_code = $ExitCode
      command = $Command
      artifact_path = $ArtifactPath
      message = $Message
    }
    Add-Content -Path $Global:ExecutionJsonlPath -Value (Convert-ToCollectorJsonText -InputObject $obj -Compress -Label 'execution step JSONL') -Encoding UTF8 -ErrorAction Stop
  }
}
