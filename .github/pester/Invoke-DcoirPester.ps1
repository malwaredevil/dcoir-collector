[CmdletBinding()]
param(
  [string]$Path,
  [Version]$MinimumPesterVersion = '5.0.0',
  [Version]$RequiredPesterVersion,
  [switch]$CI,
  [switch]$PassThru,
  [string]$TestResultOutputPath,
  [ValidateRange(1, 2147483647)]
  [int]$MinimumTestCount = 1
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($Path)) {
  $Path = $PSScriptRoot
}

if ([string]::IsNullOrWhiteSpace($TestResultOutputPath)) {
  $TestResultOutputPath = Join-Path $PSScriptRoot 'TestResults.xml'
}

function Get-InstalledPesterSummary {
  $modules = @(Get-Module -ListAvailable -Name Pester | Sort-Object Version -Descending)
  if (@($modules).Count -eq 0) {
    return '<none found>'
  }

  return (($modules | ForEach-Object { '{0} at {1}' -f $_.Version, $_.Path }) -join [Environment]::NewLine)
}

$resolvedPath = (Resolve-Path -LiteralPath $Path).ProviderPath

$availablePester = if ($null -ne $RequiredPesterVersion) {
  @(Get-Module -ListAvailable -Name Pester | Where-Object { $_.Version -eq $RequiredPesterVersion }) | Select-Object -First 1
} else {
  @(Get-Module -ListAvailable -Name Pester | Where-Object { $_.Version -ge $MinimumPesterVersion } | Sort-Object Version -Descending) | Select-Object -First 1
}

if (-not $availablePester) {
  $found = Get-InstalledPesterSummary
  $requirement = if ($null -ne $RequiredPesterVersion) { "exactly $RequiredPesterVersion" } else { "$MinimumPesterVersion or newer" }
  $installArgument = if ($null -ne $RequiredPesterVersion) { "-RequiredVersion $RequiredPesterVersion" } else { "-MinimumVersion $MinimumPesterVersion" }
  throw @"
DCOIR Pester tests require Pester $requirement.

Installed Pester modules:
$found

Install or update Pester for the current user, then rerun this script:
  Install-Module Pester -Scope CurrentUser $installArgument -Force -SkipPublisherCheck

If Windows PowerShell has already loaded the inbox Pester module, start a fresh PowerShell session or run:
  Remove-Module Pester -ErrorAction SilentlyContinue
"@
}

$loadedPester = Get-Module -Name Pester
if ($loadedPester) {
  Remove-Module Pester -Force -ErrorAction Stop
}

Import-Module -Name $availablePester.Path -Force -ErrorAction Stop
$importedPester = Get-Module -Name Pester
Write-Host ('[dcoir-pester] Using Pester {0} from {1}' -f $importedPester.Version, $importedPester.Path)
Write-Host ('[dcoir-pester] Test path: {0}' -f $resolvedPath)

if (-not (Get-Command New-PesterConfiguration -ErrorAction SilentlyContinue)) {
  throw 'The imported Pester module does not expose New-PesterConfiguration. Install Pester 5 or newer.'
}

$config = New-PesterConfiguration
$config.Run.Path = @($resolvedPath)
$config.Run.PassThru = $true
$config.Output.Verbosity = 'Detailed'

if ($CI) {
  $TestResultOutputPath = [System.IO.Path]::GetFullPath($TestResultOutputPath)
  $testResultDirectory = Split-Path -Parent $TestResultOutputPath
  if (-not (Test-Path -LiteralPath $testResultDirectory)) {
    New-Item -ItemType Directory -Force -Path $testResultDirectory | Out-Null
  }
  Remove-Item -LiteralPath $TestResultOutputPath -Force -ErrorAction SilentlyContinue
  $config.TestResult.Enabled = $true
  $config.TestResult.OutputPath = $TestResultOutputPath
  $config.TestResult.OutputFormat = 'NUnitXml'
}

$result = Invoke-Pester -Configuration $config

if ($null -eq $result) {
  throw 'DCOIR Pester validation did not return a result. Test discovery may have failed or found no tests.'
}

if ([int]$result.TotalCount -lt $MinimumTestCount) {
  throw ('DCOIR Pester validation discovered {0} tests; expected at least {1}.' -f $result.TotalCount, $MinimumTestCount)
}

if ($CI -and -not (Test-Path -LiteralPath $TestResultOutputPath -PathType Leaf)) {
  throw "DCOIR Pester validation did not create the required test result: $TestResultOutputPath"
}

Write-Host ('DCOIR_PESTER_ENGINE={0}' -f $PSVersionTable.PSEdition)
Write-Host ('DCOIR_PESTER_ENGINE_VERSION={0}' -f $PSVersionTable.PSVersion)
Write-Host ('DCOIR_PESTER_VERSION={0}' -f $importedPester.Version)
Write-Host ('DCOIR_PESTER_RESULT={0}' -f $result.Result)
Write-Host ('DCOIR_PESTER_TOTAL={0}' -f $result.TotalCount)
Write-Host ('DCOIR_PESTER_PASSED={0}' -f $result.PassedCount)
Write-Host ('DCOIR_PESTER_FAILED={0}' -f $result.FailedCount)
Write-Host ('DCOIR_PESTER_SKIPPED={0}' -f $result.SkippedCount)
if ($CI) {
  Write-Host ('DCOIR_PESTER_NUNIT_PATH={0}' -f $TestResultOutputPath)
}

$failedCount = 0
foreach ($propertyName in @('FailedCount', 'FailedBlocksCount', 'FailedContainersCount')) {
  $property = $result.PSObject.Properties[$propertyName]
  if ($property -and $null -ne $property.Value) {
    $failedCount += [int]$property.Value
  }
}

if ($PassThru) {
  $result
}

if (($failedCount -gt 0) -or ([string]$result.Result -ne 'Passed')) {
  throw ('DCOIR Pester validation failed. Failed item count: {0}' -f $failedCount)
}
