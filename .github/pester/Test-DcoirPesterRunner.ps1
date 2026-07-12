[CmdletBinding()]
param(
  [Version]$MinimumPesterVersion = '5.0.0',
  [Version]$RequiredPesterVersion
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$runner = Join-Path $PSScriptRoot 'Invoke-DcoirPester.ps1'
$engine = Join-Path $PSHOME 'powershell.exe'
if (-not (Test-Path -LiteralPath $engine)) {
  $engine = (Get-Process -Id $PID).Path
}

$controlRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('dcoir-pester-runner-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $controlRoot | Out-Null

function Invoke-DcoirPesterControl {
  param(
    [string]$Name,
    [AllowNull()]
    [string]$TestText,
    [bool]$ExpectSuccess
  )

  $testRoot = Join-Path $controlRoot $Name
  $resultPath = Join-Path $testRoot 'result.xml'
  $logPath = Join-Path $testRoot 'runner.log'
  New-Item -ItemType Directory -Path $testRoot | Out-Null
  if ($null -ne $TestText) {
    Set-Content -LiteralPath (Join-Path $testRoot 'Control.Tests.ps1') -Value $TestText -Encoding UTF8
  }

  $previousErrorActionPreference = $ErrorActionPreference
  try {
    $ErrorActionPreference = 'Continue'
    $versionArgs = if ($null -ne $RequiredPesterVersion) { @('-RequiredPesterVersion', $RequiredPesterVersion) } else { @('-MinimumPesterVersion', $MinimumPesterVersion) }
    & $engine -NoLogo -NoProfile -ExecutionPolicy Bypass -File $runner -Path $testRoot @versionArgs -MinimumTestCount 1 -CI -TestResultOutputPath $resultPath 2>&1 | Set-Content -LiteralPath $logPath -Encoding UTF8
    $exitCode = $LASTEXITCODE
  } finally {
    $ErrorActionPreference = $previousErrorActionPreference
  }
  if ($ExpectSuccess -and $exitCode -ne 0) {
    throw "Pester runner control '$Name' should pass but exited $exitCode. Log: $logPath"
  }
  if (-not $ExpectSuccess -and $exitCode -eq 0) {
    throw "Pester runner control '$Name' should fail but exited zero. Log: $logPath"
  }
  if ($ExpectSuccess -and -not (Test-Path -LiteralPath $resultPath -PathType Leaf)) {
    throw "Pester runner control '$Name' did not create NUnit output: $resultPath"
  }
}

try {
  Invoke-DcoirPesterControl -Name pass -ExpectSuccess $true -TestText "Describe 'runner pass control' { It 'passes' { `$true | Should -BeTrue } }"
  Invoke-DcoirPesterControl -Name fail -ExpectSuccess $false -TestText "Describe 'runner failure control' { It 'fails' { `$true | Should -BeFalse } }"
  Invoke-DcoirPesterControl -Name empty -ExpectSuccess $false -TestText $null
  $global:LASTEXITCODE = 0
  Write-Host 'DCOIR Pester runner controls passed: pass, known-failure, and empty-discovery behavior.'
} finally {
  Remove-Item -LiteralPath $controlRoot -Recurse -Force -ErrorAction SilentlyContinue
}
