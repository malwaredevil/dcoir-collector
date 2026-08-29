<#
.SYNOPSIS
DCOIR collector tool staging, service, task, and availability helpers.

.DESCRIPTION
Provides external-tool text capture, deterministic stage names, service binary path
resolution, staged path copying, scheduled task XML capture, tool map construction, and
command availability reporting.

.FILE NAME
DCOIR_Collector.01E_Tool_Staging_And_Availability.ps1

.INPUTS
Tool paths, service names, file paths, scheduled task names, and collector state
directories.

.OUTPUTS
Tool output text, staged file paths, task XML text, tool availability maps, and command
availability rows.
#>

<#
.SYNOPSIS
Runs one staged external tool and returns its combined text output.

.DESCRIPTION
Wraps Invoke-ProcessCapture for a staged tool executable and formats the result into the
standard combined output text block.

.FUNCTION NAME
Invoke-ToolToText

.INPUTS
ToolPath string, argument array, StepName string, and optional allowed exit-code list.

.OUTPUTS
String containing the combined tool output text.
#>
function Invoke-ToolToText {
  param(
    [string]$ToolPath,
    [string[]]$Arguments,
    [string]$StepName,
    [int[]]$AllowedExitCodes = @(0)
  )
  $result = Invoke-ProcessCapture -FilePath $ToolPath -Arguments $Arguments -StepName $StepName -AllowedExitCodes $AllowedExitCodes
  return (Get-CombinedProcessOutput -Result $result)
}

<#
.SYNOPSIS
Builds a unique staged filename.

.DESCRIPTION
Combines the supplied prefix, hostname, timestamp, GUID fragment, and extension into a
unique staged artifact filename.

.FUNCTION NAME
New-StageName

.INPUTS
Prefix string and Extension string.

.OUTPUTS
String staged filename.
#>
function New-StageName {
  param([string]$Prefix,[string]$Extension)
  $ts = Get-Date -Format "yyyyMMdd_HHmmss"
  $guid = ([guid]::NewGuid().ToString("N")).Substring(0,8)
  return ("{0}_{1}_{2}_{3}{4}" -f $Prefix, $env:COMPUTERNAME, $ts, $guid, $Extension)
}

<#
.SYNOPSIS
Resolves the binary path for one Windows service.

.DESCRIPTION
Queries Win32_Service for the requested service name and extracts the executable path
from the service PathName field.

.FUNCTION NAME
Get-ServiceBinaryPath

.INPUTS
Name string for the service.

.OUTPUTS
String service-binary path or null when unresolved.
#>
function Get-ServiceBinaryPath {
  param([string]$Name)
  try {
    $svc = Get-CimInstance -ClassName Win32_Service -Filter ("Name='{0}'" -f ($Name -replace "'", "''")) -ErrorAction Stop
    if (-not $svc) { return $null }
    $pn = [string]$svc.PathName
    if ([string]::IsNullOrWhiteSpace($pn)) { return $null }
    if ($pn.StartsWith('"')) {
      return ($pn -replace '^"([^"]+)".*$', '$1')
    }
    return ($pn -replace '^([^\s]+).*$', '$1')
  } catch {
    Add-CollectorError "Failed to resolve service binary for [$Name]: $($_.Exception.Message)"
    return $null
  }
}

<#
.SYNOPSIS
Stages a copy of one filesystem path into the staged directory.

.DESCRIPTION
Validates that the source path exists, ensures the staged directory exists, copies the
source into a unique staged filename, and returns the staged path.

.FUNCTION NAME
Stage-PathCopy

.INPUTS
SourcePath string and StagedDir string.

.OUTPUTS
String staged copy path.
#>
function Stage-PathCopy {
  [CmdletBinding(SupportsShouldProcess=$true)]
  param([string]$SourcePath,[string]$StagedDir)
  if (-not (Test-Path -LiteralPath $SourcePath)) {
    throw "Path not found: $SourcePath"
  }
  $leaf = Split-Path -Leaf $SourcePath
  $dest = Join-Path $StagedDir (New-StageName -Prefix ("STAGED_" + $leaf) -Extension "")
  if ($PSCmdlet.ShouldProcess($dest, ("Copy staged evidence from {0}" -f $SourcePath))) {
    Ensure-Directory -Path $StagedDir
    Copy-Item -LiteralPath $SourcePath -Destination $dest -Force -ErrorAction Stop
    return $dest
  }
  return $null
}

<#
.SYNOPSIS
Exports one scheduled task XML surface.

.DESCRIPTION
Runs schtasks.exe /query /xml for the requested task name and returns the combined
command output text.

.FUNCTION NAME
Get-TaskXml

.INPUTS
TaskName string.

.OUTPUTS
String containing task XML command output or an error message.
#>
function Get-TaskXml {
  param([string]$TaskName)
  try {
    $result = Invoke-ProcessCapture -FilePath "schtasks.exe" -Arguments @("/query","/tn",$TaskName,"/xml") -StepName "ENRICH_PULL_TASK_XML"
    return (Get-CombinedProcessOutput -Result $result)
  } catch {
    Add-CollectorError "Failed to export task XML for [$TaskName]: $($_.Exception.Message)"
    return "ERROR exporting task XML: $($_.Exception.Message)"
  }
}

<#
.SYNOPSIS
Builds the tool map for the staged tools directory.

.DESCRIPTION
Resolves the expected collector helper tools from the staged tools directory and returns
the resulting tool-path map.

.FUNCTION NAME
Get-ToolMap

.INPUTS
ToolsDir string.

.OUTPUTS
Hashtable mapping tool names to resolved paths.
#>
function Get-ToolMap {
  param([string]$ToolsDir)
  return @{
    accesschk = Resolve-Tool -ToolsDir $ToolsDir -BaseName "accesschk"
    autorunsc = Resolve-Tool -ToolsDir $ToolsDir -BaseName "autorunsc"
    listdlls = Resolve-Tool -ToolsDir $ToolsDir -BaseName "listdlls"
    pipelist = Resolve-Tool -ToolsDir $ToolsDir -BaseName "pipelist"
    pslist = Resolve-Tool -ToolsDir $ToolsDir -BaseName "pslist"
    sigcheck = Resolve-Tool -ToolsDir $ToolsDir -BaseName "sigcheck"
    streams = Resolve-Tool -ToolsDir $ToolsDir -BaseName "streams"
    strings = Resolve-Tool -ToolsDir $ToolsDir -BaseName "strings"
    tcpvcon = Resolve-Tool -ToolsDir $ToolsDir -BaseName "tcpvcon"
  }
}

<#
.SYNOPSIS
Builds the tool-availability table text.

.DESCRIPTION
Formats the tool map into an analyst-friendly table showing tool presence and resolved
path.

.FUNCTION NAME
Get-CommandAvailabilityTable

.INPUTS
ToolMap hashtable.

.OUTPUTS
String containing the tool-availability table.
#>
function Get-CommandAvailabilityTable {
  param([hashtable]$ToolMap)
  $rows = foreach ($key in ($ToolMap.Keys | Sort-Object)) {
    [pscustomobject]@{
      Tool = $key
      Present = [bool]($ToolMap[$key])
      Path = $ToolMap[$key]
    }
  }
  return ($rows | Format-Table -AutoSize | Out-String -Width 500)
}
