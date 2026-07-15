Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'
Describe 'DCOIR collector harness and Pester boundary evidence contract' {
  BeforeAll {
    . (Join-Path $PSScriptRoot 'DcoirPester.Helpers.ps1')
    $script:Layout = Get-DcoirCollectorLayout
  }

  It 'keeps the collector harness source, assembler, and harness parts present' {
    Test-Path -LiteralPath $script:Layout.CollectorHarness | Should -BeTrue
    Test-Path -LiteralPath $script:Layout.HarnessAssembler | Should -BeTrue
    Test-Path -LiteralPath $script:Layout.HarnessPartsDirectory | Should -BeTrue
    @(Get-ChildItem -LiteralPath $script:Layout.HarnessPartsDirectory -File -Filter 'run_DCOIR_Tests.part-*.ps1').Count | Should -BeGreaterThan 0
  }

  It 'parses the checked-in harness and harness assembler without parser errors' {
    foreach ($path in @($script:Layout.CollectorHarness, $script:Layout.HarnessAssembler)) {
      $parsed = Get-DcoirParsedFile -Path $path
      $message = if (@($parsed.Errors).Count -eq 0) { '' } else { (@($parsed.Errors | ForEach-Object { $_.Message }) -join '; ') }
      @($parsed.Errors).Count | Should -Be 0 -Because ("PowerShell parser errors in {0}: {1}" -f $path, $message)
    }
  }

  It 'keeps the harness assembler using deterministic UTF-8 without BOM output' {
    $text = Read-DcoirText -Path $script:Layout.HarnessAssembler
    $text | Should -Match 'New-Object System\.Text\.UTF8Encoding\(\$false\)'
    $text | Should -Match 'Get-NormalizedTextSha256'
    $text | Should -Match 'ExpectedHarnessPath'
  }

  It 'keeps the repository Pester boundary explicit that Pester is supporting evidence, not a static analyzer substitute' {
    Test-Path -LiteralPath $script:Layout.PesterBoundaryJson | Should -BeTrue
    Test-Path -LiteralPath $script:Layout.PesterBoundaryReport | Should -BeTrue

    $boundary = Read-DcoirJson -Path $script:Layout.PesterBoundaryJson
    [bool]$boundary.policy.pester_may_replace_analyzer_or_custom_checks | Should -BeFalse
    [bool]$boundary.policy.independent_analyzer_enforcement_required | Should -BeTrue
    [bool]$boundary.independent_analyzer_enforcement_proof.requires_pester | Should -BeFalse
    [string]$boundary.pester_boundary.scope_decision | Should -BeExactly 'supporting-in-scope-not-analyzer-substitute'
  }
}
