<#
.SYNOPSIS
DCOIR collector PR #186 event-window and validation review-fix helpers.

.DESCRIPTION
Applies narrowly scoped helper refinements for PR #186 review findings before the main
collector entrypoint runs. Normalizes invalid explicit-window state across downstream
scope surfaces and gates synthetic validation padding behind an explicit harness
test-mode flag.

.FILE NAME
DCOIR_Collector.04F2_PR186_Review_Fixes.ps1

.INPUTS
Current collector globals, process environment variables, and state hashtables.

.OUTPUTS
Maintained event-window, targeted-scope, and validation-padding helper functions used by the compiled collector runtime.
#>

<#
.SYNOPSIS
Resolves the effective event window for the current collector call.

.DESCRIPTION
Combines WindowHours with explicit WindowStart and WindowEnd inputs. Invalid or inverted
explicit bounds clear the script-level raw window values so later targeted scope and plan
surfaces cannot reuse rejected values after event readers have fallen back.

.FUNCTION NAME
Get-CollectorEffectiveEventWindow

.INPUTS
WindowHours integer plus WindowStart and WindowEnd globals.

.OUTPUTS
Hashtable containing HasExplicitWindow, StartTime, EndTime, and EffectiveHours.
#>
function Get-CollectorEffectiveEventWindow {
  param([int]$WindowHours = 24)

  $effectiveHours = [math]::Abs($WindowHours)
  if ($effectiveHours -le 0) { $effectiveHours = 24 }

  $now = Get-Date
  $parsedStart = $null
  $parsedEnd = $null
  $parseFailed = $false

  if (-not [string]::IsNullOrWhiteSpace($WindowStart)) {
    [datetime]$tmpStart = [datetime]::MinValue
    if ([datetime]::TryParse($WindowStart, [ref]$tmpStart)) {
      $parsedStart = $tmpStart
    } else {
      Add-CollectorError ("Invalid WindowStart value [{0}]; falling back to hour-window behavior." -f $WindowStart)
      $parseFailed = $true
    }
  }

  if (-not [string]::IsNullOrWhiteSpace($WindowEnd)) {
    [datetime]$tmpEnd = [datetime]::MinValue
    if ([datetime]::TryParse($WindowEnd, [ref]$tmpEnd)) {
      $parsedEnd = $tmpEnd
    } else {
      Add-CollectorError ("Invalid WindowEnd value [{0}]; falling back to hour-window behavior." -f $WindowEnd)
      $parseFailed = $true
    }
  }

  if ($parseFailed) {
    $parsedStart = $null
    $parsedEnd = $null
    $script:WindowStart = $null
    $script:WindowEnd = $null
  } elseif ($parsedStart -and $parsedEnd -and $parsedEnd -lt $parsedStart) {
    Add-CollectorError ("WindowEnd [{0}] is earlier than WindowStart [{1}]; falling back to hour-window behavior." -f $WindowEnd, $WindowStart)
    $parsedStart = $null
    $parsedEnd = $null
    $script:WindowStart = $null
    $script:WindowEnd = $null
  }

  if ($parsedStart -and -not $parsedEnd) {
    $parsedEnd = $now
  } elseif ($parsedEnd -and -not $parsedStart) {
    $parsedStart = $parsedEnd.AddHours(-1 * $effectiveHours)
  }

  if ($parsedStart -and $parsedEnd -and $parsedEnd -lt $parsedStart) {
    Add-CollectorError ("Effective WindowEnd [{0}] is earlier than WindowStart [{1}] after partial-window normalization; falling back to hour-window behavior." -f $parsedEnd.ToString('o'), $parsedStart.ToString('o'))
    $parsedStart = $null
    $parsedEnd = $null
    $script:WindowStart = $null
    $script:WindowEnd = $null
  }

  $hasExplicitWindow = ($parsedStart -ne $null) -or ($parsedEnd -ne $null)
  $startTime = if ($parsedStart) { $parsedStart } else { $now.AddHours(-1 * $effectiveHours) }
  $endTime = if ($parsedEnd) { $parsedEnd } else { $null }

  return @{
    HasExplicitWindow = [bool]$hasExplicitWindow
    StartTime = $startTime
    EndTime = $endTime
    EffectiveHours = $effectiveHours
  }
}

<#
.SYNOPSIS
Builds the targeted collection scope object.

.DESCRIPTION
Uses the same effective event-window resolver as event collection metadata so invalid
explicit-window fallback cannot produce contradictory targeted scope output.

.FUNCTION NAME
Get-TargetedCollectionScopeObject

.INPUTS
State hashtable.

.OUTPUTS
Ordered hashtable describing the targeted collection scope.
#>
function Get-TargetedCollectionScopeObject {
  param([hashtable]$State)

  $window = Get-CollectorEffectiveEventWindow -WindowHours $Hours
  $hasWindow = [bool]$window.HasExplicitWindow
  $windowStartText = if ($window.HasExplicitWindow) { $window.StartTime.ToString('o') } else { '' }
  $windowEndText = if ($window.HasExplicitWindow -and $window.EndTime) { $window.EndTime.ToString('o') } else { '' }
  $hasFocus = (-not [string]::IsNullOrWhiteSpace($FocusProcess)) -or (-not [string]::IsNullOrWhiteSpace($FocusPath)) -or (-not [string]::IsNullOrWhiteSpace($FocusIndicator)) -or (-not [string]::IsNullOrWhiteSpace($UserReport))
  $categories = @()
  if ($IncludeArtifactCategory) { $categories = @($IncludeArtifactCategory | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }) }

  return [ordered]@{
    targeted_mode_enabled = [bool]$Targeted
    target_profile = $TargetProfile
    has_explicit_time_window = $hasWindow
    window_start = $windowStartText
    window_end = $windowEndText
    requested_hours = $Hours
    included_artifact_categories = $categories
    focus_process = $FocusProcess
    focus_path = $FocusPath
    focus_indicator = $FocusIndicator
    focus_indicator_type = $FocusIndicatorType
    user_report = $UserReport
    has_focus_context = $hasFocus
    implementation_boundary = 'This major-version targeted collection feature currently narrows analyst guidance, collection scope intent, artifact prioritization, and recommended next actions. It does not yet rewrite every baseline collection helper into exact start-end timestamp filtering across all artifact families.'
  }
}

<#
.SYNOPSIS
Reads the synthetic oversized-artifact validation size.

.DESCRIPTION
Returns the requested synthetic oversized artifact size only when collector harness test
mode is explicitly enabled. This prevents stale response-action environment variables
from creating synthetic artifacts in normal collection runs.

.FUNCTION NAME
Get-ValidationSyntheticOversizeArtifactKB

.INPUTS
Process environment variables DCOIR_COLLECTOR_TEST_MODE and DCOIR_TEST_SYNTHETIC_OVERSIZE_ARTIFACT_KB.

.OUTPUTS
Integer requested synthetic artifact size in KB.
#>
function Get-ValidationSyntheticOversizeArtifactKB {
  if (-not (Test-DCOIRCollectorTestModeEnabled)) { return 0 }
  $raw = [Environment]::GetEnvironmentVariable('DCOIR_TEST_SYNTHETIC_OVERSIZE_ARTIFACT_KB', 'Process')
  if ([string]::IsNullOrWhiteSpace($raw)) { return 0 }
  $parsed = 0
  if ([int]::TryParse($raw, [ref]$parsed) -and $parsed -gt 0) { return $parsed }
  return 0
}

<#
.SYNOPSIS
Builds deterministic test padding for a text artifact.

.DESCRIPTION
Returns deterministic chunk-test padding only when collector harness test mode is
explicitly enabled. Normal collection runs ignore stale inherited padding variables.

.FUNCTION NAME
Get-TestTextPaddingFromEnvironment

.INPUTS
Environment variable name plus DCOIR_COLLECTOR_TEST_MODE.

.OUTPUTS
String containing deterministic padding or an empty string.
#>
function Get-TestTextPaddingFromEnvironment {
  param([string]$Name)
  if (-not (Test-DCOIRCollectorTestModeEnabled)) { return '' }
  $raw = [Environment]::GetEnvironmentVariable($Name, 'Process')
  if ([string]::IsNullOrWhiteSpace($raw)) { return '' }
  [int]$requestedKB = 0
  if (-not [int]::TryParse($raw, [ref]$requestedKB) -or $requestedKB -le 0) { return '' }

  $line = 'DCOIR_PRODUCTION_CHUNK_TEST_PAYLOAD|ABCDEFGHIJKLMNOPQRSTUVWXYZ|0123456789|line='
  $encoding = [System.Text.Encoding]::UTF8
  $targetBytes = $requestedKB * 1024
  $sb = New-Object System.Text.StringBuilder
  $index = 0
  $bytes = 0
  while ($bytes -lt $targetBytes) {
    $entry = ('{0}{1:000000}' -f $line, $index) + [Environment]::NewLine
    [void]$sb.Append($entry)
    $bytes += $encoding.GetByteCount($entry)
    $index += 1
  }
  return $sb.ToString()
}

<#
.SYNOPSIS
Formats normalized event-window target details for enrich reports.

.DESCRIPTION
Builds target-details text from the same normalized event-window object used by event
readers so invalid explicit windows do not leave rejected raw bounds in enrich action
metadata.

.FUNCTION NAME
Get-CollectorEventWindowTargetDetails

.INPUTS
LogName string, Hours integer, optional EventIds, and optional MaxEvents.

.OUTPUTS
String suitable for action target-details fields.
#>
function Get-CollectorEventWindowTargetDetails {
  param([string]$LogName,[int]$Hours,[int[]]$Ids,[int]$Take)
  $window = Get-CollectorEffectiveEventWindow -WindowHours $Hours
  $parts = New-Object System.Collections.ArrayList
  [void]$parts.Add(("LogName={0}" -f $LogName))
  [void]$parts.Add(("Hours={0}" -f $Hours))
  if ($window.HasExplicitWindow) {
    [void]$parts.Add(("WindowStart={0}" -f $window.StartTime.ToString('o')))
    if ($window.EndTime) { [void]$parts.Add(("WindowEnd={0}" -f $window.EndTime.ToString('o'))) }
  }
  if ($Ids -and @($Ids).Count -gt 0) { [void]$parts.Add(("EventIds={0}" -f ($Ids -join ','))) }
  if ($Take -gt 0) { [void]$parts.Add(("MaxEvents={0}" -f $Take)) }
  return ($parts -join '; ')
}
# DCOIR_REVIEW_AUDIT_BATCH_2G1_MARKER
