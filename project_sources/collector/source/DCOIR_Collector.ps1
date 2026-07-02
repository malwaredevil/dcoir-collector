[CmdletBinding(SupportsShouldProcess=$true)]
param(
  [ValidateSet("Collect","Enrich","Cleanup")]
  [string]$Mode = "Collect",

  [ValidateSet("T1","T2")]
  [string]$Tier = "T1",

  [int]$Hours = 24,

  [string]$OutRoot = "C:\Temp",

  [string]$PackageName = "DCOIR_Collector.zip",

  [string]$RunId,

  [ValidateSet(
    "SigcheckPath",
    "ListDllsPid",
    "AccessChkFile",
    "AccessChkService",
    "AccessChkReg",
    "StringsPath",
    "StreamsPath",
    "TcpvconRefresh",
    "LogText",
    "LogRaw",
    "PullSuspiciousFile",
    "PullScriptOrConfig",
    "PullTaskXml",
    "PullServiceBinary",
    "PullWmiReferencedFile"
  )]
  [string]$Action,

  [int]$TargetPid,
  [string]$Path,
  [string]$ServiceName,
  [string]$RegistryPath,
  [string]$LogName,
  [int[]]$EventId,
  [int]$MaxEvents = 500,
  [string]$EnrichSessionId,
  [switch]$NewEnrichSession,
  [switch]$FinalizeEnrichSession,
  [string]$Quick,
  [string]$Target,
  [string]$Target2,

  [switch]$Targeted,
  [ValidateSet("Generic","PopupWindow","ScriptExecution","PersistenceFollowUp","NetworkOnly","ProcessAndPowerShell")]
  [string]$TargetProfile = "Generic",
  [string]$WindowStart,
  [string]$WindowEnd,
  [string[]]$IncludeArtifactCategory,
  [string]$FocusProcess,
  [string]$FocusPath,
  [string]$FocusIndicator,
  [string]$FocusIndicatorType,
  [string]$UserReport,

  [Alias("help","h","?")]
  [switch]$ShowHelp,

  [Alias("version","ver","buildinfo")]
  [switch]$ShowVersion
)

Set-StrictMode -Version 2
$ErrorActionPreference = "Stop"

<#
.SYNOPSIS
Checks whether one runtime path candidate is usable for collector self-location.

.DESCRIPTION
Rejects blank paths and host shell executable paths such as powershell.exe or pwsh.exe
so script-mode execution does not mistake the PowerShell host for the collector source.

.FUNCTION NAME
Test-DCOIRRuntimePathCandidate

.INPUTS
Path string.

.OUTPUTS
Boolean indicating whether the candidate is a usable collector runtime path.
#>
function Test-DCOIRRuntimePathCandidate {
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
Resolves the collector runtime path for script and optional EXE execution.

.DESCRIPTION
Prefers script-specific paths such as PSCommandPath and MyInvocation.PSCommandPath for
PowerShell script execution, then safely checks MyInvocation.MyCommand properties, and
finally falls back to the current process executable path for the optional EXE variant.
The resolver avoids strict-mode property errors when PS2EXE command metadata lacks a
Path property.

.FUNCTION NAME
Resolve-DCOIRRuntimePath

.INPUTS
No direct parameters.

.OUTPUTS
String absolute path to the active collector script or optional EXE runtime.
#>
function Resolve-DCOIRRuntimePath {
  foreach ($candidate in @($PSCommandPath, $MyInvocation.PSCommandPath)) {
    if (Test-DCOIRRuntimePathCandidate -Path $candidate) {
      return [System.IO.Path]::GetFullPath([string]$candidate)
    }
  }

  try {
    $cmd = $MyInvocation.MyCommand
    if ($null -ne $cmd) {
      $pathProperty = $cmd.PSObject.Properties['Path']
      if ($pathProperty -and (Test-DCOIRRuntimePathCandidate -Path ([string]$pathProperty.Value))) {
        return [System.IO.Path]::GetFullPath([string]$pathProperty.Value)
      }
      $sourceProperty = $cmd.PSObject.Properties['Source']
      if ($sourceProperty -and (Test-DCOIRRuntimePathCandidate -Path ([string]$sourceProperty.Value))) {
        return [System.IO.Path]::GetFullPath([string]$sourceProperty.Value)
      }
    }
  } catch { }

  try {
    $processPath = [System.Diagnostics.Process]::GetCurrentProcess().MainModule.FileName
    if (Test-DCOIRRuntimePathCandidate -Path $processPath) {
      return [System.IO.Path]::GetFullPath($processPath)
    }
  } catch { }

  return [System.IO.Path]::GetFullPath((Join-Path (Get-Location).Path "DCOIR_Collector.ps1"))
}

$ScriptFilePath = Resolve-DCOIRRuntimePath
$ScriptVersion = "4.0.7"

$Global:CollectorErrors = New-Object System.Collections.ArrayList
$Global:CollectorNotes = New-Object System.Collections.ArrayList
$Global:RecommendedActions = New-Object System.Collections.ArrayList
$Global:ExecutionTxtPath = $null
$Global:ExecutionJsonlPath = $null
$Global:ErrorsLogPath = $null
$Global:CurrentRunId = $null
$script:ContextualHelpTopic = $null
$script:DCOIRRunIdParameterWasBound = $PSBoundParameters.ContainsKey("RunId")

$collectorPartsRoot = Join-Path (Split-Path -Parent $ScriptFilePath) "parts"
$collectorPartFiles = @(
  "DCOIR_Collector.01A1_Core_Logging_And_Process_Capture.ps1",
  "DCOIR_Collector.01A2_Core_Logging_And_Process_Capture.ps1",
  "DCOIR_Collector.01B1_Json_State_And_Array_Utilities.ps1",
  "DCOIR_Collector.01B2_Json_State_And_Array_Utilities.ps1",
  "DCOIR_Collector.01C_Runtime_Paths_Artifacts_And_Reports.ps1",
  "DCOIR_Collector.01D1_Process_Event_And_Baseline_Utilities.ps1",
  "DCOIR_Collector.01D2_Process_Event_And_Baseline_Utilities.ps1",
  "DCOIR_Collector.01E_Tool_Staging_And_Availability.ps1",
  "DCOIR_Collector.02A_Baseline_Collection_And_Reports.ps1",
  "DCOIR_Collector.02B_Baseline_Collection_And_Reports.ps1",
  "DCOIR_Collector.02C_Baseline_Collection_And_Reports.ps1",
  "DCOIR_Collector.02D1A_Baseline_Collection_And_Reports.ps1",
  "DCOIR_Collector.02D1B_Baseline_Collection_And_Reports.ps1",
  "DCOIR_Collector.02D2_Baseline_Collection_And_Reports.ps1",
  "DCOIR_Collector.03A_Enrich_Session_State.ps1",
  "DCOIR_Collector.03B_Enrich_Actions_Review.ps1",
  "DCOIR_Collector.03C_Enrich_Actions_Retrieval.ps1",
  "DCOIR_Collector.04A1_Quick_Interface_And_Output.ps1",
  "DCOIR_Collector.04A2_Quick_Interface_And_Output.ps1",
  "DCOIR_Collector.04A3_Quick_Interface_And_Output.ps1",
  "DCOIR_Collector.04B1_Feature_Wave_Targeted_Collection.ps1",
  "DCOIR_Collector.04B2_Feature_Wave_Targeted_Collection.ps1",
  "DCOIR_Collector.04C_Explicit_Event_Window_Overrides.ps1",
  "DCOIR_Collector.04D1_Bounded_Parallel_Runtime.ps1",
  "DCOIR_Collector.04D2_Bounded_Parallel_Runtime.ps1",
  "DCOIR_Collector.04D3_Bounded_Parallel_Runtime.ps1",
  "DCOIR_Collector.04E1_Diagnostic_Context_Overrides.ps1",
  "DCOIR_Collector.04E2_Diagnostic_Context_Overrides.ps1",
  "DCOIR_Collector.04F1_PR186_Review_Fixes.ps1",
  "DCOIR_Collector.04F2_PR186_Review_Fixes.ps1",
  "DCOIR_Collector.04G1_PR186_External_Review_Fixes.ps1",
  "DCOIR_Collector.04G2_PR186_External_Review_Fixes.ps1",
  "DCOIR_Collector.04H1_PR212_Metadata_Finalization_Fixes.ps1",
  "DCOIR_Collector.04H2_PR212_Metadata_Finalization_Fixes.ps1",
  "DCOIR_Collector.04H3_PR212_Metadata_Finalization_Fixes.ps1",
  "DCOIR_Collector.05A1_Main_Entry.ps1",
  "DCOIR_Collector.05A2_Main_Entry.ps1",
  "DCOIR_Collector.05A3_Main_Entry.ps1",
  "DCOIR_Collector.05B_Main_Entry.ps1",
  "DCOIR_Collector.05C_Main_Entry.ps1",
  "DCOIR_Collector.05_Main_Entry.ps1"
)

foreach ($partFile in $collectorPartFiles) {
  $partPath = Join-Path $collectorPartsRoot $partFile
  if (-not (Test-Path -LiteralPath $partPath)) {
    throw "Required collector part file missing: $partPath"
  }
  . $partPath
}
