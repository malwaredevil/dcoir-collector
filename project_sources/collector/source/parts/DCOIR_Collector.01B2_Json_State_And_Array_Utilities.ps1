<#
.SYNOPSIS
DCOIR collector run-state, package-name, cleanup, and array helpers.

.DESCRIPTION
Provides run identifier and package-name validation, state-path helpers, state
persistence, no-state cleanup, object-to-hashtable conversion, and ArrayList
normalization helpers.

.FILE NAME
DCOIR_Collector.01B2_Json_State_And_Array_Utilities.ps1

.INPUTS
Collector state objects, filesystem paths, RunId values, PackageName values, and
generic object arrays.

.OUTPUTS
Validated path/name values, state paths, normalized hashtables, ArrayList instances,
and cleanup results.
#>

<#
.SYNOPSIS
Creates a new collector run identifier.

.DESCRIPTION
Returns the current local timestamp in the standard DCOIR run-id format.

.FUNCTION NAME
Get-NewRunId

.INPUTS
No direct parameters.

.OUTPUTS
String run identifier.
#>
function Get-NewRunId {
  return (Get-Date -Format "yyyyMMdd_HHmmss")
}

<#
.SYNOPSIS
Checks whether one run ID is safe to use as a path leaf.

.DESCRIPTION
Requires a nonblank filename-leaf identifier and rejects path separators, rooted
path syntax, parent traversal, oversized values, and surrounding whitespace.
Single dots are allowed inside custom IDs to preserve the existing custom run-root
predicate shape.

.FUNCTION NAME
Test-DCOIRRunIdLeaf

.INPUTS
CurrentRunId string.

.OUTPUTS
Boolean indicating whether the run ID is safe.
#>
function Test-DCOIRRunIdLeaf {
  param([string]$CurrentRunId)

  if ([string]::IsNullOrWhiteSpace($CurrentRunId)) { return $false }
  if ($CurrentRunId.Length -gt 128) { return $false }
  if ($CurrentRunId.Trim() -ne $CurrentRunId) { return $false }
  if ($CurrentRunId -in @(".", "..")) { return $false }
  if ($CurrentRunId.EndsWith(".")) { return $false }
  if ($CurrentRunId.Contains("..")) { return $false }
  if ([regex]::IsMatch($CurrentRunId, '[\\/]')) { return $false }
  if ([System.IO.Path]::IsPathRooted($CurrentRunId)) { return $false }

  return [regex]::IsMatch($CurrentRunId, '^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$')
}

<#
.SYNOPSIS
Returns a validated collector run ID.

.DESCRIPTION
Generates the standard timestamp run ID when requested for omitted collect-mode
input. Explicit blank values can be rejected by callers that know the parameter
was supplied.

.FUNCTION NAME
Resolve-DCOIRRunId

.INPUTS
CurrentRunId string and optional switches controlling blank handling.

.OUTPUTS
Validated run ID string, generated run ID string, or null when blank is allowed.
#>
function Resolve-DCOIRRunId {
  param(
    [string]$CurrentRunId,
    [switch]$GenerateIfBlank,
    [switch]$RejectBlank
  )

  if ([string]::IsNullOrWhiteSpace($CurrentRunId)) {
    if ($RejectBlank) {
      throw "Invalid RunId: value must not be blank."
    }
    if ($GenerateIfBlank) {
      return (Get-NewRunId)
    }
    return $null
  }

  if (-not (Test-DCOIRRunIdLeaf -CurrentRunId $CurrentRunId)) {
    throw "Invalid RunId: value must be a filename-leaf identifier of 1-128 characters using letters, numbers, dot, underscore, or dash, with no rooted path, separator, or parent traversal syntax."
  }

  return $CurrentRunId
}

<#
.SYNOPSIS
Checks whether one package name is safe to use as a ZIP filename leaf.

.DESCRIPTION
Allows custom collector package ZIP filenames while rejecting empty values,
path-shaped values, rooted paths, parent traversal, invalid filename characters,
reserved Windows device names, and non-ZIP extensions.

.FUNCTION NAME
Test-DCOIRPackageNameLeaf

.INPUTS
CurrentPackageName string.

.OUTPUTS
Boolean indicating whether the package name is safe.
#>
function Test-DCOIRPackageNameLeaf {
  param([string]$CurrentPackageName)

  if ([string]::IsNullOrWhiteSpace($CurrentPackageName)) { return $false }
  if ($CurrentPackageName.Length -gt 128) { return $false }
  if ($CurrentPackageName.Trim() -ne $CurrentPackageName) { return $false }
  if ($CurrentPackageName -in @(".", "..")) { return $false }
  if ($CurrentPackageName.Contains("..")) { return $false }
  if ([regex]::IsMatch($CurrentPackageName, '[<>:"/\\|?*\x00-\x1F]')) { return $false }
  if ([System.IO.Path]::IsPathRooted($CurrentPackageName)) { return $false }
  if ([System.IO.Path]::GetFileName($CurrentPackageName) -ne $CurrentPackageName) { return $false }
  if ([System.IO.Path]::GetExtension($CurrentPackageName) -ine ".zip") { return $false }

  $baseName = [System.IO.Path]::GetFileNameWithoutExtension($CurrentPackageName)
  if ([string]::IsNullOrWhiteSpace($baseName)) { return $false }
  if ($baseName -match '^(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$') { return $false }

  return $true
}

<#
.SYNOPSIS
Returns a validated collector package filename.

.DESCRIPTION
Normalizes PackageName through the shared package-name leaf validator before the
collector can use it to check, move, purge, or delete package artifacts.

.FUNCTION NAME
Resolve-DCOIRPackageName

.INPUTS
CurrentPackageName string.

.OUTPUTS
Validated package filename string.
#>
function Resolve-DCOIRPackageName {
  param([string]$CurrentPackageName)

  if (-not (Test-DCOIRPackageNameLeaf -CurrentPackageName $CurrentPackageName)) {
    throw "Invalid PackageName: value must be a nonblank .zip filename leaf with no rooted path, separator, parent traversal, invalid filename characters, or reserved Windows device name."
  }

  return $CurrentPackageName
}

<#
.SYNOPSIS
Builds the run-root path for one run identifier.

.DESCRIPTION
Combines the root path, hostname, and run identifier into the standard DCOIR run-root
folder name.

.FUNCTION NAME
Get-RunRoot

.INPUTS
Root string and CurrentRunId string.

.OUTPUTS
String run-root path.
#>
function Get-RunRoot {
  param([string]$Root,[string]$CurrentRunId)
  return (Join-Path $Root ("DCOIR_{0}_{1}" -f $env:COMPUTERNAME, $CurrentRunId))
}


<#
.SYNOPSIS
Builds the state-file path for one run.

.DESCRIPTION
Returns the state.json path inside the resolved run-root directory.

.FUNCTION NAME
Get-StatePath

.INPUTS
Root string and CurrentRunId string.

.OUTPUTS
String state-file path.
#>
function Get-StatePath {
  param([string]$Root,[string]$CurrentRunId)
  return (Join-Path (Get-RunRoot -Root $Root -CurrentRunId $CurrentRunId) "state.json")
}

<#
.SYNOPSIS
Saves the collector state to disk.

.DESCRIPTION
Serializes the supplied state hashtable to JSON and writes it to the state path stored
inside the state object.

.FUNCTION NAME
Save-State

.INPUTS
Mandatory State hashtable.

.OUTPUTS
State path string when state.json is written, or null when WhatIf/confirmation skips the write.
#>
function Save-State {
  [CmdletBinding(SupportsShouldProcess=$true, ConfirmImpact='Medium')]
  param([Parameter(Mandatory=$true)][hashtable]$State)
  $json = Convert-ToCollectorJsonText -InputObject $State -Label 'state.json' -ThrowOnTruncation
  if ($PSCmdlet.ShouldProcess($State.StatePath, 'Write collector state')) {
    Set-Content -Path $State.StatePath -Value $json -Encoding UTF8 -ErrorAction Stop
    return $State.StatePath
  }
  return $null
}

<#
.SYNOPSIS
Removes a bounded no-state collector run directory.

.DESCRIPTION
Used by cleanup mode after early collect failures where a run directory was created before
state.json was saved. Deletes only the expected or latest DCOIR_* run directory under the
selected OutRoot and the configured package file under that same root.

.FUNCTION NAME
Invoke-NoStateCleanup

.INPUTS
Root string, optional CurrentRunId, and current package name.

.OUTPUTS
Hashtable describing cleanup status and targets.
#>
function Invoke-NoStateCleanup {
  [CmdletBinding(SupportsShouldProcess=$true)]
  param([string]$Root,[string]$CurrentRunId,[string]$CurrentPackageName)

  $targets = New-Object System.Collections.ArrayList
  $runDir = Find-LatestDCOIRRunDirectory -Root $Root -CurrentRunId $CurrentRunId
  if ($runDir -and (Test-DCOIRNoStateCleanupCandidate -Directory $runDir)) {
    [void]$targets.Add($runDir.FullName)
  }

  $pkg = Join-Path $Root $CurrentPackageName
  if (Test-Path -LiteralPath $pkg) { [void]$targets.Add($pkg) }

  $removed = New-Object System.Collections.ArrayList
  $failed = New-Object System.Collections.ArrayList
  $skipped = New-Object System.Collections.ArrayList
  foreach ($target in @($targets)) {
    try {
      if ($PSCmdlet.ShouldProcess($target, 'Remove no-state collector cleanup target')) {
        Remove-Item -LiteralPath $target -Recurse -Force -ErrorAction Stop
        [void]$removed.Add($target)
      } else {
        [void]$skipped.Add($target)
      }
    } catch {
      [void]$failed.Add(("{0} :: {1}" -f $target, $_.Exception.Message))
    }
  }

  $status = if (@($targets).Count -eq 0) {
    'NO_TARGET_FOUND'
  } elseif (@($skipped).Count -gt 0 -and @($removed).Count -eq 0 -and @($failed).Count -eq 0) {
    'SKIPPED'
  } elseif (@($skipped).Count -gt 0 -or @($failed).Count -gt 0) {
    'PARTIAL'
  } else {
    'MISSING_STATE_ORPHAN_CLEANED'
  }

  return @{
    Status = $status
    RunRoot = if ($runDir) { $runDir.FullName } else { $null }
    RemovedTargets = @($removed)
    FailedTargets = @($failed)
    SkippedTargets = @($skipped)
    TargetCount = @($targets).Count
    RemovedCount = @($removed).Count
    SkippedCount = @($skipped).Count
    FailedCount = @($failed).Count
  }
}

<#
.SYNOPSIS
Recursively converts a deserialized state object into plain hashtables and arrays.

.DESCRIPTION
Normalizes dictionaries, enumerable collections, and PSObject properties into plain
PowerShell hashtables and arrays so saved state can be reused consistently. Stops with a
descriptive error when the object graph exceeds the configured depth limit.

.FUNCTION NAME
Convert-StateObjectToHashtable

.INPUTS
InputObject to normalize, optional maximum depth, current recursion depth, and current
object path.

.OUTPUTS
Hashtable, array, scalar, or null matching the normalized input structure.
#>
function Convert-StateObjectToHashtable {
  param(
    [object]$InputObject,
    [int]$Depth = 20,
    [int]$CurrentDepth = 0,
    [string]$Path = '$'
  )

  if ($null -eq $InputObject) { return $null }
  if ([string]::IsNullOrWhiteSpace($Path)) { $Path = '$' }
  if (($InputObject -is [string]) -or ($InputObject -is [System.ValueType])) { return $InputObject }
  if ($CurrentDepth -ge $Depth) {
    throw ('Convert-StateObjectToHashtable exceeded configured depth {0} at path {1}.' -f $Depth, $Path)
  }

  if ($InputObject -is [System.Collections.IDictionary]) {
    $hash = @{}
    foreach ($key in @($InputObject.Keys)) {
      $childPath = ('{0}.{1}' -f $Path, [string]$key)
      $hash[$key] = Convert-StateObjectToHashtable -InputObject $InputObject[$key] -Depth $Depth -CurrentDepth ($CurrentDepth + 1) -Path $childPath
    }
    return $hash
  }

  if (($InputObject -is [System.Collections.IEnumerable]) -and -not ($InputObject -is [string])) {
    $list = @()
    $index = 0
    foreach ($item in @($InputObject)) {
      $childPath = ('{0}[{1}]' -f $Path, $index)
      $list += ,(Convert-StateObjectToHashtable -InputObject $item -Depth $Depth -CurrentDepth ($CurrentDepth + 1) -Path $childPath)
      $index += 1
    }
    return ,$list
  }

  $psProps = @()
  try { $psProps = @($InputObject.PSObject.Properties) } catch { $psProps = @() }
  if (@($psProps).Count -gt 0 -and -not ($InputObject -is [string])) {
    $hash = @{}
    foreach ($prop in $psProps) {
      $childPath = ('{0}.{1}' -f $Path, [string]$prop.Name)
      $hash[$prop.Name] = Convert-StateObjectToHashtable -InputObject $prop.Value -Depth $Depth -CurrentDepth ($CurrentDepth + 1) -Path $childPath
    }
    return $hash
  }

  return $InputObject
}

<#
.SYNOPSIS
Normalizes one input into an ArrayList.

.DESCRIPTION
Returns an empty ArrayList for null, expands enumerable non-string/non-dictionary input
into an ArrayList, or wraps a single scalar object into an ArrayList.

.FUNCTION NAME
Convert-ToArrayList

.INPUTS
InputObject to normalize.

.OUTPUTS
System.Collections.ArrayList.
#>
function Convert-ToArrayList {
  param([object]$InputObject)

  $list = New-Object System.Collections.ArrayList

  if ($null -eq $InputObject) {
    return $list
  }

  if (($InputObject -is [System.Collections.IEnumerable]) -and -not ($InputObject -is [string]) -and -not ($InputObject -is [System.Collections.IDictionary])) {
    foreach ($item in $InputObject) {
      [void]$list.Add($item)
    }
    return $list
  }

  [void]$list.Add($InputObject)
  return $list
}
