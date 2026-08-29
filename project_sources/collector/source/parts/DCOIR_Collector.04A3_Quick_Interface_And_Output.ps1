<#
.SYNOPSIS
DCOIR collector cleanup path and cleanup execution helpers.

.DESCRIPTION
Normalizes cleanup authority paths, records cleanup refusals, builds cleanup result
objects, and removes approved runtime/package artifacts during cleanup.

.FILE NAME
DCOIR_Collector.04A3_Quick_Interface_And_Output.ps1

.INPUTS
Collector runtime paths, package paths, cleanup roots, and persisted collector state.

.OUTPUTS
Cleanup result objects, refusal details, and cleanup side effects on approved paths.
#>

<#
.SYNOPSIS
Normalizes a cleanup path for comparison.

.DESCRIPTION
Returns a full path string for state-backed cleanup authority checks.

.FUNCTION NAME
Resolve-DCOIRCleanupFullPath

.INPUTS
Path string.

.OUTPUTS
Full path string or null for blank input.
#>
function Resolve-DCOIRCleanupFullPath {
  param([string]$Path)
  if ([string]::IsNullOrWhiteSpace($Path)) { return $null }
  try {
    return [System.IO.Path]::GetFullPath($Path)
  } catch {
    return $null
  }
}

<#
.SYNOPSIS
Normalizes a cleanup directory path for boundary comparisons.

.DESCRIPTION
Returns a full directory path without trailing separators so root-prefix checks cannot be
fooled by similarly prefixed sibling directories.

.FUNCTION NAME
Resolve-DCOIRCleanupDirectoryText

.INPUTS
Directory path string.

.OUTPUTS
Normalized directory path string or null for blank input.
#>
function Resolve-DCOIRCleanupDirectoryText {
  param([string]$Path)
  $fullPath = Resolve-DCOIRCleanupFullPath -Path $Path
  if ([string]::IsNullOrWhiteSpace($fullPath)) { return $null }
  $separators = [char[]]@([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
  return $fullPath.TrimEnd($separators)
}

<#
.SYNOPSIS
Compares cleanup paths after normalization.

.DESCRIPTION
Performs a case-insensitive exact comparison of normalized full paths.

.FUNCTION NAME
Test-DCOIRCleanupPathEquals

.INPUTS
Actual and expected path strings.

.OUTPUTS
Boolean.
#>
function Test-DCOIRCleanupPathEquals {
  param([string]$Actual,[string]$Expected)
  $actualPath = Resolve-DCOIRCleanupFullPath -Path $Actual
  $expectedPath = Resolve-DCOIRCleanupFullPath -Path $Expected
  if ([string]::IsNullOrWhiteSpace($actualPath) -or [string]::IsNullOrWhiteSpace($expectedPath)) { return $false }
  return [string]::Equals($actualPath, $expectedPath, [System.StringComparison]::OrdinalIgnoreCase)
}

<#
.SYNOPSIS
Checks whether a cleanup target is inside the selected OutRoot.

.DESCRIPTION
Normalizes both paths and accepts only the same directory or a true child path. Sibling
paths that share a string prefix with OutRoot are rejected.

.FUNCTION NAME
Test-DCOIRCleanupPathWithinRoot

.INPUTS
Root path and candidate path.

.OUTPUTS
Boolean.
#>
function Test-DCOIRCleanupPathWithinRoot {
  param([string]$Root,[string]$Path)
  $rootPath = Resolve-DCOIRCleanupDirectoryText -Path $Root
  $candidatePath = Resolve-DCOIRCleanupFullPath -Path $Path
  if ([string]::IsNullOrWhiteSpace($rootPath) -or [string]::IsNullOrWhiteSpace($candidatePath)) { return $false }
  $separators = [char[]]@([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
  $candidateDirectoryText = $candidatePath.TrimEnd($separators)
  if ([string]::Equals($candidateDirectoryText, $rootPath, [System.StringComparison]::OrdinalIgnoreCase)) { return $true }
  $rootPrefix = $rootPath + [System.IO.Path]::DirectorySeparatorChar
  return $candidatePath.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)
}

<#
.SYNOPSIS
Adds a refused cleanup target and reason.

.DESCRIPTION
Records path-authority validation failures without deleting state-provided paths.

.FUNCTION NAME
Add-DCOIRCleanupRefusal

.INPUTS
Refused target list, refusal reason list, target, and reason.

.OUTPUTS
No direct output. Mutates the supplied lists.
#>
function Add-DCOIRCleanupRefusal {
  param(
    [System.Collections.ArrayList]$Targets,
    [System.Collections.ArrayList]$Reasons,
    [string]$Target,
    [string]$Reason
  )
  $targetLabel = if ([string]::IsNullOrWhiteSpace($Target)) { '<missing>' } else { $Target }
  if (-not @($Targets).Contains($targetLabel)) { [void]$Targets.Add($targetLabel) }
  [void]$Reasons.Add(("{0} :: {1}" -f $targetLabel, $Reason))
}

<#
.SYNOPSIS
Builds the cleanup result object.

.DESCRIPTION
Creates a consistent cleanup result including optional refused target evidence.

.FUNCTION NAME
New-DCOIRCleanupResult

.INPUTS
Status and cleanup target lists.

.OUTPUTS
Cleanup result object.
#>
function New-DCOIRCleanupResult {
  param(
    [string]$Status,
    [System.Collections.ArrayList]$Targets,
    [System.Collections.ArrayList]$RemovedTargets,
    [System.Collections.ArrayList]$SkippedTargets,
    [System.Collections.ArrayList]$FailedTargets,
    [System.Collections.ArrayList]$RefusedTargets,
    [System.Collections.ArrayList]$RefusalReasons
  )

  return [pscustomobject][ordered]@{
    Status = $Status
    TargetCount = @($Targets).Count
    RemovedCount = @($RemovedTargets).Count
    SkippedCount = @($SkippedTargets).Count
    FailedCount = @($FailedTargets).Count
    RefusedCount = @($RefusedTargets).Count
    RemovedTargets = @($RemovedTargets)
    SkippedTargets = @($SkippedTargets)
    FailedTargets = @($FailedTargets)
    RefusedTargets = @($RefusedTargets)
    RefusalReasons = @($RefusalReasons)
  }
}

<#
.SYNOPSIS
Removes run/package artifacts during cleanup.

.DESCRIPTION
Treats state.json as evidence, not deletion authority. It recomputes the allowed run root,
state path, and package path from the selected OutRoot, selected cleanup RunId, and
current package name, then refuses state-backed cleanup if state-provided paths do not
match that bounded authority surface.

.FUNCTION NAME
Invoke-Cleanup

.INPUTS
Collector state object, selected OutRoot, current package name, and selected cleanup RunId.

.OUTPUTS
Cleanup result object with status, target, removed, skipped, failed, and refused counts.
#>
function Invoke-Cleanup {
  [CmdletBinding(SupportsShouldProcess=$true)]
  param(
    $StateObject,
    [Parameter(Mandatory=$true)][string]$Root,
    [Parameter(Mandatory=$true)][string]$CurrentPackageName,
    [string]$SelectedRunId
  )

  $targets = New-Object System.Collections.ArrayList
  $removedTargets = New-Object System.Collections.ArrayList
  $skippedTargets = New-Object System.Collections.ArrayList
  $failedTargets = New-Object System.Collections.ArrayList
  $refusedTargets = New-Object System.Collections.ArrayList
  $refusalReasons = New-Object System.Collections.ArrayList

  $resolvedRoot = Resolve-DCOIRCleanupFullPath -Path $Root
  if ([string]::IsNullOrWhiteSpace($resolvedRoot)) {
    Add-DCOIRCleanupRefusal -Targets $refusedTargets -Reasons $refusalReasons -Target $Root -Reason 'Selected OutRoot is blank or invalid.'
  }

  $stateRunId = if ($StateObject) { [string]$StateObject.RunId } else { $null }
  $selectedRunIdText = [string]$SelectedRunId
  $authorityRunId = if ([string]::IsNullOrWhiteSpace($selectedRunIdText)) { $stateRunId } else { $selectedRunIdText }
  $safeRunId = $null
  $safeStateRunId = $null
  try {
    $safeRunId = Resolve-DCOIRRunId -CurrentRunId $authorityRunId -RejectBlank
  } catch {
    Add-DCOIRCleanupRefusal -Targets $refusedTargets -Reasons $refusalReasons -Target $authorityRunId -Reason ("Selected cleanup RunId failed validation: {0}" -f $_.Exception.Message)
  }
  try {
    $safeStateRunId = Resolve-DCOIRRunId -CurrentRunId $stateRunId -RejectBlank
  } catch {
    Add-DCOIRCleanupRefusal -Targets $refusedTargets -Reasons $refusalReasons -Target $stateRunId -Reason ("State RunId failed validation: {0}" -f $_.Exception.Message)
  }
  if (
    -not [string]::IsNullOrWhiteSpace($selectedRunIdText) -and
    -not [string]::IsNullOrWhiteSpace($safeRunId) -and
    -not [string]::IsNullOrWhiteSpace($safeStateRunId) -and
    -not [string]::Equals($safeStateRunId, $safeRunId, [System.StringComparison]::OrdinalIgnoreCase)
  ) {
    Add-DCOIRCleanupRefusal -Targets $refusedTargets -Reasons $refusalReasons -Target $stateRunId -Reason ("State RunId does not match selected RunId {0}." -f $safeRunId)
  }

  $expectedRunRoot = $null
  $expectedStatePath = $null
  $expectedPackagePath = $null
  if ($resolvedRoot -and $safeRunId) {
    $expectedRunRoot = Resolve-DCOIRCleanupFullPath -Path (Get-RunRoot -Root $resolvedRoot -CurrentRunId $safeRunId)
    $expectedStatePath = Resolve-DCOIRCleanupFullPath -Path (Join-Path $expectedRunRoot 'state.json')
  }
  if ($resolvedRoot -and -not [string]::IsNullOrWhiteSpace($CurrentPackageName)) {
    $expectedPackagePath = Resolve-DCOIRCleanupFullPath -Path (Join-Path $resolvedRoot $CurrentPackageName)
  }

  $stateRunRoot = if ($StateObject) { [string]$StateObject.RunRoot } else { $null }
  $statePath = if ($StateObject -and ($StateObject.PSObject.Properties.Name -contains 'StatePath')) { [string]$StateObject.StatePath } else { $null }
  $statePackagePath = if ($StateObject) { [string]$StateObject.PackagePath } else { $null }

  if (-not (Test-DCOIRCleanupPathWithinRoot -Root $resolvedRoot -Path $stateRunRoot)) {
    Add-DCOIRCleanupRefusal -Targets $refusedTargets -Reasons $refusalReasons -Target $stateRunRoot -Reason 'State RunRoot is outside the selected OutRoot, blank, or invalid.'
  }
  if (-not (Test-DCOIRCleanupPathEquals -Actual $stateRunRoot -Expected $expectedRunRoot)) {
    Add-DCOIRCleanupRefusal -Targets $refusedTargets -Reasons $refusalReasons -Target $stateRunRoot -Reason ("State RunRoot does not match expected run root {0}." -f $expectedRunRoot)
  }
  if ($expectedRunRoot -and -not (Test-DCOIRRunDirectoryName -Name ([System.IO.Path]::GetFileName($expectedRunRoot)))) {
    Add-DCOIRCleanupRefusal -Targets $refusedTargets -Reasons $refusalReasons -Target $expectedRunRoot -Reason 'Expected run root name is not a collector run directory name.'
  }

  if (-not (Test-DCOIRCleanupPathWithinRoot -Root $resolvedRoot -Path $statePath)) {
    Add-DCOIRCleanupRefusal -Targets $refusedTargets -Reasons $refusalReasons -Target $statePath -Reason 'StatePath is outside the selected OutRoot, blank, or invalid.'
  }
  if (-not (Test-DCOIRCleanupPathEquals -Actual $statePath -Expected $expectedStatePath)) {
    Add-DCOIRCleanupRefusal -Targets $refusedTargets -Reasons $refusalReasons -Target $statePath -Reason ("StatePath does not match expected state path {0}." -f $expectedStatePath)
  }

  if (-not (Test-DCOIRCleanupPathWithinRoot -Root $resolvedRoot -Path $statePackagePath)) {
    Add-DCOIRCleanupRefusal -Targets $refusedTargets -Reasons $refusalReasons -Target $statePackagePath -Reason 'PackagePath is outside the selected OutRoot, blank, or invalid.'
  }
  if (-not (Test-DCOIRCleanupPathEquals -Actual $statePackagePath -Expected $expectedPackagePath)) {
    Add-DCOIRCleanupRefusal -Targets $refusedTargets -Reasons $refusalReasons -Target $statePackagePath -Reason ("PackagePath does not match expected package path {0}." -f $expectedPackagePath)
  }

  if (@($refusedTargets).Count -gt 0) {
    return (New-DCOIRCleanupResult -Status 'REFUSED' -Targets $targets -RemovedTargets $removedTargets -SkippedTargets $skippedTargets -FailedTargets $failedTargets -RefusedTargets $refusedTargets -RefusalReasons $refusalReasons)
  }

  foreach ($candidate in @($expectedPackagePath,$expectedRunRoot)) {
    if ([string]::IsNullOrWhiteSpace($candidate)) { continue }
    if (-not (Test-Path -LiteralPath $candidate)) { continue }
    if (-not @($targets).Contains($candidate)) { [void]$targets.Add($candidate) }
  }

  foreach ($target in @($targets)) {
    if ($PSCmdlet.ShouldProcess($target, 'Remove collector cleanup target')) {
      Remove-Item -LiteralPath $target -Recurse -Force -ErrorAction SilentlyContinue
      if (Test-Path -LiteralPath $target) {
        [void]$failedTargets.Add($target)
      } else {
        [void]$removedTargets.Add($target)
      }
    } else {
      [void]$skippedTargets.Add($target)
    }
  }

  $status = 'COMPLETE'
  if (@($targets).Count -eq 0) {
    $status = 'NO_TARGET_FOUND'
  } elseif (@($removedTargets).Count -eq 0 -and @($skippedTargets).Count -gt 0 -and @($failedTargets).Count -eq 0) {
    $status = 'SKIPPED'
  } elseif (@($skippedTargets).Count -gt 0 -or @($failedTargets).Count -gt 0) {
    $status = 'PARTIAL'
  }

  return (New-DCOIRCleanupResult -Status $status -Targets $targets -RemovedTargets $removedTargets -SkippedTargets $skippedTargets -FailedTargets $failedTargets -RefusedTargets $refusedTargets -RefusalReasons $refusalReasons)
}
