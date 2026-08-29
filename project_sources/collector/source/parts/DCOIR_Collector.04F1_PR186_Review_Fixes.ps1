<#
.SYNOPSIS
DCOIR collector PR #186 run-root and command review-fix helpers.

.DESCRIPTION
Applies narrowly scoped helper refinements for PR #186 review findings before the main
collector entrypoint runs. Keeps custom run-id discovery compatible with collector-created
run roots, preserves exact state lookup for custom RunId runs, and keeps synthetic
validation padding gated behind an explicit harness test-mode flag.

.FILE NAME
DCOIR_Collector.04F1_PR186_Review_Fixes.ps1

.INPUTS
Current collector globals, process environment variables, run-root directory names, and
state hashtables.

.OUTPUTS
Maintained run-root, state, test-mode, and command helper functions used by the compiled collector runtime.
#>

<#
.SYNOPSIS
Checks whether a directory name matches a collector run-root for the current host.

.DESCRIPTION
Accepts timestamp run IDs and supported custom run IDs produced by Get-RunRoot while
remaining bounded to the current host prefix and a conservative run-id character set. Use
this broad predicate for exact run lookup only; bulk deletion uses the stricter purge
predicate below.

.FUNCTION NAME
Test-DCOIRRunDirectoryName

.INPUTS
Directory name string.

.OUTPUTS
Boolean.
#>
function Test-DCOIRRunDirectoryName {
  param([string]$Name)
  if ([string]::IsNullOrWhiteSpace($Name)) { return $false }
  $hostPrefix = "DCOIR_{0}_" -f [string]$env:COMPUTERNAME
  if (-not $Name.StartsWith($hostPrefix, [System.StringComparison]::OrdinalIgnoreCase)) { return $false }
  $runIdPart = $Name.Substring($hostPrefix.Length)
  if ([string]::IsNullOrWhiteSpace($runIdPart)) { return $false }
  return [regex]::IsMatch($runIdPart, '^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$')
}

<#
.SYNOPSIS
Checks whether a directory name is safe for bulk prior-run purge.

.DESCRIPTION
Allows only timestamp-style collector run-root names for automatic bulk purge. Custom
RunId directories are resolved by exact RunId lookup or no-state cleanup only after
collector-created structure is present.

.FUNCTION NAME
Test-DCOIRBulkPurgeRunDirectoryName

.INPUTS
Directory name string.

.OUTPUTS
Boolean.
#>
function Test-DCOIRBulkPurgeRunDirectoryName {
  param([string]$Name)
  if ([string]::IsNullOrWhiteSpace($Name)) { return $false }
  $hostPattern = [regex]::Escape([string]$env:COMPUTERNAME)
  return [regex]::IsMatch($Name, ("^DCOIR_{0}_\d{{8}}_\d{{6}}$" -f $hostPattern))
}

<#
.SYNOPSIS
Checks whether a no-state directory is safe for fallback cleanup.

.DESCRIPTION
Allows supported custom run-root names only when collector-created child structure is
present and no state.json exists, so exact custom RunId cleanup can remove collector-owned
early-failure directories without broadening bulk purge.

.FUNCTION NAME
Test-DCOIRNoStateCleanupCandidate

.INPUTS
DirectoryInfo object.

.OUTPUTS
Boolean.
#>
function Test-DCOIRNoStateCleanupCandidate {
  param([object]$Directory)
  if (-not $Directory) { return $false }
  if (-not (Test-DCOIRRunDirectoryName -Name $Directory.Name)) { return $false }
  if (Test-Path -LiteralPath (Join-Path $Directory.FullName 'state.json')) { return $false }
  $requiredChildren = @('tools','reports','final_artifacts','logs','bundles')
  foreach ($child in $requiredChildren) {
    if (-not (Test-Path -LiteralPath (Join-Path $Directory.FullName $child))) { return $false }
  }
  return $true
}

<#
.SYNOPSIS
Finds the newest collector run directory under a root without broad custom deletion.

.DESCRIPTION
Preserves exact custom RunId lookup while keeping blank-RunId latest discovery limited to
timestamp-style collector runs. This prevents plain cleanup from selecting custom-like
no-state directories unless the operator supplied that exact RunId.

.FUNCTION NAME
Find-LatestDCOIRRunDirectory

.INPUTS
Root string and optional CurrentRunId string.

.OUTPUTS
DirectoryInfo object or null.
#>
function Find-LatestDCOIRRunDirectory {
  param([string]$Root,[string]$CurrentRunId)

  if ([string]::IsNullOrWhiteSpace($Root) -or -not (Test-Path -LiteralPath $Root)) { return $null }
  if (-not [string]::IsNullOrWhiteSpace($CurrentRunId)) {
    $expected = Get-RunRoot -Root $Root -CurrentRunId $CurrentRunId
    if (Test-Path -LiteralPath $expected) { return Get-Item -LiteralPath $expected -ErrorAction Stop }
    return $null
  }

  $dirs = Get-ChildItem -LiteralPath $Root -Directory -ErrorAction SilentlyContinue |
    Where-Object { Test-DCOIRBulkPurgeRunDirectoryName -Name $_.Name } |
    Sort-Object LastWriteTime -Descending
  return ($dirs | Select-Object -First 1)
}

<#
.SYNOPSIS
Loads saved collector state without broad custom discovery.

.DESCRIPTION
Preserves exact custom RunId lookup when the operator supplies a RunId, but limits blank
RunId latest-state discovery to timestamp-style collector run roots. This keeps plain
cleanup from selecting state-backed custom RunId roots by LastWriteTime.

.FUNCTION NAME
Load-State

.INPUTS
Root string and optional CurrentRunId string.

.OUTPUTS
Deserialized state object.
#>
function Load-State {
  param([string]$Root,[string]$CurrentRunId)

  if ([string]::IsNullOrWhiteSpace($CurrentRunId)) {
    $dirs = Get-ChildItem -LiteralPath $Root -Directory -ErrorAction SilentlyContinue |
      Where-Object { Test-DCOIRBulkPurgeRunDirectoryName -Name $_.Name } |
      Sort-Object LastWriteTime -Descending
    if (-not $dirs) {
      throw "No DCOIR run directories found under $Root"
    }
    $selected = $dirs | Select-Object -First 1
    $statePath = Join-Path $selected.FullName "state.json"
    if (-not (Test-Path -LiteralPath $statePath)) {
      throw "State file not found: $statePath"
    }
    return (Get-Content -LiteralPath $statePath -Raw -ErrorAction Stop | ConvertFrom-Json)
  }

  $statePath = Get-StatePath -Root $Root -CurrentRunId $CurrentRunId
  if (-not (Test-Path -LiteralPath $statePath)) {
    throw "State file not found: $statePath"
  }

  return (Get-Content -LiteralPath $statePath -Raw -ErrorAction Stop | ConvertFrom-Json)
}

<#
.SYNOPSIS
Checks whether collector validation-only behavior is explicitly enabled.

.DESCRIPTION
Returns true when DCOIR_COLLECTOR_TEST_MODE is set to 1 or when the collector was
spawned by the maintained harness script. Test payload helpers must require this before
mutating runtime artifacts from environment variables.

.FUNCTION NAME
Test-DCOIRCollectorTestModeEnabled

.INPUTS
Process environment variable DCOIR_COLLECTOR_TEST_MODE and parent process command line.

.OUTPUTS
Boolean.
#>
function Test-DCOIRCollectorTestModeEnabled {
  if ([Environment]::GetEnvironmentVariable('DCOIR_COLLECTOR_TEST_MODE', 'Process') -eq '1') { return $true }
  try {
    $current = Get-CimInstance Win32_Process -Filter ("ProcessId = {0}" -f $PID) -ErrorAction Stop
    if ($current -and $current.ParentProcessId) {
      $parent = Get-CimInstance Win32_Process -Filter ("ProcessId = {0}" -f $current.ParentProcessId) -ErrorAction Stop
      if ($parent.CommandLine -match 'run_DCOIR_Tests\.ps1') { return $true }
    }
  } catch {
    return $false
  }
  return $false
}

<#
.SYNOPSIS
Builds the response-action-safe collector command base with exact run scope when known.

.DESCRIPTION
Returns the response-action-safe collector command base and appends the current RunId
when collector state has already established one. This keeps emitted cleanup/enrich
commands exact for custom RunId runs without broadening blank-RunId discovery.

.FUNCTION NAME
Get-CollectorResponseActionCommandBase

.INPUTS
Current Global:CurrentRunId.

.OUTPUTS
String containing the response-action-safe command base.
#>
function Get-CollectorResponseActionCommandBase {
  $base = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File """".\DCOIR_Collector.ps1"""""
  $packageName = ''
  $packageNameVariable = Get-Variable -Scope Global -Name CurrentPackageName -ErrorAction SilentlyContinue
  if ($packageNameVariable -and -not [string]::IsNullOrWhiteSpace([string]$packageNameVariable.Value)) {
    $packageName = [string]$packageNameVariable.Value
  }
  if (
    -not [string]::IsNullOrWhiteSpace($packageName) -and
    $packageName -ne 'DCOIR_Collector.zip' -and
    (Test-DCOIRPackageNameLeaf -CurrentPackageName $packageName)
  ) {
    $base = ('{0} -PackageName ""{1}""' -f $base, $packageName)
  }
  $current = ''
  $currentRunIdVariable = Get-Variable -Scope Global -Name CurrentRunId -ErrorAction SilentlyContinue
  if ($currentRunIdVariable -and -not [string]::IsNullOrWhiteSpace([string]$currentRunIdVariable.Value)) {
    $current = [string]$currentRunIdVariable.Value
  }
  if (-not [string]::IsNullOrWhiteSpace($current) -and [regex]::IsMatch($current, '^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$')) {
    return ('{0} -RunId ""{1}""' -f $base, $current)
  }
  return $base
}
# DCOIR_REVIEW_AUDIT_BATCH_2F_MARKER
