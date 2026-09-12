$ErrorActionPreference = 'Stop'

$source = Join-Path $env:GITHUB_WORKSPACE '.github/chatgpt_staging/exec_scripts/issue550-pr553-repair-consolidation-validation-001.ps1'
if (-not (Test-Path -LiteralPath $source)) { throw "Missing source validation script: $source" }
$text = [IO.File]::ReadAllText($source)

$oldEnv = @'
$repo = [Environment]::GetEnvironmentVariable('DCOIR_REPO_ROOT','Machine')
$downloads = [Environment]::GetEnvironmentVariable('DCOIR_DOWNLOADS_DIR','Machine')
if ([string]::IsNullOrWhiteSpace($repo)) { throw 'DCOIR_REPO_ROOT is unavailable' }
if ([string]::IsNullOrWhiteSpace($downloads)) { throw 'DCOIR_DOWNLOADS_DIR is unavailable' }
'@
$newEnv = @'
$repo = [Environment]::GetEnvironmentVariable('DCOIR_REPO_ROOT','Machine')
if ([string]::IsNullOrWhiteSpace($repo)) { $repo = $env:GITHUB_WORKSPACE }
if ([string]::IsNullOrWhiteSpace($repo)) { $repo = (Get-Location).Path }
$downloads = [Environment]::GetEnvironmentVariable('DCOIR_DOWNLOADS_DIR','Machine')
if ([string]::IsNullOrWhiteSpace($downloads)) { $downloads = $env:RUNNER_TEMP }
if ([string]::IsNullOrWhiteSpace($downloads)) { $downloads = [IO.Path]::GetTempPath() }
'@
if (-not $text.Contains($oldEnv)) { throw 'Expected runner-path block was not found in source validation script' }
$text = $text.Replace($oldEnv, $newEnv)

$hashHelper = @'
function Get-Sha256Hex {
    param([Parameter(Mandatory=$true)][string]$Path)
    $stream = [IO.File]::OpenRead($Path)
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '')
    }
    finally {
        $sha.Dispose()
        $stream.Dispose()
    }
}

'@
$text = $hashHelper + $text
$oldHash = '(Get-FileHash -Algorithm SHA256 -LiteralPath $requestPath).Hash'
if (([regex]::Matches($text, [regex]::Escape($oldHash))).Count -ne 2) { throw 'Expected exactly two Get-FileHash request-hash expressions' }
$text = $text.Replace($oldHash, '(Get-Sha256Hex -Path $requestPath)')

$text = $text.Replace('07cf4c1e11f833c7273d059c9a0fc367e9b4de53', 'de2bb9c23dc1c72c2e22b425e3a710a42bb75020')
$text = $text.Replace('issue550-pr553-repair-consolidation-validation-001.json', 'issue550-pr553-repair-consolidation-validation-005.json')
$text = $text.Replace('issue550-pr553-repair-consolidation-validation-001-summary.txt', 'issue550-pr553-repair-consolidation-validation-005-summary.txt')
$text = $text.Replace('ISSUE550_PR553_REPAIR_CONSOLIDATION_VALIDATION_PASS', 'ISSUE550_PR553_REPAIR_CONSOLIDATION_VALIDATION_005_PASS')

$tempRoot = if ([string]::IsNullOrWhiteSpace($env:RUNNER_TEMP)) { [IO.Path]::GetTempPath() } else { $env:RUNNER_TEMP }
$tempScript = Join-Path $tempRoot ('issue550-pr553-validation-005-' + [Guid]::NewGuid().ToString('N') + '.ps1')
try {
    [IO.File]::WriteAllText($tempScript, $text, [Text.UTF8Encoding]::new($false))
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $tempScript
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    Remove-Item -LiteralPath $tempScript -Force -ErrorAction SilentlyContinue
}
