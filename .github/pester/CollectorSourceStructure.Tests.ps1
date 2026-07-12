Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'
Describe 'DCOIR collector source structure and part manifest contract' {
  BeforeAll {
    . (Join-Path $PSScriptRoot 'DcoirPester.Helpers.ps1')
    $script:Layout = Get-DcoirCollectorLayout
    $script:Manifest = Read-DcoirJson -Path $script:Layout.CollectorManifest
    $script:WrapperPartNames = Get-DcoirWrapperPartNames -CollectorEntryPath $script:Layout.CollectorEntry
    $script:ManifestPartNames = Get-DcoirManifestPartNames -Manifest $script:Manifest
    $script:ManifestPartPaths = Get-DcoirManifestPartPaths -Manifest $script:Manifest
  }

  It 'keeps the collector wrapper, part directory, and runtime manifest present' {
    Test-Path -LiteralPath $script:Layout.CollectorEntry | Should -BeTrue
    Test-Path -LiteralPath $script:Layout.CollectorPartsDirectory | Should -BeTrue
    Test-Path -LiteralPath $script:Layout.CollectorManifest | Should -BeTrue
  }

  It 'declares the expected compile-single-runtime packaging strategy' {
    [string]$script:Manifest.source_strategy | Should -BeExactly 'compile_single_runtime_then_package'
    [string]$script:Manifest.collector_wrapper_source | Should -BeExactly 'project_sources/collector/source/DCOIR_Collector.ps1'
    [string]$script:Manifest.compiled_runtime_name | Should -BeExactly 'DCOIR_Collector.ps1'
  }

  It 'keeps the wrapper part load order identical to the manifest part order' {
    $diff = Compare-DcoirStringArray -Expected $script:ManifestPartNames -Actual $script:WrapperPartNames
    @($diff).Count | Should -Be 0
  }

  It 'keeps every manifest-declared collector part present and non-empty' {
    foreach ($relativePath in $script:ManifestPartPaths) {
      $fullPath = Join-Path $script:Layout.RepoRoot $relativePath
      Test-Path -LiteralPath $fullPath | Should -BeTrue
      (Get-Item -LiteralPath $fullPath).Length | Should -BeGreaterThan 0
    }
  }

  It 'does not leave executable unmanifested collector part files under source/parts' {
    $actualNames = @(
      Get-ChildItem -LiteralPath $script:Layout.CollectorPartsDirectory -File -Filter 'DCOIR_Collector.*.ps1' |
        Where-Object {
          $parsed = Get-DcoirParsedFile -Path $_.FullName
          @($parsed.Ast.EndBlock.Statements).Count -gt 0
        } |
        Sort-Object Name |
        ForEach-Object { $_.Name }
    )
    $manifestSorted = @($script:ManifestPartNames | Sort-Object)
    $diff = Compare-DcoirStringArray -Expected $manifestSorted -Actual $actualNames
    @($diff).Count | Should -Be 0
  }

  It 'loads the main entrypoint part last' {
    @($script:WrapperPartNames).Count | Should -BeGreaterThan 0
    $script:WrapperPartNames[@($script:WrapperPartNames).Count - 1] | Should -BeExactly 'DCOIR_Collector.05_Main_Entry.ps1'
  }

  It 'keeps the wrapper import block shape that the runtime compiler replaces' {
    $wrapperText = Read-DcoirText -Path $script:Layout.CollectorEntry
    $wrapperText | Should -Match '(?ms)^\$collectorPartsRoot = .*?^foreach \(\$partFile in \$collectorPartFiles\) \{.*?^\}\s*'
  }
}
