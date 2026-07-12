[CmdletBinding()]
param(
  [string]$AnalyzerPath = 'project_sources/collector/powershell_analyzer_report.json',
  [string]$DuplicatePath = 'project_sources/collector/powershell_duplicate_function_report.json'
)

$ErrorActionPreference = 'Stop'
$failures = [System.Collections.Generic.List[string]]::new()

if (-not (Test-Path -LiteralPath $AnalyzerPath)) {
  $failures.Add("PSScriptAnalyzer report missing: $AnalyzerPath")
} else {
  $analyzer = Get-Content -LiteralPath $AnalyzerPath -Raw | ConvertFrom-Json
  if ($analyzer.validation.success -ne $true) {
    $failures.Add('PSScriptAnalyzer validation did not report success.')
  }

  $errorCount = 0
  if ($null -ne $analyzer.summary.error_count) {
    $errorCount = [int]$analyzer.summary.error_count
  }
  if ($errorCount -gt 0) {
    $failures.Add("PSScriptAnalyzer reported $errorCount Error-severity finding(s).")
  }
}

if (-not (Test-Path -LiteralPath $DuplicatePath)) {
  $failures.Add("Duplicate-function report missing: $DuplicatePath")
} else {
  $duplicate = Get-Content -LiteralPath $DuplicatePath -Raw | ConvertFrom-Json
  if ($duplicate.validation.success -ne $true) {
    $failures.Add('Duplicate-function validation did not report success.')
  }

  $duplicateCount = 0
  if ($null -ne $duplicate.summary.duplicate_function_count) {
    $duplicateCount = [int]$duplicate.summary.duplicate_function_count
  }

  $parseFailureCount = 0
  if ($null -ne $duplicate.summary.parse_failure_count) {
    $parseFailureCount = [int]$duplicate.summary.parse_failure_count
  }

  if ($parseFailureCount -gt 0) {
    $failures.Add("Duplicate-function report has $parseFailureCount parse failure(s).")
  }
  if ($duplicateCount -gt 0) {
    $failures.Add("Duplicate-function report found $duplicateCount duplicate function name(s).")
  }
}

if ($failures.Count -gt 0) {
  Write-Host ''
  Write-Host 'STATIC ANALYSIS VALIDATION GATE FAILED'
  Write-Host '======================================'
  foreach ($failure in $failures) {
    Write-Host "  - $failure"
  }
  throw "Static analysis validation gate failed with $($failures.Count) blocking condition(s)."
}

Write-Host 'PASS: Static analysis validation gates are clear after report generation.'
