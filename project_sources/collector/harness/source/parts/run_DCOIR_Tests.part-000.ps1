<#
.SYNOPSIS
DCOIR collector harness and regression runner.

.DESCRIPTION
Executes the collector through bounded validation suites, captures per-step logs and
summaries, verifies output contracts and failure gates, and writes machine-readable and
human-readable summary artifacts for regression review.

.FILE NAME
run_DCOIR_Tests.generated.ps1

.INPUTS
Suite selection, collector path, output root, master ZIP path, live-response mode flag,
attachment-budget thresholds, and cleanup/continue-on-error switches.

.OUTPUTS
Per-step harness logs, suite summary text and JSON, and the collector executions that
those validation suites drive.
#>

param(
  [ValidateSet("Core","Retrieval","QuickAliases","SessionBehavior","TargetedCollection","ChunkingOversizeArtifact","ChunkingReconstructionMetadata","Tier2BoundedCollect","MajorVersion","FullRegression","FailureGates")]
  [string]$Suite = "Core",

  [string]$CollectorPath = ".\DCOIR_Collector.ps1",

  [string]$OutputRoot = ".\TestResults",

  [string]$MasterZipPath = ".\assets\DCOIR_Collector.zip",

  [switch]$LiveResponseMode,

  [int]$SafePerFileKB = 900,

  [int]$HardPerFileKB = 1000,

  [int]$SafePerPromptKB = 1800,

  [int]$HardPerPromptKB = 2000,

  [switch]$ContinueOnError,

  [switch]$SkipCleanup,

  [ValidateSet("Auto","PowerShellFile","Executable")]
  [string]$CollectorInvocationMode = "Auto",

  [ValidateRange(1,3600)]
  [int]$CollectorStepTimeoutSeconds = 600
)

Set-StrictMode -Version 2
$ErrorActionPreference = "Stop"

if ($LiveResponseMode) {
  if ($CollectorPath -eq ".\DCOIR_Collector.ps1") { $CollectorPath = "C:\Temp\DCOIR_Collector.ps1" }
  if ($OutputRoot -eq ".\TestResults") { $OutputRoot = "C:\Temp\DCOIR_TestResults" }
  if ($MasterZipPath -eq ".\assets\DCOIR_Collector.zip") { $MasterZipPath = "C:\Temp\assets\DCOIR_Collector.zip" }
}

$ProjectRoot = Split-Path -Parent (Resolve-Path -LiteralPath $CollectorPath)
$CollectorFullPath = (Resolve-Path -LiteralPath $CollectorPath).Path
$script:ResolvedCollectorInvocationMode = $CollectorInvocationMode
if ($script:ResolvedCollectorInvocationMode -eq "Auto") {
  $collectorExtension = [System.IO.Path]::GetExtension($CollectorFullPath)
  if ($collectorExtension -ieq ".exe") {
    $script:ResolvedCollectorInvocationMode = "Executable"
  } else {
    $script:ResolvedCollectorInvocationMode = "PowerShellFile"
  }
}
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$OutputRootFullPath = if ([System.IO.Path]::IsPathRooted($OutputRoot)) {
  [System.IO.Path]::GetFullPath($OutputRoot)
} else {
  [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot $OutputRoot))
}
$RunOutputRoot = Join-Path $OutputRootFullPath ("DCOIR_TestRun_{0}" -f $Timestamp)
$LogsDir = Join-Path $RunOutputRoot "logs"
$WorkingZipPath = [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot "DCOIR_Collector.zip"))
$MasterZipFullPath = if ([System.IO.Path]::IsPathRooted($MasterZipPath)) {
  [System.IO.Path]::GetFullPath($MasterZipPath)
} else {
  [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot $MasterZipPath))
}

$script:CollectorRunId = $null
$script:CollectorSessionId = $null
$script:Results = New-Object System.Collections.ArrayList
$script:CoverageRows = New-Object System.Collections.ArrayList
$script:CollectorStepTimeoutMilliseconds = [int]($CollectorStepTimeoutSeconds * 1000)
$ProgressJsonlPath = Join-Path $RunOutputRoot "progress.jsonl"
$ProgressTxtPath = Join-Path $RunOutputRoot "progress.txt"
$EvidenceRoot = Join-Path $RunOutputRoot "evidence"
$CoverageJsonPath = Join-Path $RunOutputRoot "collector_capability_coverage.json"
$CoverageMdPath = Join-Path $RunOutputRoot "collector_capability_coverage.md"

<#
.SYNOPSIS
Ensures that one directory exists.

.DESCRIPTION
Creates the requested directory path when it does not already exist.

.FUNCTION NAME
Ensure-Directory

.INPUTS
Path string.

.OUTPUTS
No direct output. Creates the directory as a side effect.
#>
function Ensure-Directory {
  param([string]$Path)
  if (-not (Test-Path -LiteralPath $Path)) {
    New-Item -Path $Path -ItemType Directory -Force | Out-Null
  }
}

<#
.SYNOPSIS
Parses one KEY=value line from collector or harness output text.

.DESCRIPTION
Finds the first line matching the supplied key and returns the trimmed value portion.
Returns null when the key is absent.

.FUNCTION NAME
Parse-OutputValue

.INPUTS
Text string and Key string.

.OUTPUTS
String value or null.
#>
function Parse-OutputValue {
  param([string]$Text,[string]$Key)
  $pattern = '(?m)^{0}=(.+)$' -f [regex]::Escape($Key)
  $m = [regex]::Match($Text, $pattern)
  if ($m.Success) { return $m.Groups[1].Value.Trim() }
  return $null
}

<#
.SYNOPSIS
Writes one harness log file.

.DESCRIPTION
Ensures the logs directory exists, writes the supplied lines to a named step log, and
returns the log path.

.FUNCTION NAME
Write-HarnessLog

.INPUTS
StepName string and Lines string array.

.OUTPUTS
String log-file path.
#>
function Write-HarnessLog {
  param([string]$StepName,[string[]]$Lines)
  Ensure-Directory -Path $LogsDir
  $logPath = Join-Path $LogsDir ("{0}.txt" -f $StepName)
  Set-Content -Path $logPath -Value $Lines -Encoding UTF8
  return $logPath
}


<#
.SYNOPSIS
Writes one durable harness progress event.

.DESCRIPTION
Appends JSONL and text progress records before and after meaningful harness operations so
interrupted FullRegression runs preserve the last active suite, step, command, and log path.

.FUNCTION NAME
Write-HarnessProgress

.INPUTS
SuiteName, StepName, Phase, Status, Command, TimeoutSeconds, ProcessId, RunId, SessionId,
LogPath, and Message values.

.OUTPUTS
No direct output. Appends progress.jsonl and progress.txt entries.
#>
function Write-HarnessProgress {
  param(
    [string]$SuiteName = $Suite,
    [string]$StepName,
    [string]$Phase,
    [string]$Status = '',
    [string]$Command = '',
    [int]$TimeoutSeconds = 0,
    [int]$ProcessId = 0,
    [string]$RunId = $script:CollectorRunId,
    [string]$SessionId = $script:CollectorSessionId,
    [string]$LogPath = '',
    [string]$Message = ''
  )
  Ensure-Directory -Path $RunOutputRoot
  $event = [ordered]@{
    timestamp = (Get-Date).ToString('o')
    suite = $SuiteName
    step = $StepName
    phase = $Phase
    status = $Status
    command = $Command
    timeout_seconds = $TimeoutSeconds
    process_id = $ProcessId
    run_id = $RunId
    enrich_session_id = $SessionId
    log_path = $LogPath
    message = $Message
  }
  $json = $event | ConvertTo-Json -Compress -Depth 4
  Add-Content -Path $ProgressJsonlPath -Value $json -Encoding UTF8
  Add-Content -Path $ProgressTxtPath -Value ("{0} SUITE={1} STEP={2} PHASE={3} STATUS={4} RUN_ID={5} LOG={6} MESSAGE={7}" -f $event.timestamp, $SuiteName, $StepName, $Phase, $Status, $RunId, $LogPath, $Message) -Encoding UTF8
}

<#
.SYNOPSIS
Copies one evidence file into the durable harness evidence folder.

.DESCRIPTION
Preserves bounded copies of collector artifacts referenced by harness logs so workflow
artifacts can be independently reviewed without transient C:\Temp paths.

.FUNCTION NAME
Add-HarnessEvidenceFile

.INPUTS
StepName, Path, and optional Label.

.OUTPUTS
String copied evidence path or null.
#>
function Add-HarnessEvidenceFile {
  param([string]$StepName,[string]$Path,[string]$Label = '')
  if ([string]::IsNullOrWhiteSpace($Path) -or -not (Test-Path -LiteralPath $Path)) { return $null }
  Ensure-Directory -Path $EvidenceRoot
  $safeStep = ($StepName -replace '[\\/:*?"<>| ]','_')
  $stepDir = Join-Path $EvidenceRoot $safeStep
  Ensure-Directory -Path $stepDir
  $baseName = Split-Path -Leaf $Path
  if (-not [string]::IsNullOrWhiteSpace($Label)) { $baseName = ("{0}_{1}" -f (($Label -replace '[\\/:*?"<>| ]','_')), $baseName) }
  $dest = Join-Path $stepDir $baseName
  Copy-Item -LiteralPath $Path -Destination $dest -Force
  return $dest
}

<#
.SYNOPSIS
Copies standard collector contract artifacts for one step.

.DESCRIPTION
Preserves reports, manifests, targeted artifacts, summaries, and chunk manifests that are
printed as collector response paths.

.FUNCTION NAME
Add-CollectorStepEvidence

.INPUTS
StepName and CollectorStep object.

.OUTPUTS
No direct output. Copies available artifacts into the evidence folder.
#>
function Add-CollectorStepEvidence {
  param([string]$StepName,[object]$CollectorStep)
  foreach ($row in @(
    @{ Label='metadata'; Path=$CollectorStep.MetadataReportPath },
