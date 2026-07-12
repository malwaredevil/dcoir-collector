<#
.SYNOPSIS
DCOIR collector JSON serialization and process-output helpers.

.DESCRIPTION
Provides shared JSON serialization guardrails, JSON depth/truncation detection, and
combined process-output text shaping helpers.

.FILE NAME
DCOIR_Collector.01B1_Json_State_And_Array_Utilities.ps1

.INPUTS
JSON-serializable objects and process-capture result objects.

.OUTPUTS
Serialized JSON text, JSON path sets, and formatted process-output text.
#>

<#
.SYNOPSIS
Records every exact ellipsis string path inside one object graph.

.DESCRIPTION
Walks dictionaries, arrays, and PSObject properties to find exact string values equal to
"...". The resulting path set is used to distinguish legitimate ellipsis strings already
present in source objects from ConvertTo-Json depth truncation sentinels introduced during
serialization.

.FUNCTION NAME
Add-CollectorJsonEllipsisPaths

.INPUTS
InputObject, current path, destination path set, max traversal depth, and current depth.

.OUTPUTS
No direct output. Updates PathSet as a side effect.
#>
function Add-CollectorJsonEllipsisPaths {
  param(
    [object]$InputObject,
    [string]$Path,
    [hashtable]$PathSet,
    [int]$MaxDepth,
    [int]$CurrentDepth = 0
  )

  if ($null -eq $InputObject) { return }
  if ([string]::IsNullOrWhiteSpace($Path)) { $Path = '$' }
  if ($InputObject -is [string]) {
    if ([string]$InputObject -eq '...') { $PathSet[$Path] = $true }
    return
  }
  if ($CurrentDepth -ge $MaxDepth) { return }

  if ($InputObject -is [System.Collections.IDictionary]) {
    foreach ($key in @($InputObject.Keys)) {
      $childPath = ('{0}.{1}' -f $Path, [string]$key)
      Add-CollectorJsonEllipsisPaths -InputObject $InputObject[$key] -Path $childPath -PathSet $PathSet -MaxDepth $MaxDepth -CurrentDepth ($CurrentDepth + 1)
    }
    return
  }

  if (($InputObject -is [System.Collections.IEnumerable]) -and -not ($InputObject -is [string])) {
    $index = 0
    foreach ($item in @($InputObject)) {
      $childPath = ('{0}[{1}]' -f $Path, $index)
      Add-CollectorJsonEllipsisPaths -InputObject $item -Path $childPath -PathSet $PathSet -MaxDepth $MaxDepth -CurrentDepth ($CurrentDepth + 1)
      $index += 1
    }
    return
  }

  $psProps = @()
  try { $psProps = @($InputObject.PSObject.Properties) } catch { $psProps = @() }
  foreach ($prop in $psProps) {
    $childPath = ('{0}.{1}' -f $Path, [string]$prop.Name)
    Add-CollectorJsonEllipsisPaths -InputObject $prop.Value -Path $childPath -PathSet $PathSet -MaxDepth $MaxDepth -CurrentDepth ($CurrentDepth + 1)
  }
}

<#
.SYNOPSIS
Returns exact ellipsis string paths from one object graph.

.DESCRIPTION
Creates a path set for exact "..." strings found in an object graph. This supports
post-serialization truncation detection without flagging legitimate ellipsis values.

.FUNCTION NAME
Get-CollectorJsonEllipsisPathSet

.INPUTS
InputObject and optional max traversal depth.

.OUTPUTS
Hashtable keyed by path.
#>
function Get-CollectorJsonEllipsisPathSet {
  param([object]$InputObject,[int]$MaxDepth = 25)
  $paths = @{}
  Add-CollectorJsonEllipsisPaths -InputObject $InputObject -Path '$' -PathSet $paths -MaxDepth $MaxDepth
  return $paths
}

<#
.SYNOPSIS
Records object paths that exceed one ConvertTo-Json depth policy.

.DESCRIPTION
Walks dictionaries, arrays, and PSObject properties before serialization. PowerShell does
not consistently emit an exact "..." sentinel when ConvertTo-Json exceeds depth, so this
preflight identifies non-scalar objects that would be serialized at or beyond the policy
depth and records their paths as truncation risks.

.FUNCTION NAME
Add-CollectorJsonDepthRiskPaths

.INPUTS
InputObject, current path, destination path set, max JSON depth, and current depth.

.OUTPUTS
No direct output. Updates PathSet as a side effect.
#>
function Add-CollectorJsonDepthRiskPaths {
  param(
    [object]$InputObject,
    [string]$Path,
    [hashtable]$PathSet,
    [int]$MaxDepth,
    [int]$CurrentDepth = 0
  )

  if ($null -eq $InputObject) { return }
  if ([string]::IsNullOrWhiteSpace($Path)) { $Path = '$' }
  if (($InputObject -is [string]) -or ($InputObject -is [System.ValueType])) { return }
  if ($CurrentDepth -ge $MaxDepth) {
    $PathSet[$Path] = $true
    return
  }

  if ($InputObject -is [System.Collections.IDictionary]) {
    foreach ($key in @($InputObject.Keys)) {
      $childPath = ('{0}.{1}' -f $Path, [string]$key)
      Add-CollectorJsonDepthRiskPaths -InputObject $InputObject[$key] -Path $childPath -PathSet $PathSet -MaxDepth $MaxDepth -CurrentDepth ($CurrentDepth + 1)
    }
    return
  }

  if (($InputObject -is [System.Collections.IEnumerable]) -and -not ($InputObject -is [string])) {
    $index = 0
    foreach ($item in @($InputObject)) {
      $childPath = ('{0}[{1}]' -f $Path, $index)
      Add-CollectorJsonDepthRiskPaths -InputObject $item -Path $childPath -PathSet $PathSet -MaxDepth $MaxDepth -CurrentDepth ($CurrentDepth + 1)
      $index += 1
    }
    return
  }

  $psProps = @()
  try { $psProps = @($InputObject.PSObject.Properties) } catch { $psProps = @() }
  foreach ($prop in $psProps) {
    $childPath = ('{0}.{1}' -f $Path, [string]$prop.Name)
    Add-CollectorJsonDepthRiskPaths -InputObject $prop.Value -Path $childPath -PathSet $PathSet -MaxDepth $MaxDepth -CurrentDepth ($CurrentDepth + 1)
  }
}

<#
.SYNOPSIS
Returns object paths that exceed one ConvertTo-Json depth policy.

.DESCRIPTION
Creates a path set for non-scalar source objects that would be serialized at or beyond the
configured JSON depth.

.FUNCTION NAME
Get-CollectorJsonDepthRiskPathSet

.INPUTS
InputObject and max JSON depth.

.OUTPUTS
Hashtable keyed by path.
#>
function Get-CollectorJsonDepthRiskPathSet {
  param([object]$InputObject,[int]$MaxDepth = 20)
  $paths = @{}
  Add-CollectorJsonDepthRiskPaths -InputObject $InputObject -Path '$' -PathSet $paths -MaxDepth $MaxDepth
  return $paths
}

<#
.SYNOPSIS
Serializes one collector object to JSON with truncation detection.

.DESCRIPTION
Uses one collector-wide JSON depth policy, checks the source graph for depth-risk paths,
parses the emitted JSON back, and compares exact ellipsis-string paths against the
original object. If source depth exceeds policy or ConvertTo-Json introduced an ellipsis
sentinel at a path that was not already an exact ellipsis string, the helper records an
operator-visible collector error and can throw for truth surfaces.

.FUNCTION NAME
Convert-ToCollectorJsonText

.INPUTS
InputObject, optional depth, compression flag, newline flag, label, and truncation policy.

.OUTPUTS
JSON string, optionally newline-terminated.
#>
function Convert-ToCollectorJsonText {
  param(
    [object]$InputObject,
    [int]$Depth = 20,
    [switch]$Compress,
    [switch]$AppendNewline,
    [string]$Label = 'collector JSON',
    [switch]$ThrowOnTruncation
  )

  $jsonArgs = @{ Depth = $Depth; ErrorAction = 'Stop' }
  if ($Compress) { $jsonArgs['Compress'] = $true }
  $sourceDepthRisks = Get-CollectorJsonDepthRiskPathSet -InputObject $InputObject -MaxDepth $Depth
  if (@($sourceDepthRisks.Keys).Count -gt 0) {
    $depthRiskPaths = @($sourceDepthRisks.Keys | Sort-Object)
    $message = ('JSON serialization for [{0}] exceeds configured depth {1}; non-scalar source object paths at risk: {2}' -f $Label, $Depth, ($depthRiskPaths -join ', '))
    Add-CollectorError $message
    if ($ThrowOnTruncation) { throw $message }
  }
  $json = $InputObject | ConvertTo-Json @jsonArgs

  try {
    $parsed = $json | ConvertFrom-Json -ErrorAction Stop
    $emittedEllipsis = Get-CollectorJsonEllipsisPathSet -InputObject $parsed -MaxDepth ([Math]::Max($Depth + 5, 25))
    if (@($emittedEllipsis.Keys).Count -gt 0) {
      $sourceEllipsis = Get-CollectorJsonEllipsisPathSet -InputObject $InputObject -MaxDepth ([Math]::Max($Depth + 5, 25))
      $truncatedPaths = @($emittedEllipsis.Keys | Where-Object { -not $sourceEllipsis.ContainsKey($_) } | Sort-Object)
      if (@($truncatedPaths).Count -gt 0) {
        $message = ('JSON serialization for [{0}] appears truncated at depth {1}; ConvertTo-Json emitted ellipsis sentinel at: {2}' -f $Label, $Depth, ($truncatedPaths -join ', '))
        Add-CollectorError $message
        if ($ThrowOnTruncation) { throw $message }
      }
    }
  } catch {
    if ($ThrowOnTruncation) { throw }
  }

  if ($AppendNewline) { return ($json + [Environment]::NewLine) }
  return $json
}

<#
.SYNOPSIS
Formats one process-capture object into durable text.

.DESCRIPTION
Builds the combined command, exit-code, optional status/timeout details, stdout, and
stderr text block used in many collector artifacts.

.FUNCTION NAME
Get-CombinedProcessOutput

.INPUTS
Result object returned by Invoke-ProcessCapture or Invoke-CmdCapture.

.OUTPUTS
String containing the combined process output text.
#>
function Get-CombinedProcessOutput {
  param($Result)
  $lines = New-Object System.Collections.ArrayList
  [void]$lines.Add(("COMMAND={0}" -f $Result.Command))
  [void]$lines.Add(("EXIT_CODE={0}" -f $Result.ExitCode))
  $statusProperty = $Result.PSObject.Properties['Status']
  if ($statusProperty) {
    [void]$lines.Add(("STATUS={0}" -f $statusProperty.Value))
  }
  $timedOutProperty = $Result.PSObject.Properties['TimedOut']
  if ($timedOutProperty) {
    [void]$lines.Add(("TIMED_OUT={0}" -f $timedOutProperty.Value))
  }
  $timeoutSecondsProperty = $Result.PSObject.Properties['TimeoutSeconds']
  if ($timeoutSecondsProperty) {
    [void]$lines.Add(("TIMEOUT_SECONDS={0}" -f $timeoutSecondsProperty.Value))
  }
  [void]$lines.Add("")
  [void]$lines.Add("STDOUT:")
  [void]$lines.Add(($Result.StdOut))
  [void]$lines.Add("")
  [void]$lines.Add("STDERR:")
  [void]$lines.Add(($Result.StdErr))
  return ($lines -join [Environment]::NewLine)
}
