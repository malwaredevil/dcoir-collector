<#
.SYNOPSIS
DCOIR collector explicit event-window helpers.

.DESCRIPTION
Implements explicit event-window parsing, event-filter hashtable construction, event-log
text export, Security high-signal summarization, and raw EVTX export for targeted and
enrichment-driven collection lanes.

.FILE NAME
DCOIR_Collector.04C_Explicit_Event_Window_Overrides.ps1

.INPUTS
Window-hours values, explicit WindowStart and WindowEnd globals, event-log channel
names, optional event IDs, output paths, and scratch directories.

.OUTPUTS
Window hashtables, event-filter hashtables, analyst-facing text summaries, and staged
EVTX exports.
#>

<#
.SYNOPSIS
Builds a Get-WinEvent filter hashtable from a normalized window object.

.DESCRIPTION
Creates the filter hashtable used by event readers, always including LogName and
StartTime and conditionally adding EndTime and Id constraints when present.

.FUNCTION NAME
Get-CollectorEventFilterHashtable

.INPUTS
LogName string, Window hashtable from Get-CollectorEffectiveEventWindow, and optional
integer event IDs.

.OUTPUTS
Hashtable suitable for Get-WinEvent -FilterHashtable.
#>
function Get-CollectorEventFilterHashtable {
  param(
    [Parameter(Mandatory=$true)][string]$LogName,
    [hashtable]$Window,
    [int[]]$Ids
  )

  $fh = @{
    LogName = $LogName
    StartTime = $Window.StartTime
  }

  if ($Window.EndTime) {
    $fh.EndTime = $Window.EndTime
  }

  if ($Ids -and @($Ids).Count -gt 0) {
    $fh.Id = $Ids
  }

  return $fh
}

<#
.SYNOPSIS
Formats event-window metadata for text reports.

.DESCRIPTION
Returns stable key-value lines that make the effective event-window behavior observable in
event text, summaries, and enrichment reports.

.FUNCTION NAME
Get-CollectorEventWindowMetadataLines

.INPUTS
Window hashtable, channel name, optional event IDs, and max-event count.

.OUTPUTS
Array of strings.
#>
function Get-CollectorEventWindowMetadataLines {
  param(
    [hashtable]$Window,
    [string]$Channel,
    [int[]]$Ids,
    [int]$Take
  )

  $lines = New-Object System.Collections.ArrayList
  if (-not [string]::IsNullOrWhiteSpace($Channel)) { [void]$lines.Add(("CHANNEL={0}" -f $Channel)) }
  [void]$lines.Add(("WINDOW_HOURS={0}" -f $Window.EffectiveHours))
  [void]$lines.Add(("HAS_EXPLICIT_TIME_WINDOW={0}" -f $Window.HasExplicitWindow))
  [void]$lines.Add(("WINDOW_START={0}" -f $Window.StartTime.ToString("o")))
  [void]$lines.Add(("WINDOW_END={0}" -f $(if ($Window.EndTime) { $Window.EndTime.ToString("o") } else { "" })))
  if ($Ids -and @($Ids).Count -gt 0) { [void]$lines.Add(("EVENT_IDS={0}" -f ($Ids -join ','))) }
  if ($Take -gt 0) { [void]$lines.Add(("MAX_EVENTS={0}" -f $Take)) }
  return @($lines)
}

<#
.SYNOPSIS
Exports a filtered EVTX file for the requested channel and window.

.DESCRIPTION
Builds the effective time filter and optional Event ID filter, renders the matching
XPath query, calls wevtutil.exe to export the EVTX file, and verifies that the output
file was created.

.FUNCTION NAME
Export-FilteredEvtx

.INPUTS
LogChannel string, WindowHours integer, optional event IDs, output path, and scratch
directory path.

.OUTPUTS
No direct output. Writes the EVTX file to OutPath or throws on failure.
#>
function Export-FilteredEvtx {
  [CmdletBinding(SupportsShouldProcess=$true)]
  param(
    [string]$LogChannel,
    [int]$WindowHours,
    [int[]]$Ids,
    [string]$OutPath,
    [string]$ScratchDir
  )

  $parentDir = Split-Path -Parent $OutPath

  $window = Get-CollectorEffectiveEventWindow -WindowHours $WindowHours
  if ($window.HasExplicitWindow -and $window.EndTime) {
    $startUtc = $window.StartTime.ToUniversalTime().ToString("o")
    $endUtc = $window.EndTime.ToUniversalTime().ToString("o")
    $systemParts = @("TimeCreated[@SystemTime>='$startUtc' and @SystemTime<='$endUtc']")
  } else {
    $ms = [math]::Abs($window.EffectiveHours) * 3600000
    $systemParts = @("TimeCreated[timediff(@SystemTime) <= $ms]")
  }

  if ($Ids -and @($Ids).Count -gt 0) {
    $idExpr = "(" + (($Ids | ForEach-Object { "EventID=$_"}) -join " or ") + ")"
    $systemParts += $idExpr
  }
  $xpath = "*[System[" + ($systemParts -join " and ") + "]]"

  $args = @(
    "epl",
    $LogChannel,
    $OutPath,
    "/q:$xpath",
    "/ow:true"
  )

  if ($PSCmdlet.ShouldProcess($OutPath, ("Export filtered EVTX from {0}" -f $LogChannel))) {
    Ensure-Directory -Path $ScratchDir
    if (-not [string]::IsNullOrWhiteSpace($parentDir)) {
      Ensure-Directory -Path $parentDir
    }

    $result = Invoke-ProcessCapture -FilePath "wevtutil.exe" -Arguments $args -StepName ("ENRICH_LOGRAW_{0}" -f ($LogChannel -replace '[\\/:*?"<>|]','_'))
    if ($result.ExitCode -ne 0) {
      throw "wevtutil.exe returned exit code $($result.ExitCode)"
    }
    if (-not (Test-Path -LiteralPath $OutPath)) {
      throw "EVTX export did not create output file."
    }
  }
}
