<#
.SYNOPSIS
DCOIR collector diagnostic event-text export helper.

.DESCRIPTION
Contains the event-log text query helper separated from the high-signal Security summary implementation.

.FILE NAME
DCOIR_Collector.04E3_Event_Text.ps1
#>

<#
.SYNOPSIS
Exports diagnostic-friendly event-log text for the requested channel.

.DESCRIPTION
Uses the effective event window to query the requested channel with optional event IDs,
returns analyst-facing text for the matching events, and preserves the special
non-elevated Security visibility explanation when appropriate.

.FUNCTION NAME
Get-EventText

.INPUTS
Channel string, WindowHours integer, optional integer event IDs, and Take integer.

.OUTPUTS
String containing event-log text or an explicit visibility/error message.
#>
function Get-EventText {
  param(
    [Parameter(Mandatory=$true)][string]$Channel,
    [int]$WindowHours = 24,
    [int[]]$Ids,
    [int]$Take = 500
  )

  try {
    $window = Get-CollectorEffectiveEventWindow -WindowHours $WindowHours
    $fh = @{
      LogName = $Channel
      StartTime = $window.StartTime
    }
    if ($window.HasExplicitWindow -and $window.EndTime) {
      $fh.EndTime = $window.EndTime
    }
    if ($Ids -and @($Ids).Count -gt 0) { $fh.Id = $Ids }

    $queryLimit = [Math]::Max(0, $Take)
    $events = @(Invoke-CollectorBoundedWinEventQuery -FilterHashtable $fh -MaxEvents $queryLimit)

    if (@($events).Count -eq 0) {
      $lines = New-Object System.Collections.ArrayList
      foreach ($metadataLine in (Get-CollectorEventWindowMetadataLines -Window $window -Channel $Channel -Ids $Ids -Take $Take)) { [void]$lines.Add($metadataLine) }
      [void]$lines.Add('EVENT_COUNT=0')
      [void]$lines.Add('')
      if (($Channel -eq 'Security') -and (-not (Test-DiagnosticCollectorIsElevated))) {
        $message = Get-NonElevatedSecurityVisibilityMessage
        Add-CollectorNote $message
        [void]$lines.Add($message)
        return ($lines -join [Environment]::NewLine)
      }
      $message = ("No events were found for channel [{0}] in the selected window." -f $Channel)
      Add-CollectorNote $message
      [void]$lines.Add($message)
      return ($lines -join [Environment]::NewLine)
    }

    $lines = New-Object System.Collections.ArrayList
    foreach ($metadataLine in (Get-CollectorEventWindowMetadataLines -Window $window -Channel $Channel -Ids $Ids -Take $Take)) { [void]$lines.Add($metadataLine) }
    [void]$lines.Add(("EVENT_COUNT={0}" -f @($events).Count))
    [void]$lines.Add('')

    foreach ($ev in $events) {
      [void]$lines.Add(("TimeCreated={0}" -f $ev.TimeCreated.ToString('o')))
      [void]$lines.Add(("Id={0}" -f $ev.Id))
      [void]$lines.Add(("Provider={0}" -f $ev.ProviderName))
      [void]$lines.Add(("Level={0}" -f $ev.LevelDisplayName))
      [void]$lines.Add(("RecordId={0}" -f $ev.RecordId))
      [void]$lines.Add(("MachineName={0}" -f $ev.MachineName))
      if ($ev.TaskDisplayName) { [void]$lines.Add(("Task={0}" -f $ev.TaskDisplayName)) }
      if ($ev.UserId) { [void]$lines.Add(("UserId={0}" -f $ev.UserId.Value)) }
      [void]$lines.Add('Message:')
      [void]$lines.Add(($ev.Message -replace "`r", ''))
      [void]$lines.Add('-' * 60)
    }

    return ($lines -join [Environment]::NewLine)
  } catch {
    $msg = $_.Exception.Message
    if ($msg -match 'No events were found') {
      $window = Get-CollectorEffectiveEventWindow -WindowHours $WindowHours
      $lines = New-Object System.Collections.ArrayList
      foreach ($metadataLine in (Get-CollectorEventWindowMetadataLines -Window $window -Channel $Channel -Ids $Ids -Take $Take)) { [void]$lines.Add($metadataLine) }
      [void]$lines.Add('EVENT_COUNT=0')
      [void]$lines.Add('')
      if (($Channel -eq 'Security') -and (-not (Test-DiagnosticCollectorIsElevated))) {
        $message = Get-NonElevatedSecurityVisibilityMessage
        Add-CollectorNote $message
        [void]$lines.Add($message)
        return ($lines -join [Environment]::NewLine)
      }
      $message = ("No events were found for channel [{0}] in the selected window." -f $Channel)
      Add-CollectorNote $message
      [void]$lines.Add($message)
      return ($lines -join [Environment]::NewLine)
    }
    Add-CollectorError (("Failed to collect event log text for [{0}]: {1}" -f $Channel, $msg))
    return (("ERROR collecting event log text for [{0}]: {1}" -f $Channel, $msg))
  }
}
# DCOIR_REVIEW_AUDIT_BATCH_2F_MARKER
