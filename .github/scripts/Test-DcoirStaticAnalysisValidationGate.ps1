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
  $parseCount = Get-DcoirReportSummaryCount -Report $analyzer -Field 'parse_error_count' -Label 'PSScriptAnalyzer'
  $fragmentParseCount = Get-DcoirReportSummaryCount -Report $analyzer -Field 'harness_fragment_parse_error_count' -Label 'PSScriptAnalyzer'
  $unexpectedSeverityCount = Get-DcoirReportSummaryCount -Report $analyzer -Field 'unexpected_severity_count' -Label 'PSScriptAnalyzer'
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
    $policyWarningFindings = @($analyzer.findings | Where-Object {
      $_.severity -eq 'Warning' -and $policyRules -contains $_.rule_name
    })
    $invalidPolicyWarningSuppressionMetadataCount = @($policyWarningFindings | Where-Object {
      (-not $_.PSObject.Properties.Match('suppressed_by_baseline')) -or ($_.suppressed_by_baseline -isnot [bool])
    }).Count
    if ($invalidPolicyWarningSuppressionMetadataCount -gt 0) {
      $failures.Add('PSScriptAnalyzer policy Warning findings must include boolean suppressed_by_baseline metadata.')
    }
    $actualPolicyWarnings = @($policyWarningFindings | Where-Object {
      $_.suppressed_by_baseline -ne $true
    }).Count
    $actualParseErrors = @($analyzer.findings | Where-Object { $_.severity -eq 'ParseError' }).Count
    $knownFragments = @($analyzer.targets | Where-Object {
      $_.category -eq 'collector_harness_source_part' -and $_.path -match '^project_sources/collector/harness/source/parts/'
    } | ForEach-Object { $_.path })
    $actualFragmentErrors = @($analyzer.findings | Where-Object {
      $_.severity -eq 'ParseError' -and $knownFragments -contains $_.target_path
    }).Count
    $actualUnknownSeverities = @($analyzer.findings | Where-Object {
      $_.severity -notin @('Error', 'Warning', 'Information', 'ParseError')
    }).Count
    if ($parseCount -ne $actualParseErrors -or $fragmentParseCount -ne $actualFragmentErrors) {
      $failures.Add('PSScriptAnalyzer parser-error counts disagree with per-target evidence.')
    }
    if ($unexpectedSeverityCount -ne $actualUnknownSeverities) {
      $failures.Add('PSScriptAnalyzer unknown severity count disagrees with findings.')
    }
    if ($actualParseErrors -ne $actualFragmentErrors) {
      $failures.Add('PSScriptAnalyzer has parser errors outside known split harness fragments.')
    }
    if ($actualUnknownSeverities -gt 0) {
      $failures.Add('PSScriptAnalyzer has unrecognized finding severity.')
    }
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
