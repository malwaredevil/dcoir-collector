[CmdletBinding()]
param(
  [string]$AnalyzerPath = 'project_sources/collector/powershell_analyzer_report.json',
  [string]$DuplicatePath = 'project_sources/collector/powershell_duplicate_function_report.json'
)

$ErrorActionPreference = 'Stop'
$failures = [System.Collections.Generic.List[string]]::new()

# A missing or malformed count fails the gate instead of reading as zero, so a
# producer that stops emitting a summary field cannot turn the gate into a pass.
function Get-DcoirReportSummaryCount {
  param(
    [object]$Report,
    [string]$Field,
    [string]$Label
  )
  $summary = $Report.summary
  if ($null -eq $summary -or $null -eq $summary.PSObject.Properties[$Field]) {
    $failures.Add("$Label report summary is missing $Field.")
    return 0
  }
  $value = $summary.$Field
  if (-not ($value -is [int] -or $value -is [long]) -or $value -lt 0) {
    $failures.Add("$Label report summary.$Field must be a non-negative integer.")
    return 0
  }
  return [int]$value
}

if (-not (Test-Path -LiteralPath $AnalyzerPath)) {
  $failures.Add("PSScriptAnalyzer report missing: $AnalyzerPath")
} else {
  $analyzer = Get-Content -LiteralPath $AnalyzerPath -Raw | ConvertFrom-Json
  if ($analyzer.validation.success -ne $true) {
    $failures.Add('PSScriptAnalyzer validation did not report success.')
  }

  $errorCount = Get-DcoirReportSummaryCount -Report $analyzer -Field 'error_count' -Label 'PSScriptAnalyzer'
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

  $duplicateCount = Get-DcoirReportSummaryCount -Report $duplicate -Field 'duplicate_function_count' -Label 'Duplicate-function'
  $parseFailureCount = Get-DcoirReportSummaryCount -Report $duplicate -Field 'parse_failure_count' -Label 'Duplicate-function'

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
