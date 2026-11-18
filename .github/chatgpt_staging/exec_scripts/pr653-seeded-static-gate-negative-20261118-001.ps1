# Validation-only fixture runner for PR #653 exact head. No source or workflow changes.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$expectedHead = 'af6d6540bde5ef0803856721054fa88e07419bcc'
$expectedGateBlob = 'f35fa9527d063c38f24977cfe6fbe14dbaa0e288'
$branch = 'fix/issue608-drop-dead-static-gates-20261118'
$baseDir = Join-Path $env:RUNNER_TEMP 'pr653-seeded-static-gate-negative-20261118-001'
$exactTree = Join-Path $baseDir 'exact-head-tree'
$casesDir = Join-Path $baseDir 'fixtures'
[void](New-Item -ItemType Directory -Path $baseDir -Force)
$ls = @(& git ls-remote origin "refs/heads/$branch")
if ($LASTEXITCODE -ne 0 -or $ls.Count -ne 1) { throw "Unable to read the PR branch remote head." }
$observedHead = ($ls[0] -split '\s+')[0]
if ($observedHead -ne $expectedHead) {
  throw "FAIL-CLOSED: PR branch head drift: expected $expectedHead, actual $observedHead"
}
& git fetch --no-tags origin "refs/heads/$branch"
if ($LASTEXITCODE -ne 0) { throw 'Git fetch of the expected PR branch failed.' }
& git worktree add --detach $exactTree $expectedHead
if ($LASTEXITCODE -ne 0) { throw 'Unable to create isolated exact-head worktree.' }

$script:passCount = 0
try {
  $actualHead = (& git -C $exactTree rev-parse HEAD).Trim()
  $actualBlob = (& git -C $exactTree rev-parse 'HEAD:.github/scripts/Test-DcoirStaticAnalysisValidationGate.ps1').Trim()
  if ($actualHead -ne $expectedHead -or $actualBlob -ne $expectedGateBlob) {
    throw "Source identity mismatch: head=$actualHead gate_blob=$actualBlob"
  }
  $script:gate = Join-Path $exactTree '.github/scripts/Test-DcoirStaticAnalysisValidationGate.ps1'
  if (-not (Test-Path -LiteralPath $script:gate -PathType Leaf)) { throw 'Missing exact-head gate source.' }
  [void](New-Item -ItemType Directory -Path $casesDir -Force)
  Write-Host "EXACT HEAD VERIFIED: $actualHead"
  Write-Host "GATE SOURCE BLOB VERIFIED: $actualBlob"

  function New-GoodAnalyzer {
    return @{
      validation = @{ success = $true }
      summary = @{
        error_count = 0; policy_warning_count = 0; blocking_finding_count = 0
        parse_error_count = 0; harness_fragment_parse_error_count = 0
        unexpected_severity_count = 0
      }
      settings = @{
        path = 'project_sources/collector/PSScriptAnalyzerSettings.psd1'
        active_include_rules = @(
          'PSAvoidUsingPlainTextForPassword'
          'PSAvoidUsingConvertToSecureStringWithPlainText'
          'PSAvoidUsingInvokeExpression'
          'PSAvoidUsingWriteHost'
          'PSUseDeclaredVarsMoreThanAssignments'
          'PSUseShouldProcessForStateChangingFunctions'
        )
      }
      findings = @()
      targets = @()
    }
  }
  function New-GoodDuplicate {
    return @{
      validation = @{ success = $true }
      summary = @{ duplicate_function_count = 0; parse_failure_count = 0 }
    }
  }
  function Assert-GateCase {
    param(
      [Parameter(Mandatory)][string]$Name,
      [Parameter(Mandatory)][string]$Variant,
      [Parameter(Mandatory)][string]$ExpectedFragment
    )
    $analyzer = New-GoodAnalyzer
    $duplicate = New-GoodDuplicate
    $skipAnalyzer = $false
    $skipDuplicate = $false
    switch ($Variant) {
      'clean' {}
      'baselined-warning' {
        $analyzer.findings = @(@{
          severity = 'Warning'; rule_name = 'PSAvoidUsingWriteHost'
          suppressed_by_baseline = $true; target_path = 'example.ps1'
        })
      }
      'information-only' {
        $analyzer.findings = @(@{
          severity = 'Information'; rule_name = 'PSUseApprovedVerbs'
          target_path = 'example.ps1'
        })
      }
      'error-found' {
        $analyzer.findings = @(@{
          severity = 'Error'; rule_name = 'SeededNonPolicyError'; target_path = 'example.ps1'
        })
        $analyzer.summary.error_count = 1
        $analyzer.summary.blocking_finding_count = 1
      }
      'duplicate-found' { $duplicate.summary.duplicate_function_count = 1 }
      'missing-analyzer' { $skipAnalyzer = $true }
      'missing-duplicate' { $skipDuplicate = $true }
      'missing-error-count' { [void]$analyzer.summary.Remove('error_count') }
      'invalid-duplicate-count' { $duplicate.summary.duplicate_function_count = '0' }
      'duplicate-parse-failure' { $duplicate.summary.parse_failure_count = 1 }
      'misreported-error-count' {
        $analyzer.findings = @(@{
          severity = 'Error'; rule_name = 'SeededNonPolicyError'; target_path = 'example.ps1'
        })
      }
      'unsuppressed-policy-warning' {
        $analyzer.findings = @(@{
          severity = 'Warning'; rule_name = 'PSAvoidUsingInvokeExpression'
          suppressed_by_baseline = $false; target_path = 'example.ps1'
        })
        $analyzer.summary.policy_warning_count = 1
        $analyzer.summary.blocking_finding_count = 1
      }
      'invalid-analyzer-evidence' { $analyzer.validation.success = $false }
      default { throw "Unknown synthetic scenario: $Variant" }
    }
    $path = Join-Path $casesDir $Name
    [void](New-Item -ItemType Directory -Path $path -Force)
    $ap = Join-Path $path 'analyzer.json'
    $dp = Join-Path $path 'duplicates.json'
    if (-not $skipAnalyzer) {
      $analyzer | ConvertTo-Json -Depth 15 | Set-Content -LiteralPath $ap -Encoding utf8
    }
    if (-not $skipDuplicate) {
      $duplicate | ConvertTo-Json -Depth 15 | Set-Content -LiteralPath $dp -Encoding utf8
    }
    $lines = [System.Collections.Generic.List[string]]::new()
    $thrown = $null
    try {
      & $script:gate -AnalyzerPath $ap -DuplicatePath $dp 6>&1 |
        ForEach-Object { [void]$lines.Add([string]$_) }
    } catch {
      $thrown = [string]$_.Exception.Message
    }
    $captured = $lines -join [Environment]::NewLine
    if ($ExpectedFragment -eq 'SAFE') {
      if ($thrown) { throw "SAFE scenario $Name wrongly rejected: $thrown; output=$captured" }
      if (-not $captured.Contains('PASS: Static analysis validation gates are clear after report generation.')) {
        throw "SAFE scenario $Name did not emit the expected PASS marker; output=$captured"
      }
      Write-Host "PASS: SAFE CONTROL $Name accepted"
    } else {
      if (-not $thrown) { throw "FAIL-CLOSED BYPASS: $Name was incorrectly accepted; output=$captured" }
      if (-not $thrown.Contains('Static analysis validation gate failed with')) {
        throw "WRONG FAILURE: $Name threw an unrelated error: $thrown"
      }
      if (-not $captured.Contains($ExpectedFragment)) {
        throw "WRONG FAILURE CAUSE: $Name missing reason '$ExpectedFragment'; actual=$captured"
      }
      Write-Host "PASS: UNSAFE CONTROL $Name blocked for intended reason"
    }
    $script:passCount++
  }
  Assert-GateCase 'clean-report' 'clean' 'SAFE'
  Assert-GateCase 'suppressed-policy-warning' 'baselined-warning' 'SAFE'
  Assert-GateCase 'information-finding' 'information-only' 'SAFE'
  Assert-GateCase 'seeded-error-finding' 'error-found' 'PSScriptAnalyzer reported 1 Error-severity finding(s).'
  Assert-GateCase 'seeded-duplicate-count' 'duplicate-found' 'Duplicate-function report found 1 duplicate function name(s).'
  Assert-GateCase 'missing-analyzer-report' 'missing-analyzer' 'PSScriptAnalyzer report missing:'
  Assert-GateCase 'missing-duplicate-report' 'missing-duplicate' 'Duplicate-function report missing:'
  Assert-GateCase 'missing-analyzer-summary-count' 'missing-error-count' 'PSScriptAnalyzer report summary is missing error_count.'
  Assert-GateCase 'noninteger-duplicate-count' 'invalid-duplicate-count' 'Duplicate-function report summary.duplicate_function_count must be a non-negative integer.'
  Assert-GateCase 'seeded-duplicate-parse-failure' 'duplicate-parse-failure' 'Duplicate-function report has 1 parse failure(s).'
  Assert-GateCase 'inconsistent-error-evidence' 'misreported-error-count' 'PSScriptAnalyzer Error count disagrees with findings.'
  Assert-GateCase 'unsuppressed-warning' 'unsuppressed-policy-warning' 'PSScriptAnalyzer reported 1 new unbaselined policy Warning finding(s).'
  Assert-GateCase 'invalid-analyzer-report' 'invalid-analyzer-evidence' 'PSScriptAnalyzer validation did not report success.'
  if ($script:passCount -ne 13) { throw "Case-count mismatch: $script:passCount / 13" }
  Write-Host "ALL THIRTEEN SEEDED CONTROLS PASSED on exact PR #653 head $expectedHead."
  Write-Host 'No production reports, workflow files, or PR branch files were modified.'
} finally {
  & git worktree remove --force $exactTree 2>&1 | Out-Host
  if ($LASTEXITCODE -ne 0) { Write-Warning 'Unable to automatically remove temporary isolated test worktree.' }
  Remove-Item -LiteralPath $baseDir -Recurse -Force -ErrorAction SilentlyContinue
}
