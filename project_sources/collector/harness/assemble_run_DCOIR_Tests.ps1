<#
.SYNOPSIS
Assembles the DCOIR collector harness from checked-in source parts.

.DESCRIPTION
Concatenates the ordered harness source parts into a generated run_DCOIR_Tests script.
This keeps the harness reviewable in smaller chunks while producing the runnable
harness used by validation workflows and direct operator runs.
#>

param(
  [string]$PartsDirectory = (Join-Path $PSScriptRoot 'source\parts'),
  [string]$OutputPath = (Join-Path $PSScriptRoot 'run_DCOIR_Tests.generated.ps1'),
  [string]$ExpectedSha256 = '',
  [string]$ExpectedHarnessPath = ''
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
function Get-NormalizedTextSha256 {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Text
  )

  $bytes = $utf8NoBom.GetBytes($Text)
  $sha256 = [System.Security.Cryptography.SHA256]::Create()
  try {
    return (($sha256.ComputeHash($bytes) | ForEach-Object { $_.ToString('x2') }) -join '')
  } finally {
    $sha256.Dispose()
  }
}

if (-not (Test-Path -LiteralPath $PartsDirectory)) {
  throw "Harness parts directory not found: $PartsDirectory"
}

$parts = @(Get-ChildItem -LiteralPath $PartsDirectory -File -Filter 'run_DCOIR_Tests.part-*.ps1' | Sort-Object Name)
if (@($parts).Count -eq 0) {
  throw "No harness parts found under: $PartsDirectory"
}

$outputDirectory = Split-Path -Parent $OutputPath
if (-not (Test-Path -LiteralPath $outputDirectory)) {
  New-Item -Path $outputDirectory -ItemType Directory -Force | Out-Null
}

$builder = New-Object System.Text.StringBuilder
$partDiagnostics = New-Object System.Collections.ArrayList
foreach ($part in $parts) {
  $text = [System.IO.File]::ReadAllText($part.FullName) -replace "`r`n", "`n" -replace "`r", "`n"
  [void]$builder.Append($text)
  if (-not $text.EndsWith("`n")) {
    [void]$builder.Append("`n")
  }
  $partHash = (Get-FileHash -LiteralPath $part.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
  [void]$partDiagnostics.Add(("{0} sha256={1} bytes={2}" -f $part.Name, $partHash, (Get-Item -LiteralPath $part.FullName).Length))
}

$assembledText = $builder.ToString()
[System.IO.File]::WriteAllText($OutputPath, $assembledText, $utf8NoBom)

$actualSha256 = (Get-FileHash -LiteralPath $OutputPath -Algorithm SHA256).Hash.ToLowerInvariant()
if (-not [string]::IsNullOrWhiteSpace($ExpectedSha256)) {
  if ($actualSha256 -ne $ExpectedSha256.ToLowerInvariant()) {
    $diagnosticText = ($partDiagnostics -join [Environment]::NewLine)
    throw ("Generated harness SHA256 mismatch. Expected {0} but got {1}. Parts used, in order:{2}{3}" -f $ExpectedSha256, $actualSha256, [Environment]::NewLine, $diagnosticText)
  }
}

if (-not [string]::IsNullOrWhiteSpace($ExpectedHarnessPath)) {
  if (-not (Test-Path -LiteralPath $ExpectedHarnessPath)) {
    throw "Expected comparison harness not found: $ExpectedHarnessPath"
  }
  $checkedInHarnessRawSha256 = (Get-FileHash -LiteralPath $ExpectedHarnessPath -Algorithm SHA256).Hash.ToLowerInvariant()
  $checkedInHarnessText = [System.IO.File]::ReadAllText($ExpectedHarnessPath) -replace "`r`n", "`n" -replace "`r", "`n"
  $checkedInHarnessNormalizedSha256 = Get-NormalizedTextSha256 -Text $checkedInHarnessText
  if ($actualSha256 -ne $checkedInHarnessNormalizedSha256) {
    $diagnosticText = ($partDiagnostics -join [Environment]::NewLine)
    throw ("Expected comparison harness mismatch after newline/encoding normalization. Generated {0} has normalized SHA256 {1}, but comparison harness {2} has normalized SHA256 {3} and raw file SHA256 {4}. Parts used, in order:{5}{6}" -f $OutputPath, $actualSha256, $ExpectedHarnessPath, $checkedInHarnessNormalizedSha256, $checkedInHarnessRawSha256, [Environment]::NewLine, $diagnosticText)
  }
  Write-Host ("CHECKED_IN_HARNESS_PATH={0}" -f (Resolve-Path -LiteralPath $ExpectedHarnessPath).Path)
  Write-Host ("CHECKED_IN_HARNESS_SHA256_NORMALIZED={0}" -f $checkedInHarnessNormalizedSha256)
  Write-Host ("CHECKED_IN_HARNESS_SHA256_RAW={0}" -f $checkedInHarnessRawSha256)
}

Write-Host ("ASSEMBLED_HARNESS_PATH={0}" -f (Resolve-Path -LiteralPath $OutputPath).Path)
Write-Host ("ASSEMBLED_HARNESS_SHA256={0}" -f $actualSha256)
Write-Host ("ASSEMBLED_HARNESS_PARTS={0}" -f @($parts).Count)
