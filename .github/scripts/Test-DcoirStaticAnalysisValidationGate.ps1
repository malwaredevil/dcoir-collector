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
  return $value
}

if (-not (Test-Path -LiteralPath $AnalyzerPath)) {
  $failures.Add("PSScriptAnalyzer report missing: $AnalyzerPath")
} else {
  $analyzer = Get-Content -LiteralPath $AnalyzerPath -Raw | ConvertFrom-Json
  if ($analyzer.validation.success -ne $true) {
    $failures.Add('PSScriptAnalyzer validation did not report success.')
  }

  # The canonical Python report preserves all legacy Error findings while
  # the six declared policy rules become blocking at Warning severity.
  $errorCount = Get-DcoirReportSummaryCount -Report $analyzer -Field 'error_count' -Label 'PSScriptAnalyzer'
  $policyWarningCount = Get-DcoirReportSummaryCount -Report $analyzer -Field 'policy_warning_count' -Label 'PSScriptAnalyzer'
  $blockingCount = Get-DcoirReportSummaryCount -Report $analyzer -Field 'blocking_finding_count' -Label 'PSScriptAnalyzer'
  $policyRules = @(
    'PSAvoidUsingPlainTextForPassword', 'PSAvoidUsingConvertToSecureStringWithPlainText',
    'PSAvoidUsingInvokeExpression', 'PSAvoidUsingWriteHost',
    'PSUseDeclaredVarsMoreThanAssignments', 'PSUseShouldProcessForStateChangingFunctions'
  )
  if ($analyzer.settings.path -ne 'project_sources/collector/PSScriptAnalyzerSettings.psd1') {
    $failures.Add('PSScriptAnalyzer report does not identify the active repository policy file.')
  }
  foreach ($rule in $policyRules) {
    if (@($analyzer.settings.active_include_rules) -cnotcontains $rule) {
      $failures.Add("PSScriptAnalyzer policy is missing blocking rule: $rule")
    }
  }
  if ($null -eq $analyzer.findings -or $analyzer.findings -isnot [array]) {
    $failures.Add('PSScriptAnalyzer findings must be an array for count readback.')
  } else {
    $actualErrorCount = @($analyzer.findings | Where-Object { $_.severity -eq 'Error' }).Count
    $actualPolicyWarnings = @($analyzer.findings | Where-Object {
      $_.severity -eq 'Warning' -and $policyRules -contains $_.rule_name -and $_.suppressed_by_baseline -eq $false
    }).Count
    if ($actualErrorCount -ne $errorCount) {
      $failures.Add('PSScriptAnalyzer Error count disagrees with findings.')
    }
    if ($actualPolicyWarnings -ne $policyWarningCount -or $blockingCount -ne ($actualErrorCount + $actualPolicyWarnings)) {
      $failures.Add('PSScriptAnalyzer blocking count disagrees with policy findings.')
    }
  }
  if ($errorCount -gt 0) {
    $failures.Add("PSScriptAnalyzer reported $errorCount Error-severity finding(s).")
  }
  if ($policyWarningCount -gt 0) {
    $failures.Add("PSScriptAnalyzer reported $policyWarningCount new unbaselined policy Warning finding(s).")
  }
  if ($blockingCount -gt 0) {
    $failures.Add("PSScriptAnalyzer has $blockingCount blocking policy or Error finding(s).")
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
