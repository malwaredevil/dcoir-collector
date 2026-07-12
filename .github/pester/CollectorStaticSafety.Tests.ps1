Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'
Describe 'DCOIR collector static safety guardrails' {
  BeforeAll {
    . (Join-Path $PSScriptRoot 'DcoirPester.Helpers.ps1')
    $script:Layout = Get-DcoirCollectorLayout
    $script:Manifest = Read-DcoirJson -Path $script:Layout.CollectorManifest
    $script:SourceFiles = Get-DcoirCollectorSourceFiles -Layout $script:Layout -Manifest $script:Manifest
    $script:Commands = Get-DcoirCommandAsts -Paths $script:SourceFiles
  }

  It 'does not define duplicate PowerShell functions across wrapper and part load order' {
    $definitions = Get-DcoirFunctionDefinitions -Paths $script:SourceFiles
    $duplicates = @($definitions | Group-Object -Property NormalizedName | Where-Object { $_.Count -gt 1 })
    $duplicateText = ($duplicates | ForEach-Object { $_.Name }) -join ', '
    @($duplicates).Count | Should -Be 0 -Because ("Duplicate collector function definitions are package-validation failures: {0}" -f $duplicateText)
  }

  It 'does not execute source text through Invoke-Expression or iex commands' {
    $dynamicExecution = @($script:Commands | Where-Object {
      $name = $_.GetCommandName()
      ($name -ieq 'Invoke-Expression') -or ($name -ieq 'iex')
    })
    $locations = ($dynamicExecution | ForEach-Object { '{0}:{1}' -f $_.Extent.File, $_.Extent.StartLineNumber }) -join ', '
    @($dynamicExecution).Count | Should -Be 0 -Because ("Dynamic expression execution is not allowed in collector source: {0}" -f $locations)
  }

  It 'uses Remove-Item only with LiteralPath in executable collector source' {
    $unsafeRemoveItem = @($script:Commands | Where-Object {
      $_.GetCommandName() -ieq 'Remove-Item' -and -not (@(Get-DcoirCommandParameterNames -CommandAst $_) -icontains 'LiteralPath')
    })
    $locations = ($unsafeRemoveItem | ForEach-Object { '{0}:{1}' -f $_.Extent.File, $_.Extent.StartLineNumber }) -join ', '
    @($unsafeRemoveItem).Count | Should -Be 0 -Because ("Remove-Item must use -LiteralPath to avoid wildcard/path expansion surprises: {0}" -f $locations)
  }

  It 'bounds every executable ConvertTo-Json command with an explicit Depth parameter or governed Depth splat' {
    $jsonUtilityText = ($script:SourceFiles | ForEach-Object { Read-DcoirText -Path $_ }) -join [Environment]::NewLine
    $jsonUtilityText | Should -Match '\$jsonArgs\s*=\s*@\{[\s\S]*?Depth\s*=\s*\$Depth' -Because 'Convert-ToCollectorJsonText must keep Depth in the governed ConvertTo-Json splat.'

    $unboundedJson = @($script:Commands | Where-Object {
      if ($_.GetCommandName() -ine 'ConvertTo-Json') { return $false }
      $parameterNames = @(Get-DcoirCommandParameterNames -CommandAst $_)
      if ($parameterNames -icontains 'Depth') { return $false }

      $commandText = [string]$_.Extent.Text
      if ($commandText -match '@jsonArgs\b') { return $false }

      return $true
    })
    $locations = ($unboundedJson | ForEach-Object { '{0}:{1}' -f $_.Extent.File, $_.Extent.StartLineNumber }) -join ', '
    @($unboundedJson).Count | Should -Be 0 -Because ("ConvertTo-Json calls must declare -Depth or use the governed @jsonArgs splat: {0}" -f $locations)
  }

  It 'bounds every executable Get-WinEvent command with MaxEvents' {
    $unboundedWinEvent = @($script:Commands | Where-Object {
      $_.GetCommandName() -ieq 'Get-WinEvent' -and -not (@(Get-DcoirCommandParameterNames -CommandAst $_) -icontains 'MaxEvents')
    })
    $locations = ($unboundedWinEvent | ForEach-Object { '{0}:{1}' -f $_.Extent.File, $_.Extent.StartLineNumber }) -join ', '
    @($unboundedWinEvent).Count | Should -Be 0 -Because ("Get-WinEvent calls must be bounded with -MaxEvents: {0}" -f $locations)
  }

  It 'keeps the wrapper declared with SupportsShouldProcess for WhatIf and confirmation behavior' {
    $parse = Get-DcoirParsedFile -Path $script:Layout.CollectorEntry
    $cmdletBinding = @($parse.Ast.ParamBlock.Attributes | Where-Object { [string]$_.TypeName.Name -ieq 'CmdletBinding' })
    @($cmdletBinding).Count | Should -Be 1
    $attributeText = [string]$cmdletBinding[0].Extent.Text
    $attributeText | Should -Match 'SupportsShouldProcess\s*=\s*\$true'
  }
}
