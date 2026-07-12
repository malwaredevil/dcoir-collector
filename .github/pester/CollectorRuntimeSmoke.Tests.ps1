Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'
Describe 'DCOIR collector low-risk runtime smoke behavior' {
  BeforeAll {
    . (Join-Path $PSScriptRoot 'DcoirPester.Helpers.ps1')
    $script:Layout = Get-DcoirCollectorLayout
    $script:Manifest = Read-DcoirJson -Path $script:Layout.CollectorManifest
    $script:ExpectedVersion = Convert-DcoirBundleVersionToScriptVersion -BundleVersion ([string]$script:Manifest.bundle_version)
    $Global:CollectorErrors = New-Object System.Collections.ArrayList
    $Global:CollectorNotes = New-Object System.Collections.ArrayList
    $Global:ErrorsLogPath = $null
    . (Join-Path $script:Layout.CollectorPartsDirectory 'DCOIR_Collector.01A1_Core_Logging_And_Process_Capture.ps1')
    . (Join-Path $script:Layout.CollectorPartsDirectory 'DCOIR_Collector.01A2_Core_Logging_And_Process_Capture.ps1')
    . (Join-Path $script:Layout.CollectorPartsDirectory 'DCOIR_Collector.01B1_Json_State_And_Array_Utilities.ps1')
    . (Join-Path $script:Layout.CollectorPartsDirectory 'DCOIR_Collector.01B2_Json_State_And_Array_Utilities.ps1')
  }

  It 'prints version metadata without starting collection side effects' {
    $output = @(& $script:Layout.CollectorEntry -ShowVersion)
    $map = ConvertTo-DcoirKeyValueMap -Lines $output

    $map.ContainsKey('COLLECTOR_VERSION') | Should -BeTrue
    $map['COLLECTOR_VERSION'] | Should -BeExactly $script:ExpectedVersion
    $map['COLLECTOR_BUILD_IDENTITY'] | Should -BeExactly ("DCOIR_Collector.ps1/{0}" -f $script:ExpectedVersion)
    $map['COLLECTOR_RUNTIME_FILENAME'] | Should -BeExactly 'DCOIR_Collector.ps1'
    $map['EXPECTED_PACKAGE_NAME'] | Should -BeExactly 'DCOIR_Collector.zip'
    $map.ContainsKey('COLLECTOR_SCRIPT_PATH') | Should -BeTrue
  }

  It 'prints general help with the main operating modes and quick examples' {
    $helpText = (@(& $script:Layout.CollectorEntry -ShowHelp) -join "`n")
    $helpText | Should -Match 'DCOIR Collector'
    $helpText | Should -Match 'Collect'
    $helpText | Should -Match 'Enrich'
    $helpText | Should -Match 'Cleanup'
    $helpText | Should -Match 'Quick command examples'
    $helpText | Should -Match 'collect-targeted-popup'
  }

  It 'accepts safe run IDs and rejects path-shaped or traversal run IDs' {
    Test-DCOIRRunIdLeaf -CurrentRunId 'RUN_20260625T151112Z' | Should -BeTrue
    Test-DCOIRRunIdLeaf -CurrentRunId 'run.id-01' | Should -BeTrue
    Test-DCOIRRunIdLeaf -CurrentRunId '..' | Should -BeFalse
    Test-DCOIRRunIdLeaf -CurrentRunId '..\escape' | Should -BeFalse
    Test-DCOIRRunIdLeaf -CurrentRunId 'C:\Temp\evil' | Should -BeFalse
    { Resolve-DCOIRRunId -CurrentRunId '..\escape' } | Should -Throw
  }

  It 'accepts safe package names and rejects path-shaped, traversal, non-zip, and reserved package names' {
    Test-DCOIRPackageNameLeaf -CurrentPackageName 'DCOIR_Collector.zip' | Should -BeTrue
    Test-DCOIRPackageNameLeaf -CurrentPackageName 'DCOIR_Collector_Custom-01.zip' | Should -BeTrue
    Test-DCOIRPackageNameLeaf -CurrentPackageName '..\DCOIR_Collector.zip' | Should -BeFalse
    Test-DCOIRPackageNameLeaf -CurrentPackageName 'DCOIR_Collector.txt' | Should -BeFalse
    Test-DCOIRPackageNameLeaf -CurrentPackageName 'CON.zip' | Should -BeFalse
    { Resolve-DCOIRPackageName -CurrentPackageName '..\DCOIR_Collector.zip' } | Should -Throw
  }

  It 'throws instead of silently emitting truncated JSON when the configured depth is too low' {
    $deepObject = @{ level1 = @{ level2 = @{ level3 = 'value' } } }
    { Convert-ToCollectorJsonText -InputObject $deepObject -Label 'pester-depth-check' -Depth 1 -ThrowOnTruncation } | Should -Throw
  }

  It 'emits newline-terminated safe JSON when object depth is within policy' {
    $json = Convert-ToCollectorJsonText -InputObject @{ ok = @{ value = 1 } } -Label 'pester-safe-json' -Depth 10 -AppendNewline -ThrowOnTruncation
    $json.EndsWith("`n") | Should -BeTrue
    $json | Should -Match '"ok"'
    $json | Should -Match '"value"'
  }
}
