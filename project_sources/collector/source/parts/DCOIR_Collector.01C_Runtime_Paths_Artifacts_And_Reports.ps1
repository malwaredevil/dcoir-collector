<#
.SYNOPSIS
DCOIR collector runtime path, artifact, and report utility helpers.

.DESCRIPTION
Provides script-directory and tool resolution, report section formatting, run-structure
initialization, package staging, baseline artifact prefixes, and session artifact helpers.

.FILE NAME
DCOIR_Collector.01C_Runtime_Paths_Artifacts_And_Reports.ps1

.INPUTS
Collector runtime globals, output roots, package paths, report builders, state objects,
session IDs, and artifact text.

.OUTPUTS
Resolved paths, initialized run state, report text sections, package staging results, and
session artifact paths.
#>

<#
.SYNOPSIS
Returns the active script directory.

.DESCRIPTION
Resolves the script directory from ScriptFilePath first, then PSScriptRoot, and finally
falls back to the current working directory.

.FUNCTION NAME
Get-ScriptDirectory

.INPUTS
No direct parameters.

.OUTPUTS
String script-directory path.
#>
function Get-ScriptDirectory {
  if (-not [string]::IsNullOrWhiteSpace($ScriptFilePath)) {
    return (Split-Path -Parent $ScriptFilePath)
  }
  if ($PSScriptRoot) {
    return $PSScriptRoot
  }
  return (Get-Location).Path
}

<#
.SYNOPSIS
Resolves one staged tool path from the tools directory.

.DESCRIPTION
Checks the 64-bit and standard executable names for the requested Sysinternals-style
base tool name and returns the first existing path.

.FUNCTION NAME
Resolve-Tool

.INPUTS
ToolsDir string and BaseName string.

.OUTPUTS
String tool path or null when the tool is absent.
#>
function Resolve-Tool {
  param([string]$ToolsDir,[string]$BaseName)

  $candidates = @(
    (Join-Path $ToolsDir ("{0}64.exe" -f $BaseName)),
    (Join-Path $ToolsDir ("{0}.exe" -f $BaseName))
  )

  foreach ($candidate in $candidates) {
    if (Test-Path -LiteralPath $candidate) { return $candidate }
  }
  return $null
}

<#
.SYNOPSIS
Builds the standard report-section header lines.

.DESCRIPTION
Returns the blank line and divider pattern used before each named report section.

.FUNCTION NAME
New-SectionHeader

.INPUTS
Name string for the section title.

.OUTPUTS
String array containing the section header lines.
#>
function New-SectionHeader {
  param([string]$Name)
  return @(
    ""
    ("=" * 80)
    $Name
    ("=" * 80)
    ""
  )
}

<#
.SYNOPSIS
Appends one named section to a StringBuilder report.

.DESCRIPTION
Writes the standard section header and the supplied text to the StringBuilder.

.FUNCTION NAME
Add-Section

.INPUTS
Builder StringBuilder, section Name string, and Text string.

.OUTPUTS
No direct output. Appends to the StringBuilder as a side effect.
#>
function Add-Section {
  param(
    [System.Text.StringBuilder]$Builder,
    [string]$Name,
    [string]$Text
  )
  foreach ($line in (New-SectionHeader -Name $Name)) {
    [void]$Builder.AppendLine($line)
  }
  [void]$Builder.AppendLine(($Text | Out-String))
}

<#
.SYNOPSIS
Formats one object into a wide text block.

.DESCRIPTION
Returns an empty string for null input and otherwise uses Out-String with width 500.

.FUNCTION NAME
Convert-ToTextBlock

.INPUTS
InputObject to format.

.OUTPUTS
String text block.
#>
function Convert-ToTextBlock {
  param([object]$InputObject)
  if ($null -eq $InputObject) { return "" }
  return ($InputObject | Out-String -Width 500)
}

<#
.SYNOPSIS
Creates the run directory structure for one collector run.

.DESCRIPTION
Builds the standard run-root, tools, reports, artifacts, enrich-sessions, logs, and
bundles directories and returns their paths plus the state-file path.

.FUNCTION NAME
Initialize-RunStructure

.INPUTS
Root string and CurrentRunId string.

.OUTPUTS
Hashtable containing the run-structure paths.
#>
function Initialize-RunStructure {
  param([string]$Root,[string]$CurrentRunId)

  $runRoot = Get-RunRoot -Root $Root -CurrentRunId $CurrentRunId
  $toolsDir = Join-Path $runRoot "tools"
  $reportsDir = Join-Path $runRoot "reports"
  $artifactsDir = Join-Path $runRoot "final_artifacts"
  $enrichSessionsDir = Join-Path $runRoot "enrich_sessions"
  $logsDir = Join-Path $runRoot "logs"
  $bundlesDir = Join-Path $runRoot "bundles"

  Ensure-Directory -Path $Root
  Ensure-Directory -Path $runRoot
  Ensure-Directory -Path $toolsDir
  Ensure-Directory -Path $reportsDir
  Ensure-Directory -Path $artifactsDir
  Ensure-Directory -Path $enrichSessionsDir
  Ensure-Directory -Path $logsDir
  Ensure-Directory -Path $bundlesDir

  return @{
    RunRoot = $runRoot
    ToolsDir = $toolsDir
    ReportsDir = $reportsDir
    ArtifactsDir = $artifactsDir
    EnrichSessionsDir = $enrichSessionsDir
    LogsDir = $logsDir
    BundlesDir = $bundlesDir
    StatePath = (Join-Path $runRoot "state.json")
  }
}

<#
.SYNOPSIS
Moves the package ZIP into the out-root when needed.

.DESCRIPTION
Looks for the current package in the script directory first, moves it into the out-root
when necessary, or returns the already-present out-root package path.

.FUNCTION NAME
Move-PackageToOutRoot

.INPUTS
Root string and CurrentPackageName string.

.OUTPUTS
String package path in the out-root, or null when package movement is skipped.
#>
function Move-PackageToOutRoot {
  [CmdletBinding(SupportsShouldProcess=$true, ConfirmImpact='Medium')]
  param([string]$Root,[string]$CurrentPackageName)

  $scriptDir = Get-ScriptDirectory
  $sourcePath = Join-Path $scriptDir $CurrentPackageName
  $destPath = Join-Path $Root $CurrentPackageName
  $checkedPaths = @($sourcePath, $destPath)

  if (Test-Path -LiteralPath $sourcePath) {
    if ($sourcePath -ne $destPath) {
      if ($PSCmdlet.ShouldProcess($destPath, ("Move collector package from {0}" -f $sourcePath))) {
        Move-Item -LiteralPath $sourcePath -Destination $destPath -Force
        return $destPath
      }
      return $null
    }
    return $sourcePath
  }

  if (Test-Path -LiteralPath $destPath) {
    return $destPath
  }

  throw ("Package not found: {0}. CheckedPaths={1}" -f $CurrentPackageName, ($checkedPaths -join '; '))
}

<#
.SYNOPSIS
Expands the package ZIP into the tools directory.

.DESCRIPTION
Recreates the tools directory and extracts the package ZIP into it, throwing on
extraction failure.

.FUNCTION NAME
Expand-PackageToTools

.INPUTS
PackagePath string and ToolsDir string.

.OUTPUTS
Boolean true when tools were expanded, false when expansion was skipped.
#>
function Expand-PackageToTools {
  [CmdletBinding(SupportsShouldProcess=$true, ConfirmImpact='Medium')]
  param([string]$PackagePath,[string]$ToolsDir)

  if ([string]::IsNullOrWhiteSpace($PackagePath)) { return $false }

  try {
    if ($PSCmdlet.ShouldProcess($ToolsDir, ("Recreate tools directory from package {0}" -f $PackagePath))) {
      Remove-IfExists -LiteralPath $ToolsDir
      if (Test-Path -LiteralPath $ToolsDir) { return $false }
      Ensure-Directory -Path $ToolsDir
      if (-not (Test-Path -LiteralPath $ToolsDir)) { return $false }
      Expand-Archive -LiteralPath $PackagePath -DestinationPath $ToolsDir -Force -ErrorAction Stop
      return $true
    }
    return $false
  } catch {
    throw "Failed to expand package [$PackagePath] to [$ToolsDir]: $($_.Exception.Message)"
  }
}

<#
.SYNOPSIS
Returns the numeric prefix used for one baseline artifact name.

.DESCRIPTION
Maps well-known baseline artifact names to stable ordering prefixes used in final
artifact filenames.

.FUNCTION NAME
Get-BaselineArtifactPrefix

.INPUTS
Name string for the artifact file.

.OUTPUTS
String prefix value.
#>
function Get-BaselineArtifactPrefix {
  param([string]$Name)
  switch ($Name.ToLowerInvariant()) {
    "collection_metadata.txt" { "01" }
    "collection_notes_and_limitations.txt" { "02" }
    "time_host.txt" { "03" }
    "systeminfo.txt" { "04" }
    "whoami_all.txt" { "05" }
    "sessions.txt" { "06" }
    "logon_sessions_wmi.txt" { "07" }
    "process_inventory.txt" { "08" }
    "pslist.txt" { "09" }
    "ipconfig_all.txt" { "10" }
    "netstat_abno.txt" { "11" }
    "structured_net.txt" { "12" }
    "dns_cache.txt" { "13" }
    "route_print.txt" { "14" }
    "arp_a.txt" { "15" }
    "tcpvcon.txt" { "16" }
    "pipelist.txt" { "17" }
    "services.txt" { "18" }
    "scheduled_tasks.txt" { "19" }
    "run_hklm.txt" { "20" }
    "run_hku_loaded_users.txt" { "21" }
    "autorunsc.csv.txt" { "22" }
    "defender_status.txt" { "23" }
    "firewall_profiles.txt" { "24" }
    "security_filtered.txt" { "25" }
    "security_high_signal_summary.txt" { "25A" }
    "powershell_operational_filtered.txt" { "26" }
    "taskscheduler_operational_filtered.txt" { "27" }
    "tier2_reg_ifeo.txt" { "28" }
    "tier2_reg_winlogon.txt" { "29" }
    "tier2_reg_lsa.txt" { "30" }
    "tier2_wmi_persistence.txt" { "31" }
    "tier2_net_share.txt" { "32" }
    "tier2_net_session.txt" { "33" }
    "tier2_firewall_profiles.txt" { "34" }
    "analyst_follow_up_queue.txt" { "35" }
    default { "99" }
  }
}

<#
.SYNOPSIS
Returns the next enrichment-session action sequence number.

.DESCRIPTION
Counts the existing text artifacts in the session artifacts directory and returns the
next sequential number.

.FUNCTION NAME
Get-SessionActionSequence

.INPUTS
SessionArtifactsDir string.

.OUTPUTS
Integer sequence number.
#>
function Get-SessionActionSequence {
  param([string]$SessionArtifactsDir)
  $count = @(Get-ChildItem -LiteralPath $SessionArtifactsDir -File -Filter "*.txt" -ErrorAction SilentlyContinue).Count
  return ($count + 1)
}

<#
.SYNOPSIS
Writes one enrichment-session artifact text file.

.DESCRIPTION
Builds the sequential enrich artifact filename, writes the supplied text, and returns
the created session artifact path.

.FUNCTION NAME
Write-SessionArtifactText

.INPUTS
SessionArtifactsDir string, ActionName string, TargetLabel string, and Text string.

.OUTPUTS
String session artifact path.
#>
function Write-SessionArtifactText {
  [CmdletBinding(SupportsShouldProcess=$true)]
  param(
    [string]$SessionArtifactsDir,
    [string]$ActionName,
    [string]$TargetLabel,
    [string]$Text
  )
  if ($PSCmdlet.ShouldProcess($SessionArtifactsDir, 'Ensure enrich session artifacts directory')) {
    Ensure-Directory -Path $SessionArtifactsDir
  }
  $seq = if (Test-Path -LiteralPath $SessionArtifactsDir) {
    Get-SessionActionSequence -SessionArtifactsDir $SessionArtifactsDir
  } else {
    1
  }
  $safeAction = ($ActionName -replace '[\\/:*?"<>| ]','_')
  $safeTarget = ($TargetLabel -replace '[\\/:*?"<>| ]','_')
  if ([string]::IsNullOrWhiteSpace($safeTarget)) { $safeTarget = "artifact" }
  if ($safeTarget.Length -gt 80) { $safeTarget = $safeTarget.Substring(0,80) }
  $path = Join-Path $SessionArtifactsDir ("{0:D2}_ENRICH_{1}_{2}.txt" -f $seq, $safeAction, $safeTarget)
  if ($PSCmdlet.ShouldProcess($path, 'Write enrich session artifact')) {
    Set-Content -LiteralPath $path -Value $Text -Encoding UTF8 -ErrorAction Stop
    return $path
  }
  return $null
}
