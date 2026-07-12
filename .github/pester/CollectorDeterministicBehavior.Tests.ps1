Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

Describe 'DCOIR collector deterministic function behavior' {
  BeforeAll {
    . (Join-Path $PSScriptRoot 'DcoirPester.Helpers.ps1')
    $script:Layout = Get-DcoirCollectorLayout
    $parts = $script:Layout.CollectorPartsDirectory
    $Global:CollectorErrors = New-Object System.Collections.ArrayList
    $Global:CollectorNotes = New-Object System.Collections.ArrayList
    $Global:ErrorsLogPath = $null

    @(
      'DCOIR_Collector.01A1_Core_Logging_And_Process_Capture.ps1',
      'DCOIR_Collector.01A2_Core_Logging_And_Process_Capture.ps1',
      'DCOIR_Collector.01C_Runtime_Paths_Artifacts_And_Reports.ps1',
      'DCOIR_Collector.02A_Baseline_Collection_And_Reports.ps1',
      'DCOIR_Collector.04A2_Quick_Interface_And_Output.ps1',
      'DCOIR_Collector.04A3_Quick_Interface_And_Output.ps1',
      'DCOIR_Collector.04C_Explicit_Event_Window_Overrides.ps1',
      'DCOIR_Collector.04F1_PR186_Review_Fixes.ps1',
      'DCOIR_Collector.04F2_PR186_Review_Fixes.ps1',
      'DCOIR_Collector.04G1_PR186_External_Review_Fixes.ps1'
    ) | ForEach-Object { . (Join-Path $parts $_) }
  }

  BeforeEach {
    $Global:CollectorErrors.Clear()
    $script:WindowStart = $null
    $script:WindowEnd = $null
    $script:Quick = $null
    $script:Target = $null
    $script:Target2 = $null
    $script:Hours = 24
    $script:Mode = 'Collect'
    $script:Tier = 'T1'
    $script:Targeted = $false
    $script:TargetProfile = 'Generic'
    $script:NewEnrichSession = $false
    $script:Action = $null
    $script:TargetPid = 0
    $script:RunId = $null
    $script:CollectPrepSkipReason = $null
  }

  It 'normalizes cleanup containment without accepting similarly named siblings' {
    $root = Join-Path $TestDrive 'DCOIR-root'
    $child = Join-Path $root 'DCOIR_RUN_01'
    $sibling = Join-Path $TestDrive 'DCOIR-root-escape'
    New-Item -ItemType Directory -Force -Path $child, $sibling | Out-Null

    Test-DCOIRCleanupPathWithinRoot -Root $root -Path $root | Should -BeTrue
    Test-DCOIRCleanupPathWithinRoot -Root $root -Path $child | Should -BeTrue
    Test-DCOIRCleanupPathWithinRoot -Root $root -Path $sibling | Should -BeFalse
    Test-DCOIRCleanupPathEquals -Actual $child -Expected $child.ToUpperInvariant() | Should -BeTrue
  }

  It 'recognizes only host-bound timestamp run directories for bulk purge' {
    Test-DCOIRBulkPurgeRunDirectoryName -Name ("DCOIR_{0}_20260712_145900" -f $env:COMPUTERNAME) | Should -BeTrue
    Test-DCOIRBulkPurgeRunDirectoryName -Name ("DCOIR_{0}_20260712_1459" -f $env:COMPUTERNAME) | Should -BeFalse
    Test-DCOIRBulkPurgeRunDirectoryName -Name 'DCOIR_OTHERHOST_20260712_145900' | Should -BeFalse
    Test-DCOIRBulkPurgeRunDirectoryName -Name '..\DCOIR_ESCAPE_20260712_145900' | Should -BeFalse
  }

  It 'honors WhatIf while purging prior run directories and packages' {
    $root = Join-Path $TestDrive 'purge-root'
    $runRoot = Join-Path $root ("DCOIR_{0}_20260712_145900" -f $env:COMPUTERNAME)
    $package = Join-Path $root 'DCOIR_Collector.zip'
    New-Item -ItemType Directory -Force -Path $runRoot | Out-Null
    Set-Content -LiteralPath (Join-Path $runRoot 'evidence.txt') -Value 'retain under WhatIf'
    Set-Content -LiteralPath $package -Value 'retain under WhatIf'

    Purge-PreviousRuns -Root $root -CurrentPackageName 'DCOIR_Collector.zip' -WhatIf | Should -BeFalse
    Test-Path -LiteralPath $runRoot | Should -BeTrue
    Test-Path -LiteralPath $package | Should -BeTrue
    $script:CollectPrepSkipReason | Should -BeExactly 'PACKAGE_PURGE_SKIPPED'
  }

  It 'builds event filters from explicit bounds and selected event IDs' {
    $start = [datetime]'2026-07-12T10:00:00Z'
    $end = [datetime]'2026-07-12T11:00:00Z'
    $filter = Get-CollectorEventFilterHashtable -LogName Security -Window @{ StartTime = $start; EndTime = $end } -Ids @(4688, 4624)

    $filter.LogName | Should -BeExactly 'Security'
    $filter.StartTime | Should -Be $start
    $filter.EndTime | Should -Be $end
    @($filter.Id) | Should -Be @(4688, 4624)
  }

  It 'uses explicit event windows and rejects inverted windows with observable fallback' {
    $script:WindowStart = '2026-07-12T10:00:00Z'
    $script:WindowEnd = '2026-07-12T11:00:00Z'
    $explicit = Get-CollectorEffectiveEventWindow -WindowHours 6
    $explicit.HasExplicitWindow | Should -BeTrue
    $explicit.StartTime.ToUniversalTime().ToString('o') | Should -BeExactly '2026-07-12T10:00:00.0000000Z'
    $explicit.EndTime.ToUniversalTime().ToString('o') | Should -BeExactly '2026-07-12T11:00:00.0000000Z'

    $script:WindowStart = '2026-07-12T12:00:00Z'
    $script:WindowEnd = '2026-07-12T11:00:00Z'
    $fallback = Get-CollectorEffectiveEventWindow -WindowHours 6
    $fallback.HasExplicitWindow | Should -BeFalse
    $fallback.EndTime | Should -BeNullOrEmpty
    $fallback.EffectiveHours | Should -Be 6
    @($Global:CollectorErrors).Count | Should -Be 1
    $script:WindowStart | Should -BeNullOrEmpty
    $script:WindowEnd | Should -BeNullOrEmpty
  }

  It 'does not split inside a multibyte UTF-8 character' {
    $bytes = [System.Text.Encoding]::UTF8.GetBytes("A$([char]::ConvertFromUtf32(0x1F600))B")
    Get-Utf8SafeChunkLength -Bytes $bytes -Offset 0 -TargetBytes 3 | Should -Be 1
    Get-Utf8SafeChunkLength -Bytes $bytes -Offset 1 -TargetBytes 3 | Should -Be 4
  }

  It 'reassembles upload-safe chunks byte-for-byte across a multibyte boundary' {
    $source = Join-Path $TestDrive 'source.txt'
    $artifacts = Join-Path $TestDrive 'chunks'
    New-Item -ItemType Directory -Path $artifacts | Out-Null
    $content = ('a' * 1022) + [char]::ConvertFromUtf32(0x1F600) + ('b' * 64)
    [System.IO.File]::WriteAllText($source, $content, (New-Object System.Text.UTF8Encoding($false)))

    $manifest = Split-TextArtifactIntoUploadSafeChunks -SourcePath $source -ArtifactsDir $artifacts -SourceKey 'pester/test' -TargetChunkKB 1
    $manifest.chunk_count | Should -BeGreaterThan 1

    $stream = New-Object System.IO.MemoryStream
    try {
      foreach ($chunkPath in $manifest.chunk_paths) {
        $chunkBytes = [System.IO.File]::ReadAllBytes($chunkPath)
        $stream.Write($chunkBytes, 0, $chunkBytes.Length)
      }
      [Convert]::ToBase64String($stream.ToArray()) | Should -BeExactly ([Convert]::ToBase64String([System.IO.File]::ReadAllBytes($source)))
    } finally {
      $stream.Dispose()
    }
  }

  It 'honors WhatIf without writing upload-safe chunk companions' {
    $source = Join-Path $TestDrive 'whatif-source.txt'
    $artifacts = Join-Path $TestDrive 'whatif-chunks'
    New-Item -ItemType Directory -Path $artifacts | Out-Null
    [System.IO.File]::WriteAllText($source, 'bounded content')

    Split-TextArtifactIntoUploadSafeChunks -SourcePath $source -ArtifactsDir $artifacts -SourceKey 'whatif' -TargetChunkKB 1 -WhatIf
    @(Get-ChildItem -LiteralPath $artifacts -File).Count | Should -Be 0
  }

  It 'applies collect and targeted quick aliases to runtime state' {
    $script:Quick = 'collect-t2'
    Apply-QuickShortcut
    $script:Mode | Should -BeExactly 'Collect'
    $script:Tier | Should -BeExactly 'T2'
    $script:Hours | Should -Be 72

    $script:Quick = 'collect_targeted_script'
    $script:Target = 'reported popup'
    $script:Target2 = 'powershell.exe'
    $script:Hours = 24
    Apply-QuickShortcut
    $script:Targeted | Should -BeTrue
    $script:TargetProfile | Should -BeExactly 'ScriptExecution'
    $script:Hours | Should -Be 12
  }

  It 'validates numeric quick-alias targets before changing action state' {
    $script:Quick = 'enrich-start-listdlls'
    $script:Target = '4321'
    Apply-QuickShortcut
    $script:Mode | Should -BeExactly 'Enrich'
    $script:NewEnrichSession | Should -BeTrue
    $script:Action | Should -BeExactly 'ListDllsPid'
    $script:TargetPid | Should -Be 4321

    $script:Quick = 'enrich-add-listdlls'
    $script:Target = 'not-a-pid'
    { Apply-QuickShortcut } | Should -Throw
  }
}
