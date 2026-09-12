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
$text = $text.Replace('07cf4c1e11f833c7273d059c9a0fc367e9b4de53', 'b03b94a43d019a054d361e2facef8f65b1b86cd6')
$text = $text.Replace('issue550-pr553-repair-consolidation-validation-001.json', 'issue550-pr553-repair-consolidation-validation-002.json')
$text = $text.Replace('issue550-pr553-repair-consolidation-validation-001-summary.txt', 'issue550-pr553-repair-consolidation-validation-002-summary.txt')
$text = $text.Replace('ISSUE550_PR553_REPAIR_CONSOLIDATION_VALIDATION_PASS', 'ISSUE550_PR553_REPAIR_CONSOLIDATION_VALIDATION_002_PASS')

$tempRoot = if ([string]::IsNullOrWhiteSpace($env:RUNNER_TEMP)) { [IO.Path]::GetTempPath() } else { $env:RUNNER_TEMP }
$tempScript = Join-Path $tempRoot ('issue550-pr553-validation-002-' + [Guid]::NewGuid().ToString('N') + '.ps1')
try {
    [IO.File]::WriteAllText($tempScript, $text, [Text.UTF8Encoding]::new($false))
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $tempScript
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    Remove-Item -LiteralPath $tempScript -Force -ErrorAction SilentlyContinue
}
