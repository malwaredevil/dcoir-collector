Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'
Describe 'DCOIR collector parser compatibility and public parameter contract' {
  BeforeAll {
    . (Join-Path $PSScriptRoot 'DcoirPester.Helpers.ps1')
    $script:Layout = Get-DcoirCollectorLayout
    $script:Manifest = Read-DcoirJson -Path $script:Layout.CollectorManifest
    $script:SourceFiles = Get-DcoirCollectorSourceFiles -Layout $script:Layout -Manifest $script:Manifest
    $script:EntryParse = Get-DcoirParsedFile -Path $script:Layout.CollectorEntry
  }

  It 'parses the wrapper and every collector source part without parser errors' {
    foreach ($path in $script:SourceFiles) {
      $parsed = Get-DcoirParsedFile -Path $path
      $message = if (@($parsed.Errors).Count -eq 0) { '' } else { (@($parsed.Errors | ForEach-Object { $_.Message }) -join '; ') }
      @($parsed.Errors).Count | Should -Be 0 -Because ("PowerShell parser errors in {0}: {1}" -f $path, $message)
    }
  }

  It 'keeps the public Mode ValidateSet scoped to Collect, Enrich, and Cleanup' {
    $parameter = Get-DcoirEntryParameterAst -Ast $script:EntryParse.Ast -Name 'Mode'
    $values = @(Get-DcoirAttributePositionalValues -ParameterAst $parameter -AttributeName 'ValidateSet')
    $diff = Compare-DcoirStringArray -Expected @('Collect','Enrich','Cleanup') -Actual $values
    @($diff).Count | Should -Be 0
  }

  It 'keeps the public Tier ValidateSet scoped to T1 and T2' {
    $parameter = Get-DcoirEntryParameterAst -Ast $script:EntryParse.Ast -Name 'Tier'
    $values = @(Get-DcoirAttributePositionalValues -ParameterAst $parameter -AttributeName 'ValidateSet')
    $diff = Compare-DcoirStringArray -Expected @('T1','T2') -Actual $values
    @($diff).Count | Should -Be 0
  }

  It 'keeps the enrichment Action ValidateSet aligned with supported response actions' {
    $expectedActions = @(
      'SigcheckPath',
      'ListDllsPid',
      'AccessChkFile',
      'AccessChkService',
      'AccessChkReg',
      'StringsPath',
      'StreamsPath',
      'TcpvconRefresh',
      'LogText',
      'LogRaw',
      'PullSuspiciousFile',
      'PullScriptOrConfig',
      'PullTaskXml',
      'PullServiceBinary',
      'PullWmiReferencedFile'
    )
    $parameter = Get-DcoirEntryParameterAst -Ast $script:EntryParse.Ast -Name 'Action'
    $values = @(Get-DcoirAttributePositionalValues -ParameterAst $parameter -AttributeName 'ValidateSet')
    $diff = Compare-DcoirStringArray -Expected $expectedActions -Actual $values
    @($diff).Count | Should -Be 0
  }

  It 'keeps targeted collection profiles explicit and bounded' {
    $expectedProfiles = @('Generic','PopupWindow','ScriptExecution','PersistenceFollowUp','NetworkOnly','ProcessAndPowerShell')
    $parameter = Get-DcoirEntryParameterAst -Ast $script:EntryParse.Ast -Name 'TargetProfile'
    $values = @(Get-DcoirAttributePositionalValues -ParameterAst $parameter -AttributeName 'ValidateSet')
    $diff = Compare-DcoirStringArray -Expected $expectedProfiles -Actual $values
    @($diff).Count | Should -Be 0
  }

  It 'keeps help and version aliases available for operator-friendly invocation' {
    $helpParameter = Get-DcoirEntryParameterAst -Ast $script:EntryParse.Ast -Name 'ShowHelp'
    $versionParameter = Get-DcoirEntryParameterAst -Ast $script:EntryParse.Ast -Name 'ShowVersion'

    $helpAliases = @(Get-DcoirAttributePositionalValues -ParameterAst $helpParameter -AttributeName 'Alias')
    $versionAliases = @(Get-DcoirAttributePositionalValues -ParameterAst $versionParameter -AttributeName 'Alias')

    @($helpAliases | Where-Object { $_ -in @('help','h','?') }).Count | Should -Be 3
    @($versionAliases | Where-Object { $_ -in @('version','ver','buildinfo') }).Count | Should -Be 3
  }

  It 'keeps wrapper ScriptVersion aligned with the runtime package manifest bundle_version' {
    $scriptVersion = Get-DcoirScriptVersionFromWrapper -CollectorEntryPath $script:Layout.CollectorEntry
    $manifestVersion = Convert-DcoirBundleVersionToScriptVersion -BundleVersion ([string]$script:Manifest.bundle_version)
    $scriptVersion | Should -BeExactly $manifestVersion
  }

  It 'keeps high-impact public parameter types and defaults stable' {
    $expected = @(
      @{ Name = 'Mode'; Type = 'System.String'; Default = 'Collect' },
      @{ Name = 'Tier'; Type = 'System.String'; Default = 'T1' },
      @{ Name = 'Hours'; Type = 'System.Int32'; Default = 24 },
      @{ Name = 'OutRoot'; Type = 'System.String'; Default = 'C:\Temp' },
      @{ Name = 'PackageName'; Type = 'System.String'; Default = 'DCOIR_Collector.zip' },
      @{ Name = 'MaxEvents'; Type = 'System.Int32'; Default = 500 },
      @{ Name = 'TargetProfile'; Type = 'System.String'; Default = 'Generic' }
    )

    foreach ($row in $expected) {
      $parameter = Get-DcoirEntryParameterAst -Ast $script:EntryParse.Ast -Name $row.Name
      $parameter.StaticType.FullName | Should -BeExactly $row.Type -Because ("public parameter type drifted: {0}" -f $row.Name)
      $parameter.DefaultValue.SafeGetValue() | Should -Be $row.Default -Because ("public parameter default drifted: {0}" -f $row.Name)
    }
  }
}
